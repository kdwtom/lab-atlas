"""Namesake resolution (PLAN_PHASE3.md 3): which OpenAlex author is this professor?

Evidence per candidate, beyond what step 3 already checks (name, affiliation, field share, anchors, ORCID):
  dept_coauthor  papers in the window written with another professor of the same department (by OpenAlex id);
                 a namesake in the university hospital rarely shares papers with the chemistry department
  subfield_sim   cosine between the candidate's OpenAlex subfield mix and the department's (other labs' papers)
  home_recent    papers in the window that list the matched institution for this author
  pi_papers      papers counting toward the field's selection rule (same as step 3's tie-break)

    python -m pipeline.namesake eval              # score the current six universities against the hand-made decisions
    python -m pipeline.namesake pilot hand 10     # ask the adjudicator about uncertain cases; report accuracy and cost

The gold set is the hand-reviewed decisions in curation/match_overrides.json (truth known) plus multi-candidate
matches nobody changed (assumed right, reported separately as "silver"). The rules were designed while looking at
part of this set, so the numbers are optimistic for new universities.
"""
from __future__ import annotations

import logging
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

from . import config
from .lib.http import CachedClient
from .lib.io import read_json, read_jsonl, write_json
from .lib.openalex import OpenAlex, short_id
from .step03_match import pi_paper_count

log = logging.getLogger(__name__)


@dataclass
class Features:
    openalex_id: str
    display_name: str
    name_ok: bool
    affiliation_ok: bool
    field_share: float
    anchor_hits: int
    works_window: int = 0
    home_recent: int = 0
    dept_coauthor: int = 0
    subfield_sim: float = 0.0      # against the whole department's mix
    subfield_near: float = 0.0     # against the closest single lab in the department
    pi_papers: int = 0
    top_titles: list[str] = field(default_factory=list)


def cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def subfields(works: list[dict]) -> Counter:
    c: Counter = Counter()
    for w in works:
        t = (w.get("topics") or [{}])[0]
        sf = (t.get("subfield") or {}).get("display_name") if isinstance(t.get("subfield"), dict) else t.get("subfield")
        if sf:
            c[sf] += 1
    return c


class Context:
    """Department-level evidence: who else is in the department, and what its papers are about."""

    def __init__(self, matches: list[dict], papers: list[dict]):
        self.dept_ids: dict[str, set[str]] = defaultdict(set)      # dept -> OpenAlex ids of matched professors
        self.owner: dict[str, tuple[str, str]] = {}                # OpenAlex id -> (dept, name) for exclusion
        for m in matches:
            if m["status"] == "matched":
                self.dept_ids[m["dept"]].add(m["openalex_id"])
                self.owner[m["openalex_id"]] = (m["dept"], m["name_ko"] or m["name_en"])
        lab_dept = {f"{m['univ']}-{m['openalex_id']}": m["dept"] for m in matches if m["status"] == "matched"}
        self.dept_subfields: dict[str, dict[str, Counter]] = defaultdict(dict)  # dept -> lab id -> subfields
        for p in papers:
            t = (p.get("topics") or [{}])[0]
            sf = t.get("subfield")
            if not sf:
                continue
            for lid in p["lab_ids"]:
                d = lab_dept.get(lid)
                if d:
                    self.dept_subfields[d].setdefault(lid, Counter())[sf] += 1

    def nearest_lab(self, dept: str, exclude_lab: Optional[str], mix: Counter) -> float:
        """Best cosine against one colleague's lab. Departments such as math or CS span many subfields, so a
        combinatorialist looks unlike the department as a whole but very like the other combinatorics lab."""
        return max((cosine(mix, c) for lid, c in self.dept_subfields.get(dept, {}).items()
                    if lid != exclude_lab and sum(c.values()) >= 3), default=0.0)

    def dept_mix(self, dept: str, exclude_lab: Optional[str]) -> Counter:
        total: Counter = Counter()
        for lid, c in self.dept_subfields.get(dept, {}).items():
            if lid != exclude_lab:
                total.update(c)
        return total


