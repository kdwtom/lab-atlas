"""Step 3 — match each professor to one OpenAlex author (principle 3: avoid namesakes).

Evidence per candidate (all from API responses):
  affiliation  : institution appears in author.affiliations within recent years
  name         : English-name token match (order/hyphen-insensitive) or Korean surname romanisation
  topic        : share of author's top topics in the department field's OpenAlex domains
  anchors      : # of publications listed on the faculty page that this author wrote
  orcid        : ORCID on the faculty page equals the author's ORCID
Anything uncertain is excluded and written to excluded.csv.

Candidates come from an OpenAlex name search per professor (departments with matching: search) or from
the institution's author roster (matching: roster, PLAN_PHASE1.md 0-4); the decision rules are the same.
Roster departments add two tie-breaks for several strong candidates (roster_tiebreak): profiles sharing one
ORCID are the same person, and a PI is the candidate who actually leads papers (the field's selection count).
"""
from __future__ import annotations

import logging
from typing import Optional

from rapidfuzz import fuzz

from . import config
from .lib.http import CachedClient, QuotaExceeded
from .lib.io import read_json, write_json
from .lib.names import given_name_compatible, names_compatible, search_variants, surname_compatible
from .lib.openalex import OpenAlex, short_id
from .lib.roster import Roster, load as load_roster
from .lib.textutil import norm_title, title_from_citation
from .schemas import CandidateEvidence, FacultyRecord, MatchResult

log = logging.getLogger(__name__)


# ------------------------------------------------------------------ evidence helpers
def affiliation_years(author: dict, inst_id: str) -> list[int]:
    years: set[int] = set()
    for aff in author.get("affiliations") or []:
        if short_id((aff.get("institution") or {}).get("id")) == inst_id:
            years.update(aff.get("years") or [])
    return sorted(years)


def affiliation_ok(author: dict, inst_id: str) -> bool:
    yrs = affiliation_years(author, inst_id)
    if yrs and max(yrs) >= config.YEAR_TO - config.CURRENT_AFFILIATION_YEARS:
        return True
    for inst in author.get("last_known_institutions") or []:
        if short_id(inst.get("id")) == inst_id:
            return True
    return False


def field_share(author: dict, domains: tuple[str, ...] = ("Life Sciences",), top_n: int = 10,
                fields: tuple[str, ...] | None = None) -> float:
    """Share of the author's top topics inside the given OpenAlex fields (if any) or domains."""
    topics = (author.get("topics") or [])[:top_n]
    total = sum(t.get("count") or 1 for t in topics)
    if not total:
        return 0.0
    level, names = ("field", fields) if fields else ("domain", domains)
    inside = sum((t.get("count") or 1) for t in topics if ((t.get(level) or {}).get("display_name") in names))
    return round(inside / total, 3)


def all_names(author: dict) -> list[str]:
    return [author.get("display_name") or ""] + list(author.get("display_name_alternatives") or [])


def name_check(fac: FacultyRecord, author: dict, anchor_hits: int, roster_mode: bool = False) -> tuple[bool, str]:
    # Merged OpenAlex profiles carry noisy display_name_alternatives (other people's names), so an
    # alternative-only match counts only when faculty-page publications confirm the profile.
    names = all_names(author) if anchor_hits >= 1 else [author.get("display_name") or ""]
    if fac.name_en:
        if any(names_compatible(fac.name_en, n) for n in names if n):
            return True, "english name match"
        return False, f"'{fac.name_en}' vs '{author.get('display_name')}'"
    sur_ok = [n for n in names if n and surname_compatible(fac.name_ko, n) is True]
    if sur_ok:
        gv = [given_name_compatible(fac.name_ko, n) for n in sur_ok]
        if any(v is True for v in gv):
            # roster mode: the institution roster is the candidate pool, so a full romanisation match of
            # the display name is accepted without anchors; decide() still requires a single strong candidate
            return (anchor_hits >= 1 or roster_mode,
                    f"surname+given-name romanisation match, anchors={anchor_hits}" + (", roster" if roster_mode else ""))
        if any(v is None for v in gv):
            # given name not judgeable (initials only); surname alone is weak
            return (anchor_hits >= 2, f"surname match, anchors={anchor_hits}")
        return False, f"given name of '{fac.name_ko}' not in '{author.get('display_name')}'"
    sc = [surname_compatible(fac.name_ko, n) for n in names if n]
    if all(v is None for v in sc):
        return (anchor_hits >= 3, f"surname not judgeable, anchors={anchor_hits}")
    return False, f"surname of '{fac.name_ko}' not in '{author.get('display_name')}'"


