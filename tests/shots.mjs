// Usage: node shots.mjs <app> [theme]  -> screenshots of every registered screen into ../docs/shots/<app>/
import { chromium } from 'playwright-core';
import { mkdirSync } from 'fs';
import { pathToFileURL } from 'url';
import path from 'path';
const app = process.argv[2], theme = process.argv[3] || 'light';
const root = path.resolve(import.meta.dirname, '..');
const out = path.join(root, 'docs/shots', app, theme); mkdirSync(out, { recursive: true });
const exe = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const b = await chromium.launch({ executablePath: exe });
const ctx = await b.newContext({ viewport: { width: 390, height: 800 }, deviceScaleFactor: 2, colorScheme: theme });
const p = await ctx.newPage();
const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => m.type() === 'error' && !/telegram|ERR_/i.test(m.text()) && errs.push(m.text()));
await p.goto(pathToFileURL(path.join(root, app, 'index.html')).href);
await p.waitForTimeout(300);
const ids = await p.evaluate(() => window.__app.ids());
for (const id of ids) {
  const SAMPLE = { detail: 'NT-047', trend: 't1', author: 'a1', video: 'v1' };
  await p.evaluate(([i, s]) => window.__app.go(i, { params: { id: s } }), [id, SAMPLE[id] || '']);
  await p.waitForTimeout(450);
  await p.screenshot({ path: path.join(out, id + '.png') });
}
console.log('screens', ids.length, 'errors', errs.length, errs.slice(0, 5));
await b.close();
