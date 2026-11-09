(function () {
  const { h, clear } = dom;
  async function enter(root) {
    tgx.setMain(null); clear(root);
    root.append(h('h1', { text: 'Профиль', style: 'margin-bottom:12px' }));
    const box = h('div', { class: 'col' }); root.append(box); box.append(App.skeleton(2));
    try { await App.refreshMe(); } catch (e) { if (e.status !== 401) { clear(box); box.append(App.errorBox(() => enter(root))); } return; }
    const me = App.me;
    clear(box);
    let left = '';
    if (me.access_until) {
      const d = Math.max(0, Math.ceil((Date.parse(me.access_until) - Date.now()) / 86400000));
      left = `Осталось примерно ${d} дн. (до ${me.access_until.slice(0, 10)})`;
    }
    box.append(
      h('div', { class: 'card col', 'data-testid': 'access-card' }, h('b', { text: me.has_access ? 'Доступ открыт' : 'Доступа нет' }),
        h('div', { class: 'muted sm', 'data-testid': 'access-left', text: me.has_access ? left : 'Платные разделы закрыты.' }),
        h('button', { class: 'btn', 'data-go': 'pay', 'data-testid': 'to-pay', text: me.has_access ? 'Продлить' : 'Открыть доступ' })),
      h('div', { class: 'card col' }, h('b', { text: 'Ваши отзывы' }), h('div', { class: 'price', 'data-testid': 'reviews-count', text: String(me.reviews_published) }),
        h('p', { class: 'sm muted', text: `Каждый подтверждённый отзыв дарит ${App.cfg.review_reward_days} дня доступа. Нужны: текст от ${App.cfg.review_min_chars} символов, ${App.cfg.review_min_photos}-${App.cfg.review_max_photos} фото с камеры и геопозиция рядом с местом.` }),
        h('button', { class: 'btn soft', text: 'Оставить отзыв', onclick: () => tgx.go('check') })),
      h('div', { class: 'card col' }, h('b', { text: 'Поддержка и возврат' }),
        h('p', { class: 'sm muted', text: 'Вопросы по оплате: отправьте команду /paysupport боту' + (App.cfg.bot_username ? ' @' + App.cfg.bot_username : '') + '.' })));
  }
  tgx.register({ profile: { title: 'Профиль', tab: 'profile', enter } });
})();