# ------------------------------------------------------------------ anchors
def anchor_authors(oa: OpenAlex, fac: FacultyRecord, inst_id: str,
                   max_papers: int = config.MAX_ANCHOR_PAPERS) -> tuple[dict[str, int], int]:
    """Return {author_id: hits} for authors of faculty-page publications, and #anchors resolved."""
    hits: dict[str, int] = {}
    resolved = 0
    for cit in fac.anchor_citations[:max_papers]:
        title = title_from_citation(cit)
        if len(norm_title(title)) < 15:
            continue
        ncit = norm_title(cit)
        for w in oa.search_works_by_title(title):
            wt = norm_title(w.get("display_name") or "")
            if len(wt) < 20 or fuzz.partial_ratio(wt, ncit) < config.ANCHOR_TITLE_SIMILARITY:
                continue
            resolved += 1
            for au in w.get("authorships") or []:
                aid = short_id((au.get("author") or {}).get("id"))
                if not aid:
                    continue
                at_inst = any(short_id(i.get("id")) == inst_id for i in au.get("institutions") or [])
                dn = (au.get("author") or {}).get("display_name") or ""
                if fac.name_en:
                    plausible = names_compatible(fac.name_en, dn)
                else:
                    plausible = (at_inst and surname_compatible(fac.name_ko, dn) is not False
                                 and given_name_compatible(fac.name_ko, dn) is not False)
                if plausible:
                    hits[aid] = hits.get(aid, 0) + 1
            break  # first verified work per citation
    return hits, resolved


# ------------------------------------------------------------------ main logic
def discipline_of(fac: FacultyRecord) -> config.Discipline:
    d = config.DEPT_BY_CODE.get(fac.dept)
    return d.disc if d else config.DISCIPLINES["life"]


def evaluate(fac: FacultyRecord, author: dict, inst_id: str, hits: dict[str, int]) -> CandidateEvidence:
    aid = short_id(author["id"])
    n_anchor = hits.get(aid, 0)
    dept = config.DEPT_BY_CODE.get(fac.dept)
    ok_name, note = name_check(fac, author, n_anchor, roster_mode=bool(dept and dept.matching == "roster"))
    disc = discipline_of(fac)
    share = field_share(author, disc.topic_domains, fields=disc.topic_fields)
    orcid = (author.get("orcid") or "").rsplit("/", 1)[-1] or None
    ev = CandidateEvidence(
        openalex_id=aid, display_name=author.get("display_name") or "", orcid=orcid,
        works_count=author.get("works_count") or 0,
        affiliation_ok=affiliation_ok(author, inst_id),
        affiliation_years=affiliation_years(author, inst_id)[-6:],
        name_ok=ok_name, name_note=note, field_share=share,
        topic_ok=share >= config.TOPIC_SHARE, anchor_hits=n_anchor,
        orcid_match=(orcid == fac.orcid) if (fac.orcid and orcid) else None,
    )
    ev.strong = ev.affiliation_ok and ev.name_ok and (ev.topic_ok or ev.anchor_hits >= 1)
    return ev


