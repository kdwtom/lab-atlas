// Visual + performance check using the locally installed Microsoft Edge (playwright-core, no download).
//   npm run build && npx vite preview --port 4173   (in another terminal)
//   node scripts/check.mjs [outDir]
// Saves main / hover / detail / mobile screenshots and prints hover frame-rate for the real data and
// for 300 dummy nodes.
import { chromium } from 'playwright-core';
import { mkdirSync } from 'node:fs';

const BASE = process.env.BASE_URL ?? 'http://localhost:4173/';
const OUT = process.argv[2] ?? '../docs/screenshots';
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ channel: 'msedge', headless: true });

async function settle(page, ms = 6000) {
  await page.waitForFunction(() => window.__labAtlas && window.__labAtlas.ids().length > 0, null, { timeout: 30000 });
  await page.waitForTimeout(ms);
}

/** Move the mouse across N nodes and measure frames per second while hovering. */
async function hoverFps(page, steps = 40) {
  const ids = await page.evaluate(() => window.__labAtlas.ids());
  await page.evaluate(() => {
    window.__frames = 0;
    const tick = () => { window.__frames++; window.__raf = requestAnimationFrame(tick); };
    window.__raf = requestAnimationFrame(tick);
  });
  const t0 = Date.now();
  for (let i = 0; i < steps; i++) {
    const p = await page.evaluate((id) => window.__labAtlas.nodeScreen(id), ids[(i * 7) % ids.length]);
    if (p) await page.mouse.move(p.x, p.y, { steps: 4 });
    await page.waitForTimeout(60);
  }
  const frames = await page.evaluate(() => { cancelAnimationFrame(window.__raf); return window.__frames; });
  return frames / ((Date.now() - t0) / 1000);
}

const results = {};
for (const theme of ['dark']) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: theme, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));

  await page.goto(BASE + '#/');
  await settle(page);
  await page.screenshot({ path: `${OUT}/main.png` });

  // hover the best-connected lab
  const target = await page.evaluate(() => window.__labAtlas.ids()[0]);
  const ids = await page.evaluate(() => window.__labAtlas.ids());
  let hovered = target;
  for (const id of ids.slice(0, 40)) {
    const p = await page.evaluate((i) => window.__labAtlas.nodeScreen(i), id);
    if (!p) continue;
    await page.mouse.move(p.x, p.y);
    await page.waitForTimeout(250);
    const named = await page.locator('aside.panel .panel-title').first().textContent();
    if (named && !named.includes('한눈에')) { hovered = id; break; }
  }
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${OUT}/hover.png` });
  results.realFps = await hoverFps(page);

  await page.goto(BASE + `#/lab/${encodeURIComponent(hovered)}`);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/detail.png`, fullPage: true });

  await page.goto(BASE + '#/about');
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/about.png` });

  await page.goto(BASE + '#/');
  await page.getByRole('button', { name: '목록' }).click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${OUT}/list.png` });
  await page.getByRole('button', { name: '그래프' }).click();

  // performance with 300 dummy nodes
  await page.goto(BASE + '#/?dummy=300');
  await page.reload();
  await settle(page, 7000);
  results.dummyNodes = (await page.evaluate(() => window.__labAtlas.ids())).length;
  await page.screenshot({ path: `${OUT}/dummy300.png` });
  results.dummyFps = await hoverFps(page);
  results.errors = errors;
  await ctx.close();
}

// mobile: tap a node -> bottom sheet preview
{
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: 'light', isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  await page.goto(BASE + '#/');
  await settle(page);
  await page.screenshot({ path: `${OUT}/mobile.png` });
  const ids = await page.evaluate(() => window.__labAtlas.ids());
  for (const id of ids.slice(0, 30)) {
    const p = await page.evaluate((i) => window.__labAtlas.nodeScreen(i), id);
    if (!p || p.y < 260 || p.y > 820 || p.x < 10 || p.x > 380) continue;
    await page.mouse.click(p.x, p.y);
    await page.waitForTimeout(700);
    if (await page.locator('aside.panel.sheet').count()) break;
  }
  results.mobileSheet = await page.locator('aside.panel.sheet').count();
  await page.screenshot({ path: `${OUT}/mobile_sheet.png` });
  await ctx.close();
}

await browser.close();
console.log(JSON.stringify(results, null, 2));
