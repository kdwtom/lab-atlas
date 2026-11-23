import type { IndexedRecord, NormalizedText, SearchDataset, SearchField, SearchIndex, ConceptDictionary } from './types';
import { nameKey, normalizeText, stableCompare } from './normalize';
import { compileConcepts, dictionary, recognizeConcepts } from './concepts';
export * from './types';
export { dictionary, getConceptLabel, compileConcepts } from './concepts';
export { fromKeyboard } from './keyboard';
export { searchLabs, interpretQuery, passesSearchFilters, filterLabIds, filterKey, EMPTY_FILTERS } from './query';
export function buildSearchIndex(data: SearchDataset, dict: ConceptDictionary = dictionary): SearchIndex {
  const start = performance.now(); compileConcepts(dict);
  const labs = new Map(data.labs.map((lab) => [lab.id,{lab,recordIds:[] as string[],nameRecordIds:[] as string[]}]));
  const names = new Map<string,Set<string>>();
  const records = new Map<string,IndexedRecord>(); const concepts = new Map<string,Set<string>>(); const tokens = new Map<string,Set<string>>();
  const diagnostics: string[] = [];
  const cache = new Map<string,{normalized:NormalizedText;conceptIds:ReadonlySet<string>}>();
  function add(id: string, labIds: string[], field: SearchField, text: string | null, paperId?:string, year?:number, sourceRecordId?:string) {
    if (!text?.trim() || !labIds.length) return;
    let values = cache.get(text);
    if (!values) { values = {normalized:normalizeText(text),conceptIds:new Set(recognizeConcepts(text,dict).map((m) => m.id))}; cache.set(text,values); }
    const record:IndexedRecord = {id,labIds,field,originalText:text,...values,conceptIds:field==='translated_label'?new Set():values.conceptIds,paperId,year,sourceRecordId};
    records.set(id,record);
    for (const labId of labIds) labs.get(labId)?.recordIds.push(id);
    if(['pi_name_ko','pi_name_en','lab_name'].includes(field)) {
      const key=nameKey(text); const keys=[key];if(/^[가-힣\s]+$/.test(key))keys.push(key.replace(/\s/g,''));
      for(const labId of labIds){labs.get(labId)!.nameRecordIds.push(id);for(const k of keys){if(!names.has(k))names.set(k,new Set());names.get(k)!.add(labId);}}
    }
    for (const c of record.conceptIds) { if (!concepts.has(c)) concepts.set(c,new Set()); concepts.get(c)!.add(id); }
    for (const t of new Set(record.normalized.tokens.map((t) => t.text))) { if (!tokens.has(t)) tokens.set(t,new Set()); tokens.get(t)!.add(id); }
    if (['keyword','timeline_keyword','paper_topic'].includes(field)) {
      for (const [i,ko] of (data.legacyTerms[text] ?? []).entries()) add(`${id}:ko:${i}`,labIds,'translated_label',ko,paperId,year,id);
    }
  }
  for (const lab of data.labs) {
    for (const field of ['pi_name_ko','pi_name_en','lab_name'] as const) add(`${lab.id}:${field}`,[lab.id],field,lab[field]);
    add(`${lab.id}:university`,[lab.id],'university',lab.univ_name_ko);
    add(`${lab.id}:department`,[lab.id],'department',lab.dept_name_ko);
    add(`${lab.id}:intro`,[lab.id],'intro',lab.intro_ko);
    for (const k of new Set(lab.keywords)) add(`${lab.id}:kw:${k}`,[lab.id],'keyword',k);
    for (const y of lab.keyword_timeline) for (const k of new Set(y.keywords)) add(`${lab.id}:year:${y.year}:${k}`,[lab.id],'timeline_keyword',k,undefined,y.year);
    const cluster=data.clusters.find((c) => c.id===lab.cluster_id);
    add(`${lab.id}:cluster`,[lab.id],'cluster',cluster?.label_ko ?? null);
    add(`${lab.id}:subcluster`,[lab.id],'subcluster',cluster?.subclusters?.find((c) => c.id===lab.subcluster_id)?.label_ko ?? null);
  }
  for (const paper of data.papers) {
    const ids=paper.lab_ids.filter((id) => {
      const valid=labs.has(id) && paper.pi_roles[id]?.at_home_institution===true;
      if (!valid) diagnostics.push(`Ignored invalid paper association ${paper.id}:${id}`);
      return valid;
    });
    add(`paper:${paper.id}`,ids,'paper_title',paper.title,paper.id);
    for (const topic of paper.topics) {
      add(`paper:${paper.id}:topic:${topic.id}`,ids,'paper_topic',topic.name,paper.id);
    }
  }
  for (const l of labs.values()) l.recordIds.sort(stableCompare);
  return {datasetVersion:data.version,dictionaryVersion:dict.version,dictionary:dict,labs,names,records,concepts,tokens,diagnostics,buildMs:performance.now()-start};
}
