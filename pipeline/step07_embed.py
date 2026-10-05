"""Step 7 — SPECTER embeddings of each lab's recent papers -> one vector per lab.

Lab vector = mean of paper vectors weighted by 1 + ln(1 + citations), L2-normalised.
Paper vectors are cached in pipeline/cache/embeddings/ keyed by a hash of the input text,
so re-runs only embed new or changed papers. CPU only.
"""
from __future__ import annotations

import hashlib
import logging
import math

import numpy as np

from . import config
from .lib.io import read_json, read_jsonl, write_json
from .lib.selection import embedding_papers

log = logging.getLogger(__name__)
CACHE = config.CACHE_DIR / "embeddings" / (config.EMBED_MODEL.rsplit("/", 1)[-1] + ".npz")


def paper_text(p: dict, sep: str) -> str:
    # SPECTER input format: title [SEP] abstract
    return p["title"] + (sep + p["abstract"] if p.get("abstract") else "")


def load_cache() -> dict[str, np.ndarray]:
    if not CACHE.exists():
        return {}
    z = np.load(CACHE)
    return dict(zip(z["keys"].tolist(), z["vectors"]))


def save_cache(cache: dict[str, np.ndarray]) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted(cache)
    np.savez_compressed(CACHE, keys=np.array(keys), vectors=np.stack([cache[k] for k in keys]))


def qualifying_papers() -> dict[str, list[dict]]:
    """lab_id -> its papers, for labs that meet the selection criterion."""
    status = read_json(config.OUTPUT_DIR / "lab_status.json")
    by_lab: dict[str, list[dict]] = {s["lab_id"]: [] for s in status if s["meets_criterion"]}
    for p in read_jsonl(config.OUTPUT_DIR / "papers_raw.jsonl"):
        for lid in p["lab_ids"]:
            if lid in by_lab:
                by_lab[lid].append(p)
    return by_lab


def embed(papers: list[dict]) -> dict[str, np.ndarray]:
    """paper id -> unit vector, using and extending the on-disk cache."""
    from sentence_transformers import SentenceTransformer  # heavy import, stage 3 only

    texts = {p["id"]: paper_text(p, "[SEP]") for p in papers}
    key = {pid: hashlib.sha1(t.encode("utf-8")).hexdigest() for pid, t in texts.items()}
    cache = load_cache()
    todo = sorted({k: pid for pid, k in key.items() if k not in cache}.items())
    if todo:
        model = SentenceTransformer(config.EMBED_MODEL, device="cpu")
        assert model.tokenizer.sep_token == "[SEP]"
        log.info("embedding %d papers (%d cached)", len(todo), len(key) - len(todo))
        vecs = model.encode([texts[pid] for _, pid in todo], batch_size=16, show_progress_bar=True,
                            convert_to_numpy=True, normalize_embeddings=True)
        for (k, _), v in zip(todo, vecs):
            cache[k] = v.astype(np.float32)
        save_cache(cache)
    return {pid: cache[k] for pid, k in key.items()}


def run(client=None) -> None:
    by_lab = qualifying_papers()
    keep = list(by_lab)
    selected = {lid: embedding_papers(ps, lid) for lid, ps in by_lab.items()}
    vec_of = embed([p for ps in selected.values() for p in ps])

    lab_ids, rows, used = [], [], {}
    for lid in keep:
        ps = selected[lid]
        if not ps:
            log.warning("%s has no analysis papers; skipped", lid)
            continue
        w = np.array([1 + math.log1p(p["cited_by_count"]) for p in ps])
        v = (np.stack([vec_of[p["id"]] for p in ps]) * w[:, None]).sum(0) / w.sum()
        rows.append(v / np.linalg.norm(v))
        lab_ids.append(lid)
        used[lid] = [p["id"] for p in ps]
    np.savez_compressed(config.OUTPUT_DIR / "lab_vectors.npz", lab_ids=np.array(lab_ids), vectors=np.stack(rows))
    write_json(config.OUTPUT_DIR / "embedding_papers.json", used)
    log.info("lab vectors: %d labs, %d papers, model %s", len(lab_ids), len(vec_of), config.EMBED_MODEL)
