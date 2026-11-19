"""Korean renderings of the English research terms the site shows, for bilingual search (F1, tester feedback).

The vocabulary is every OpenAlex term a visitor can meet: lab keywords, yearly keywords, paper topics and their
subfields. The Claude API gives each term one to three Korean renderings (the usual Korean term, a common
synonym, a Korean abbreviation where one is in use). The site matches a Korean query against these renderings
and so finds labs whose keywords are English, and the other way round.

    python -m pipeline.search_terms pilot     # one batch; prints the renderings and the cost
    python -m pipeline.search_terms all       # every term without a rendering yet

Output: curation/search_terms_ko.json {english term: [korean, ...]} (kept, reviewed by eye; reruns only add
missing terms). Responses are cached in cache/search_terms/.
"""
from __future__ import annotations

import hashlib
import json
import sys

from . import config
from .lib.io import read_json, read_jsonl, write_json

MODEL = "claude-sonnet-5-5"
PRICE = (2.0, 10.0)            # USD per million input / output tokens
BATCH = 120
CACHE = config.CACHE_DIR / "search_terms"
OUT = config.PIPELINE_DIR / "curation" / "search_terms_ko.json"

SYSTEM = """You translate English research-topic labels (OpenAlex topics and subfields) into Korean for a search index
used by Korean undergraduates looking for graduate labs in the natural sciences.

For each label give 1 to 3 Korean renderings, most common first:
- the term Korean researchers and textbooks actually use (e.g. "Immunology" -> "면역학");
- if useful, a shorter everyday form or a common synonym (e.g. "Graph Neural Networks" -> "그래프 신경망", "GNN");
- keep established English acronyms or loanwords when Koreans use them as is (e.g. "CRISPR", "MOF").
Drop filler words such as "Advanced", "Research", "Studies", "Techniques", "Applications" unless they carry meaning.
Every input label must appear exactly once in the output, spelled exactly as given."""


def vocabulary() -> list[str]:
    """English terms a visitor can see on the site, from the analysis and paper data."""
    analysis = read_json(config.OUTPUT_DIR / "analysis.json")
    terms: set[str] = set()
    for lab in analysis["labs"].values():
        terms.update(lab["keywords"])
        for y in lab.get("keyword_timeline") or []:
            terms.update(y["keywords"])
    for p in read_jsonl(config.OUTPUT_DIR / "papers_raw.jsonl"):
        for t in p.get("topics") or []:
            terms.add(t["name"])
            if t.get("subfield"):
                terms.add(t["subfield"])
    return sorted(t for t in terms if t)


def translate(ai, batch: list[str]) -> tuple[dict[str, list[str]], dict]:
    key = hashlib.sha256((MODEL + SYSTEM + "\n".join(batch)).encode()).hexdigest()[:24]
    path = CACHE / f"{key}.json"
    if path.exists():
        d = read_json(path)
        return d["terms"], {"input": 0, "output": 0}
    schema = {"type": "object", "additionalProperties": False, "required": ["terms"],
              "properties": {"terms": {"type": "array", "items": {
                  "type": "object", "additionalProperties": False, "required": ["en", "ko"],
                  "properties": {"en": {"type": "string"}, "ko": {"type": "array", "items": {"type": "string"}}}}}}}
    r = ai.messages.create(model=MODEL, max_tokens=16000, system=SYSTEM,
                           messages=[{"role": "user", "content": "\n".join(batch)}],
                           output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}})
    if r.stop_reason != "end_turn":
        raise RuntimeError(f"stopped with {r.stop_reason}")
    data = json.loads(next(b.text for b in r.content if b.type == "text"))
    wanted = set(batch)
    out = {t["en"]: [k.strip() for k in t["ko"] if k.strip()][:3] for t in data["terms"] if t["en"] in wanted}
    CACHE.mkdir(parents=True, exist_ok=True)
    write_json(path, {"terms": out})
    return out, {"input": r.usage.input_tokens, "output": r.usage.output_tokens}


def run(pilot: bool) -> None:
    import anthropic
    ai = anthropic.Anthropic()   # key from local.env, loaded by config
    have = read_json(OUT) if OUT.exists() else {}
    todo = [t for t in vocabulary() if t not in have]
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    if pilot:
        batches = batches[:1]
    got, usages = {}, []
    for n, b in enumerate(batches, 1):
        out, u = translate(ai, b)
        got.update(out)
        usages.append(u)
        print(f"  batch {n}/{len(batches)}: {len(out)}/{len(b)} terms", file=sys.stderr, flush=True)
    cost = sum(u["input"] * PRICE[0] + u["output"] * PRICE[1] for u in usages) / 1e6
    missing = [t for b in batches for t in b if t not in got]
    print(f"terms {len(todo)} to do, rendered {len(got)}, missing {len(missing)}; cost ${cost:.3f}")
    if pilot:
        for t in list(got)[:40]:
            print(f"  {t} -> {', '.join(got[t])}")
        return
    write_json(OUT, dict(sorted({**have, **got}.items())))
    print(f"saved {len(have) + len(got)} terms to {OUT.name}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:] == ["pilot"]:
        run(pilot=True)
    elif sys.argv[1:] == ["all"]:
        run(pilot=False)
    else:
        print(__doc__)
