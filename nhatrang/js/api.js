/* Клиент API. initData идёт в заголовке; вне Telegram работает только режим dev (?dev=ID) при DEV_AUTH на сервере. */
(function () {
  const tg = window.Telegram && window.Telegram.WebApp;
  const initData = (tg && tg.initData) || '';
  const devId = (() => { try { return new URLSearchParams(location.search).get('dev'); } catch (e) { return null; } })();
  let onUnauth = () => {};

  function headers(extra) {
    const hd = Object.assign({}, extra);
    if (initData) hd['Authorization'] = 'tma ' + initData;
    else if (devId) hd['X-Dev-User'] = devId;
    return hd;
  }
  async function req(method, path, { params, body } = {}) {
    let url = path;
    if (params) {
      const q = new URLSearchParams();
      for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') q.append(k, v);
      const s = q.toString(); if (s) url += '?' + s;
    }
    const init = { method, headers: headers() };
    if (body instanceof FormData) init.body = body;
    else if (body !== undefined) { init.body = JSON.stringify(body); init.headers['Content-Type'] = 'application/json'; }
    let r;
    try { r = await fetch(url, init); } catch (e) { const err = new Error('network'); err.network = true; throw err; }
    let data = null;
    try { data = await r.json(); } catch (e) { /* пустое тело */ }
    if (r.status === 401) { onUnauth(); const err = new Error('unauth'); err.status = 401; throw err; }
    if (!r.ok) { const err = new Error('http ' + r.status); err.status = r.status; err.data = data; throw err; }
    return data;
  }
  window.api = {
    get: (p, params) => req('GET', p, { params }),
    post: (p, body) => req('POST', p, { body }),
    put: (p, body) => req('PUT', p, { body }),
    del: p => req('DELETE', p),
    hasCredentials: () => !!(initData || devId),
    set onUnauth(fn) { onUnauth = fn; },
  };
})();
