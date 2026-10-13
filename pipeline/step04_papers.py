"""Step 4 — collect each matched PI's works in the window and apply the selection criterion.

A professor listed by two departments of the same university is one lab (all departments kept); the
first department in departments.yaml decides which field's selection rule applies (config.DISCIPLINES).
"""
from __future__ import annotations

import logging

from . import config
from .lib.curation import excluded_papers
from .lib.http import CachedClient
from .lib.io import read_json, write_json, write_jsonl
from .lib.names import name_tokens, names_compatible
from .lib.openalex import OpenAlex, short_id
from .lib.textutil import reconstruct_abstract
from .schemas import LabStatus, MatchResult, PiRole, RawPaper, Topic

log = logging.getLogger(__name__)


def lab_id(univ: str, author_id: str) -> str:
    return f"{univ}-{author_id}"


def to_topics(w: dict) -> list[Topic]:
    out = []
    for t in (w.get("topics") or [])[:5]:
        out.append(Topic(
            id=short_id(t.get("id")) or "", name=t.get("display_name") or "",
            score=float(t.get("score") or 0),
            subfield=(t.get("subfield") or {}).get("display_name"),
            field=(t.get("field") or {}).get("display_name"),
            domain=(t.get("domain") or {}).get("display_name"),
        ))
    return out


def alphabetical(authorships: list[dict]) -> bool:
    """>= 3 authors listed in alphabetical order of surname (convention in mathematics / theory CS)."""
    surnames = []
    for a in authorships:
        toks = name_tokens((a.get("author") or {}).get("display_name") or "")
        if not toks:
            return False
        surnames.append(toks[-1])
    return len(surnames) >= 3 and surnames == sorted(surnames)


def same_person(a: MatchResult, b: MatchResult, emails: dict[str, str]) -> bool:
    """Joint appointment = the same e-mail on both faculty pages, or the same Korean name and compatible
    English names. A shared Korean name alone is not enough (two professors can share one)."""
    ea, eb = emails.get(a.faculty_page_url), emails.get(b.faculty_page_url)
    if ea and eb:
        return ea == eb
    if a.name_en and b.name_en and names_compatible(a.name_en, b.name_en):
        return not (a.name_ko and b.name_ko) or a.name_ko == b.name_ko
    return False


def group_labs(matched: list[MatchResult], emails: dict[str, str] | None = None
               ) -> tuple[list[list[MatchResult]], list[MatchResult]]:
    """Group matches by OpenAlex author. The same person listed by several departments of one university
    becomes one lab. An author matched to different people is a namesake conflict: when exactly one of them
    was matched through an English name and the others only through a Korean name, the English-name match
    is kept; otherwise all are excluded. Matches at different universities are always excluded."""
    emails = emails or {}
    order = {d.code: i for i, d in enumerate(config.DEPARTMENTS)}
    by_aid: dict[str, list[MatchResult]] = {}
    for m in matched:
        by_aid.setdefault(m.openalex_id, []).append(m)
    groups, conflicts = [], []
    for aid, ms in by_aid.items():
        ms.sort(key=lambda m: order[m.dept])
        if len({m.univ for m in ms}) > 1:
            conflicts += ms
            continue
        people: list[list[MatchResult]] = []
        for m in ms:
            home = next((p for p in people if same_person(p[0], m, emails)), None)
            if home:
                home.append(m)
            else:
                people.append([m])
        if len(people) == 1:
            groups.append(people[0])
            continue
        english = [p for p in people if any(m.name_en for m in p)]
        if len(english) == 1:
            groups.append(english[0])
            conflicts += [m for p in people if p is not english[0] for m in p]
        else:
            conflicts += ms
    return groups, conflicts


def venue(w: dict) -> str | None:
    src = ((w.get("primary_location") or {}).get("source") or {})
    return src.get("display_name")


