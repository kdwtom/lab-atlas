"""Korean lab introductions written by the Claude API (PLAN_PHASE3.md S6).

Same rules as the hand-written intros (PLAN_PHASE2.md 3): evidence is the lab's recent last/corresponding-author
titles (up to 10), its OpenAlex keywords and its department. Abstracts are not read, so an intro names research
topics only, in about two sentences, without figures, awards or people. When the titles cannot support an intro,
the model returns a reason instead (insufficient_papers, mixed_topics, wrong_field), as the hand review did.

    python -m pipeline.write_intros pilot 20     # first 20 labs without an intro; prints them and the cost
    python -m pipeline.write_intros all          # every lab still without an intro or a reason

Output: curation/summaries/batch_api_NN.json ({"labs": {...}}) and new entries in curation/intro_unavailable.json.
Responses are cached in cache/intros/, so a rerun does not pay twice.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sys
from collections import defaultdict

from . import config
from .lib.io import read_json, read_jsonl, write_json
from .lib.selection import in_analysis_set, is_senior, pub_date

log = logging.getLogger(__name__)
MODEL = "claude-opus-5-5"
PRICE = (4.0, 20.0)                       # USD per million input / output tokens
CACHE = config.CACHE_DIR / "intros"
SUMMARIES = config.PIPELINE_DIR / "curation" / "summaries"
UNAVAILABLE = config.PIPELINE_DIR / "curation" / "intro_unavailable.json"
PER_FILE = 50

SYSTEM = """당신은 한국 대학 자연과학 연구실 지도(Lab Atlas)의 연구실 소개를 쓴다. 독자는 대학원 진학을 고민하는 학부생이다.

근거는 연구실 책임자가 마지막·교신저자인 최근 논문 제목, OpenAlex 키워드, 학과뿐이다. 초록은 없다.

쓰는 법:
- 한국어 평서문 2문장 안팎(최대 3문장, 220자 안팎). "~를 연구한다", "~를 다룬다"처럼 끝맺는다.
- 제목들에 반복해서 나오는 연구 주제와 대상, 접근 방식을 묶어 쓴다. 전문용어는 처음 나올 때 괄호에 영어를 붙일 수 있다.
- 근거에 없는 수치, 성과, 수상, 인물, 기관, 순위, 평가("세계적인", "선도하는")는 쓰지 않는다. 연구실 이름이나 교수 이름도 쓰지 않는다.
- 제목 하나만으로 확대 해석하지 않는다.

