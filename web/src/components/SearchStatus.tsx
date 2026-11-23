import type {SearchResponse} from '../lib/search/index';
export default function SearchStatus({response,onOriginal,onClearFilters}:{response:SearchResponse;onOriginal?:()=>void;onClearFilters?:()=>void}) {
  return <div className="search-status small" aria-live="polite">
    {response.correction&&<p>‘{response.correction.original}’을 ‘{response.correction.applied}’으로 바꿔 찾았습니다. {onOriginal&&<button className="link-btn" onClick={onOriginal}>입력한 글자로만 찾기</button>}</p>}
    {response.query.state==='invalid'&&<p>{response.query.notices.includes('query_too_long')?'검색어는 200자, 20개 항목 이내로 입력해 주세요.':'이름이나 연구 주제를 입력해 주세요.'}</p>}
    {response.query.notices.includes('ambiguous_abbreviation')&&<p>약어는 여러 뜻이 있어 입력한 글자로 찾았습니다. 연구 주제를 함께 입력해 보세요.</p>}
    {response.query.notices.includes('unclosed_quote')&&<p>닫히지 않은 따옴표는 일반 검색어로 처리했습니다.</p>}
    {response.query.state==='ready'&&response.total===0&&<p>{(response.unfilteredTotal??0)>0?<>선택한 필터에서는 결과가 없습니다. 전체에서는 {response.unfilteredTotal}곳이 일치합니다. {onClearFilters&&<button className="link-btn" onClick={onClearFilters}>필터 해제</button>}</>:'일치하는 연구실이 없습니다. 다른 표현이나 이름으로 검색해 보세요.'}</p>}
  </div>;
}