def features(oa: OpenAlex, ctx: Context, m: dict, cand: dict, inst_id: str) -> Features:
    aid = cand["openalex_id"]
    disc = config.DEPT_BY_CODE[m["dept"]].disc
    f = Features(openalex_id=aid, display_name=cand["display_name"], name_ok=cand["name_ok"],
                 affiliation_ok=cand["affiliation_ok"], field_share=cand["field_share"], anchor_hits=cand["anchor_hits"])
    if not cand["name_ok"]:   # scored -1 whatever the papers say; skip the OpenAlex works download
        return f
    colleagues = ctx.dept_ids.get(m["dept"], set()) - {aid}
    works = []
    for w, _ in oa.works_for_author(aid, config.YEAR_FROM):
        if w.get("type") not in disc.work_types or not (config.YEAR_FROM <= (w.get("publication_year") or 0) <= config.YEAR_TO):
            continue
        au = w.get("authorships") or []
        mine = next((a for a in au if short_id((a.get("author") or {}).get("id")) == aid), None)
        if not mine:
            continue
        works.append(w)
        if any(short_id(i.get("id")) == inst_id for i in mine.get("institutions") or []):
            f.home_recent += 1
        if any(short_id((a.get("author") or {}).get("id")) in colleagues for a in au):
            f.dept_coauthor += 1
    f.works_window = len(works)
    own_lab = f"{m['univ']}-{aid}"
    mix = subfields(works)
    f.subfield_sim = round(cosine(mix, ctx.dept_mix(m["dept"], own_lab)), 3)
    f.subfield_near = round(ctx.nearest_lab(m["dept"], own_lab, mix), 3)
    f.pi_papers = pi_paper_count(oa, aid, disc)
    f.top_titles = [(w.get("display_name") or "")[:110] for w in works[:8]]
    return f


# ------------------------------------------------------------------ rule decision
# Weights picked by a small grid search on namesake_eval.json (hand + silver). Subfield fit got weight 0 there:
# step 3's field share already carries the topic signal, and departments like math/CS span too many subfields.
# subfield_sim / subfield_near stay in the features for the adjudicator to read.
CERTAIN_MARGIN = 0.8


def score(f: Features) -> float:
    """Higher is more likely the professor."""
    if not f.name_ok or f.works_window == 0:
        return -1.0
    n = f.works_window
    home = (f.home_recent / n) * min(n, 10) / 10   # a one-paper fragment cannot score full home share
    return 1.0 * min(f.dept_coauthor, 5) / 5 + 1.0 * f.field_share + 1.0 * home + (1.0 if f.anchor_hits else 0.0)


@dataclass
class Decision:
    choice: Optional[str]          # OpenAlex id, or None for "no reliable profile"
    margin: float
    certain: bool                  # False = send to the adjudicator / human review
    reason: str


def decide(feats: list[Features]) -> Decision:
    ranked = sorted(feats, key=score, reverse=True)
    if not ranked or score(ranked[0]) <= 0:
        # not certain: the right profile may be spelled differently or have no papers in the window yet
        return Decision(None, 0.0, False, "no name-matching candidate with papers in the window")
    best = ranked[0]
    second = score(ranked[1]) if len(ranked) > 1 else 0.0
    margin = round(score(best) - max(second, 0.0), 3)
    # weak = nothing ties the profile to this university beyond the name: few home papers, no colleagues, no anchor
    weak = best.home_recent < 0.3 * best.works_window and best.dept_coauthor == 0 and not best.anchor_hits
    certain = not weak and (margin >= CERTAIN_MARGIN or best.anchor_hits > 0)
    return Decision(best.openalex_id, margin, certain,
                    f"field {best.field_share:.2f}, coauthors in dept {best.dept_coauthor}, "
                    f"home {best.home_recent}/{best.works_window}, margin {margin}")


# ------------------------------------------------------------------ adjudicator (Claude API, uncertain cases only)
ADJ_MODEL = "claude-opus-5-5"
ADJ_PRICE = (4.0, 20.0)            # USD per million input / output tokens (Opus 5.5)
ADJ_CACHE = config.CACHE_DIR / "adjudicator"
ADJ_SYSTEM = """You decide which OpenAlex author profile belongs to a given Korean university professor.
Common Korean names produce many namesakes: hospital doctors, engineers or students at the same university,
and fragments of one person's work split across several profiles. You get the professor's department and research
fields from the faculty page, and for each candidate profile: counts computed from OpenAlex and recent paper titles.

How to judge:
- The professor's own papers should fit the department and the listed research fields. Titles matter most.
- A profile whose papers are mostly another discipline (medicine, mechanical engineering, materials) is a namesake,
  even if it lists the right university.
- Small profiles (1-3 papers) are often fragments. Prefer the profile carrying the professor's main body of work,
  unless the large profile is clearly someone else.
- Answer "none" when no candidate looks like this professor.
- confidence: "high" only when the titles leave little doubt; "low" when you are guessing."""


