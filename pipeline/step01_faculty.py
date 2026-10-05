"""Step 1 — collect professors from each department's official faculty page."""
from __future__ import annotations

import logging
import traceback

from . import config
from .lib.faculty import PARSERS
from .lib.http import CachedClient
from .lib.io import write_json

log = logging.getLogger(__name__)


def run(client: CachedClient) -> None:
    all_records, errors = [], []
    for dept in config.DEPARTMENTS:
        try:
            recs = PARSERS[dept.univ](client)
        except Exception as e:  # report and continue with other departments
            log.error("[%s] faculty collection failed: %s", dept.univ, e)
            errors.append({"univ": dept.univ, "url": dept.faculty_list_url,
                           "error": f"{type(e).__name__}: {e}",
                           "trace": traceback.format_exc(limit=3)})
            continue
        if not recs:
            errors.append({"univ": dept.univ, "url": dept.faculty_list_url,
                           "error": "parser returned 0 professors (page structure changed?)"})
        n_ft = sum(r.is_full_time for r in recs)
        no_en = sum(r.name_en is None for r in recs)
        log.info("[%s] %d listed (%d full-time), %d without English name", dept.univ, len(recs), n_ft, no_en)
        all_records.extend(recs)
    write_json(config.OUTPUT_DIR / "faculty.json", all_records)
    write_json(config.OUTPUT_DIR / "faculty_errors.json", errors)
    if errors:
        log.warning("faculty collection blocked/failed for: %s", ", ".join(e["univ"] for e in errors))
