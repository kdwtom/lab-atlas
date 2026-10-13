"""Regression check (PLAN_PHASE1.md completion criterion 1): the original life-science labs must keep
their ids, matching decisions and paper counts when departments are added.

    python -m pipeline.regression <baseline output dir>

The baseline is a copy of pipeline/output/ taken before the change. Fields added later (dept, depts,
discipline, order_agnostic, field_share) and retrieval dates are ignored.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import config

LIFE_UNIV_DEPT = {d.univ: d.code for d in config.DEPARTMENTS if d.discipline == "life"}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def decisions(matches: list[dict]) -> dict[tuple, tuple]:
    out = {}
    for m in matches:
        if m.get("dept", LIFE_UNIV_DEPT.get(m["univ"])) not in LIFE_UNIV_DEPT.values():
            continue
        key = (m["univ"], m.get("name_ko"), m.get("name_en"), m["faculty_page_url"])
        out[key] = (m["status"], m.get("openalex_id"), m.get("confidence"), m.get("reason"))
    return out


def lab_counts(status: list[dict]) -> dict[str, tuple]:
    return {s["lab_id"]: (s["paper_count_5y"], s["senior_paper_count_5y"], s["meets_criterion"],
                          s.get("home_paper_count_5y"))
            for s in status if set(s.get("depts", [LIFE_UNIV_DEPT[s["univ"]]])) & set(LIFE_UNIV_DEPT.values())}


def compare(name: str, old: dict, new: dict) -> int:
    missing = sorted(set(old) - set(new), key=str)
    changed = sorted((k for k in set(old) & set(new) if old[k] != new[k]), key=str)
    for k in missing[:10]:
        print(f"  [{name}] missing: {k} (was {old[k]})")
    for k in changed[:10]:
        print(f"  [{name}] changed: {k}: {old[k]} -> {new[k]}")
    print(f"{name}: {len(old)} baseline rows, {len(missing)} missing, {len(changed)} changed")
    return len(missing) + len(changed)


def main(argv: list[str]) -> int:
    base = Path(argv[0])
    out = config.OUTPUT_DIR
    bad = compare("matches", decisions(load(base / "matches.json")), decisions(load(out / "matches.json")))
    old_status = load(base / "lab_status.json")
    new_status = [s for s in load(out / "lab_status.json") if s["lab_id"] in {o["lab_id"] for o in old_status}
                  or "life" == s.get("discipline")]
    bad += compare("lab_status", lab_counts(old_status), lab_counts(new_status))
    print("OK: life-science labs unchanged" if not bad else f"REGRESSION: {bad} differences")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
