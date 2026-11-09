/* Общее состояние, вход, онбординг. */
(function () {
  const { h, clear } = dom;
  const App = window.App = {
    cfg: { tiles_url: '', review_min_chars: 150, review_min_photos: 2, review_max_photos: 5, geo_radius_m: 150, review_reward_days: 3, center: [12.2388, 109.1967], bot_username: '', tags: { complaints: [], positive: [], labels: {} } },
    me: null,
    KINDS: { hotel: 'Отель', guest_house: 'Гостевой дом', apartment: 'Апартаменты', hostel: 'Хостел', other: 'Другое' },
    AMENITY: { massage: 'Массаж', shop: 'Магазины', laundry: 'Прачечные', fruit: 'Фрукты', cafe: 'Кафе', cheap_local: 'Местные недорогие', pharmacy: 'Аптеки', hospital: 'Больницы', bank_exchange: 'Банки и обмен' },
    async refreshMe() { App.me = await api.get('/api/me'); return App.me; },
    hasAccess: () => !!(App.me && App.me.has_access),
    skeleton: n => h('div', { class: 'col' }, Array.from({ length: n || 3 }, () => h('div', { class: 'skel', style: 'height:84px' }))),
    errorBox(retry) {
      return h('div', { class: 'empty', 'data-testid': 'err' }, h('div', { class: 'big', text: '🫧' }),
        h('p', { text: 'Не получилось загрузить. Проверьте связь и попробуйте ещё раз.' }),
        h('button', { class: 'btn ghost', style: 'margin-top:12px', text: 'Повторить', onclick: retry }));
    },
    emptyBox: (emoji, text, extra) => h('div', { class: 'empty' }, h('div', { class: 'big', text: emoji }), h('p', { text }), extra),
    pill: (text, cls) => h('span', { class: 'pill ' + (cls || 'p-lav'), text }),
    lockedCta: (text) => h('button', { class: 'btn block', 'data-go': 'pay', 'data-testid': 'unlock', text: text || 'Открыть доступ' }),
  };

  function showNoTelegram() {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('on'));
    const s = tgx.$('#s-nopen'); s.classList.add('on');
    tgx.$('.tabbar')?.classList.add('hidden');
  }
  api.onUnauth = showNoTelegram;

  const STEPS = [
    ['🔎', 'Правда о жилье до заезда', 'На карте места с отзывами тех, кто там жил. Без рекламы в выдаче.'],
    ['📍', 'Отзывы только от живых жильцов', 'Отзыв принимается с геометкой на месте и с фото. Так накрутить его сложно.'],
    ['🎁', 'Напишите отзыв, получите дни', 'За каждый подтверждённый отзыв открываем платные разделы на 3 дня. Или оплатите Stars.'],
  ];
  function renderOnboard(el, step) {
    clear(el);
    const [emoji, title, text] = STEPS[step];
    const last = step === STEPS.length - 1;
    el.append(
      h('div', { class: 'stepper' }, STEPS.map((_, i) => h('i', { class: i <= step ? 'on' : '' }))),
      h('div', { class: 'hero', text: emoji }),
      h('h1', { style: 'text-align:center', text: title }),
      h('p', { class: 'muted', style: 'text-align:center;margin:10px 0 24px', text }),
      h('button', {
        class: 'btn block', 'data-testid': 'ob-next', text: last ? 'Начать' : 'Дальше',
        onclick: () => {
          if (!last) return renderOnboard(el, step + 1);
          try { localStorage.setItem('nd_onboarded', '1'); } catch (e) { /* без хранилища */ }
          tgx.go('check');
        },
      }));
  }
  tgx.register({
    onboard: { title: 'Нячанг Дом', hideTabs: true, enter: el => { tgx.setMain(null); renderOnboard(el, 0); } },
    nopen: { title: 'Нячанг Дом', hideTabs: true, enter: () => tgx.setMain(null) },
  });

  App.start = async function () {
    if (!api.hasCredentials()) { tgx.boot('nopen'); return; }
    try {
      App.cfg = await api.get('/api/config');
      await App.refreshMe();
    } catch (e) { if (e.status === 401) return; }
    let seen = false;
    try { seen = localStorage.getItem('nd_onboarded') === '1'; } catch (e) { /* без хранилища */ }
    tgx.boot(seen ? 'check' : 'onboard');
  };
})();
