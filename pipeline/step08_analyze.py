"""Step 8 — similarity edges, co-authorship edges, Louvain clusters, UMAP layout, keywords.

Each similarity edge also records the lab papers whose vectors are closest, so readers can judge the link from
titles (the shared topics come from OpenAlex and are not what the similarity is computed from).

Similarity edges = each lab's top-k neighbours above a data-driven threshold, plus a "bridge" to its most
similar lab in a different field (same threshold) so cross-disciplinary neighbours are never crowded out
(PLAN_PHASE1.md 3-4). Edges between labs of different fields carry cross=True.

Inputs : lab_vectors.npz (step 7), papers_raw.jsonl, lab_status.json,
         curation/cluster_labels.json (hand-written Korean labels, optional)
Output : output/analysis.json
"""
from __future__ import annotations

import logging
import math
from collections import Counter, defaultdict
from itertools import combinations

import numpy as np

from . import config
from .lib.io import read_json, read_jsonl, write_json
from .lib.selection import in_analysis_set
from .lib.textutil import norm_title
from .schemas import Cluster, Edge
from .step07_embed import cached_paper_vectors

log = logging.getLogger(__name__)
LABELS_PATH = config.PIPELINE_DIR / "curation" / "cluster_labels.json"


# ------------------------------------------------------------------ keywords
def topic_profiles(papers: list[dict], lab_ids: list[str]) -> dict[str, Counter]:
    """lab -> {topic name: summed OpenAlex topic score over the lab's analysis papers}."""
    prof = {lid: Counter() for lid in lab_ids}
    for p in papers:
        for lid in p["lab_ids"]:
            if lid in prof and in_analysis_set(p, lid):
                for t in p["topics"]:
                    prof[lid][t["name"]] += t["score"]
    return prof


def shared_keywords(a: Counter, b: Counter, n: int = 3) -> list[str]:
    sa, sb = sum(a.values()) or 1, sum(b.values()) or 1
    common = {t: min(a[t] / sa, b[t] / sb) for t in a.keys() & b.keys()}
    return [t for t, _ in sorted(common.items(), key=lambda x: -x[1])[:n]]


def keyword_timeline(papers: list[dict], lid: str, n: int = 3) -> list[dict]:
    per_year: dict[int, Counter] = defaultdict(Counter)
    for p in papers:
        if lid in p["lab_ids"] and in_analysis_set(p, lid):
            for t in p["topics"]:
                per_year[p["year"]][t["name"]] += t["score"]
    return [{"year": y, "keywords": [t for t, _ in per_year[y].most_common(n)]} for y in sorted(per_year)]


def ctfidf(groups: dict[int, Counter], n: int = 5) -> dict[int, list[str]]:
    """Class-based TF-IDF over topic weights: what is distinctive for each cluster."""
    total = Counter()
    for c in groups.values():
        total.update(c)
    avg = sum(total.values()) / max(len(groups), 1)
    out = {}
    for gid, c in groups.items():
        s = sum(c.values()) or 1
        score = {t: (w / s) * math.log(1 + avg / total[t]) for t, w in c.items()}
        out[gid] = [t for t, _ in sorted(score.items(), key=lambda x: -x[1])[:n]]
    return out


# ------------------------------------------------------------------ graph
def knn_pairs(sim: np.ndarray, k: int) -> dict[tuple[int, int], float]:
    pairs = {}
    for i in range(len(sim)):
        order = [j for j in np.argsort(-sim[i]) if j != i][:k]
        for j in order:
            pairs[(min(i, j), max(i, j))] = float(sim[i, j])
    return pairs


def bridge_pairs(sim: np.ndarray, fields: list[frozenset[str]], threshold: float) -> dict[tuple[int, int], float]:
    """Each lab's most similar lab sharing no field with it, when the similarity reaches the threshold."""
    out = {}
    for i in range(len(sim)):
        others = [j for j in range(len(sim)) if not (fields[i] & fields[j])]
        if not others:
            continue
        j = max(others, key=lambda j: sim[i, j])
        if sim[i, j] >= threshold:
            out[(min(i, j), max(i, j))] = float(sim[i, j])
    return out


def closest_paper_pairs(ids_a: list[str], vec_a: np.ndarray, ids_b: list[str], vec_b: np.ndarray,
                        title_of: dict[str, str], n: int = 3) -> list[tuple[str, str]]:
    """Closest pairs across two labs, each title used once. Papers both labs have are no evidence of similar work
    (they are one paper, sometimes under two ids such as a preprint), so any title on both sides is skipped."""
    titles_a = {norm_title(title_of[p]) for p in ids_a}
    shared = titles_a & {norm_title(title_of[p]) for p in ids_b}
    sims = vec_a @ vec_b.T
    out: list[tuple[str, str]] = []
    seen: set[str] = set(shared)
    for k in np.argsort(-sims, axis=None):
        i, j = np.unravel_index(k, sims.shape)
        pa, pb = ids_a[i], ids_b[j]
        ta, tb = norm_title(title_of[pa]), norm_title(title_of[pb])
        if ta in seen or tb in seen:
            continue
        out.append((pa, pb))
        seen.update((ta, tb))
        if len(out) == n:
            break
    return out


