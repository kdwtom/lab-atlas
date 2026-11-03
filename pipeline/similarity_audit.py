"""How far can the lab similarity be trusted? Writes output/similarity_audit.{md,json}.

    python -m pipeline.run --steps audit

Needs the embedding cache (step 7) but no model and no network. These checks measure stability and agreement with
other signals. None of them is a human judgement of whether two labs really are similar.
"""
from __future__ import annotations

import logging
import math
from collections import Counter, defaultdict

import numpy as np

from . import config
from .lib.io import read_json, read_jsonl, write_json
from .step07_embed import cached_paper_vectors
from .step08_analyze import similarity_band

log = logging.getLogger(__name__)
SEED = 42
SPLIT_REPEATS = 5
BOOTSTRAP_REPEATS = 20
SIZE_BINS = [("5편 이하", 0, 5), ("6–10편", 6, 10), ("11–20편", 11, 20), ("21편 이상", 21, 10**6)]


def lab_vector(vectors: np.ndarray, citations: np.ndarray) -> np.ndarray:
    """Same formula as step 7."""
    w = 1 + np.log1p(citations)
    v = (vectors * w[:, None]).sum(0) / w.sum()
    return v / np.linalg.norm(v)


def top_neighbours(sim: np.ndarray, i: int, k: int = 5) -> list[int]:
    return [int(j) for j in np.argsort(-sim[i]) if j != i][:k]


def overlap_share(a: list[int], b: list[int]) -> float:
    return len(set(a) & set(b)) / max(len(a), 1)


def self_retrieval_rank(half_a: np.ndarray, half_b: np.ndarray, others: np.ndarray, own: int) -> int:
    """Rank of a lab's other half among all labs, for a vector made from one half of its papers (1 = found first)."""
    scores = others @ half_a
    scores[own] = half_a @ half_b
    return int((scores > scores[own]).sum()) + 1


def size_bin(n: int) -> str:
    return next(name for name, lo, hi in SIZE_BINS if lo <= n <= hi)


