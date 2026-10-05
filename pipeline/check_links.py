"""Broken-link check for every link the site shows (stage 6).

    python -m pipeline.run --steps links

Checked live (no cache):
- lab homepages, faculty roster/detail pages, Semantic Scholar source link: HTTP GET
- OpenAlex author and work pages: existence via the OpenAlex API (batched, 50 ids per call)
- ORCID iDs: ORCID public API
- DOIs of every paper the site links to (representative papers + co-authored papers): the doi.org
  handle API, which answers without going through publisher bot protection

Verdicts: ok | blocked (401/403/429/503 — bot protection, check by hand) | broken | unreachable.
Writes output/link_report.csv and exits non-zero if anything is broken.
"""
from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

from . import config
from .lib.io import read_json, write_csv
from .lib.live import LiveClient, Result, openalex_params

log = logging.getLogger(__name__)


def _collect(labs: list[dict], papers: list[dict], edges: list[dict]) -> dict[str, list[tuple[str, str]]]:
    """kind -> [(target, where)]; `target` is a URL, or an id for the API-checked kinds."""
    out: dict[str, dict[str, str]] = {k: {} for k in ("web", "openalex_author", "openalex_work", "orcid", "doi")}
    shown_papers = {pid for l in labs for pid in l["representative_paper_ids"]}
    shown_papers |= {pid for e in edges if e["type"] == "coauthor" for pid in e["paper_ids"][:3]}
    for l in labs:
        if l["homepage_url"]:
            out["web"].setdefault(l["homepage_url"], l["id"])
        out["web"].setdefault(l["faculty_page_url"], l["id"])
        for s in l["sources"]:
            if s["kind"] in ("openalex_author", "openalex_works"):
                continue  # covered by the API checks below
            out["web"].setdefault(s["url"], l["id"])
        out["openalex_author"].setdefault(l["openalex_id"], l["id"])
        if l["orcid"]:
            out["orcid"].setdefault(l["orcid"], l["id"])
    for p in papers:
        if p["id"] not in shown_papers:
            continue
        out["openalex_work"].setdefault(p["id"], ",".join(p["lab_ids"]))
        if p["doi"]:
            out["doi"].setdefault(p["doi"].removeprefix("https://doi.org/"), ",".join(p["lab_ids"]))
    return {k: list(v.items()) for k, v in out.items()}


def _openalex_exist(client: LiveClient, entity: str, ids: list[str]) -> dict[str, Result]:
    res: dict[str, Result] = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        q = "&".join(f"{k}={quote(str(v), safe=':|,')}" for k, v in
                     openalex_params(filter="openalex:" + "|".join(chunk), select="id", **{"per-page": 50}).items())
        url = f"{config.OPENALEX_BASE}/{entity}?{q}"
        r = client.get(url, keep_body=True)
        found: set[str] = set()
        if r.status == 200:
            found = {x["id"].rsplit("/", 1)[-1] for x in json.loads(r.body)["results"]}
        for oid in chunk:
            page = f"https://openalex.org/{oid}"
            if r.status != 200:
                res[oid] = Result(page, r.status, None, r.error or "OpenAlex API error")
            else:
                res[oid] = Result(page, 200 if oid in found else 404, page, None if oid in found else "not in OpenAlex")
    return res


def _doi(client: LiveClient, doi: str) -> Result:
    r = client.get(f"https://doi.org/api/handles/{quote(doi, safe='/')}", keep_body=True)
    if r.status == 200 and json.loads(r.body).get("responseCode") == 1:
        return Result(f"https://doi.org/{doi}", 200, None, None)
    return Result(f"https://doi.org/{doi}", r.status if r.status != 200 else 404, None, r.error or "DOI not registered")


def _orcid(client: LiveClient, orcid: str) -> Result:
    r = client.get(f"https://pub.orcid.org/v3.0/{orcid}/person", headers={"Accept": "application/json"})
    return Result(f"https://orcid.org/{orcid}", r.status, None, r.error)


def run(client=None) -> None:
    d = config.WEB_DATA_DIR
    targets = _collect(read_json(d / "labs.json"), read_json(d / "papers.json"), read_json(d / "edges.json"))
    log.info("links to check: %s", {k: len(v) for k, v in targets.items()})
    live = LiveClient(min_interval=0.5)
    rows: list[dict] = []

    def add(kind: str, where: str, r: Result) -> None:
        rows.append({"kind": kind, "verdict": r.verdict, "status": r.status or "", "url": r.url,
                     "final_url": r.final_url or "", "error": r.error or "", "lab_ids": where})

    with ThreadPoolExecutor(max_workers=12) as pool:
        web = list(pool.map(lambda t: live.get(t[0]), targets["web"]))
        # some university servers reset connections under parallel load: retry those once, one at a time
        slow = LiveClient(min_interval=2.0)
        web = [slow.get(r.url, timeout=30) if r.verdict == "unreachable" else r for r in web]
        for (url, where), r in zip(targets["web"], web):
            add("web", where, r)
        for (doi, where), r in zip(targets["doi"], pool.map(lambda t: _doi(live, t[0]), targets["doi"])):
            add("doi", where, r)
        for (oid, where), r in zip(targets["orcid"], pool.map(lambda t: _orcid(live, t[0]), targets["orcid"])):
            add("orcid", where, r)
    for entity, kind in (("authors", "openalex_author"), ("works", "openalex_work")):
        found = _openalex_exist(live, entity, [t[0] for t in targets[kind]])
        for oid, where in targets[kind]:
            add(kind, where, found[oid])

    rows.sort(key=lambda r: (r["verdict"] == "ok", r["kind"], r["url"]))
    write_csv(config.OUTPUT_DIR / "link_report.csv", rows,
              ["kind", "verdict", "status", "url", "final_url", "error", "lab_ids"])
    by = Counter((r["kind"], r["verdict"]) for r in rows)
    for kind in targets:
        log.info("%-16s %s", kind, {v: n for (k, v), n in sorted(by.items()) if k == kind})
    bad = [r for r in rows if r["verdict"] in ("broken", "unreachable")]
    for r in bad + [r for r in rows if r["verdict"] == "blocked"]:
        log.warning("%-11s %-15s %s %s %s", r["verdict"], r["kind"], r["status"], r["url"], r["error"])
    if any(r["verdict"] == "broken" for r in rows):
        sys.exit("broken links found (see output/link_report.csv)")
    log.info("link check: %d links, none broken", len(rows))
