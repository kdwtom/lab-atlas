import { useEffect,useId,useRef,useState,type KeyboardEvent } from 'react';
import type { Lab } from '../types/data';
import type { SearchResult } from '../lib/search/index';
import { affiliation,piName } from '../lib/format';
import SearchEvidence from './SearchEvidence';
interface Props {query:string;rows:readonly {lab:Lab;result:SearchResult}[];total:number;onQuery:(q:string)=>void;onPick:(lab:Lab)=>void;onViewAll:()=>void;onEndEditing?:()=>void;resetKey?:string}
export default function SearchBox({query,rows,total,onQuery,onPick,onViewAll,onEndEditing,resetKey}:Props) {
  const id=useId();const [draft,setDraft]=useState(query);const [open,setOpen]=useState(false);const [active,setActive]=useState<string|null>(null);const composing=useRef(false);const compositionEnd=useRef(0);
  useEffect(()=>{setDraft(query);setActive(null);},[query,resetKey]);
  const activeRow=rows.find(r=>r.lab.id===active);const shown=open&&query.trim().length>0;
  useEffect(()=>{if(shown&&activeRow)document.getElementById(`${id}-${activeRow.lab.id}`)?.scrollIntoView({block:'nearest'});},[shown,activeRow?.lab.id,id]);
  const choose=(lab:Lab)=>{onEndEditing?.();onPick(lab);setOpen(false);setActive(null);};
  const key=(e:KeyboardEvent<HTMLInputElement>)=>{
    if(composing.current||e.nativeEvent.isComposing||e.keyCode===229||(e.key==='Enter'&&performance.now()-compositionEnd.current<80))return;
    const index=rows.findIndex(r=>r.lab.id===active);
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();setOpen(true);if(!rows.length){setActive(null);return;}const next=e.key==='ArrowDown'?Math.min(index+1,rows.length-1):index<0?rows.length-1:Math.max(0,index-1);setActive(rows[next].lab.id);}
    else if(e.key==='Enter'){e.preventDefault();onEndEditing?.();if(shown&&activeRow)choose(activeRow.lab);else if(total){setOpen(false);onViewAll();}}
    else if(e.key==='Escape'){e.stopPropagation();setOpen(false);setActive(null);}
  };
  return <div className="search" onBlur={e=>{if(!e.currentTarget.contains(e.relatedTarget as Node)){setOpen(false);onEndEditing?.();}}}>
    <label htmlFor={`${id}-input`} className="sr-only">교수·연구실 이름 또는 연구 주제 검색</label>
    <input id={`${id}-input`} type="search" role="combobox" aria-expanded={shown&&rows.length>0} aria-controls={shown&&rows.length?`${id}-list`:undefined} aria-activedescendant={shown&&activeRow?`${id}-${activeRow.lab.id}`:undefined} aria-autocomplete="list" autoComplete="off" placeholder="교수 이름 · 연구 주제(한/영) 검색" value={draft}
      onChange={e=>{setDraft(e.target.value);setOpen(true);setActive(null);if(!composing.current)onQuery(e.target.value);}}
      onCompositionStart={()=>{composing.current=true;setActive(null);}}
      onCompositionEnd={e=>{composing.current=false;compositionEnd.current=performance.now();onQuery(e.currentTarget.value);setOpen(true);}}
      onFocus={()=>setOpen(true)} onKeyDown={key}/>
    {shown&&<div className="search-popup">{rows.length>0?<ul id={`${id}-list`} role="listbox" className="search-list">{rows.map(({lab,result})=><li key={lab.id} id={`${id}-${lab.id}`} role="option" aria-selected={active===lab.id} className={active===lab.id?'active':''} onPointerDown={e=>{e.preventDefault();choose(lab);}} onMouseEnter={()=>setActive(lab.id)}><span className="opt-name">{piName(lab)}{lab.pi_name_ko&&lab.pi_name_en?` · ${lab.pi_name_en}`:''}</span><span className="opt-sub">{affiliation(lab)}</span><SearchEvidence result={result} compact/></li>)}</ul>:<p className="small search-empty" role="status">일치하는 연구실이 없습니다.</p>}
      {total>0&&<button type="button" className="search-all" onClick={()=>{setOpen(false);onEndEditing?.();onViewAll();}}>전체 {total}개 결과 보기</button>}
    </div>}
  </div>;
}
