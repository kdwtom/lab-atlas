"""Step 8b — where is each lab's research heading? Writes output/trends.json.

A lab's papers from the first two years of the window are compared with those from the last two years:
  - shift   : 1 - cosine between the mean paper vectors of the two periods, tested against random splits of the same
              papers (a permutation test), with a Benjamini-Hochberg correction because several hundred labs are tested
  - topics  : OpenAlex topics whose share grew or shrank most between the periods
  - toward  : for a lab that shifted, the labs and sub-cluster its recent papers came closer to, and a point on the map
              in that direction (mean UMAP position of those labs)
Namesake papers merged into an OpenAlex profile would look like a change of topic, so papers unusually far from the
lab's own vector are left out first (robust per-lab cut-off), and labs marked mixed_topics are not judged at all.
Directions are chosen among the areas and labs already near the lab, so a tiny wobble towards a distant field never
becomes "the direction". Labs with fewer than MIN_PAPERS papers in either period are not judged.
This describes a change of topic, not quality.
"""
from __future__ import annotations

import logging
from collections import Counter

import numpy as np

from . import config
from .lib.io import read_json, read_jsonl, write_json
from .lib.selection import in_analysis_set
from .step07_embed import embed

log = logging.getLogger(__name__)
EARLY = (config.YEAR_FROM, config.YEAR_FROM + 1)
RECENT = (config.YEAR_TO - 1, config.YEAR_TO)
MIN_PAPERS = 4
PERMUTATIONS = 10000                    # enough resolution for the correction across several hundred labs
# At 5% no lab passes: within five years a single lab's change is hard to tell from sampling noise, although far more
# labs have small p-values than chance would give. 20% flags the clearest cases; the site says about 1 in 5 may be chance.
FDR = 0.2
TOWARD_LABS = 5
NEAR_SUBCLUSTERS = 3                    # directions are picked among the sub-clusters nearest to each period
NEAR_LABS = 20
OUTLIER_MADS = 2.5                      # a paper this many robust deviations below the lab's median similarity is set aside
OUTLIER_FLOOR = 0.72                    # ... and any paper this far from the lab's vector (about the 2% least similar)


def drop_outliers(papers: list[dict], vecs: np.ndarray, core: np.ndarray) -> tuple[list[dict], np.ndarray]:
    """Papers unusually far from the lab's own vector (often a namesake's) are set aside before comparing periods."""
    sim = vecs @ core
    med = np.median(sim)
    mad = np.median(np.abs(sim - med)) or 1e-6
    # the floor catches namesake papers in small periods, where they can pull the median itself down
    keep = (sim >= med - OUTLIER_MADS * 1.4826 * mad) & (sim >= OUTLIER_FLOOR)
    return [p for p, k in zip(papers, keep) if k], vecs[keep]


def unit_mean(m: np.ndarray) -> np.ndarray:
    v = m.mean(0)
    return v / np.linalg.norm(v)


def shift_test(early: np.ndarray, recent: np.ndarray, rng: np.random.RandomState,
               permutations: int = PERMUTATIONS) -> tuple[float, float]:
    """(observed shift, one-sided p-value): how often a random split of the same papers drifts as far apart."""
    observed = 1 - float(unit_mean(early) @ unit_mean(recent))
    pool = np.vstack([early, recent])
    n, k = len(pool), len(early)
    total = pool.sum(0)
    hits = 0
    for start in range(0, permutations, 2000):  # splits as 0/1 rows: one matrix product gives every group sum
        m = min(2000, permutations - start)
        pick = np.zeros((m, n))
        pick[np.arange(m)[:, None], np.argsort(rng.rand(m, n), axis=1)[:, :k]] = 1
        a = pick @ pool
        b = total - a
        cos = (a * b).sum(1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1))
        hits += int((1 - cos >= observed - 1e-12).sum())
    return observed, (hits + 1) / (permutations + 1)


def benjamini_hochberg(p: dict[str, float], q: float = FDR) -> set[str]:
    """Keys whose p-values pass the Benjamini-Hochberg procedure at false discovery rate q."""
    ranked = sorted(p.items(), key=lambda kv: kv[1])
    passed = 0
    for i, (_, pv) in enumerate(ranked, 1):
        if pv <= q * i / len(ranked):
            passed = i
    return {k for k, _ in ranked[:passed]}


def map_place(vec: np.ndarray, V: np.ndarray, xy: np.ndarray, skip: int, k: int = 8) -> list[float]:
    """Where a period's papers would sit on the map: similarity-weighted mean position of the k most similar other labs."""
    sim = V @ vec
    sim[skip] = -np.inf
    top = np.argsort(-sim)[:k]
    w = np.exp((sim[top] - sim[top].max()) * 40)  # sharp weights: the closest labs decide
    p = (xy[top] * w[:, None]).sum(0) / w.sum()
    return [round(float(p[0]), 5), round(float(p[1]), 5)]


def topic_shift(early: list[dict], recent: list[dict], n: int = 3) -> tuple[list[str], list[str]]:
    """Topics whose share grew most (seen in 2+ recent papers) and shrank most (seen in 2+ early papers)."""
    def shares(ps: list[dict]) -> tuple[Counter, Counter]:
        weight, papers = Counter(), Counter()
        for p in ps:
            for t in p["topics"]:
                weight[t["name"]] += t["score"]
                papers[t["name"]] += 1
        total = sum(weight.values()) or 1
        return Counter({k: v / total for k, v in weight.items()}), papers
    se, ne = shares(early)
    sr, nr = shares(recent)
    diff = {t: sr[t] - se[t] for t in set(se) | set(sr)}
    grew = [t for t, d in sorted(diff.items(), key=lambda kv: -kv[1]) if d > 0 and nr[t] >= 2][:n]
    shrank = [t for t, d in sorted(diff.items(), key=lambda kv: kv[1]) if d < 0 and ne[t] >= 2][:n]
    return grew, shrank


