import type { Discipline, Univ } from '../types/data';
import type { SearchFilters } from '../lib/search/types';
export type SearchSort = 'relevance' | `${'name'|'univ'|'field'|'cluster'|'papers'|'senior'}-${'asc'|'desc'}`;
export interface SearchUrlState { query: string; filters: SearchFilters; datasetVersion: string; keyboardCorrection: boolean; view:'graph'|'list'; edgeMode:'similarity'|'coauthor'|'cross'; sort:SearchSort }
export interface ParsedSearchUrl {state:SearchUrlState;filterState:'valid'|'invalid'|'stale';notices:readonly string[]}
const UNIVS:Univ[]=['kaist','snu','postech','unist','gist','dgist','yonsei','korea','skku','hanyang','sogang'];
const FIELDS:Discipline[]=['life','chem','phys','math','cs'];
export function parseSearchParams(params:URLSearchParams,clusters:ReadonlySet<number>,version:string):ParsedSearchUrl {
  let filterState:ParsedSearchUrl['filterState']='valid'; const notices:string[]=[];
  function parse<T>(key:string,convert:(s:string)=>T,allowed:ReadonlySet<T>):Set<T> {
    const raw=params.get(key);if(raw===null)return new Set();
    const values=raw.split(',').filter(Boolean).map(convert);const valid=values.filter((v)=>allowed.has(v));
    if(!valid.length){filterState='invalid';notices.push('선택한 필터를 확인할 수 없습니다. 필터를 초기화해 주세요.');}
    else if(valid.length!==values.length)notices.push('알 수 없는 필터 값은 제외했습니다.');
    return new Set(valid);
  }
  const filters={univs:parse('univ',s=>s as Univ,new Set(UNIVS)),fields:parse('field',s=>s as Discipline,new Set(FIELDS)),clusters:parse('cluster',s=>/^\d+$/.test(s)?Number(s):NaN,clusters)};
  const saved=params.get('data');
  if(filters.clusters.size&&saved&&saved!==version&&filterState==='valid'){filterState='stale';notices.push('데이터가 갱신되어 클러스터 구성이 달라졌을 수 있습니다. 현재 필터를 확인해 주세요.');}
  if(filters.clusters.size&&!saved)notices.push('현재 데이터의 클러스터 필터를 사용합니다.');
  const query=params.get('q')??'';const sort=params.get('sort');
  const validSort=sort==='relevance'||/^(name|univ|field|cluster|papers|senior)-(asc|desc)$/.test(sort??'');
  return {filterState,notices,state:{query,filters,datasetVersion:version,keyboardCorrection:params.get('correction')!=='off',view:params.get('view')==='list'?'list':'graph',edgeMode:params.get('edge')==='coauthor'?'coauthor':params.get('edge')==='cross'?'cross':'similarity',sort:validSort?sort as SearchSort:query.trim()?'relevance':'papers-desc'}};
}
export function writeSearchParams(previous:URLSearchParams,state:SearchUrlState):URLSearchParams {
  const p=new URLSearchParams(previous);const put=(k:string,v:string|undefined)=>{if(v)p.set(k,v);else p.delete(k);};
  put('q',state.query||undefined);put('univ',[...state.filters.univs].sort().join(','));put('field',[...state.filters.fields].sort().join(','));put('cluster',[...state.filters.clusters].sort((a,b)=>a-b).join(','));
  put('data',state.filters.univs.size||state.filters.fields.size||state.filters.clusters.size?state.datasetVersion:undefined);
  put('view',state.view==='list'?'list':undefined);put('edge',state.edgeMode==='similarity'?undefined:state.edgeMode);put('sort',state.sort===(state.query.trim()?'relevance':'papers-desc')?undefined:state.sort);put('correction',state.keyboardCorrection?undefined:'off');return p;
}
/** Editing text or presentation must not implicitly accept invalid/stale filters. */
export function writeSearchUpdate(previous:URLSearchParams,parsed:ParsedSearchUrl,next:SearchUrlState,acceptFilters=false):URLSearchParams {
  const p=writeSearchParams(previous,next);
  if(parsed.filterState==='valid'||acceptFilters)return p;
  const same=(a:ReadonlySet<unknown>,b:ReadonlySet<unknown>)=>a.size===b.size&&[...a].every(v=>b.has(v));
  const retain=(key:string)=>{const value=previous.get(key);if(value===null)p.delete(key);else p.set(key,value);};
  for(const [key,field] of [['univ','univs'],['field','fields'],['cluster','clusters']] as const) {
    if(same(parsed.state.filters[field],next.filters[field]))retain(key);
  }
  if(same(parsed.state.filters.clusters,next.filters.clusters))retain('data');
  return p;
}
