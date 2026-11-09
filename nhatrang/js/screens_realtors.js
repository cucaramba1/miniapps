/* Справочник риелторов. Метка «без комиссии» только у подтверждённых вручную; контакты платные. */
(function () {
  const { h, clear } = dom;
  const LANG = { ru: 'русский', en: 'английский', vi: 'вьетнамский' };
  async function enter(root) {
    tgx.setMain(null); clear(root);
    root.append(h('h1', { text: 'Риелторы' }), h('p', { class: 'muted sm', style: 'margin:4px 0 12px', text: 'Люди, с которыми можно связаться напрямую. Метка «без комиссии» ставится только после ручной проверки.' }));
    const box = h('div', { class: 'col' }); root.append(box); box.append(App.skeleton(3));
    try {
      await App.refreshMe();
      const rs = await api.get('/api/realtors');
      clear(box);
      if (!rs.length) { box.append(App.emptyBox('🤝', 'Справочник пока пополняется.')); return; }
      rs.forEach(r => box.append(h('div', { class: 'card col', 'data-testid': 'realtor' },
        h('div', { class: 'row between' }, h('h3', { text: r.name }), App.pill(r.kind === 'ru' ? 'Русскоязычный' : 'Местный', 'p-lav')),
        h('div', { class: 'row wrap' }, r.commission_free_confirmed && App.pill('Без комиссии ✓', 'p-mint'), r.languages.map(l => App.pill(LANG[l] || l, 'p-sky'))),
        r.notes && h('p', { class: 'sm', text: r.notes }),
        r.contacts ? h('div', { class: 'col', 'data-testid': 'contacts' }, Object.entries(r.contacts).map(([k, v]) => h('div', { class: 'row between sm contact' }, h('span', { text: `${k}: ${v}`, style: 'word-break:break-all' }), h('button', { class: 'chip', text: 'Копировать', onclick: () => tgx.copy(String(v)) }))))
          : App.lockedCta('Открыть контакты'))));
    } catch (e) { if (e.status !== 401) { clear(box); box.append(App.errorBox(() => enter(root))); } }
  }
  tgx.register({ realtors: { title: 'Риелторы', tab: 'realtors', enter } });
})();
