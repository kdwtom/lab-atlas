import { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D, { type ForceGraphMethods, type LinkObject, type NodeObject } from 'react-force-graph-2d';
import type { Edge, Lab } from '../types/data';
import { CHROME, FIELD_LABEL, FIELD_ORDER, fieldColor, type Mode } from '../lib/palette';
import { detailBudget, detailRanks, placeLabels, wrapLabel, type LabelBox } from '../lib/graphDetail';
import { labTitle, piName } from '../lib/format';

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
// what is named at each zoom (multiples of the fitted zoom): clusters, then sub-clusters, then labs
const CLUSTER_LABEL_ZOOM = 2;  // cluster regions fade out by here
const CLUSTER_NAME_END = 1.7;  // cluster names fade out between 1.3 and here
const SUB_NAME_START = 1.3;    // sub-cluster names fade in from here ...
const SUB_NAME_END = 3.4;      // ... and out by here
const LAB_NAME_ZOOM = 2.2;     // lab names appear from here; a hovered, selected or searched lab is always named
const ALL_LINKS_ZOOM = 1.4;    // similarity lines of ordinary nodes appear at this multiple of the fitted zoom
const DETAIL_KEY = 'lab-atlas:show-all-nodes';
const MIN_NODE_PX = 4.5;       // a drawn lab stays this large on screen however far the map is zoomed out
const LABEL_LINE_PX = 150;     // a long lab name wraps onto more lines instead of being cut

export function nodeRadius(paperCount: number): number {
  return 3.2 + 2.1 * Math.log(1 + paperCount); // log scale: 5 papers ≈ 7.0, 60 ≈ 11.8
}

function loadShowAll(): boolean {
  try { return localStorage.getItem(DETAIL_KEY) === '1'; } catch { return false; }
}

interface Props {
  labs: Lab[];                       // labs passing the filters
  edges: Edge[];                     // edges of the current mode
  mode: Mode;
  matched: Set<string> | null;       // search matches (null = no query)
  focusId: string | null;            // selected (pinned) lab: highlighted with its neighbours
  selectedEdge: Edge | null;         // clicked line: highlighted with its two labs
  center: { id: string } | null;     // centre the view on this lab (new object = new request)
  sheet: boolean;                    // mobile layout: a bottom sheet covers the lower half
  clusterName: (id: number | null) => string;
  subclusterName: (id: number) => string;
  onHover: (lab: Lab | null) => void;
  onEdgeClick: (edge: Edge) => void;
  onSelect: (lab: Lab) => void;
  onBackgroundClick: () => void;
}

function endpointId(v: GLink['source']): string {
  return typeof v === 'object' && v ? String(v.id) : String(v);
}

export default function GraphView({ labs, edges, mode, matched, focusId, selectedEdge, center, sheet, clusterName, subclusterName, onHover, onEdgeClick, onSelect, onBackgroundClick }: Props) {
  const fg = useRef<ForceGraphMethods<GNode, GLink> | undefined>(undefined);
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 800, h: 600 });
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const [hoverLink, setHoverLink] = useState<GLink | null>(null);
  const nodeCache = useRef(new Map<string, GNode>());
  const fitted = useRef(false);
  const fitZoom = useRef(1);                  // zoom at which the whole map fits the canvas
  const zoomNow = useRef(1);
  const zoomTarget = useRef<{ k: number; timer: number } | null>(null);
  const clusterBoxes = useRef<(LabelBox & { id: number; sub: boolean })[]>([]);
  const [showAll, setShowAll] = useState(loadShowAll);
  const [showTrends, setShowTrends] = useState(false); // every lab with a topic-shift signal, at once
  const [visibleCount, setVisibleCount] = useState(0);
  const visibleCountRef = useRef(0);

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

  // which labs stay on the zoomed-out map: within each cluster, most connected first, so every region keeps
  // its share. This is a drawing order, not an evaluation of the labs.
  const ranks = useMemo(() => detailRanks(data.nodes.map((n) => ({
    id: n.id, cluster: n.lab.cluster_id, degree: neighborIds.get(n.id)?.size ?? 0, papers: n.lab.paper_count_5y,
  }))), [data, neighborIds]);
  const hubIds = useMemo(() => new Set([...ranks].filter(([, r]) => r.rank === 0 && r.size >= 2).map(([id]) => id)), [ranks]);
  // labels are tried most important first, so they only need sorting when the labs change
  const labelOrder = useMemo(
    () => [...data.nodes].sort((a, b) => (ranks.get(a.id)?.share ?? 1) - (ranks.get(b.id)?.share ?? 1)),
    [data, ranks],
  );

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
    // keep the (larger) marks from overlapping so each stays clickable; a grid keeps this fast with many labs
    let knodes: GNode[] = [];
    const collide = Object.assign(() => {
      const cell = 2 * Math.max(1, ...knodes.map((n) => n.r)) + 2;
      const grid = new Map<string, GNode[]>();
      for (const a of knodes) {
        const cx = Math.floor((a.x ?? 0) / cell);
        const cy = Math.floor((a.y ?? 0) / cell);
        for (let gx = cx - 1; gx <= cx + 1; gx++) {
          for (let gy = cy - 1; gy <= cy + 1; gy++) {
            for (const b of grid.get(`${gx},${gy}`) ?? []) {
              const dx = (b.x ?? 0) - (a.x ?? 0);
              const dy = (b.y ?? 0) - (a.y ?? 0);
              const min = a.r + b.r + 2;
              const d2 = dx * dx + dy * dy;
              if (d2 >= min * min) continue;
              const d = Math.sqrt(d2) || 0.01;
              const push = ((min - d) / d) * 0.25;
              a.vx = (a.vx ?? 0) - dx * push;
              a.vy = (a.vy ?? 0) - dy * push;
              b.vx = (b.vx ?? 0) + dx * push;
              b.vy = (b.vy ?? 0) + dy * push;
            }
          }
        }
        const key = `${cx},${cy}`;
        const bucket = grid.get(key);
        if (bucket) bucket.push(a);
        else grid.set(key, [a]);
      }
    }, { initialize: (ns: GNode[]) => { knodes = ns; } });
    g.d3Force('anchor', anchor);
    g.d3Force('cluster', cluster);
    g.d3Force('collide', collide);
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
    if (!g || data.nodes.length === 0 || size.w < 50) return;
    const xs = data.nodes.map((n) => n.ax);
    const ys = data.nodes.map((n) => n.ay);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    fitZoom.current = Math.min(size.w / (x1 - x0 + 120), size.h / (y1 - y0 + 120));
    if (fitted.current) return;
    g.centerAt((x0 + x1) / 2, (y0 + y1) / 2, 0);
    g.zoom(fitZoom.current, 0);
  }, [data, size]);

  // centre on a requested lab (search result / mobile tap); with the mobile bottom sheet open, place the
  // node in the middle of the visible upper half instead of behind the sheet
  useEffect(() => {
    if (!center) return;
    const n = nodeCache.current.get(center.id);
    if (n && n.x !== undefined && n.y !== undefined) {
      const zoom = sheet ? 1.8 : 2.4;
      const dy = sheet ? (size.h * 0.25) / zoom : 0;
      fg.current?.centerAt(n.x, n.y + dy, 600);
      fg.current?.zoom(zoom, 600);
    }
  }, [center]); // eslint-disable-line react-hooks/exhaustive-deps -- re-centre only on a new request

  const chrome = CHROME[mode];
  // while a line is selected it stays the subject: hovering a lab does not take over the highlight. A dragged lab stays
  // active for the whole drag, so its arrow and neighbours follow it even when the pointer slips off the node.
  const activeId = selectedEdge ? null : dragId ?? hoverId ?? focusId;
  const activeSet = activeId ? neighborIds.get(activeId) ?? new Set<string>() : null;
  const edgeEnds = selectedEdge ? [selectedEdge.source, selectedEdge.target] : null;

  // relative zoom: 1 = the whole map fits; more labs appear as each one gets more room on screen
  const zoomLevel = () => zoomNow.current / (fitZoom.current || 1);
  const shownShare = () => {
    if (showAll || data.nodes.length === 0) return 1;
    return detailBudget(size.w * size.h, zoomLevel()) / data.nodes.length;
  };
  // the hovered or selected lab's topic shift, if it has one: its destination labs are drawn and lit with it
  const activeLab = activeId ? nodeCache.current.get(activeId)?.lab : undefined;
  const trendFocus = activeLab?.trend?.status === 'shifted' ? activeLab.trend : null;
  const trendTargets = new Set(trendFocus?.toward_lab_ids ?? []);
  const forced = (id: string) => id === activeId || id === focusId || (activeSet?.has(id) ?? false)
    || (edgeEnds?.includes(id) ?? false) || (matched?.has(id) ?? false) || trendTargets.has(id)
    || (showTrends && nodeCache.current.get(id)?.lab.trend?.status === 'shifted');
  const isDrawn = (id: string, share = shownShare()) => {
    const r = ranks.get(id);
    return !r || r.rank === 0 || r.share <= share || forced(id);
  };

  const isLit = (id: string): boolean => {
    if (edgeEnds) return edgeEnds.includes(id);
    if (activeId) return id === activeId || activeSet!.has(id) || trendTargets.has(id);
    if (matched) return matched.has(id);
    return true;
  };

  const paintNode = (node: GNode, ctx: CanvasRenderingContext2D, scale: number) => {
    const lit = isLit(node.id);
    const x = node.x ?? 0;
    const y = node.y ?? 0;
    ctx.globalAlpha = lit ? 1 : 0.14;
    ctx.beginPath();
    ctx.arc(x, y, Math.max(node.r, MIN_NODE_PX / scale), 0, 2 * Math.PI);
    ctx.fillStyle = fieldColor(node.lab.disciplines[0], mode);
    ctx.fill();
    // 2px surface ring separates overlapping marks; focused node gets an ink ring
    ctx.lineWidth = (node.id === activeId ? 2.4 : 1.2) / scale;
    ctx.strokeStyle = node.id === activeId ? chrome.ink : chrome.surface;
    ctx.stroke();
    ctx.globalAlpha = 1;
  };

  const paintPointer = (node: GNode, color: string, ctx: CanvasRenderingContext2D, scale: number) => {
    ctx.fillStyle = color;
    ctx.beginPath();
    // hit target at least ~5 screen px larger than the mark at any zoom
    ctx.arc(node.x ?? 0, node.y ?? 0, Math.max(node.r, MIN_NODE_PX / scale) + Math.max(3, 5 / scale), 0, 2 * Math.PI);
    ctx.fill();
  };

  // before the nodes: soft cluster regions, and the labs not drawn yet as small dots so the density stays visible
  const paintUnderlay = (ctx: CanvasRenderingContext2D, scale: number) => {
    zoomNow.current = scale;
    const level = zoomLevel();
    const share = shownShare();
    const clusters = clusterGeometry();
    const fade = Math.max(0, Math.min(1, (CLUSTER_LABEL_ZOOM - level) / 0.6));
    if (fade > 0 && !activeId) {
      ctx.globalAlpha = 0.5 * fade;
      ctx.fillStyle = chrome.region;
      for (const c of clusters.values()) {
        if (c.n < 2) continue;
        ctx.beginPath();
        ctx.arc(c.x, c.y, c.radius, 0, 2 * Math.PI);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
    }
    ctx.fillStyle = chrome.inkSecondary;
    ctx.globalAlpha = activeId || matched ? 0.1 : 0.4;
    const dot = 1.4 / scale;
    let drawn = 0;
    for (const n of data.nodes) {
      if (isDrawn(n.id, share)) { drawn += 1; continue; }
      ctx.beginPath();
      ctx.arc(n.x ?? 0, n.y ?? 0, dot, 0, 2 * Math.PI);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    if (drawn !== visibleCountRef.current) {
      visibleCountRef.current = drawn;
      setVisibleCount(drawn);
    }
  };

  const clusterGeometry = (sub = false) => {
    const key = (n: GNode) => (sub ? n.lab.subcluster_id ?? null : n.lab.cluster_id);
    const c = new Map<number, { x: number; y: number; n: number; radius: number }>();
    for (const n of data.nodes) {
      const k = key(n);
      if (k === null) continue;
      const s = c.get(k) ?? { x: 0, y: 0, n: 0, radius: 0 };
      s.x += n.x ?? 0;
      s.y += n.y ?? 0;
      s.n += 1;
      c.set(k, s);
    }
    for (const s of c.values()) {
      s.x /= s.n;
      s.y /= s.n;
    }
    const spread = new Map<number, number>();
    for (const n of data.nodes) {
      const k = key(n);
      if (k === null) continue;
      const s = c.get(k)!;
      spread.set(k, (spread.get(k) ?? 0) + Math.hypot((n.x ?? 0) - s.x, (n.y ?? 0) - s.y));
    }
    for (const [id, s] of c) s.radius = (spread.get(id)! / s.n) * 1.5 + 14; // covers most of the cluster, not its outliers
    return c;
  };

  // topic shift: from where the lab's 2022-23 papers would sit on the map to where its 2025-26 papers sit. Map distances
  // compress the change, so the arrow is kept long enough to read; a tiny projected move takes the direction of the
  // labs the recent papers came closer to.
  const trendArrow = (n: GNode, scale: number) => {
    const t = n.lab.trend;
    if (!t || t.status !== 'shifted' || n.x === undefined || n.y === undefined) return null;
    const lx = n.lab.x ?? 0;
    const ly = n.lab.y ?? 0;
    // the arrow always starts at the centre of the lab's own node (read every frame, so it follows a drag); only its
    // direction comes from the two periods' map positions
    let dx = t.early_xy && t.recent_xy ? (t.recent_xy[0] - t.early_xy[0]) * SCALE : 0;
    let dy = t.early_xy && t.recent_xy ? (t.recent_xy[1] - t.early_xy[1]) * SCALE : 0;
    if (Math.hypot(dx, dy) < 8 && t.toward_xy) {
      dx = (t.toward_xy[0] - lx) * SCALE;
      dy = (t.toward_xy[1] - ly) * SCALE;
    }
    const len = Math.hypot(dx, dy);
    if (len < 1e-6) return null;
    const r = Math.max(n.r, MIN_NODE_PX / scale);
    const L = r + Math.max(Math.min(len, 160 / scale), 70 / scale);
    return { x0: n.x, y0: n.y, x1: n.x + (dx / len) * L, y1: n.y + (dy / len) * L, ux: dx / len, uy: dy / len };
  };

  const paintTrend = (ctx: CanvasRenderingContext2D, scale: number) => {
    const focus = trendFocus && activeId ? nodeCache.current.get(activeId) : undefined;
    const list = showTrends && !focus
      ? data.nodes.filter((n) => n.lab.trend?.status === 'shifted')
      : focus ? [focus] : [];
    if (list.length === 0) return;
    const one = list.length === 1;
    ctx.save();
    // destination labs: a ring, so the arrow's meaning ("came closer to these") is visible on the map
    if (focus) {
      ctx.strokeStyle = chrome.ink;
      ctx.lineWidth = 1.6 / scale;
      ctx.setLineDash([3 / scale, 3 / scale]);
      for (const id of trendTargets) {
        const m = nodeCache.current.get(id);
        if (!m || m.x === undefined || m.y === undefined) continue;
        ctx.beginPath();
        ctx.arc(m.x, m.y, Math.max(m.r, MIN_NODE_PX / scale) + 4 / scale, 0, 2 * Math.PI);
        ctx.stroke();
      }
      ctx.setLineDash([]);
    }
    const label = (text: string, x: number, y: number, bold: boolean) => {
      ctx.font = `${bold ? 700 : 600} ${12 / scale}px system-ui, -apple-system, "Segoe UI", sans-serif`;
      ctx.lineWidth = 4 / scale;
      ctx.strokeStyle = chrome.surface;
      ctx.strokeText(text, x, y);
      ctx.fillStyle = chrome.ink;
      ctx.fillText(text, x, y);
    };
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    for (const n of list) {
      const a = trendArrow(n, scale);
      if (!a) continue;
      const head = (one ? 12 : 9) / scale;
      const bx = a.x1 - a.ux * head;
      const by = a.y1 - a.uy * head;
      // halo under the line keeps it readable over nodes and other lines
      ctx.lineCap = 'round';
      ctx.strokeStyle = chrome.surface;
      ctx.lineWidth = (one ? 7 : 5) / scale;
      ctx.beginPath();
      ctx.moveTo(a.x0, a.y0);
      ctx.lineTo(bx, by);
      ctx.stroke();
      ctx.strokeStyle = chrome.ink;
      ctx.lineWidth = (one ? 3 : 2) / scale;
      ctx.beginPath();
      ctx.moveTo(a.x0, a.y0);
      ctx.lineTo(bx, by);
      ctx.stroke();
      // start: hollow ring (the past), end: solid head (now)
      ctx.beginPath();
      ctx.arc(a.x0, a.y0, (one ? 6 : 4) / scale, 0, 2 * Math.PI);
      ctx.fillStyle = chrome.surface;
      ctx.fill();
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(a.x1, a.y1);
      ctx.lineTo(bx - a.uy * head * 0.6, by + a.ux * head * 0.6);
      ctx.lineTo(bx + a.uy * head * 0.6, by - a.ux * head * 0.6);
      ctx.closePath();
      ctx.fillStyle = chrome.ink;
      ctx.fill();
      const t = n.lab.trend!;
      const off = 16 / scale;
      if (one) {
        const toward = t.toward_subcluster_id != null ? subclusterName(t.toward_subcluster_id) : '';
        // the start sits on the node, so its year goes just outside the node on the opposite side of the arrow
        const back = Math.max(n.r, MIN_NODE_PX / scale) + off;
        label(`${t.early_years[0]}–${String(t.early_years[1]).slice(2)}`, a.x0 - a.ux * back, a.y0 - a.uy * back, false);
        label(`${t.recent_years[0]}–${String(t.recent_years[1]).slice(2)}${toward ? ` · ${toward}` : ''}`,
          a.x1 + a.ux * off, a.y1 + a.uy * off, true);
      } // with every arrow shown, the lab's own name at the start already says whose arrow it is
    }
    ctx.restore();
  };

  // direct cluster labels at centroids (identity never by colour alone), then lab names, most important first,
  // wherever they fit on screen; more fit as the map is zoomed in
  const paintOverlay = (ctx: CanvasRenderingContext2D, scale: number) => {
    paintOverlayLabels(ctx, scale);
    paintTrend(ctx, scale); // on top: the arrow and its labels are the subject while shown
  };

  const paintOverlayLabels = (ctx: CanvasRenderingContext2D, scale: number) => {
    const taken: LabelBox[] = [];
    const font = (weight: number, px: number) => `${weight} ${px / scale}px system-ui, -apple-system, "Segoe UI", sans-serif`;
    const drawText = (text: string, x: number, y: number, fill: string, halo: number) => {
      ctx.lineWidth = halo / scale;
      ctx.strokeStyle = chrome.surface;
      ctx.strokeText(text, x, y);
      ctx.fillStyle = fill;
      ctx.fillText(text, x, y);
    };
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    const level = zoomLevel();
    const g = fg.current;
    const tl = g?.screen2GraphCoords(0, 0);
    const br = g?.screen2GraphCoords(size.w, size.h);
    clusterBoxes.current = [];
    const clamp01 = (v: number) => Math.max(0, Math.min(1, v));
    // an area whose centre is off screen is not named; one whose centre is on screen keeps its whole name inside
    const nameAreas = (sub: boolean, name: (id: number) => string, px: number, alpha: number) => {
      if (alpha <= 0 || activeId) return;
      ctx.font = font(700, px);
      ctx.globalAlpha = alpha;
      const h = (px * 0.72) / scale;
      // largest areas first; a name that would cover another moves up or down
      const geometry = [...clusterGeometry(sub)].filter(([, s]) => s.n >= 2).sort(([, a], [, b]) => b.n - a.n);
      for (const [id, s] of geometry) {
        if (tl && br && (s.x < tl.x || s.x > br.x || s.y < tl.y || s.y > br.y)) continue;
        const text = name(id);
        const w = ctx.measureText(text).width / 2;
        const x = tl && br ? Math.max(tl.x + w + 4 / scale, Math.min(br.x - w - 4 / scale, s.x)) : s.x;
        for (const step of [0, 1, -1, 2, -2, 3, -3]) {
          const y = s.y + step * 2.1 * h;
          const b = { x0: x - w, y0: y - h, x1: x + w, y1: y + h };
          if (taken.some((t) => b.x0 < t.x1 && t.x0 < b.x1 && b.y0 < t.y1 && t.y0 < b.y1)) continue;
          taken.push(b);
          clusterBoxes.current.push({ ...b, id, sub });
          drawText(text, x, y, chrome.ink, 4);
          break;
        }
      }
      ctx.globalAlpha = 1;
    };
    const small = size.w < 500;
    nameAreas(false, (id) => clusterName(id), small ? 12 : 14, clamp01((CLUSTER_NAME_END - level) / 0.4));
    nameAreas(true, subclusterName, small ? 11 : 13,
      Math.min(clamp01((level - SUB_NAME_START) / 0.4), clamp01((SUB_NAME_END - level) / 0.6)));

    // only what is on screen is measured, so this stays cheap however many labs exist
    const share = shownShare();
    const namesOn = level >= LAB_NAME_ZOOM;
    const candidates = labelOrder.filter((n) => {
      if (!isDrawn(n.id, share) || !isLit(n.id)) return false;
      if (!namesOn && !forced(n.id)) return false; // zoomed out: only area names, plus the labs in focus
      const x = n.x ?? 0;
      const y = n.y ?? 0;
      return !tl || !br || (x >= tl.x && x <= br.x && y >= tl.y && y <= br.y);
    });
    // the active lab and its neighbours claim their places before anything else
    const important = (n: GNode) => n.id === activeId || (activeSet?.has(n.id) ?? false) || (edgeEnds?.includes(n.id) ?? false);
    const ordered = [...candidates.filter(important), ...candidates.filter((n) => !important(n))];
    const bold = font(700, 12);
    const plain = font(400, 11);
    const texts = ordered.map((n) => {
      const strong = n.id === activeId || (hubIds.has(n.id) && !activeId);
      ctx.font = strong ? bold : plain;
      const lines = strong ? wrapLabel(labTitle(n.lab), LABEL_LINE_PX / scale, (s) => ctx.measureText(s).width) : [piName(n.lab)];
      const width = Math.max(...lines.map((s) => ctx.measureText(s).width)) + 4 / scale;
      // a name near the canvas edge slides inward instead of running off screen
      const x = tl && br ? Math.max(tl.x + width / 2, Math.min(br.x - width / 2, n.x ?? 0)) : n.x ?? 0;
      return { n, lines, strong, width, x };
    });
    const lineH = 14 / scale;
    const placed = placeLabels(
      texts.map((t) => ({ x: t.x, y: t.n.y ?? 0, r: t.n.r, width: t.width, height: t.lines.length * lineH + 1 / scale })),
      taken, 15 / scale, 3 / scale,
    );
    placed.forEach((cy, i) => {
      if (cy === null) return;
      const t = texts[i];
      ctx.font = t.strong ? bold : plain;
      const top = cy - ((t.lines.length - 1) * lineH) / 2;
      t.lines.forEach((s, k) => drawText(s, t.x, top + k * lineH, chrome.ink, 3.5));
    });
  };

  // similarity lines would form a hairball when zoomed out, so only those of the hovered or selected lab show
  const similarityLines = data.links.some((l) => l.edge.type === 'similarity') && !data.links.some((l) => l.edge.type === 'coauthor');
  const linkVisible = (l: GLink) => {
    const a = endpointId(l.source);
    const b = endpointId(l.target);
    if (a === activeId || b === activeId || l.edge === selectedEdge) return true;
    const share = shownShare();
    if (!isDrawn(a, share) || !isDrawn(b, share)) return false;
    return showAll || l.edge.type === 'coauthor' || !similarityLines || zoomLevel() >= ALL_LINKS_ZOOM;
  };

  const linkColor = (l: GLink) => {
    const a = endpointId(l.source);
    const b = endpointId(l.target);
    const hot = l.edge === selectedEdge || (activeId !== null && (a === activeId || b === activeId));
    const dim = (activeId !== null || selectedEdge !== null) && !hot;
    const base = l.edge.type === 'coauthor' ? 0.32 : 0.18;
    // hovering only strengthens that one line; nothing else on the map changes
    const alpha = hot ? 0.75 : dim ? 0.04 : hoverLink === l ? base + 0.3 : base;
    return `rgba(${chrome.link},${alpha})`;
  };

  const linkWidth = (l: GLink) => {
    const base = l.edge.type === 'coauthor' ? 0.6 + Math.log2(1 + l.edge.weight) * 0.7 : 0.8;
    if (l.edge === selectedEdge) return base + 1.5;
    return hoverLink === l ? base + 0.6 : base;
  };

  const fit = () => {
    fg.current?.zoomToFit(500, 40);
    window.setTimeout(() => { if (fg.current) fitZoom.current = fg.current.zoom(); }, 550);
  };
  // quick clicks add up, and zooming into an empty part of the map moves to the nearest lab instead of showing nothing
  const zoomBy = (factor: number) => {
    const g = fg.current;
    if (!g) return;
    const k = (zoomTarget.current?.k ?? g.zoom()) * factor;
    window.clearTimeout(zoomTarget.current?.timer);
    zoomTarget.current = { k, timer: window.setTimeout(() => { zoomTarget.current = null; }, 400) };
    g.zoom(k, 250);
    if (factor <= 1) return;
    const c = g.centerAt();
    const halfW = size.w / 2 / k;
    const halfH = size.h / 2 / k;
    const inView = (n: GNode) => Math.abs((n.x ?? 0) - c.x) < halfW && Math.abs((n.y ?? 0) - c.y) < halfH;
    if (data.nodes.some(inView)) return;
    let best: GNode | null = null;
    let bestD = Infinity;
    for (const n of data.nodes) {
      const d = Math.hypot((n.x ?? 0) - c.x, (n.y ?? 0) - c.y);
      if (d < bestD) { bestD = d; best = n; }
    }
    if (best) g.centerAt(best.x, best.y, 250);
  };
  const shiftedCount = data.nodes.filter((n) => n.lab.trend?.status === 'shifted').length;
  const toggleShowAll = () => {
    const next = !showAll;
    setShowAll(next);
    try { localStorage.setItem(DETAIL_KEY, next ? '1' : '0'); } catch { /* the choice just is not remembered */ }
  };
  // a click on a cluster name zooms into that cluster; any other background click clears the selection
  const onCanvasBackgroundClick = (e: MouseEvent) => {
    const rect = box.current?.getBoundingClientRect();
    const p = rect && fg.current?.screen2GraphCoords(e.clientX - rect.left, e.clientY - rect.top);
    const hit = p && clusterBoxes.current.find((b) => p.x >= b.x0 && p.x <= b.x1 && p.y >= b.y0 && p.y <= b.y1);
    if (hit) fg.current?.zoomToFit(600, 70, (n: GNode) => (hit.sub ? n.lab.subcluster_id === hit.id : n.lab.cluster_id === hit.id));
    else onBackgroundClick();
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
        nodeVisibility={(n: GNode) => isDrawn(n.id)}
        linkVisibility={linkVisible}
        nodePointerAreaPaint={paintPointer}
        nodeLabel={() => ''}
        linkColor={linkColor}
        linkWidth={linkWidth}
        linkHoverPrecision={3}
        onRenderFramePre={paintUnderlay}
        onRenderFramePost={paintOverlay}
        onNodeDrag={(n) => { if (dragId !== String(n.id)) setDragId(String(n.id)); }}
        onNodeDragEnd={() => setDragId(null)}
        onNodeHover={(n) => {
          setHoverId(n ? String(n.id) : null);
          onHover(n ? n.lab : null);
          if (box.current) box.current.style.cursor = n ? 'pointer' : 'default';
        }}
        onLinkHover={(l) => {
          setHoverLink(l ?? null);
          if (box.current) box.current.style.cursor = l ? 'pointer' : 'default';
        }}
        onLinkClick={(l) => onEdgeClick(l.edge)}
        onNodeClick={(n) => onSelect(n.lab)}
        onBackgroundClick={onCanvasBackgroundClick}
        cooldownTicks={180}
        d3AlphaDecay={0.035}
        d3VelocityDecay={0.35}
        onEngineStop={() => {
          if (!fitted.current) {
            fitted.current = true;
            fit();
          }
        }}
      />
      <div className="graph-tools">
        <div className="graph-note" aria-live="polite">
          {showAll || visibleCount >= data.nodes.length
            ? `${data.nodes.length}곳 모두 표시`
            : `${data.nodes.length}곳 중 ${visibleCount}곳 표시 · 확대하면 더 보입니다`}
        </div>
        <button className="graph-btn" aria-pressed={showAll} onClick={toggleShowAll}>모두 표시</button>
        {shiftedCount > 0 && (
          <button className="graph-btn" aria-pressed={showTrends} onClick={() => setShowTrends(!showTrends)}
                  title="최근 연구 주제가 달라진 신호가 있는 연구실의 방향을 모두 표시">
            방향 변화 {shiftedCount}곳
          </button>
        )}
        <div className="graph-zoom" role="group" aria-label="지도 확대·축소">
          <button className="graph-btn" onClick={() => zoomBy(1.5)} aria-label="확대">+</button>
          <button className="graph-btn" onClick={() => zoomBy(1 / 1.5)} aria-label="축소">−</button>
          <button className="graph-btn" onClick={fit}>전체 보기</button>
        </div>
      </div>
      {(trendFocus || showTrends) && (
        <div className="trend-legend" role="note">
          <strong>연구 방향 변화</strong>
          <span><span className="trend-key-start" aria-hidden="true" /> 2022–23 논문 위치</span>
          <span><span className="trend-key-end" aria-hidden="true" /> 2025–26 논문 위치</span>
          {trendFocus && <span><span className="trend-key-ring" aria-hidden="true" /> 최근 가까워진 연구실</span>}
          <span className="muted">길이는 방향을 읽기 쉽게 늘인 것이며 거리를 뜻하지 않습니다. 약 5곳에 1곳은 우연일 수 있습니다.</span>
        </div>
      )}
      <ul className="graph-legend" aria-label="노드 색 범례">
        {FIELD_ORDER.filter((f) => data.nodes.some((n) => n.lab.disciplines[0] === f)).map((f) => (
          <li key={f}><span className="dot" style={{ background: fieldColor(f, mode) }} aria-hidden="true" />{FIELD_LABEL[f]}</li>
        ))}
      </ul>
    </div>
  );
}
