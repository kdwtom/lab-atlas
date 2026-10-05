"""Step 9 — choose representative papers and write summary-writing tasks.

Representative papers (lib/selection.representative_papers): analysis set + PI last/corresponding
author + abstract available; ranked by citations per year since publication; at least one paper
from the last RECENT_PAPER_YEARS years.

Outputs
  output/representatives.json            {lab_id: [paper ids]}
  output/summary_tasks/batch_NN.md       abstracts + TLDRs + lab context, read by the summary writer
Korean summaries are written by hand into curation/summaries/batch_NN.json and curation/lab_intros.json.
"""
from __future__ import annotations

import logging
from collections import defaultdict

from . import config
from .lib.io import read_json, read_jsonl, write_json
from .lib.selection import in_analysis_set, is_senior, pub_date, representative_papers

log = logging.getLogger(__name__)
LABS_PER_BATCH = 10
TASK_DIR = config.OUTPUT_DIR / "summary_tasks"


def run(client=None) -> None:
    analysis = read_json(config.OUTPUT_DIR / "analysis.json")
    status = {s["lab_id"]: s for s in read_json(config.OUTPUT_DIR / "lab_status.json")}
    by_lab = defaultdict(list)
    for p in read_jsonl(config.OUTPUT_DIR / "papers_raw.jsonl"):
        for lid in p["lab_ids"]:
            if lid in analysis["labs"]:
                by_lab[lid].append(p)
    lab_ids = sorted(analysis["labs"], key=lambda l: (status[l]["univ"], status[l]["name_ko"] or status[l]["name_en"]))

    reps = {lid: representative_papers(by_lab[lid], lid) for lid in lab_ids}
    write_json(config.OUTPUT_DIR / "representatives.json", {l: [p["id"] for p in ps] for l, ps in reps.items()})

    TASK_DIR.mkdir(parents=True, exist_ok=True)
    for f in TASK_DIR.glob("batch_*.md"):
        f.unlink()
    for b in range(0, len(lab_ids), LABS_PER_BATCH):
        lines = []
        for lid in lab_ids[b:b + LABS_PER_BATCH]:
            s = status[lid]
            senior = sorted((p for p in by_lab[lid] if in_analysis_set(p, lid) and is_senior(p, lid)),
                            key=pub_date, reverse=True)
            lines += [f"# LAB {lid} | {s['name_ko']} / {s['name_en']} | keywords: "
                      + "; ".join(analysis["labs"][lid]["keywords"]),
                      "## recent last/corresponding-author titles (for the lab intro)"]
            lines += [f"- ({p['year']}) {p['title']}" for p in senior[:12]]
            for p in reps[lid]:
                lines += [f"## PAPER {p['id']} ({p['year']}, {p.get('venue')}, cites {p['cited_by_count']})",
                          f"TITLE: {p['title']}", f"ABSTRACT: {p['abstract']}", f"TLDR: {p.get('tldr') or '-'}"]
            lines.append("")
        (TASK_DIR / f"batch_{b // LABS_PER_BATCH + 1:02d}.md").write_text("\n".join(lines), encoding="utf-8")
    n = sum(len(v) for v in reps.values())
    log.info("representative papers: %d for %d labs (%d labs with < %d); %d task batches", n, len(reps),
             sum(len(v) < config.REPRESENTATIVE_PAPERS for v in reps.values()), config.REPRESENTATIVE_PAPERS,
             -(-len(lab_ids) // LABS_PER_BATCH))
