import { useState } from 'react';
import type { Lab } from '../types/data';
import { useAtlas } from '../data/DataContext';
import { useExplore } from '../data/explore';
import { UNIV_LABEL, UNIV_ORDER } from '../lib/format';
import { FIELD_LABEL, FIELD_ORDER, fieldColor, type Mode } from '../lib/palette';
import SearchBox from './SearchBox';

const EDGE_NOTE = {
  similarity: '주제 유사도(상위 5개 이웃 + 다른 분야 최근접 1곳)',
  coauthor: '공동 논문(굵을수록 많음)',
  cross: '다른 분야 연구실 사이의 유사도·공동 논문',
} as const;

type Section = 'univ' | 'field' | 'cluster';
const SECTION_LABEL: Record<Section, string> = { univ: '대학', field: '분야', cluster: '클러스터' };
const SECTION_KEY = 'lab-atlas:filter-rows';

/** Open filter rows, remembered per browser. Clusters start closed (the map labels them), and phones start with all closed. */
function loadOpen(): Set<Section> {
  try {
    const saved = JSON.parse(localStorage.getItem(SECTION_KEY) ?? 'null');
    if (Array.isArray(saved)) return new Set(saved.filter((s): s is Section => s in SECTION_LABEL));
  } catch { /* storage may be blocked; fall through to the default */ }
  return new Set(window.matchMedia?.('(max-width: 768px)').matches ? [] : ['univ', 'field']);
}

interface Props {
  mode: Mode;
  shown: number;
  onPick: (lab: Lab) => void;
}

export default function Toolbar({ mode, shown, onPick }: Props) {
  const atlas = useAtlas();
  const ex = useExplore();
  const filtered = ex.univs.size > 0 || ex.fields.size > 0 || ex.clusters.size > 0 || ex.query.trim() !== '';
  const fieldCount = (f: string) => atlas.labs.filter((l) => (l.disciplines as string[]).includes(f)).length;
  const [open, setOpen] = useState(loadOpen);
  const toggle = (s: Section) => {
    const next = new Set(open);
    if (!next.delete(s)) next.add(s);
    setOpen(next);
    try { localStorage.setItem(SECTION_KEY, JSON.stringify([...next])); } catch { /* the choice just is not remembered */ }
  };
  const active: Record<Section, number> = { univ: ex.univs.size, field: ex.fields.size, cluster: ex.clusters.size };

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
            <button aria-pressed={ex.edgeMode === 'cross'} onClick={() => ex.set({ edgeMode: 'cross' })}
                    title="서로 다른 분야 연구실 사이의 유사도·공동연구 연결만 표시">
              학제간 연결
            </button>
          </div>
        )}
        <span className="count" aria-live="polite">{atlas.labs.length}개 중 {shown}개</span>
        <div className="folds" role="group" aria-label="필터 줄 보이기">
          {(Object.keys(SECTION_LABEL) as Section[]).map((s) => (
            <button key={s} className="fold" aria-expanded={open.has(s)} aria-controls={`filter-${s}`} onClick={() => toggle(s)}>
              <span className="fold-mark" aria-hidden="true" />
              {SECTION_LABEL[s]}
              {active[s] > 0 && <span className="fold-count">{active[s]}개 선택</span>}
            </button>
          ))}
        </div>
        {filtered && <button className="link-btn" onClick={ex.reset}>필터 초기화</button>}
      </div>

      <div id="filter-univ" hidden={!open.has('univ')} className="toolbar-row chips" role="group" aria-label="대학 필터">
        <span className="chips-label">대학</span>
        {UNIV_ORDER.map((u) => (
          <button key={u} className="chip" aria-pressed={ex.univs.has(u)} onClick={() => ex.toggleUniv(u)}>
            {UNIV_LABEL[u]}
          </button>
        ))}
      </div>

      <div id="filter-field" hidden={!open.has('field')} className="toolbar-row chips" role="group" aria-label="분야 범례 및 필터">
        <span className="chips-label">분야</span>
        {FIELD_ORDER.filter((f) => fieldCount(f) > 0).map((f) => (
          <button key={f} className="chip" aria-pressed={ex.fields.has(f)} onClick={() => ex.toggleField(f)}>
            <span className="dot" style={{ background: fieldColor(f, mode) }} aria-hidden="true" />
            {FIELD_LABEL[f]} <span className="muted">{fieldCount(f)}</span>
          </button>
        ))}
      </div>

      <div id="filter-cluster" hidden={!open.has('cluster')} className="toolbar-row chips" role="group" aria-label="클러스터 필터">
        <span className="chips-label">클러스터</span>
        {atlas.clusters.map((c) => (
          <button key={c.id} className="chip" aria-pressed={ex.clusters.has(c.id)} onClick={() => ex.toggleCluster(c.id)}
                  title={c.keywords.slice(0, 3).join(', ')}>
            {c.label_ko} <span className="muted">{c.size}</span>
          </button>
        ))}
      </div>
      {ex.view === 'graph' && (
        <p className="legend-note">
          노드 색 = 분야 · 크기 = 최근 5년 논문 수(로그) · 선 = {EDGE_NOTE[ex.edgeMode]}
        </p>
      )}
    </div>
  );
}
