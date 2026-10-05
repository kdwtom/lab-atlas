// Ad-hoc screenshot of specific routes, for checking a change by eye.
//   node scripts/shot.mjs <outDir> <name>=<hash-route> ...
import { chromium } from 'playwright-core';
import { mkdirSync } from 'node:fs';

const BASE = process.env.BASE_URL ?? 'http://localhost:4173/';
const [out, ...pairs] = process.argv.slice(2);
mkdirSync(out, { recursive: true });

const browser = await chromium.launch({ channel: 'msedge', headless: true });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 1100 }, colorScheme: 'dark' });
const page = await ctx.newPage();
for (const pair of pairs) {
  const i = pair.indexOf('=');
  const [name, route] = [pair.slice(0, i), pair.slice(i + 1)];
  await page.goto(BASE + route);
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${out}/${name}.png`, fullPage: true });
  console.log(name, '->', route);
}
await browser.close();
