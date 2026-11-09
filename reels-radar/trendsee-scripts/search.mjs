import { chromium } from '/Users/cucaramba/Claude Code/miniapps/tests/node_modules/playwright-core/index.mjs';
import fs from 'fs';
const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
const p = b.contexts()[0].pages().slice(-1)[0];
const tokens = async () => ((await p.innerText('body')).match(/Осталось токенов:?\s*(\d+)/) || [])[1];
await p.goto('https://app2.trendsee.io/search', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(5000);
for (let i = 0; i < 4; i++) {
  const next = p.getByRole('button', { name: 'Далее' });
  if (await next.count()) { try { await next.first().click({ timeout: 1500 }); await p.waitForTimeout(500); } catch {} }
}
await p.getByText('Расширенный поиск', { exact: true }).first().click();
await p.waitForTimeout(1500);
const t0 = await tokens();
const box = p.getByPlaceholder('Найдем видео по словам в описании');
await box.click();
await box.fill('разбор анкет');
await p.screenshot({ path: 'se0.png' });
await p.getByRole('button', { name: /Найти/ }).first().click();
await p.waitForTimeout(15000);
await p.screenshot({ path: 'se1.png' });
const body = (await p.innerText('body')).replace(/\s+/g, ' ');
fs.writeFileSync('se1.txt', body);
console.log(body.slice(380, 2800));
console.log('tokens', t0, '->', await tokens());
await b.close();
