// Stress / chaos test for the mini-app UI.
// usage: node stress.mjs <app> [users=20] [actions=60] [concurrency=10] [seed=1]
// Each "bot" is an isolated browser context doing a seeded random walk of taps, typing and back-navigation,
// with hostile input (XSS, emoji, very long strings). Checks invariants after every action.
// Для reels-radar/faceless: UI под параллельными сессиями, бэкенда нет.
// Для nhatrang (v2): поднимается тестовый сервер (tools/test_server.py), боты ходят под разными Telegram ID без доступа,
// дополнительный инвариант: платный контент и контакты никогда не попадают в DOM.
import { launch, urlOf, watch, sleep, rng, SAMPLE } from './lib.mjs';
import { execSync, spawn } from 'child_process';
import fs from 'fs'; import os from 'os'; import path0 from 'path';

const [app = 'reels-radar', USERS = 20, ACTIONS = 60, CONC = 10, SEED = 1] = process.argv.slice(2);
const N = +USERS, M = +ACTIONS, C = +CONC;
const NT = app === 'nhatrang';
const PORT = 8792, BASE = `http://127.0.0.1:${PORT}`;
const SECRETS = ['УНИКАЛЬНЫЙ_ТЕКСТ', 'seed_agent', 'seed_realtor', '0900000001', 'example.test/post'];
const EVIL = ['<img src=x onerror="window.__xss=1">', '"><script>window.__xss=1</script>', '😀🏠'.repeat(40), 'a'.repeat(3000), '', '   ', "'; DROP TABLE x;--", '0'.repeat(30), '@' + 'z'.repeat(80)];

const rssMB = () => { try { return Math.round(execSync("ps -axo rss=,args= | grep -i headless_shell | grep -v grep | awk '{s+=$1} END{print s}'").toString().trim() / 1024) || 0; } catch { return 0; } };

async function bot(browser, id, out) {
  const rand = rng(+SEED * 1000 + id);
  const ctx = await browser.newContext({ viewport: { width: 360 + Math.floor(rand() * 80), height: 700 + Math.floor(rand() * 150) }, hasTouch: true });
  const p = await ctx.newPage(); const errs = []; watch(p, errs);
  await p.addInitScript(() => { window.__lat = []; });
  try {
    await p.goto(NT ? `${BASE}/?dev=${3000 + id}` : urlOf(app), { timeout: 15000 }); await sleep(150);
    for (let i = 0; i < M; i++) {
      // pick a random visible interactive element that is inside the viewport and not covered
      const pick = await p.evaluate(r => {
        const on = document.querySelector('.screen.on');
        const sheetOn = document.querySelector('.sheet.on');
        const roots = sheetOn ? [sheetOn] : [on, document.querySelector('.tabbar:not(.hidden)'), document.getElementById('mainbtn'), document.getElementById('tgback')].filter(Boolean);
        const c = [];
        roots.forEach(root => root.querySelectorAll('button,input,textarea,[data-act],[data-go]').forEach(n => {
          const b = n.getBoundingClientRect(); if (b.width < 4 || b.height < 4 || n.disabled) return;
          const x = b.left + b.width / 2, y = b.top + b.height / 2; if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) return;
          const top = document.elementFromPoint(x, y); if (!top || !(n === top || n.contains(top) || top.contains(n))) return;
          c.push({ x, y, tag: n.tagName, type: n.type, id: n.dataset.testid || n.id || '' });
        }));
        if (!c.length) return null; return { el: c[Math.floor(r * c.length)], n: c.length };
      }, rand());
      if (!pick) { out.noTargets++; await p.evaluate(() => tgx.back()); continue; }
      const t0 = Date.now();
      const { x, y, tag, type } = pick.el;
      if (tag === 'INPUT' && type === 'range') { await p.mouse.click(x, y); }
      else if ((tag === 'INPUT' || tag === 'TEXTAREA')) { await p.mouse.click(x, y); await p.keyboard.insertText(EVIL[Math.floor(rand() * EVIL.length)]); }
      else await p.mouse.click(x, y);
      if (rand() < .08) await p.evaluate(() => tgx.back());
      const dt = await p.evaluate(() => new Promise(r => { const s = performance.now(); requestAnimationFrame(() => requestAnimationFrame(() => r(performance.now() - s))); }));
      out.lat.push(dt); out.actions++;
      const inv = await p.evaluate(secrets => {
        const on = document.querySelectorAll('.screen.on').length; const bad = [];
        if (on !== 1) bad.push('screens_on=' + on);
        if (window.__xss) bad.push('XSS');
        try { if (typeof S !== 'undefined' && (('free' in S && S.free < 0) || ('freeC' in S && S.freeC < 0))) bad.push('quota<0'); } catch { }
        if (document.documentElement.scrollWidth > innerWidth + 2) bad.push('hscroll');
        for (const s of secrets) if (document.documentElement.innerHTML.includes(s)) bad.push('LEAK:' + s);
        return bad;
      }, NT ? SECRETS : []);
      if (inv.length) { out.inv.push(`bot${id}#${i} ${inv.join(',')} after ${pick.el.id}`); if (inv.includes('XSS')) { await p.evaluate(() => { window.__xss = 0; }); } }
      if (Date.now() - t0 > 3000) out.slow++;
      await sleep(20 + Math.floor(rand() * 60));
    }
  } catch (e) { out.crash.push(`bot${id}: ${String(e.message).split('\n')[0]}`); }
  out.errs.push(...errs.map(e => `bot${id}: ${e}`));
  await ctx.close();
}

