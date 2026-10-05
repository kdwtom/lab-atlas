import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { Lab } from '../types/data';
import { useAtlas } from '../data/DataContext';
import { UNIV_LABEL, labTitle, piName } from '../lib/format';
import { clusterColor, type Mode } from '../lib/palette';

type Key = 'name' | 'univ' | 'cluster' | 'papers' | 'senior';
const COLS: { key: Key; label: string; numeric?: boolean }[] = [
  { key: 'name', label: 'PI · 연구실' },
  { key: 'univ', label: '대학' },
  { key: 'cluster', label: '클러스터' },
  { key: 'papers', label: '최근 5년 논문', numeric: true },
  { key: 'senior', label: '마지막·교신저자', numeric: true },
];

export default function ListView({ labs, mode }: { labs: Lab[]; mode: Mode }) {
  const atlas = useAtlas();
  const [sort, setSort] = useState<{ key: Key; asc: boolean }>({ key: 'papers', asc: false });
  const clusterName = (l: Lab) => (l.cluster_id === null ? '' : atlas.clusterById.get(l.cluster_id)?.label_ko ?? '');

  const rows = useMemo(() => {
    const val = (l: Lab): string | number => {
      switch (sort.key) {
        case 'name': return piName(l);
        case 'univ': return UNIV_LABEL[l.univ];
        case 'cluster': return clusterName(l);
        case 'papers': return l.paper_count_5y;
        case 'senior': return l.senior_paper_count_5y;
      }
    };
    return [...labs].sort((a, b) => {
      const x = val(a);
      const y = val(b);
      const c = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y), 'ko');
      return sort.asc ? c : -c;
    });
  }, [labs, sort]); // eslint-disable-line react-hooks/exhaustive-deps -- clusterName only reads static atlas data

  return (
    <div className="list-wrap">
      <table className="list">
        <caption className="sr-only">연구실 목록. 열 제목 버튼으로 정렬할 수 있습니다.</caption>
        <thead>
          <tr>
            {COLS.map((c) => (
              <th key={c.key} scope="col" className={c.numeric ? 'num' : ''}
                  aria-sort={sort.key === c.key ? (sort.asc ? 'ascending' : 'descending') : 'none'}>
                <button onClick={() => setSort((s) => ({ key: c.key, asc: s.key === c.key ? !s.asc : !c.numeric }))}>
                  {c.label}
                  <span aria-hidden="true" className="sort-ind">{sort.key === c.key ? (sort.asc ? '▲' : '▼') : ''}</span>
                </button>
              </th>
            ))}
            <th scope="col">핵심 키워드</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((l) => (
            <tr key={l.id}>
              <td>
                <Link to={`/lab/${encodeURIComponent(l.id)}`} className="row-link">{piName(l)}</Link>
                {l.pi_name_en && l.pi_name_ko && <span className="en"> {l.pi_name_en}</span>}
                <div className="muted small">{labTitle(l)}</div>
              </td>
              <td>{UNIV_LABEL[l.univ]}</td>
              <td>
                <span className="dot" style={{ background: clusterColor(l.cluster_id, mode) }} aria-hidden="true" />
                {clusterName(l)}
              </td>
              <td className="num">{l.paper_count_5y}</td>
              <td className="num">{l.senior_paper_count_5y}</td>
              <td className="small">{l.keywords.slice(0, 3).join(' · ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && <p className="empty">조건에 맞는 연구실이 없습니다.</p>}
    </div>
  );
}
