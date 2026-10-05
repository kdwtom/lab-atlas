"""Hand-curated inputs under pipeline/curation/ (reviewed decisions, not generated data)."""
from __future__ import annotations

import csv

from .. import config

EXCLUDED_PAPERS = config.PIPELINE_DIR / "curation" / "excluded_papers.csv"
EXCLUDED_FIELDS = ["lab_id", "paper_id", "pi_name", "title", "cosine", "reason"]


def excluded_papers() -> set[tuple[str, str]]:
    """{(lab_id, paper_id)} confirmed during review as a namesake's paper merged into the PI's profile."""
    if not EXCLUDED_PAPERS.exists():
        return set()
    with EXCLUDED_PAPERS.open(encoding="utf-8-sig") as f:
        return {(r["lab_id"], r["paper_id"]) for r in csv.DictReader(f)}