const pct = (a, q) => a.length ? [...a].sort((x, y) => x - y)[Math.min(a.length - 1, Math.floor(a.length * q))] : 0;
let server, dbDir;
if (NT) {
  const sd = path0.resolve(import.meta.dirname, '../nhatrang/server'); dbDir = fs.mkdtempSync(path0.join(os.tmpdir(), 'nd-stress-'));
  server = spawn(path0.join(sd, '.venv/bin/python'), ['-m', 'tools.test_server', String(PORT), dbDir], { cwd: sd, stdio: 'ignore' });
  for (let i = 0; i < 60; i++) { try { if ((await fetch(BASE + '/api/health')).ok) break; } catch { } await sleep(250); }
}
const browser = await launch(); const out = { actions: 0, lat: [], inv: [], errs: [], crash: [], slow: 0, noTargets: 0 };
const t0 = Date.now(); let peak = 0;
const mon = setInterval(() => { peak = Math.max(peak, rssMB()); }, 700);
const q = [...Array(N).keys()];
await Promise.all(Array.from({ length: C }, async () => { while (q.length) await bot(browser, q.shift(), out); }));
clearInterval(mon); await browser.close();
if (server) { server.kill('SIGTERM'); await sleep(400); try { process.kill(server.pid, 0); server.kill('SIGKILL'); } catch { } fs.rmSync(dbDir, { recursive: true, force: true }); }
const secs = (Date.now() - t0) / 1000;
const uniq = a => [...new Set(a.map(s => s.replace(/bot\d+#?\d*\s?/g, '')))];
const summary = { app, users: N, concurrency: C, actionsPerBot: M, seed: +SEED, totalActions: out.actions, secs: +secs.toFixed(1), actionsPerSec: +(out.actions / secs).toFixed(1),
  latencyMs: { p50: +pct(out.lat, .5).toFixed(0), p95: +pct(out.lat, .95).toFixed(0), p99: +pct(out.lat, .99).toFixed(0), max: +Math.max(0, ...out.lat).toFixed(0) },
  peakChromeRssMB: peak, slowActions: out.slow, noTargets: out.noTargets, invariantViolations: out.inv.length, jsErrors: out.errs.length, crashes: out.crash.length,
  invariantSamples: uniq(out.inv).slice(0, 6), errorSamples: uniq(out.errs).slice(0, 6), crashSamples: out.crash.slice(0, 3) };
console.log(JSON.stringify(summary, null, 1));
import { writeFileSync, mkdirSync } from 'fs'; import path from 'path'; import { root } from './lib.mjs';
mkdirSync(path.join(root, 'docs/stress'), { recursive: true });
writeFileSync(path.join(root, 'docs/stress', `${app}-${N}u.json`), JSON.stringify(summary, null, 1));
process.exit(summary.invariantViolations + summary.jsErrors + summary.crashes ? 1 : 0);
