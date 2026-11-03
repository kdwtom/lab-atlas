import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';

const KEY = 'lab-atlas.shortlist.v1';

interface Ctx {
  ids: string[];
  has: (id: string) => boolean;
  toggle: (id: string) => void;
  addAll: (ids: string[]) => void;
  clear: () => void;
}

const ShortlistCtx = createContext<Ctx | null>(null);

// Browser storage can be missing or blocked (private windows, previews); the list then lasts for the visit.
function load(): string[] {
  try {
    const v: unknown = JSON.parse(localStorage.getItem(KEY) ?? '[]');
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : [];
  } catch {
    return [];
  }
}

function save(ids: string[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(ids));
  } catch {
    // keep the in-memory list
  }
}

/** Labs the visitor collected: the starting point for recommendations and the columns of the comparison. */
export function ShortlistProvider({ children }: { children: ReactNode }) {
  const [ids, setIds] = useState<string[]>(load);
  const value = useMemo<Ctx>(() => {
    const update = (next: string[]) => {
      save(next);
      setIds(next);
    };
    return {
      ids,
      has: (id) => ids.includes(id),
      toggle: (id) => update(ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]),
      addAll: (more) => update([...ids, ...more.filter((x) => !ids.includes(x))]),
      clear: () => update([]),
    };
  }, [ids]);
  return <ShortlistCtx.Provider value={value}>{children}</ShortlistCtx.Provider>;
}

export function useShortlist(): Ctx {
  const c = useContext(ShortlistCtx);
  if (!c) throw new Error('ShortlistProvider missing');
  return c;
}
