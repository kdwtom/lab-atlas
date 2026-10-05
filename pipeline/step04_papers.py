"""Step 4 — collect each matched PI's works in the window and apply the selection criterion."""
from __future__ import annotations

import logging
from collections import Counter

from . import config
from .lib.curation import excluded_papers
from .lib.http import CachedClient
from .lib.io import read_json, write_json, write_jsonl
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


def venue(w: dict) -> str | None:
    src = ((w.get("primary_location") or {}).get("source") or {})
    return src.get("display_name")


def run(client: CachedClient) -> None:
    oa = OpenAlex(client)
    matches = [MatchResult(**m) for m in read_json(config.OUTPUT_DIR / "matches.json")]
    matched = [m for m in matches if m.status == "matched"]

    dup = [aid for aid, n in Counter(m.openalex_id for m in matched).items() if n > 1]
    if dup:
        log.warning("same OpenAlex author matched to several professors, excluding: %s", dup)
        for m in matched:
            if m.openalex_id in dup:
                m.status, m.reason = "excluded", "ambiguous_multiple_candidates"
                m.detail = "OpenAlex author matched to more than one professor"
        matched = [m for m in matched if m.status == "matched"]

    excluded = excluded_papers()  # reviewed namesake papers (curation/excluded_papers.csv)
    n_excluded = 0
    papers: dict[str, RawPaper] = {}
    statuses: list[LabStatus] = []
    for i, m in enumerate(matched, 1):
        lid = lab_id(m.univ, m.openalex_id)
        n_all = n_senior = n_abs = n_senior_abs = n_home = n_home_senior_abs = 0
        for w, day in oa.works_for_author(m.openalex_id, config.YEAR_FROM):
            if w.get("type") not in config.COUNTED_WORK_TYPES:
                continue
            year = w.get("publication_year")
            if not year or year < config.YEAR_FROM or year > config.YEAR_TO:
                continue
            authorships = w.get("authorships") or []
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
            lab_id=lid, univ=m.univ, name_ko=m.name_ko, name_en=m.name_en, openalex_id=m.openalex_id,
            paper_count_5y=n_all, senior_paper_count_5y=n_senior,
            meets_criterion=n_senior >= config.MIN_SENIOR_PAPERS,
            abstract_count=n_abs, senior_abstract_count=n_senior_abs,
            home_paper_count_5y=n_home, home_senior_abstract_count=n_home_senior_abs,
        ))
        log.info("[%d/%d] %s %s: %d papers (%d at home institution), %d senior", i, len(matched),
                 m.univ, m.name_ko or m.name_en, n_all, n_home, n_senior)

    write_json(config.OUTPUT_DIR / "matches.json", matches)  # persists duplicate exclusions
    write_json(config.OUTPUT_DIR / "lab_status.json", statuses)
    n = write_jsonl(config.OUTPUT_DIR / "papers_raw.jsonl", papers.values())
    log.info("papers stored: %d (window %d-%d); %d lab-paper pairs excluded after namesake review",
             n, config.YEAR_FROM, config.YEAR_TO, n_excluded)
