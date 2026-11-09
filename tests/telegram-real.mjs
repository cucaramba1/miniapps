// node telegram-real.mjs [app]  -> проверки ветки "настоящий Telegram.WebApp" из shared/tgx.js (e2e/stress гоняют только мок).
// Подставляет поддельный window.Telegram.WebApp с initData ДО загрузки страницы и проверяет:
//  boot      ready/expand/disableVerticalSwipes по одному разу, тема от colorScheme, без рамки и без шапки-имитации, без ошибок
//  haptic    навигация вызывает HapticFeedback.impactOccurred
//  back      на каждом не-табовом экране есть способ вернуться: видимый [data-back] или Telegram BackButton.show()
//  nativeback системная кнопка Telegram следует стеку экранов: видна на глубоком, нажатие возвращает, на корне скрыта
//  safearea  нижние плавающие элементы (tabbar, mainbtn) отъезжают вверх при --tg-safe-area-inset-bottom (iPhone, полоса жестов)
//  clipboard отказ navigator.clipboard не роняет страницу и даёт сообщение
//  offline   без сети и без telegram-web-app.js приложение стартует
// Отчёт: ../docs/telegram-real-report.json. Код выхода 1, если есть провалы.
import { launch, APPS, SAMPLE, urlOf, watch, sleep, root } from './lib.mjs';
import { writeFileSync } from 'fs';
import path from 'path';

const ONLY = process.argv[2];
const results = [];
const rec = (app, suite, name, ok, detail = '') => { results.push({ app, suite, name, ok: !!ok, detail }); if (!ok) console.log('  FAIL', app, suite, name, detail); };

const FAKE_TG = `(() => {
  const log = { ready: 0, expand: 0, swipes: 0, haptics: [], back: [], backClick: 0 };
  window.__tglog = log;
  window.Telegram = { WebApp: {
    initData: 'query_id=AAHtest&user=%7B%22id%22%3A1%7D&hash=deadbeef', initDataUnsafe: {}, colorScheme: 'dark', platform: 'ios', version: '8.0',
    ready() { log.ready++; }, expand() { log.expand++; }, disableVerticalSwipes() { log.swipes++; },
    HapticFeedback: { impactOccurred(k) { log.haptics.push(k); } },
    BackButton: { isVisible: false, show() { this.isVisible = true; log.back.push('show'); }, hide() { this.isVisible = false; log.back.push('hide'); }, onClick(fn) { log.backClick++; log.backFn = fn; }, offClick() {} },
    MainButton: { show() {}, hide() {}, setText() {}, onClick() {}, offClick() {} },
    onEvent() {}, offEvent() {}, close() {}, openLink() {}
  } };
})();`;

async function fresh(browser, app, { w = 390, h = 844, scheme = 'light' } = {}) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme });
  // страница сама грузит https://telegram.org/js/telegram-web-app.js и он затёр бы подделку: отдаём вместо него свой
  await ctx.route('**/telegram-web-app.js', r => r.fulfill({ contentType: 'application/javascript', body: FAKE_TG }));
  const page = await ctx.newPage(); const errs = []; watch(page, errs);
  await page.goto(urlOf(app)); await sleep(250);
  return { ctx, page, errs };
}

