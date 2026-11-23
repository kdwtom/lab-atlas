import type { LabMatch, MatchEvidence, ParsedQuery, SearchField, SearchResult, SearchIndex } from './types';
import { hasPhrase, stableCompare } from './normalize';
const weights: Record<SearchField,number> = {pi_name_ko:12,pi_name_en:12,lab_name:12,keyword:10,intro:6,paper_title:6,timeline_keyword:3,paper_topic:3,university:2,department:2,cluster:2,subcluster:2,translated_label:1};
export function compareEvidence(a:MatchEvidence,b:MatchEvidence):number {
  return Number(a.quality!=='ordinary')-Number(b.quality!=='ordinary') || weights[b.field]-weights[a.field] || stableCompare(a.recordId,b.recordId);
}
export function rankLabMatch(match:LabMatch, query:ParsedQuery,index:SearchIndex):SearchResult {
  const complete=match.evidence.filter((e) => e.unitIds.length===query.units.length);
  const ordinaryComplete=complete.filter((e) => e.quality==='ordinary');
  let tier: SearchResult['tier']=1;
  if (match.exactName) tier=5;
  else for (const e of ordinaryComplete) {
    const strong=query.literalGroups.every((g) => g.length<2 || hasPhrase(index.records.get(e.recordId)!.normalized,g));
    const t=e.field==='keyword' && strong?4:(e.field==='intro'||e.field==='paper_title')&&strong?3:2;
    tier=Math.max(tier,t) as SearchResult['tier'];
  }
  if (!match.exactName && match.requiresQuestionableEvidence) tier=1;
  const sorted=[...match.evidence].sort(compareEvidence);
  const chosen=new Set<string>();
  let sum=0;
  for (const unit of query.units) {
    const evidence=sorted.find((e) => e.unitIds.includes(unit.id))!;
    chosen.add(evidence.recordId); sum+=weights[evidence.field];
  }
  const usedPapers=new Set(sorted.filter(e=>chosen.has(e.recordId)&&e.paperId).map(e=>e.paperId));
  const extraPapers=new Set(sorted.filter((e) => e.paperId && e.quality==='ordinary' && !usedPapers.has(e.paperId)).map((e) => e.paperId));
  const mean=match.exactName?12:sum/Math.max(1,query.units.length);
  const base=Math.min(99,Math.floor(90*mean/12)+Math.min(9,5*Math.min(2,extraPapers.size)));
  const detail=tier===1?(match.requiresQuestionableEvidence?Math.floor(base/2):50+Math.floor(base/2)):base;
  // Start with a coherent record where available, then cover every remaining unit.
  const first=complete.sort(compareEvidence)[0] ?? sorted[0];
  const evidence:MatchEvidence[]=[]; const covered=new Set<string>();
  for (const e of [first,...sorted]) {
    if (!e || !e.unitIds.some((id) => !covered.has(id))) continue;
    evidence.push(e); e.unitIds.forEach((id) => covered.add(id));
  }
  return {labId:match.labId,score:tier*1000+detail,tier,evidence,coverage:complete.length?'single_record':'scattered',cautions:match.cautions};
}
export const compareResults=(a:SearchResult,b:SearchResult) => b.score-a.score || stableCompare(a.labId,b.labId);
