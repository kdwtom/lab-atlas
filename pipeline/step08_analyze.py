"""Step 8 — similarity edges, co-authorship edges, Louvain clusters, UMAP layout, keywords.

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
from .schemas import Cluster, Edge

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


def louvain(n: int, pairs: dict[tuple[int, int], float]) -> tuple[list[set[int]], float, list[dict]]:
    import networkx as nx

    g = nx.Graph()
    g.add_nodes_from(range(n))
    for (i, j), w in pairs.items():
        g.add_edge(i, j, weight=w)
    lo, hi = config.LOUVAIN_TARGET_CLUSTERS
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

    # similarity edges: top-k neighbours above a data-driven threshold
    sim = vec @ vec.T
    pairs = knn_pairs(sim, config.SIMILARITY_K)
    topk = np.sort(np.array([sorted((sim[i, j] for j in range(len(sim)) if j != i), reverse=True)
                             [: config.SIMILARITY_K] for i in range(len(sim))]).ravel())
    threshold = round(float(np.quantile(topk, config.SIMILARITY_THRESHOLD_QUANTILE)), 4)
    prof = topic_profiles(papers, lab_ids)
    edges: list[Edge] = []
    for (i, j), w in sorted(pairs.items()):
        if w >= threshold:
            a, b = sorted((lab_ids[i], lab_ids[j]))
            edges.append(Edge(source=a, target=b, type="similarity", weight=round(w, 4),
                              reasons=shared_keywords(prof[a], prof[b])))

    # co-authorship edges: papers on which two dataset PIs are both authors (both at home institution)
    co: dict[tuple[str, str], list[str]] = defaultdict(list)
    for p in papers:
        labs = sorted(l for l in p["lab_ids"] if l in idx and in_analysis_set(p, l))
        for a, b in combinations(labs, 2):
            co[(a, b)].append(p["id"])
    for (a, b), pids in sorted(co.items()):
        edges.append(Edge(source=a, target=b, type="coauthor", weight=len(pids), paper_ids=sorted(pids)))

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
              "keywords": [t for t, _ in prof[lid].most_common(5)],
              "keyword_timeline": keyword_timeline(papers, lid)}
        for i, lid in enumerate(lab_ids)
    }
    n_sim = sum(e.type == "similarity" for e in edges)
    write_json(config.OUTPUT_DIR / "analysis.json", {
        "params": {"model": config.EMBED_MODEL, "k": config.SIMILARITY_K,
                   "threshold_quantile": config.SIMILARITY_THRESHOLD_QUANTILE, "threshold": threshold,
                   "louvain_seed": config.LOUVAIN_SEED, "louvain_resolution": resolution,
                   "umap_seed": config.UMAP_SEED, "resolution_sweep": sweep},
        "labs": labs_out, "edges": edges, "clusters": clusters,
    })
    log.info("labs %d | similarity edges %d (threshold %.4f) | coauthor edges %d | clusters %d (resolution %.2f)",
             len(lab_ids), n_sim, threshold, len(edges) - n_sim, len(clusters), resolution)