def candidate_block(i: int, f: Features) -> str:
    titles = "\n".join(f"    - {t}" for t in f.top_titles) or "    (no papers in the window)"
    return (f"C{i}: {f.display_name}\n  papers {config.YEAR_FROM}-{config.YEAR_TO}: {f.works_window}, "
            f"listing this university: {f.home_recent}, with department colleagues: {f.dept_coauthor}, "
            f"share in the department's discipline: {f.field_share:.2f}\n  recent titles:\n{titles}")


def adjudicate(ai, m: dict, fac: Optional[dict], feats: list[Features]) -> dict:
    """Ask Claude. Returns {choice: OpenAlex id or None, confidence, reason, usage}. Cached by prompt."""
    import hashlib
    d = config.DEPT_BY_CODE[m["dept"]]
    fac = fac or {}
    shown = sorted((f for f in feats if f.works_window > 0), key=score, reverse=True)[:8]
    if not shown:
        return {"choice": None, "confidence": "high", "reason": "no candidate has papers in the window",
                "model": None, "usage": {"input": 0, "output": 0}, "cached": True}
    prof = (f"Professor: {m['name_ko'] or ''} ({m['name_en'] or ''})\n"
            f"University: {d.univ_name_en} ({d.univ_name_ko}), department: {d.dept_name_ko} ({d.discipline})\n"
            f"Lab: {fac.get('lab_name') or '-'}\n"
            f"Research fields on the faculty page: {', '.join(fac.get('research_fields') or []) or '-'}")
    prompt = prof + "\n\nCandidates:\n" + "\n\n".join(candidate_block(i, f) for i, f in enumerate(shown, 1))
    key = hashlib.sha256((ADJ_MODEL + ADJ_SYSTEM + prompt).encode()).hexdigest()[:24]
    path = ADJ_CACHE / f"{key}.json"
    if path.exists():
        out = read_json(path)
        out["cached"] = True
        return out
    labels = [f"C{i}" for i in range(1, len(shown) + 1)] + ["none"]
    schema = {"type": "object", "additionalProperties": False, "required": ["choice", "confidence", "reason"],
              "properties": {"choice": {"type": "string", "enum": labels},
                             "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                             "reason": {"type": "string"}}}
    r = ai.messages.create(model=ADJ_MODEL, max_tokens=8000, system=ADJ_SYSTEM,
                           messages=[{"role": "user", "content": prompt}],
                           output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}})
    import json as _json
    data = _json.loads(next(b.text for b in r.content if b.type == "text"))
    pick = None if data["choice"] == "none" else shown[int(data["choice"][1:]) - 1].openalex_id
    out = {"choice": pick, "confidence": data["confidence"], "reason": data["reason"], "model": r.model,
           "usage": {"input": r.usage.input_tokens, "output": r.usage.output_tokens}}
    ADJ_CACHE.mkdir(parents=True, exist_ok=True)
    write_json(path, out)
    out["cached"] = False
    return out


def cost(usages: list[dict]) -> float:
    return sum(u["input"] * ADJ_PRICE[0] + u["output"] * ADJ_PRICE[1] for u in usages) / 1e6


def pilot(kind: str, limit: int) -> None:
    """Run the adjudicator on uncertain cases of the saved evaluation and report accuracy and cost."""
    import anthropic
    ai = anthropic.Anthropic()   # key from local.env, loaded by config
    rows = read_json(config.OUTPUT_DIR / "namesake_eval.json")
    fac = {f"{f['dept']}|{f['name_ko'] or f['name_en']}": f for f in read_json(config.OUTPUT_DIR / "faculty.json")}
    matches = {f"{m['dept']}|{m['name_ko'] or m['name_en']}": m for m in read_json(config.OUTPUT_DIR / "matches.json")}
    todo = [r for r in rows if not r["certain"] and r["kind"] == kind][:limit]
    usages, results = [], []
    for n, r in enumerate(todo, 1):
        k = f"{r['dept']}|{r['name']}"
        feats = [Features(**c) for c in r["candidates"]]
        a = adjudicate(ai, matches[k], fac.get(k), feats)
        if not a["cached"]:
            usages.append(a["usage"])
        ok = a["choice"] == r["truth"]
        results.append((r, a, ok))
        print(f"  {n:3}/{len(todo)} {'OK ' if ok else 'BAD'} {a['confidence']:6} {r['dept']} {r['name']}", file=sys.stderr, flush=True)
    write_json(config.OUTPUT_DIR / f"namesake_pilot_{kind}.json",
               [{"dept": r["dept"], "name": r["name"], "truth": r["truth"], "rule": r["choice"], **a, "correct": ok}
                for r, a, ok in results])
    for conf in ("high", "medium", "low"):
        sub = [ok for _, a, ok in results if a["confidence"] == conf]
        print(f"{conf:6} n={len(sub):3} correct={sum(sub)}")
    print(f"total n={len(results)} correct={sum(ok for *_, ok in results)} | new calls {len(usages)}, "
          f"tokens in {sum(u['input'] for u in usages)} out {sum(u['output'] for u in usages)}, "
          f"cost ${cost(usages):.3f} (${cost(usages) / max(len(usages), 1):.4f} per call)")


