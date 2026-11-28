import { useAtlas } from '../data/DataContext';
import { getConceptLabel,type SearchResult,type MatchEvidence,type SearchField } from '../lib/search/index';
import { doiHref } from '../lib/format';
const FIELD:Record<SearchField,string>={pi_name_ko:'교수 이름',pi_name_en:'교수 이름',lab_name:'연구실 이름',university:'대학',department:'학과',keyword:'키워드',timeline_keyword:'연도별 키워드',intro:'소개',paper_title:'논문 제목',paper_topic:'논문 주제',cluster:'클러스터',subcluster:'세부 분야',translated_label:'키워드 번역'};
const cautionText={mixed_topics:'동명이인의 논문이 섞였을 수 있어 이 근거는 확인이 필요합니다.',wrong_field:'연구자와 논문의 연결이 정확한지 확인이 필요합니다.',limited_papers:'수집된 논문이 적어 근거가 제한적입니다.'};
export function evidenceText(e:MatchEvidence):string{return `${FIELD[e.field]} · ${e.originalText}`;}
export default function SearchEvidence({result,compact=false}:{result:SearchResult;compact?:boolean}) {
  const atlas=useAtlas();const first=result.evidence[0];if(!first)return null;
  const original=(e:MatchEvidence)=>{const source=e.sourceRecordId?atlas.searchIndex().records.get(e.sourceRecordId):undefined;return evidenceText(e)+(source?` (원문: ${source.originalText})`:'');};
  if(compact)return <span className="opt-why">{original(first)}{result.coverage==='scattered'?' · 여러 항목에서 찾음':''}{result.cautions.length?' · 근거 확인 필요':''}</span>;
  return <div className="search-evidence small"><p>{original(first)}</p>{result.coverage==='scattered'&&<p>여러 항목에서 함께 찾음</p>}
    <details><summary>일치 근거 {result.evidence.length}개</summary><ul>{result.evidence.map(e=>{const paper=e.paperId?atlas.paperById.get(e.paperId):undefined;return <li key={e.recordId}><span>{original(e)}</span>{e.conceptIds.map(id=><span key={id} className="concept-badge">{getConceptLabel(id)}</span>)}{paper&&<> · <a href={doiHref(paper.doi)??paper.openalex_url} target="_blank" rel="noreferrer">논문 원문 정보</a></>}</li>;})}</ul></details>
    {result.cautions.map(c=><p className="search-caution" key={c}>{cautionText[c]}</p>)}
  </div>;
}
