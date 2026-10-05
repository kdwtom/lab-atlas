import type { Lab } from '../types/data';
import { useAtlas } from '../data/DataContext';
import { useExplore } from '../data/explore';
import { UNIV_LABEL, UNIV_ORDER } from '../lib/format';
import { clusterColor, type Mode } from '../lib/palette';
import SearchBox from './SearchBox';

interface Props {
  mode: Mode;
  shown: number;
  onPick: (lab: Lab) => void;
}

export default function Toolbar({ mode, shown, onPick }: Props) {
  const atlas = useAtlas();
  const ex = useExplore();
  const filtered = ex.univs.size > 0 || ex.clusters.size > 0 || ex.query.trim() !== '';

  return (
    <div className="toolbar">
      <div className="toolbar-row">
        <SearchBox labs={atlas.labs} query={ex.query} onQuery={(q) => ex.set({ query: q })} onPick={onPick} />
        <div className="seg" role="group" aria-label="보기 방식">
          <button aria-pressed={ex.view === 'graph'} onClick={() => ex.set({ view: 'graph' })}>그래프</button>
          <button aria-pressed={ex.view === 'list'} onClick={() => ex.set({ view: 'list' })}>목록</button>
        </div>
        {ex.view === 'graph' && (
          <div className="seg" role="group" aria-label="연결선 종류">
            <button aria-pressed={ex.edgeMode === 'similarity'} onClick={() => ex.set({ edgeMode: 'similarity' })}>
              연구 주제 유사도
            </button>
            <button aria-pressed={ex.edgeMode === 'coauthor'} onClick={() => ex.set({ edgeMode: 'coauthor' })}>
              공동연구
            </button>
          </div>
        )}
        <span className="count" aria-live="polite">{atlas.labs.length}개 중 {shown}개</span>
        {filtered && <button className="link-btn" onClick={ex.reset}>필터 초기화</button>}
      </div>

      <div className="toolbar-row chips" role="group" aria-label="대학 필터">
        <span className="chips-label">대학</span>
        {UNIV_ORDER.map((u) => (
          <button key={u} className="chip" aria-pressed={ex.univs.has(u)} onClick={() => ex.toggleUniv(u)}>
            {UNIV_LABEL[u]}
          </button>
        ))}
      </div>

      <div className="toolbar-row chips legend" role="group" aria-label="클러스터 범례 및 필터">
        <span className="chips-label">클러스터</span>
        {atlas.clusters.map((c) => (
          <button key={c.id} className="chip" aria-pressed={ex.clusters.has(c.id)} onClick={() => ex.toggleCluster(c.id)}
                  title={c.keywords.slice(0, 3).join(', ')}>
            <span className="dot" style={{ background: clusterColor(c.id, mode) }} aria-hidden="true" />
            {c.label_ko} <span className="muted">{c.size}</span>
          </button>
        ))}
        {ex.view === 'graph' && (
          <span className="legend-note">
            노드 크기 = 최근 5년 논문 수(로그) · 선 = {ex.edgeMode === 'similarity' ? '주제 유사도(상위 5개 이웃)' : '공동 논문(굵을수록 많음)'}
          </span>
        )}
      </div>
    </div>
  );
}
