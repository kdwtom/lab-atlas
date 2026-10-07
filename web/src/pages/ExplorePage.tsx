import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Edge, Lab } from '../types/data';
import { useAtlas } from '../data/DataContext';
import { matchesQuery, passesFilters, useExplore } from '../data/explore';
import { useMedia } from '../lib/useMedia';
import type { Mode } from '../lib/palette';
import GraphView from '../components/GraphView';
import LabPanel from '../components/LabPanel';
import ListView from '../components/ListView';
import Toolbar from '../components/Toolbar';

const HOVER_INTENT_MS = 150;

export default function ExplorePage({ mode }: { mode: Mode }) {
  const atlas = useAtlas();
  const ex = useExplore();
  const navigate = useNavigate();
  const mobile = useMedia('(max-width: 768px)');
  // hover preview stays after the pointer leaves the node, so it can be moved onto the panel and scrolled
  const [hover, setHover] = useState<Lab | null>(null);
  const [hoverEdge, setHoverEdge] = useState<Edge | null>(null);
  // a node only takes over the panel after the pointer rests on it briefly, so passing over other
  // nodes on the way to the panel does not replace the preview
  const hoverTimer = useRef<number | undefined>(undefined);
  const onNodeHover = (lab: Lab | null) => {
    window.clearTimeout(hoverTimer.current);
    if (lab) hoverTimer.current = window.setTimeout(() => setHover(lab), HOVER_INTENT_MS);
  };
  useEffect(() => () => window.clearTimeout(hoverTimer.current), []);
  // desktop: lab pinned by a click (hover no longer replaces it); mobile: lab shown in the bottom sheet
  const [selected, setSelected] = useState<Lab | null>(null);
  const [center, setCenter] = useState<{ id: string } | null>(null);

  const filtered = useMemo(() => atlas.labs.filter((l) => passesFilters(l, ex)), [atlas.labs, ex]);
  const matched = useMemo(
    () => (ex.query.trim() ? new Set(filtered.filter((l) => matchesQuery(l, ex.query)).map((l) => l.id)) : null),
    [filtered, ex.query],
  );
  const edges = useMemo(() => atlas.edges.filter((e) => e.type === ex.edgeMode), [atlas.edges, ex.edgeMode]);
  const listRows = matched ? filtered.filter((l) => matched.has(l.id)) : filtered;

  // desktop: click pins the lab in the panel, a second click opens its page; mobile: tap previews in the sheet
  const select = (lab: Lab) => {
    if (mobile) {
      setSelected(lab);
      setCenter({ id: lab.id });
    } else if (selected?.id === lab.id) {
      navigate(`/lab/${encodeURIComponent(lab.id)}`);
    } else {
      setSelected(lab);
    }
  };
  // search pick: focus the node in the graph (and preview it), or open the page from the list
  const pick = (lab: Lab) => {
    if (ex.view === 'list') navigate(`/lab/${encodeURIComponent(lab.id)}`);
    else {
      setSelected(lab);
      setCenter({ id: lab.id });
    }
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setSelected(null); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const clusterName = (id: number | null) => (id === null ? '' : atlas.clusterById.get(id)?.label_ko ?? '');
  const hoverLab = hover && filtered.includes(hover) ? hover : null;
  // a hovered edge shows briefly; once the pointer leaves it the last hovered lab comes back
  const panelLab = mobile || selected ? selected : hoverEdge ? null : hoverLab;

  return (
    <div className="explore">
      {atlas.dummy && (
        <p className="banner" role="status">성능 확인용 더미 데이터 {atlas.labs.length}개 노드를 표시 중입니다 (실제 연구실 아님).</p>
      )}
      <Toolbar mode={mode} shown={ex.view === 'list' ? listRows.length : filtered.length} onPick={pick} />
      {ex.view === 'graph' ? (
        <div className="stage">
          <GraphView
            labs={filtered}
            edges={edges}
            mode={mode}
            matched={matched}
            focusId={selected?.id ?? null}
            center={center}
            sheet={mobile}
            clusterName={clusterName}
            onHover={onNodeHover}
            onEdgeHover={setHoverEdge}
            onSelect={select}
            onBackgroundClick={() => setSelected(null)}
          />
          <LabPanel lab={panelLab} edge={mobile || selected ? null : hoverEdge} mode={mode} sheet={mobile}
                    pinned={!mobile && selected !== null} onClose={() => setSelected(null)} />
        </div>
      ) : (
        <ListView labs={listRows} mode={mode} />
      )}
    </div>
  );
}
