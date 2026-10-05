import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';
import type { Edge, Lab, Univ } from '../types/data';
import { labTitle } from '../lib/format';

export type View = 'graph' | 'list';

export interface ExploreState {
  view: View;
  edgeMode: Edge['type'];
  query: string;
  univs: Set<Univ>;          // empty = all
  clusters: Set<number>;     // empty = all
}

interface Ctx extends ExploreState {
  set: (patch: Partial<ExploreState>) => void;
  toggleUniv: (u: Univ) => void;
  toggleCluster: (c: number) => void;
  reset: () => void;
}

const initial: ExploreState = { view: 'graph', edgeMode: 'similarity', query: '', univs: new Set(), clusters: new Set() };
const ExploreCtx = createContext<Ctx | null>(null);

function toggled<T>(s: Set<T>, v: T): Set<T> {
  const n = new Set(s);
  if (n.has(v)) n.delete(v);
  else n.add(v);
  return n;
}

/** Lives above the router so filters survive a visit to a lab page and back. */
export function ExploreProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ExploreState>(initial);
  const value = useMemo<Ctx>(() => ({
    ...state,
    set: (patch) => setState((s) => ({ ...s, ...patch })),
    toggleUniv: (u) => setState((s) => ({ ...s, univs: toggled(s.univs, u) })),
    toggleCluster: (c) => setState((s) => ({ ...s, clusters: toggled(s.clusters, c) })),
    reset: () => setState((s) => ({ ...initial, view: s.view, edgeMode: s.edgeMode })),
  }), [state]);
  return <ExploreCtx.Provider value={value}>{children}</ExploreCtx.Provider>;
}

export function useExplore(): Ctx {
  const c = useContext(ExploreCtx);
  if (!c) throw new Error('ExploreProvider missing');
  return c;
}

const norm = (s: string) => s.toLowerCase().replace(/[\s\-‐·]/g, '');

/** Search over lab name, PI Korean/English name and keywords. */
export function matchesQuery(lab: Lab, query: string): boolean {
  const q = norm(query.trim());
  if (!q) return true;
  const hay = [labTitle(lab), lab.pi_name_ko ?? '', lab.pi_name_en ?? '', ...lab.keywords].map(norm);
  return hay.some((h) => h.includes(q));
}

export function passesFilters(lab: Lab, s: Pick<ExploreState, 'univs' | 'clusters'>): boolean {
  return (s.univs.size === 0 || s.univs.has(lab.univ)) &&
    (s.clusters.size === 0 || (lab.cluster_id !== null && s.clusters.has(lab.cluster_id)));
}