def decide(fac: FacultyRecord, cands: list[CandidateEvidence]) -> tuple[Optional[CandidateEvidence], Optional[str], str]:
    """Return (chosen, exclude_reason, detail)."""
    if fac.orcid:
        by_orcid = [c for c in cands if c.orcid_match]
        if len(by_orcid) == 1 and by_orcid[0].affiliation_ok:
            return by_orcid[0], None, "ORCID on faculty page"
    strong = [c for c in cands if c.strong]
    if len(strong) == 1:
        return strong[0], None, "single strong candidate"
    if len(strong) > 1:
        anchored = [c for c in strong if c.anchor_hits > 0]
        if len(anchored) == 1:
            return anchored[0], None, "only candidate confirmed by faculty-page publications"
        if anchored:
            top, *others = sorted(anchored, key=lambda c: c.anchor_hits, reverse=True)
            if top.anchor_hits >= 3 and all(top.anchor_hits >= 2 * c.anchor_hits for c in others):
                return top, None, ("dominant author of faculty-page publications "
                                   f"({top.anchor_hits} vs {max(c.anchor_hits for c in others)})")
        big = max(strong, key=lambda c: c.works_count)
        rest = [c for c in strong if c is not big]
        conflict = any(c.orcid and big.orcid and c.orcid != big.orcid for c in rest)
        if not conflict and all(c.works_count <= config.SPLIT_PROFILE_RATIO * max(big.works_count, 1)
                                for c in rest):
            return big, None, ("largest of likely split OpenAlex profiles; ignored: "
                               + ",".join(c.openalex_id for c in rest))
        return None, "ambiguous_multiple_candidates", f"{len(strong)} strong candidates"
    if not cands:
        if not fac.name_en and not fac.anchor_citations:
            return None, "no_english_name_no_anchor", "no English name and no publications on page"
        return None, "no_candidate", "no OpenAlex author found at this institution"
    if not any(c.affiliation_ok for c in cands):
        return None, "affiliation_mismatch", "no candidate with recent affiliation to the institution"
    if not any(c.affiliation_ok and c.name_ok for c in cands):
        return None, "name_mismatch", "affiliated candidates do not match the name"
    disc = discipline_of(fac)
    field = "life sciences" if disc.code == "life" else f"the {disc.code} field"
    return None, "topic_mismatch", f"affiliated, name-matching candidates are outside {field}"


def pi_paper_count(oa: OpenAlex, author_id: str, disc: config.Discipline) -> int:
    """Papers in the window that count toward the field's selection rule (same rule as step 4)."""
    from .step04_papers import alphabetical

    n = 0
    for w, _ in oa.works_for_author(author_id, config.YEAR_FROM):
        year = w.get("publication_year")
        if w.get("type") not in disc.work_types or not year or not config.YEAR_FROM <= year <= config.YEAR_TO:
            continue
        au = w.get("authorships") or []
        if disc.max_authors and len(au) >= disc.max_authors:
            continue
        mine = next((a for a in au if short_id((a.get("author") or {}).get("id")) == author_id), None)
        if not mine:
            continue
        senior = mine.get("author_position") == "last" or bool(mine.get("is_corresponding"))
        n += senior or disc.position_agnostic or (disc.alphabetical_counts and alphabetical(au))
    return n


def roster_tiebreak(oa: OpenAlex, fac: FacultyRecord, cands: list[CandidateEvidence]
                    ) -> tuple[Optional[CandidateEvidence], str]:
    strong = [c for c in cands if c.strong]
    orcids = {c.orcid for c in strong}
    if len(orcids) == 1 and None not in orcids:
        big = max(strong, key=lambda c: c.works_count)
        return big, f"split OpenAlex profiles with one ORCID; largest chosen ({big.works_count} works)"
    disc = discipline_of(fac)
    counts = {c.openalex_id: pi_paper_count(oa, c.openalex_id, disc) for c in strong}
    for c in strong:
        c.pi_papers = counts[c.openalex_id]
    top, *rest = sorted(strong, key=lambda c: counts[c.openalex_id], reverse=True)
    best = counts[top.openalex_id]
    if best >= disc.min_papers and all(best >= 3 * counts[c.openalex_id] for c in rest):
        return top, ("only candidate leading papers in the window "
                     f"({best} vs {', '.join(str(counts[c.openalex_id]) for c in rest)})")
    return None, f"{len(strong)} strong candidates; papers led {sorted(counts.values(), reverse=True)}"


