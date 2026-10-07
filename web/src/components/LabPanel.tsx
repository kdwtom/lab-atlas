import { Link } from 'react-router-dom';
import type { Edge, Lab } from '../types/data';
import { useAtlas } from '../data/DataContext';
import { NA, affiliation, piName } from '../lib/format';
import { clusterColor, type Mode } from '../lib/palette';

interface Props {
  lab: Lab | null;
  edge: Edge | null;
  mode: Mode;
  sheet: boolean;          // rendered as a mobile bottom sheet
  pinned?: boolean;        // desktop: the lab was pinned by a click
  onClose?: () => void;
}

export function ClusterChip({ id, mode }: { id: number | null; mode: Mode }) {
  const atlas = useAtlas();
  const c = id === null ? undefined : atlas.clusterById.get(id);
  return (
    <span className="cluster-chip">
      <span className="dot" style={{ background: clusterColor(id, mode) }} aria-hidden="true" />
      {c ? c.label_ko : NA}
    </span>
  );
}

function EdgeInfo({ edge }: { edge: Edge }) {
  const atlas = useAtlas();
  const a = atlas.labById.get(edge.source);
  const b = atlas.labById.get(edge.target);
  return (
    <div className="panel-body">
      <p className="eyebrow">{edge.type === 'similarity' ? '연구 주제 유사도' : '공동연구'}</p>
      <h2 className="panel-title">{a ? piName(a) : edge.source} ↔ {b ? piName(b) : edge.target}</h2>
      {edge.type === 'similarity' ? (
        <>
          <p>코사인 유사도 <strong>{edge.weight.toFixed(3)}</strong></p>
          <h3>연결 이유 (공통 키워드)</h3>
          {edge.reasons.length ? (
            <ul className="tags">{edge.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
          ) : <p className="muted">{NA}</p>}
        </>
      ) : (
        <p>두 PI가 함께 저자로 참여한 논문 <strong>{edge.weight}편</strong></p>
      )}
    </div>
  );
}

export default function LabPanel({ lab, edge, mode, sheet, pinned, onClose }: Props) {
  const atlas = useAtlas();
  if (!lab && edge) {
    return <aside className={sheet ? 'panel sheet' : 'panel'} aria-live="polite"><EdgeInfo edge={edge} /></aside>;
  }
  if (!lab) {
    if (sheet) return null;
    const m = atlas.meta;
    return (
      <aside className="panel">
        <div className="panel-body">
          <p className="eyebrow">연구실 지형도</p>
          <h2 className="panel-title">비슷한 연구를 하는 연구실을 한눈에</h2>
          <p>
            국내 6개 생명과학 학과의 연구실 {m.counts.labs}곳을 최근 논문의 내용으로 배치했습니다.
            가까이 있거나 선으로 이어진 연구실일수록 연구 주제가 비슷합니다.
          </p>
          <ul className="hint">
            <li>노드에 마우스를 올리면 연구실 정보가 여기에 표시되고, 마우스를 옮겨도 남아 있어 스크롤할 수 있습니다.</li>
            <li>노드를 클릭하면 이 창에 고정되고, 한 번 더 클릭하면 상세 페이지로 이동합니다. 빈 곳 클릭이나 Esc로 고정을 풉니다.</li>
            <li>세부분야마다 연결선이 가장 많은 연구실은 이름이 항상 표시되고, 확대하면 모든 PI 이름이 나타납니다.</li>
            <li>선에 마우스를 올리면 연결 이유를 볼 수 있습니다.</li>
          </ul>
          <p className="muted small">
            {m.window_years[0]}–{m.window_years[1]}년 마지막·교신저자 논문 {m.min_senior_papers}편 이상 기준 ·{' '}
            <Link to="/about">방법론 보기</Link>
          </p>
        </div>
      </aside>
    );
  }

  const rep = lab.representative_paper_ids.map((id) => atlas.paperById.get(id)).find((p) => p !== undefined);
  return (
    // keyed by lab so switching labs starts the panel scrolled to the top
    <aside key={lab.id} className={sheet ? 'panel sheet' : 'panel'} aria-live="polite" aria-label={`${piName(lab)} 연구실 미리보기`}>
      {sheet && onClose && <button className="sheet-close" onClick={onClose} aria-label="닫기">×</button>}
      <div className="panel-body">
        {pinned && onClose && (
          <p className="pin-bar">
            <span>고정됨 · 노드를 다시 클릭하면 상세 페이지</span>
            <button type="button" onClick={onClose}>고정 해제</button>
          </p>
        )}
        <p className="eyebrow">{affiliation(lab)}</p>
        <h2 className="panel-title">
          {piName(lab)}
          {lab.pi_name_en && lab.pi_name_ko && <span className="en"> {lab.pi_name_en}</span>}
        </h2>
        <ClusterChip id={lab.cluster_id} mode={mode} />
        {sheet && <Link className="btn btn-top" to={`/lab/${encodeURIComponent(lab.id)}`}>상세 페이지 보기</Link>}
        <h3>핵심 키워드</h3>
        {lab.keywords.length ? <ul className="tags">{lab.keywords.slice(0, 5).map((k) => <li key={k}>{k}</li>)}</ul>
          : <p className="muted">{NA}</p>}
        <h3>연구실 소개</h3>
        <p className={lab.intro_ko ? '' : 'muted'}>{lab.intro_ko ?? NA}</p>
        <h3>대표 논문</h3>
        {rep ? (
          <div className="rep">
            <p className="rep-title">{rep.title} <span className="muted">({rep.year})</span></p>
            <p className={rep.summary_ko ? '' : 'muted'}>{rep.summary_ko?.one_line ?? `한 줄 요약: ${NA}`}</p>
          </div>
        ) : <p className="muted">{NA}</p>}
        {!sheet && <Link className="btn" to={`/lab/${encodeURIComponent(lab.id)}`}>상세 페이지 보기</Link>}
      </div>
    </aside>
  );
}
