// In-browser recommendations from the quantised lab vectors (pipeline step 10). Loaded on demand so the
// map's first screen does not download them.

export interface LabVectors {
  ids: string[];
  index: Map<string, number>;
  dim: number;
  values: Float32Array; // unit vectors, row by row
}

let cached: Promise<LabVectors> | null = null;

export function loadLabVectors(): Promise<LabVectors> {
  cached ??= (async () => {
    const base = `${import.meta.env.BASE_URL}data/`;
    const [metaRes, binRes] = await Promise.all([fetch(`${base}lab_vectors.json`), fetch(`${base}lab_vectors.bin`)]);
    if (!metaRes.ok || !binRes.ok) throw new Error('lab vectors unavailable');
    const { ids, dim } = (await metaRes.json()) as { ids: string[]; dim: number };
    const raw = new Int8Array(await binRes.arrayBuffer());
    const values = new Float32Array(raw.length);
    for (let i = 0; i < ids.length; i++) {
      let norm = 0;
      for (let d = 0; d < dim; d++) norm += raw[i * dim + d] ** 2;
      norm = Math.sqrt(norm) || 1;
      for (let d = 0; d < dim; d++) values[i * dim + d] = raw[i * dim + d] / norm;
    }
    return { ids, dim, values, index: new Map(ids.map((id, i) => [id, i])) };
  })().catch((e) => {
    cached = null; // allow a retry on the next visit
    throw e;
  });
  return cached;
}

export interface Recommendation {
  id: string;
  score: number;            // cosine similarity to the mean of the seeds
  nearestSeed: string;      // the collected lab it is closest to
  nearestSimilarity: number;
}

function dot(v: LabVectors, a: number, b: Float32Array | number): number {
  let s = 0;
  if (typeof b === 'number') for (let d = 0; d < v.dim; d++) s += v.values[a * v.dim + d] * v.values[b * v.dim + d];
  else for (let d = 0; d < v.dim; d++) s += v.values[a * v.dim + d] * b[d];
  return s;
}

/** Labs ranked by similarity to the mean of the seed labs; seeds themselves are left out. */
export function recommend(v: LabVectors, seeds: string[]): Recommendation[] {
  const rows = seeds.map((id) => v.index.get(id)).filter((r): r is number => r !== undefined);
  if (rows.length === 0) return [];
  const mean = new Float32Array(v.dim);
  for (const r of rows) for (let d = 0; d < v.dim; d++) mean[d] += v.values[r * v.dim + d];
  const norm = Math.hypot(...mean) || 1;
  for (let d = 0; d < v.dim; d++) mean[d] /= norm;
  const seedSet = new Set(rows);
  const out: Recommendation[] = [];
  v.ids.forEach((id, i) => {
    if (seedSet.has(i)) return;
    let nearest = rows[0];
    let best = -Infinity;
    for (const r of rows) {
      const s = dot(v, i, r);
      if (s > best) {
        best = s;
        nearest = r;
      }
    }
    out.push({ id, score: dot(v, i, mean), nearestSeed: v.ids[nearest], nearestSimilarity: best });
  });
  return out.sort((a, b) => b.score - a.score);
}

/** Lab id -> OpenAlex topic weights, normalised per lab (same basis as the map's "연결 이유"). */
export function topicProfiles(papers: { lab_ids: string[]; topics: { name: string; score: number }[] }[]) {
  const prof = new Map<string, Map<string, number>>();
  for (const p of papers) {
    for (const lab of p.lab_ids) {
      let m = prof.get(lab);
      if (!m) prof.set(lab, (m = new Map()));
      for (const t of p.topics) m.set(t.name, (m.get(t.name) ?? 0) + t.score);
    }
  }
  for (const m of prof.values()) {
    let sum = 0;
    for (const w of m.values()) sum += w;
    for (const [k, w] of m) m.set(k, w / (sum || 1));
  }
  return prof;
}

/** The topics two labs share most, by the smaller of their shares. */
export function sharedTopics(a: Map<string, number> | undefined, b: Map<string, number> | undefined, n = 3): string[] {
  if (!a || !b) return [];
  const common: [string, number][] = [];
  for (const [t, w] of a) {
    const o = b.get(t);
    if (o !== undefined) common.push([t, Math.min(w, o)]);
  }
  return common.sort((x, y) => y[1] - x[1]).slice(0, n).map(([t]) => t);
}
