// Cluster colours: the validated 8-slot categorical palette (dataviz reference instance), assigned in
// fixed order by cluster id. Validator: light — all gates pass, slots 3/4/5 below 3:1 on the light
// surface (relief: direct cluster labels on the graph + list view); dark — all gates pass.
// With 9 clusters the 9th never gets a generated hue: it takes the neutral muted ink, and cluster
// identity is always also given by text (on-canvas labels, legend, panel), never by colour alone.
const LIGHT = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948'];
const DARK = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'];
const NEUTRAL = '#898781';

export type Mode = 'light' | 'dark';

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
