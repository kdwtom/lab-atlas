import type {Atlas} from './DataContext';
import {searchLabs,EMPTY_FILTERS,type SearchFilters} from '../lib/search/index';
/** Opt-in local-only instrumentation used by the production-build browser checks. */
export function installSearchDiagnostics(atlas:Atlas) {
  if(!['localhost','127.0.0.1','[::1]'].includes(window.location.hostname)||!new URLSearchParams(window.location.hash.split('?')[1]).has('searchDebug'))return;
  const heap=()=> (performance as Performance & {memory?:{usedJSHeapSize:number}}).memory?.usedJSHeapSize;
  const heapAtAtlasReady=heap();
  Object.assign(window,{__labAtlasSearch:{
    stats:()=>{const i=atlas.searchIndex();return {version:i.datasetVersion,dictionaryVersion:i.dictionaryVersion,buildMs:i.buildMs,records:i.records.size,labs:i.labs.size,papers:atlas.papers.length,heapAtAtlasReady,heapAfterIndex:heap()};},
    run:(q:string,raw?:{univs:string[];fields:string[];clusters:number[]})=>{
      const filters=raw?{univs:new Set(raw.univs),fields:new Set(raw.fields),clusters:new Set(raw.clusters)} as SearchFilters:EMPTY_FILTERS;
      const i=atlas.searchIndex();const start=performance.now();const r=searchLabs(i,q,filters);
      return {ms:performance.now()-start,ids:r.results.map(x=>x.labId),scores:r.results.map(x=>x.score),total:r.total};
    },
  }});
}
