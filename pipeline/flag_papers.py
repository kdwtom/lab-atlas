"""Flag papers that may belong to a namesake (same-name researcher merged into the PI's profile).

For every qualifying lab, each paper is embedded with SPECTER and compared with the lab's centre
(normalised element-wise median of its analysis-set papers). Papers below FLAG_COSINE are written
to output/paper_flags.csv for manual review. Review decisions live in
curation/excluded_papers.csv and are applied by step 4 (papers) on the next collect run.
"""
from __future__ import annotations

import logging

import numpy as np

from . import config
from .lib.curation import excluded_papers
from .lib.io import read_json, write_csv
from .lib.selection import in_analysis_set, is_senior
from .step07_embed import embed, qualifying_papers

log = logging.getLogger(__name__)


def run(client=None) -> None:
    by_lab = qualifying_papers()
    vec = embed([p for ps in by_lab.values() for p in ps])
    names = {s["lab_id"]: s["name_ko"] or s["name_en"] for s in read_json(config.OUTPUT_DIR / "lab_status.json")}
    reviewed = excluded_papers()
    rows, all_cos = [], []
    for lid, ps in by_lab.items():
        core = [vec[p["id"]] for p in ps if in_analysis_set(p, lid)] or [vec[p["id"]] for p in ps]
        centre = np.median(np.stack(core), axis=0)
        centre /= np.linalg.norm(centre)
        for p in ps:
            c = float(vec[p["id"]] @ centre)
            all_cos.append(c)
            if c < config.FLAG_COSINE:
                rows.append({"lab_id": lid, "paper_id": p["id"], "pi_name": names.get(lid), "cosine": round(c, 3),
                             "senior": is_senior(p, lid), "home": in_analysis_set(p, lid), "year": p["year"],
                             "venue": p.get("venue") or "", "title": p["title"],
                             "already_excluded": (lid, p["id"]) in reviewed})
    rows.sort(key=lambda r: (r["pi_name"] or "", r["cosine"]))
    write_csv(config.OUTPUT_DIR / "paper_flags.csv", rows,
              ["lab_id", "paper_id", "pi_name", "cosine", "senior", "home", "year", "venue", "title",
               "already_excluded"])
    log.info("flagged %d of %d papers (cosine < %.2f; %.1f%%)", len(rows), len(all_cos), config.FLAG_COSINE,
             100 * len(rows) / max(len(all_cos), 1))
