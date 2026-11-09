/* Paywall и оплата Stars. */
(function () {
  const { h, clear } = dom;
  const st = { plans: [], plan: 'd3', busy: false };
  const tg = window.Telegram && window.Telegram.WebApp;
  const inTg = !!(tg && tg.initData);

  async function enter(root) {
    tgx.setMain(null); clear(root);
    root.append(h('div', { class: 'top' }, h('button', { class: 'back', 'data-back': '', 'aria-label': 'Назад', text: '‹' }), h('h1', { text: 'Доступ' })));
    const box = h('div', { class: 'col' }); root.append(box); box.append(App.skeleton(2));
    try { st.plans = await api.get('/api/plans'); } catch (e) { if (e.status !== 401) { clear(box); box.append(App.errorBox(() => enter(root))); } return; }
    draw(box);
  }
  function draw(box) {
    clear(box);
    const msg = h('div', { class: 'sm', 'data-testid': 'pay-msg' });
    const pay = h('button', { class: 'btn block', 'data-testid': 'pay-btn' });
    const sel = st.plans.find(p => p.id === st.plan) || st.plans[0];
    pay.textContent = `Оплатить ⭐ ${sel.stars}`;
    pay.disabled = st.busy;
    pay.addEventListener('click', async () => {
      if (!inTg) { msg.textContent = 'Оплата работает только внутри Telegram. Откройте приложение из бота.'; return; }
      st.busy = true; pay.disabled = true; msg.textContent = '';
      try {
        const { invoice_url } = await api.post('/api/pay/invoice', { plan: sel.id });
        tg.openInvoice(invoice_url, async status => {
          st.busy = false;
          if (status === 'paid') {
            await pollAccess();
            done(box);
          } else if (status === 'cancelled') { pay.disabled = false; msg.textContent = 'Оплата отменена. Ничего не списано.'; }
          else { fail(box); }
        });
      } catch (e) { st.busy = false; pay.disabled = false; msg.textContent = 'Не удалось создать счёт. Попробуйте ещё раз.'; }
    });
    box.append(
      h('div', { class: 'card col' }, h('b', { text: 'Что открывается' }),
        h('ul', { class: 'chk' }, ['Тексты и фото отзывов жильцов', 'Даты и источники сигналов', 'Бытовые места рядом с заметками', 'Контакты риелторов и хозяев в объявлениях'].map(t => h('li', null, h('b', { text: '✓' }), h('span', { text: t }))))),
      ...st.plans.map(p => h('button', { class: 'card plan tap col' + (p.id === sel.id ? ' on' : ''), style: 'text-align:left', 'data-testid': 'plan-' + p.id, onclick: () => { st.plan = p.id; draw(box); } },
        h('div', { class: 'row between' }, h('b', { text: p.days + ' дня' }), h('span', { class: 'price', text: '⭐ ' + p.stars })),
        h('div', { class: 'xs muted', text: `около ${p.rub.toLocaleString('ru-RU')} ₽, подписки нет` }))),
      pay, msg,
      h('div', { class: 'card col' }, h('b', { text: 'Или бесплатно' }), h('p', { class: 'sm muted', text: `Оставьте отзыв о месте, где жили: за подтверждённый отзыв +${App.cfg.review_reward_days} дня доступа.` }),
        h('button', { class: 'btn soft', text: 'Найти место для отзыва', onclick: () => tgx.go('check') })),
      h('p', { class: 'xs muted', text: 'Вопросы по оплате и возврат Stars: команда /paysupport в чате с ботом.' }));
  }
  async function pollAccess() {
    for (let i = 0; i < 8; i++) { // webhook может прийти чуть позже закрытия окна оплаты
      await App.refreshMe().catch(() => {});
      if (App.hasAccess()) return;
      await new Promise(r => setTimeout(r, 1500));
    }
  }
  function done(box) {
    clear(box);
    box.append(h('div', { class: 'hero', text: '🎉' }), h('h1', { style: 'text-align:center', 'data-testid': 'pay-done', text: App.hasAccess() ? 'Доступ открыт' : 'Платёж получен, доступ откроется через минуту' }),
      h('button', { class: 'btn block', style: 'margin-top:18px', text: 'К жилью', onclick: () => tgx.go('check') }));
  }
  function fail(box) {
    clear(box);
    box.append(h('div', { class: 'hero', text: '🫧' }), h('h1', { style: 'text-align:center', 'data-testid': 'pay-fail', text: 'Платёж не прошёл' }),
      h('p', { class: 'muted', style: 'text-align:center', text: 'Если Stars списались, напишите /paysupport боту, вернём.' }),
      h('button', { class: 'btn block', 'data-testid': 'pay-retry', text: 'Повторить', onclick: () => draw(box) }));
  }
  tgx.register({ pay: { title: 'Доступ', hideTabs: true, enter } });
})();
