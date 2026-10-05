import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Cluster, Edge, Lab, Meta, Paper } from '../types/data';
import { makeDummy } from './dummy';

export interface Neighbor {
  lab: Lab;
  edge: Edge;
}

export interface Atlas {
  labs: Lab[];
  papers: Paper[];
  edges: Edge[];
  clusters: Cluster[];
  meta: Meta;
  labById: Map<string, Lab>;
  paperById: Map<string, Paper>;
  clusterById: Map<number, Cluster>;
  /** neighbours per lab and edge type, strongest first */
  neighbors: (labId: string, type: Edge['type']) => Neighbor[];
  dummy: boolean;
}

type State = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; atlas: Atlas };

const Ctx = createContext<State>({ status: 'loading' });

async function getJson<T>(name: string): Promise<T> {
  const res = await fetch(`${import.meta.env.BASE_URL}data/${name}`);
  if (!res.ok) throw new Error(`${name}: HTTP ${res.status}`);
  return (await res.json()) as T;
}

/** `#/?dummy=300` replaces the data with N synthetic labs (performance testing only). */
function dummyCount(): number {
  const q = window.location.hash.split('?')[1];
  const n = q ? Number(new URLSearchParams(q).get('dummy')) : 0;
  return Number.isFinite(n) && n > 0 ? Math.min(n, 3000) : 0;
}

export function buildAtlas(labs: Lab[], papers: Paper[], edges: Edge[], clusters: Cluster[], meta: Meta,
                           dummy = false): Atlas {
  const labById = new Map(labs.map((l) => [l.id, l]));
  const adj = new Map<string, Neighbor[]>();
  for (const e of edges) {
    for (const [a, b] of [[e.source, e.target], [e.target, e.source]] as const) {
      const other = labById.get(b);
      if (!other) continue;
      const key = `${a}|${e.type}`;
      if (!adj.has(key)) adj.set(key, []);
      adj.get(key)!.push({ lab: other, edge: e });
    }
  }
  for (const list of adj.values()) list.sort((x, y) => y.edge.weight - x.edge.weight);
  return {
    labs, papers, edges, clusters, meta, labById, dummy,
    paperById: new Map(papers.map((p) => [p.id, p])),
    clusterById: new Map(clusters.map((c) => [c.id, c])),
    neighbors: (labId, type) => adj.get(`${labId}|${type}`) ?? [],
  };
}

export function DataProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ status: 'loading' });
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [labs, papers, edges, clusters, meta] = await Promise.all([
          getJson<Lab[]>('labs.json'), getJson<Paper[]>('papers.json'), getJson<Edge[]>('edges.json'),
          getJson<Cluster[]>('clusters.json'), getJson<Meta>('meta.json'),
        ]);
        const n = dummyCount();
        const atlas = n
          ? (() => {
              const d = makeDummy(n, clusters, meta);
              return buildAtlas(d.labs, [], d.edges, d.clusters, d.meta, true);
            })()
          : buildAtlas(labs, papers, edges, clusters, meta);
        if (alive) setState({ status: 'ready', atlas });
      } catch (e) {
        if (alive) setState({ status: 'error', message: e instanceof Error ? e.message : String(e) });
      }
    })();
    return () => {
      alive = false;
    };
  }, []);
  return <Ctx.Provider value={state}>{children}</Ctx.Provider>;
}

export function useAtlasState(): State {
  return useContext(Ctx);
}

/** Only call below a component that has checked status === 'ready'. */
export function useAtlas(): Atlas {
  const s = useContext(Ctx);
  if (s.status !== 'ready') throw new Error('atlas not ready');
  return s.atlas;
}