def run(client=None) -> None:
    z = np.load(config.OUTPUT_DIR / "lab_vectors.npz")
    lab_ids = z["lab_ids"].tolist()
    V = z["vectors"]
    n = len(lab_ids)
    idx = {l: i for i, l in enumerate(lab_ids)}
    used = read_json(config.OUTPUT_DIR / "embedding_papers.json")
    papers = {p["id"]: p for p in read_jsonl(config.OUTPUT_DIR / "papers_raw.jsonl")}
    vec_of = cached_paper_vectors([papers[p] for l in lab_ids for p in used[l]])
    pv = {l: np.stack([vec_of[p] for p in used[l]]) for l in lab_ids}
    cites = {l: np.array([papers[p]["cited_by_count"] for p in used[l]], dtype=float) for l in lab_ids}
    sizes = np.array([len(used[l]) for l in lab_ids])

    labs = {l["id"]: l for l in read_json(config.WEB_DATA_DIR / "labs.json")}
    field = [labs[l]["disciplines"][0] for l in lab_ids]
    edges = read_json(config.WEB_DATA_DIR / "edges.json")
    meta = read_json(config.WEB_DATA_DIR / "meta.json")
    sim_edges = [e for e in edges if e["type"] == "similarity"]
    co_edges = [e for e in edges if e["type"] == "coauthor"]

    S = V @ V.T
    all_pairs = np.sort(S[np.triu_indices(n, 1)])
    percentile = lambda x: float(np.searchsorted(all_pairs, x) / len(all_pairs))  # noqa: E731
    base_top = [top_neighbours(S, i) for i in range(n)]
    out: dict = {"labs": n, "similarity_edges": len(sim_edges), "model": config.EMBED_MODEL}

    # what the numbers mean
    weights = np.array([e["weight"] for e in sim_edges])
    threshold = meta["similarity_threshold"]
    out["scale"] = {
        "all_pairs_median": round(float(np.median(all_pairs)), 4),
        "threshold": threshold, "threshold_percentile": round(percentile(threshold), 4),
        "edge_median": round(float(np.median(weights)), 4),
    }
    out["input"] = {
        "papers_per_lab_median": float(np.median(sizes)),
        "papers_per_lab_p10": float(np.percentile(sizes, 10)),
        "share_with_abstract": round(float(np.mean([bool(papers[p].get("abstract")) for l in lab_ids for p in used[l]])), 3),
    }

    # 1. split-half: can half of a lab's papers find the other half among all labs?
    rng = np.random.RandomState(SEED)
    ranks: dict[str, list[int]] = defaultdict(list)
    by_field: dict[str, list[int]] = defaultdict(list)
    for _ in range(SPLIT_REPEATS):
        for i, l in enumerate(lab_ids):
            if sizes[i] < 4:
                continue
            order = rng.permutation(sizes[i])
            h = sizes[i] // 2
            a, b = order[:h], order[h:]
            r = self_retrieval_rank(lab_vector(pv[l][a], cites[l][a]), lab_vector(pv[l][b], cites[l][b]), V.copy(), i)
            ranks["전체"].append(r)
            ranks[size_bin(int(sizes[i]))].append(r)
            by_field[field[i]].append(r)
    share = lambda rs, k: round(float((np.array(rs) <= k).mean()), 3)  # noqa: E731
    out["split_half"] = {
        "chance_top1": round(1 / n, 4),
        "by_size": {k: {"n": len(v), "top1": share(v, 1), "top5": share(v, 5)} for k, v in ranks.items()},
        "by_field": {k: {"n": len(v), "top1": share(v, 1), "top5": share(v, 5)} for k, v in by_field.items()},
    }

    # 2. bootstrap: resample each lab's papers; how many of its top 5 stay, and how often does each shown line survive?
    overlap = np.zeros((BOOTSTRAP_REPEATS, n))
    kept: Counter = Counter()
    for b in range(BOOTSTRAP_REPEATS):
        rs = np.random.RandomState(SEED + 1 + b)
        Vb = np.stack([lab_vector(pv[l][pick], cites[l][pick])
                       for l in lab_ids for pick in [rs.randint(0, len(used[l]), len(used[l]))]])
        Sb = Vb @ Vb.T
        tops = [set(top_neighbours(Sb, i)) for i in range(n)]
        for i in range(n):
            overlap[b, i] = len(tops[i] & set(base_top[i])) / 5
        for e in sim_edges:
            i, j = idx[e["source"]], idx[e["target"]]
            kept[(e["source"], e["target"])] += j in tops[i] or i in tops[j]
    mean_overlap = overlap.mean(0)
    band_rows: dict[str, list[float]] = defaultdict(list)
    for e in sim_edges:
        i, j = idx[e["source"]], idx[e["target"]]
        group = field[i] if field[i] == field[j] else "cross"
        band = similarity_band(e["weight"], meta["similarity_bands"].get(group) or meta["similarity_bands"]["all"], threshold)
        band_rows[band].append(kept[(e["source"], e["target"])] / BOOTSTRAP_REPEATS)
    out["bootstrap"] = {
        "repeats": BOOTSTRAP_REPEATS, "top5_kept_mean": round(float(mean_overlap.mean()), 3),
        "top5_kept_p10": round(float(np.percentile(mean_overlap, 10)), 3),
        "by_size": {name: {"labs": int(((sizes >= lo) & (sizes <= hi)).sum()),
                           "kept": round(float(mean_overlap[(sizes >= lo) & (sizes <= hi)].mean()), 3)}
                    for name, lo, hi in SIZE_BINS},
        "line_survival_by_band": {k: {"lines": len(v), "survival": round(float(np.mean(v)), 3)}
                                  for k, v in sorted(band_rows.items(), key=lambda kv: -np.mean(kv[1]))},
    }

    # 3. agreement with other signals. Shared papers are removed first: they sit in both vectors and would inflate this.
    pct, fully_shared = [], 0
    for e in co_edges:
        a, b = e["source"], e["target"]
        shared = set(e["paper_ids"])
        keep_a = [i for i, p in enumerate(used[a]) if p not in shared]
        keep_b = [i for i, p in enumerate(used[b]) if p not in shared]
        if not keep_a or not keep_b:
            fully_shared += 1
            continue
        s = float(lab_vector(pv[a][keep_a], cites[a][keep_a]) @ lab_vector(pv[b][keep_b], cites[b][keep_b]))
        pct.append(percentile(s))
    same_univ_field = [percentile(S[i, j]) for i in range(n) for j in range(i + 1, n)
                       if field[i] == field[j] and labs[lab_ids[i]]["univ"] == labs[lab_ids[j]]["univ"]]
    out["coauthor"] = {
        "pairs": len(pct), "skipped_all_papers_shared": fully_shared,
        "median_percentile_without_shared_papers": round(float(np.median(pct)), 3),
        "baseline_same_univ_same_field": round(float(np.median(same_univ_field)), 3),
    }
    top_topics = {}
    for l in lab_ids:
        c: Counter = Counter()
        for p in used[l]:
            for t in papers[p]["topics"]:
                c[t["name"]] += t["score"]
        top_topics[l] = {t for t, _ in c.most_common(15)}
    jaccard = lambda a, b: len(a & b) / max(len(a | b), 1)  # noqa: E731
    near = [jaccard(top_topics[lab_ids[i]], top_topics[lab_ids[j]]) for i in range(n) for j in base_top[i]]
    rng2 = np.random.RandomState(SEED)
    rand = [jaccard(top_topics[lab_ids[i]], top_topics[lab_ids[j]])
            for i in range(n) for j in rng2.choice([x for x in range(n) if x != i], 5, replace=False)]
    out["topics"] = {"jaccard_neighbours": round(float(np.mean(near)), 3), "jaccard_random": round(float(np.mean(rand)), 3),
                     "neighbours_sharing_no_top15_topic": round(float(np.mean(np.array(near) == 0)), 3)}
    out["same_field_share_top5"] = {
        f: round(float(np.mean([field[j] == f for i in range(n) if field[i] == f for j in base_top[i]])), 3)
        for f in sorted(set(field))
    }

    # 4. sensitivity to a design choice, and hubs
    Vu = np.stack([lab_vector(pv[l], np.zeros(len(used[l]))) for l in lab_ids])
    Su = Vu @ Vu.T
    out["citation_weight_top5_kept"] = round(float(np.mean([overlap_share(base_top[i], top_neighbours(Su, i)) for i in range(n)])), 3)
    indeg = Counter(j for top in base_top for j in top)
    vals = np.array([indeg.get(i, 0) for i in range(n)])
    out["hubness"] = {"max": int(vals.max()), "never_a_neighbour": int((vals == 0).sum()),
                      "corr_log_papers": round(float(np.corrcoef(np.log(sizes), vals)[0, 1]), 3)}
    out["lines_without_shared_topic"] = sum(1 for e in sim_edges if not e["reasons"])

    write_json(config.OUTPUT_DIR / "similarity_audit.json", out)
    (config.OUTPUT_DIR / "similarity_audit.md").write_text(report(out), encoding="utf-8", newline="\n")
    log.info("similarity audit: split-half top5 %.3f, bootstrap top5 kept %.3f",
             out["split_half"]["by_size"]["전체"]["top5"], out["bootstrap"]["top5_kept_mean"])


