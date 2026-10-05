"""Schema validation for pipeline outputs (run at the end of every stage)."""
from __future__ import annotations

import logging
import sys

from pydantic import TypeAdapter, ValidationError

from . import config
from .lib.io import read_json, read_jsonl
from .schemas import Cluster, Edge, FacultyRecord, LabStatus, Lab, MatchResult, Meta, Paper, RawPaper

log = logging.getLogger(__name__)

INTERMEDIATE = [
    ("faculty.json", list[FacultyRecord], "json"),
    ("matches.json", list[MatchResult], "json"),
    ("lab_status.json", list[LabStatus], "json"),
    ("papers_raw.jsonl", RawPaper, "jsonl"),
]
WEB = [
    ("labs.json", list[Lab]), ("papers.json", list[Paper]), ("edges.json", list[Edge]),
    ("clusters.json", list[Cluster]), ("meta.json", Meta),
]


def web_integrity() -> list[str]:
    """Cross-file references and publication rules for web/public/data."""
    d = config.WEB_DATA_DIR
    if not (d / "labs.json").exists():
        return []
    errors: list[str] = []
    labs = read_json(d / "labs.json")
    papers = read_json(d / "papers.json")
    edges = read_json(d / "edges.json")
    clusters = {c["id"] for c in read_json(d / "clusters.json")}
    lab_ids, paper_ids = {l["id"] for l in labs}, {p["id"] for p in papers}
    if any(r not in paper_ids for l in labs for r in l["representative_paper_ids"]):
        errors.append("web: representative paper missing from papers.json")
    if any(l["cluster_id"] is not None and l["cluster_id"] not in clusters for l in labs):
        errors.append("web: lab refers to unknown cluster")
    if any(e["source"] not in lab_ids or e["target"] not in lab_ids or e["source"] >= e["target"] for e in edges):
        errors.append("web: edge endpoints unknown or not ordered (source < target)")
    if any(not set(p["lab_ids"]) <= lab_ids for p in papers):
        errors.append("web: paper refers to unknown lab")
    # principle 4 (no abstract text) and no personal contact data on the site
    raw = "".join((d / n).read_text(encoding="utf-8") for n in ("labs.json", "papers.json"))
    for banned in ('"abstract"', '"tldr"', '"email"', "@kaist.ac.kr", "@snu.ac.kr"):
        if banned in raw:
            errors.append(f"web: forbidden content {banned} in published data")
    if not errors:
        log.info("OK  web cross-references and publication rules")
    return errors


def run(client=None) -> None:
    errors: list[str] = []
    out = config.OUTPUT_DIR
    for name, typ, kind in INTERMEDIATE:
        p = out / name
        if not p.exists():
            log.info("skip %s (not produced yet)", name)
            continue
        try:
            if kind == "json":
                TypeAdapter(typ).validate_python(read_json(p))
            else:
                ta = TypeAdapter(typ)
                for i, row in enumerate(read_jsonl(p)):
                    ta.validate_python(row)
            log.info("OK  %s", name)
        except ValidationError as e:
            errors.append(f"{name}: {e}")

    # referential integrity
    if (out / "lab_status.json").exists() and (out / "papers_raw.jsonl").exists():
        lab_ids = {s["lab_id"] for s in read_json(out / "lab_status.json")}
        bad = [p["id"] for p in read_jsonl(out / "papers_raw.jsonl") if not set(p["lab_ids"]) <= lab_ids]
        if bad:
            errors.append(f"papers_raw.jsonl: {len(bad)} papers reference unknown labs, e.g. {bad[:3]}")
        else:
            log.info("OK  papers -> labs references")

    if (out / "analysis.json").exists():
        a = read_json(out / "analysis.json")
        try:
            TypeAdapter(list[Edge]).validate_python(a["edges"])
            TypeAdapter(list[Cluster]).validate_python(a["clusters"])
            ids = set(a["labs"])
            bad = [e for e in a["edges"] if e["source"] not in ids or e["target"] not in ids]
            if bad:
                errors.append(f"analysis.json: {len(bad)} edges reference unknown labs")
            log.info("OK  analysis.json")
        except ValidationError as e:
            errors.append(f"analysis.json: {e}")

    for name, typ in WEB:
        p = config.WEB_DATA_DIR / name
        if p.exists():
            try:
                TypeAdapter(typ).validate_python(read_json(p))
                log.info("OK  web/%s", name)
            except ValidationError as e:
                errors.append(f"web/{name}: {e}")

    errors += web_integrity()
    if errors:
        for e in errors:
            log.error(e)
        sys.exit("schema validation failed")
    log.info("schema validation passed")
