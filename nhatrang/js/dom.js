/* Мини-хелперы DOM. Весь текст из API идёт только через textContent, HTML-строки в js/ не собираются. */
(function () {
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === false || v == null) continue;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else if (k === 'data') for (const [dk, dv] of Object.entries(v)) el.dataset[dk] = dv;
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) {
      if (kid == null || kid === false) continue;
      el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }
  const clear = el => { while (el.firstChild) el.removeChild(el.firstChild); return el; };
  const fmtVnd = n => n == null ? '' : Number(n).toLocaleString('ru-RU') + ' ₫';
  const safeUrl = u => { try { const x = new URL(u); return /^https?:$/.test(x.protocol) ? x.href : null; } catch (e) { return null; } };
  const len = s => [...String(s).trim()].length; // символы, а не UTF-16: совпадает с Python len()
  function ago(iso) {
    const t = Date.parse(iso); if (isNaN(t)) return '';
    const m = Math.round((Date.now() - t) / 60000);
    if (m < 1) return 'только что';
    if (m < 60) return m + ' мин назад';
    if (m < 1440) return Math.round(m / 60) + ' ч назад';
    return Math.round(m / 1440) + ' дн назад';
  }
  function openLink(url) {
    const u = safeUrl(url); if (!u) return;
    const tg = window.Telegram && window.Telegram.WebApp;
    if (tg && tg.initData && tg.openLink) tg.openLink(u); else window.open(u, '_blank', 'noopener');
  }
  window.dom = { h, clear, fmtVnd, safeUrl, len, ago, openLink };
})();
