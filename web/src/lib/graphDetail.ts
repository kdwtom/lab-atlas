// Level of detail for the map: how many labs to draw at a zoom, which ones, and where their names fit.

export interface DetailInput {
  id: string;
  cluster: number | null;
  degree: number;
  papers: number;
}

export interface DetailRank {
  rank: number;   // 0 = first in its cluster
  size: number;   // labs in the cluster
  share: number;  // the lab appears once this share of labs is drawn
}

/** Screen area one lab gets on the map; a denser map stops being readable. */
const AREA_PER_LAB = 7000;

/** Labs that fit at a relative zoom (1 = whole map fits). Each zoom step shows 1/zoom² of the map, so the count grows with zoom². */
export function detailBudget(canvasArea: number, zoomLevel: number): number {
  return (canvasArea / AREA_PER_LAB) * Math.max(zoomLevel, 1) ** 2;
}

/** Order labs inside each cluster, most connected first (more papers, then id, break ties), so every region keeps its share. */
export function detailRanks(labs: DetailInput[]): Map<string, DetailRank> {
  const groups = new Map<number, DetailInput[]>();
  for (const l of labs) {
    const k = l.cluster ?? -1;
    const g = groups.get(k);
    if (g) g.push(l);
    else groups.set(k, [l]);
  }
  const out = new Map<string, DetailRank>();
  for (const g of groups.values()) {
    g.sort((a, b) => b.degree - a.degree || b.papers - a.papers || a.id.localeCompare(b.id));
    g.forEach((l, i) => out.set(l.id, { rank: i, size: g.length, share: (i + 1) / g.length }));
  }
  return out;
}

export interface LabelBox { x0: number; y0: number; x1: number; y1: number }
export interface LabelInput { x: number; y: number; r: number; width: number }

/** Place labels in order, below or else above each node, skipping any that would collide. Returns each label's centre y, or null. */
export function placeLabels(labels: LabelInput[], taken: LabelBox[], height: number, gap: number): (number | null)[] {
  // a grid on the label height keeps this near linear in the number of labels
  const cell = height * 8;
  const grid = new Map<string, LabelBox[]>();
  const cellsOf = (b: LabelBox) => {
    const keys: string[] = [];
    for (let cx = Math.floor(b.x0 / cell); cx <= Math.floor(b.x1 / cell); cx++) {
      for (let cy = Math.floor(b.y0 / cell); cy <= Math.floor(b.y1 / cell); cy++) keys.push(`${cx},${cy}`);
    }
    return keys;
  };
  const add = (b: LabelBox) => {
    for (const k of cellsOf(b)) {
      const list = grid.get(k);
      if (list) list.push(b);
      else grid.set(k, [b]);
    }
  };
  const hits = (b: LabelBox) => cellsOf(b).some((k) =>
    (grid.get(k) ?? []).some((t) => b.x0 < t.x1 && t.x0 < b.x1 && b.y0 < t.y1 && t.y0 < b.y1));
  taken.forEach(add);
  return labels.map((l) => {
    const w = l.width / 2;
    for (const cy of [l.y + l.r + gap + height / 2, l.y - l.r - gap - height / 2]) {
      const b = { x0: l.x - w, y0: cy - height / 2, x1: l.x + w, y1: cy + height / 2 };
      if (hits(b)) continue;
      add(b);
      return cy;
    }
    return null;
  });
}
