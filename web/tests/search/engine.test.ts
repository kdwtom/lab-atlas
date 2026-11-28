import { describe,it,expect } from 'vitest';
import { buildSearchIndex,searchLabs,EMPTY_FILTERS,dictionary,compileConcepts } from '../../src/lib/search/index';
import type {Lab,Paper,Meta} from '../../src/types/data';
import {buildAtlas} from '../../src/data/DataContext';
const lab=(id:string,patch:Partial<Lab>={}):Lab=>({id,univ:'kaist',univ_name_ko:'KAIST',dept_name_ko:'전산학부',dept_codes:[],disciplines:['cs'],pi_name_ko:null,pi_name_en:`Professor ${id}`,lab_name:null,position:null,homepage_url:null,faculty_page_url:'',openalex_id:id,orcid:null,match_confidence:'medium',paper_count_5y:1,senior_paper_count_5y:1,vector_paper_count:1,keywords:[],cluster_id:0,x:null,y:null,intro_ko:null,intro_unavailable:null,representative_paper_ids:[],keyword_timeline:[],sources:[],...patch});
const paper=(id:string,labId:string,title:string):Paper=>({id,lab_ids:[labId],title,year:2025,venue:null,doi:null,cited_by_count:0,type:'article',pi_roles:{[labId]:{position:'last',is_corresponding:true,at_home_institution:true,order_agnostic:false}},has_abstract:false,has_tldr:false,topics:[],summary_ko:null,openalex_url:`https://openalex.org/${id}`,retrieved_at:'2026-11-16'});
const make=(labs:Lab[],papers:Paper[]=[])=>buildSearchIndex({version:'fixture',labs,papers,clusters:[],legacyTerms:{}});
const ids=(r:ReturnType<typeof searchLabs>)=>r.results.map(x=>x.labId);
describe('shared engine',()=>{
  it('builds once per Atlas load, not per query, and never reuses a different load',()=>{
    const labs=[lab('a')];const meta={generated_at:'same'} as Meta;
    const atlas=buildAtlas(labs,[],[],[],meta);const first=atlas.searchIndex();
    searchLabs(first,'missing');searchLabs(first,'RNA');
    expect(atlas.searchIndex()).toBe(first);expect(buildAtlas(labs,[],[],[],meta).searchIndex()).not.toBe(first);
  });
  it('canonical aliases have identical IDs scores and order including Korean spacing',()=>{
    const index=make([lab('b',{intro_ko:'기계학습 연구'}),lab('a',{keywords:['Machine Learning Applications']})]);
    const expected=searchLabs(index,'machine learning').results.map(({labId,score})=>({labId,score}));
    for(const q of ['기계학습','기계 학습','머신러닝']) expect(searchLabs(index,q).results.map(({labId,score})=>({labId,score}))).toEqual(expected);
  });
  it('unique exact bilingual names and names with spacing rank first',()=>{
    const index=make([lab('volume',{intro_ko:'성민혁 교수',paper_count_5y:900}),lab('named',{pi_name_ko:'성민혁',pi_name_en:'Minhyuk Sung'})]);
    for(const q of ['성민혁','성 민혁','Minhyuk Sung']) expect(ids(searchLabs(index,q))[0]).toBe('named');
  });
  it('RNA never matches internal or RNase, but matches RNA-sequencing',()=>{
    const index=make([lab('false'),lab('rna')],[paper('1','false','Internal RNase transport'),paper('2','rna','RNA-sequencing')]);
    expect(ids(searchLabs(index,'RNA'))).toEqual(['rna']);
  });
  it('atomic phrases cannot be assembled across records or punctuation',()=>{
    const index=make([lab('scatter'),lab('good'),lab('punct')],[paper('1','scatter','graph'),paper('2','scatter','neural'),paper('3','scatter','network'),paper('4','good','Graph neural network methods'),paper('5','punct','graph. neural. network')]);
    expect(ids(searchLabs(index,'graph neural network'))).toEqual(['good']);
    expect(ids(searchLabs(index,'그래프 신경망'))).toEqual(['good']);
  });
  it('unknown coherent words outrank same-record separated then scattered words',()=>{
    const index=make([lab('scatter'),lab('coherent'),lab('separate')],[paper('1','scatter','unicorn'),paper('2','scatter','transport'),paper('3','coherent','unicorn transport'),paper('4','separate','unicorn waves transport')]);
    expect(ids(searchLabs(index,'unicorn transport'))).toEqual(['coherent','separate','scatter']);
    expect(ids(searchLabs(index,'"unicorn transport"'))).toEqual(['coherent']);
  });
  it('requires all mixed/unknown terms and does not conflate related concepts',()=>{
    const index=make([lab('ml',{keywords:['machine learning']}),lab('both',{keywords:['protein structure deep learning']}),lab('dl',{keywords:['deep learning']})]);
    expect(ids(searchLabs(index,'단백질 구조 deep learning'))).toEqual(['both']);
    expect(ids(searchLabs(index,'machine learning'))).toEqual(['ml']);
    expect(ids(searchLabs(index,'machine learning missing'))).toEqual([]);
  });
  it('filters before any suggestion limit and supports multiple disciplines',()=>{
    const index=make([...Array.from({length:10},(_,i)=>lab(`a${i}`,{keywords:['machine learning']})),lab('eligible',{univ:'snu',disciplines:['math','cs'],keywords:['machine learning']})]);
    expect(ids(searchLabs(index,'기계학습',{...EMPTY_FILTERS,univs:new Set(['snu']),fields:new Set(['math'])}))).toEqual(['eligible']);
  });
  it('stable ID ties and capped paper support ignore volume/input order',()=>{
    const labs=[lab('b'),lab('a')]; const ps=[paper('1','a','unicorn'),paper('2','b','unicorn')];
    expect(ids(searchLabs(make(labs,ps),'unicorn'))).toEqual(['a','b']);
    expect(ids(searchLabs(make([...labs].reverse(),[...ps].reverse()),'unicorn'))).toEqual(['a','b']);
    const many=Array.from({length:100},(_,i)=>paper(`many${i}`,'b','unicorn'));
    expect(searchLabs(make(labs,many),'unicorn').results[0].score).toBeLessThan(4000);
  });
  it('flags questionable topic evidence without hiding exact names',()=>{
    const index=make([lab('flag',{intro_unavailable:'wrong_field',keywords:['machine learning'],pi_name_ko:'김교수'}),lab('clean',{intro_ko:'기계학습'})]);
    expect(ids(searchLabs(index,'기계학습'))).toEqual(['clean','flag']);
    expect(searchLabs(index,'김교수').results[0]).toMatchObject({labId:'flag',tier:5,cautions:['wrong_field']});
  });
  it('keeps paper IDs and full coverage evidence',()=>{
    const index=make([lab('x')],[paper('p1','x','unicorn'),paper('p2','x','transport')]);
    const hit=searchLabs(index,'unicorn transport').results[0];
    expect(hit.coverage).toBe('scattered');expect(hit.evidence.map(e=>e.paperId).sort()).toEqual(['p1','p2']);
  });
  it('excludes invalid lab-paper associations',()=>{
    const p=paper('p','x','unicorn');p.pi_roles.x.at_home_institution=false;
    const index=make([lab('x')],[p]);expect(index.diagnostics).toHaveLength(1);expect(ids(searchLabs(index,'unicorn'))).toEqual([]);
  });
  it('empty, invalid punctuation and excessive queries never match all',()=>{
    const index=make([lab('a')]);
    expect(searchLabs(index,' ').query.state).toBe('empty');
    for(const q of [',','[]','a'.repeat(201)]) {const r=searchLabs(index,q);expect(r.query.state).toBe('invalid');expect(r.results).toHaveLength(0);}
  });
  it('preserves filter-aware keyboard correction and allows original-only retry',()=>{
    const index=make([lab('ko',{univ:'snu',keywords:['Immunology']}),lab('literal',{pi_name_en:'aus dur'})]);
    const f={...EMPTY_FILTERS,univs:new Set<'snu'>(['snu'])};
    expect(searchLabs(index,'aus dur',f).correction?.applied).toBe('면역');
    expect(ids(searchLabs(index,'aus dur',f,{keyboardCorrection:false}))).toEqual([]);
    expect(searchLabs(index,'RNA').correction).toBeUndefined();
  });
  it('corrects unknown Latin spans while preserving recognized concepts and joined spacing',()=>{
    const index=make([lab('mixed',{keywords:['Machine learning','Immunology']})]);
    for(const raw of ['machine learning ausdur','기계학습 aus dur']) {
      const response=searchLabs(index,raw);
      expect(ids(response)).toEqual(['mixed']);
      expect(response.correction).toEqual({original:raw,applied:raw.replace(/aus\s?dur/,'면역'),kind:'keyboard_layout'});
      expect(ids(searchLabs(index,raw,EMPTY_FILTERS,{keyboardCorrection:false}))).toEqual([]);
    }
  });
  it('preserves scientific abbreviations while correcting adjacent unknown spans',()=>{
    const index=make([lab('rms',{keywords:['RMS','Immunology']}),lab('wrong',{keywords:['근','Immunology']})]);
    const response=searchLabs(index,'RMS ausdur');
    expect(ids(response)).toEqual(['rms']);
    expect(response.correction).toEqual({original:'RMS ausdur',applied:'RMS 면역',kind:'keyboard_layout'});
  });
  it('prefers as-typed mixed matches and only corrects within the active filters',()=>{
    const index=make([lab('typed',{keywords:['machine learning','ausdur']}),lab('corrected',{univ:'snu',keywords:['machine learning','Immunology']})]);
    expect(ids(searchLabs(index,'machine learning ausdur'))).toEqual(['typed']);
    expect(searchLabs(index,'machine learning ausdur').correction).toBeUndefined();
    const filtered=searchLabs(index,'machine learning ausdur',{...EMPTY_FILTERS,univs:new Set(['snu'])});
    expect(ids(filtered)).toEqual(['corrected']);
    expect(filtered.correction?.applied).toBe('machine learning 면역');
  });
  it('compiled dictionary has enough actual source-backed reviewed concepts',()=>{
    expect(dictionary.concepts.length).toBeGreaterThanOrEqual(50);expect(dictionary.concepts.length).toBeLessThanOrEqual(100);
    expect(()=>compileConcepts(dictionary)).not.toThrow();
    for(const c of dictionary.concepts) expect(c.sourceExamples.length).toBeGreaterThan(0);
    const collision={...dictionary,concepts:[dictionary.concepts[0],{...dictionary.concepts[0],id:'collision'}]};
    expect(()=>compileConcepts(collision)).toThrow(/Ambiguous/);
  });
});
