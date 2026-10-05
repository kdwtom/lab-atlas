"""Step 3 — match each professor to one OpenAlex author (principle 3: avoid namesakes).

Evidence per candidate (all from API responses):
  affiliation  : institution appears in author.affiliations within recent years
  name         : English-name token match (order/hyphen-insensitive) or Korean surname romanisation
  topic        : share of author's top topics in the Life Sciences domain
  anchors      : # of publications listed on the faculty page that this author wrote
  orcid        : ORCID on the faculty page equals the author's ORCID
Anything uncertain is excluded and written to excluded.csv.
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


def life_sci_share(author: dict, top_n: int = 10) -> float:
    topics = (author.get("topics") or [])[:top_n]
    total = sum(t.get("count") or 1 for t in topics)
    if not total:
        return 0.0
    life = sum((t.get("count") or 1) for t in topics
               if ((t.get("domain") or {}).get("display_name") == "Life Sciences"))
    return round(life / total, 3)


def all_names(author: dict) -> list[str]:
    return [author.get("display_name") or ""] + list(author.get("display_name_alternatives") or [])


def name_check(fac: FacultyRecord, author: dict, anchor_hits: int) -> tuple[bool, str]:
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
            return (anchor_hits >= 1, f"surname+given-name romanisation match, anchors={anchor_hits}")
        if any(v is None for v in gv):
            # given name not judgeable (initials only); surname alone is weak
            return (anchor_hits >= 2, f"surname match, anchors={anchor_hits}")
        return False, f"given name of '{fac.name_ko}' not in '{author.get('display_name')}'"
    sc = [surname_compatible(fac.name_ko, n) for n in names if n]
    if all(v is None for v in sc):
        return (anchor_hits >= 3, f"surname not judgeable, anchors={anchor_hits}")
    return False, f"surname of '{fac.name_ko}' not in '{author.get('display_name')}'"


# ------------------------------------------------------------------ anchors
def anchor_authors(oa: OpenAlex, fac: FacultyRecord, inst_id: str) -> tuple[dict[str, int], int]:
    """Return {author_id: hits} for authors of faculty-page publications, and #anchors resolved."""
    hits: dict[str, int] = {}
    resolved = 0
    for cit in fac.anchor_citations[: config.MAX_ANCHOR_PAPERS]:
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
def evaluate(fac: FacultyRecord, author: dict, inst_id: str, hits: dict[str, int]) -> CandidateEvidence:
    aid = short_id(author["id"])
    n_anchor = hits.get(aid, 0)
    ok_name, note = name_check(fac, author, n_anchor)
    share = life_sci_share(author)
    orcid = (author.get("orcid") or "").rsplit("/", 1)[-1] or None
    ev = CandidateEvidence(
        openalex_id=aid, display_name=author.get("display_name") or "", orcid=orcid,
        works_count=author.get("works_count") or 0,
        affiliation_ok=affiliation_ok(author, inst_id),
        affiliation_years=affiliation_years(author, inst_id)[-6:],
        name_ok=ok_name, name_note=note, life_sci_share=share,
        topic_ok=share >= config.LIFE_SCI_TOPIC_SHARE, anchor_hits=n_anchor,
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
    return None, "topic_mismatch", "affiliated, name-matching candidates are outside life sciences"


def match_one(oa: OpenAlex, fac: FacultyRecord, inst_id: str) -> MatchResult:
    authors: dict[str, dict] = {}
    if fac.name_en:
        queries = search_variants(fac.name_en)
        toks = fac.name_en.replace(",", " ").split()
        if not fac.name_ko and len(toks) >= 3:  # foreign faculty: "Robert James Mitchell" -> "Robert Mitchell"
            queries.append(f"{toks[0]} {toks[-1]}")
        for q in queries:
            for a in oa.search_authors(q, inst_id):
                authors.setdefault(short_id(a["id"]), a)
    hits, _resolved = anchor_authors(oa, fac, inst_id) if fac.anchor_citations else ({}, 0)
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
    base = dict(univ=fac.univ, name_ko=fac.name_ko, name_en=fac.name_en,
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
    results: list[MatchResult] = []
    for i, fac in enumerate(faculty, 1):
        label = f"{fac.univ} {fac.name_ko or ''} {fac.name_en or ''}".strip()
        if not fac.is_full_time:
            results.append(MatchResult(
                univ=fac.univ, name_ko=fac.name_ko, name_en=fac.name_en,
                faculty_page_url=fac.faculty_page_url, status="excluded", reason="not_full_time",
                detail=f"position: {fac.position_raw}", retrieved_at=config.TODAY))
            continue
        try:
            r = match_one(oa, fac, inst[fac.univ]["id"])
        except QuotaExceeded:
            raise  # never record a quota stop as an exclusion
        except Exception as e:
            log.exception("match failed for %s", label)
            r = MatchResult(univ=fac.univ, name_ko=fac.name_ko, name_en=fac.name_en,
                            faculty_page_url=fac.faculty_page_url, status="excluded",
                            reason="no_candidate", detail=f"error: {e}", retrieved_at=config.TODAY)
        results.append(r)
        log.info("[%d/%d] %s -> %s %s", i, len(faculty), label, r.status, r.openalex_id or r.reason)
    write_json(config.OUTPUT_DIR / "matches.json", results)