def band_cuts(weights: list[float]) -> tuple[float, float]:
    """Cut-offs splitting a group's lines into three equal parts."""
    lo, hi = np.quantile(weights, [1 / 3, 2 / 3])
    return round(float(lo), 4), round(float(hi), 4)


def similarity_band(weight: float, cuts: tuple[float, float], threshold: float) -> str:
    """Band shown on the site (web/src/lib/format.ts has the same rule)."""
    if weight < threshold:
        return "주제 거리가 있음"
    if weight >= cuts[1]:
        return "매우 가까움"
    return "가까움" if weight >= cuts[0] else "비교적 가까움"


def cluster_target(n: int) -> tuple[int, int]:
    """Cluster count range: 6-12 for the original 106 labs, growing with the number of labs."""
    lo, hi = config.LOUVAIN_TARGET_CLUSTERS
    return max(lo, round(n / 45)), max(hi, round(n / 22))


def louvain(n: int, pairs: dict[tuple[int, int], float]) -> tuple[list[set[int]], float, list[dict]]:
    import networkx as nx

    g = nx.Graph()
    g.add_nodes_from(range(n))
    for (i, j), w in pairs.items():
        g.add_edge(i, j, weight=w)
    lo, hi = cluster_target(n)
    target = (lo + hi) / 2
    sweep, best = [], None
    for r in config.LOUVAIN_RESOLUTIONS:
        comms = nx.community.louvain_communities(g, weight="weight", resolution=r, seed=config.LOUVAIN_SEED)
        q = nx.community.modularity(g, comms, weight="weight")
        sweep.append({"resolution": r, "clusters": len(comms), "modularity": round(q, 4)})
        if lo <= len(comms) <= hi:
            key = (abs(len(comms) - target), -q)
            if best is None or key < best[0]:
                best = (key, r, comms)
    if best is None:
        raise SystemExit(f"no resolution in {config.LOUVAIN_RESOLUTIONS[0]}..{config.LOUVAIN_RESOLUTIONS[-1]} "
                         f"gives {lo}-{hi} clusters; sweep: {sweep}")
    _, r, comms = best
    return sorted(comms, key=lambda c: (-len(c), min(c))), r, sweep


def umap_xy(vectors: np.ndarray) -> np.ndarray:
    import umap

    reducer = umap.UMAP(n_components=2, n_neighbors=min(15, len(vectors) - 1), min_dist=0.3,
                        metric="cosine", random_state=config.UMAP_SEED)
    xy = reducer.fit_transform(vectors)
    xy = xy - xy.mean(0)
    return xy / np.abs(xy).max()  # centred, scaled to [-1, 1]


