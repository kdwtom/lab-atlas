import {describe,it,expect} from 'vitest';
import {parseSearchParams,writeSearchParams,writeSearchUpdate} from '../../src/data/searchUrl';
const parse=(p:string)=>parseSearchParams(new URLSearchParams(p),new Set([0,3]),'v1');
describe('hash-route search state',()=>{
  it('round trips query/filter/sort while preserving shortlist and unknown keys',()=>{
    const p=new URLSearchParams('q=RNA&univ=snu,kaist&field=cs&cluster=3&data=v1&view=list&sort=papers-desc&labs=a,b&dummy=300&custom=x');
    const state=parseSearchParams(p,new Set([3]),'v1').state;
    const out=writeSearchParams(p,state);
    expect(out.get('univ')).toBe('kaist,snu');expect(out.get('labs')).toBe('a,b');expect(out.get('dummy')).toBe('300');expect(out.get('custom')).toBe('x');
    expect(parse(out.toString()).state).toEqual(state);
  });
  it('does not silently broaden an invalid filter to all',()=>{
    expect(parse('univ=unknown').filterState).toBe('invalid');expect(parse('cluster=999').filterState).toBe('invalid');expect(parse('field=').filterState).toBe('invalid');
    expect([...parse('univ=kaist,unknown').state.filters.univs]).toEqual(['kaist']);expect(parse('univ=kaist,unknown').notices.length).toBeGreaterThan(0);
  });
  it('detects changed dataset clusters and preserves explicit original-only search',()=>{
    expect(parse('cluster=3&data=old').filterState).toBe('stale');expect(parse('correction=off').state.keyboardCorrection).toBe(false);
  });
  it('defaults active searches to relevance and empty browsing to papers',()=>{
    expect(parse('q=RNA').state.sort).toBe('relevance');expect(parse('').state.sort).toBe('papers-desc');expect(parse('q=RNA&sort=oops').state.sort).toBe('relevance');
  });
  it('keeps invalid filter groups blocked during query/view or other filter edits',()=>{
    const previous=new URLSearchParams('q=RNA&univ=unknown&custom=keep');const parsed=parse(previous.toString());
    const next={...parsed.state,query:'machine learning',view:'list' as const,filters:{...parsed.state.filters,fields:new Set<'cs'>(['cs'])}};
    const updated=writeSearchUpdate(previous,parsed,next);
    expect(updated.get('univ')).toBe('unknown');expect(updated.get('custom')).toBe('keep');expect(parse(updated.toString()).filterState).toBe('invalid');
    const cleared=writeSearchUpdate(previous,parsed,{...parsed.state,filters:{univs:new Set(),fields:new Set(),clusters:new Set()}},true);
    expect(parse(cleared.toString()).filterState).toBe('valid');expect(cleared.has('univ')).toBe(false);
    const selected=writeSearchUpdate(previous,parsed,{...parsed.state,filters:{...parsed.state.filters,univs:new Set<'kaist'>(['kaist'])}});
    expect(parse(selected.toString()).filterState).toBe('valid');expect(selected.get('univ')).toBe('kaist');
  });
  it('keeps an old cluster version until explicit acceptance or cluster replacement',()=>{
    const previous=new URLSearchParams('q=RNA&cluster=3&data=old');const parsed=parse(previous.toString());
    const updated=writeSearchUpdate(previous,parsed,{...parsed.state,query:'RNA splicing',view:'list'});
    expect(updated.get('data')).toBe('old');expect(parse(updated.toString()).filterState).toBe('stale');
    expect(parse(writeSearchUpdate(previous,parsed,parsed.state,true).toString()).filterState).toBe('valid');
    const changed=writeSearchUpdate(previous,parsed,{...parsed.state,filters:{...parsed.state.filters,clusters:new Set([0])}});
    expect(changed.get('data')).toBe('v1');expect(parse(changed.toString()).filterState).toBe('valid');
  });
});
