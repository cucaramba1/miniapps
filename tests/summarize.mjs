import { readFileSync } from 'fs'; import path from 'path'; import { root } from './lib.mjs';
const r = JSON.parse(readFileSync(path.join(root, 'docs/e2e-report.json')));
const g = {}; r.results.filter(x => !x.ok).forEach(x => { const k = x.app + ' | ' + x.name.replace(/^\S+@\S+ /, ''); (g[k] = g[k] || []).push(x.detail); });
console.log(`passed ${r.total - r.failed}/${r.total}`);
Object.entries(g).forEach(([k, v]) => console.log(v.length, k, '|', [...new Set(v)].slice(0, 3).join(' ## ')));
