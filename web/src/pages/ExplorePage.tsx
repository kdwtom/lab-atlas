import { useMemo, useState } from 'react';
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

export default function ExplorePage({ mode }: { mode: Mode }) {
  const atlas = useAtlas();
  const ex = useExplore();
  const navigate = useNavigate();
  const mobile = useMedia('(max-width: 768px)');
  const [hover, setHover] = useState<Lab | null>(null);
  const [hoverEdge, setHoverEdge] = useState<Edge | null>(null);
  const [selected, setSelected] = useState<Lab | null>(null);

  const filtered = useMemo(() => atlas.labs.filter((l) => passesFilters(l, ex)), [atlas.labs, ex]);
  const matched = useMemo(
    () => (ex.query.trim() ? new Set(filtered.filter((l) => matchesQuery(l, ex.query)).map((l) => l.id)) : null),
    [filtered, ex.query],
  );
  const edges = useMemo(() => atlas.edges.filter((e) => e.type === ex.edgeMode), [atlas.edges, ex.edgeMode]);
  const listRows = matched ? filtered.filter((l) => matched.has(l.id)) : filtered;

  // desktop: click opens the lab page; mobile: tap previews in the bottom sheet first
  const select = (lab: Lab) => {
    if (mobile) setSelected(lab);
    else navigate(`/lab/${encodeURIComponent(lab.id)}`);
  };
  // search pick: focus the node in the graph (and preview it), or open the page from the list
  const pick = (lab: Lab) => {
    if (ex.view === 'list') navigate(`/lab/${encodeURIComponent(lab.id)}`);
    else setSelected(lab);
  };

  const clusterName = (id: number | null) => (id === null ? '' : atlas.clusterById.get(id)?.label_ko ?? '');
  const panelLab = mobile ? selected : hover ?? selected;

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
            sheet={mobile}
            clusterName={clusterName}
            onHover={setHover}
            onEdgeHover={setHoverEdge}
            onSelect={select}
          />
          <LabPanel lab={panelLab} edge={mobile ? null : hoverEdge} mode={mode} sheet={mobile}
                    onClose={() => setSelected(null)} />
        </div>
      ) : (
        <ListView labs={listRows} mode={mode} />
      )}
    </div>
  );
}
