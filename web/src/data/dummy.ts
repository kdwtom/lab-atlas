import type { Cluster, Edge, Lab, Meta, Univ } from '../types/data';

/** Deterministic synthetic data for the performance check (`#/?dummy=300`). Never shown as real labs. */
export function makeDummy(n: number, clusters: Cluster[], meta: Meta): { labs: Lab[]; edges: Edge[]; clusters: Cluster[]; meta: Meta } {
  let seed = 42;
  const rand = () => ((seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296);
  const univs: Univ[] = ['kaist', 'snu', 'postech', 'unist', 'gist', 'dgist'];
  const k = Math.max(clusters.length, 1);
  const centers = Array.from({ length: k }, (_, i) => [Math.cos((2 * Math.PI * i) / k) * 0.6, Math.sin((2 * Math.PI * i) / k) * 0.6]);
  const labs: Lab[] = Array.from({ length: n }, (_, i) => {
    const c = i % k;
    return {
      id: `dummy-${i}`, univ: univs[i % univs.length], univ_name_ko: '더미 대학', dept_name_ko: '더미 학과',
      pi_name_ko: `더미 ${i + 1}`, pi_name_en: `Dummy ${i + 1}`, position: null, lab_name: null, homepage_url: null,
      faculty_page_url: '#', openalex_id: `D${i}`, orcid: null, match_confidence: 'medium',
      paper_count_5y: 5 + Math.floor(rand() * 60), senior_paper_count_5y: 5, keywords: clusters[c]?.keywords.slice(0, 3) ?? [],
      cluster_id: clusters[c]?.id ?? null, x: centers[c][0] + (rand() - 0.5) * 0.5, y: centers[c][1] + (rand() - 0.5) * 0.5,
      intro_ko: null, representative_paper_ids: [], keyword_timeline: [], sources: [],
    };
  });
  const edges: Edge[] = [];
  const seen = new Set<string>();
  labs.forEach((l, i) => {
    for (let j = 0; j < 5; j++) {
      const sameCluster = rand() < 0.8;
      const t = sameCluster ? (i + k * (1 + Math.floor(rand() * 8))) % n : Math.floor(rand() * n);
      if (t === i) continue;
      const [a, b] = [l.id, labs[t].id].sort();
      const key = `${a}|${b}`;
      if (seen.has(key)) continue;
      seen.add(key);
      edges.push({ source: a, target: b, type: rand() < 0.75 ? 'similarity' : 'coauthor', weight: 0.9 + rand() * 0.08,
                   reasons: ['더미 키워드'], paper_ids: [] });
    }
  });
  const dummyClusters = clusters.map((c) => ({ ...c, size: labs.filter((l) => l.cluster_id === c.id).length }));
  return { labs, edges, clusters: dummyClusters, meta: { ...meta, counts: { ...meta.counts, labs: n, edges_similarity: edges.length } } };
}
