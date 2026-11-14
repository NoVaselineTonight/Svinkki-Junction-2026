/* Svinkki inside a host app (S-mobiili). Loaded only by /embed, before app.js.
 *
 * The host opens /embed#handover=<token>. The fragment never reaches a server or a Referer.
 * This script takes the token out of the address at once, trades it (one POST) for a session,
 * and keeps the session id in memory only. Every API call app.js makes then carries it in the
 * X-Svinkki-Session header, so the app works even where the browser blocks third-party cookies
 * inside the iframe. app.js waits for nothing: its API calls are held until the trade is done.
 */
(function () {
  'use strict';
  var HEADER = 'X-Svinkki-Session';
  var m = /(?:^#|&)handover=([A-Za-z0-9_\-.]{10,400})(?:&|$)/.exec(location.hash || '');
  if (!m) return;                                  // opened without a token: the normal picker
  var token = m[1];
  try { history.replaceState(null, '', location.pathname + location.search); } catch (e) { /* ignore */ }

  var realFetch = window.fetch.bind(window);
  var session = null;

  function isApi(input) {
    var url = typeof input === 'string' ? input : (input && input.url) || '';
    try {
      var u = new URL(url, location.href);
      return u.origin === location.origin && u.pathname.indexOf('/api/') === 0;
    } catch (e) { return false; }
  }

  var ready = realFetch('/api/embed/session', {
    method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify({ token: token })
  }).then(function (res) {
    return res.ok ? res.json() : null;
  }).then(function (data) {
    session = data && typeof data.session === 'string' ? data.session : null;
  }, function () { session = null; });
  token = null;

  window.fetch = function (input, init) {
    if (!isApi(input)) return realFetch(input, init);
    return ready.then(function () {
      if (!session) return realFetch(input, init);
      var opts = {};
      init = init || {};
      for (var k in init) { if (Object.prototype.hasOwnProperty.call(init, k)) opts[k] = init[k]; }
      var headers = new Headers(init.headers || (typeof input !== 'string' && input.headers) || {});
      headers.set(HEADER, session);
      opts.headers = headers;
      return realFetch(input, opts).then(function (res) {
        if (res.status === 401) session = null;    // logged out or expired: back to the picker
        return res;
      });
    });
  };
})();
