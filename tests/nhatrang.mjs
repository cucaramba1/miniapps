// UI-тесты Нячанг Дом v2: поднимает тестовый сервер (поддельный бот, сид-данные), гасит его по PID.
// Запуск: cd tests && node nhatrang.mjs      (один тяжёлый прогон за раз, ноут на 8 ГБ)
// Отчёт: ../docs/nhatrang-report.json
import { spawn } from 'child_process';
import crypto from 'crypto';
import fs from 'fs';
import os from 'os';
import path from 'path';
import { launch, root, sleep, watch } from './lib.mjs';

const PORT = 8790, BASE = `http://127.0.0.1:${PORT}`, TOKEN = 'test-token', SECRET = 'test-webhook-secret';
const serverDir = path.join(root, 'nhatrang', 'server');
const dbDir = fs.mkdtempSync(path.join(os.tmpdir(), 'nd-ui-'));
const photos = [0, 1, 2].map(i => path.join(root, 'tests', 'fixtures', `photo${i}.jpg`));
const results = []; const t0 = Date.now();
const ok = (name, cond, extra = '') => { results.push({ name, pass: !!cond, extra: cond ? '' : String(extra) }); if (!cond) console.log('FAIL', name, extra); };

function startServer() {
  const py = path.join(serverDir, '.venv', 'bin', 'python');
  const p = spawn(py, ['-m', 'tools.test_server', String(PORT), dbDir], { cwd: serverDir, stdio: ['ignore', 'pipe', 'pipe'] });
  p.stderr.on('data', d => { if (process.env.VERBOSE) process.stderr.write(d); });
  return p;
}
async function waitHealth() {
  for (let i = 0; i < 60; i++) { try { const r = await fetch(BASE + '/api/health'); if (r.ok) return; } catch (e) { /* ещё не поднялся */ } await sleep(250); }
  throw new Error('сервер не поднялся');
}
function initData(userId) {
  const f = { auth_date: String(Math.floor(Date.now() / 1000)), query_id: 'AAH', user: JSON.stringify({ id: userId, first_name: 'Тест' }) };
  const check = Object.keys(f).sort().map(k => `${k}=${f[k]}`).join('\n');
  const sec = crypto.createHmac('sha256', 'WebAppData').update(TOKEN).digest();
  f.hash = crypto.createHmac('sha256', sec).update(check).digest('hex');
  return new URLSearchParams(f).toString();
}
async function webhook(update) {
  await fetch(BASE + '/api/bot/webhook', { method: 'POST', headers: { 'content-type': 'application/json', 'X-Telegram-Bot-Api-Secret-Token': SECRET }, body: JSON.stringify(update) });
}