# ------------------------------------------------------------------ main
def run(client=None) -> None:
    z = np.load(config.OUTPUT_DIR / "lab_vectors.npz")
    lab_ids = z["lab_ids"].tolist()
    vec = z["vectors"]
    papers = read_jsonl(config.OUTPUT_DIR / "papers_raw.jsonl")
    idx = {lid: i for i, lid in enumerate(lab_ids)}
    status = {s["lab_id"]: s for s in read_json(config.OUTPUT_DIR / "lab_status.json")}
    fields = [frozenset(config.DEPT_BY_CODE[d].discipline for d in status[lid]["depts"]) for lid in lab_ids]
    field_of = dict(zip(lab_ids, fields))

    # similarity edges: top-k neighbours above a data-driven threshold
    sim = vec @ vec.T
    pairs = knn_pairs(sim, config.SIMILARITY_K)
    topk = np.sort(np.array([sorted((sim[i, j] for j in range(len(sim)) if j != i), reverse=True)
                             [: config.SIMILARITY_K] for i in range(len(sim))]).ravel())
    threshold = round(float(np.quantile(topk, config.SIMILARITY_THRESHOLD_QUANTILE)), 4)
    prof = topic_profiles(papers, lab_ids)
    edges: list[Edge] = []
    shown = {k: w for k, w in pairs.items() if w >= threshold}
    bridges = {k: w for k, w in bridge_pairs(sim, fields, threshold).items() if k not in shown}
    used = read_json(config.OUTPUT_DIR / "embedding_papers.json")
    by_id = {p["id"]: p for p in papers}
    title_of = {pid: p["title"] for pid, p in by_id.items()}
    vec_of = cached_paper_vectors([by_id[p] for lid in lab_ids for p in used[lid]])
    paper_vecs = {lid: np.stack([vec_of[p] for p in used[lid]]) for lid in lab_ids}
    primary = {lid: config.DEPT_BY_CODE[status[lid]["depts"][0]].discipline for lid in lab_ids}
    band_weights: dict[str, list[float]] = defaultdict(list)

    def evidence(a: str, b: str) -> list[tuple[str, str]]:
        # a paper of both labs may sit outside one lab's 30 embedded papers, so check its full lab list
        rows_a = [i for i, p in enumerate(used[a]) if b not in by_id[p]["lab_ids"]]
        rows_b = [i for i, p in enumerate(used[b]) if a not in by_id[p]["lab_ids"]]
        return closest_paper_pairs([used[a][i] for i in rows_a], paper_vecs[a][rows_a],
                                   [used[b][i] for i in rows_b], paper_vecs[b][rows_b], title_of)

    for (i, j), w in sorted({**shown, **bridges}.items()):
        a, b = sorted((lab_ids[i], lab_ids[j]))
        edges.append(Edge(source=a, target=b, type="similarity", weight=round(w, 4),
                          reasons=shared_keywords(prof[a], prof[b]), cross=not (fields[i] & fields[j]),
                          paper_pairs=evidence(a, b)))
        band_weights[primary[a] if primary[a] == primary[b] else "cross"].append(w)
        band_weights["all"].append(w)

    # co-authorship edges: papers on which two dataset PIs are both authors (both at home institution)
    co: dict[tuple[str, str], list[str]] = defaultdict(list)
    for p in papers:
        labs = sorted(l for l in p["lab_ids"] if l in idx and in_analysis_set(p, l))
        for a, b in combinations(labs, 2):
            co[(a, b)].append(p["id"])
    for (a, b), pids in sorted(co.items()):
        edges.append(Edge(source=a, target=b, type="coauthor", weight=len(pids), paper_ids=sorted(pids),
                          cross=not (field_of[a] & field_of[b])))

    # clusters on the full kNN graph (no threshold, so no lab is isolated)
    comms, resolution, sweep = louvain(len(lab_ids), pairs)
    cluster_of = {lab_ids[i]: cid for cid, c in enumerate(comms) for i in c}
    groups = {cid: sum((prof[lab_ids[i]] for i in c), Counter()) for cid, c in enumerate(comms)}
    kw = ctfidf(groups)
    labels = read_json(LABELS_PATH) if LABELS_PATH.exists() else {}
    clusters = []
    for cid, c in enumerate(comms):
        lab = labels.get(str(cid))
        if lab and lab.get("keywords") != kw[cid]:
            log.warning("cluster %d keywords changed since labelling; label '%s' needs review", cid, lab["label_ko"])
        clusters.append(Cluster(id=cid, label_ko=(lab or {}).get("label_ko", f"클러스터 {cid + 1}"),
                                keywords=kw[cid], size=len(c)))

    xy = umap_xy(vec)
    labs_out = {
        lid: {"cluster_id": cluster_of[lid], "x": round(float(xy[i, 0]), 5), "y": round(float(xy[i, 1]), 5),
              "keywords": [t for t, _ in prof[lid].most_common(5)], "vector_paper_count": len(used[lid]),
              "keyword_timeline": keyword_timeline(papers, lid)}
        for i, lid in enumerate(lab_ids)
    }
    n_sim = sum(e.type == "similarity" for e in edges)
    write_json(config.OUTPUT_DIR / "analysis.json", {
        "params": {"model": config.EMBED_MODEL, "k": config.SIMILARITY_K,
                   "threshold_quantile": config.SIMILARITY_THRESHOLD_QUANTILE, "threshold": threshold,
                   "louvain_seed": config.LOUVAIN_SEED, "louvain_resolution": resolution,
                   "umap_seed": config.UMAP_SEED, "resolution_sweep": sweep,
                   "cluster_target": cluster_target(len(lab_ids)), "bridges_added": len(bridges),
                   "similarity_bands": {k: band_cuts(v) for k, v in sorted(band_weights.items())}},
        "labs": labs_out, "edges": edges, "clusters": clusters,
    })
    log.info("labs %d | similarity edges %d (threshold %.4f; %d bridges, %d cross-field) | coauthor edges %d | "
             "clusters %d (resolution %.2f)", len(lab_ids), n_sim, threshold, len(bridges),
             sum(e.cross for e in edges if e.type == "similarity"), len(edges) - n_sim, len(clusters), resolution)