# ------------------------------------------------------------------ evaluation on the existing universities
def gold_set(matches: list[dict], overrides: dict, flags: dict) -> list[tuple[dict, Optional[str], str]]:
    """(match, true OpenAlex id or None, kind). kind = hand (reviewed) or silver (unchanged multi-candidate match)."""
    key = lambda m: f"{m['dept']}|{m['name_ko'] or m['name_en']}"  # noqa: E731
    out = []
    flagged = set(flags.get("unavailable", {})) | set(flags.get("review", {}))
    for m in matches:
        k = key(m)
        if k in overrides["force"]:
            out.append((m, overrides["force"][k]["openalex_id"], "hand"))
        elif k in overrides["exclude"]:
            out.append((m, None, "hand"))
        elif (m["status"] == "matched" and len(m["candidates"]) >= 2
              and f"{m['univ']}-{m['openalex_id']}" not in flagged):
            out.append((m, m["openalex_id"], "silver"))
    return out


def evaluate(client: CachedClient) -> None:
    oa = OpenAlex(client)
    matches = read_json(config.OUTPUT_DIR / "matches.json")
    ctx = Context(matches, read_jsonl(config.OUTPUT_DIR / "papers_raw.jsonl"))
    overrides = read_json(config.PIPELINE_DIR / "curation" / "match_overrides.json")
    flags = read_json(config.PIPELINE_DIR / "curation" / "intro_unavailable.json")
    inst = read_json(config.OUTPUT_DIR / "institutions.json")
    rows = []
    gold = gold_set(matches, overrides, flags)
    for n, (m, truth, kind) in enumerate(gold, 1):
        if n % 25 == 0:
            print(f"  {n}/{len(gold)}", file=sys.stderr, flush=True)
        feats = [features(oa, ctx, m, c, inst[m["univ"]]["id"]) for c in m["candidates"]]
        d = decide(feats)
        rows.append({"dept": m["dept"], "name": m["name_ko"] or m["name_en"], "kind": kind, "truth": truth,
                     "choice": d.choice, "certain": d.certain, "margin": d.margin, "reason": d.reason,
                     "correct": d.choice == truth, "candidates": [vars(f) for f in feats]})
    write_json(config.OUTPUT_DIR / "namesake_eval.json", rows)
    for kind in ("hand", "silver"):
        rs = [r for r in rows if r["kind"] == kind]
        cert = [r for r in rs if r["certain"]]
        print(f"{kind:6} n={len(rs):3} correct={sum(r['correct'] for r in rs):3} "
              f"certain={len(cert):3} (correct among certain {sum(r['correct'] for r in cert)}) "
              f"to review={len(rs) - len(cert)}")


# ------------------------------------------------------------------ resolve (new universities, S4)
DECISIONS = config.PIPELINE_DIR / "curation" / "namesake_decisions.json"
REVIEW = config.OUTPUT_DIR / "namesake_review.json"