const server = startServer();
let browser;
const errors = [];
try {
  await waitHealth();
  browser = await launch();
  const ctxFor = async (user, { w = 390, h = 844, geo, scheme = 'light', tg = false } = {}) => {
    const c = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme, permissions: geo ? ['geolocation'] : [], geolocation: geo });
    if (tg) {
      const data = initData(user);
      await c.addInitScript(({ data }) => {
        window.__invoice = { calls: [], cb: null };
        window.Telegram = { WebApp: { initData: data, colorScheme: 'light', ready() {}, expand() {}, disableVerticalSwipes() {},
          HapticFeedback: { impactOccurred() {} }, BackButton: { show() {}, hide() {}, onClick() {} },
          openInvoice(url, cb) { window.__invoice.calls.push(url); window.__invoice.cb = cb; }, openLink() {} } };
      }, { data });
    }
    // telegram-web-app.js из сети не нужен и перетирает мок: блокируем
    await c.route(/telegram\.org\/js/, r => r.fulfill({ status: 200, contentType: 'application/javascript', body: '' }));
    const page = await c.newPage(); watch(page, errors);
    return { c, page };
  };
  const open = async (user, opts = {}, p = '') => {
    const { c, page } = await ctxFor(user, opts);
    await page.goto(BASE + '/' + (opts.tg ? '' : `?dev=${user}`) + p);
    return { c, page };
  };
  const skipOnboard = async page => { for (let i = 0; i < 3; i++) await page.click('[data-testid=ob-next]'); await page.waitForSelector('#s-check.on'); };
  const onCount = page => page.$$eval('.screen.on', n => n.length);
  const text = page => page.evaluate(() => document.body.innerText + '\n' + document.documentElement.innerHTML);

  // ---------- Task 15: оболочка, вход, онбординг, навигация ----------
  {
    const { c, page } = await open(1001);
    ok('онбординг виден при первом запуске', await page.isVisible('#s-onboard.on'));
    await skipOnboard(page);
    ok('после онбординга открыт экран Проверить', await page.isVisible('#s-check.on'));
    await page.reload(); await page.waitForSelector('#s-check.on');
    ok('повторный запуск без онбординга', !(await page.isVisible('#s-onboard.on')));
    for (const t of ['check', 'free', 'realtors', 'favs', 'profile']) {
      await page.click(`[data-testid=tab-${t}]`); await page.waitForSelector(`#s-${t}.on`);
      ok(`таб ${t}: активен ровно один экран`, (await onCount(page)) === 1);
    }
    await c.close();
  }
  {
    const { c, page } = await ctxFor(1);
    await page.goto(BASE + '/'); await sleep(400);
    ok('без initData и без dev: экран «Откройте из Telegram»', await page.isVisible('#s-nopen.on'));
    await c.close();
  }
  {
    const { c, page } = await ctxFor(1);
    await page.goto(BASE + '/?dev=abc'); await sleep(400);
    ok('dev=нечисло не пускает', await page.isVisible('#s-nopen.on'));
    await c.close();
  }
  {
    const files = fs.readdirSync(path.join(root, 'nhatrang', 'js')).map(f => fs.readFileSync(path.join(root, 'nhatrang', 'js', f), 'utf8'));
    const all = files.join('\n') + fs.readFileSync(path.join(root, 'nhatrang', 'index.html'), 'utf8');
    ok('в js/ нет innerHTML/outerHTML/insertAdjacentHTML/document.write', !/innerHTML|outerHTML|insertAdjacentHTML|document\.write/.test(files.join('\n')));
    ok('нет длинного тире в интерфейсе', !all.includes('—'));
  }

  // ---------- Task 16: Проверить жильё ----------
  {
    const { c, page } = await open(1001); await skipOnboard(page);
    await page.waitForSelector('[data-testid=place-card]');
    ok('карточки мест загружены', (await page.$$('[data-testid=place-card]')).length === 4);
    await page.fill('[data-testid=chk-q]', 'vinh hai'); await sleep(700);
    const names = await page.$$eval('[data-testid=place-card] h3', n => n.map(x => x.textContent));
    ok('поиск «vinh hai» находит место с диакритикой', names.length === 1 && names[0] === 'Vĩnh Hải Hotel', names);
    await page.fill('[data-testid=chk-q]', ''); await sleep(700);
    ok('XSS-название отображено текстом', (await page.$$eval('[data-testid=place-card] h3', n => n.map(x => x.textContent))).includes('<img src=x onerror=window.__xss=1>'));
    ok('XSS не сработал', !(await page.evaluate(() => window.__xss)));
    const hasL = await page.evaluate(() => typeof L !== 'undefined');
    ok('Leaflet загружен (cdnjs)', hasL);
    if (hasL) {
      await sleep(300);
      ok('на карте подпись района из фикстуры', (await page.$$eval('.dist-label', n => n.map(x => x.textContent))).includes('Тестовый район'));
    }
    // карточка без доступа
    await page.fill('[data-testid=chk-q]', 'vinh'); await sleep(700);
    await page.click('[data-testid=place-card]'); await page.waitForSelector('#s-place.on [data-testid=tag-counts]');
    let t = await text(page);
    ok('без доступа в DOM нет текста отзыва', !t.includes('УНИКАЛЬНЫЙ_ТЕКСТ'));
    ok('без доступа есть счётчики жалоб', (await page.textContent('[data-testid=tag-counts]')).includes('Шум'));
    ok('без доступа есть блок оплаты', await page.isVisible('[data-testid=locked-block]'));
    await c.close();
  }
  {
    const { c, page } = await open(1001); await skipOnboard(page);
    await page.fill('[data-testid=chk-q]', 'пустое'); await sleep(700);
    await page.click('[data-testid=place-card]'); await page.waitForSelector('#s-place.on [data-testid=empty-note]');
    ok('пустое место: честная плашка', await page.isVisible('[data-testid=empty-note]'));
    ok('пустое место: нет кнопки оплаты', (await page.$$('#s-place [data-testid=unlock]')).length === 0);
    await c.close();
  }
  {
    const { c, page } = await open(1002); await skipOnboard(page);
    await page.fill('[data-testid=chk-q]', 'vinh'); await sleep(700);
    await page.click('[data-testid=place-card]'); await page.waitForSelector('#s-place.on [data-testid=review]');
    ok('с доступом видны тексты отзывов', (await text(page)).includes('УНИКАЛЬНЫЙ_ТЕКСТ_ОТЗЫВА_ОДИН'));
    await c.close();
  }

  // ---------- Task 18: Свободно, Риелторы, Избранное ----------
  {
    const { c, page } = await open(1001); await skipOnboard(page);
    await page.click('[data-testid=tab-free]'); await page.waitForSelector('[data-testid=listing]');
    let t = await text(page);
    ok('Свободно без доступа: нет ников и ссылок', !t.includes('seed_agent') && !t.includes('example.test/post'));
    ok('Свободно без доступа: есть кнопка открытия', (await page.$$('#s-free [data-testid=unlock]')).length === 2);
    ok('HTML в названии объявления показан текстом', (await page.$$eval('[data-testid=listing] h3', n => n.map(x => x.textContent))).includes('Студия <b>без привязки</b>'));
    await page.click('[data-testid=only-place]'); await sleep(500);
    ok('фильтр «только с местом» оставляет одно', (await page.$$('[data-testid=listing]')).length === 1);
    await page.click('[data-testid=tab-realtors]'); await page.waitForSelector('[data-testid=realtor]');
    t = await text(page);
    ok('Риелторы без доступа: нет контактов', !t.includes('seed_realtor') && !t.includes('0900000001'));
    ok('метка «без комиссии» ровно у одного (подтверждённого)', (await page.$$eval('#s-realtors .pill', n => n.filter(x => x.textContent.includes('Без комиссии')).length)) === 1);
    await c.close();
  }
  {
    const { c, page } = await open(1002); await skipOnboard(page);
    await page.click('[data-testid=tab-free]'); await page.waitForSelector('[data-testid=contacts]');
    ok('Свободно с доступом: контакты есть', (await text(page)).includes('seed_agent_nick'));
    await page.click('[data-testid=tab-realtors]'); await page.waitForSelector('[data-testid=realtor]');
    ok('Риелторы с доступом: контакты есть', (await text(page)).includes('seed_realtor_nick'));
    // избранное
    await page.click('[data-testid=tab-check]'); await page.fill('[data-testid=chk-q]', 'vinh'); await sleep(700);
    await page.click('[data-testid=place-card]'); await page.waitForSelector('[data-testid=fav]');
    await page.click('[data-testid=fav]'); await sleep(400);
    await page.click('[data-testid=tab-favs]'); await page.waitForSelector('#s-favs [data-testid=place-card]');
    ok('избранное: место появилось', (await page.$$('#s-favs [data-testid=place-card]')).length === 1);
    await c.close();
  }
  {
    const { c, page } = await open(1003); await skipOnboard(page);
    await page.click('[data-testid=tab-favs]'); await page.waitForSelector('#s-favs .empty');
    ok('избранное: пустое состояние, не пустой экран', await page.isVisible('#s-favs .empty'));
    await c.close();
  }

  // ---------- Task 18/16: флажки ----------
  {
    const { c, page } = await open(1001); await skipOnboard(page);
    if (await page.evaluate(() => typeof L !== 'undefined')) {
      await page.waitForSelector('#chk-map .leaflet-container, #chk-map.leaflet-container'); await sleep(500);
      await page.click('[data-testid=chk-flag]');
      const box = await page.locator('[data-testid=chk-map]').boundingBox();
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2 + 30);
      await page.waitForSelector('[data-testid=flag-label]');
      await page.fill('[data-testid=flag-label]', 'Хороший кофе'); await page.click('[data-testid=flag-save]'); await sleep(600);
      const flags = await page.evaluate(async () => (await fetch('/api/flags', { headers: { 'X-Dev-User': '1001' } })).json());
      ok('флажок сохранён на сервере', flags.length === 1 && flags[0].label === 'Хороший кофе');
      await page.reload(); await page.waitForSelector('#s-check.on'); await sleep(600);
      const again = await page.evaluate(async () => (await fetch('/api/flags', { headers: { 'X-Dev-User': '1001' } })).json());
      ok('флажок после перезагрузки на месте', again.length === 1);
      await page.evaluate(id => fetch('/api/flags/' + id, { method: 'DELETE', headers: { 'X-Dev-User': '1001' } }), flags[0].id);
    } else ok('флажки: Leaflet недоступен, пропуск', false, 'нет сети до cdnjs');
    await c.close();
  }

  // ---------- Task 17: отзыв ----------
  const PLACE = { latitude: 12.2388, longitude: 109.1967, accuracy: 10 };
  const gotoReview = async (page, query) => {
    await page.fill('[data-testid=chk-q]', query); await sleep(700);
    await page.click('[data-testid=place-card]'); await page.waitForSelector('[data-testid=write-review]');
    await page.click('[data-testid=write-review]'); await page.waitForSelector('[data-testid=rv-submit]');
  };
  {
    const { c, page } = await open(1001, { geo: PLACE }); await skipOnboard(page);
    await gotoReview(page, 'vinh'); await sleep(600);
    ok('геопозиция: «вы в N м»', (await page.textContent('[data-testid=rv-geo]')).includes('Подходит'), await page.textContent('[data-testid=rv-geo]'));
    await page.click('[data-testid=rv-star-4]');
    await page.fill('[data-testid=rv-text]', 'а'.repeat(149));
    await page.setInputFiles('[data-testid=rv-file]', [photos[0], photos[1]]);
    ok('149 символов: кнопка отправки неактивна', await page.isDisabled('[data-testid=rv-submit]'));
    await page.fill('[data-testid=rv-text]', 'а'.repeat(150));
    ok('150 символов: кнопка активна', !(await page.isDisabled('[data-testid=rv-submit]')));
    await page.fill('[data-testid=rv-text]', '😀'.repeat(150));
    ok('150 эмодзи (по символам, не по UTF-16): активна', !(await page.isDisabled('[data-testid=rv-submit]')));
    await page.fill('[data-testid=rv-text]', 'а'.repeat(150));
    // убрать одно фото
    await page.click('[data-testid=rv-photos] button'); await sleep(100);
    ok('1 фото: кнопка неактивна', await page.isDisabled('[data-testid=rv-submit]'));
    await page.setInputFiles('[data-testid=rv-file]', [photos[2]]);
    await page.click('[data-testid=rv-submit]'); await page.waitForSelector('[data-testid=rv-done]');
    ok('успешная отправка показывает «+3 дня»', (await page.textContent('[data-testid=rv-done]')).includes('+3 дня'));
    const me = await page.evaluate(async () => (await fetch('/api/me', { headers: { 'X-Dev-User': '1001' } })).json());
    ok('после отзыва доступ открыт', me.has_access === true);
    // второй отзыв в тот же день на другое место: лимит
    await page.click('text=К месту'); await page.click('[data-testid=tab-check]');
    await gotoReview(page, 'sunrise'); await sleep(500);
    await page.click('[data-testid=rv-star-3]'); await page.fill('[data-testid=rv-text]', 'б'.repeat(150));
    await page.setInputFiles('[data-testid=rv-file]', [photos[0], photos[1]]);
    ok('геопозиция далеко от другого места', (await page.textContent('[data-testid=rv-geo]')).includes('далеко'));
    await c.close();
  }
  {
    const { c, page } = await open(1003, { geo: { latitude: 12.2388 + 0.0045, longitude: 109.1967, accuracy: 10 } }); await skipOnboard(page);
    await gotoReview(page, 'vinh'); await sleep(600);
    ok('~500 м от места: «вы далеко»', (await page.textContent('[data-testid=rv-geo]')).includes('далеко'));
    await c.close();
  }
  {
    // дневной лимит: пользователь 1004 пишет на пустое место (рядом), потом на второе рядом (одна точка нельзя, ставим координаты второго)
    const { c, page } = await open(1004, { geo: { latitude: 12.2300, longitude: 109.1900, accuracy: 10 } }); await skipOnboard(page);
    await gotoReview(page, 'пустое'); await sleep(500);
    await page.click('[data-testid=rv-star-5]'); await page.fill('[data-testid=rv-text]', 'в'.repeat(150));
    await page.setInputFiles('[data-testid=rv-file]', [photos[0], photos[1]]);
    await page.click('[data-testid=rv-submit]'); await page.waitForSelector('[data-testid=rv-done]');
    await c.setGeolocation({ latitude: 12.2400, longitude: 109.1980, accuracy: 10 });
    await page.click('text=К месту'); await page.click('[data-testid=tab-check]');
    await gotoReview(page, 'img src'); await sleep(500);
    await page.click('[data-testid=rv-locate]'); await sleep(400);
    await page.click('[data-testid=rv-star-3]'); await page.fill('[data-testid=rv-text]', 'г'.repeat(150));
    await page.setInputFiles('[data-testid=rv-file]', [photos[1], photos[2]]);
    await page.click('[data-testid=rv-submit]'); await sleep(800);
    ok('второй отзыв в день: человеческий текст про лимит', (await page.textContent('[data-testid=rv-msg]')).includes('Сегодня вы уже оставили отзыв'), await page.textContent('[data-testid=rv-msg]'));
    await c.close();
  }
  {
    // добавить место
    const { c, page } = await open(1005, { geo: PLACE }); await skipOnboard(page);
    await page.click('[data-testid=add-place]'); await page.waitForSelector('[data-testid=ap-name]');
    await page.fill('[data-testid=ap-name]', 'Новый Хостел Тест');
    ok('добавление места: без точки кнопка неактивна', await page.isDisabled('[data-testid=ap-save]'));
    if (await page.evaluate(() => typeof L !== 'undefined')) {
      await page.waitForSelector('[data-testid=ap-map].leaflet-container'); await sleep(400);
      const box = await page.locator('[data-testid=ap-map]').boundingBox();
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2); await sleep(200);
      await page.click('[data-testid=ap-save]'); await page.waitForSelector('[data-testid=ap-done]');
      ok('новое место: «на проверке»', (await page.textContent('[data-testid=ap-done]')).includes('на проверке'));
    }
    await c.close();
  }

  // ---------- Task 19: оплата и профиль ----------
  {
    const { c, page } = await open(1006); await skipOnboard(page);
    await page.click('[data-testid=tab-profile]'); await page.waitForSelector('[data-testid=access-card]');
    ok('профиль без доступа: «Доступа нет»', (await page.textContent('[data-testid=access-card]')).includes('Доступа нет'));
    await page.click('[data-testid=to-pay]'); await page.waitForSelector('[data-testid=plan-d3]');
    ok('paywall: два тарифа', (await page.$$('[data-testid^=plan-]')).length === 2);
    ok('paywall: цена 300 Stars', (await page.textContent('[data-testid=plan-d3]')).includes('300'));
    await page.click('[data-testid=pay-btn]'); await sleep(300);
    ok('вне Telegram оплата сообщает «откройте из Telegram»', (await page.textContent('[data-testid=pay-msg]')).includes('Telegram'));
    ok('нет карты и QR Bybit', !(await text(page)).match(/Bybit|Номер карты/));
    await c.close();
  }
  for (const status of ['paid', 'cancelled', 'failed']) {
    const uid = 2000 + ['paid', 'cancelled', 'failed'].indexOf(status);
    const { c, page } = await open(uid, { tg: true }); await skipOnboard(page);
    await page.click('[data-testid=tab-profile]'); await page.click('[data-testid=to-pay]'); await page.waitForSelector('[data-testid=pay-btn]');
    await page.click('[data-testid=pay-btn]');
    await page.waitForFunction(() => window.__invoice.calls.length === 1);
    const url = await page.evaluate(() => window.__invoice.calls[0]);
    ok(`оплата ${status}: invoice от сервера с payload плана`, url.includes(`d3:${uid}`) && url.endsWith('_300'), url);
    if (status === 'paid') {
      await webhook({ message: { from: { id: uid }, chat: { id: uid }, successful_payment: { currency: 'XTR', total_amount: 300, invoice_payload: `d3:${uid}`, telegram_payment_charge_id: 'ui-' + uid } } });
    }
    await page.evaluate(s => window.__invoice.cb(s), status); await sleep(500);
    if (status === 'paid') {
      await page.waitForSelector('[data-testid=pay-done]');
      ok('оплата paid: экран «Доступ открыт»', (await page.textContent('[data-testid=pay-done]')).includes('Доступ открыт'));
      await page.click('[data-testid=tab-profile]').catch(() => {});
    } else if (status === 'cancelled') {
      ok('оплата cancelled: остаёмся на paywall без изменений', await page.isVisible('[data-testid=pay-btn]') && (await page.textContent('[data-testid=pay-msg]')).includes('отменена'));
    } else {
      ok('оплата failed: ошибка и «Повторить»', await page.isVisible('[data-testid=pay-fail]') && await page.isVisible('[data-testid=pay-retry]'));
    }
    await c.close();
  }

  // ---------- раскладка: ширины × темы ----------
  const SCREENS = ['check', 'free', 'realtors', 'favs', 'profile', 'pay', 'place', 'review', 'addplace'];
  for (const w of [360, 390, 430]) for (const scheme of ['light', 'dark']) {
    const { c, page } = await open(1002, { w, scheme, geo: PLACE }); await skipOnboard(page);
    for (const id of SCREENS) {
      await page.evaluate(([id]) => tgx.go(id, { params: { id: 1 } }), [id]); await sleep(450);
      const r = await page.evaluate(id => {
        const el = document.getElementById('s-' + id);
        const small = [...el.querySelectorAll('button,a,input,select,textarea')].filter(b => { const r = b.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.height < 36 && !b.closest('.leaflet-container') && b.type !== 'file'; }).map(b => (b.textContent || b.placeholder || b.tagName).slice(0, 20));
        return { on: document.querySelectorAll('.screen.on').length, active: el.classList.contains('on'), overflow: el.scrollWidth > el.clientWidth + 1, textLen: el.innerText.trim().length, small };
      }, id);
      ok(`раскладка ${id} ${w}px ${scheme}: один активный экран`, r.on === 1 && r.active, JSON.stringify(r));
      ok(`раскладка ${id} ${w}px ${scheme}: нет горизонтального скролла`, !r.overflow);
      ok(`раскладка ${id} ${w}px ${scheme}: не пустой`, r.textLen > 5);
      ok(`раскладка ${id} ${w}px ${scheme}: тап-зоны от 36px`, r.small.length === 0, r.small.join(','));
    }
    await c.close();
  }
} catch (e) {
  ok('прогон без исключений', false, e.stack || e.message);
} finally {
  if (browser) await browser.close();
  server.kill('SIGTERM'); await sleep(500);
  const alive = (() => { try { process.kill(server.pid, 0); return true; } catch (e) { return false; } })();
  if (alive) server.kill('SIGKILL');
  fs.rmSync(dbDir, { recursive: true, force: true });
}
ok('нет ошибок в консоли/pageerror', errors.length === 0, errors.slice(0, 5).join(' | '));
const failed = results.filter(r => !r.pass);
fs.mkdirSync(path.join(root, 'docs'), { recursive: true });
fs.writeFileSync(path.join(root, 'docs', 'nhatrang-report.json'), JSON.stringify({ total: results.length, failed: failed.length, secs: Math.round((Date.now() - t0) / 1000), results }, null, 1));
console.log(`nhatrang: ${results.length - failed.length}/${results.length} pass, ${failed.length} FAIL, ${Math.round((Date.now() - t0) / 1000)} c`);
process.exit(failed.length ? 1 : 0);
