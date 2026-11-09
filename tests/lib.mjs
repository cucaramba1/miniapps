import { chromium } from 'playwright-core';
import { pathToFileURL } from 'url';
import path from 'path';
export const root = path.resolve(import.meta.dirname, '..');
// nhatrang (v2, с сервером) гоняется отдельно: nhatrang.mjs и stress.mjs nhatrang
export const APPS = ['reels-radar', 'faceless'];
export const SAMPLE = { trend: 't1', author: 'a1', video: 'v1' };
const exe = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell';
export const launch = () => chromium.launch({ executablePath: exe });
export const urlOf = app => pathToFileURL(path.join(root, app, 'index.html')).href;

/** Attach error collectors. Страница сама грузит telegram-web-app.js: в e2e он реально приходит из сети (initData пустой, значит мок-ветка), в telegram-real.mjs подменяется. */
export function watch(page, sink) {
  page.on('pageerror', e => sink.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error' && !/telegram\.org|ERR_(INTERNET|NAME|FAILED|BLOCKED)|Failed to load resource/i.test(m.text())) sink.push('console: ' + m.text()); });
}
export const sleep = ms => new Promise(r => setTimeout(r, ms));

/** Mulberry32 seeded rng for reproducible stress runs. */
export function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
