window.api = (function() {
  const BASE = '/api';

  async function request(method, path, body, opts) {
    const headers = { 'Content-Type': 'application/json' };
    const cfg = { method, headers };
    if (body && method !== 'GET') {
      if (body instanceof FormData) {
        delete headers['Content-Type'];
        cfg.body = body;
      } else {
        cfg.body = JSON.stringify(body);
      }
    }
    if (opts && opts.signal) cfg.signal = opts.signal;

    const r = await fetch(BASE + path, cfg);

    if (window.uiLog) {
      if (!r.ok) {
        var detail = '';
        try {
          var errBody = await r.clone().text();
          try { var j = JSON.parse(errBody); detail = j.detail || j.message || errBody; } catch(e) { detail = errBody; }
        } catch(e) {}
        window.uiLog('warn', method + ' ' + path + ' → ' + r.status + (detail ? ': ' + detail.slice(0, 120) : ''));
      } else {
        window.uiLog('verbose', method + ' ' + path + ' → ' + r.status);
      }
    }

    if (opts && opts.raw) return r;

    if (!r.ok) {
      const errText = await r.text();
      throw new Error(errText || '请求失败 (' + r.status + ')');
    }

    const ct = r.headers.get('content-type') || '';
    if (ct.includes('json')) return r.json();
    return r.text();
  }

  return {
    get(path) { return request('GET', path); },
    post(path, body) { return request('POST', path, body); },
    put(path, body) { return request('PUT', path, body); },
    patch(path, body) { return request('PATCH', path, body); },
    del(path) { return request('DELETE', path); },
    upload(path, formData) { return request('POST', path, formData); },
    request,
  };
})();