def resolve(client: CachedClient, univs: list[str]) -> None:
    """Rule decision for every professor with candidates; the adjudicator for uncertain ones.

    Accepted automatically: certain rule decisions and adjudicator answers with high or medium confidence
    (user decision 2026-11-11). Low-confidence answers go to namesake_review.json for a person. Decisions that
    differ from step 3's pick are written to curation/namesake_decisions.json, which step 3 applies below the
    hand-made match_overrides.json.
    """
    import anthropic
    ai = anthropic.Anthropic()   # key from local.env, loaded by config
    oa = OpenAlex(client)
    matches = read_json(config.OUTPUT_DIR / "matches.json")
    ctx = Context(matches, read_jsonl(config.OUTPUT_DIR / "papers_raw.jsonl"))
    inst = read_json(config.OUTPUT_DIR / "institutions.json")
    fac = {f"{f['dept']}|{f['name_ko'] or f['name_en']}": f for f in read_json(config.OUTPUT_DIR / "faculty.json")}
    hand = read_json(config.PIPELINE_DIR / "curation" / "match_overrides.json")
    # professors whose candidates all fail the name check (step 3: name_mismatch) are left to step 3
    todo = [m for m in matches if m["univ"] in univs and any(c["name_ok"] for c in m["candidates"])
            and f"{m['dept']}|{m['name_ko'] or m['name_en']}" not in hand["force"] | hand["exclude"]]
    force, exclude, review, usages, rows = {}, {}, [], [], []
    # after a rerun of step 3, matches.json already carries earlier decisions, so "same as step 3" can mean
    # "same as our own earlier decision": keep those entries instead of dropping them
    old = read_json(DECISIONS) if DECISIONS.exists() else {"force": {}, "exclude": {}}
    for n, m in enumerate(todo, 1):
        key = f"{m['dept']}|{m['name_ko'] or m['name_en']}"
        feats = [features(oa, ctx, m, c, inst[m["univ"]]["id"]) for c in m["candidates"]]
        if not any(f.works_window > 0 for f in feats):
            # nothing to tell namesakes apart by; step 3's pick stands and the selection step drops it for
            # too few papers, as on the first six universities
            continue
        d = decide(feats)
        source, final, conf, why = "rule", d.choice, "certain", d.reason
        if not d.certain:
            a = adjudicate(ai, m, fac.get(key), feats)
            if not a["cached"]:
                usages.append(a["usage"])
            source, final, conf, why = "adjudicator", a["choice"], a["confidence"], a["reason"]
        current = m["openalex_id"] if m["status"] == "matched" else None
        row = {"key": key, "univ": m["univ"], "dept": m["dept"], "name_ko": m["name_ko"], "name_en": m["name_en"],
               "faculty_page_url": m["faculty_page_url"], "research_fields": (fac.get(key) or {}).get("research_fields"),
               "step3": current, "step3_reason": m.get("reason"), "rule": d.choice, "rule_certain": d.certain,
               "source": source, "choice": final, "confidence": conf, "why": why,
               "candidates": [vars(f) for f in sorted(feats, key=score, reverse=True) if f.works_window > 0][:8]}
        rows.append(row)
        if conf == "low":
            review.append(row)
        elif (final != current or (final and old["force"].get(key, {}).get("openalex_id") == final)
              or (not final and key in old["exclude"])):
            note = f"namesake system ({source}, {conf}): {why}"[:300]
            if final:
                force[key] = {"openalex_id": final, "note": note}
            else:
                exclude[key] = {"note": note}
        if n % 25 == 0:
            print(f"  {n}/{len(todo)} | calls {len(usages)} ${cost(usages):.2f}", file=sys.stderr, flush=True)
    keep = lambda d: {k: v for k, v in d.items() if k.split("-", 1)[0] not in univs}  # noqa: E731
    write_json(DECISIONS, {"_comment": "Automatic namesake decisions (pipeline/namesake.py resolve). Applied by step 3 "
                                       "below match_overrides.json; low-confidence cases are not here but in "
                                       "output/namesake_review.json.",
                           "force": {**keep(old["force"]), **force}, "exclude": {**keep(old["exclude"]), **exclude}})
    write_json(REVIEW, review)
    write_json(config.OUTPUT_DIR / "namesake_resolve.json", rows)
    by = Counter((r["source"], r["confidence"]) for r in rows)
    print(f"professors with candidates {len(rows)}: " + ", ".join(f"{s}/{c} {v}" for (s, c), v in sorted(by.items())))
    print(f"changed from step 3: force {len(force)}, exclude {len(exclude)}; for review {len(review)}")
    print(f"adjudicator calls {len(usages)}, cost ${cost(usages):.2f}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:] == ["eval"]:
        evaluate(CachedClient())
    elif sys.argv[1:2] == ["resolve"]:
        resolve(CachedClient(), sys.argv[2].split(","))
    elif sys.argv[1:2] == ["pilot"]:
        pilot(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 10)
    else:
        print(__doc__)
