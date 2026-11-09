// node e2e.mjs  -> runs layout/a11y sweeps + scripted flows for all three mini-apps.
// Exit code 1 if any check fails. Writes ../docs/e2e-report.json
import { launch, APPS, SAMPLE, urlOf, watch, sleep, root } from './lib.mjs';
import { writeFileSync } from 'fs';
import path from 'path';

const results = []; // {app, suite, name, ok, detail}
const rec = (app, suite, name, ok, detail = '') => { results.push({ app, suite, name, ok: !!ok, detail }); if (!ok) console.log('  FAIL', app, suite, name, detail); };

// ---------- sweep: every screen x 3 widths x 2 themes ----------
async function sweep(browser, app) {
  for (const theme of ['light', 'dark']) for (const w of [360, 390, 430]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: 780 }, colorScheme: theme });
    const p = await ctx.newPage(); const errs = []; watch(p, errs);
    await p.goto(urlOf(app)); await sleep(200);
    const ids = await p.evaluate(() => window.__app.ids());
    for (const id of ids) {
      await p.evaluate(([i, s]) => window.__app.go(i, { params: { id: s } }), [id, SAMPLE[id] || '']);
      await sleep(320);
      const m = await p.evaluate(() => {
        const on = document.querySelectorAll('.screen.on');
        const el = on[0]; const app = document.getElementById('app');
        const txt = el ? el.innerText.trim().length : 0;
        // overflow: any visible element wider than the viewport
        let over = [];
        el && el.querySelectorAll('*').forEach(n => { const r = n.getBoundingClientRect(); if (r.width > 0 && (r.right > innerWidth + 1) && !n.closest('.chips,.sheet,.map')) over.push((n.className || n.tagName).toString().slice(0, 30)); });
        // tap targets (interactive, visible)
        const small = [];
        document.querySelectorAll('button,[data-act],[data-go],input,textarea,select').forEach(n => {
          const r = n.getBoundingClientRect(); const cs = getComputedStyle(n);
          if (r.width === 0 || r.height === 0 || cs.visibility === 'hidden' || n.closest('.sheet:not(.on)') || n.closest('.screen:not(.on)') || n.closest('.tabbar.hidden')) return;
          if (cs.display === 'none' || n.type === 'range') return;
          if (r.height < 36 || r.width < 36) small.push(((n.dataset.testid || n.className || n.tagName) + '').slice(0, 30) + ` ${Math.round(r.width)}x${Math.round(r.height)}`);
        });
        // contrast
        const lum = c => { const [r, g, b] = c.map(v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }); return .2126 * r + .7152 * g + .0722 * b; };
        const parse = s => { const m = s.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,\/]+/).map(Number); return { c: p.slice(0, 3), a: p[3] === undefined ? 1 : p[3] }; };
        const bgOf = n => { while (n) { const c = parse(getComputedStyle(n).backgroundColor); if (c && c.a > .5) return c.c; n = n.parentElement; } return [255, 255, 255]; };
        const low = [];
        const walker = document.createTreeWalker(el || document.body, NodeFilter.SHOW_TEXT);
        let t; while ((t = walker.nextNode())) {
          if (!t.textContent.trim()) continue; const n = t.parentElement; const r = n.getBoundingClientRect(); if (!r.width) continue;
          const cs = getComputedStyle(n); if (cs.visibility === 'hidden') continue;
          const fg = parse(cs.color); if (!fg) continue; const bg = bgOf(n);
          const l1 = lum(fg.c), l2 = lum(bg); const ratio = (Math.max(l1, l2) + .05) / (Math.min(l1, l2) + .05);
          const size = parseFloat(cs.fontSize), bold = +cs.fontWeight >= 600; const need = (size >= 24 || (size >= 18.66 && bold)) ? 3 : 4.5;
          if (ratio < need) low.push(`${t.textContent.trim().slice(0, 18)} ${ratio.toFixed(2)}<${need}`);
        }
        return { screens: on.length, txt, over: [...new Set(over)].slice(0, 4), small: [...new Set(small)].slice(0, 6), low: [...new Set(low)].slice(0, 6) };
      });
      const tag = `${id}@${w}/${theme}`;
      rec(app, 'sweep', `${tag} one screen visible`, m.screens === 1, `n=${m.screens}`);
      rec(app, 'sweep', `${tag} not empty`, m.txt > 15, `len=${m.txt}`);
      rec(app, 'sweep', `${tag} no horizontal overflow`, !m.over.length, m.over.join(','));
      rec(app, 'sweep', `${tag} tap targets >=36px`, !m.small.length, m.small.join(' | '));
      rec(app, 'sweep', `${tag} contrast AA`, !m.low.length, m.low.join(' | '));
    }
    rec(app, 'sweep', `no JS errors @${w}/${theme}`, !errs.length, errs.slice(0, 3).join(' | '));
    await ctx.close();
  }
}

// ---------- flows ----------
const T = (p, id) => p.locator(`[data-testid="${id}"]`);
const click = async (p, id) => { await p.locator(`[data-testid="${id}"]:visible`).first().click({ timeout: 2500 }); await sleep(260); };
const cur = p => p.evaluate(() => window.__app.state.current);
const main = async p => { await p.locator('#mainbtn').click({ timeout: 2500 }); await sleep(260); };
const expect = (app, name, cond, d) => rec(app, 'flow', name, cond, d);

const b = await launch(); const t0 = Date.now();
const ONLY = process.env.ONLY;
for (const a of APPS) { if (ONLY && a !== ONLY) continue; console.log('sweep', a); await sweep(b, a); }
console.log('flows');
if (!ONLY || ONLY === 'reels-radar') await flowReels(b);
if (!ONLY || ONLY === 'faceless') await flowFaceless(b);
await b.close();
const fails = results.filter(r => !r.ok);
writeFileSync(path.join(root, 'docs/e2e-report.json'), JSON.stringify({ total: results.length, failed: fails.length, secs: (Date.now() - t0) / 1000, results }, null, 1));
for (const a of APPS) { const r = results.filter(x => x.app === a); console.log(a.padEnd(12), `${r.filter(x => x.ok).length}/${r.length}`); }
console.log(`TOTAL ${results.length - fails.length}/${results.length} in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
process.exit(fails.length ? 1 : 0);
