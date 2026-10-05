"""Empty-field statistics for the published data (stage 6).

    python -m pipeline.run --steps fields

A field counts as empty when it is null, "", or []; the site shows these as "정보 없음".
Writes output/field_stats.md.
"""
from __future__ import annotations

import logging

from . import config
from .lib.io import read_json

log = logging.getLogger(__name__)

NOT_IN_ABSTRACT = "초록에서 확인 불가"
LAB_FIELDS = ["pi_name_ko", "pi_name_en", "position", "lab_name", "homepage_url", "orcid", "keywords",
              "cluster_id", "x", "intro_ko", "representative_paper_ids", "keyword_timeline"]
PAPER_FIELDS = ["venue", "doi", "topics", "summary_ko"]
SUMMARY_FIELDS = ["one_line", "background", "methods", "findings", "significance"]


def _empty(v) -> bool:
    return v is None or v == "" or v == []


def _table(title: str, total: int, counts: list[tuple[str, int]]) -> list[str]:
    lines = [f"### {title} (n={total})", "", "| 필드 | 비어 있음 | 비율 |", "|---|---:|---:|"]
    lines += [f"| `{f}` | {n} | {n / total:.1%} |" for f, n in counts]
    return lines + [""]


def run(client=None) -> None:
    d = config.WEB_DATA_DIR
    labs = read_json(d / "labs.json")
    papers = read_json(d / "papers.json")
    reps = {pid for l in labs for pid in l["representative_paper_ids"]}
    rep_papers = [p for p in papers if p["id"] in reps]

    lab_counts = [(f, sum(_empty(l[f]) for l in labs)) for f in LAB_FIELDS]
    lab_counts.append(("representative_paper_ids (<3편)", sum(len(l["representative_paper_ids"]) < 3 for l in labs)))
    all_counts = [(f, sum(_empty(p[f]) for p in papers)) for f in PAPER_FIELDS if f != "summary_ko"]
    rep_counts = [(f, sum(_empty(p[f]) for p in rep_papers)) for f in PAPER_FIELDS]
    summaries = [p["summary_ko"] for p in rep_papers if p["summary_ko"]]
    sum_counts = [(f, sum(s[f] == NOT_IN_ABSTRACT for s in summaries)) for f in SUMMARY_FIELDS]

    md = ["# 빈 필드 통계", "", f"데이터 생성일 {read_json(d / 'meta.json')['generated_at']}. "
          "null·빈 문자열·빈 배열을 비어 있는 것으로 셉니다(사이트에는 \"정보 없음\"으로 표시).", ""]
    md += _table("연구실 labs.json", len(labs), lab_counts)
    md += _table("전체 논문 papers.json", len(papers), all_counts)
    md += _table("대표 논문", len(rep_papers), rep_counts)
    if summaries:
        md += [f"### 작성된 요약 중 \"{NOT_IN_ABSTRACT}\" 항목 (n={len(summaries)})", "",
               "| 항목 | 건수 | 비율 |", "|---|---:|---:|"]
        md += [f"| `{f}` | {n} | {n / len(summaries):.1%} |" for f, n in sum_counts] + [""]
    out = config.OUTPUT_DIR / "field_stats.md"
    out.write_text("\n".join(md), encoding="utf-8")
    for title, n, counts in (("labs", len(labs), lab_counts), ("papers", len(papers), all_counts),
                             ("representative", len(rep_papers), rep_counts)):
        log.info("%s (n=%d): %s", title, n, ", ".join(f"{f}={c}" for f, c in counts if c))
    log.info("wrote %s", out.relative_to(config.ROOT))
