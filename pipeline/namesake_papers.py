"""Namesake resolution, part B (PLAN_PHASE3.md 3): find a namesake's papers mixed into a chosen profile.

1. Screen (no API): for each lab, the similarity of every paper to the lab's medoid paper (the paper most like the
   others, so a minority of foreign papers cannot pull the centre). A paper is an outlier below the 10th percentile
   of that similarity over all labs. A lab is a suspect when outliers make up at least SUSPECT_SHARE of its papers.
   Measured on the six current universities: the hand-made mixed_topics flags score AUC 0.97.
2. Adjudicate (Claude API, suspects only): core titles vs outlier titles. Is it one person working across topics,
   or are some papers someone else's? The answer names the foreign papers.

    python -m pipeline.namesake_papers screen            # suspects and how they compare with the hand flags
    python -m pipeline.namesake_papers pilot 10          # adjudicate the first suspects; accuracy and cost
"""
from __future__ import annotations

import hashlib
import json
import logging
import sys
from collections import defaultdict

import numpy as np

from . import config
from .lib.io import read_json, read_jsonl, write_json
from .lib.selection import in_analysis_set
from .namesake import ADJ_MODEL, cost

log = logging.getLogger(__name__)

OUTLIER_PCT = 10        # papers below this percentile of medoid similarity (over all labs) are outliers
SUSPECT_SHARE = 0.3     # labs with at least this share of outliers go to the adjudicator
CACHE = config.CACHE_DIR / "adjudicator_papers"


def lab_papers(lab_dept: dict[str, str]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for p in read_jsonl(config.OUTPUT_DIR / "papers_raw.jsonl"):
        for lid in p["lab_ids"]:
            if lid in lab_dept and in_analysis_set(p, lid):
                out[lid].append(p)
    return out


def medoid_similarity(X: np.ndarray) -> np.ndarray:
    X = X / np.linalg.norm(X, axis=1, keepdims=True)
    med = X[np.argmax(np.median(X @ X.T, axis=1))]
    return X @ med


def screen() -> list[dict]:
    from .step07_embed import embed
    matches = read_json(config.OUTPUT_DIR / "matches.json")
    lab_dept = {f"{m['univ']}-{m['openalex_id']}": m["dept"] for m in matches if m["status"] == "matched"}
    papers = lab_papers(lab_dept)
    vec = embed([p for ps in papers.values() for p in ps])
    sims = {lid: medoid_similarity(np.stack([vec[p["id"]] for p in ps])) for lid, ps in papers.items() if len(ps) >= 3}
    cut = float(np.percentile(np.concatenate(list(sims.values())), OUTLIER_PCT))
    rows = []
    for lid, s in sims.items():
        out = s < cut
        ps = papers[lid]
        order = np.argsort(-s)
        rows.append({"lab_id": lid, "dept": lab_dept[lid], "papers": len(ps), "outlier_share": round(float(out.mean()), 3),
                     "core": [ps[i]["title"] for i in order[:8]],
                     "outliers": [{"id": ps[i]["id"], "title": ps[i]["title"], "venue": ps[i].get("venue")}
                                  for i in order[::-1] if out[i]][:12]})
    rows.sort(key=lambda r: -r["outlier_share"])
    suspects = [r for r in rows if r["outlier_share"] >= SUSPECT_SHARE]
    write_json(config.OUTPUT_DIR / "namesake_paper_suspects.json", {"cut": round(cut, 4), "suspects": suspects})
    return suspects


SYSTEM = """You check whether a research lab's paper list mixes in papers by a different person with the same name.
Korean names repeat often, so OpenAlex sometimes merges a professor's papers with a namesake's (a doctor, an
engineer, a student). You get the department, the lab's most central papers, and the papers least like them.

Decide:
- "one_person": the outlying papers are plausibly the same professor (collaborations, side projects, methods
  papers, a shift of topic). Interdisciplinary professors are common; do not flag them.
- "mixed": some outlying papers are clearly someone else's (a field the professor would not publish in, such as
  clinical medicine for a physicist, or law for a chemist). List those papers by number.
- "unclear": you cannot tell.
Only list papers you would remove."""


def adjudicate(ai, r: dict, fac: dict | None) -> dict:
    d = config.DEPT_BY_CODE[r["dept"]]
    fac = fac or {}
    prompt = (f"University: {d.univ_name_en}, department: {d.dept_name_ko} ({d.discipline})\n"
              f"Professor: {fac.get('name_ko') or ''} ({fac.get('name_en') or ''}), lab: {fac.get('lab_name') or '-'}\n"
              f"Research fields on the faculty page: {', '.join(fac.get('research_fields') or []) or '-'}\n\n"
              "Central papers:\n" + "\n".join(f"- {t}" for t in r["core"]) +
              "\n\nOutlying papers:\n" + "\n".join(f"P{i}. {o['title']} ({o.get('venue') or '-'})"
                                                   for i, o in enumerate(r["outliers"], 1)))
    key = hashlib.sha256((ADJ_MODEL + SYSTEM + prompt).encode()).hexdigest()[:24]
    path = CACHE / f"{key}.json"
    if path.exists():
        return {**read_json(path), "cached": True}
    labels = [f"P{i}" for i in range(1, len(r["outliers"]) + 1)]
    schema = {"type": "object", "additionalProperties": False, "required": ["verdict", "foreign", "reason"],
              "properties": {"verdict": {"type": "string", "enum": ["one_person", "mixed", "unclear"]},
                             "foreign": {"type": "array", "items": {"type": "string", "enum": labels}},
                             "reason": {"type": "string"}}}
    resp = ai.messages.create(model=ADJ_MODEL, max_tokens=8000, system=SYSTEM,
                              messages=[{"role": "user", "content": prompt}],
                              output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}})
    data = json.loads(next(b.text for b in resp.content if b.type == "text"))
    out = {"verdict": data["verdict"], "reason": data["reason"],
           "foreign": [r["outliers"][int(x[1:]) - 1]["id"] for x in data["foreign"]],
           "usage": {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens}}
    CACHE.mkdir(parents=True, exist_ok=True)
    write_json(path, out)
    return {**out, "cached": False}


