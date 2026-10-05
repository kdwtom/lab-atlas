"""Paper selection rules shared by analysis (stage 3) and export (stage 4).

All functions take raw paper dicts (papers_raw.jsonl rows) and a lab id.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from .. import config


def role(p: dict, lab_id: str) -> dict:
    return p["pi_roles"][lab_id]


def is_senior(p: dict, lab_id: str) -> bool:
    r = role(p, lab_id)
    return r["position"] == "last" or r["is_corresponding"]


def in_analysis_set(p: dict, lab_id: str) -> bool:
    """CP1 decision (option C): analysis uses only papers where the PI's authorship lists the
    matched institution or no institution (filters namesakes merged into OpenAlex profiles)."""
    return lab_id in p["pi_roles"] and role(p, lab_id).get("at_home_institution", True)


def pub_date(p: dict) -> date:
    try:
        return date.fromisoformat(p.get("publication_date") or "")
    except ValueError:
        return date(p["year"], 7, 1)


def embedding_papers(papers: list[dict], lab_id: str, limit: int = config.EMBED_MAX_PAPERS) -> list[dict]:
    """Most recent analysis papers, senior-author papers first (they define the lab's own agenda)."""
    own = [p for p in papers if in_analysis_set(p, lab_id)]
    own.sort(key=lambda p: (is_senior(p, lab_id), pub_date(p)), reverse=True)
    return own[:limit]


def citations_per_year(p: dict, today: Optional[date] = None) -> float:
    today = today or config.TODAY
    years = max((today - pub_date(p)).days / 365.25, 1.0)
    return p["cited_by_count"] / years


def representative_papers(papers: list[dict], lab_id: str, n: int = config.REPRESENTATIVE_PAPERS,
                          today: Optional[date] = None) -> list[dict]:
    """Candidates: analysis set + PI last/corresponding author + abstract available.
    Ranked by citations per year since publication; at least one paper from the last
    RECENT_PAPER_YEARS calendar years is included when such a candidate exists."""
    today = today or config.TODAY
    cands = [p for p in papers if in_analysis_set(p, lab_id) and is_senior(p, lab_id) and p.get("abstract")]
    cands.sort(key=lambda p: (citations_per_year(p, today), p["cited_by_count"], pub_date(p)), reverse=True)
    top = cands[:n]
    recent_from = today.year - config.RECENT_PAPER_YEARS + 1
    if top and not any(p["year"] >= recent_from for p in top):
        recent = next((p for p in cands[n:] if p["year"] >= recent_from), None)
        if recent:
            top = top[: n - 1] + [recent] if len(top) == n else top + [recent]
    return top
