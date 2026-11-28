// Run with Node 24 (built-in type stripping); only for the frozen historical engine.
import { readFileSync, writeFileSync } from 'node:fs';
import { buildSearchIndex, searchLabs } from '../tests/search/fixtures/legacy-search.ts';
const read = (path) => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'));
const labs = read('../public/data/labs.json');
const papers = read('../public/data/papers.json');
const clusters = read('../public/data/clusters.json');
const terms = read('../public/data/search_terms.json');
const benchmark = read('../../docs/search/benchmark.json');
const index = buildSearchIndex(labs, papers, terms, (lab) => {
  const cluster = clusters.find((c) => c.id === lab.cluster_id);
  return [cluster?.label_ko, cluster?.subclusters?.find((c) => c.id === lab.subcluster_id)?.label_ko].filter(Boolean);
});
const results = benchmark.cases.map((c) => {
  const f = c.filters;
  const hits = searchLabs(index, c.query).filter(({lab:l}) =>
    (!f.univs.length || f.univs.includes(l.univ)) &&
    (!f.fields.length || l.disciplines.some((x) => f.fields.includes(x))) &&
    (!f.clusters.length || f.clusters.includes(l.cluster_id)));
  return { id:c.id, total:hits.length, hits:hits.map((h) => ({labId:h.lab.id,score:h.score,reason:h.reason})) };
});
writeFileSync(new URL('../../docs/search/baseline-results.json',import.meta.url), JSON.stringify({commit:benchmark.commit,files:benchmark.files,results},null,2)+'\n');
console.log(`Captured the legacy engine for ${results.length} cases; no relevance judgments inferred.`);
