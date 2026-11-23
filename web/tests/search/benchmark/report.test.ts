import {it,expect} from 'vitest';
import {readFileSync,writeFileSync} from 'node:fs';
import {buildSearchIndex,searchLabs,dictionary,EMPTY_FILTERS} from '../../../src/lib/search/index';
import type {SearchFilters,SearchResult} from '../../../src/lib/search/index';
import {collectLabMatch} from '../../../src/lib/search/query';
import {rankLabMatch,compareResults} from '../../../src/lib/search/rank';
const read=(file:string)=>JSON.parse(readFileSync(new URL(file,import.meta.url),'utf8'));
it('evaluates the real corpus and reports honest review coverage',()=>{
  const labs=read('../../../public/data/labs.json'),papers=read('../../../public/data/papers.json'),clusters=read('../../../public/data/clusters.json'),legacyTerms=read('../../../public/data/search_terms.json');
  const inventory=read('../../../../docs/search/benchmark.json');
  const index=buildSearchIndex({version:inventory.commit,labs,papers,clusters,legacyTerms});
  const resultKey=(r:readonly SearchResult[])=>r.map(({labId,score})=>({labId,score}));
  let pairs=0;
  for(const c of dictionary.concepts){
    const en=c.aliases.find(a=>a.language==='en')??c.aliases[0];const ko=c.aliases.find(a=>a.language==='ko')!;
    for(const filters of [EMPTY_FILTERS,{...EMPTY_FILTERS,univs:new Set<'kaist'>(['kaist'])}]){
      expect(resultKey(searchLabs(index,en.text,filters,{keyboardCorrection:false}).results),c.id).toEqual(resultKey(searchLabs(index,ko.text,filters,{keyboardCorrection:false}).results));pairs++;
    }
    for(const e of c.sourceExamples){
      const lab=labs.find((l:{id:string})=>l.id===e.labId);expect(lab,c.id).toBeDefined();
      if(e.paperId){const p=papers.find((p:{id:string})=>p.id===e.paperId);expect(p?.title).toBe(e.text);expect(p?.lab_ids).toContain(e.labId);}
      else expect(lab.keywords).toContain(e.text);
    }
  }
  const results=inventory.cases.map((c:{id:string;query:string;filters:{univs:string[];fields:string[];clusters:number[]};judgments:{labId:string;grade:number}[]})=>{
    const filters={univs:new Set(c.filters.univs),fields:new Set(c.filters.fields),clusters:new Set(c.filters.clusters)} as SearchFilters;
    const t=performance.now();const r=searchLabs(index,c.query,filters,{includeUnfilteredCount:true});const durationMs=performance.now()-t;
    // Independently scan all records on every eligible lab to prove the postings
    // optimization preserves full results, scores, paper support and explanations.
    const reference=r.query.state==='ready'?r.eligibleLabIds.flatMap(id=>{
      const match=collectLabMatch(index,id,r.query);
      return match?[rankLabMatch(match,r.query,index)]:[];
    }).sort(compareResults):[];
    expect(r.results,c.id).toEqual(reference);
    if(c.judgments.length)expect(r.results[0]?.labId,c.id).toBe(c.judgments[0].labId);
    return {id:c.id,total:r.total,durationMs,correction:r.correction,results:resultKey(r.results)};
  });
  const report={date:new Date().toISOString(),dataset:inventory.files,dictionaryVersion:dictionary.version,concepts:dictionary.concepts.length,pairedChecks:pairs,fullScanChecks:results.length,indexMs:index.buildMs,records:index.records.size,diagnostics:index.diagnostics,identityChecks:5,topicRelevance:'Pending human judgments; no nDCG or recall claim',results};
  writeFileSync(new URL('../../../../docs/search/implementation-results.json',import.meta.url),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify({concepts:report.concepts,pairedChecks:pairs,indexMs:index.buildMs,records:index.records.size,queries:results.length}));
});
