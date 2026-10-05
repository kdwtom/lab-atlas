import { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D, { type ForceGraphMethods, type LinkObject, type NodeObject } from 'react-force-graph-2d';
import type { Edge, Lab } from '../types/data';
import { CHROME, clusterColor, type Mode } from '../lib/palette';
import { piName } from '../lib/format';

interface NodeData {
  id: string;
  lab: Lab;
  r: number;
  ax: number; // UMAP anchor
  ay: number;
}
type GNode = NodeObject<NodeData>;
type GLink = LinkObject<NodeData, { edge: Edge }>;

const SCALE = 420;          // UMAP [-1, 1] -> canvas units
const LABEL_ZOOM = 1.6;     // PI names appear above this zoom
const CLUSTER_LABEL_ZOOM = 2.2;

export function nodeRadius(paperCount: number): number {
  return 2.4 + 1.7 * Math.log(1 + paperCount); // log scale: 5 papers ≈ 5.4, 60 ≈ 9.4
}

interface Props {
  labs: Lab[];                       // labs passing the filters
  edges: Edge[];                     // edges of the current mode
  mode: Mode;
  matched: Set<string> | null;       // search matches (null = no query)
  focusId: string | null;            // selected lab (search result / tap)
  sheet: boolean;                    // mobile layout: a bottom sheet covers the lower half
  clusterName: (id: number | null) => string;
  onHover: (lab: Lab | null) => void;
  onEdgeHover: (edge: Edge | null) => void;
  onSelect: (lab: Lab) => void;
}

function endpointId(v: GLink['source']): string {
  return typeof v === 'object' && v ? String(v.id) : String(v);
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
}

export default function GraphView({ labs, edges, mode, matched, focusId, sheet, clusterName, onHover, onEdgeHover, onSelect }: Props) {
  const fg = useRef<ForceGraphMethods<GNode, GLink> | undefined>(undefined);
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 800, h: 600 });
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [hoverLink, setHoverLink] = useState<GLink | null>(null);
  const nodeCache = useRef(new Map<string, GNode>());
  const fitted = useRef(false);

  // resize with the container
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setSize({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // node objects are reused across filter changes so positions persist
  const data = useMemo(() => {
    const nodes: GNode[] = labs.map((lab) => {
      let n = nodeCache.current.get(lab.id);
      if (!n) {
        const ax = (lab.x ?? 0) * SCALE;
        const ay = (lab.y ?? 0) * SCALE;
        n = { id: lab.id, lab, r: nodeRadius(lab.paper_count_5y), ax, ay, x: ax, y: ay };
        nodeCache.current.set(lab.id, n);
      }
      return n;
    });
    const ids = new Set(labs.map((l) => l.id));
    const links: GLink[] = edges
      .filter((e) => ids.has(e.source) && ids.has(e.target))
      .map((e) => ({ source: e.source, target: e.target, edge: e }));
    return { nodes, links };
  }, [labs, edges]);

  const neighborIds = useMemo(() => {
    const m = new Map<string, Set<string>>();
    for (const l of data.links) {
      const a = endpointId(l.source);
      const b = endpointId(l.target);
      if (!m.has(a)) m.set(a, new Set());
      if (!m.has(b)) m.set(b, new Set());
      m.get(a)!.add(b);
      m.get(b)!.add(a);
    }
    return m;
  }, [data]);

  // forces: weak anchor to UMAP coordinates + weak pull towards the cluster centroid
  useEffect(() => {
    const g = fg.current;
    if (!g) return;
    let nodes: GNode[] = [];
    const anchor = Object.assign((alpha: number) => {
      for (const n of nodes) {
        n.vx = (n.vx ?? 0) + (n.ax - (n.x ?? 0)) * 0.03 * alpha;
        n.vy = (n.vy ?? 0) + (n.ay - (n.y ?? 0)) * 0.03 * alpha;
      }
    }, { initialize: (ns: GNode[]) => { nodes = ns; } });
    let cnodes: GNode[] = [];
    const cluster = Object.assign((alpha: number) => {
      const c = new Map<number, { x: number; y: number; n: number }>();
      for (const n of cnodes) {
        const k = n.lab.cluster_id ?? -1;
        const s = c.get(k) ?? { x: 0, y: 0, n: 0 };
        s.x += n.x ?? 0;
        s.y += n.y ?? 0;
        s.n += 1;
        c.set(k, s);
      }
      for (const n of cnodes) {
        const s = c.get(n.lab.cluster_id ?? -1)!;
        n.vx = (n.vx ?? 0) + (s.x / s.n - (n.x ?? 0)) * 0.05 * alpha;
        n.vy = (n.vy ?? 0) + (s.y / s.n - (n.y ?? 0)) * 0.05 * alpha;
      }
    }, { initialize: (ns: GNode[]) => { cnodes = ns; } });
    g.d3Force('anchor', anchor);
    g.d3Force('cluster', cluster);
    g.d3Force('center', null);
    const charge = g.d3Force('charge');
    charge?.strength?.(-45);
    const link = g.d3Force('link');
    link?.distance?.(38);
    link?.strength?.((l: GLink) => (l.edge.type === 'coauthor' ? 0.05 : 0.12));
    g.d3ReheatSimulation();
  }, [data]);

  // read-only hook for the automated screenshot/performance script (scripts/check.mjs)
  useEffect(() => {
    const w = window as unknown as { __labAtlas?: object };
    w.__labAtlas = {
      nodeScreen: (id: string) => {
        const n = nodeCache.current.get(id);
        const r = box.current?.getBoundingClientRect();
        if (!n || !r || !fg.current || n.x === undefined || n.y === undefined) return null;
        const p = fg.current.graph2ScreenCoords(n.x, n.y);
        return { x: r.left + p.x, y: r.top + p.y };
      },
      ids: () => data.nodes.map((n) => n.id),
    };
  }, [data]);

  // initial view: fit the UMAP layout to the canvas immediately (zoomToFit runs again when the engine stops)
  useEffect(() => {
    const g = fg.current;
    if (!g || fitted.current || data.nodes.length === 0 || size.w < 50) return;
    const xs = data.nodes.map((n) => n.ax);
    const ys = data.nodes.map((n) => n.ay);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    g.centerAt((x0 + x1) / 2, (y0 + y1) / 2, 0);
    g.zoom(Math.min(size.w / (x1 - x0 + 120), size.h / (y1 - y0 + 120)), 0);
  }, [data, size]);

  // centre on the selected lab (search result / tap); with the mobile bottom sheet open, place the node
  // in the middle of the visible upper half instead of behind the sheet
  useEffect(() => {
    if (!focusId) return;
    const n = nodeCache.current.get(focusId);
    if (n && n.x !== undefined && n.y !== undefined) {
      const zoom = sheet ? 1.8 : 2.4;
      const dy = sheet ? (size.h * 0.25) / zoom : 0;
      fg.current?.centerAt(n.x, n.y + dy, 600);
      fg.current?.zoom(zoom, 600);
    }
  }, [focusId]); // eslint-disable-line react-hooks/exhaustive-deps -- re-centre only when the focus changes

  const chrome = CHROME[mode];
  const activeId = hoverId ?? focusId;
  const activeSet = activeId ? neighborIds.get(activeId) ?? new Set<string>() : null;
  const hoverLinkEnds = hoverLink ? [endpointId(hoverLink.source), endpointId(hoverLink.target)] : null;

  const isLit = (id: string): boolean => {
    if (hoverLinkEnds) return hoverLinkEnds.includes(id);
    if (activeId) return id === activeId || activeSet!.has(id);
    if (matched) return matched.has(id);
    return true;
  };

  const paintNode = (node: GNode, ctx: CanvasRenderingContext2D, scale: number) => {
    const lit = isLit(node.id);
    const x = node.x ?? 0;
    const y = node.y ?? 0;
    ctx.globalAlpha = lit ? 1 : 0.14;
    ctx.beginPath();
    ctx.arc(x, y, node.r, 0, 2 * Math.PI);
    ctx.fillStyle = clusterColor(node.lab.cluster_id, mode);
    ctx.fill();
    // 2px surface ring separates overlapping marks; focused node gets an ink ring
    ctx.lineWidth = (node.id === activeId ? 2.4 : 1.2) / scale;
    ctx.strokeStyle = node.id === activeId ? chrome.ink : chrome.surface;
    ctx.stroke();
    const showLabel = scale >= LABEL_ZOOM || node.id === activeId || (activeSet?.has(node.id) ?? false);
    if (showLabel && lit) {
      const fontSize = Math.max(11 / scale, 2.2);
      ctx.font = `${fontSize}px system-ui, -apple-system, "Segoe UI", sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      const text = piName(node.lab);
      const ty = y + node.r + 2 / scale;
      ctx.lineWidth = 3 / scale;
      ctx.strokeStyle = chrome.surface;
      ctx.strokeText(text, x, ty);
      ctx.fillStyle = chrome.ink;
      ctx.fillText(text, x, ty);
    }
    ctx.globalAlpha = 1;
  };

  const paintPointer = (node: GNode, color: string, ctx: CanvasRenderingContext2D) => {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(node.x ?? 0, node.y ?? 0, node.r + 3, 0, 2 * Math.PI); // hit target larger than the mark
    ctx.fill();
  };

  // direct cluster labels at centroids (identity never by colour alone)
  const paintClusterLabels = (ctx: CanvasRenderingContext2D, scale: number) => {
    if (scale >= CLUSTER_LABEL_ZOOM || activeId) return;
    const c = new Map<number, { x: number; y: number; n: number }>();
    for (const n of data.nodes) {
      if (n.lab.cluster_id === null) continue;
      const s = c.get(n.lab.cluster_id) ?? { x: 0, y: 0, n: 0 };
      s.x += n.x ?? 0;
      s.y += n.y ?? 0;
      s.n += 1;
      c.set(n.lab.cluster_id, s);
    }
    const fontSize = 13 / scale;
    ctx.font = `600 ${fontSize}px system-ui, -apple-system, "Segoe UI", sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    for (const [id, s] of c) {
      if (s.n < 2) continue;
      const text = clusterName(id);
      const x = s.x / s.n;
      const y = s.y / s.n;
      ctx.lineWidth = 4 / scale;
      ctx.strokeStyle = chrome.surface;
      ctx.globalAlpha = 0.92;
      ctx.strokeText(text, x, y);
      ctx.fillStyle = chrome.inkSecondary;
      ctx.fillText(text, x, y);
      ctx.globalAlpha = 1;
    }
  };

  const linkColor = (l: GLink) => {
    const a = endpointId(l.source);
    const b = endpointId(l.target);
    const hot = hoverLink === l || (activeId !== null && (a === activeId || b === activeId));
    const dim = (activeId !== null || hoverLink !== null) && !hot;
    const alpha = hot ? 0.75 : dim ? 0.04 : l.edge.type === 'coauthor' ? 0.32 : 0.18;
    return `rgba(${chrome.link},${alpha})`;
  };

  const linkWidth = (l: GLink) => {
    const base = l.edge.type === 'coauthor' ? 0.6 + Math.log2(1 + l.edge.weight) * 0.7 : 0.8;
    return hoverLink === l ? base + 1.5 : base;
  };

  const linkLabel = (l: GLink) => {
    const e = l.edge;
    const head = e.type === 'similarity'
      ? `연구 주제 유사도 ${e.weight.toFixed(3)}`
      : `공동 논문 ${e.weight}편`;
    const body = e.type === 'similarity'
      ? (e.reasons.length ? `연결 이유: ${e.reasons.map(escapeHtml).join(' · ')}` : '연결 이유: 정보 없음')
      : '';
    return `<div class="tip"><strong>${head}</strong>${body ? `<br/>${body}` : ''}</div>`;
  };

  return (
    <div ref={box} className="graph" role="img"
         aria-label="연구실 관계 그래프. 키보드로는 목록 보기와 검색을 사용하세요.">
      <ForceGraph2D<NodeData, { edge: Edge }>
        ref={fg}
        width={size.w}
        height={size.h}
        graphData={data}
        backgroundColor={chrome.surface}
        nodeRelSize={1}
        nodeCanvasObject={paintNode}
        nodePointerAreaPaint={paintPointer}
        nodeLabel={() => ''}
        linkColor={linkColor}
        linkWidth={linkWidth}
        linkLabel={linkLabel}
        linkHoverPrecision={6}
        onRenderFramePost={paintClusterLabels}
        onNodeHover={(n) => {
          setHoverId(n ? String(n.id) : null);
          onHover(n ? n.lab : null);
          if (box.current) box.current.style.cursor = n ? 'pointer' : 'default';
        }}
        onLinkHover={(l) => {
          setHoverLink(l ?? null);
          onEdgeHover(l ? l.edge : null);
        }}
        onNodeClick={(n) => onSelect(n.lab)}
        cooldownTicks={180}
        d3AlphaDecay={0.035}
        d3VelocityDecay={0.35}
        onEngineStop={() => {
          if (!fitted.current) {
            fitted.current = true;
            fg.current?.zoomToFit(500, 40);
          }
        }}
      />
    </div>
  );
}
