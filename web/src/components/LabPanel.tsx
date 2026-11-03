import { Link } from 'react-router-dom';
import type { Edge, Lab, Paper } from '../types/data';
import { useAtlas } from '../data/DataContext';
import { NA, affiliation, doiHref, introText, neighbourCaution, piName, similarityBand } from '../lib/format';
import StarButton from './StarButton';
import { FIELD_LABEL, fieldColor, type Mode } from '../lib/palette';

interface Props {
  lab: Lab | null;
  edge: Edge | null;
  mode: Mode;
  sheet: boolean;          // rendered as a mobile bottom sheet
  pinned?: boolean;        // desktop: the lab was pinned by a click
  onClose?: () => void;
}

export function ClusterChip({ id }: { id: number | null }) {
  const atlas = useAtlas();
  const c = id === null ? undefined : atlas.clusterById.get(id);
  return <span className="cluster-chip" title="연구 주제 클러스터">{c ? c.label_ko : NA}</span>;
}

export function FieldChips({ lab, mode }: { lab: Lab; mode: Mode }) {
  return (
    <>
      {lab.disciplines.map((d) => (
        <span key={d} className="cluster-chip" title="학과 분야">
          <span className="dot" style={{ background: fieldColor(d, mode) }} aria-hidden="true" />
          {FIELD_LABEL[d]}
        </span>
      ))}
    </>
  );
}

function PaperLink({ paper }: { paper: Paper }) {
  return (
    <>
      <a href={doiHref(paper.doi) ?? paper.openalex_url} target="_blank" rel="noreferrer">{paper.title}</a>
      {' '}<span className="muted">({paper.year})</span>
    </>
  );
}

function EdgeInfo({ edge, onClose }: { edge: Edge; onClose?: () => void }) {
  const atlas = useAtlas();
  const a = atlas.labById.get(edge.source);
  const b = atlas.labById.get(edge.target);
  const nameA = a ? piName(a) : edge.source;
  const nameB = b ? piName(b) : edge.target;
  const caution = a && b && edge.type === 'similarity' ? neighbourCaution(a, b) : null;
  const pairs = (edge.paper_pairs ?? []).flatMap(([x, y]) => {
    const pa = atlas.paperById.get(x);
    const pb = atlas.paperById.get(y);
    return pa && pb ? [{ pa, pb }] : [];
  });
  const shared = edge.paper_ids.flatMap((id) => atlas.paperById.get(id) ?? []);
  return (
    <div className="panel-body">
      {onClose && (
        <p className="pin-bar">
          <span>선택한 연결</span>
          <button type="button" onClick={onClose}>선택 해제</button>
        </p>
      )}
      <p className="eyebrow">{edge.type === 'similarity' ? '연구 주제 유사도' : '공동연구'}</p>
      <h2 className="panel-title">{nameA} ↔ {nameB}</h2>
      {edge.type === 'similarity' ? (
        <>
          {a && b && <p><strong>{similarityBand(atlas.meta, edge.weight, a, b)}</strong></p>}
          {caution && <p className="caution">{caution}</p>}
          <h3>공통 주제</h3>
          {edge.reasons.length ? (
            <ul className="tags">{edge.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
          ) : <p className="muted">{NA}</p>}
          <h3>내용이 가까운 논문</h3>
          {pairs.length ? (
            <>
              <ol className="paper-pairs">
                {pairs.map(({ pa, pb }) => (
                  <li key={`${pa.id}-${pb.id}`}>
                    <div><span className="pair-name">{nameA}</span><PaperLink paper={pa} /></div>
                    <div><span className="pair-name">{nameB}</span><PaperLink paper={pb} /></div>
                  </li>
                ))}
              </ol>
              <p className="muted small">유사도 계산에 쓴 논문 중 벡터가 가장 가까운 쌍입니다. 제목을 보고 정말 비슷한지 직접 판단해 보세요.</p>
            </>
          ) : <p className="muted">{NA}</p>}
        </>
      ) : (
        <>
          <p>두 PI가 함께 저자로 참여한 논문 <strong>{edge.weight}편</strong></p>
          {shared.length > 0 && (
            <ul className="paper-list">{shared.map((p) => <li key={p.id}><PaperLink paper={p} /></li>)}</ul>
          )}
        </>
      )}
    </div>
  );
}

export default function LabPanel({ lab, edge, mode, sheet, pinned, onClose }: Props) {
  const atlas = useAtlas();
  if (!lab && edge) {
    return (
      <aside key={`${edge.source}-${edge.target}-${edge.type}`} className={sheet ? 'panel sheet' : 'panel'} aria-live="polite">
        <EdgeInfo edge={edge} onClose={onClose} />
      </aside>
    );
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
            국내 6개 대학 생명과학·화학·물리·수학·컴퓨터 학과의 연구실 {m.counts.labs}곳을 최근 논문의 내용으로
            배치했습니다. 가까이 있거나 선으로 이어진 연구실일수록 연구 주제가 비슷하고, 색은 분야를 나타냅니다.
          </p>
          <ul className="hint">
            <li>노드에 마우스를 올리면 연구실 정보가 여기에 표시되고, 마우스를 옮겨도 남아 있어 스크롤할 수 있습니다.</li>
            <li>노드를 클릭하면 이 창에 고정되고, 한 번 더 클릭하면 상세 페이지로 이동합니다. 빈 곳 클릭이나 Esc로 고정을 풉니다.</li>
            <li>축소하면 일부 연구실만 크게 보이고 나머지는 작은 점으로 남습니다. 확대할수록 연구실과 이름이 늘어나고, 클러스터 이름을 누르면 그 묶음으로 들어갑니다. 표시 순서는 평가가 아닙니다.</li>
            <li>선을 클릭하면 두 연구실의 공통 주제와 내용이 가까운 논문을 볼 수 있습니다.</li>
            <li>☆ 담기를 누르면 <Link to="/shortlist">내 후보</Link>에서 비슷한 연구실 추천과 비교표를 볼 수 있습니다.</li>
          </ul>
          <p className="muted small">
            {m.window_years[0]}–{m.window_years[1]}년 논문 기준(분야별로 다름) ·{' '}
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
        <div className="chip-row"><FieldChips lab={lab} mode={mode} /><ClusterChip id={lab.cluster_id} /></div>
        <StarButton id={lab.id} name={piName(lab)} />
        {sheet && <Link className="btn btn-top" to={`/lab/${encodeURIComponent(lab.id)}`}>상세 페이지 보기</Link>}
        <h3>핵심 키워드</h3>
        {lab.keywords.length ? <ul className="tags">{lab.keywords.slice(0, 5).map((k) => <li key={k}>{k}</li>)}</ul>
          : <p className="muted">{NA}</p>}
        <h3>연구실 소개</h3>
        <p className={lab.intro_ko ? '' : 'muted'}>{introText(lab)}</p>
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