소개를 쓰지 않는 경우(verdict):
- insufficient_papers: 제목이 너무 적거나 일반적이어서 연구 주제를 말할 수 없다.
- mixed_topics: 제목의 절반 안팎이 서로 동떨어진 분야여서 동명이인 논문이 섞인 것으로 보인다.
- wrong_field: 제목 대부분이 학과와 맞지 않아 프로필 매칭 자체가 의심된다.
이때 intro_ko는 빈 문자열로 두고 note에 판단 근거를 영어 한 문장으로 쓴다."""

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["verdict", "intro_ko", "note"],
          "properties": {"verdict": {"type": "string",
                                     "enum": ["intro", "insufficient_papers", "mixed_topics", "wrong_field"]},
                         "intro_ko": {"type": "string"}, "note": {"type": "string"}}}


def existing() -> tuple[dict[str, str], dict]:
    intros: dict[str, str] = {}
    for f in sorted(SUMMARIES.glob("batch_*.json")):
        intros.update(read_json(f).get("labs") or {})
    return intros, read_json(UNAVAILABLE)


def evidence() -> dict[str, dict]:
    analysis = read_json(config.OUTPUT_DIR / "analysis.json")
    status = {s["lab_id"]: s for s in read_json(config.OUTPUT_DIR / "lab_status.json")}
    by_lab = defaultdict(list)
    for p in read_jsonl(config.OUTPUT_DIR / "papers_raw.jsonl"):
        for lid in p["lab_ids"]:
            if lid in analysis["labs"]:
                by_lab[lid].append(p)
    out = {}
    for lid in analysis["labs"]:
        s = status[lid]
        depts = [config.DEPT_BY_CODE[c] for c in s["depts"]]
        senior = sorted((p for p in by_lab[lid] if in_analysis_set(p, lid) and is_senior(p, lid)), key=pub_date,
                        reverse=True)
        out[lid] = {"dept": f"{depts[0].univ_name_ko} " + " · ".join(f"{d.dept_name_ko} ({d.discipline})" for d in depts),
                    "keywords": analysis["labs"][lid]["keywords"],
                    "titles": [f"({p['year']}) {p['title']}" for p in senior[:10]]}
    return out


def prompt_for(ev: dict) -> str:
    return (f"학과: {ev['dept']}\nOpenAlex 키워드: {'; '.join(ev['keywords'])}\n"
            f"최근 마지막·교신저자 논문 제목 ({len(ev['titles'])}편):\n" + "\n".join(f"- {t}" for t in ev["titles"]))


def examples(intros: dict[str, str], ev: dict[str, dict], n: int = 3) -> list[dict]:
    """A few hand-written intros as style examples (fixed choice, so the prompt and cache stay stable)."""
    picks = [lid for lid in sorted(intros) if lid in ev and len(ev[lid]["titles"]) >= 6][:: max(1, len(intros) // 40)][:n]
    msgs = []
    for lid in picks:
        msgs += [{"role": "user", "content": prompt_for(ev[lid])},
                 {"role": "assistant", "content": json.dumps({"verdict": "intro", "intro_ko": intros[lid], "note": ""},
                                                             ensure_ascii=False)}]
    return msgs


def write_one(ai, ev: dict, shots: list[dict]) -> dict:
    user = prompt_for(ev)
    key = hashlib.sha256((MODEL + SYSTEM + json.dumps(shots, ensure_ascii=False) + user).encode()).hexdigest()[:24]
    path = CACHE / f"{key}.json"
    if path.exists():
        return {**read_json(path), "cached": True}
    r = ai.messages.create(model=MODEL, max_tokens=16000, system=SYSTEM,
                           messages=shots + [{"role": "user", "content": user}],
                           output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}})
    if r.stop_reason != "end_turn":
        raise RuntimeError(f"intro writer stopped with {r.stop_reason}")
    data = json.loads(next(b.text for b in r.content if b.type == "text"))
    out = {**data, "usage": {"input": r.usage.input_tokens, "output": r.usage.output_tokens}}
    CACHE.mkdir(parents=True, exist_ok=True)
    write_json(path, out)
    return {**out, "cached": False}


def run(limit: int | None, save: bool) -> None:
    import anthropic
    ai = anthropic.Anthropic()   # key from local.env, loaded by config
    intros, unavailable = existing()
    ev = evidence()
    todo = [lid for lid in sorted(ev) if lid not in intros and lid not in unavailable["unavailable"]]
    if limit:   # spread the pilot over universities and fields instead of taking one university's first labs
        step = max(1, len(todo) // limit)
        todo = todo[::step][:limit]
    shots = examples(intros, ev)
    results, usages = {}, []
    for n, lid in enumerate(todo, 1):
        r = write_one(ai, ev[lid], shots)
        if not r["cached"]:
            usages.append(r["usage"])
        results[lid] = r
        if n % 25 == 0:
            print(f"  {n}/{len(todo)}", file=sys.stderr, flush=True)
    cost = sum(u["input"] * PRICE[0] + u["output"] * PRICE[1] for u in usages) / 1e6
    written = {lid: r["intro_ko"].strip() for lid, r in results.items() if r["verdict"] == "intro"}
    refused = {lid: {"reason": r["verdict"], "note": f"API intro writer: {r['note']}"}
               for lid, r in results.items() if r["verdict"] != "intro"}
    write_json(config.OUTPUT_DIR / "intro_drafts.json",
               {lid: {"evidence": ev[lid], **{k: v for k, v in r.items() if k != "usage"}} for lid, r in results.items()})
    print(f"labs {len(results)}: intros {len(written)}, refused {len(refused)}")
    by = defaultdict(int)
    for v in refused.values():
        by[v["reason"]] += 1
    print(f"refusals: {dict(by)}; new calls {len(usages)}, tokens in {sum(u['input'] for u in usages)} "
          f"out {sum(u['output'] for u in usages)}, cost ${cost:.3f} (${cost / max(len(usages), 1):.4f} per lab)")
    if save:
        items = sorted(written.items())
        start = 1 + len(list(SUMMARIES.glob("batch_api_*.json")))
        for i in range(0, len(items), PER_FILE):
            write_json(SUMMARIES / f"batch_api_{start + i // PER_FILE:02d}.json", {"labs": dict(items[i:i + PER_FILE])})
        unavailable["unavailable"].update(refused)
        write_json(UNAVAILABLE, unavailable)
        print(f"saved {len(written)} intros and {len(refused)} reasons")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:2] == ["pilot"]:
        run(int(sys.argv[2]) if len(sys.argv) > 2 else 20, save=False)
    elif sys.argv[1:] == ["all"]:
        run(None, save=True)
    else:
        print(__doc__)
