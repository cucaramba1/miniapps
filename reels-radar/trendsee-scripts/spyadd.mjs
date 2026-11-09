import { chromium } from '/Users/cucaramba/Claude Code/miniapps/tests/node_modules/playwright-core/index.mjs';
const dir = '/private/tmp/claude-501/-Users-cucaramba-Claude-Code/3b6d4bbe-9669-4e7a-b31d-12de453aedf1/scratchpad/';
const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
const p = b.contexts()[0].pages().slice(-1)[0];
const tokens = async () => ((await p.innerText('body')).match(/Осталось токенов:?\s*(\d+)/) || [])[1];
await p.goto('https://app2.trendsee.io/spy', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(4000);
const t0 = await tokens();
// закрыть тур крестиком
try { await p.locator('button:has(svg)').filter({ hasText: '' }).first(); } catch {}
await p.getByRole('button', { name: /Добавить блогера/ }).first().evaluate(el => el.click());
await p.waitForTimeout(3000);
await p.screenshot({ path: dir + 'spy_add.png' });
const body = (await p.innerText('body')).replace(/\s+/g, ' ');
console.log(body.slice(body.indexOf('Шпионаж', 300), body.indexOf('Шпионаж', 300) + 1800));
console.log('tokens', t0, '->', await tokens());
await b.close();
