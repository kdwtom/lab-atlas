"""Pipeline entry point (Windows-friendly; no make).

    python -m pipeline.run --stage collect           # stage 2: all collection steps + stats + validation
    python -m pipeline.run --steps match,papers      # individual steps
    python -m pipeline.run --stage collect --offline # re-run purely from cache
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

from . import (check_links, config, field_stats, flag_papers, spot_check, step01_faculty, step02_institutions,
               step03_match, step04_papers, step05_tldr, step06_stats, step07_embed, step08_analyze, step09_select,
               step10_export, validate)
from .lib.http import CachedClient

STEPS = {
    "faculty": step01_faculty.run,
    "institutions": step02_institutions.run,
    "match": step03_match.run,
    "papers": step04_papers.run,
    "tldr": step05_tldr.run,
    "stats": step06_stats.run,
    "flag": flag_papers.run,
    "embed": step07_embed.run,
    "analyze": step08_analyze.run,
    "select": step09_select.run,
    "export": step10_export.run,
    "validate": validate.run,
    "fields": field_stats.run,
    "links": check_links.run,
    "spotcheck": spot_check.run,
}
STAGES = {
    "collect": ["faculty", "institutions", "match", "papers", "tldr", "stats", "validate"],
    "analyze": ["embed", "analyze", "validate"],
    "export": ["select", "export", "validate"],
    "verify": ["validate", "fields", "links", "spotcheck"],  # stage 6: live checks, no cache
}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Lab Atlas data pipeline")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--stage", choices=sorted(STAGES))
    g.add_argument("--steps", help="comma-separated: " + ",".join(STEPS))
    ap.add_argument("--offline", action="store_true", help="use cache only; fail on cache miss")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):  # Korean output on Windows consoles
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")
    steps = STAGES[args.stage] if args.stage else (args.steps.split(",") if args.steps else STAGES["collect"])
    unknown = [s for s in steps if s not in STEPS]
    if unknown:
        ap.error(f"unknown steps: {unknown}")

    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = CachedClient(offline=args.offline)
    for s in steps:
        t0 = time.time()
        logging.info("=== step: %s ===", s)
        STEPS[s](client)
        logging.info("=== %s done in %.1fs (cache hits %d, network %d, errors %d) ===", s,
                     time.time() - t0, client.stats["cache_hits"], client.stats["network"], client.stats["errors"])


if __name__ == "__main__":
    main()
