import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { Lab } from '../types/data';
import { useAtlas, clusterPath } from '../data/DataContext';
import { UNIV_LABEL, labTitle, piName } from '../lib/format';
import { FIELD_LABEL, fieldColor, type Mode } from '../lib/palette';
import StarButton from './StarButton';
import SearchEvidence from './SearchEvidence';
import type { SearchResult } from '../lib/search/index';
import type { SearchSort } from '../data/searchUrl';

type Key = 'name' | 'univ' | 'field' | 'cluster' | 'papers' | 'senior';
const COLS: { key: Key; label: string; numeric?: boolean }[] = [
  { key: 'name', label: 'PI · 연구실' },
  { key: 'univ', label: '대학' },
  { key: 'field', label: '분야 · 학과' },
  { key: 'cluster', label: '클러스터' },
  { key: 'papers', label: '최근 5년 논문', numeric: true },
  { key: 'senior', label: '기준 충족 논문', numeric: true },
];

export default function ListView({ labs, mode, results, searching, sort, onSort, resetKey }: { labs: Lab[]; mode: Mode; results:readonly SearchResult[]; searching:boolean; sort:SearchSort; onSort:(sort:SearchSort)=>void; resetKey:string }) {
  const atlas = useAtlas();
  const [sortKey,direction]=sort.split('-');
  const pageKey=resetKey+sort;
  const [page,setPage]=useState({key:pageKey,limit:50});
  const limit=page.key===pageKey?page.limit:50;
  const evidence=useMemo(()=>new Map(results.map(r=>[r.labId,r])),[results]);
  const clusterName = (l: Lab) => clusterPath(atlas, l);

  const rows = useMemo(() => {
    if(sort==='relevance')return labs;
    const val = (l: Lab): string | number => {
      switch (sortKey) {
        case 'name': return piName(l);
        case 'univ': return UNIV_LABEL[l.univ];
        case 'field': return FIELD_LABEL[l.disciplines[0]] + l.dept_name_ko;
        case 'cluster': return clusterName(l);
        case 'papers': return l.paper_count_5y;
        case 'senior': return l.senior_paper_count_5y;
        default: return l.id;
      }
    };
    return [...labs].sort((a, b) => {
      const x = val(a);
      const y = val(b);
      const c = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y), 'ko');
      return (direction==='asc' ? c : -c) || (a.id<b.id?-1:a.id>b.id?1:0);
    });
  }, [labs, sort, atlas]);

  return (
    <div className="list-wrap">
      {searching&&<p className="small"><button type="button" aria-pressed={sort==='relevance'} onClick={()=>onSort('relevance')}>관련도순</button> 검색어와의 관련도이며 연구실 평가가 아닙니다.</p>}
      <p className="small muted" aria-live="polite">{rows.length}곳 중 {Math.min(limit,rows.length)}곳 표시</p>
      <table className="list">
        <caption className="sr-only">연구실 목록. 열 제목 버튼으로 정렬할 수 있습니다.</caption>
        <thead>
          <tr>
            {COLS.map((c) => (
              <th key={c.key} scope="col" className={c.numeric ? 'num' : ''}
                  aria-sort={sortKey === c.key ? (direction==='asc' ? 'ascending' : 'descending') : 'none'}>
                <button onClick={() => onSort(`${c.key}-${sortKey===c.key?(direction==='asc'?'desc':'asc'):c.numeric?'desc':'asc'}`)}>
                  {c.label}
                  <span aria-hidden="true" className="sort-ind">{sortKey === c.key ? (direction==='asc' ? '▲' : '▼') : ''}</span>
                </button>
              </th>
            ))}
            <th scope="col">핵심 키워드</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0,limit).map((l) => (
            <tr key={l.id} data-lab-id={l.id}>
              <td>
                <StarButton id={l.id} name={piName(l)} compact />{' '}
                <Link to={`/lab/${encodeURIComponent(l.id)}`} className="row-link">{piName(l)}</Link>
                {l.pi_name_en && l.pi_name_ko && <span className="en"> {l.pi_name_en}</span>}
                <div className="muted small">{labTitle(l)}</div>
                {searching&&evidence.has(l.id)&&<SearchEvidence result={evidence.get(l.id)!}/>}
              </td>
              <td>{UNIV_LABEL[l.univ]}</td>
              <td>
                <span className="dot" style={{ background: fieldColor(l.disciplines[0], mode) }} aria-hidden="true" />
                {l.disciplines.map((d) => FIELD_LABEL[d]).join(' · ')}
                <div className="muted small">{l.dept_name_ko}</div>
              </td>
              <td>{clusterName(l)}</td>
              <td className="num">{l.paper_count_5y}</td>
              <td className="num">{l.senior_paper_count_5y}</td>
              <td className="small">{l.keywords.slice(0, 3).join(' · ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length>limit&&<button type="button" className="list-more load-more" onClick={()=>setPage({key:pageKey,limit:limit+50})}>{Math.min(50,rows.length-limit)}곳 더 보기</button>}
      {rows.length === 0 && <p className="empty">조건에 맞는 연구실이 없습니다.</p>}
    </div>
  );
}