def human_flags() -> dict[str, str]:
    cur = read_json(config.PIPELINE_DIR / "curation" / "intro_unavailable.json")
    flags = {lid: "mixed" for lid, v in cur["unavailable"].items() if v["reason"] == "mixed_topics"}
    flags.update({lid: "review" for lid in cur["review"]})
    return flags


def report_screen(suspects: list[dict]) -> None:
    flags = human_flags()
    got = defaultdict(int)
    for r in suspects:
        got[flags.get(r["lab_id"], "none")] += 1
    total = defaultdict(int)
    for v in flags.values():
        total[v] += 1
    print(f"suspects {len(suspects)}: hand mixed_topics {got['mixed']}/{total['mixed']}, "
          f"hand review {got['review']}/{total['review']}, not flagged by hand {got['none']}")


def pilot(limit: int) -> None:
    import anthropic
    ai = anthropic.Anthropic()   # key from local.env, loaded by config
    data = read_json(config.OUTPUT_DIR / "namesake_paper_suspects.json")
    matches = read_json(config.OUTPUT_DIR / "matches.json")
    name_of = {f"{m['univ']}-{m['openalex_id']}": f"{m['dept']}|{m['name_ko'] or m['name_en']}"
               for m in matches if m["status"] == "matched"}
    fac = {f"{f['dept']}|{f['name_ko'] or f['name_en']}": f for f in read_json(config.OUTPUT_DIR / "faculty.json")}
    flags = human_flags()
    usages, rows = [], []
    for n, r in enumerate(data["suspects"][:limit], 1):
        a = adjudicate(ai, r, fac.get(name_of.get(r["lab_id"], "")))
        if not a["cached"]:
            usages.append(a["usage"])
        hand = flags.get(r["lab_id"], "none")
        rows.append({"lab_id": r["lab_id"], "dept": r["dept"], "hand": hand, **a})
        print(f"  {n:3} {a['verdict']:10} hand={hand:6} foreign={len(a['foreign']):2} {r['lab_id']}", file=sys.stderr, flush=True)
    write_json(config.OUTPUT_DIR / "namesake_paper_pilot.json", rows)
    table = defaultdict(int)
    for x in rows:
        table[(x["hand"], x["verdict"])] += 1
    for hand in ("mixed", "review", "none"):
        print(f"hand {hand:6}: " + ", ".join(f"{v} {table[(hand, v)]}" for v in ("mixed", "unclear", "one_person")))
    print(f"new calls {len(usages)}, tokens in {sum(u['input'] for u in usages)} out {sum(u['output'] for u in usages)}, "
          f"cost ${cost(usages):.3f}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:] == ["screen"]:
        report_screen(screen())
    elif sys.argv[1:2] == ["pilot"]:
        pilot(int(sys.argv[2]) if len(sys.argv) > 2 else 10)
    else:
        print(__doc__)
