import { chromium } from '/Users/cucaramba/Claude Code/miniapps/tests/node_modules/playwright-core/index.mjs';
import fs from 'fs';
const dir = '/private/tmp/claude-501/-Users-cucaramba-Claude-Code/3b6d4bbe-9669-4e7a-b31d-12de453aedf1/scratchpad/';
const [label, tag] = process.argv.slice(2);
const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
const p = b.contexts()[0].pages().slice(-1)[0];
await p.goto('https://app2.trendsee.io/radar/', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(4000);
for (let i = 0; i < 4; i++) {
  const next = p.getByRole('button', { name: 'Далее' });
  if (await next.count()) { try { await next.first().click({ timeout: 1500 }); await p.waitForTimeout(500); } catch {} }
}
await p.getByText(label, { exact: true }).first().evaluate(el => el.click());
await p.waitForTimeout(5000);
for (let i = 0; i < 3; i++) {
  const next = p.getByRole('button', { name: 'Далее' });
  if (await next.count()) { try { await next.first().click({ timeout: 1500 }); await p.waitForTimeout(500); } catch {} }
}
await p.screenshot({ path: dir + `m_${tag}.png` });
const body = (await p.innerText('body')).replace(/\s+/g, ' ');
fs.writeFileSync(dir + `m_${tag}.txt`, body);
console.log('URL', p.url());
const i = body.indexOf('Осталось токенов');
console.log(body.slice(i, i + 2500));
await b.close();
