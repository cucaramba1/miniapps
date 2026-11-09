(function () {
  const { h, clear } = dom;
  async function enter(root) {
    tgx.setMain(null); clear(root);
    root.append(h('h1', { text: 'Избранное', style: 'margin-bottom:12px' }));
    const box = h('div', { class: 'col' }); root.append(box); box.append(App.skeleton(2));
    try {
      const items = await api.get('/api/favorites');
      clear(box);
      if (!items.length) { box.append(App.emptyBox('♡', 'Пока пусто. Нажмите «В избранное» в карточке места.')); return; }
      items.forEach(p => box.append(CheckScreen.card(p)));
    } catch (e) { if (e.status !== 401) { clear(box); box.append(App.errorBox(() => enter(root))); } }
  }
  tgx.register({ favs: { title: 'Избранное', tab: 'favs', enter } });
})();
