/* «Проверить жильё»: поиск, карта, районы, флажки, карточка места. */
(function () {
  const { h, clear, fmtVnd } = dom;
  const el = id => document.getElementById(id);
  const PALETTE = ['#e5484d', '#f76b15', '#ffb224', '#30a46c', '#12a594', '#0091ff', '#6e56cf', '#d6409f'];
  const FLAG_CATS = ['Кафе', 'Рынок', 'Массаж', 'Прачечная', 'Опасно', 'Другое'];
  const st = { q: '', kind: '', district: '', items: [], shown: 30, flagMode: false, map: null, flags: [], timer: null, built: false };

  function ratingPill(p) {
    if (p.rating == null) return App.pill('Отзывов пока нет', 'p-butter');
    return App.pill('★ ' + p.rating.toFixed(1) + ' · ' + p.reviews_count, p.rating >= 4 ? 'p-mint' : p.rating >= 3 ? 'p-butter' : 'p-rose');
  }
  function topTags(p, labels) {
    return Object.entries(p.tag_counts || {}).sort((a, b) => b[1] - a[1]).slice(0, 3)
      .map(([t, n]) => App.pill((App.cfg.tags.labels[t] || t) + ' ' + n, 'p-sky'));
  }
  function card(p) {
    return h('button', { class: 'card tap col', style: 'text-align:left;gap:8px', 'data-testid': 'place-card', onclick: () => tgx.go('place', { params: { id: p.id } }) },
      h('div', { class: 'row between' }, h('h3', { text: p.name }), ratingPill(p)),
      h('div', { class: 'row wrap' }, App.pill(App.KINDS[p.kind] || p.kind, 'p-lav'), p.district && App.pill(p.district, 'p-peach'),
        p.commercial && App.pill('Коммерческое', 'p-rose'), topTags(p)),
      p.price_from_vnd && h('div', { class: 'sm muted', text: 'от ' + fmtVnd(p.price_from_vnd) }));
  }
  function renderList() {
    const box = el('chk-list'); clear(box);
    if (!st.items.length) { box.append(App.emptyBox('🧐', 'Ничего не нашли. Попробуйте другое название или добавьте место.')); return; }
    st.items.slice(0, st.shown).forEach(p => box.append(card(p)));
    if (st.items.length > st.shown) box.append(h('button', { class: 'btn ghost block', 'data-testid': 'more', text: 'Показать ещё', onclick: () => { st.shown += 30; renderList(); } }));
  }
  async function load() {
    const box = el('chk-list'); clear(box); box.append(App.skeleton(3));
    try {
      st.items = await api.get('/api/places', { q: st.q, kind: st.kind, district_id: st.district, limit: 200 });
      st.shown = 30; renderList();
      if (st.map) st.map.setPlaces(st.items, p => tgx.go('place', { params: { id: p.id } }));
    } catch (e) { if (e.status !== 401) { clear(box); box.append(App.errorBox(load)); } }
  }
  function chips(boxId, opts, cur, set) {
    const box = el(boxId); clear(box);
    opts.forEach(([val, label]) => box.append(h('button', { class: 'chip' + (cur() === val ? ' on' : ''), text: label, 'data-testid': 'chip-' + boxId + '-' + (val || 'all'),
      onclick: () => { set(val); chips(boxId, opts, cur, set); load(); } })));
  }
  async function loadFlags() {
    try { st.flags = await api.get('/api/flags'); if (st.map) st.map.setFlags(st.flags, openFlag); } catch (e) { /* флажки не критичны */ }
  }
  function openFlag(f) { flagSheet({ view: f }); }
  function flagSheet({ lat, lon, view }) {
    const box = el('sh-flag'); clear(box);
    box.append(h('div', { class: 'grab' }));
    if (view) {
      box.append(h('h2', { text: view.label }), h('p', { class: 'muted', text: view.category }),
        h('button', { class: 'btn ghost block', style: 'margin-top:14px', 'data-testid': 'flag-del', text: 'Удалить флажок', onclick: async () => {
          try { await api.del('/api/flags/' + view.id); tgx.sheet('sh-flag', false); tgx.toast('Флажок удалён'); loadFlags(); } catch (e) { tgx.toast('Не удалось удалить'); }
        } }));
      tgx.sheet('sh-flag', true); return;
    }
    let cat = FLAG_CATS[0], color = PALETTE[3];
    const inp = h('input', { class: 'input', maxlength: '40', placeholder: 'Подпись (до 40 символов)', 'data-testid': 'flag-label' });
    const catBox = h('div', { class: 'chips' }), colBox = h('div', { class: 'row wrap' });
    const draw = () => {
      clear(catBox); FLAG_CATS.forEach(c => catBox.append(h('button', { class: 'chip' + (c === cat ? ' on' : ''), text: c, onclick: () => { cat = c; draw(); } })));
      clear(colBox); PALETTE.forEach(c => colBox.append(h('button', { 'aria-label': 'Цвет ' + c, style: `width:40px;height:40px;border-radius:50%;background:${c};box-shadow:${c === color ? '0 0 0 3px var(--ink)' : 'none'}`, onclick: () => { color = c; draw(); } })));
    };
    draw();
    box.append(h('h2', { text: 'Новый флажок' }), h('div', { class: 'col', style: 'margin-top:10px' }, inp, catBox, colBox,
      h('button', { class: 'btn block', 'data-testid': 'flag-save', text: 'Сохранить', onclick: async () => {
        if (!inp.value.trim()) return tgx.toast('Добавьте подпись');
        try { await api.post('/api/flags', { label: inp.value.trim(), category: cat, color, lat, lon }); tgx.sheet('sh-flag', false); tgx.toast('Флажок сохранён'); loadFlags(); }
        catch (e) { tgx.toast(e.status === 422 ? 'Лимит флажков или неверные данные' : 'Не удалось сохранить'); }
      } })));
    tgx.sheet('sh-flag', true);
  }
  async function build() {
    if (st.built) return; st.built = true;
    chips('chk-kinds', [['', 'Все'], ...Object.entries(App.KINDS).filter(([k]) => k !== 'other')], () => st.kind, v => { st.kind = v; });
    el('chk-q').addEventListener('input', ev => { clearTimeout(st.timer); st.timer = setTimeout(() => { st.q = ev.target.value.trim(); load(); }, 250); });
    el('chk-flag').addEventListener('click', () => {
      st.flagMode = !st.flagMode; el('chk-flag').classList.toggle('on', st.flagMode);
      tgx.toast(st.flagMode ? 'Тапните по карте, чтобы поставить флажок' : 'Режим флажков выключен');
    });
    st.map = mapkit.createMap(el('chk-map'), { center: App.cfg.center, zoom: 12, tilesUrl: App.cfg.tiles_url });
    if (!st.map) { el('chk-map').style.display = 'none'; el('chk-flag').style.display = 'none'; return; }
    st.map.onPick((lat, lon) => { if (st.flagMode) flagSheet({ lat, lon }); });
    try {
      const fc = await api.get('/api/districts');
      st.map.addDistricts(fc);
      if (fc.features.length) {
        chips('chk-districts', [['', 'Все районы'], ...fc.features.map(f => [String(f.properties.id), f.properties.name_ru])], () => st.district, v => { st.district = v; });
      }
    } catch (e) { /* районы появятся, когда Некит заполнит districts_ru.json */ }
  }
  tgx.register({
    check: { title: 'Проверить жильё', tab: 'check', async enter() {
      tgx.setMain(null); await build(); if (st.map) setTimeout(() => st.map.invalidate(), 60);
      loadFlags(); load();
    } },
    place: { title: 'Место', parentTab: 'check', enter: (e, p) => loadPlace(e, Number(p.id)) },
  });

  // ---------- карточка места ----------
  async function loadPlace(root, id) {
    clear(root); root.append(App.skeleton(4));
    try {
      const [v] = await Promise.all([api.get('/api/places/' + id), App.refreshMe()]);
      const favs = await api.get('/api/favorites').catch(() => []);
      renderPlace(root, v, favs.some(f => f.id === id));
    } catch (e) { if (e.status === 404) { clear(root); root.append(App.emptyBox('🕳️', 'Такого места нет или оно ещё на проверке.')); } else if (e.status !== 401) { clear(root); root.append(App.errorBox(() => loadPlace(root, id))); } }
  }
  function renderPlace(root, v, isFav) {
    clear(root);
    const L = App.cfg.tags.labels;
    const favBtn = h('button', { class: 'chip' + (isFav ? ' on' : ''), 'data-testid': 'fav', text: isFav ? '♥ В избранном' : '♡ В избранное', onclick: async () => {
      try { if (isFav) await api.del('/api/favorites/' + v.id); else await api.put('/api/favorites/' + v.id); isFav = !isFav; favBtn.classList.toggle('on', isFav); favBtn.textContent = isFav ? '♥ В избранном' : '♡ В избранное'; }
      catch (e) { tgx.toast('Не удалось обновить избранное'); }
    } });
    root.append(h('div', { class: 'top' }, h('button', { class: 'back', 'data-back': '', 'aria-label': 'Назад', text: '‹' }), h('h1', { text: v.name })));
    const col = h('div', { class: 'col' });
    root.append(col);
    col.append(h('div', { class: 'row wrap' }, App.pill(App.KINDS[v.kind] || v.kind, 'p-lav'), v.district && App.pill(v.district, 'p-peach'),
      v.commercial && App.pill('Коммерческое место', 'p-rose'), favBtn));
    if (v.official_photos.length) col.append(h('div', { class: 'chips' }, v.official_photos.map(u => dom.safeUrl(u) && h('img', { src: u, alt: '', loading: 'lazy', style: 'height:140px;border-radius:14px;flex:none' }))));
    const basics = Object.entries(v.basics || {});
    col.append(h('div', { class: 'card col' },
      h('div', { class: 'row between' }, h('b', { text: 'Оценка жильцов' }), v.rating == null ? App.pill('Пока нет', 'p-butter') : App.pill('★ ' + v.rating.toFixed(1), 'p-mint')),
      v.price_from_vnd && h('div', { class: 'price', text: 'от ' + fmtVnd(v.price_from_vnd) + (v.price_to_vnd ? ' до ' + fmtVnd(v.price_to_vnd) : '') }),
      basics.map(([k, val]) => h('div', { class: 'sm' }, h('b', { text: k + ': ' }), String(val)))));
    if (v.empty) col.append(h('div', { class: 'card', 'data-testid': 'empty-note' }, h('b', { text: 'Отзывов пока нет' }), h('p', { class: 'muted sm', text: 'Здесь ещё никто не рассказал, как там живётся. Если вы были, оставьте отзыв и получите дни доступа.' })));
    else col.append(h('div', { class: 'card col' }, h('b', { text: 'Жалобы и плюсы' }),
      h('div', { class: 'row wrap', 'data-testid': 'tag-counts' }, Object.entries(v.tag_counts).map(([t, n]) => App.pill((L[t] || t) + ' · ' + n, 'p-sky')))));
    col.append(h('div', { class: 'card col' }, h('b', { text: 'Что рядом (пешком около 5 минут)' }),
      h('div', { class: 'row wrap', 'data-testid': 'amenity-index' }, Object.entries(v.amenity_index).filter(([, n]) => n > 0).map(([c, n]) => App.pill((App.AMENITY[c] || c) + ' ' + n, 'p-mint')))));
    if (v.locked) {
      if (!v.empty) col.append(h('div', { class: 'card col', 'data-testid': 'locked-block' }, h('h3', { text: 'Что пишут жильцы' }),
        h('p', { class: 'muted sm', text: `Тексты и фото ${v.reviews_count} отзывов, даты, источники сигналов и список бытовых мест. Открывается на 3 или 7 дней.` }), App.lockedCta('Открыть отзывы')));
    } else {
      const P = v.paid;
      col.append(h('h2', { text: 'Что пишут жильцы' }));
      if (!P.reviews.length) col.append(h('p', { class: 'muted', text: 'Текстов пока нет.' }));
      P.reviews.forEach(r => col.append(h('div', { class: 'card col', 'data-testid': 'review' },
        h('div', { class: 'row between' }, h('span', { class: 'muted xs', text: r.created_at.slice(0, 10) }), r.author_badge && App.pill(r.author_badge, 'p-mint')),
        h('p', { text: r.text, style: 'white-space:pre-wrap' }),
        r.photo_urls.length && h('div', { class: 'chips' }, r.photo_urls.map(u => h('img', { src: u, alt: 'Фото жильца', loading: 'lazy', style: 'height:120px;border-radius:12px;flex:none' }))),
        h('button', { class: 'chip', style: 'align-self:flex-start', text: 'Пожаловаться', onclick: async () => { try { await api.post(`/api/reviews/${r.id}/report`); tgx.toast('Спасибо, проверим'); } catch (e) { tgx.toast('Не удалось отправить'); } } }))));
      if (P.signals.length) col.append(h('div', { class: 'card col' }, h('b', { text: 'Сигналы из других источников' }),
        P.signals.map(s => h('div', { class: 'row between sm' }, h('span', { text: `${s.source}: ${L[s.tag] || s.tag} (${s.count})` }),
          dom.safeUrl(s.url) && h('button', { class: 'chip', text: 'Открыть', onclick: () => dom.openLink(s.url) })))));
      if (P.amenities.length) col.append(h('div', { class: 'card col' }, h('b', { text: 'Бытовые места рядом' }),
        P.amenities.slice(0, 40).map(a => h('div', { class: 'row between sm' }, h('span', { text: (a.name || App.AMENITY[a.category] || a.category) }), h('span', { class: 'muted', text: a.distance_m + ' м' })))));
    }
    col.append(h('button', { class: 'btn block', 'data-testid': 'write-review', text: 'Я тут жил: оставить отзыв', onclick: () => tgx.go('review', { params: { id: v.id } }) }));
  }
  window.CheckScreen = { card };
})();
