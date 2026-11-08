"""Step 10 — build the static web data (web/public/data/*.json) from pipeline outputs.

Inputs : faculty.json, matches.json, lab_status.json, papers_raw.jsonl, analysis.json,
         representatives.json, curation/summaries/*.json, curation/excluded_papers.csv
Outputs: labs.json, papers.json, edges.json, clusters.json, meta.json,
         lab_vectors.bin + lab_vectors.json (8-bit lab vectors for in-browser recommendations)

Abstracts never leave the pipeline: papers.json carries only has_abstract / has_tldr flags,
the hand-written Korean summary (when one exists) and links. Missing values stay null so the
site can show "정보 없음".
"""
from __future__ import annotations

import logging
from datetime import date

import numpy as np

from . import config
from .lib.curation import excluded_papers
from .lib.io import read_json, read_jsonl, write_json
from .lib.selection import in_analysis_set
from .schemas import (Cluster, Counts, DepartmentInfo, Edge, Lab, LabTrend, Meta, Paper, PaperSummary, PiRole, Source,
                      SummaryCoverage, Topic, YearKeywords)
from .step06_stats import rule_ko

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


def load_intro_unavailable() -> dict[str, str]:
    """Lab id -> reason for labs whose intro could not be written (curation/intro_unavailable.json)."""
    path = config.PIPELINE_DIR / "curation" / "intro_unavailable.json"
    if not path.exists():
        return {}
    return {lid: v["reason"] for lid, v in read_json(path)["unavailable"].items()}


def export_vectors(lab_ids: list[str]) -> None:
    """Lab vectors for the browser: int8 (about 370 KB for 478 labs), loaded only by the shortlist page.
    Quantising keeps 98% of each lab's top-10 neighbours (PLAN_PHASE2.md)."""
    z = np.load(config.OUTPUT_DIR / "lab_vectors.npz")
    row = {lid: i for i, lid in enumerate(z["lab_ids"].tolist())}
    vec = z["vectors"][[row[lid] for lid in lab_ids]]
    q = np.round(vec / np.abs(vec).max() * 127).astype(np.int8)
    (config.WEB_DATA_DIR / "lab_vectors.bin").write_bytes(q.tobytes())
    write_json(config.WEB_DATA_DIR / "lab_vectors.json", {"ids": lab_ids, "dim": int(q.shape[1])})


def faculty_key(univ: str, page_url: str, name_ko, name_en) -> tuple:
    return univ, page_url, name_ko or name_en


