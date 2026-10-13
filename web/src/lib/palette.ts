import type { Discipline } from '../types/data';

// Cluster colours: the validated 8-slot categorical palette (dataviz reference instance), assigned in
// fixed order by cluster id. Validator: light — all gates pass, slots 3/4/5 below 3:1 on the light
// surface (relief: direct cluster labels on the graph + list view); dark — all gates pass.
// With 9 clusters the 9th never gets a generated hue: it takes the neutral muted ink, and cluster
// identity is always also given by text (on-canvas labels, legend, panel), never by colour alone.
const LIGHT = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948'];
const DARK = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'];
const NEUTRAL = '#898781';

export type Mode = 'light' | 'dark';

// Node colour = field of the lab's (first) department. Five fields take slots 0, 1, 2, 6, 7 of the same
// validated palette, skipping slots 3-5 that fall below 3:1 on the light surface. Field identity is also
// given by text (legend chips, panel, list column).
const FIELD_SLOT: Record<Discipline, number> = { phys: 0, chem: 1, life: 2, math: 6, cs: 7 };
export const FIELD_ORDER: Discipline[] = ['life', 'chem', 'phys', 'math', 'cs'];
export const FIELD_LABEL: Record<Discipline, string> = {
  life: '생명과학', chem: '화학', phys: '물리', math: '수학', cs: '컴퓨터',
};

export function fieldColor(d: Discipline | undefined, mode: Mode): string {
  if (!d) return NEUTRAL;
  return (mode === 'dark' ? DARK : LIGHT)[FIELD_SLOT[d]];
}

export function clusterColor(id: number | null | undefined, mode: Mode): string {
  if (id === null || id === undefined) return NEUTRAL;
  const p = mode === 'dark' ? DARK : LIGHT;
  return id < p.length ? p[id] : NEUTRAL;
}

/** Canvas chrome per mode (mirrors the CSS tokens in styles.css). */
export const CHROME: Record<Mode, { surface: string; ink: string; inkSecondary: string; muted: string; link: string }> = {
  light: { surface: '#fcfcfb', ink: '#0b0b0b', inkSecondary: '#52514e', muted: '#898781', link: '11,11,11' },
  dark: { surface: '#1a1a19', ink: '#ffffff', inkSecondary: '#c3c2b7', muted: '#898781', link: '255,255,255' },
};
