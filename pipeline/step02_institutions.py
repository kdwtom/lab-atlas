"""Step 2 — resolve each university to an OpenAlex institution ID (from the API, not memory)."""
from __future__ import annotations

import logging

from . import config
from .lib.http import CachedClient
from .lib.io import write_json
from .lib.openalex import OpenAlex, short_id

log = logging.getLogger(__name__)


def pick(results: list[dict], query: str) -> dict | None:
    q = query.lower()
    exact = [r for r in results if (r.get("display_name") or "").lower() == q]
    pool = exact or [r for r in results if r.get("type") in ("education", "funder", None)] or results
    return max(pool, key=lambda r: r.get("works_count") or 0) if pool else None


def run(client: CachedClient) -> None:
    oa = OpenAlex(client)
    out = {}
    for dept in config.DEPARTMENTS:
        results = oa.search_institutions(dept.institution_query)
        best = pick(results, dept.institution_query)
        if not best:
            raise SystemExit(f"OpenAlex institution not found for {dept.univ}: {dept.institution_query}")
        out[dept.univ] = {
            "id": short_id(best["id"]), "display_name": best.get("display_name"),
            "ror": best.get("ror"), "works_count": best.get("works_count"),
            "query": dept.institution_query,
            "alternatives": [{"id": short_id(r["id"]), "display_name": r.get("display_name")}
                             for r in results[:5]],
        }
        log.info("[%s] institution %s = %s", dept.univ, out[dept.univ]["id"], best.get("display_name"))
    write_json(config.OUTPUT_DIR / "institutions.json", out)