def run(client=None) -> None:
    out = config.OUTPUT_DIR
    analysis = read_json(out / "analysis.json")
    status = {s["lab_id"]: s for s in read_json(out / "lab_status.json")}
    faculty = {faculty_key(f["univ"], f["faculty_page_url"], f["name_ko"], f["name_en"]): f
               for f in read_json(out / "faculty.json")}
    matches: dict[tuple[str, str], dict] = {}  # (lab id, department) -> match
    for m in read_json(out / "matches.json"):
        if m["status"] == "matched":
            matches[(f"{m['univ']}-{m['openalex_id']}", m["dept"])] = m
    reps = read_json(out / "representatives.json")
    summaries, intros = load_summaries()
    unavailable = load_intro_unavailable()
    lab_ids = sorted(analysis["labs"])
    trends_path = out / "trends.json"
    trends = read_json(trends_path) if trends_path.exists() else {}
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
        st, a = status[lid], analysis["labs"][lid]
        ms = [matches[(lid, d)] for d in st["depts"]]  # first department = primary
        fs = [faculty[faculty_key(x["univ"], x["faculty_page_url"], x["name_ko"], x["name_en"])] for x in ms]
        m, f = ms[0], fs[0]
        cand = next(c for c in m["candidates"] if c["openalex_id"] == m["openalex_id"])
        depts = [config.DEPT_BY_CODE[d] for d in st["depts"]]
        rep_ids = [r for r in reps.get(lid, []) if r in paper_ids][: config.REPRESENTATIVE_PAPERS]
        sources = []
        for ff in fs:
            sources.append(Source(url=ff["faculty_list_url"], kind="faculty_page", retrieved_at=ff["retrieved_at"]))
            if ff["faculty_page_url"] != ff["faculty_list_url"]:
                sources.append(Source(url=ff["faculty_page_url"], kind="faculty_detail", retrieved_at=ff["retrieved_at"]))
        sources += [
            Source(url=f"https://openalex.org/{m['openalex_id']}", kind="openalex_author", retrieved_at=m["retrieved_at"]),
            Source(url=f"https://openalex.org/works?filter=author.id:{m['openalex_id']}", kind="openalex_works",
                   retrieved_at=m["retrieved_at"]),
        ]
        if any(pid in has_tldr for pid in rep_ids):
            sources.append(Source(url="https://www.semanticscholar.org/", kind="semantic_scholar",
                                  retrieved_at=m["retrieved_at"]))
        labs.append(Lab(
            id=lid, univ=m["univ"], univ_name_ko=depts[0].univ_name_ko,
            dept_name_ko=" · ".join(d.dept_name_ko for d in depts), dept_codes=[d.code for d in depts],
            disciplines=list(dict.fromkeys(d.discipline for d in depts)),
            pi_name_ko=f.get("name_ko") or next((x["name_ko"] for x in fs if x.get("name_ko")), None),
            pi_name_en=f.get("name_en") or next((x["name_en"] for x in fs if x.get("name_en")), None)
            or cand["display_name"],
            position=f.get("position"), lab_name=f.get("lab_name") or next((x["lab_name"] for x in fs if x.get("lab_name")), None),
            homepage_url=f.get("homepage_url") or next((x["homepage_url"] for x in fs if x.get("homepage_url")), None),
            faculty_page_url=f["faculty_page_url"], openalex_id=m["openalex_id"], orcid=cand.get("orcid"),
            match_confidence="high" if any(x["confidence"] == "high" for x in ms) else "medium",
            paper_count_5y=st["paper_count_5y"],
            senior_paper_count_5y=st["senior_paper_count_5y"], vector_paper_count=a["vector_paper_count"],
            keywords=a["keywords"],
            cluster_id=a["cluster_id"], subcluster_id=a["subcluster_id"], x=a["x"], y=a["y"], intro_ko=intros.get(lid),
            intro_unavailable=None if lid in intros else unavailable.get(lid),
            representative_paper_ids=rep_ids,
            trend=LabTrend(**trends[lid]) if lid in trends else None,
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
        similarity_bands=params["similarity_bands"],
        counts=Counts(labs=len(labs), papers=len(papers),
                      edges_similarity=sum(e.type == "similarity" for e in edges),
                      edges_coauthor=sum(e.type == "coauthor" for e in edges)),
        summary_coverage=SummaryCoverage(
            representative_papers=len(all_reps),
            papers_with_summary=sum(1 for r in all_reps if r in summaries),
            labs=len(labs), labs_with_intro=sum(1 for l in labs if l.intro_ko),
            labs_intro_unavailable=sum(1 for l in labs if l.intro_unavailable)),
        excluded_namesake_papers=len(excluded_papers()),
        departments=[DepartmentInfo(code=d.code, univ=d.univ, univ_name_ko=d.univ_name_ko, name_ko=d.dept_name_ko,
                                    discipline=d.discipline, faculty_list_url=d.faculty_list_url,
                                    labs=sum(d.code in l.dept_codes for l in labs))
                     for d in config.DEPARTMENTS],
        rules={k: rule_ko(v) for k, v in config.DISCIPLINES.items()},
    )

    d = config.WEB_DATA_DIR
    write_json(d / "labs.json", labs)
    write_json(d / "papers.json", papers)
    write_json(d / "edges.json", edges)
    write_json(d / "clusters.json", clusters)
    write_json(d / "meta.json", meta.model_dump(mode="json"))
    export_vectors([l.id for l in labs])
    sc = meta.summary_coverage
    log.info("exported %d labs, %d papers, %d edges, %d clusters -> %s", len(labs), len(papers), len(edges),
             len(clusters), d)
    log.info("Korean summaries: %d/%d representative papers, intros %d/%d labs",
             sc.papers_with_summary, sc.representative_papers, sc.labs_with_intro, sc.labs)
