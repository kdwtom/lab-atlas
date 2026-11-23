import type { Lab } from '../../types/data';
import type { ConceptDictionary, IndexedRecord, LabMatch, MatchEvidence, ParsedQuery, QueryUnit, SearchFilters, SearchIndex, SearchOptions, SearchResponse } from './types';
import { fold, nameKey, normalizeText, exactName, hasPhrase, literalHit, stableCompare } from './normalize';
import { recognizeConcepts } from './concepts';
import { fromKeyboard } from './keyboard';
import { rankLabMatch, compareResults } from './rank';
export const EMPTY_FILTERS:SearchFilters={univs:new Set(),fields:new Set(),clusters:new Set()};
export const filterKey=(f:SearchFilters) => JSON.stringify([[...f.univs].sort(),[...f.fields].sort(),[...f.clusters].sort((a,b)=>a-b)]);
export function passesSearchFilters(l:Lab,f:SearchFilters):boolean {
  return (!f.univs.size||f.univs.has(l.univ)) && (!f.fields.size||l.disciplines.some((d)=>f.fields.has(d))) && (!f.clusters.size||(l.cluster_id!==null&&f.clusters.has(l.cluster_id)));
}
export const filterLabIds=(index:SearchIndex,f:SearchFilters) => [...index.labs.values()].filter(({lab})=>passesSearchFilters(lab,f)).map(({lab})=>lab.id).sort(stableCompare);
export function interpretQuery(raw:string,dict:ConceptDictionary):ParsedQuery {
  const value=fold(raw).trim(); const units:QueryUnit[]=[]; const notices:string[]=[]; const groups:string[][]=[];
  const add=(u:QueryUnit) => {if (!units.some((x)=>x.id===u.id)) units.push(u);};
  let masked=value;
  for (const m of value.matchAll(/"([^"]+)"/g)) {
    const body=m[1]; const mentions=recognizeConcepts(body,dict);
    if (mentions.length===1 && mentions[0].start===0 && mentions[0].end===body.length) add({id:`c:${mentions[0].id}`,kind:'concept',conceptId:mentions[0].id});
    else {
      const tokens=normalizeText(body).tokens.map((t)=>t.text);
      if(tokens.length) add({id:`p:${tokens.join(' ')}`,kind:'phrase',tokens});
    }
    masked=masked.slice(0,m.index)+'\0'.repeat(m[0].length)+masked.slice(m.index!+m[0].length);
  }
  for (const m of recognizeConcepts(masked,dict)) {
    add({id:`c:${m.id}`,kind:'concept',conceptId:m.id});
    masked=masked.slice(0,m.start)+'\0'.repeat(m.end-m.start)+masked.slice(m.end);
  }
  for (const part of masked.split(/\0+/)) {
    const tokens=normalizeText(part).tokens; const grouped=new Map<number,string[]>();
    for (const t of tokens) {
      add({id:`l:${t.text}`,kind:'literal',normalized:t.text});
      if(!grouped.has(t.segment)) grouped.set(t.segment,[]);
      grouped.get(t.segment)!.push(t.text);
    }
    groups.push(...grouped.values());
  }
  if ((value.match(/"/g)?.length ?? 0)%2) notices.push('unclosed_quote');
  if (units.some((u)=>u.kind==='literal' && ['ml','ai','pde'].includes(u.normalized))) notices.push('ambiguous_abbreviation');
  const state=!value?'empty':!units.length || raw.length>200 || units.length>20?'invalid':'ready';
  if (raw.length>200||units.length>20) notices.push('query_too_long');
  return {raw,normalized:value,state,units,key:JSON.stringify([units.map((u)=>u.id).sort(),groups.filter((g)=>g.length>1)]),notices,literalGroups:groups};
}
const matchUnit=(r:IndexedRecord,u:QueryUnit) => u.kind==='concept'?r.conceptIds.has(u.conceptId):u.kind==='phrase'?hasPhrase(r.normalized,u.tokens):literalHit(r.normalized,u.normalized);
const nameFields=new Set(['pi_name_ko','pi_name_en','lab_name']);
function evidence(r:IndexedRecord,units:readonly QueryUnit[],lab:Lab,exact=false):MatchEvidence {
  const identity=nameFields.has(r.field)||r.field==='university'||r.field==='department'||r.field==='intro';
  const quality=!identity && (lab.intro_unavailable==='mixed_topics'||lab.intro_unavailable==='wrong_field')?lab.intro_unavailable:'ordinary';
  return {recordId:r.id,unitIds:units.map((u)=>u.id),field:r.field,originalText:r.originalText,conceptIds:units.flatMap((u)=>u.kind==='concept'?[u.conceptId]:[]),paperId:r.paperId,sourceRecordId:r.sourceRecordId,quality,method:exact?'exact_name':r.field==='translated_label'?'legacy_translation':units.some((u)=>u.kind==='concept')?'concept':units.some((u)=>u.kind==='phrase')?'phrase':'literal'};
}
export function collectLabMatch(index:SearchIndex,labId:string,query:ParsedQuery,matchingRecordIds?:ReadonlySet<string>):LabMatch|null {
  const doc=index.labs.get(labId)!;
  const caution=doc.lab.intro_unavailable;
  const cautions:LabMatch['cautions']=caution==='insufficient_papers'?['limited_papers']:caution?[caution]:[];
  const named=doc.nameRecordIds.map(id=>index.records.get(id)!).find((r)=>exactName(r.originalText,query.raw));
  if(named) return {labId,exactName:true,evidence:[evidence(named,query.units,doc.lab,true)],coveredUnitIds:new Set(query.units.map((u)=>u.id)),requiresQuestionableEvidence:false,cautions};
  const found:MatchEvidence[]=[]; const covered=new Set<string>(); const ordinary=new Set<string>();
  for (const id of matchingRecordIds??doc.recordIds) {
    const r=index.records.get(id)!;
    const units=query.units.filter((u)=>matchUnit(r,u));
    if(!units.length) continue;
    const e=evidence(r,units,doc.lab); found.push(e);
    units.forEach((u)=>{covered.add(u.id);if(e.quality==='ordinary') ordinary.add(u.id);});
  }
  if(covered.size!==query.units.length) return null;
  return {labId,exactName:false,evidence:found,coveredUnitIds:covered,requiresQuestionableEvidence:ordinary.size!==query.units.length,cautions};
}
function candidates(index:SearchIndex,q:ParsedQuery,eligible:readonly string[]) {
  const eligibleIds=new Set(eligible);let allowed=eligibleIds;
  const recordsByLab=new Map<string,Set<string>>();
  // A full stored name is an independent identity path, including Korean spacing.
  const key=nameKey(q.raw);const named=new Set(index.names.get(key)??[]);
  if(/^[가-힣\s]+$/.test(key))(index.names.get(key.replace(/\s/g,''))??[]).forEach(id=>named.add(id));
  const names=[...named].filter(id=>allowed.has(id));
  for (const unit of q.units) {
    const records=new Set<string>();
    if(unit.kind==='concept') (index.concepts.get(unit.conceptId)??[]).forEach((id)=>records.add(id));
    else {
      const word=unit.kind==='phrase'?unit.tokens[0]:unit.normalized;
      if(/[가-힣]/.test(word)) for(const [token,ids] of index.tokens) {if(token.includes(word)) ids.forEach((id)=>records.add(id));}
      else (index.tokens.get(word)??[]).forEach((id)=>records.add(id));
    }
    const ids=new Set<string>();
    for(const rid of records) {
      const r=index.records.get(rid)!;
      if(!matchUnit(r,unit))continue;
      for(const id of r.labIds) {
        if(!eligibleIds.has(id))continue;
        ids.add(id);
        if(!recordsByLab.has(id))recordsByLab.set(id,new Set());
        recordsByLab.get(id)!.add(rid);
      }
    }
    allowed=new Set([...allowed].filter((id)=>ids.has(id)));
  }
  return {labIds:[...new Set([...allowed,...names])].sort(stableCompare),recordsByLab};
}
function run(index:SearchIndex,q:ParsedQuery,eligible:readonly string[]) {
  if(q.state!=='ready') return [];
  const matches=candidates(index,q,eligible);
  return matches.labIds.flatMap((id)=>{const m=collectLabMatch(index,id,q,matches.recordsByLab.get(id));return m?[rankLabMatch(m,q,index)]:[];}).sort(compareResults);
}
/** Preserve known concepts and scientific abbreviations while correcting only unknown Latin spans. */
function keyboardAttempts(raw:string,dict:ConceptDictionary):string[] {
  const value=raw.normalize('NFKC');
  // Concept offsets refer to folded text. Skip the rare length-changing case fold rather than
  // risk replacing part of a protected Unicode word with offsets from a different string.
  if(fold(value).length!==value.length) return [];
  const protectedSpans=[...recognizeConcepts(value,dict)];
  for(const m of value.matchAll(/"[^"]*"|\b[A-Z]{2,}\b/g)) {
    protectedSpans.push({id:'literal',start:m.index!,end:m.index!+m[0].length});
  }
  const abbreviations=new Set(['ml','ai','pde',...dict.concepts
    .filter(c=>c.review.status==='approved')
    .flatMap(c=>c.aliases.filter(a=>a.kind==='abbreviation').map(a=>fold(a.text)))]);
  const spans:[number,number][]=[];
  for(const m of value.matchAll(/(?<![\p{L}\p{N}])[a-zA-Z]+(?![\p{L}\p{N}])/gu)) {
    const start=m.index!; const end=start+m[0].length;
    if(abbreviations.has(fold(m[0])) || protectedSpans.some(s=>start<s.end&&end>s.start)) continue;
    spans.push([start,end]);
  }
  const groups:[number,number][]=[];
  for(const [start,end] of spans) {
    const previous=groups.at(-1);
    if(previous && /^\s+$/.test(value.slice(previous[1],start))) previous[1]=end;
    else groups.push([start,end]);
  }
  const replace=(ranges:readonly [number,number][],joined:boolean)=>{
    let result=value;
    // Replace right to left so earlier original offsets remain valid.
    for(const [start,end] of [...ranges].reverse()) {
      const original=value.slice(start,end);
      const converted=fromKeyboard(joined?original.replace(/\s+/g,''):original);
      if(converted) result=result.slice(0,start)+converted+result.slice(end);
    }
    return result;
  };
  return [...new Set([replace(groups,true),replace(spans,false)])].filter(attempt=>attempt!==value);
}
export function searchLabs(index:SearchIndex,raw:string,filters:SearchFilters=EMPTY_FILTERS,options:SearchOptions={}):SearchResponse {
  const query=interpretQuery(raw,index.dictionary); const eligibleLabIds=filterLabIds(index,filters);
  let applied=query; let results=run(index,query,eligibleLabIds); let correction:SearchResponse['correction'];
  if(!results.length&&query.state==='ready'&&options.keyboardCorrection!==false) {
    for(const attempt of keyboardAttempts(raw,index.dictionary)) {
      const next=interpretQuery(attempt,index.dictionary); const hits=run(index,next,eligibleLabIds);
      if(hits.length){applied=next;results=hits;correction={original:raw,applied:attempt,kind:'keyboard_layout'};break;}
    }
  }
  const response:SearchResponse={query:applied,eligibleLabIds,results,matchedIds:new Set(results.map((r)=>r.labId)),total:results.length,correction};
  if(options.includeUnfilteredCount && !results.length && applied.state==='ready') response.unfilteredTotal=run(index,applied,filterLabIds(index,EMPTY_FILTERS)).length;
  return response;
}
