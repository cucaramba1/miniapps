import { chromium } from '/Users/cucaramba/Claude Code/miniapps/tests/node_modules/playwright-core/index.mjs';
import fs from 'fs';
const dir = '/private/tmp/claude-501/-Users-cucaramba-Claude-Code/3b6d4bbe-9669-4e7a-b31d-12de453aedf1/scratchpad/';
const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
const p = b.contexts()[0].pages().slice(-1)[0];
const tokens = async () => ((await p.innerText('body')).match(/Осталось токенов:?\s*(\d+)/) || [])[1];
const t0 = await tokens();
const vp = await p.evaluate(() => ({ width: window.innerWidth, height: window.innerHeight }));
await p.mouse.click(Math.round(1645 / 2000 * vp.width), Math.round(687 / 1088 * vp.height));
for (let i = 0; i < 20; i++) { await p.waitForTimeout(5000); const t = await p.innerText('body'); if (/слайд\s*1|Слайд 1/.test(t) && i > 3) break; }
await p.waitForTimeout(5000);
await p.screenshot({ path: dir + 'car_res2.png' });
const body = (await p.innerText('body')).replace(/\s+/g, ' ');
fs.writeFileSync(dir + 'car_res2.txt', body);
console.log('URL', p.url());
const i = body.indexOf('Осталось токенов');
console.log(body.slice(i, i + 3800));
console.log('tokens', t0, '->', await tokens());
await b.close();
