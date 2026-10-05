"""Step 10 — build the static web data (web/public/data/*.json) from pipeline outputs.

Inputs : faculty.json, matches.json, lab_status.json, papers_raw.jsonl, analysis.json,
         representatives.json, curation/summaries/*.json, curation/excluded_papers.csv
Outputs: labs.json, papers.json, edges.json, clusters.json, meta.json

Abstracts never leave the pipeline: papers.json carries only has_abstract / has_tldr flags,
the hand-written Korean summary (when one exists) and links. Missing values stay null so the
site can show "정보 없음".
"""
from __future__ import annotations

import logging
from datetime import date

from . import config
from .lib.curation import excluded_papers
from .lib.io import read_json, read_jsonl, write_json
from .lib.selection import in_analysis_set
from .schemas import (Cluster, Counts, Edge, Lab, Meta, Paper, PaperSummary, PiRole, Source, SummaryCoverage,
                      Topic, YearKeywords)

log = logging.getLogger(__name__)
SUMMARY_DIR = config.PIPELINE_DIR / "curation" / "summaries"


def load_summaries() -> tuple[dict[str, dict], dict[str, str]]:
    """Merge all hand-written batches: (paper id -> summary fields, lab id -> intro)."""
    papers: dict[str, dict] = {}
    labs: dict[str, str] = {}
    for f in sorted(SUMMARY_DIR.glob("batch_*.json")):
        d = read_json(f)
        papers.update(d.get("papers", {}))
        labs.update(d.get("labs", {}))
    return papers, labs


def faculty_key(univ: str, page_url: str, name_ko, name_en) -> tuple:
    return univ, page_url, name_ko or name_en


