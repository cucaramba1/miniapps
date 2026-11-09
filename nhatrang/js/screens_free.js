/* «Свободно сейчас»: объявления с жалобами по месту. Контакты закрыты без доступа. */
(function () {
  const { h, clear, fmtVnd } = dom;
  const f = { bedrooms: '', maxPrice: '', onlyPlace: false };
  const BEDS = [['', 'Любые'], ['1', '1 спальня'], ['2', '2'], ['3', '3'], ['4', '4']];
  const PRICES = [['', 'Любой бюджет'], ['10000000', 'до 10 млн'], ['15000000', 'до 15 млн'], ['20000000', 'до 20 млн'], ['30000000', 'до 30 млн']];

  function contactRows(c) {
    const rows = [];
    for (const [k, v] of Object.entries(c)) {
      if (v == null || v === '') continue;
      const val = Array.isArray(v) ? v.join(', ') : String(v);
      const url = dom.safeUrl(val);
      rows.push(h('div', { class: 'row between sm contact' }, h('span', { text: val, style: 'word-break:break-all' }),
        url ? h('button', { class: 'chip', text: 'Открыть', onclick: () => dom.openLink(url) }) : h('button', { class: 'chip', text: 'Копировать', onclick: () => tgx.copy(val) })));
    }
    return rows;
  }
  function item(l) {
    const s = l.place_summary;
    return h('div', { class: 'card col', 'data-testid': 'listing' },
      h('h3', { text: l.title }),
      h('div', { class: 'row wrap' }, l.price_vnd && h('span', { class: 'price', text: fmtVnd(l.price_vnd) }),
        l.bedrooms != null && App.pill(l.bedrooms + ' спальни', 'p-lav'), l.district_text && App.pill(l.district_text, 'p-peach'),
        l.posted_at && App.pill(dom.ago(l.posted_at), 'p-sky'), l.chats_count > 0 && App.pill(`в ${l.chats_count} чатах`, 'p-butter')),
      s ? h('button', { class: 'chip', style: 'align-self:flex-start', text: `${s.name}: ${s.rating == null ? 'отзывов нет' : '★ ' + s.rating.toFixed(1)}`, onclick: () => tgx.go('place', { params: { id: l.place_id } }) })
        : h('div', { class: 'xs muted', text: 'Место не распознано, жалоб по нему нет.' }),
      s && Object.keys(s.tag_counts).length > 0 && h('div', { class: 'row wrap' }, Object.entries(s.tag_counts).map(([t, n]) => App.pill((App.cfg.tags.labels[t] || t) + ' · ' + n, 'p-rose'))),
      l.contacts ? h('div', { class: 'col', 'data-testid': 'contacts' }, contactRows(l.contacts)) : App.lockedCta('Открыть контакты'));
  }
  async function load(root) {
    const box = root.querySelector('#fr-list'); clear(box); box.append(App.skeleton(3));
    try {
      await App.refreshMe();
      const items = await api.get('/api/listings', { bedrooms: f.bedrooms, max_price: f.maxPrice, only_with_place: f.onlyPlace ? 1 : '' });
      clear(box);
      if (!items.length) box.append(App.emptyBox('🏝️', 'Свежих объявлений под такие условия сейчас нет. Заглядывайте позже или ослабьте фильтры.'));
      items.forEach(l => box.append(item(l)));
    } catch (e) { if (e.status !== 401) { clear(box); box.append(App.errorBox(() => load(root))); } }
  }
  function chipRow(opts, key, root) {
    const row = h('div', { class: 'chips' });
    const draw = () => { clear(row); opts.forEach(([v, label]) => row.append(h('button', { class: 'chip' + (f[key] === v ? ' on' : ''), text: label, onclick: () => { f[key] = v; draw(); load(root); } }))); };
    draw(); return row;
  }
  function enter(root) {
    tgx.setMain(null); clear(root);
    const onlyBtn = h('button', { class: 'chip' + (f.onlyPlace ? ' on' : ''), text: 'Только с известным местом', 'data-testid': 'only-place', onclick: () => { f.onlyPlace = !f.onlyPlace; onlyBtn.classList.toggle('on', f.onlyPlace); load(root); } });
    root.append(h('h1', { text: 'Свободно сейчас' }), h('p', { class: 'muted sm', style: 'margin:4px 0 10px', text: 'Свежие объявления и то, что жильцы пишут об этом месте.' }),
      chipRow(BEDS, 'bedrooms', root), chipRow(PRICES, 'maxPrice', root), h('div', { class: 'chips' }, onlyBtn), h('div', { class: 'col', id: 'fr-list' }));
    load(root);
  }
  tgx.register({ free: { title: 'Свободно', tab: 'free', enter } });
})();