async function suiteApp(browser, app) {
  // boot + haptic
  {
    const { ctx, page, errs } = await fresh(browser, app, { scheme: 'light' });
    const s = await page.evaluate(() => ({
      log: window.__tglog, theme: document.documentElement.dataset.theme, frame: document.body.classList.contains('frame'),
      bar: getComputedStyle(document.getElementById('tgbar')).display, ids: window.__app.ids(), cur: window.__app.state.current
    }));
    rec(app, 'boot', 'ready() ровно один раз', s.log.ready === 1, `ready=${s.log.ready}`);
    rec(app, 'boot', 'expand() ровно один раз', s.log.expand === 1, `expand=${s.log.expand}`);
    rec(app, 'boot', 'disableVerticalSwipes() вызван', s.log.swipes === 1, `swipes=${s.log.swipes}`);
    rec(app, 'boot', 'тема от colorScheme=dark при светлой системной', s.theme === 'dark', `theme=${s.theme}`);
    rec(app, 'boot', 'нет рамки-телефона (.frame)', !s.frame);
    rec(app, 'boot', 'нет шапки-имитации #tgbar', s.bar === 'none', `display=${s.bar}`);
    rec(app, 'boot', 'без ошибок в консоли', errs.length === 0, errs.slice(0, 2).join(' | '));
    const h0 = s.log.haptics.length;
    const next = await page.evaluate(() => window.__app.ids().find(i => i !== window.__app.state.current && window.__app.screens[i].tab));
    await page.evaluate(([i, S]) => window.__app.go(i, { params: { id: S[i] || '' } }), [next, SAMPLE]); await sleep(200);
    const h1 = await page.evaluate(() => window.__tglog.haptics.length);
    rec(app, 'haptic', 'переход экрана вызывает impactOccurred', h1 > h0, `${h0}->${h1}`);
    await ctx.close();
  }
  // back на каждом не-табовом экране
  {
    const { ctx, page, errs } = await fresh(browser, app);
    const info = await page.evaluate(() => ({ ids: window.__app.ids(), tabs: Object.fromEntries(Object.entries(window.__app.screens).map(([k, v]) => [k, !!v.tab])), parent: Object.fromEntries(Object.entries(window.__app.screens).map(([k, v]) => [k, !!v.parentTab])), start: window.__app.state.current }));
    const home = info.ids.find(i => info.tabs[i]) || info.start;
    for (const id of info.ids) {
      if (info.tabs[id]) continue;
      await page.evaluate(([h, i, s]) => { window.__app.go(h, {}); window.__tglog.back.length = 0; window.__app.go(i, { params: { id: s } }); }, [home, id, SAMPLE[id] || '']);
      await sleep(250);
      const r = await page.evaluate(() => {
        const el = document.querySelector('.screen.on');
        const vis = n => { const r = n.getBoundingClientRect(); const cs = getComputedStyle(n); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
        const inPage = el ? [...el.querySelectorAll('[data-back]')].some(vis) : false;
        const native = window.__tglog.back.includes('show');
        // служебные экраны (оплата, ошибка, готово) выходят через кнопку-действие, это тоже выход
        const exits = el ? [...el.querySelectorAll('[data-go],[data-act],button:not([disabled])')].filter(vis).length : 0;
        const main = document.getElementById('mainbtn')?.classList.contains('show') || false;
        const tabs = !document.querySelector('.tabbar')?.classList.contains('hidden');
        return { cur: window.__app.state.current, depth: window.__app.state.stack.length, inPage, native, exits, main, tabs };
      });
      if (r.cur !== id) { rec(app, 'back', `${id}: экран открылся`, false, `открыт ${r.cur}`); continue; }
      // явная кнопка назад обязательна только на содержательных экранах (parentTab), служебные (старт, ожидание, итог) выходят действием
      if (info.parent[id]) rec(app, 'back', `${id}: есть способ вернуться`, r.inPage || r.native, `data-back=${r.inPage} BackButton.show=${r.native}`);
      rec(app, 'deadend', `${id}: не тупик (есть хоть какой-то выход)`, r.inPage || r.native || r.exits > 0 || r.main || r.tabs, `кнопок-выходов=${r.exits} main=${r.main} табы=${r.tabs}`);
    }
    rec(app, 'back', 'без ошибок при обходе экранов', errs.length === 0, errs.slice(0, 2).join(' | '));
    await ctx.close();
  }
  // нативный BackButton
  {
    const { ctx, page, errs } = await fresh(browser, app);
    const info = await page.evaluate(() => ({ tab: window.__app.ids().find(i => window.__app.screens[i].tab), deep: window.__app.ids().find(i => window.__app.screens[i].parentTab) }));
    const st = async () => page.evaluate(() => ({ cur: window.__app.state.current, vis: window.Telegram.WebApp.BackButton.isVisible }));
    await page.evaluate(([h]) => window.__app.go(h, {}), [info.tab]); await sleep(150);
    const root = await st();
    await page.evaluate(([d, S]) => window.__app.go(d, { params: { id: S[d] || '' } }), [info.deep, SAMPLE]); await sleep(150);
    const deep = await st();
    const hasHandler = await page.evaluate(() => typeof window.__tglog.backFn === 'function');
    if (hasHandler) await page.evaluate(() => window.__tglog.backFn());
    await sleep(150);
    const after = await st();
    rec(app, 'nativeback', 'скрыта на корневом экране', root.vis === false, `visible=${root.vis}`);
    rec(app, 'nativeback', 'видна на глубоком экране', deep.vis === true, `${info.deep}: visible=${deep.vis}`);
    rec(app, 'nativeback', 'onClick зарегистрирован', hasHandler);
    rec(app, 'nativeback', 'нажатие возвращает на предыдущий экран и скрывает кнопку', after.cur === info.tab && after.vis === false, `cur=${after.cur} visible=${after.vis}`);
    rec(app, 'nativeback', 'без ошибок', errs.length === 0, errs.slice(0, 2).join(' | '));
    await ctx.close();
  }
  // safe-area: тянем нижний инсет и смотрим, поднимаются ли плавающие элементы (iPhone, полоса жестов ~34px)
  {
    const { ctx, page } = await fresh(browser, app);
    const gap = (sel, inset) => page.evaluate(async ([s, v]) => {
      document.documentElement.style.setProperty('--tg-safe-area-inset-bottom', v + 'px');
      document.documentElement.style.setProperty('--tg-content-safe-area-inset-bottom', '0px');
      await new Promise(r => setTimeout(r, 60));
      const n = document.querySelector(s); const r = n && n.getBoundingClientRect();
      return n && r.height > 0 && getComputedStyle(n).display !== 'none' ? Math.round(innerHeight - r.bottom) : null;
    }, [sel, inset]);
    const found = await page.evaluate(([S]) => {
      const out = { tab: null, main: null };
      for (const id of window.__app.ids()) {
        const d = window.__app.screens[id];
        try { window.__app.go(id, { params: { id: S[id] || '' } }); } catch (e) { continue; }
        if (!out.tab && !document.querySelector('.tabbar')?.classList.contains('hidden')) out.tab = id;
        if (!out.main && document.getElementById('mainbtn')?.classList.contains('show')) out.main = id;
      }
      return out;
    }, [SAMPLE]);
    for (const [k, sel, scr] of [['tabbar', '.tabbar', found.tab], ['mainbtn', '#mainbtn', found.main]]) {
      if (!scr) { rec(app, 'safearea', `${k}: экран для замера найден`, false, 'нет экрана, где элемент виден'); continue; }
      await page.evaluate(([i, S]) => window.__app.go(i, { params: { id: S[i] || '' } }), [scr, SAMPLE]); await sleep(300);
      const g0 = await gap(sel, 0), g34 = await gap(sel, 34);
      rec(app, 'safearea', `${k} (экран ${scr}): поднимается при инсете 34px`, g0 !== null && g34 - g0 >= 30, `зазор снизу ${g0}px -> ${g34}px`);
    }
    await ctx.close();
  }
  // clipboard denied
  {
    const { ctx, page, errs } = await fresh(browser, app);
    const r = await page.evaluate(async () => {
      Object.defineProperty(navigator, 'clipboard', { value: { writeText: () => Promise.reject(new DOMException('denied', 'NotAllowedError')) }, configurable: true });
      document.execCommand = () => false;
      tgx.copy('test'); await new Promise(r => setTimeout(r, 200));
      return document.getElementById('toast')?.textContent || '';
    });
    rec(app, 'clipboard', 'отказ буфера даёт сообщение, не падает', /Не удалось/.test(r) && errs.length === 0, `toast="${r}" errs=${errs.length}`);
    await ctx.close();
  }
  // offline + без telegram-web-app.js
  {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, offline: true });
    const page = await ctx.newPage(); const errs = []; watch(page, errs);
    await page.goto(urlOf(app)); await sleep(300);
    const ok = await page.evaluate(() => !!window.__app && document.querySelectorAll('.screen.on').length === 1);
    rec(app, 'offline', 'старт без сети и без Telegram-скрипта', ok && errs.length === 0, errs.slice(0, 2).join(' | '));
    await ctx.close();
  }
}

const t0 = Date.now();
const b = await launch();
for (const a of APPS) { if (ONLY && a !== ONLY) continue; console.log('app', a); await suiteApp(b, a); }
await b.close();
const fails = results.filter(r => !r.ok);
writeFileSync(path.join(root, 'docs', 'telegram-real-report.json'), JSON.stringify({ at: new Date().toISOString(), total: results.length, fails: fails.length, results }, null, 1));
for (const a of APPS) { const r = results.filter(x => x.app === a); if (r.length) console.log(a.padEnd(12), `${r.filter(x => x.ok).length}/${r.length}`); }
console.log(`TOTAL ${results.length - fails.length}/${results.length} in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
process.exit(fails.length ? 1 : 0);
