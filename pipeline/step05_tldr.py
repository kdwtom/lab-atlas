"""Step 5 — enrich papers with Semantic Scholar TLDRs (best effort; never fails the pipeline)."""
from __future__ import annotations

import json
import logging

from . import config
from .lib.http import CachedClient, FetchError
from .lib.io import read_json, read_jsonl, write_json, write_jsonl

log = logging.getLogger(__name__)
BATCH = 400


def run(client: CachedClient) -> None:
    status = {s["lab_id"]: s for s in read_json(config.OUTPUT_DIR / "lab_status.json")}
    keep = {lid for lid, s in status.items() if s["meets_criterion"]}
    papers = read_jsonl(config.OUTPUT_DIR / "papers_raw.jsonl")
    targets = [p for p in papers if p.get("doi") and set(p["lab_ids"]) & keep]
    doi_of = {p["id"]: p["doi"].replace("https://doi.org/", "") for p in targets}
    tldr: dict[str, str] = {}
    headers = {"x-api-key": config.S2_API_KEY} if config.S2_API_KEY else None
    ids = list(doi_of.items())
    failed_batches = 0
    for start in range(0, len(ids), BATCH):
        chunk = ids[start:start + BATCH]
        try:
            e = client.fetch(
                f"{config.S2_BASE}/paper/batch", namespace="s2", method="POST",
                params={"fields": "tldr,externalIds"},
                json_body={"ids": [f"DOI:{d}" for _, d in chunk]},
                headers=headers, min_interval=config.S2_MIN_INTERVAL, retries=5,
            )
            rows = json.loads(e["body"])
        except (FetchError, ValueError) as err:
            failed_batches += 1
            log.warning("Semantic Scholar batch failed (%s); continuing without TLDRs", err)
            continue
        for (wid, _), row in zip(chunk, rows):
            t = ((row or {}).get("tldr") or {}).get("text")
            if t:
                tldr[wid] = t
    for p in papers:
        p["tldr"] = tldr.get(p["id"], p.get("tldr"))
    write_jsonl(config.OUTPUT_DIR / "papers_raw.jsonl", papers)
    write_json(config.OUTPUT_DIR / "tldr.json", {
        "requested": len(ids), "with_tldr": len(tldr), "failed_batches": failed_batches,
        "tldr": tldr,
    })
    log.info("TLDR: %d / %d papers (failed batches: %d)", len(tldr), len(ids), failed_batches)
