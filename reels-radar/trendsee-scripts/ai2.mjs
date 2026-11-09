import { chromium } from '/Users/cucaramba/Claude Code/miniapps/tests/node_modules/playwright-core/index.mjs';
import fs from 'fs';
const dir = '/private/tmp/claude-501/-Users-cucaramba-Claude-Code/3b6d4bbe-9669-4e7a-b31d-12de453aedf1/scratchpad/';
const [query, tag, platform] = process.argv.slice(2);
const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
const p = b.contexts()[0].pages().slice(-1)[0];
await p.goto('https://app2.trendsee.io/search/ai', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(4000);
for (let i = 0; i < 4; i++) {
  const next = p.getByRole('button', { name: 'Далее' });
  if (await next.count()) { try { await next.first().click({ timeout: 1500 }); await p.waitForTimeout(500); } catch {} }
}
await p.getByText('Instagram', { exact: true }).first().click({ timeout: 3000 });
await p.waitForTimeout(800);
await p.getByText(platform, { exact: true }).first().click();
const box = p.getByPlaceholder(/Например/);
await box.click();
await box.fill(query);
await p.getByRole('button', { name: /Найти/ }).first().click();
let body = '';
for (let i = 0; i < 30; i++) {
  await p.waitForTimeout(5000);
  body = (await p.innerText('body')).replace(/\s+/g, ' ');
  if (body.includes('Время поиска')) break;
}
await p.waitForTimeout(3000);
await p.screenshot({ path: dir + `ai2_${tag}.png` });
body = (await p.innerText('body')).replace(/\s+/g, ' ');
fs.writeFileSync(dir + `ai2_${tag}.txt`, body);
const i = body.indexOf('Осталось', body.indexOf('AI Поиск'));
console.log(body.slice(i, i + 4800));
console.log('TOK', (body.match(/Осталось токенов:?\s*(\d+)/) || [])[1]);
await b.close();