def run(client=None) -> None:
    analysis = read_json(config.OUTPUT_DIR / "analysis.json")
    z = np.load(config.OUTPUT_DIR / "lab_vectors.npz")
    lab_ids = z["lab_ids"].tolist()
    V = z["vectors"]
    idx = {lid: i for i, lid in enumerate(lab_ids)}
    by_lab: dict[str, dict[str, list[dict]]] = {lid: {"early": [], "recent": []} for lid in lab_ids}
    for p in read_jsonl(config.OUTPUT_DIR / "papers_raw.jsonl"):
        period = "early" if EARLY[0] <= p["year"] <= EARLY[1] else "recent" if RECENT[0] <= p["year"] <= RECENT[1] else None
        if not period:
            continue
        for lid in p["lab_ids"]:
            if lid in by_lab and in_analysis_set(p, lid):
                by_lab[lid][period].append(p)
    vec_of = embed([p for d in by_lab.values() for ps in d.values() for p in ps])  # adds missing papers to the cache

    labs = analysis["labs"]
    xy = np.array([[labs[lid]["x"], labs[lid]["y"]] for lid in lab_ids])
    subs = sorted({labs[lid]["subcluster_id"] for lid in lab_ids})
    sub_vec = {}
    for s in subs:
        m = V[[idx[lid] for lid in lab_ids if labs[lid]["subcluster_id"] == s]]
        sub_vec[s] = unit_mean(m)

    # labs whose paper lists are known to mix in other people's work (fully or partly) are not judged
    curation = read_json(config.PIPELINE_DIR / "curation" / "intro_unavailable.json")
    mixed = {lid for lid, v in curation["unavailable"].items() if v["reason"] == "mixed_topics"} | set(curation["review"])
    rng = np.random.RandomState(config.LOUVAIN_SEED)
    out: dict[str, dict] = {}
    pvals: dict[str, float] = {}
    period_vecs: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for lid in lab_ids:
        early, recent = by_lab[lid]["early"], by_lab[lid]["recent"]
        if lid in mixed:  # its paper list mixes other people's work, so a "change" would mean nothing
            continue
        e = np.stack([vec_of[p["id"]] for p in early]) if early else np.zeros((0, V.shape[1]))
        r = np.stack([vec_of[p["id"]] for p in recent]) if recent else np.zeros((0, V.shape[1]))
        if len(early):
            early, e = drop_outliers(early, e, V[idx[lid]])
        if len(recent):
            recent, r = drop_outliers(recent, r, V[idx[lid]])
        row = {"early_years": list(EARLY), "recent_years": list(RECENT),
               "early_papers": len(early), "recent_papers": len(recent)}
        if len(early) < MIN_PAPERS or len(recent) < MIN_PAPERS:
            out[lid] = {**row, "status": "insufficient"}
            continue
        shift, pv = shift_test(e, r, rng)
        grew, shrank = topic_shift(early, recent)
        pvals[lid] = pv
        period_vecs[lid] = (unit_mean(e), unit_mean(r))
        out[lid] = {**row, "status": "stable", "shift": round(shift, 4), "p_value": round(pv, 4),
                    "emerging_topics": grew, "fading_topics": shrank}
    shifted = benjamini_hochberg(pvals)
    for lid in shifted:
        e, r = period_vecs[lid]
        i = idx[lid]
        delta = V @ r - V @ e
        near = [j for j in np.argsort(-(V @ r)) if j != i][:NEAR_LABS]
        top = [j for j in sorted(near, key=lambda j: -delta[j])[:TOWARD_LABS] if delta[j] > 0]
        sub_delta = {s: float(v @ r - v @ e) for s, v in sub_vec.items()}
        near_recent = sorted(sub_vec, key=lambda s: -float(sub_vec[s] @ r))[:NEAR_SUBCLUSTERS]
        near_early = sorted(sub_vec, key=lambda s: -float(sub_vec[s] @ e))[:NEAR_SUBCLUSTERS]
        toward_sub = max(near_recent, key=sub_delta.get)
        away_sub = min(near_early, key=sub_delta.get)
        row = out[lid]
        row.update(status="shifted", toward_lab_ids=[lab_ids[j] for j in top],
                   early_xy=map_place(e, V, xy, i), recent_xy=map_place(r, V, xy, i))
        if sub_delta[toward_sub] > 0:
            row["toward_subcluster_id"] = toward_sub
        if sub_delta[away_sub] < 0 and away_sub != toward_sub:
            row["away_subcluster_id"] = away_sub
        if top:
            w = delta[top]
            target = (xy[top] * w[:, None]).sum(0) / w.sum()
            row["toward_xy"] = [round(float(target[0]), 5), round(float(target[1]), 5)]
    write_json(config.OUTPUT_DIR / "trends.json", out)
    status = Counter(v["status"] for v in out.values())
    log.info("trends: %d shifted, %d stable, %d not judged (fewer than %d papers in %d-%d or %d-%d), %d mixed labs skipped",
             status["shifted"], status["stable"], status["insufficient"], MIN_PAPERS, *EARLY, *RECENT, len(mixed))
