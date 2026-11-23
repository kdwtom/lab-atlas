import { createContext,useContext,useEffect,useMemo,useRef,type ReactNode } from 'react';
import { useLocation,useNavigate,useNavigationType } from 'react-router-dom';
import type { Discipline,Univ } from '../types/data';
import { useAtlasState } from './DataContext';
import { parseSearchParams,writeSearchUpdate,type SearchSort,type SearchUrlState } from './searchUrl';
export { passesSearchFilters as passesFilters } from '../lib/search/index';
export type View='graph'|'list';
export type EdgeMode='similarity'|'coauthor'|'cross';
export interface ExploreState {view:View;edgeMode:EdgeMode;query:string;univs:ReadonlySet<Univ>;fields:ReadonlySet<Discipline>;clusters:ReadonlySet<number>;sort:SearchSort;keyboardCorrection:boolean}
interface Ctx extends ExploreState {set:(patch:Partial<ExploreState>)=>void;setQuery:(q:string)=>void;endEditing:()=>void;toggleUniv:(u:Univ)=>void;toggleField:(f:Discipline)=>void;toggleCluster:(c:number)=>void;reset:()=>void;clearFilters:()=>void;acceptFilters:()=>void;notices:readonly string[];blocked:boolean;returnUrl:string}
const C=createContext<Ctx|null>(null);
const toggle=<T,>(s:ReadonlySet<T>,v:T)=>{const n=new Set(s);if(!n.delete(v))n.add(v);return n;};
export function ExploreProvider({children}:{children:ReactNode}) {
  const location=useLocation();const navigate=useNavigate();const navType=useNavigationType();const atlas=useAtlasState();
  const saved=useRef('');const editing=useRef(false);const onExplorer=location.pathname==='/';
  const search=onExplorer?location.search:saved.current;const version=atlas.status==='ready'?atlas.atlas.version:'';
  const clusters=useMemo(()=>new Set(atlas.status==='ready'?atlas.atlas.clusters.map(c=>c.id):[]),[atlas]);
  const parsed=useMemo(()=>parseSearchParams(new URLSearchParams(search),clusters,version),[search,clusters,version]);const state=parsed.state;
  useEffect(()=>{if(onExplorer)saved.current=location.search;},[onExplorer,location.search]);
  useEffect(()=>{if(navType==='POP')editing.current=false;},[location.key,navType]);
  useEffect(()=>{editing.current=false;},[location.pathname]);
  const write=(next:SearchUrlState,replace=false,acceptFilters=false)=>{const p=writeSearchUpdate(new URLSearchParams(search),parsed,next,acceptFilters).toString();if(`?${p}`!==search&&!(p===''&&search===''))navigate({pathname:'/',search:p?`?${p}`:''},{replace});};
  const set=(patch:Partial<ExploreState>,acceptFilters=false)=>{editing.current=false;write({...state,...patch,filters:{univs:patch.univs??state.filters.univs,fields:patch.fields??state.filters.fields,clusters:patch.clusters??state.filters.clusters}},false,acceptFilters);};
  const clearFilters=()=>set({univs:new Set(),fields:new Set(),clusters:new Set()},true);
  const value:Ctx={...state,...state.filters,set,setQuery:q=>{const replace=editing.current;editing.current=true;write({...state,query:q,sort:q.trim()?'relevance':'papers-desc',keyboardCorrection:true},replace);},endEditing:()=>{editing.current=false;},toggleUniv:u=>set({univs:toggle(state.filters.univs,u)}),toggleField:f=>set({fields:toggle(state.filters.fields,f)}),toggleCluster:c=>set({clusters:toggle(state.filters.clusters,c)}),clearFilters,acceptFilters:()=>set({},true),reset:()=>set({query:'',univs:new Set(),fields:new Set(),clusters:new Set(),sort:'papers-desc',keyboardCorrection:true},true),notices:parsed.notices,blocked:parsed.filterState!=='valid',returnUrl:`/${onExplorer?location.search:saved.current}`};
  return <C.Provider value={value}>{children}</C.Provider>;
}
export function useExplore():Ctx {const c=useContext(C);if(!c)throw new Error('ExploreProvider missing');return c;}
