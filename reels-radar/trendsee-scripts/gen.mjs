import { chromium } from '/Users/cucaramba/Claude Code/miniapps/tests/node_modules/playwright-core/index.mjs';
import fs from 'fs';
const [trend, ctx, tag] = process.argv.slice(2);
const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
const p = b.contexts()[0].pages().slice(-1)[0];
const tokens = async () => ((await p.innerText('body')).match(/Осталось токенов:?\s*(\d+)/) || [])[1];
await p.goto('https://app2.trendsee.io/trends', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(5000);
for (let i = 0; i < 4; i++) {
  const next = p.getByRole('button', { name: 'Далее' });
  if (await next.count()) { try { await next.first().click({ timeout: 1500 }); await p.waitForTimeout(500); } catch {} }
}
await p.getByText('Все ниши', { exact: true }).first().click();
await p.waitForTimeout(1000);
await p.getByText('Психология отношений').first().click();
await p.waitForTimeout(3500);
await p.getByText(trend, { exact: true }).first().click({ timeout: 8000 });
await p.waitForTimeout(3500);
await p.getByRole('button', { name: /Адаптировать под мою нишу/ }).first().click();
await p.waitForTimeout(5000);
const t0 = await tokens();
const box = p.getByPlaceholder('Дополнительный контекст (необязательно)');
await box.click();
await box.fill(ctx);
const vp = await p.evaluate(() => ({ width: window.innerWidth, height: window.innerHeight }));
await p.mouse.click(Math.round(1617 / 2000 * vp.width), Math.round(1018 / 1088 * vp.height));
await p.waitForTimeout(45000);
await p.screenshot({ path: `gen_${tag}.png` });
const body = (await p.innerText('body')).replace(/\s+/g, ' ');
fs.writeFileSync(`gen_${tag}.txt`, body);
const m = body.match(/(\d+) слов(?:а)? [•(] ?\(?(\d+) секунд/);
console.log('TREND', trend, '| counter:', m ? `${m[1]} слов, ${m[2]} сек` : 'не найден');
const i = body.indexOf('Сценарий:');
console.log(body.slice(i, i + 1800));
console.log('tokens', t0, '->', await tokens());
await b.close();