def run(client: CachedClient) -> None:
    oa = OpenAlex(client)
    matches = [MatchResult(**m) for m in read_json(config.OUTPUT_DIR / "matches.json")]
    matched = [m for m in matches if m.status == "matched"]

    emails = {f["faculty_page_url"]: f["email"] for f in read_json(config.OUTPUT_DIR / "faculty.json")
              if f.get("email") and f["faculty_page_url"] != f["faculty_list_url"]}  # list pages are shared
    groups, conflicts = group_labs(matched, emails)
    if conflicts:
        log.warning("same OpenAlex author matched to several professors, excluding: %s",
                    sorted({m.openalex_id for m in conflicts}))
        for m in conflicts:
            m.status, m.reason = "excluded", "ambiguous_multiple_candidates"
            m.detail = "OpenAlex author matched to more than one professor"
    merged = [g for g in groups if len(g) > 1]
    if merged:
        log.info("professors listed by several departments (one lab each): %d", len(merged))

    excluded = excluded_papers()  # reviewed namesake papers (curation/excluded_papers.csv)
    n_excluded = 0
    papers: dict[str, RawPaper] = {}
    statuses: list[LabStatus] = []
    for i, group in enumerate(groups, 1):
        m = group[0]
        disc = config.DEPT_BY_CODE[m.dept].disc
        lid = lab_id(m.univ, m.openalex_id)
        n_all = n_senior = n_abs = n_senior_abs = n_home = n_home_senior_abs = 0
        for w, day in oa.works_for_author(m.openalex_id, config.YEAR_FROM):
            if w.get("type") not in disc.work_types:
                continue
            year = w.get("publication_year")
            if not year or year < config.YEAR_FROM or year > config.YEAR_TO:
                continue
            authorships = w.get("authorships") or []
            if disc.max_authors and len(authorships) >= disc.max_authors:
                continue  # large collaboration: not the lab's own agenda (phys, cs)
            mine = next((a for a in authorships
                         if short_id((a.get("author") or {}).get("id")) == m.openalex_id), None)
            if not mine:
                continue
            if (lid, short_id(w["id"])) in excluded:
                n_excluded += 1
                continue
            insts = {short_id(x.get("id")) for x in mine.get("institutions") or []}
            role = PiRole(position=mine.get("author_position") or "middle",
                          is_corresponding=bool(mine.get("is_corresponding")),
                          at_home_institution=not insts or m.institution_id in insts)
            senior = role.position == "last" or role.is_corresponding
            if not senior and (disc.position_agnostic or (disc.alphabetical_counts and alphabetical(authorships))):
                role.order_agnostic = senior = True
            wid = short_id(w["id"])
            abstract = reconstruct_abstract(w.get("abstract_inverted_index"))
            n_all += 1
            n_senior += senior
            n_abs += abstract is not None
            n_senior_abs += senior and abstract is not None
            n_home += role.at_home_institution
            n_home_senior_abs += role.at_home_institution and senior and abstract is not None
            if wid in papers:
                p = papers[wid]
                if lid not in p.lab_ids:
                    p.lab_ids.append(lid)
                p.pi_roles[lid] = role
                continue
            coauthors = [short_id((a.get("author") or {}).get("id")) for a in authorships]
            papers[wid] = RawPaper(
                id=wid, lab_ids=[lid], title=w.get("display_name") or "(제목 없음)", year=year,
                publication_date=w.get("publication_date"), venue=venue(w), doi=w.get("doi"),
                cited_by_count=w.get("cited_by_count") or 0, type=w.get("type"),
                pi_roles={lid: role}, abstract=abstract, topics=to_topics(w),
                coauthor_ids=[c for c in coauthors if c and c != m.openalex_id],
                openalex_url=w["id"], retrieved_at=day,
            )
        statuses.append(LabStatus(
            lab_id=lid, univ=m.univ, depts=[g.dept for g in group], discipline=disc.code,
            name_ko=m.name_ko, name_en=m.name_en, openalex_id=m.openalex_id,
            paper_count_5y=n_all, senior_paper_count_5y=n_senior,
            meets_criterion=n_senior >= disc.min_papers,
            abstract_count=n_abs, senior_abstract_count=n_senior_abs,
            home_paper_count_5y=n_home, home_senior_abstract_count=n_home_senior_abs,
        ))
        log.info("[%d/%d] %s %s: %d papers (%d at home institution), %d senior", i, len(groups),
                 "+".join(g.dept for g in group), m.name_ko or m.name_en, n_all, n_home, n_senior)

    write_json(config.OUTPUT_DIR / "matches.json", matches)  # persists duplicate exclusions
    write_json(config.OUTPUT_DIR / "lab_status.json", statuses)
    n = write_jsonl(config.OUTPUT_DIR / "papers_raw.jsonl", papers.values())
    log.info("papers stored: %d (window %d-%d); %d lab-paper pairs excluded after namesake review",
             n, config.YEAR_FROM, config.YEAR_TO, n_excluded)