def report(o: dict) -> str:
    sh, bs, co, tp, sc = o["split_half"], o["bootstrap"], o["coauthor"], o["topics"], o["scale"]
    L = ["# 유사도 신뢰성 측정", "",
         f"`python -m pipeline.run --steps audit`로 다시 만듭니다. 연구실 {o['labs']}곳, 유사도 선 {o['similarity_edges']}개, 모델 `{o['model']}`.", "",
         "> **사람이 평가한 정답과 비교한 결과가 아닙니다.** 아래는 안정성과, 다른 신호와의 일치 정도만 보여 줍니다.", "",
         "## 숫자의 의미", "",
         f"- 모든 연구실 쌍의 유사도 중앙값은 {sc['all_pairs_median']}입니다. 선을 긋는 기준 {sc['threshold']}는 전체 쌍의 상위 {100 * (1 - sc['threshold_percentile']):.1f}%입니다. 0.92가 \"92% 비슷하다\"는 뜻은 아닙니다.",
         f"- 입력: 연구실당 논문 중앙값 {o['input']['papers_per_lab_median']:.0f}편, 하위 10%는 {o['input']['papers_per_lab_p10']:.0f}편 이하. 초록이 있는 논문 {100 * o['input']['share_with_abstract']:.0f}%, 나머지는 제목만 씁니다.", "",
         "## 1. 논문을 반으로 나눠도 자기 연구실을 찾는가", "",
         f"논문의 절반으로 만든 벡터가 나머지 절반을 전체 연구실 중 몇 위로 찾는지 봅니다. 우연이면 1위 확률은 {100 * sh['chance_top1']:.1f}%입니다.", "",
         "| 구분 | 시도 | 1위 | 5위 안 |", "|---|---:|---:|---:|"]
    for k in ["전체"] + [b[0] for b in SIZE_BINS]:
        v = sh["by_size"][k]
        L.append(f"| {k} | {v['n']} | {100 * v['top1']:.0f}% | {100 * v['top5']:.0f}% |")
    for k, v in sorted(sh["by_field"].items()):
        L.append(f"| {k} | {v['n']} | {100 * v['top1']:.0f}% | {100 * v['top5']:.0f}% |")
    L += ["", "## 2. 논문 표본이 바뀌어도 이웃이 유지되는가", "",
          f"연구실마다 논문을 복원 추출해 {bs['repeats']}번 다시 계산했습니다. 상위 5개 이웃 중 평균 {100 * bs['top5_kept_mean']:.0f}%가 유지되고, 하위 10% 연구실은 {100 * bs['top5_kept_p10']:.0f}% 이하입니다.", "",
          "| 논문 수 | 연구실 | 유지율 |", "|---|---:|---:|"]
    L += [f"| {k} | {v['labs']} | {100 * v['kept']:.0f}% |" for k, v in bs["by_size"].items()]
    L += ["", "사이트의 구간별로, 표시된 선이 다시 계산해도 어느 한쪽의 상위 5개에 남는 비율입니다.", "",
          "| 구간 | 선 | 유지율 |", "|---|---:|---:|"]
    L += [f"| {k} | {v['lines']} | {100 * v['survival']:.0f}% |" for k, v in bs["line_survival_by_band"].items()]
    L += ["", "## 3. 다른 신호와 일치하는가", "",
          f"- **공동연구**: 공동 논문을 양쪽 벡터에서 뺀 뒤 계산해도 공동연구 쌍 {co['pairs']}개의 유사도는 전체 쌍의 {100 * co['median_percentile_without_shared_papers']:.0f}번째 백분위(중앙값)입니다. 같은 대학·같은 분야 쌍은 {100 * co['baseline_same_univ_same_field']:.0f}번째입니다. 공동연구는 원래 가까운 사람끼리 하므로 정확도 자체를 뜻하지는 않습니다.",
          f"- **OpenAlex 주제**: 상위 15개 주제의 자카드 지수가 이웃은 {tp['jaccard_neighbours']}, 무작위 쌍은 {tp['jaccard_random']}입니다. 이웃의 {100 * tp['neighbours_sharing_no_top15_topic']:.0f}%는 공통 주제가 없습니다.",
          "- **같은 분야 비율(상위 5개)**: " + ", ".join(f"{k} {100 * v:.0f}%" for k, v in o["same_field_share_top5"].items()), "",
          "## 4. 설계에 따른 변화와 쏠림", "",
          f"- 인용 가중치를 빼면 상위 5개 이웃의 {100 * o['citation_weight_top5_kept']:.0f}%가 유지됩니다.",
          f"- 가장 많이 이웃으로 뽑힌 연구실은 {o['hubness']['max']}곳의 이웃이고, {o['hubness']['never_a_neighbour']}곳은 누구의 상위 5개에도 없습니다. 논문 수(로그)와의 상관은 {o['hubness']['corr_log_papers']}입니다.",
          f"- 공통 OpenAlex 주제가 없는 유사도 선은 {o['lines_without_shared_topic']}개입니다.", "",
          "## 사이트에 반영한 내용", "",
          "- 소수점 값 대신 구간으로 표시합니다. 분야마다 값의 범위가 달라 구간 경계도 분야별로 정합니다.",
          "- 논문이 10편 이하인 연구실의 이웃에는 달라질 수 있다는 안내를 붙입니다.",
          "- 선을 클릭하면 벡터가 가장 가까운 논문 쌍을 보여 줍니다. 사용자가 제목으로 직접 판단할 수 있게 하기 위해서입니다.", ""]
    return "\n".join(L)