def run(client=None) -> None:
    out = config.OUTPUT_DIR
    analysis = read_json(out / "analysis.json")
    status = {s["lab_id"]: s for s in read_json(out / "lab_status.json")}
    faculty = {faculty_key(f["univ"], f["faculty_page_url"], f["name_ko"], f["name_en"]): f
               for f in read_json(out / "faculty.json")}
    matches = {f"{m['univ']}-{m['openalex_id']}": m for m in read_json(out / "matches.json")
               if m["status"] == "matched"}
    reps = read_json(out / "representatives.json")
    summaries, intros = load_summaries()
    lab_ids = sorted(analysis["labs"])
    keep = set(lab_ids)

    # ------------------------------------------------------------------ papers (analysis set only)
    raw = read_jsonl(out / "papers_raw.jsonl")
    papers: list[Paper] = []
    for p in raw:
        labs_here = [l for l in p["lab_ids"] if l in keep and in_analysis_set(p, l)]
        if not labs_here:
            continue
        s = summaries.get(p["id"])
        papers.append(Paper(
            id=p["id"], lab_ids=labs_here, title=p["title"], year=p["year"], venue=p.get("venue"),
            doi=p.get("doi"), cited_by_count=p["cited_by_count"], type=p["type"],
            pi_roles={l: PiRole(**p["pi_roles"][l]) for l in labs_here},
            has_abstract=bool(p.get("abstract")), has_tldr=bool(p.get("tldr")),
            topics=[Topic(**t) for t in p["topics"]],
            summary_ko=PaperSummary(**s) if s else None,
            openalex_url=p["openalex_url"], retrieved_at=p["retrieved_at"],
        ))
    paper_ids = {p.id for p in papers}
    has_tldr = {p.id for p in papers if p.has_tldr}

    # ------------------------------------------------------------------ labs
    labs: list[Lab] = []
    for lid in lab_ids:
        st, m, a = status[lid], matches[lid], analysis["labs"][lid]
        f = faculty[faculty_key(m["univ"], m["faculty_page_url"], m["name_ko"], m["name_en"])]
        cand = next(c for c in m["candidates"] if c["openalex_id"] == m["openalex_id"])
        dept = config.DEPT_BY_UNIV[m["univ"]]
        rep_ids = [r for r in reps.get(lid, []) if r in paper_ids][: config.REPRESENTATIVE_PAPERS]
        sources = [Source(url=f["faculty_list_url"], kind="faculty_page", retrieved_at=f["retrieved_at"])]
        if f["faculty_page_url"] != f["faculty_list_url"]:
            sources.append(Source(url=f["faculty_page_url"], kind="faculty_detail", retrieved_at=f["retrieved_at"]))
        sources += [
            Source(url=f"https://openalex.org/{m['openalex_id']}", kind="openalex_author", retrieved_at=m["retrieved_at"]),
            Source(url=f"https://openalex.org/works?filter=author.id:{m['openalex_id']}", kind="openalex_works",
                   retrieved_at=m["retrieved_at"]),
        ]
        if any(pid in has_tldr for pid in rep_ids):
            sources.append(Source(url="https://www.semanticscholar.org/", kind="semantic_scholar",
                                  retrieved_at=m["retrieved_at"]))
        labs.append(Lab(
            id=lid, univ=m["univ"], univ_name_ko=dept.univ_name_ko, dept_name_ko=dept.dept_name_ko,
            pi_name_ko=f.get("name_ko"), pi_name_en=f.get("name_en") or cand["display_name"],
            position=f.get("position"), lab_name=f.get("lab_name"), homepage_url=f.get("homepage_url"),
            faculty_page_url=f["faculty_page_url"], openalex_id=m["openalex_id"], orcid=cand.get("orcid"),
            match_confidence=m["confidence"], paper_count_5y=st["paper_count_5y"],
            senior_paper_count_5y=st["senior_paper_count_5y"], keywords=a["keywords"],
            cluster_id=a["cluster_id"], x=a["x"], y=a["y"], intro_ko=intros.get(lid),
            representative_paper_ids=rep_ids,
            keyword_timeline=[YearKeywords(**t) for t in a["keyword_timeline"]],
            sources=sources,
        ))

    # ------------------------------------------------------------------ edges, clusters, meta
    edges = [Edge(**e) for e in analysis["edges"]]
    for e in edges:  # coauthor evidence must point at exported papers
        e.paper_ids = [p for p in e.paper_ids if p in paper_ids]
    clusters = [Cluster(**c) for c in analysis["clusters"]]
    params = analysis["params"]
    all_reps = [r for l in labs for r in l.representative_paper_ids]
    meta = Meta(
        generated_at=date.today(),
        data_retrieved_at=max(date.fromisoformat(str(p.retrieved_at)) for p in papers),
        window_years=(config.YEAR_FROM, config.YEAR_TO), min_senior_papers=config.MIN_SENIOR_PAPERS,
        louvain_resolution=params["louvain_resolution"], louvain_seed=params["louvain_seed"],
        similarity_k=params["k"], similarity_threshold=params["threshold"],
        counts=Counts(labs=len(labs), papers=len(papers),
                      edges_similarity=sum(e.type == "similarity" for e in edges),
                      edges_coauthor=sum(e.type == "coauthor" for e in edges)),
        summary_coverage=SummaryCoverage(
            representative_papers=len(all_reps),
            papers_with_summary=sum(1 for r in all_reps if r in summaries),
            labs=len(labs), labs_with_intro=sum(1 for l in labs if l.intro_ko)),
        excluded_namesake_papers=len(excluded_papers()),
    )

    d = config.WEB_DATA_DIR
    write_json(d / "labs.json", labs)
    write_json(d / "papers.json", papers)
    write_json(d / "edges.json", edges)
    write_json(d / "clusters.json", clusters)
    write_json(d / "meta.json", meta.model_dump(mode="json"))
    sc = meta.summary_coverage
    log.info("exported %d labs, %d papers, %d edges, %d clusters -> %s", len(labs), len(papers), len(edges),
             len(clusters), d)
    log.info("Korean summaries: %d/%d representative papers, intros %d/%d labs",
             sc.papers_with_summary, sc.representative_papers, sc.labs_with_intro, sc.labs)