def match_one(oa: OpenAlex, fac: FacultyRecord, inst_id: str, roster: Optional[Roster] = None) -> MatchResult:
    dept = config.DEPT_BY_CODE[fac.dept]
    authors: dict[str, dict] = {}
    if roster is not None:
        for a in roster.candidates(fac.name_en, fac.name_ko):
            authors.setdefault(short_id(a["id"]), a)
    if fac.name_en and not authors:  # search mode, or nobody in the roster: OpenAlex name search
        queries = search_variants(fac.name_en)
        toks = fac.name_en.replace(",", " ").split()
        if not fac.name_ko and len(toks) >= 3:  # foreign faculty: "Robert James Mitchell" -> "Robert Mitchell"
            queries.append(f"{toks[0]} {toks[-1]}")
        for q in queries:
            for a in oa.search_authors(q, inst_id):
                authors.setdefault(short_id(a["id"]), a)
    # roster mode reads faculty-page publications only when the page gives no English name
    use_anchors = bool(fac.anchor_citations) and (roster is None or not fac.name_en)
    hits, _resolved = anchor_authors(oa, fac, inst_id, dept.max_anchor_papers) if use_anchors else ({}, 0)
    for aid in hits:
        if aid not in authors:
            full, _ = oa.author(aid)
            if full:
                authors[aid] = full
    # keep only plausible candidates (name-compatible or anchored) to keep evidence readable
    cands = [evaluate(fac, a, inst_id, hits) for a in authors.values()]
    cands = [c for c in cands if c.name_ok or c.anchor_hits or c.affiliation_ok]
    cands.sort(key=lambda c: (c.strong, c.anchor_hits, c.affiliation_ok, c.works_count), reverse=True)
    chosen, reason, detail = decide(fac, cands)
    if roster is not None and reason == "ambiguous_multiple_candidates":
        picked, why = roster_tiebreak(oa, fac, cands)
        if picked:
            chosen, reason, detail = picked, None, why
        else:
            detail = why
    base = dict(univ=fac.univ, dept=fac.dept, name_ko=fac.name_ko, name_en=fac.name_en,
                faculty_page_url=fac.faculty_page_url, candidates=cands[:8],
                institution_id=inst_id, retrieved_at=config.TODAY)
    if chosen:
        conf = "high" if (chosen.orcid_match or chosen.anchor_hits >= 1) else "medium"
        return MatchResult(status="matched", openalex_id=chosen.openalex_id, confidence=conf,
                           detail=detail, **base)
    return MatchResult(status="excluded", reason=reason, detail=detail, **base)


def run(client: CachedClient) -> None:
    oa = OpenAlex(client)
    inst = read_json(config.OUTPUT_DIR / "institutions.json")
    faculty = [FacultyRecord(**r) for r in read_json(config.OUTPUT_DIR / "faculty.json")]
    rosters: dict[str, Roster] = {}

    def roster_for(fac: FacultyRecord) -> Optional[Roster]:
        if config.DEPT_BY_CODE[fac.dept].matching != "roster":
            return None
        iid = inst[fac.univ]["id"]
        if iid not in rosters:
            rosters[iid] = Roster(load_roster(oa, iid)[0])
        return rosters[iid]

    results: list[MatchResult] = []
    for i, fac in enumerate(faculty, 1):
        label = f"{fac.dept} {fac.name_ko or ''} {fac.name_en or ''}".strip()
        if not fac.is_full_time:
            results.append(MatchResult(
                univ=fac.univ, dept=fac.dept, name_ko=fac.name_ko, name_en=fac.name_en,
                faculty_page_url=fac.faculty_page_url, status="excluded", reason="not_full_time",
                detail=f"position: {fac.position_raw}", retrieved_at=config.TODAY))
            continue
        roster = roster_for(fac)  # a failed roster download aborts the step instead of excluding professors
        try:
            r = match_one(oa, fac, inst[fac.univ]["id"], roster)
        except QuotaExceeded:
            raise  # never record a quota stop as an exclusion
        except Exception as e:
            log.exception("match failed for %s", label)
            r = MatchResult(univ=fac.univ, dept=fac.dept, name_ko=fac.name_ko, name_en=fac.name_en,
                            faculty_page_url=fac.faculty_page_url, status="excluded",
                            reason="no_candidate", detail=f"error: {e}", retrieved_at=config.TODAY)
        results.append(r)
        log.info("[%d/%d] %s -> %s %s", i, len(faculty), label, r.status, r.openalex_id or r.reason)
    write_json(config.OUTPUT_DIR / "matches.json", results)
