/* Отзыв жильца и добавление места. */
(function () {
  const { h, clear } = dom;
  const REASONS = {
    text_short: n => `Нужно минимум ${n} символов.`,
    photos_few: n => `Нужно минимум ${n} фото.`,
    photos_many: n => `Не больше ${n} фото.`,
    too_far: () => 'Вы далеко от этого места. Отзыв принимается только рядом с ним.',
    bad_coords: () => 'Не удалось определить геопозицию.',
    daily_limit: () => 'Сегодня вы уже оставили отзыв. Следующий можно завтра.',
    place_cooldown: () => 'Об этом месте вы уже писали недавно. Повторный отзыв через 2 недели.',
    bad_photo: () => 'Одно из фото не подошло. Нужны обычные снимки (JPEG, PNG, WEBP до 6 МБ).',
    bad_tag: () => 'Неизвестная метка.',
    text_long: () => 'Слишком длинный текст.',
    no_place: () => 'Такого места нет.',
  };
  const HOLD = {
    place_pending: 'Место на проверке, отзыв опубликуется после неё.',
    low_accuracy: 'Геопозиция неточная, отзыв проверит модератор.',
    exif_stale: 'Фото сделано давно, отзыв проверит модератор.',
    duplicate_text: 'Текст похож на другой отзыв, его проверит модератор.',
    reported: 'Отзыв на проверке.',
  };
  const st = { place: null, pos: null, photos: [], tags: new Set(), rating: 0, sending: false };

  function reasonText(reason) {
    const c = App.cfg;
    const f = REASONS[reason];
    return f ? f(reason === 'text_short' ? c.review_min_chars : reason.startsWith('photos') ? (reason === 'photos_few' ? c.review_min_photos : c.review_max_photos) : null) : 'Отзыв не принят.';
  }

  async function enterReview(root, params) {
    clear(root); root.append(App.skeleton(3));
    Object.assign(st, { place: null, pos: null, photos: [], tags: new Set(), rating: 0, sending: false });
    let place;
    try { place = await api.get('/api/places/' + Number(params.id)); } catch (e) { clear(root); root.append(App.errorBox(() => enterReview(root, params))); return; }
    st.place = place;
    const c = App.cfg;
    clear(root);
    const ta = h('textarea', { class: 'input', rows: '6', style: 'padding:12px;min-height:140px', placeholder: `Расскажите, как там на самом деле (от ${c.review_min_chars} символов)`, 'data-testid': 'rv-text' });
    const counter = h('div', { class: 'xs muted', 'data-testid': 'rv-counter' });
    const geoBox = h('div', { class: 'sm', 'data-testid': 'rv-geo' });
    const photoBox = h('div', { class: 'chips', 'data-testid': 'rv-photos' });
    const fileIn = h('input', { type: 'file', accept: 'image/*', capture: 'environment', multiple: true, style: 'display:none', 'data-testid': 'rv-file' });
    const submit = h('button', { class: 'btn block', 'data-testid': 'rv-submit', text: 'Отправить отзыв' });
    const msg = h('div', { class: 'sm', 'data-testid': 'rv-msg' });
    const stars = h('div', { class: 'row' });

    const ready = () => dom.len(ta.value) >= c.review_min_chars && st.photos.length >= c.review_min_photos && st.rating >= 1 && st.pos && !st.sending;
    const refresh = () => {
      counter.textContent = `${dom.len(ta.value)} / ${c.review_min_chars}`;
      submit.disabled = !ready();
      clear(stars);
      for (let i = 1; i <= 5; i++) stars.append(h('button', { class: 'chip' + (st.rating === i ? ' on' : ''), text: '★' + i, 'data-testid': 'rv-star-' + i, onclick: () => { st.rating = i; refresh(); } }));
      clear(photoBox);
      st.photos.forEach((f, i) => photoBox.append(h('div', { style: 'position:relative;flex:none' },
        h('img', { src: URL.createObjectURL(f), alt: 'Фото', style: 'height:84px;border-radius:12px' }),
        h('button', { class: 'chip', style: 'position:absolute;right:2px;top:2px;min-height:28px;padding:0 8px', text: '✕', 'aria-label': 'Убрать фото', onclick: () => { st.photos.splice(i, 1); refresh(); } }))));
    };
    function showGeo() {
      if (!st.pos) { geoBox.textContent = 'Геопозиция ещё не получена.'; return; }
      const d = Math.round(geo.haversine(st.pos.lat, st.pos.lon, place.lat, place.lon));
      geoBox.textContent = d <= c.geo_radius_m ? `Вы в ${d} м от места. Подходит.` : `Вы далеко (около ${d} м). Нужно быть в пределах ${c.geo_radius_m} м.`;
    }
    async function locate() {
      geoBox.textContent = 'Определяем геопозицию...';
      try { st.pos = await geo.getPosition(); showGeo(); } catch (e) { st.pos = null; geoBox.textContent = e.message; }
      refresh();
    }
    ta.addEventListener('input', refresh);
    fileIn.addEventListener('change', () => {
      for (const f of fileIn.files) if (st.photos.length < c.review_max_photos) st.photos.push(f);
      fileIn.value = ''; refresh();
    });
    submit.addEventListener('click', async () => {
      if (!ready()) return;
      st.sending = true; refresh(); msg.textContent = 'Отправляем...';
      const fd = new FormData();
      fd.append('text', ta.value.trim()); fd.append('rating', String(st.rating));
      fd.append('lat', String(st.pos.lat)); fd.append('lon', String(st.pos.lon)); fd.append('accuracy_m', String(st.pos.accuracy));
      [...st.tags].forEach(t => fd.append('tags', t));
      st.photos.forEach(f => fd.append('photos', f, f.name || 'photo.jpg'));
      try {
        const r = await api.post(`/api/places/${place.id}/reviews`, fd);
        await App.refreshMe();
        const done = r.status === 'published'
          ? `Спасибо! Отзыв опубликован. +${r.reward_days} дня доступа.`
          : 'Отзыв принят и ждёт проверки. ' + (HOLD[(r.hold_reason || '').split(',')[0]] || '');
        clear(root);
        root.append(h('div', { class: 'hero', text: r.status === 'published' ? '🎉' : '🕓' }), h('h1', { style: 'text-align:center', 'data-testid': 'rv-done', text: done }),
          h('button', { class: 'btn block', style: 'margin-top:20px', text: 'К месту', onclick: () => tgx.go('place', { params: { id: place.id }, replace: true }) }));
      } catch (e) {
        st.sending = false; refresh();
        const reason = e.data && e.data.reason;
        msg.textContent = e.network ? 'Нет связи. Фото сохранены на экране, нажмите отправить ещё раз.' : reasonText(reason);
      }
    });
    const tagRow = (title, list) => h('div', null, h('b', { class: 'sm', text: title }), h('div', { class: 'chips' }, list.map(t => {
      const b = h('button', { class: 'chip', text: c.tags.labels[t] || t, onclick: () => { st.tags.has(t) ? st.tags.delete(t) : st.tags.add(t); b.classList.toggle('on', st.tags.has(t)); } });
      return b;
    })));
    root.append(
      h('div', { class: 'top' }, h('button', { class: 'back', 'data-back': '', 'aria-label': 'Назад', text: '‹' }), h('h1', { text: 'Отзыв: ' + place.name })),
      h('div', { class: 'col' },
        h('div', { class: 'card col' }, h('b', { text: '1. Вы на месте' }), geoBox, h('button', { class: 'btn soft', 'data-testid': 'rv-locate', text: 'Определить геопозицию', onclick: locate })),
        h('div', { class: 'card col' }, h('b', { text: '2. Фото (камера, ' + c.review_min_photos + '-' + c.review_max_photos + ' шт.)' }), photoBox,
          h('button', { class: 'btn soft', text: 'Снять фото', 'data-testid': 'rv-addphoto', onclick: () => fileIn.click() }), fileIn),
        h('div', { class: 'card col' }, h('b', { text: '3. Оценка и текст' }), stars, ta, counter),
        h('div', { class: 'card col' }, h('b', { text: '4. Метки (необязательно)' }), tagRow('Жалобы', c.tags.complaints), tagRow('Плюсы', c.tags.positive)),
        submit, msg,
        h('p', { class: 'xs muted', text: `За подтверждённый отзыв: +${c.review_reward_days} дня платного доступа.` })));
    refresh(); showGeo(); locate();
  }

  // ---------- добавить место ----------
  const ap = { kind: 'hotel', lat: null, lon: null, map: null };
  async function enterAddPlace(root) {
    clear(root);
    Object.assign(ap, { kind: 'hotel', lat: null, lon: null, map: null });
    const name = h('input', { class: 'input', maxlength: '120', placeholder: 'Название', 'data-testid': 'ap-name' });
    const kinds = h('div', { class: 'chips' });
    const status = h('div', { class: 'sm', 'data-testid': 'ap-status' });
    const msg = h('div', { class: 'sm', 'data-testid': 'ap-msg' });
    const mapEl = h('div', { style: 'height:220px;border-radius:18px;overflow:hidden', 'data-testid': 'ap-map' });
    const save = h('button', { class: 'btn block', 'data-testid': 'ap-save', text: 'Отправить на проверку' });
    const refresh = () => {
      clear(kinds);
      Object.entries(App.KINDS).forEach(([k, label]) => kinds.append(h('button', { class: 'chip' + (ap.kind === k ? ' on' : ''), text: label, onclick: () => { ap.kind = k; refresh(); } })));
      status.textContent = ap.lat == null ? 'Тапните по карте, где находится место.' : `Точка выбрана: ${ap.lat.toFixed(5)}, ${ap.lon.toFixed(5)}`;
      save.disabled = !(name.value.trim().length >= 2 && ap.lat != null);
    };
    name.addEventListener('input', refresh);
    save.addEventListener('click', async () => {
      save.disabled = true;
      try {
        await api.post('/api/places', { name: name.value.trim(), kind: ap.kind, lat: ap.lat, lon: ap.lon });
        clear(root);
        root.append(h('div', { class: 'hero', text: '🕓' }), h('h1', { style: 'text-align:center', 'data-testid': 'ap-done', text: 'Место на проверке' }),
          h('p', { class: 'muted', style: 'text-align:center;margin:8px 0 18px', text: 'Мы посмотрим и добавим его на карту. Отзыв, написанный к нему, опубликуется после проверки.' }),
          h('button', { class: 'btn block', text: 'Готово', onclick: () => tgx.go('check') }));
      } catch (e) {
        refresh();
        if (e.status === 409) {
          const id = e.data && e.data.existing_id;
          msg.textContent = 'Такое место уже есть. ';
          if (id) msg.append(h('button', { class: 'chip', text: 'Открыть', onclick: () => tgx.go('place', { params: { id } }) }));
        } else if (e.status === 429) msg.textContent = 'Слишком много мест на проверке. Дождитесь, пока мы разберём прежние.';
        else msg.textContent = 'Не удалось отправить. Проверьте название и точку.';
      }
    });
    root.append(h('div', { class: 'top' }, h('button', { class: 'back', 'data-back': '', 'aria-label': 'Назад', text: '‹' }), h('h1', { text: 'Добавить место' })),
      h('div', { class: 'col' }, name, kinds, mapEl, status, save, msg));
    refresh();
    ap.map = mapkit.createMap(mapEl, { center: App.cfg.center, zoom: 14, tilesUrl: App.cfg.tiles_url });
    if (ap.map) {
      ap.map.onPick((lat, lon) => { ap.lat = lat; ap.lon = lon; ap.map.setPickMarker(lat, lon); refresh(); });
      setTimeout(() => ap.map.invalidate(), 60);
      geo.getPosition().then(p => { ap.map.setView(p.lat, p.lon, 17); }).catch(() => { /* карта остаётся по центру */ });
    } else status.textContent = 'Карта недоступна без сети.';
  }
  tgx.register({
    review: { title: 'Отзыв', hideTabs: true, enter: (e, p) => { tgx.setMain(null); enterReview(e, p); } },
    addplace: { title: 'Новое место', hideTabs: true, enter: e => { tgx.setMain(null); enterAddPlace(e); } },
  });
  window.ReviewScreen = { reasonText };
})();
