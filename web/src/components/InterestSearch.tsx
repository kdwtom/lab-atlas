import {useEffect,useMemo,useRef,useState} from 'react';
import {Link,useLocation,useNavigate,useNavigationType,useSearchParams} from 'react-router-dom';
import {useAtlas} from '../data/DataContext';
import {useLabSearch} from '../data/useLabSearch';
import {parseSearchParams,writeSearchUpdate,type SearchUrlState} from '../data/searchUrl';
import {filterKey} from '../lib/search/index';
import {affiliation,piName,UNIV_LABEL} from '../lib/format';
import {FIELD_LABEL} from '../lib/palette';
import SearchBox from './SearchBox';
import SearchStatus from './SearchStatus';
import SearchEvidence from './SearchEvidence';
import StarButton from './StarButton';
export default function InterestSearch() {
  const atlas=useAtlas();const [params,setParams]=useSearchParams();const navigate=useNavigate();const location=useLocation();const navType=useNavigationType();const editing=useRef(false);
  const parsed=useMemo(()=>parseSearchParams(params,new Set(atlas.clusters.map(c=>c.id)),atlas.version),[params,atlas]);const s=parsed.state;
  useEffect(()=>{if(navType==='POP')editing.current=false;},[location.key,navType]);
  const write=(next:SearchUrlState,replace=false,acceptFilters=false)=>setParams(writeSearchUpdate(params,parsed,next,acceptFilters),{replace});
  const response=useLabSearch(parsed.filterState==='valid'?s.query:',',s.filters,{keyboardCorrection:s.keyboardCorrection,includeUnfilteredCount:true});
  const key=s.query+filterKey(s.filters);const [paging,setPaging]=useState({key:'',limit:12});const limit=paging.key===key?paging.limit:12;
  const clear=()=>{editing.current=false;write({...s,filters:{univs:new Set(),fields:new Set(),clusters:new Set()}},false,true);};
  const summary=useRef<HTMLParagraphElement>(null);
  return <section aria-labelledby="find-title" data-search-surface="shortlist">
    <h2 id="find-title">관심사로 찾기</h2>
    <SearchBox query={s.query} rows={response.results.slice(0,8).map(result=>({result,lab:atlas.labById.get(result.labId)!}))} total={response.total} resetKey={filterKey(s.filters)} onQuery={query=>{write({...s,query,keyboardCorrection:true,sort:query.trim()?'relevance':'papers-desc'},editing.current);editing.current=true;}} onEndEditing={()=>{editing.current=false;}} onPick={lab=>navigate(`/lab/${encodeURIComponent(lab.id)}`)} onViewAll={()=>summary.current?.focus()}/>
    <p className="muted small">등록된 한·영 연구 용어를 함께 찾습니다. 사전에 없는 표현은 입력한 글자로 찾습니다. 입력한 주제가 모두 포함된 연구실을 찾으며, 여러 항목에 나뉜 근거는 뒤에 표시합니다.</p>
    <div className="chips">{[...s.filters.univs].map(u=><button key={u} onClick={()=>write({...s,filters:{...s.filters,univs:new Set([...s.filters.univs].filter(x=>x!==u))}})}>{UNIV_LABEL[u]} ×</button>)}{[...s.filters.fields].map(f=><button key={f} onClick={()=>write({...s,filters:{...s.filters,fields:new Set([...s.filters.fields].filter(x=>x!==f))}})}>{FIELD_LABEL[f]} ×</button>)}{[...s.filters.clusters].map(c=><button key={c} onClick={()=>write({...s,filters:{...s.filters,clusters:new Set([...s.filters.clusters].filter(x=>x!==c))}})}>{atlas.clusterById.get(c)?.label_ko??c} ×</button>)}</div>
    {parsed.notices.map(n=><p role="status" key={n}>{n} <button onClick={clear}>필터 초기화</button>{parsed.filterState==='stale'&&<button onClick={()=>write(s,false,true)}>현재 필터 적용</button>}</p>)}
    {parsed.filterState==='valid'&&<SearchStatus response={response} onClearFilters={clear} onOriginal={()=>write({...s,keyboardCorrection:false})}/>}
    {s.query.trim()&&response.total>0&&<>
      <p ref={summary} tabIndex={-1} className="muted small" aria-live="polite">{response.total}곳 중 {Math.min(limit,response.total)}곳 표시 · 관련도순</p>
      <ul className="lab-rows interest-results">{response.results.slice(0,limit).map(result=>{const lab=atlas.labById.get(result.labId)!;return <li key={lab.id} data-lab-id={lab.id}><StarButton id={lab.id} name={piName(lab)} compact/><div><Link to={`/lab/${encodeURIComponent(lab.id)}`} className="row-link">{piName(lab)}</Link><span className="muted small"> {affiliation(lab)}</span><SearchEvidence result={result}/></div></li>;})}</ul>
      {limit<response.total&&<button type="button" className="load-more" onClick={()=>setPaging({key,limit:limit+12})}>{Math.min(12,response.total-limit)}곳 더 보기</button>}
    </>}
  </section>;
}
