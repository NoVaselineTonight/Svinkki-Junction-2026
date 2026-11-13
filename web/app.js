/* Svinkki web app. Vanilla JS, no dependencies, no inline HTML from data (SR-19). */
(function () {
  'use strict';

  // ---------- small DOM helpers ----------
  var SVG_NS = 'http://www.w3.org/2000/svg';

  function append(el, kids) {
    for (var i = 0; i < kids.length; i++) {
      var k = kids[i];
      if (k == null || k === false) continue;
      if (Array.isArray(k)) { append(el, k); continue; }
      el.appendChild(k instanceof Node ? k : document.createTextNode(String(k)));
    }
  }

  // h(tag, props, ...children). Strings always become text nodes. No style/innerHTML props.
  function h(tag, props) {
    var el = document.createElement(tag);
    if (props) {
      for (var k in props) {
        if (!Object.prototype.hasOwnProperty.call(props, k)) continue;
        var v = props[k];
        if (v == null || v === false) continue;
        if (k === 'style' || k === 'innerHTML' || k === 'outerHTML') continue;
        if (k === 'class') el.className = v;
        else if (k === 'text') el.textContent = v;
        else if (k.slice(0, 2) === 'on' && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
        else if (v === true) el.setAttribute(k, '');
        else el.setAttribute(k, String(v));
      }
    }
    append(el, Array.prototype.slice.call(arguments, 2));
    return el;
  }

  var ICONS = {
    home: ['M3 11l9-8 9 8', 'M5 10v10h5v-6h4v6h5V10'],
    chat: ['M21 12a8 8 0 0 1-11.5 7.2L4 20l1.1-4.4A8 8 0 1 1 21 12z'],
    explore: ['M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z', 'M21 21l-4.6-4.6'],
    settings: ['M4 6h9', 'M17 6h3', 'M4 12h3', 'M11 12h9', 'M4 18h11', 'M19 18h1', 'M15 4v4', 'M9 10v4', 'M17 16v4'],
    chev: ['M9 6l6 6-6 6'],
    doc: ['M7 3h7l4 4v14H7z', 'M14 3v4h4', 'M9.5 12h6', 'M9.5 16h6'],
    help: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M9.6 9.4a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1.1.9-1.1 1.8', 'M12 17h.01'],
    gear: ['M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z', 'M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z']
  };
  function icon(name, size) {
    var s = size || 24;
    var svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('width', String(s));
    svg.setAttribute('height', String(s));
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '2');
    svg.setAttribute('stroke-linecap', 'round');
    svg.setAttribute('stroke-linejoin', 'round');
    svg.setAttribute('aria-hidden', 'true');
    (ICONS[name] || []).forEach(function (d) {
      var p = document.createElementNS(SVG_NS, 'path');
      p.setAttribute('d', d);
      svg.appendChild(p);
    });
    return svg;
  }

  // ---------- formatting ----------
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

  function num(n) { n = Number(n); return isFinite(n) ? n : 0; }

  function money(n, opts) {
    opts = opts || {};
    n = Number(n);
    if (!isFinite(n)) return '-';
    var abs = Math.abs(n);
    var dec = (opts.hero && abs >= 1000) ? 0 : 2;
    var s = abs.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec });
    var isZero = Number(abs.toFixed(dec)) === 0;
    var sign = (n < 0 && !isZero) ? '-' : (opts.plus && n > 0 ? '+' : '');
    return sign + '€' + s;
  }

  function fmtDate(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || ''));
    if (!m) return s ? String(s) : '';
    return Number(m[3]) + ' ' + MON[Number(m[2]) - 1] + ' ' + m[1];
  }
  function fmtMonth(ym) {
    var m = /^(\d{4})-(\d{2})/.exec(String(ym || ''));
    if (!m) return String(ym || '');
    return MONTHS[Number(m[2]) - 1] + ' ' + m[1];
  }
  // Full calendar month: "August 2026". Same year: "1 Aug to 15 Sep 2026". Otherwise both years.
  function fmtRange(p) {
    if (!p || !p.from) return '';
    var to = p.to || p.from;
    if (p.from === to) return fmtDate(p.from);
    var a = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(p.from));
    var b = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(to));
    if (!a || !b) return fmtDate(p.from) + ' to ' + fmtDate(to);
    if (a[1] === b[1] && a[2] === b[2] && a[3] === '01' && String(to).slice(0, 10) === lastDayOfMonth(a[1] + '-' + a[2])) {
      return MONTHS[Number(a[2]) - 1] + ' ' + a[1];
    }
    if (a[1] === b[1]) return Number(a[3]) + ' ' + MON[Number(a[2]) - 1] + ' to ' + fmtDate(to);
    return fmtDate(p.from) + ' to ' + fmtDate(to);
  }
  // Replace ISO dates and ISO ranges inside free text with human dates.
  function ht(s) {
    if (s == null) return '';
    return String(s)
      .replace(/(\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})/g, function (m, x, y) { return fmtRange({ from: x, to: y }); })
      .replace(/\b\d{4}-\d{2}-\d{2}\b/g, function (m) { return fmtDate(m); });
  }
  function fmtPeriod(p) {
    if (!p) return '';
    if (typeof p === 'string') return /^\d{4}-\d{2}$/.test(p) ? fmtMonth(p) : ht(p);
    return fmtRange(p);
  }
  function pct(n) { return Math.round(num(n)) + '%'; }

  function lastDayOfMonth(ym) {
    var m = /^(\d{4})-(\d{2})/.exec(ym);
    var d = new Date(Date.UTC(Number(m[1]), Number(m[2]), 0)).getUTCDate();
    return ym.slice(0, 7) + '-' + (d < 10 ? '0' + d : String(d));
  }

  var BASKET_NAMES = { regular: 'Regular essentials', unexpected: 'Unexpected necessities', everyday: 'Everyday spending', savings: 'Savings' };
  var BASKET_BLURB = {
    regular: 'Bills and things you need every month',
    unexpected: 'Costs you could not plan for',
    everyday: 'Choices you make day to day'
  };

  // ---------- API ----------
  function ApiError(status, code, message, handled) {
    this.status = status; this.code = code; this.message = message; this.handled = !!handled;
  }

  function friendly(status, code) {
    if (status === 0) return 'We could not reach the server. Check your connection and try again.';
    if (status === 429) return 'You are going a bit fast. Wait a moment and try again.';
    if (status >= 500) return 'Something went wrong on our side. Please try again in a moment.';
    if (status === 403) return 'That needs a permission you have not given. You can change it in Settings.';
    if (status === 404 && code === 'quiz_off') return 'The weekly quiz is switched off.';
    if (status === 404) return 'We could not find that.';
    if (status === 413) return 'That message is too long.';
    if (status === 400 || status === 422) return 'That request was not valid. Please check it and try again.';
    return 'Something went wrong. Please try again.';
  }

  function api(path, opts) {
    opts = opts || {};
    var init = { method: opts.method || 'GET', credentials: 'same-origin', headers: { 'Accept': 'application/json' } };
    if (opts.body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(opts.body);
    }
    return fetch(path, init).then(function (res) {
      return res.text().then(function (txt) {
        var data = null;
        try { data = txt ? JSON.parse(txt) : null; } catch (e) { data = null; }
        if (res.ok) return data;
        var code = data && typeof data.error === 'string' ? data.error : '';
        if (res.status === 401) {
          onUnauthorised();
          throw new ApiError(401, code, 'Please sign in again.', true);
        }
        if (res.status === 403 && code === 'consent_required') {
          onConsentRequired();
          throw new ApiError(403, code, 'Consent needed.', true);
        }
        throw new ApiError(res.status, code, friendly(res.status, code), false);
      });
    }, function () {
      throw new ApiError(0, 'network', friendly(0, ''), false);
    });
  }

  // ---------- app state ----------
  var me = null;
  var token = 0;           // increments on every screen change; stale async work checks it
  var chat = null;         // the one conversation; null until the app screen is drawn
  var mode = 'boot';       // boot | login | consent | app
  var viewEl = null;

  function alive(t) { return t === token; }

  // inApp: the conversation screen (top bar buttons, pinned input, no page scroll).
  function setChrome(inApp, sub) {
    document.getElementById('top-actions').hidden = !inApp;
    document.body.classList.toggle('chat-screen', !!inApp);
    document.getElementById('topbar-sub').textContent = inApp ? '' : (sub || '');
  }

  function clearView() {
    token++;
    chat = null;
    viewEl.replaceChildren();
  }

  function onUnauthorised() {
    if (mode === 'login') return;
    me = null;
    showLogin();
  }
  function onConsentRequired() {
    if (mode === 'consent') return;
    if (me && me.consent) me.consent.analysis = false;
    showConsent();
  }

  // ---------- shared UI pieces ----------
  function loadingNode(text) {
    return h('div', { class: 'loading', role: 'status' }, h('span', { class: 'spinner', 'aria-hidden': 'true' }), text || 'Loading...');
  }

  function errorNode(err, retry) {
    var msg = (err && err.message) ? err.message : 'Something went wrong. Please try again.';
    var box = h('div', { class: 'notice err', role: 'alert' }, msg);
    if (retry) box.appendChild(h('button', { type: 'button', class: 'link-btn', onclick: retry }, 'Try again'));
    return box;
  }

  // Load async content into a container with loading and error states.
  function load(container, t, fetcher, render, loadingText) {
    container.replaceChildren(loadingNode(loadingText));
    function run() {
      container.replaceChildren(loadingNode(loadingText));
      fetcher().then(function (data) {
        if (!alive(t)) return;
        container.replaceChildren();
        render(data);
      }, function (e) {
        if (!alive(t) || (e && e.handled)) return;
        container.replaceChildren(errorNode(e, run));
      });
    }
    run();
  }

  function card(title, right, extraClass) {
    var head = h('div', { class: 'card-head' }, h('h3', null, title));
    if (right) head.appendChild(h('span', { class: 'tiny' }, right));
    return h('section', { class: 'card' + (extraClass ? ' ' + extraClass : '') }, head);
  }

  function switchRow(id, title, desc, checked, onChange, opts) {
    opts = opts || {};
    var input = h('input', { type: 'checkbox', role: 'switch', id: id, class: 'sw-input' });
    input.checked = !!checked;
    if (opts.disabled) input.disabled = true;
    input.addEventListener('change', function () { onChange(input.checked); });
    var titleEl = h('span', { class: 'sw-title', id: id + '-title' }, title);
    input.setAttribute('aria-labelledby', id + '-title');
    if (opts.tag) titleEl.appendChild(h('span', { class: 'sw-tag' }, ' (' + opts.tag + ')'));
    var label = h('label', { class: 'switch-row', for: id },
      input,
      h('span', { class: 'sw-text' }, titleEl, h('span', { class: 'sw-desc' }, desc)),
      h('span', { class: 'sw-track', 'aria-hidden': 'true' }, h('span', { class: 'sw-thumb' }))
    );
    return { el: label, input: input };
  }

  // Segmented control built from buttons with aria-pressed.
  function segmented(label, options, value, onChange) {
    var current = value;
    var wrap = h('div', { class: 'seg', role: 'group', 'aria-label': label });
    var btns = options.map(function (o) {
      var b = h('button', { type: 'button', class: 'seg-btn', 'aria-pressed': String(o.value === current) }, o.label);
      b.addEventListener('click', function () {
        if (current === o.value) return;
        current = o.value;
        paint();
        onChange(o.value);
      });
      wrap.appendChild(b);
      return b;
    });
    function paint() {
      btns.forEach(function (b, i) { b.setAttribute('aria-pressed', String(options[i].value === current)); });
    }
    return { el: wrap, get: function () { return current; }, set: function (v) { current = v; paint(); } };
  }

  function barRow(label, value, max, cls, valueText) {
    var w = max > 0 ? Math.max(0, Math.min(100, (Math.abs(value) / max) * 100)) : 0;
    var fill = h('div', { class: 'bar-fill' + (cls ? ' ' + cls : '') });
    fill.style.width = w + '%';
    return h('div', { class: 'bar-row' },
      h('span', null, label),
      h('div', { class: 'bar-track', 'aria-hidden': 'true' }, fill),
      h('span', { class: 'bar-val' }, valueText != null ? valueText : money(value))
    );
  }

  // "Compared with people like you": two bars (you, typical) plus the group in small text.
  // Without consent the result carries peer_hint instead: a quiet link to Settings.
  function peerBlock(d) {
    if (!d) return null;
    var p = d.peer;
    if (p && p.sentence) {
      var mx = Math.max(num(p.you), num(p.peer_typical), 1);
      var g = p.group || {};
      return h('div', { class: 'peer' },
        h('p', { class: 'eyebrow' }, 'Compared with people like you'),
        barRow('You', num(p.you), mx, 'you'),
        barRow(p.basis === 'mean' ? 'Average' : 'Typical', num(p.peer_typical), mx, 'median'),
        h('p', { class: 'small' }, ht(p.sentence)),
        g.description ? h('p', { class: 'tiny' }, g.description + (g.n ? ' (' + g.n + ' customers)' : '') + (p.approximate ? ', approximate' : '')) : null);
    }
    if (d.peer_hint) {
      var b = h('button', { type: 'button', class: 'link-btn inline peer-hint' }, d.peer_hint);
      b.addEventListener('click', function () { openSettings(); });
      return h('p', { class: 'small' }, b);
    }
    return null;
  }

  function stat(value, label) { return h('div', { class: 'stat' }, h('b', null, value), h('span', null, label)); }

  function explainNode(d) {
    return d && d.explain ? h('p', { class: 'explain' }, ht(d.explain)) : null;
  }

  // ---------- sheets ----------
  var sheetState = null;
  var FOCUSABLE = 'button, input, select, textarea, a[href], [tabindex]:not([tabindex="-1"])';

  // opts.full: a full-height page over the conversation instead of a bottom sheet.
  function openSheet(title, opts) {
    closeSheet();
    opts = opts || {};
    var previous = document.activeElement;
    var app = document.getElementById('app');
    var body = h('div', { class: 'sheet-body' });
    var closeBtn = h('button', { type: 'button', class: 'sheet-close', 'aria-label': 'Close' }, '×');
    var sheet = h('div', { class: 'sheet' + (opts.full ? ' full' : ''), role: 'dialog', 'aria-modal': 'true', 'aria-label': title },
      opts.full ? null : h('div', { class: 'grabber', 'aria-hidden': 'true' }),
      h('div', { class: 'sheet-head' }, h('h2', null, title), closeBtn),
      body);
    var overlay = h('div', { class: 'overlay' + (opts.full ? ' full' : '') }, sheet);
    function onKey(e) {
      if (e.key === 'Escape') { e.preventDefault(); closeSheet(); return; }
      if (e.key === 'Tab') {
        var f = Array.prototype.filter.call(sheet.querySelectorAll(FOCUSABLE), function (x) { return !x.disabled && x.offsetParent !== null; });
        if (!f.length) return;
        var first = f[0], last = f[f.length - 1];
        if (!sheet.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
        else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    }
    closeBtn.addEventListener('click', closeSheet);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) closeSheet(); });
    document.addEventListener('keydown', onKey);
    document.body.appendChild(overlay);
    if (app) app.inert = true;     // the conversation behind the sheet cannot be reached
    sheetState = { overlay: overlay, onKey: onKey, previous: previous };
    closeBtn.focus();
    return body;
  }

  function closeSheet() {
    if (!sheetState) return;
    document.removeEventListener('keydown', sheetState.onKey);
    sheetState.overlay.remove();
    var app = document.getElementById('app');
    if (app) app.inert = false;
    var p = sheetState.previous;
    sheetState = null;
    if (p && p.focus && document.contains(p)) p.focus();
  }

  // ---------- transactions ----------
  function filterQuery(f, limit) {
    var qs = new URLSearchParams();
    ['from', 'to', 'label', 'basket', 'context', 'type', 'q'].forEach(function (k) {
      if (f && f[k] != null && f[k] !== '') qs.set(k, String(f[k]));
    });
    qs.set('limit', String(limit || 100));
    return qs.toString();
  }

  function labelText(row) {
    if (row.context === 'night_out') return 'Night out';
    return row.label || row.category || 'Other';
  }

  function canRelabel(r) {
    return typeof r.id === 'number' && isFinite(r.id) && Math.floor(r.id) === r.id
      && num(r.amount) < 0 && r.basket !== 'savings' && r.basket !== 'income';
  }

  var labelCache = null;
  function loadLabels() {
    if (labelCache) return Promise.resolve(labelCache);
    return api('/api/labels').then(function (d) {
      var list = (d && Array.isArray(d.labels)) ? d.labels.filter(function (x) { return typeof x === 'string'; }) : [];
      if (list.length) labelCache = list;
      return list;
    });
  }

  // Inline picker under one purchase row. Sends only tx_id, label, context and apply_to_merchant.
  function categoryPicker(r, holder, opts) {
    holder.replaceChildren(loadingNode('Loading categories...'));
    loadLabels().then(function (labels) {
      if (!labels.length) { holder.replaceChildren(h('p', { class: 'small muted' }, 'Categories are not available right now.')); return; }
      var uid = 'cp-' + r.id + '-' + Math.random().toString(36).slice(2, 6);
      var sel = h('select', { class: 'input', id: uid + '-l' });
      labels.forEach(function (l) { sel.appendChild(h('option', { value: l }, l)); });
      if (r.label && labels.indexOf(r.label) >= 0) sel.value = r.label;
      var night = switchRow(uid + '-n', 'This was part of a night out', 'Counts it with your night out spending.', r.context === 'night_out', function () {});
      var chk = h('input', { type: 'checkbox', id: uid + '-m' });
      var msg = h('div', { 'aria-live': 'polite' });
      var save = h('button', { type: 'button', class: 'btn' }, 'Save');
      var cancel = h('button', { type: 'button', class: 'btn secondary' }, 'Cancel');
      cancel.addEventListener('click', function () { holder.replaceChildren(); });
      save.addEventListener('click', function () {
        save.disabled = true;
        msg.replaceChildren(loadingNode('Saving...'));
        api('/api/overrides', { method: 'POST', body: {
          tx_id: r.id, label: sel.value, context: night.input.checked ? 'night_out' : '', apply_to_merchant: !!chk.checked
        } }).then(function (res) {
          var n = res && res.affected != null ? num(res.affected) : 1;
          var note = 'Remembered. ' + n + ' ' + (n === 1 ? 'purchase' : 'purchases') + ' updated.';
          if (opts && opts.reload) opts.reload(note);
          else holder.replaceChildren(h('p', { class: 'notice ok', role: 'status' }, note));
        }, function (e) {
          save.disabled = false;
          if (e.handled) return;
          msg.replaceChildren(errorNode(e));
        });
      });
      holder.replaceChildren(h('div', { class: 'picker' },
        h('label', { for: uid + '-l', class: 'field-label' }, 'Category'), sel, night.el,
        h('label', { class: 'check-row', for: uid + '-m' }, chk, h('span', null, 'Apply to every purchase from this merchant')),
        h('div', { class: 'btn-row' }, save, cancel), msg));
      sel.focus();
    }, function (e) {
      if (e && e.handled) return;
      holder.replaceChildren(h('p', { class: 'small muted' }, 'Categories are not available right now.'));
    });
  }

  // opts: { reload(note), note }. reload is given when the list can redraw itself.
  function txList(res, opts) {
    opts = opts || {};
    var rows = (res && res.rows) || [];
    var box = h('div');
    if (opts.note) box.appendChild(h('p', { class: 'notice ok', role: 'status' }, opts.note));
    if (!opts.bare) {
      box.appendChild(h('p', { class: 'small muted' },
        (res.count != null ? res.count : rows.length) + ' transactions, total ' + money(Math.abs(num(res.total)))
        + (res.truncated ? ' (showing the first ' + rows.length + ')' : '')));
    }
    if (!rows.length) {
      if (!opts.bare) box.appendChild(h('p', { class: 'muted' }, 'No transactions match.'));
      return box;
    }
    var list = h('div', { role: 'list' });
    rows.forEach(function (r) {
      var amt = num(r.amount);
      // The row is named by what it was (Bar, Taxi, Groceries), not by the merchant's internal id.
      var title = String(r.label || r.display_label || r.category || 'Transaction');
      var time = (r.ts && String(r.ts).length >= 16) ? String(r.ts).slice(11, 16) : '';
      var sub = h('span', { class: 'tx-sub' }, fmtDate(r.d || r.ts) + (time ? ', ' + time : '') +
        (r.context === 'night_out' ? ' · Night out' : ''));
      if (r.basket && BASKET_NAMES[r.basket]) sub.appendChild(h('span', { class: 'pill' }, BASKET_NAMES[r.basket]));
      var main = h('div', { class: 'tx-main' }, h('span', { class: 'tx-title' }, title), sub);
      var line = h('div', { class: 'tx-line' }, main, h('span', { class: 'tx-amt' + (amt > 0 ? ' in' : '') }, money(amt, { plus: true })));
      var item = h('div', { class: 'tx', role: 'listitem' }, line);
      if (canRelabel(r)) {
        var holder = h('div', { class: 'tx-extra' });
        var btn = h('button', { type: 'button', class: 'link-btn small-link', 'aria-label': 'Change category for ' + title + ' ' + fmtDate(r.d || r.ts) }, 'Change category');
        btn.addEventListener('click', function () {
          if (holder.firstChild) { holder.replaceChildren(); return; }
          categoryPicker(r, holder, opts);
        });
        main.appendChild(btn);
        item.appendChild(holder);
      }
      list.appendChild(item);
    });
    box.appendChild(list);
    return box;
  }

  // Evidence is normally a list of filters, but /api/baskets sends one object per basket.
  function evidenceList(ev) {
    if (ev && !Array.isArray(ev) && typeof ev === 'object') ev = [ev];
    return (Array.isArray(ev) ? ev : []).filter(function (f) { return f && typeof f === 'object'; });
  }

  function openEvidence(evidence, title) {
    var filters = evidenceList(evidence);
    if (!filters.length) return;
    var body = openSheet(ht(title) || 'Transactions');
    var t = token;
    var tabs = h('div', { class: 'tabs-mini' });
    var out = h('div');
    var btns = [];
    var note = '';
    function show(i) {
      btns.forEach(function (b, j) { b.setAttribute('aria-pressed', String(i === j)); });
      load(out, t, function () { return api('/api/transactions?' + filterQuery(filters[i], 100)); }, function (res) {
        var n = note; note = '';
        out.appendChild(txList(res, { note: n, reload: function (msg) { note = msg; show(i); } }));
      }, 'Loading transactions...');
    }
    if (filters.length > 1) {
      filters.forEach(function (f, i) {
        var b = h('button', { type: 'button', class: 'chip', 'aria-pressed': 'false' }, ht(f.title) || ('Group ' + (i + 1)));
        b.addEventListener('click', function () { show(i); });
        btns.push(b); tabs.appendChild(b);
      });
      body.appendChild(tabs);
    } else if (filters[0].title) {
      body.appendChild(h('p', { class: 'small muted' }, ht(filters[0].title) + (filters[0].from && !/\d{4}-\d{2}-\d{2}/.test(filters[0].title) ? ' · ' + fmtRange(filters[0]) : '')));
    }
    body.appendChild(out);
    show(0);
  }

  function evidenceLink(evidence, title) {
    if (!evidenceList(evidence).length) return null;
    return h('button', { type: 'button', class: 'link-btn ev-link', onclick: function () { openEvidence(evidence, title); } }, 'See the transactions');
  }

  // ---------- login ----------
  function brandHeader() {
    return h('div', { class: 'brand-head' },
      h('span', { class: 'logo large' },
        h('img', { class: 'logo-mark', src: 'brand/s-mark.svg', alt: '', height: '44' }),
        h('span', { class: 'logo-word', 'aria-hidden': 'true' }, 'Vinkki'),
        h('span', { class: 'sr-only' }, 'Svinkki')));
  }

  function showLogin() {
    mode = 'login';
    closeSheet();
    clearView();
    setChrome(false, '');
    var t = token;
    var list = h('div', { class: 'persona-list' });
    var status = h('div', { 'aria-live': 'polite' });
    var randomBtn = h('button', { type: 'button', class: 'persona random' },
      h('strong', null, 'Try as a random customer'),
      h('span', null, 'Picks a real synthetic customer at random from those who use the bank as their main account and are active.'));
    randomBtn.addEventListener('click', function () {
      randomBtn.disabled = true;
      status.replaceChildren(loadingNode('Picking a customer...'));
      api('/api/demo/random', { method: 'POST' }).then(boot, function (e) {
        randomBtn.disabled = false;
        if (e.handled) return;
        var msg = (e.status === 404 || e.status >= 500)
          ? 'Random customers are not available right now. Please pick one of the examples below.'
          : e.message;
        status.replaceChildren(h('div', { class: 'notice err', role: 'alert' }, msg));
      });
    });
    viewEl.appendChild(brandHeader());
    viewEl.appendChild(h('div', null,
      h('span', { class: 'demo-tag' }, 'DEMO ONLY'),
      h('h1', { class: 'section-title' }, 'Demo login'),
      h('p', { class: 'muted' }, 'This is a prototype with synthetic data. In the real bank app you would already be signed in. Pick a customer to try Svinkki as.')));
    viewEl.appendChild(randomBtn);
    viewEl.appendChild(status);
    viewEl.appendChild(h('h2', { class: 'section-title' }, 'Or pick an example'));
    viewEl.appendChild(list);
    load(list, t, function () { return api('/api/demo/personas'); }, function (people) {
      (people || []).forEach(function (p) {
        var b = h('button', { type: 'button', class: 'persona' },
          h('strong', null, p.name || 'Customer'), h('span', null, p.blurb || ''));
        b.addEventListener('click', function () {
          b.disabled = true;
          api('/api/demo/login', { method: 'POST', body: { id: p.id } }).then(boot, function (e) {
            b.disabled = false;
            if (e.handled) return;
            list.insertBefore(errorNode(e), list.firstChild);
          });
        });
        list.appendChild(b);
      });
      if (!(people || []).length) list.appendChild(h('p', { class: 'muted' }, 'No demo customers are available.'));
    }, 'Loading demo customers...');
  }

  // ---------- consent and preferences controls ----------
  var FREQ = [
    { value: 'off', label: 'Off' },
    { value: 'weekly', label: 'Weekly' },
    { value: 'biweekly', label: 'Every 2 weeks' },
    { value: 'monthly', label: 'Monthly' }
  ];
  var LEVELS = [
    { value: 'off', label: 'Off' },
    { value: 'few', label: 'Few' },
    { value: 'normal', label: 'Normal' }
  ];
  var QUIZ = [
    { value: 'weekly', label: 'On' },
    { value: 'off', label: 'Off' }
  ];

  var CHALLENGE_OPTS = [
    { value: 'on', label: 'On' },
    { value: 'off', label: 'Off' }
  ];

  function normFreq(v) {
    if (v === 'fortnightly' || v === 'every_two_weeks' || v === 'two_weeks' || v === 'every2weeks') return 'biweekly';
    return v || 'monthly';
  }

  function consentControls(consent, onChange) {
    var state = {
      analysis: !!consent.analysis, ai: !!consent.ai,
      benchmarks: !!consent.benchmarks, suggestions: !!consent.suggestions
    };
    var wrap = h('div');
    function fire(key) { return function (v) { state[key] = v; onChange(key, state); }; }
    var rows = [
      switchRow('sw-analysis', 'Analyse my transactions', 'Svinkki reads your own transactions to work out your spending, baskets and what is safe to spend.', state.analysis, fire('analysis'), { tag: 'needed' }),
      switchRow('sw-ai', 'Let an AI model help answer', 'Chat can use an AI model. It only sees anonymised summaries, never your name, account or raw transactions.', state.ai, fire('ai')),
      switchRow('sw-bench', 'Compare me with people like me', 'See how you stack up against groups of at least 20 similar customers. Only group statistics are used.', state.benchmarks, fire('benchmarks')),
      switchRow('sw-sugg', 'Give me suggestions', 'Svinkki may suggest things like setting a surplus aside. Nothing ever happens without your say-so, and no money moves.', state.suggestions, fire('suggestions'))
    ];
    rows.forEach(function (r) { wrap.appendChild(r.el); });
    return { el: wrap, get: function () { return Object.assign({}, state); } };
  }

  function prefControls(settings, onChange) {
    var s = {
      checkin_frequency: normFreq(settings.checkin_frequency),
      suggestion_level: settings.suggestion_level || 'few',
      quiz: settings.quiz || 'weekly',
      monthly_saving_target: num(settings.monthly_saving_target),
      challenges: settings.challenges === 'on' ? 'on' : 'off'
    };
    var wrap = h('div', { class: 'prefs' });
    var summary = h('p', { class: 'pref-summary', 'aria-live': 'polite' });
    function describe() {
      var chal = s.challenges === 'on';
      if (s.checkin_frequency === 'off') {
        summary.textContent = 'Check-ins are off. You can still ask anything in chat.' + (chal ? ' One optional weekly challenge is on.' : '');
        return;
      }
      var every = { weekly: 'week', biweekly: 'two weeks', monthly: 'month' }[s.checkin_frequency] || 'month';
      var tail = { off: ' with no suggestions', few: ' with at most one suggestion', normal: ' with up to three suggestions' }[s.suggestion_level] || '';
      summary.textContent = 'You will get a check-in every ' + every + tail + (chal ? ' and one optional weekly challenge.' : '.');
    }
    describe();
    function fire() { describe(); onChange(Object.assign({}, s)); }
    var f1 = segmented('How often should I check in?', FREQ, s.checkin_frequency, function (v) { s.checkin_frequency = v; fire(); });
    var f2 = segmented('How many suggestions?', LEVELS, s.suggestion_level, function (v) { s.suggestion_level = v; fire(); });
    var f3 = segmented('Weekly quiz', QUIZ, s.quiz === 'off' ? 'off' : 'weekly', function (v) { s.quiz = v; fire(); });
    wrap.appendChild(h('div', null, h('span', { class: 'field-label' }, 'How often should I check in?'), f1.el,
      h('p', { class: 'help' }, 'A check-in is a short summary of your month with a few ideas. Choose Off for none.')));
    wrap.appendChild(h('div', null, h('span', { class: 'field-label' }, 'How many suggestions?'), f2.el,
      h('p', { class: 'help' }, 'Few shows at most one idea per check-in, Normal up to three.')));
    var f4 = segmented('Challenges', CHALLENGE_OPTS, s.challenges, function (v) { s.challenges = v; fire(); });
    wrap.appendChild(h('div', null, h('span', { class: 'field-label' }, 'Challenges'), f4.el,
      h('p', { class: 'help' }, 'One small optional challenge a week, built from your own habits. Never any pressure.')));
    wrap.appendChild(summary);
    wrap.appendChild(h('div', null, h('span', { class: 'field-label' }, 'Weekly quiz'), f3.el,
      h('p', { class: 'help' }, 'A quick guess-the-spending game that helps you notice habits.')));
    return { el: wrap, get: function () { return Object.assign({}, s); }, setTarget: function (v) { s.monthly_saving_target = v; } };
  }

  function showConsent() {
    mode = 'consent';
    closeSheet();
    clearView();
    setChrome(false, me && me.name ? me.name : '');
    var consent = (me && me.consent) || {};
    var settings = (me && me.settings) || {};
    // A new customer starts with everything on and can switch parts off before starting.
    var fresh = !consent.analysis && !consent.ai && !consent.benchmarks && !consent.suggestions;
    if (fresh) consent = { analysis: true, ai: true, benchmarks: true, suggestions: true };
    var first = me && me.name ? String(me.name).split(',')[0] : '';
    var status = h('div');
    var hint = h('p', { class: 'help', id: 'consent-hint' }, 'Turn on "Analyse my transactions" to continue.');
    var go = h('button', { type: 'button', class: 'btn block', 'aria-describedby': 'consent-hint' }, 'Start');
    var cc = consentControls(consent, function (key, st) {
      go.disabled = !st.analysis;
      hint.hidden = st.analysis;
    });
    var pc = prefControls(settings, function () {});
    go.disabled = !cc.get().analysis;
    hint.hidden = cc.get().analysis;
    go.addEventListener('click', function () {
      var c = cc.get();
      if (!c.analysis) return;
      go.disabled = true;
      status.replaceChildren(loadingNode('Saving...'));
      api('/api/consent', { method: 'POST', body: c }).then(function () {
        return api('/api/settings', { method: 'POST', body: pc.get() });
      }).then(boot, function (e) {
        go.disabled = false;
        if (e.handled) return;
        status.replaceChildren(errorNode(e));
      });
    });
    var more = h('details', { class: 'set-sec' },
      h('summary', null, 'Choose what I may do and how often I check in'),
      h('div', { class: 'set-body' }, cc.el, h('h2', null, 'How much do you want to hear from me?'), pc.el));
    viewEl.appendChild(brandHeader());
    viewEl.appendChild(h('div', { class: 'welcome' },
      h('h1', null, first ? 'Hi ' + first + '!' : 'Hi!'),
      h('p', null, 'I am Svinkki, your money coach. I read your own transactions to answer questions about your money. An AI model helps me word the answers; it sees results, never your name or account.'),
      h('p', { class: 'muted' }, 'Nothing ever moves your money. You can change all of this later in Settings.')));
    viewEl.appendChild(go);
    viewEl.appendChild(hint);
    viewEl.appendChild(status);
    viewEl.appendChild(more);
  }

  // ---------- boot ----------
  function boot() {
    mode = 'boot';
    closeSheet();
    clearView();
    setChrome(false, '');
    viewEl.appendChild(loadingNode('Loading...'));
    return api('/api/me').then(function (m) {
      me = m;
      if (!me.consent || !me.consent.analysis) { showConsent(); return; }
      showApp();
    }, function (e) {
      if (e.handled) return;
      clearView();
      viewEl.appendChild(errorNode(e, boot));
    });
  }

  var STATUS_TEXT = { ok: 'On track', tight: 'Tight', over: 'Over budget' };

  function safeHero(d) {
    var status = STATUS_TEXT[d.status] ? d.status : 'ok';
    var calc = h('div', { class: 'calc', id: 'calc-' + Math.random().toString(36).slice(2, 7), hidden: true });
    calc.appendChild(h('div', { class: 'calc-row' }, h('span', null, 'Money in your account'), h('b', null, money(d.balance))));
    var bills = d.upcoming_bills || [];
    calc.appendChild(h('div', { class: 'calc-row' }, h('span', null, 'Upcoming bills (' + bills.length + ')'), h('b', null, '-' + money(d.bills_total))));
    bills.forEach(function (b) {
      calc.appendChild(h('div', { class: 'calc-row calc-sub' }, h('span', { class: 'small' }, '  ' + (b.label || 'Bill') + (b.due ? ', ' + fmtDate(b.due) : '')), h('span', { class: 'small' }, money(b.expected))));
    });
    calc.appendChild(h('div', { class: 'calc-row' }, h('span', null, 'Buffer for unexpected costs'), h('b', null, '-' + money(d.unexpected_buffer))));
    calc.appendChild(h('div', { class: 'calc-row' }, h('span', null, 'Planned savings'), h('b', null, '-' + money(d.planned_savings))));
    calc.appendChild(h('div', { class: 'calc-row total' }, h('span', null, 'Safe to spend'), h('b', null, money(d.safe_total))));
    calc.appendChild(h('p', { class: 'calc-note' }, 'Until ' + (d.next_payday ? fmtDate(d.next_payday) : 'your next payday') + ' (' + num(d.days_left) + ' days). ' + (d.explain || '')));
    var toggle = h('button', { type: 'button', class: 'link-btn', 'aria-expanded': 'false', 'aria-controls': calc.id }, 'How this is calculated');
    var fcHost = h('div', { class: 'fc-host' });
    calc.appendChild(fcHost);
    var fcLoaded = false;
    toggle.addEventListener('click', function () {
      var open = calc.hidden;
      if (open && !fcLoaded) { fcLoaded = true; loadForecastInto(fcHost); }
      calc.hidden = !open;
      toggle.setAttribute('aria-expanded', String(open));
      toggle.textContent = open ? 'Hide the calculation' : 'How this is calculated';
    });
    var ev = evidenceLink(d.evidence, 'Where your balance comes from');
    var short = num(d.safe_total) < 0 || num(d.per_day) < 0;
    var big, sub, pill;
    if (short) {
      // Never headline a negative per-day figure: say it is short and by how much.
      pill = h('span', { class: 'status-pill over' }, 'Short until payday');
      big = h('div', { class: 'hero-big' }, '€0', h('small', null, ' safe to spend'));
      sub = h('div', { class: 'hero-sub' }, 'About ' + money(Math.abs(num(d.safe_total)), { hero: true }).replace(/\.00$/, '') + ' short before payday' + (d.next_payday ? ' on ' + fmtDate(d.next_payday) : ''));
    } else {
      pill = h('span', { class: 'status-pill ' + status }, STATUS_TEXT[status]);
      big = h('div', { class: 'hero-big' }, money(d.per_day, { hero: true }), h('small', null, ' per day'));
      sub = h('div', { class: 'hero-sub' }, money(d.per_week, { hero: true }) + ' this week');
    }
    var sec = h('section', { class: 'card hero', 'aria-label': 'Safe to spend' },
      h('div', { class: 'card-head' }, h('span', { class: 'eyebrow' }, 'Safe to spend'), pill),
      big, sub, toggle, calc);
    if (ev) sec.appendChild(ev);
    return sec;
  }

  function basketKeyOf(b) {
    var k = String(b.key || '').toLowerCase();
    if (BASKET_NAMES[k]) return k;
    return 'other';
  }

  function basketsBlock(d, opts) {
    opts = opts || {};
    var items = (d.baskets || []).filter(function (b) { return ['regular', 'unexpected', 'everyday'].indexOf(String(b.key)) >= 0; });
    var total = items.reduce(function (s, b) { return s + Math.max(0, num(b.total)); }, 0);
    var frag = h('div');
    var stack = h('div', { class: 'stack', role: 'img', 'aria-label': 'Spending split between the three baskets' });
    items.forEach(function (b) {
      var seg = h('span', { class: 'b-' + basketKeyOf(b) });
      seg.style.width = (total > 0 ? (Math.max(0, num(b.total)) / total) * 100 : 0) + '%';
      stack.appendChild(seg);
    });
    frag.appendChild(stack);
    items.forEach(function (b) {
      var k = basketKeyOf(b);
      var share = total > 0 ? (Math.max(0, num(b.total)) / total) * 100 : 0;
      var row = h('button', { type: 'button', class: 'basket-row', 'aria-label': (b.name || BASKET_NAMES[k]) + ', ' + money(b.total) + '. Open transactions.' },
        h('span', { class: 'dot b-' + k, 'aria-hidden': 'true' }),
        h('span', null, h('span', { class: 'basket-name' }, b.name || BASKET_NAMES[k]), h('span', { class: 'basket-sub' }, BASKET_BLURB[k] || '')),
        h('span', { class: 'basket-amt' }, money(b.total), h('span', null, pct(share))),
        h('span', { class: 'chev' }, icon('chev', 18)));
      row.addEventListener('click', function () { openEvidence(b.evidence, b.name || BASKET_NAMES[k]); });
      frag.appendChild(h('div', { class: 'gap-row' }, row));
      if (opts.tops && b.top && b.top.length) {
        var mx = Math.max.apply(null, b.top.map(function (x) { return num(x.total); }).concat([1]));
        b.top.slice(0, 4).forEach(function (x) { frag.appendChild(barRow(x.label || x.name || '?', num(x.total), mx, 'b-' + k)); });
      }
    });
    if (d.rules && !opts.compact) {
      var rid = 'rules-' + Math.random().toString(36).slice(2, 8);
      var rules = h('p', { class: 'explain', id: rid, hidden: true }, ht(d.rules));
      var rt = h('button', { type: 'button', class: 'link-btn', 'aria-expanded': 'false', 'aria-controls': rid }, 'How are baskets decided?');
      rt.addEventListener('click', function () {
        var open = rules.hidden;
        rules.hidden = !open;
        rt.setAttribute('aria-expanded', String(open));
      });
      frag.appendChild(rt);
      frag.appendChild(rules);
    }
    return frag;
  }

  function animateNumber(el, to, ms) {
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) { el.textContent = money(to); return; }
    var start = null;
    function step(ts) {
      if (start == null) start = ts;
      var p = Math.min(1, (ts - start) / ms);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = money(to * eased);
      if (p < 1) requestAnimationFrame(step); else el.textContent = money(to);
    }
    requestAnimationFrame(step);
  }

  function quizCard(q) {
    var min = num(q.min), max = num(q.max) || 100, stepV = num(q.step) || 1;
    var c = card('Weekly quiz', q.period ? fmtRange(q.period) : '');
    c.appendChild(h('p', { class: 'quiz-q' }, q.question || 'Guess your spending this week.'));
    var out = h('div', { class: 'quiz-guess', 'aria-live': 'polite' }, money(Math.round((min + max) / 2 / stepV) * stepV));
    var slider = h('input', { type: 'range', class: 'range', min: min, max: max, step: stepV, 'aria-label': 'Your guess in euros' });
    slider.value = String(Math.round((min + max) / 2 / stepV) * stepV);
    slider.addEventListener('input', function () { out.textContent = money(slider.value); });
    var btn = h('button', { type: 'button', class: 'btn block' }, 'Lock in my guess');
    var result = h('div', { 'aria-live': 'polite' });
    btn.addEventListener('click', function () {
      btn.disabled = true; slider.disabled = true;
      result.replaceChildren(loadingNode('Checking...'));
      var guess = Number(slider.value);
      api('/api/quiz/answer', { method: 'POST', body: { quiz_id: q.quiz_id, guess: guess } }).then(function (r) {
        btn.hidden = true;
        result.replaceChildren();
        var actual = num(r.actual);
        var big = h('div', { class: 'reveal-actual' }, money(0));
        var diff = guess - actual;
        var line = r.verdict || (Math.abs(diff) < 0.5 ? 'Spot on!' : (diff > 0 ? 'You guessed ' + money(diff) + ' too high.' : 'You guessed ' + money(-diff) + ' too low.'));
        var rev = h('div', { class: 'reveal' },
          h('div', { class: 'tiny' }, 'You spent'), big,
          h('div', { class: 'small' }, 'Your guess: ' + money(guess)),
          h('p', null, h('b', null, line)));
        result.appendChild(rev);
        if (r.tip) result.appendChild(h('p', { class: 'tip' }, r.tip));
        var pbq = peerBlock(r);
        if (pbq) result.appendChild(pbq);
        var ev = evidenceLink(r.evidence, 'The transactions behind the quiz');
        if (ev) result.appendChild(ev);
        animateNumber(big, actual, 900);
        var statsBox = h('div', { 'aria-live': 'polite' });
        var again = h('button', { type: 'button', class: 'btn secondary block' }, 'Try another');
        again.addEventListener('click', function () {
          again.disabled = true;
          api('/api/quiz?another=1').then(function (q2) {
            if (q2 && q2.quiz_id) c.replaceWith(quizCard(q2));
            else again.disabled = false;
          }, function (e) {
            again.disabled = false;
            if (e.handled) return;
            statsBox.appendChild(h('p', { class: 'small muted' }, 'No other question is available right now.'));
          });
        });
        result.appendChild(again);
        result.appendChild(statsBox);
        api('/api/quiz/stats').then(function (s) {
          var n = quizStatsNode(s);
          if (n) statsBox.replaceChildren(n);
        }, function () {});
      }, function (e) {
        btn.disabled = false; slider.disabled = false;
        if (e.handled) return;
        result.replaceChildren(errorNode(e));
      });
    });
    c.appendChild(out); c.appendChild(slider); c.appendChild(btn); c.appendChild(result);
    return c;
  }

  function checkinCard(c) {
    var sec = card('Your check-in', fmtPeriod(c.period));
    sec.appendChild(h('p', { class: 'quiz-q' }, ht(c.headline) || 'Here is how your month went.'));
    sec.appendChild(h('div', { class: 'stats' },
      stat(money(c.income), 'Money in'), stat(money(c.spent), 'Spent'), stat(money(c.surplus), 'Left over')));
    var hl = c.highlights || [];
    if (hl.length) {
      var ul = h('ul', { class: 'list' });
      hl.forEach(function (x) { ul.appendChild(h('li', null, ht(x))); });
      sec.appendChild(ul);
    }
    var ev = evidenceLink(c.evidence, 'The month in transactions');
    if (ev) sec.appendChild(ev);
    (c.suggestions || []).forEach(function (s, i) { sec.appendChild(suggestionBlock(s, i === 0)); });
    return sec;
  }

  function suggestionBlock(s, lead) {
    var box = h('div', { class: 'tip' + (lead ? ' lead' : '') });
    box.appendChild(h('b', { class: 'sugg-title' }, ht(s.title) || 'Suggestion'));
    if (s.detail) box.appendChild(h('p', { class: 'small' }, ht(s.detail)));
    if (s.amount != null) box.appendChild(h('p', { class: 'small' }, 'Amount: ' + money(s.amount)));
    var msg = h('div', { 'aria-live': 'polite' });
    var row = h('div', { class: 'btn-row' });
    function act(action) {
      row.querySelectorAll('button').forEach(function (b) { b.disabled = true; });
      api('/api/suggestions/action', { method: 'POST', body: { id: s.id, action: action } }).then(function (r) {
        row.hidden = true;
        msg.replaceChildren(h('p', { class: 'notice ok' }, (r && r.message) ? ht(r.message) : (action === 'accept' ? 'Noted. No money was moved.' : 'Okay, we will leave it for now.')));
      }, function (e) {
        row.querySelectorAll('button').forEach(function (b) { b.disabled = false; });
        if (!e.handled) msg.replaceChildren(errorNode(e));
      });
    }
    row.appendChild(h('button', { type: 'button', class: 'btn', onclick: function () { act('accept'); } }, s.action_label || 'Accept'));
    row.appendChild(h('button', { type: 'button', class: 'btn secondary', onclick: function () { act('snooze'); } }, 'Not now'));
    box.appendChild(row); box.appendChild(msg);
    return box;
  }

  // ---------- wave 2 features ----------
  function settingsLink(text) {
    return h('button', { type: 'button', class: 'link-btn inline quiet-link', onclick: function () { openSettings(); } }, text);
  }

  // --- Can I afford this? ---
  var VERDICT_WORDS = { yes: 'Yes', tight: 'Tight', no: 'Not right now' };

  function affordResult(d) {
    var v = VERDICT_WORDS[d.verdict] ? d.verdict : 'tight';
    var box = h('div', { class: 'afford-result' });
    box.appendChild(h('div', { class: 'verdict v-' + v }, VERDICT_WORDS[v]));
    if (d.verdict_text) box.appendChild(h('p', null, ht(d.verdict_text)));
    if (d.after != null) {
      box.appendChild(h('p', { class: 'small' }, h('b', null, 'Left until payday: ' + money(d.after)),
        d.per_day_after != null ? ' (' + money(d.per_day_after) + ' a day)' : ''));
    }
    var ge = d.goal_effect;
    if (ge && ge.delay_text) {
      box.appendChild(h('p', { class: 'goal-line' }, ht(ge.delay_text)));
    } else if (!ge) {
      box.appendChild(h('p', { class: 'small' }, settingsLink('Set a savings goal')));
    }
    var alts = (d.alternatives || []).filter(function (a) { return typeof a === 'string' && a; });
    if (alts.length) {
      var ul = h('ul', { class: 'bullets small' });
      alts.forEach(function (a) { ul.appendChild(h('li', null, ht(a))); });
      box.appendChild(ul);
    }
    var ex = explainNode(d);
    if (ex) box.appendChild(ex);
    var ev = evidenceLink(d.evidence, 'Where this comes from');
    if (ev) box.appendChild(ev);
    return box;
  }

  function affordForm(out) {
    var uid = 'af-' + Math.random().toString(36).slice(2, 7);
    var item = h('input', { type: 'text', class: 'input', id: uid + '-i', maxlength: '60', placeholder: 'A jacket', autocomplete: 'off' });
    var price = h('input', { type: 'number', class: 'input', id: uid + '-p', min: '0', step: '1', inputmode: 'decimal', placeholder: '300' });
    var btn = h('button', { type: 'button', class: 'btn block' }, 'Check');
    function run() {
      var p = Number(price.value);
      if (!isFinite(p) || p <= 0) { out.replaceChildren(h('p', { class: 'notice' }, 'Enter a price above zero.')); return; }
      btn.disabled = true;
      out.replaceChildren(loadingNode('Checking...'));
      api('/api/afford', { method: 'POST', body: { item: item.value.trim() || 'this', price: p } }).then(function (d) {
        btn.disabled = false;
        out.replaceChildren(affordResult(d || {}));
      }, function (e) {
        btn.disabled = false;
        if (e.handled) return;
        out.replaceChildren(errorNode(e));
      });
    }
    btn.addEventListener('click', run);
    [item, price].forEach(function (el) {
      el.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); run(); } });
    });
    return h('div', null,
      h('div', { class: 'form-grid' },
        h('div', null, h('label', { for: uid + '-i' }, 'What is it?'), item),
        h('div', null, h('label', { for: uid + '-p' }, 'Price in euros'), price)),
      btn);
  }

  // --- Alerts ---
  function alertNode(a, onDismiss) {
    var sev = a.severity === 'notice' ? 'notice' : 'info';
    var box = h('div', { class: 'alert ' + sev });
    var head = h('div', { class: 'alert-head' }, h('b', null, ht(a.title) || 'Something to look at'));
    if (onDismiss) {
      head.appendChild(h('button', { type: 'button', class: 'x-btn', 'aria-label': 'Dismiss: ' + (a.title || 'alert'), onclick: onDismiss }, '×'));
    }
    box.appendChild(head);
    if (a.detail) box.appendChild(h('p', { class: 'small' }, ht(a.detail)));
    var ev = evidenceLink(a.evidence, a.title || 'Transactions');
    if (ev) box.appendChild(ev);
    return box;
  }

  // --- Challenges ---
  function isMoneyUnit(u) { return /eur|€/i.test(String(u || '')); }

  function progressNode(p, onStop) {
    var money_ = isMoneyUnit(p.unit);
    var cur = num(p.current), tgt = num(p.target);
    var fmt = function (v) { return money_ ? money(v) : String(Math.round(v * 10) / 10); };
    var status = ['on_track', 'done', 'missed', 'at_risk'].indexOf(p.status) >= 0 ? p.status : 'on_track';
    var fill = h('div', { class: 'prog-fill s-' + status });
    fill.style.width = (tgt > 0 ? Math.max(0, Math.min(100, cur / tgt * 100)) : 0) + '%';
    var box = h('div', { class: 'challenge' });
    box.appendChild(h('div', { class: 'trait' }, h('b', null, ht(p.title) || 'Your challenge'), h('span', { class: 'small' }, fmt(cur) + ' of ' + fmt(tgt))));
    box.appendChild(h('div', { class: 'prog-track', role: 'img', 'aria-label': fmt(cur) + ' of ' + fmt(tgt) }, fill));
    if (p.text) box.appendChild(h('p', { class: 'small' }, ht(p.text)));
    var ev = evidenceLink(p.evidence, p.title || 'Your challenge');
    var row = h('div', { class: 'link-row' });
    if (ev) row.appendChild(ev);
    if (onStop) row.appendChild(h('button', { type: 'button', class: 'link-btn small-link muted-link', onclick: onStop }, 'Stop challenge'));
    if (row.childNodes.length) box.appendChild(row);
    return box;
  }

  function optionsNode(options, onPick) {
    var box = h('div', { class: 'challenge-options' });
    options.forEach(function (o) {
      var btn = h('button', { type: 'button', class: 'btn secondary small-btn' }, "I'm in");
      btn.addEventListener('click', function () { btn.disabled = true; onPick(o, btn); });
      box.appendChild(h('div', { class: 'opt' },
        h('div', { class: 'opt-text' }, h('b', null, ht(o.title) || 'Challenge'), o.why ? h('span', { class: 'small muted' }, ht(o.why)) : null),
        btn));
    });
    return box;
  }

  // data: {enabled, active, options}. refresh() reloads the container after a change.
  function challengeNode(d, refresh) {
    if (!d) return null;
    var msg = h('div', { 'aria-live': 'polite' });
    function post(body, btn) {
      api('/api/challenge', { method: 'POST', body: body }).then(function () { refresh(); }, function (e) {
        if (btn) btn.disabled = false;
        if (!e.handled) msg.replaceChildren(errorNode(e));
      });
    }
    if (d.active) {
      var c = card('Your challenge');
      c.classList.add('light');
      c.appendChild(progressNode(d.active, refresh ? function () { post({ stop: true }); } : null));
      c.appendChild(msg);
      return c;
    }
    var opts = Array.isArray(d.options) ? d.options.slice(0, 3) : [];
    if (d.enabled && opts.length) {
      var c2 = card('Try a challenge', 'Optional');
      c2.classList.add('light');
      c2.appendChild(h('p', { class: 'small muted' }, 'Pick one if you like. Skip it if you do not.'));
      c2.appendChild(optionsNode(opts, function (o, btn) { if (refresh) post({ id: o.id }, btn); }));
      c2.appendChild(msg);
      return c2;
    }
    return null;
  }

  // --- Leak finder ---
  function colChart(items, labelOf, valueOf, titleOf, compact, summary) {
    var vals = items.map(function (it) { return Math.max(0, num(valueOf(it))); });
    var mx = Math.max.apply(null, vals.concat([0.0001]));
    var top = vals.indexOf(Math.max.apply(null, vals.concat([0])));
    var wrap = h('div', { class: 'cols' + (compact ? ' compact' : ''), role: 'img', 'aria-label': summary || '' });
    items.forEach(function (it, i) {
      var fill = h('div', { class: 'col-fill' + (i === top && vals[i] > 0 ? ' peak' : '') });
      fill.style.height = Math.max(vals[i] > 0 ? 3 : 0, vals[i] / mx * 100) + '%';
      wrap.appendChild(h('div', { class: 'col', title: titleOf(it) },
        h('div', { class: 'col-track' }, fill),
        h('span', { class: 'col-label', 'aria-hidden': 'true' }, labelOf(it, i))));
    });
    return wrap;
  }

  function leaksBody(d) {
    var box = h('div', { class: 'leaks' });
    if (d.headline) box.appendChild(h('p', { class: 'avg-headline' }, ht(d.headline)));
    var sm = d.small || {};
    var thr = sm.threshold != null ? sm.threshold : 10;
    box.appendChild(h('div', null,
      h('p', { class: 'eyebrow' }, 'Small purchases under ' + money(thr).replace(/\.00$/, '')),
      h('div', { class: 'stats' }, stat(money(sm.total), 'In total'), stat(String(num(sm.count)), 'Purchases'),
        sm.per_month != null ? stat(money(sm.per_month), 'A month') : null)));
    var tops = (sm.top_labels || []).map(function (x) { return typeof x === 'string' ? x : (x && (x.label || x.name)); }).filter(Boolean);
    if (tops.length) box.appendChild(h('p', { class: 'tiny' }, 'Mostly: ' + tops.slice(0, 3).join(', ') + '.'));
    var wd = d.by_weekday || [];
    if (wd.length) {
      box.appendChild(h('p', { class: 'eyebrow' }, 'By weekday'));
      box.appendChild(colChart(wd, function (x) { return x.day; }, function (x) { return x.total; },
        function (x) { return x.day + ': ' + money(x.total) + ', ' + num(x.count) + (Number(x.count) === 1 ? ' purchase' : ' purchases'); }, false,
        'Everyday spending by weekday' + (d.peak && d.peak.text ? '. ' + d.peak.text : '')));
    }
    var hr = d.by_hour || [];
    if (hr.length) {
      box.appendChild(h('p', { class: 'eyebrow' }, 'By hour of the day'));
      box.appendChild(colChart(hr, function (x) { return (x.hour % 6 === 0) ? String(x.hour) : ''; }, function (x) { return x.total; },
        function (x) { return x.hour + ':00: ' + money(x.total) + ', ' + num(x.count) + (Number(x.count) === 1 ? ' purchase' : ' purchases'); }, true,
        'Everyday spending by hour of the day'));
    }
    if (d.peak && d.peak.text) box.appendChild(h('p', { class: 'small' }, ht(d.peak.text)));
    if (d.payday_week && d.payday_week.text) box.appendChild(h('p', { class: 'small' }, ht(d.payday_week.text)));
    box.appendChild(h('p', { class: 'eyebrow' }, 'Repeating charges'));
    var subs = d.subscriptions || [];
    if (!subs.length) {
      box.appendChild(h('p', { class: 'small muted' }, 'No repeating charges found in the last six months.'));
    } else {
      var ul = h('ul', { class: 'list' });
      subs.forEach(function (s) {
        ul.appendChild(h('li', null,
          h('div', { class: 'trait' }, h('b', null, s.label || 'Repeating charge'), h('b', null, money(s.amount) + ' a month')),
          h('div', { class: 'tiny' }, (s.yearly != null ? money(s.yearly) + ' a year' : '') + (s.last_seen ? ', last seen ' + fmtDate(s.last_seen) : ''))));
      });
      box.appendChild(ul);
    }
    var ex = explainNode(d);
    if (ex) box.appendChild(ex);
    var ev = evidenceLink(d.evidence, 'Where this comes from');
    if (ev) box.appendChild(ev);
    return box;
  }

  // --- Your area ---
  function areaBody(d) {
    var box = h('div', { class: 'area' });
    if (d.area_name) box.appendChild(h('p', { class: 'avg-headline' }, d.area_name));
    var rows = d.rows || [];
    rows.forEach(function (r) {
      var val = r.text != null && r.text !== '' ? r.text : (r.value != null ? String(r.value) + (r.unit ? ' ' + r.unit : '') : '-');
      box.appendChild(h('div', { class: 'trait area-row' }, h('span', null, r.name || r.key), h('b', null, ht(val))));
    });
    (d.compare || []).forEach(function (c) {
      if (c && c.text) box.appendChild(h('p', { class: 'small' }, ht(c.text)));
    });
    if (d.note) box.appendChild(h('p', { class: 'tiny' }, ht(d.note)));
    if (rows.length && !/^Source/i.test(String(d.note || ''))) box.appendChild(h('p', { class: 'tiny' }, 'Source: Statistics Finland, Paavo' + (d.year ? ' (' + d.year + ')' : '') + '.'));
    var ex = explainNode(d);
    if (ex) box.appendChild(ex);
    return box;
  }

  // --- Quiz awareness ---
  function sparkline(values) {
    var w = 100, ht_ = 28, n = values.length;
    var svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('viewBox', '0 0 ' + w + ' ' + ht_);
    svg.setAttribute('class', 'spark');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'How close your recent guesses were');
    var pts = values.map(function (v, i) {
      var x = n > 1 ? 3 + i * (w - 6) / (n - 1) : w / 2;
      var y = 3 + (ht_ - 6) * (1 - Math.max(0, Math.min(100, num(v))) / 100);
      return x.toFixed(1) + ',' + y.toFixed(1);
    });
    var line = document.createElementNS(SVG_NS, 'polyline');
    line.setAttribute('points', pts.join(' '));
    line.setAttribute('fill', 'none');
    line.setAttribute('stroke', 'currentColor');
    line.setAttribute('stroke-width', '2');
    line.setAttribute('stroke-linecap', 'round');
    line.setAttribute('stroke-linejoin', 'round');
    svg.appendChild(line);
    var last = pts[pts.length - 1].split(',');
    var dot = document.createElementNS(SVG_NS, 'circle');
    dot.setAttribute('cx', last[0]); dot.setAttribute('cy', last[1]); dot.setAttribute('r', '3');
    dot.setAttribute('fill', 'currentColor');
    svg.appendChild(dot);
    return svg;
  }

  function quizStatsNode(s) {
    if (!s || !num(s.count)) return null;
    var box = h('div', { class: 'awareness' });
    if (s.awareness_score != null) {
      box.appendChild(h('p', { class: 'aw-score' }, 'Awareness score ' + Math.round(num(s.awareness_score)) + '/100'));
    }
    var pts = (s.points || []).map(function (p) { return p && p.accuracy; }).filter(function (v) { return v != null; });
    if (pts.length) box.appendChild(sparkline(pts));
    if (s.text) box.appendChild(h('p', { class: 'small' }, ht(s.text)));
    return box;
  }

  // --- Savings leakage and override chat cards ---
  function savingsLeakBody(d) {
    var box = h('div');
    var text = d.text || d.detail || d.title || '';
    if (text) box.appendChild(h('p', null, ht(text)));
    var ws = d.withdrawals || [];
    if (ws.length) {
      var ul = h('ul', { class: 'list' });
      ws.slice(0, 6).forEach(function (w) {
        var extra = [];
        if (w.days_before_payday != null) extra.push(num(w.days_before_payday) + ' days before payday');
        if (w.balance_before != null) extra.push('balance before ' + money(w.balance_before));
        ul.appendChild(h('li', null, h('div', { class: 'trait' }, h('span', null, fmtDate(w.d)), h('b', null, money(w.amount))),
          extra.length ? h('div', { class: 'tiny' }, extra.join(', ')) : null));
      });
      box.appendChild(ul);
    }
    return box;
  }

  // --- Transactions used under a chat answer ---
  function usedCount(used) {
    // The number of transactions used, not the number of rows on screen.
    return (used || []).reduce(function (s, g) {
      if (!g || typeof g !== 'object') return s;
      return s + (g.count != null ? num(g.count) : (Array.isArray(g.rows) ? g.rows.length : 0));
    }, 0);
  }

  // The transactions behind an answer: a small button and the list it opens.
  function usedParts(used) {
    if (!Array.isArray(used) || !used.length) return null;
    var n = usedCount(used);
    var id = 'used-' + Math.random().toString(36).slice(2, 8);
    var body = h('div', { class: 'used-body', id: id, hidden: true });
    var btn = h('button', { type: 'button', class: 'act-btn', 'aria-expanded': 'false', 'aria-controls': id }, 'Transactions (' + n + ')');
    used.forEach(function (g) {
      if (!g || typeof g !== 'object') return;
      var rows = Array.isArray(g.rows) ? g.rows : [];
      var cnt = g.count != null ? num(g.count) : rows.length;
      var grp = h('div', { class: 'used-group' });
      grp.appendChild(h('div', { class: 'trait' }, h('b', { class: 'used-title' }, ht(g.title) || 'Transactions'),
        h('span', { class: 'tiny' }, cnt + (cnt === 1 ? ' transaction' : ' transactions') + ', ' + money(Math.abs(num(g.total))))));
      if (!rows.length) grp.appendChild(h('p', { class: 'small muted' }, 'No transactions matched.'));
      else grp.appendChild(txList({ rows: rows }, { bare: true }));
      if (rows.length && rows.length < cnt) grp.appendChild(h('p', { class: 'tiny' }, 'Showing ' + rows.length + ' of ' + cnt + '.'));
      body.appendChild(grp);
    });
    btn.addEventListener('click', function () {
      var open = body.hidden;
      body.hidden = !open;
      btn.setAttribute('aria-expanded', String(open));
    });
    return { btn: btn, body: body };
  }

  // --- Balance forecast ---
  function svgEl(name, attrs) {
    var el = document.createElementNS(SVG_NS, name);
    for (var k in attrs) { if (Object.prototype.hasOwnProperty.call(attrs, k)) el.setAttribute(k, String(attrs[k])); }
    return el;
  }

  function forecastChart(d) {
    var pts = d.points || [];
    if (pts.length < 2) return null;
    var W = 300, H = 120, padL = 4, padR = 4, padT = 8, padB = 8;
    var bal = pts.map(function (p) { return num(p.balance); });
    var lo = Math.min.apply(null, bal.concat([0])), hi = Math.max.apply(null, bal.concat([0]));
    if (hi - lo < 1) hi = lo + 1;
    function X(i) { return padL + i * (W - padL - padR) / (pts.length - 1); }
    function Y(v) { return padT + (H - padT - padB) * (1 - (v - lo) / (hi - lo)); }
    var svg = svgEl('svg', { viewBox: '0 0 ' + W + ' ' + H, class: 'fc', role: 'img',
      'aria-label': 'Projected balance until payday. ' + (d.text || '') });
    var zy = Y(0);
    svg.appendChild(svgEl('line', { x1: padL, x2: W - padR, y1: zy, y2: zy, class: 'fc-zero' }));
    var zt = svgEl('text', { x: W - padR, y: zy - 3, 'text-anchor': 'end', class: 'fc-note' });
    zt.textContent = '€0';
    svg.appendChild(zt);
    svg.appendChild(svgEl('polyline', { points: pts.map(function (p, i) { return X(i).toFixed(1) + ',' + Y(num(p.balance)).toFixed(1); }).join(' '), class: 'fc-line' }));
    pts.forEach(function (p, i) {
      if (p.events && p.events.length) svg.appendChild(svgEl('circle', { cx: X(i).toFixed(1), cy: Y(num(p.balance)).toFixed(1), r: 3, class: 'fc-bill' }));
    });
    if (d.lowest && d.lowest.d) {
      var li = -1;
      pts.forEach(function (p, i) { if (p.d === d.lowest.d) li = i; });
      if (li >= 0) svg.appendChild(svgEl('circle', { cx: X(li).toFixed(1), cy: Y(num(pts[li].balance)).toFixed(1), r: 5, class: 'fc-low' }));
    }
    return svg;
  }

  function forecastBody(d) {
    var box = h('div', { class: 'forecast' });
    if (d.text) box.appendChild(h('p', { class: 'fc-text' }, ht(d.text)));
    var chart = forecastChart(d);
    if (chart) {
      box.appendChild(chart);
      var low = d.lowest && d.lowest.d ? 'Lowest: ' + money(d.lowest.balance) + ' on ' + fmtDate(d.lowest.d) : '';
      box.appendChild(h('p', { class: 'tiny fc-legend' }, (d.from ? fmtDate(d.from) : '') + ' to ' + (d.to ? fmtDate(d.to) : '') + (low ? '. ' + low + '.' : '')));
    }
    var ev = [];
    (d.points || []).forEach(function (p) {
      (p.events || []).forEach(function (e) { ev.push({ d: p.d, label: e.label, amount: e.amount }); });
    });
    if (ev.length) {
      var ul = h('ul', { class: 'list fc-events' });
      ev.forEach(function (e) {
        ul.appendChild(h('li', null, h('div', { class: 'trait' }, h('span', { class: 'small' }, fmtDate(e.d) + ', ' + (e.label || 'Bill')), h('b', { class: 'small' }, money(e.amount)))));
      });
      box.appendChild(ul);
    }
    return box;
  }

  // Loaded the first time the hero's calculation opens. Silent when the endpoint is missing.
  function loadForecastInto(host) {
    api('/api/forecast').then(function (d) {
      if (!d || !(d.points || []).length) return;
      host.replaceChildren(h('p', { class: 'eyebrow' }, 'Until payday'), forecastBody(d));
    }, function () {});
  }

  // --- Payday plan ---
  function planBody(d) {
    var box = h('div', { class: 'plan' });
    if (d.text) box.appendChild(h('p', null, ht(d.text)));
    var lines = d.lines || [];
    var total = lines.reduce(function (s, l) { return s + Math.max(0, num(l.amount)); }, 0);
    if (lines.length && total > 0) {
      var stack = h('div', { class: 'stack', role: 'img', 'aria-label': 'Suggested split of your next salary' });
      lines.forEach(function (l) {
        var seg = h('span', { class: 'b-' + (BASKET_NAMES[l.key] ? l.key : 'other') });
        seg.style.width = (Math.max(0, num(l.amount)) / total * 100) + '%';
        stack.appendChild(seg);
      });
      box.appendChild(stack);
    }
    lines.forEach(function (l) {
      var k = BASKET_NAMES[l.key] ? l.key : 'other';
      box.appendChild(h('div', { class: 'plan-line' },
        h('div', { class: 'trait' },
          h('span', null, h('span', { class: 'dot b-' + k, 'aria-hidden': 'true' }), ' ', h('b', null, l.name || BASKET_NAMES[k] || l.key)),
          h('b', null, money(l.amount) + (l.share != null ? ' (' + pct(num(l.share) <= 1 ? num(l.share) * 100 : l.share) + ')' : ''))),
        l.why ? h('p', { class: 'tiny' }, ht(l.why)) : null));
    });
    if (d.everyday_per_week != null) {
      box.appendChild(h('p', { class: 'small' }, h('b', null, 'Everyday spending: ' + money(d.everyday_per_week) + ' a week'),
        d.everyday_per_day != null ? ' (' + money(d.everyday_per_day) + ' a day)' : ''));
    }
    var g = d.goal_line;
    if (g && g.name) {
      box.appendChild(h('p', { class: 'goal-line' }, 'Towards ' + g.name + ': ' + money(g.amount) + ' a month'
        + (g.months_to_goal != null ? ', about ' + Math.ceil(num(g.months_to_goal)) + ' months to go' : '') + '.'));
    }
    box.appendChild(h('p', { class: 'small' }, h('b', null, 'This is a plan, not a transfer.')));
    var ex = explainNode(d);
    if (ex) box.appendChild(ex);
    var ev = evidenceLink(d.evidence, 'Where this comes from');
    if (ev) box.appendChild(ev);
    return box;
  }

  // ---------- wave 3: explain a text, latest purchase, patterns, goal plan ----------
  var EXPLAIN_MIN = 40, EXPLAIN_MAX = 6000;

  function isAiMode(mode) { return mode === 'claude' || mode === 'gemini'; }

  function modeBadge(mode) {
    return h('span', { class: 'badge' + (isAiMode(mode) ? ' ai' : '') }, isAiMode(mode) ? 'AI model' : 'On-device rules');
  }

  function plural(n, one, many) { return n + ' ' + (n === 1 ? one : many); }

  function explainCard(d) {
    var c = cardShell('In plain words');
    var meta = h('div', { class: 'meta' }, modeBadge(d.mode));
    var red = num(d.redactions);
    if (red > 0) meta.appendChild(h('span', { class: 'badge' }, plural(red, 'personal detail', 'personal details') + ' removed'));
    c.appendChild(meta);
    if (d.summary) c.appendChild(h('p', { class: 'ex-summary' }, String(d.summary)));
    var kp = (d.key_points || []).filter(function (x) { return typeof x === 'string' && x; });
    if (kp.length) {
      var ul = h('ul', { class: 'bullets-tight' });
      kp.forEach(function (x) { ul.appendChild(h('li', null, x)); });
      c.appendChild(h('div', null, h('p', { class: 'eyebrow' }, 'Key points'), ul));
    }
    var terms = (d.terms || []).filter(function (x) { return x && x.term; });
    if (terms.length) {
      var tl = h('dl', { class: 'terms' });
      terms.forEach(function (x) {
        tl.appendChild(h('dt', null, String(x.term)));
        tl.appendChild(h('dd', null, String(x.meaning || '')));
      });
      c.appendChild(h('div', null, h('p', { class: 'eyebrow' }, 'Terms explained'), tl));
    }
    var wo = (d.watch_out || []).filter(function (x) { return typeof x === 'string' && x; });
    if (wo.length) {
      var wl = h('ul', { class: 'bullets-tight' });
      wo.forEach(function (x) { wl.appendChild(h('li', null, x)); });
      c.appendChild(h('div', { class: 'notice watch' }, h('b', null, 'Watch out for'), wl));
    }
    if (d.notice) c.appendChild(h('p', { class: 'tiny' }, ht(d.notice)));
    if (d.disclaimer) c.appendChild(h('p', { class: 'disclaimer' }, String(d.disclaimer)));
    return c;
  }

  function explainErrorText(e) {
    if (e.status === 400 || e.status === 422 || e.status === 413) {
      return 'Please paste between ' + EXPLAIN_MIN + ' and ' + EXPLAIN_MAX.toLocaleString('en-US') + ' characters of text.';
    }
    if (e.status === 429) return 'You are going a bit fast. Wait a moment and try again.';
    if (e.status === 404) return 'Explaining a text is not available right now.';
    return e.message || 'Something went wrong. Please try again.';
  }

  // Opens the "Explain a text" sheet. onResult(text, data) lets the chat add the exchange to the thread.
  function openExplainSheet(onResult) {
    var body = openSheet('Explain a text');
    var uid = 'ex-' + Math.random().toString(36).slice(2, 7);
    var ta = h('textarea', { class: 'input explain-text', id: uid + '-t', rows: '9', maxlength: String(EXPLAIN_MAX + 2000), placeholder: 'Paste text from a loan agreement or a fund prospectus', autocomplete: 'off', 'aria-describedby': uid + '-c ' + uid + '-p' });
    var count = h('p', { class: 'tiny', id: uid + '-c' });
    var form = h('div', { class: 'explain-form' },
      h('label', { for: uid + '-t', class: 'field-label' }, 'Text to explain'), ta, count,
      h('p', { class: 'tiny', id: uid + '-p' }, 'Personal identity codes, account numbers, e-mail addresses and phone numbers are removed before anything is sent to an AI model.'));
    var go_ = h('button', { type: 'button', class: 'btn block' }, 'Explain this text');
    var out = h('div', { 'aria-live': 'polite' });
    form.appendChild(go_);
    body.appendChild(form);
    body.appendChild(out);
    function len() { return ta.value.trim().length; }
    function paint() {
      var n = len();
      var ok = n >= EXPLAIN_MIN && n <= EXPLAIN_MAX;
      count.textContent = n.toLocaleString('en-US') + ' of ' + EXPLAIN_MAX.toLocaleString('en-US') + ' characters'
        + (n < EXPLAIN_MIN ? ' (at least ' + EXPLAIN_MIN + ' needed)' : (n > EXPLAIN_MAX ? ' (too long, please shorten it)' : ''));
      go_.disabled = !ok;
    }
    ta.addEventListener('input', paint);
    paint();
    go_.addEventListener('click', function () {
      var text = ta.value.trim();
      if (text.length < EXPLAIN_MIN || text.length > EXPLAIN_MAX) { paint(); return; }
      go_.disabled = true; ta.disabled = true;
      out.replaceChildren(loadingNode('Reading your text. The AI model can take several seconds, please wait...'));
      api('/api/explain', { method: 'POST', body: { text: text } }).then(function (d) {
        d = d || {};
        form.hidden = true;
        var again = h('button', { type: 'button', class: 'btn secondary block' }, 'Explain another text');
        again.addEventListener('click', function () {
          out.replaceChildren(); form.hidden = false; ta.disabled = false; ta.value = ''; paint(); ta.focus();
        });
        out.replaceChildren(explainCard(d), again);
        if (onResult) { try { onResult(text, d); } catch (e) { /* the chat may be gone */ } }
      }, function (e) {
        ta.disabled = false; paint();
        if (e.handled) return;
        out.replaceChildren(h('div', { class: 'notice err', role: 'alert' }, explainErrorText(e)));
      });
    });
    ta.focus();
  }

  // --- latest purchase ---
  function purchaseCard(d) {
    var c = cardShell('Latest purchase', d.tx && d.tx.d ? fmtDate(d.tx.d) : '');
    var tx = d.tx || {};
    if (tx.display_label || tx.label) {
      c.appendChild(h('div', { class: 'trait' }, h('b', null, String(tx.display_label || tx.label)), h('b', null, money(Math.abs(num(tx.amount))))));
    }
    if (d.text) c.appendChild(h('p', null, ht(d.text)));
    var hb = d.habit;
    if (hb && hb.yearly != null && d.text) {
      c.appendChild(h('div', { class: 'stats' },
        stat(String(Math.round(num(hb.per_week) * 10) / 10), 'a week'),
        stat(money(hb.avg_amount), 'each'),
        stat(money(hb.yearly, { hero: true }), 'a year')));
    }
    var eq = (d.equivalents || []).filter(function (x) { return typeof x === 'string' && x; });
    if (eq.length) {
      var ul = h('ul', { class: 'bullets-tight' });
      eq.forEach(function (x) { ul.appendChild(h('li', null, ht(x))); });
      c.appendChild(ul);
    }
    if (d.note) c.appendChild(h('p', { class: 'tiny' }, ht(d.note)));
    return finishCard(c, d, 'Where this comes from');
  }

  // --- patterns ---
  function patternsBody(d) {
    var box = h('div', { class: 'patterns' });
    var list = (d && d.patterns) || [];
    if (!list.length) {
      box.appendChild(h('p', { class: 'small muted' }, 'No clear spending patterns yet. I will say so when one shows up.'));
    }
    list.slice(0, 3).forEach(function (p, i) {
      var id = 'why-' + Math.random().toString(36).slice(2, 8) + i;
      var item = h('div', { class: 'pattern' });
      var head = h('div', { class: 'trait' }, h('b', { class: 'pattern-title' }, ht(p.title) || 'A pattern'));
      if (p.uplift_pct != null) head.appendChild(h('span', { class: 'pill' }, '+' + Math.round(num(p.uplift_pct)) + '%'));
      item.appendChild(head);
      if (p.text) item.appendChild(h('p', { class: 'small' }, ht(p.text)));
      var whyLines = (p.why || []).filter(function (x) { return typeof x === 'string' && x; });
      if (whyLines.length) {
        var why = h('div', { class: 'why', id: id, hidden: true });
        var ul = h('ul', { class: 'bullets-tight' });
        whyLines.forEach(function (x) { ul.appendChild(h('li', null, ht(x))); });
        why.appendChild(ul);
        var btn = h('button', { type: 'button', class: 'btn secondary small-btn', 'aria-expanded': 'false', 'aria-controls': id }, 'Why?');
        btn.addEventListener('click', function () {
          var open = why.hidden;
          why.hidden = !open;
          btn.setAttribute('aria-expanded', String(open));
          btn.textContent = open ? 'Hide' : 'Why?';
        });
        item.appendChild(btn); item.appendChild(why);
      }
      var ev = evidenceLink(p.evidence, p.title || 'Transactions');
      if (ev) item.appendChild(ev);
      box.appendChild(item);
    });
    var ex = explainNode(d);
    if (ex) box.appendChild(ex);
    return box;
  }

  // --- goal plan ---
  function applyGoalToSettings(g) {
    var n = document.getElementById('goal-name'), tg = document.getElementById('goal-target'), sv = document.getElementById('goal-saved');
    if (!n || !tg || !sv || !g) return;
    n.value = g.name || ''; tg.value = String(num(g.target)); sv.value = String(num(g.saved));
  }

  function deadlineText(dl) {
    if (!dl) return '';
    if (/^\d{4}-\d{2}-\d{2}/.test(dl)) return fmtDate(dl);
    if (/^\d{4}-\d{2}$/.test(dl)) return fmtMonth(dl);
    return String(dl);
  }

  function goalPlanCard(d) {
    var c = cardShell('Goal plan', d.name ? String(d.name) : '');
    var needs = Array.isArray(d.needs) ? d.needs : [];
    if (d.text) c.appendChild(h('p', null, ht(d.text)));
    if (needs.length || d.monthly_needed == null) return c;
    var months = Math.max(0, Math.ceil(num(d.months_left)));
    c.appendChild(h('div', { class: 'stats' },
      stat(plural(months, 'month', 'months'), 'left' + (d.deadline ? ' until ' + deadlineText(d.deadline) : '')),
      stat(money(d.target, { hero: true }), 'goal' + (num(d.saved) > 0 ? ', ' + money(d.saved, { hero: true }) + ' saved' : ''))));
    var mx = Math.max(num(d.monthly_needed), num(d.current_monthly_saving), 1);
    c.appendChild(barRow('Needed a month', num(d.monthly_needed), mx, 'b-unexpected'));
    c.appendChild(barRow('You save now', Math.max(0, num(d.current_monthly_saving)), mx, 'you'));
    if (d.gap != null && num(d.gap) > 0) {
      c.appendChild(h('p', { class: 'small' }, h('b', null, 'About ' + money(d.gap, { hero: true }).replace(/\.00$/, '') + ' a month to find.')));
    } else if (d.feasible) {
      c.appendChild(h('p', { class: 'small' }, h('b', null, 'At your current pace you would get there in time.')));
    }
    var ways = (d.ways || []).filter(function (w) { return w && w.title; });
    if (ways.length) {
      var ul = h('ul', { class: 'list' });
      ways.slice(0, 3).forEach(function (w) {
        ul.appendChild(h('li', null, h('div', { class: 'trait' }, h('span', { class: 'small' }, ht(w.title)), w.saved_monthly != null ? h('b', { class: 'small' }, money(w.saved_monthly) + '/mo') : null)));
      });
      c.appendChild(h('div', null, h('p', { class: 'eyebrow' }, 'Ways to close the gap'), ul));
    }
    var g = d.goal;
    if (g && g.name && num(g.target) > 0) {
      var msg = h('div', { 'aria-live': 'polite' });
      var save = h('button', { type: 'button', class: 'btn block' }, 'Save as my goal');
      save.addEventListener('click', function () {
        save.disabled = true;
        msg.replaceChildren(loadingNode('Saving...'));
        api('/api/goal', { method: 'POST', body: { name: g.name, target: num(g.target), saved: num(g.saved) } }).then(function (r) {
          save.hidden = true;
          applyGoalToSettings((r && r.goal) || g);
          msg.replaceChildren(h('p', { class: 'notice ok', role: 'status' }, 'Saved. You can change it in Settings.'));
        }, function (e) {
          save.disabled = false;
          if (e.handled) return;
          msg.replaceChildren(errorNode(e));
        });
      });
      c.appendChild(save); c.appendChild(msg);
    }
    return finishCard(c, d, 'Where this comes from');
  }

  // ---------- CHAT ----------
  // Plain text with line breaks, **bold** and simple bullet lines. Built from nodes only.
  function richText(text) {
    var box = h('div');
    var lines = ht(text).split(/\r?\n/);
    var ul = null;
    function inline(parent, s) {
      var parts = s.split(/(\*\*[^*]+\*\*)/);
      parts.forEach(function (p) {
        if (!p) return;
        if (/^\*\*[^*]+\*\*$/.test(p)) parent.appendChild(h('strong', null, p.slice(2, -2)));
        else parent.appendChild(document.createTextNode(p));
      });
    }
    lines.forEach(function (line) {
      var m = /^\s*(?:[-*•])\s+(.*)$/.exec(line);
      if (m) {
        if (!ul) { ul = h('ul'); box.appendChild(ul); }
        var li = h('li'); inline(li, m[1]); ul.appendChild(li);
        return;
      }
      ul = null;
      if (!line.trim()) return;
      var p = h('p'); inline(p, line); box.appendChild(p);
    });
    return box;
  }

  // ---------- chat card renderers (shapes: STATE.md 5.3) ----------
  function cardShell(title, sub) {
    var c = h('div', { class: 'card' });
    var head = h('div', { class: 'card-head' }, h('b', null, title));
    if (sub) head.appendChild(h('span', { class: 'tiny' }, sub));
    c.appendChild(head);
    return c;
  }

  function finishCard(c, d, evTitle) {
    var ex = explainNode(d);
    if (ex) c.appendChild(ex);
    var ev = evidenceLink(d && d.evidence, evTitle || 'Transactions');
    if (ev) c.appendChild(ev);
    return c;
  }

  function labelRows(c, list, cls) {
    list = list || [];
    var mx = Math.max.apply(null, list.map(function (x) { return Math.abs(num(x.total != null ? x.total : x.amount)); }).concat([1]));
    list.slice(0, 8).forEach(function (x) {
      var v = num(x.total != null ? x.total : x.amount);
      c.appendChild(barRow(x.label || x.name || x.target || '?', v, mx, cls));
    });
  }

  // ---------- receipts: what was bought, not only what was paid ----------
  function qtyText(l) {
    var q = num(l.qty);
    if (l.unit === 'kg') return String(Math.round(q * 100) / 100) + ' kg';
    return q > 1 ? q + ' x' : '';
  }
  function receiptLines(lines) {
    var ul = h('ul', { class: 'rc-lines' });
    (lines || []).slice(0, 40).forEach(function (l) {
      var q = qtyText(l);
      ul.appendChild(h('li', null,
        h('span', { class: 'rc-name' }, (q ? q + ' ' : '') + (l.name || 'Item')),
        h('span', { class: 'rc-sum' }, money(l.line_total))));
    });
    return ul;
  }
  function receiptNode(r, open) {
    var det = h('details', { class: 'rc' });
    if (open) det.open = true;
    det.appendChild(h('summary', null,
      h('span', null, h('b', null, r.store || 'Receipt'), r.d ? h('span', { class: 'tiny' }, '  ' + fmtDate(r.d)) : null),
      h('b', null, money(r.total))));
    det.appendChild(receiptLines(r.lines));
    if (r.bonus && r.bonus.amount != null) {
      det.appendChild(h('p', { class: 'tiny' }, 'Bonus ' + num(r.bonus.rate_pct) + '%: ' + money(r.bonus.amount) + ' (simulated estimate)'));
    }
    return det;
  }
  function groupBars(c, groups, limit) {
    groups = (groups || []).filter(function (g) { return num(g.total) > 0; }).slice(0, limit || 6);
    var mx = Math.max.apply(null, groups.map(function (g) { return num(g.total); }).concat([1]));
    groups.forEach(function (g) {
      c.appendChild(barRow(g.name || g.group || '?', num(g.total), mx, 'you',
        money(g.total) + (g.share != null ? ' (' + Math.round(num(g.share) * 100) + '%)' : '')));
    });
  }
  function simNote(c, d) {
    if (d && d.note) c.appendChild(h('p', { class: 'tiny sim-note' }, d.note));
  }
  function openReceiptSheet() {
    var body = openSheet('Read a receipt');
    var ta = h('textarea', { class: 'input explain-text', id: 'rc-text', rows: '9', maxlength: '1900', placeholder: 'PRISMA\nKevytmaito 1 l   1,29\nBanaani   1,05\nYHTEENSÄ   2,34', autocomplete: 'off' });
    var go_ = h('button', { type: 'button', class: 'btn block' }, 'Read this receipt');
    body.appendChild(h('div', { class: 'explain-form' },
      h('label', { for: 'rc-text', class: 'field-label' }, 'Paste the text of a receipt'), ta,
      h('p', { class: 'tiny' }, 'For example from the receipts in S-mobiili. One product and its price per line.'), go_));
    go_.addEventListener('click', function () {
      var text = ta.value.trim();
      if (text.length < 10) { ta.focus(); return; }
      closeSheet();
      if (chat) chat.ask('Receipt:\n' + text);
    });
    ta.focus();
  }

  var CARDS = {
    help: function (d) {
      var c = cardShell('What you can ask');
      (d.groups || []).slice(0, 10).forEach(function (g) {
        var row = h('div', { class: 'chips' });
        (g.items || []).slice(0, 4).forEach(function (it) {
          var q = it && (it.question || it.q);
          if (!q) return;
          row.appendChild(h('button', { type: 'button', class: 'chip', onclick: function () { if (chat) chat.ask(q); } }, it.label || q));
        });
        if (row.childNodes.length) { c.appendChild(h('p', { class: 'eyebrow' }, g.title || '')); c.appendChild(row); }
      });
      c.appendChild(h('button', { type: 'button', class: 'btn secondary block', 'aria-haspopup': 'dialog', onclick: function () { openAsk(); } }, 'See everything'));
      return c;
    },
    receipts: function (d) {
      var c = cardShell('Your receipts', d.period ? fmtPeriod(d.period) : '');
      var list = d.receipts || [];
      var n = num(d.count);
      c.appendChild(h('div', { class: 'stats' }, stat(money(d.total), 'In total'), stat(String(n), n === 1 ? 'Receipt' : 'Receipts')));
      if (!list.length) c.appendChild(h('p', { class: 'small muted' }, 'No grocery purchases in this period.'));
      list.forEach(function (r, i) { c.appendChild(receiptNode(r, i === 0)); });
      if (n > list.length && list.length) c.appendChild(h('p', { class: 'tiny' }, 'Showing the latest ' + list.length + ' of ' + n + '.'));
      simNote(c, d);
      return finishCard(c, d, 'Transactions');
    },
    receipt_insights: function (d) {
      var c = cardShell('What you buy', d.period ? fmtPeriod(d.period) : '');
      var tr = d.treats || {};
      c.appendChild(h('div', { class: 'stats' }, stat(money(d.total), 'Groceries'), stat(String(num(d.receipt_count)), 'Receipts'),
        tr.monthly != null ? stat(money(tr.monthly), 'Treats a month') : null));
      var hl = (d.highlights || []).slice(0, 4);
      if (hl.length) {
        var ul = h('ul', { class: 'rc-high' });
        hl.forEach(function (t) { ul.appendChild(h('li', null, ht(t))); });
        c.appendChild(ul);
      }
      if ((d.by_group || []).length) {
        c.appendChild(h('p', { class: 'eyebrow' }, 'By product group'));
        groupBars(c, d.by_group, 6);
      }
      var top = (d.top_products || []).slice(0, 5);
      if (top.length) {
        c.appendChild(h('p', { class: 'eyebrow' }, 'Bought most often'));
        var tl = h('ul', { class: 'list' });
        top.forEach(function (p) {
          tl.appendChild(h('li', null,
            h('div', { class: 'trait' }, h('b', null, p.name || 'Item'), h('b', null, money(p.total))),
            h('div', { class: 'tiny' }, plural(num(p.times), 'time', 'times') + (p.yearly != null ? ', about ' + money(p.yearly) + ' a year at this pace' : ''))));
        });
        c.appendChild(tl);
      }
      if (d.bonus && d.bonus.estimated_total != null) {
        c.appendChild(h('p', { class: 'tiny' }, 'Bonus in the period: about ' + money(d.bonus.estimated_total) + ' (simulated estimate).'));
      }
      simNote(c, d);
      return finishCard(c, d, 'Transactions');
    },
    product_habit: function (d) {
      var m = d.matched;
      var name = m && m.name ? String(m.name).charAt(0).toUpperCase() + String(m.name).slice(1) : 'From your receipts';
      var c = cardShell(name, m && d.period ? fmtPeriod(d.period) : '');
      if (!m) {
        c.appendChild(h('p', null, d.text || 'I could not find that on your receipts.'));
        return c;
      }
      c.appendChild(h('div', { class: 'stats' }, stat(money(d.total), 'Spent'), stat(String(num(d.times)), num(d.times) === 1 ? 'Purchase' : 'Purchases'),
        d.yearly != null ? stat(money(d.yearly), 'A year at this pace') : null));
      if (d.text) c.appendChild(h('p', { class: 'small' }, ht(d.text)));
      simNote(c, d);
      return finishCard(c, d, 'Transactions');
    },
    receipt_parsed: function (d) {
      var c = cardShell(d.store || 'Your receipt', d.date ? fmtDate(d.date) : '');
      var total = d.total != null ? d.total : d.lines_total;
      c.appendChild(h('div', { class: 'big-num' }, money(total)));
      if (d.matches_total === false && d.lines_total != null) {
        c.appendChild(h('div', { class: 'notice' }, 'The lines I could read add up to ' + money(d.lines_total) + ', not the total on the receipt.'));
      }
      c.appendChild(receiptLines(d.lines));
      if ((d.by_group || []).length) {
        c.appendChild(h('p', { class: 'eyebrow' }, 'By product group'));
        groupBars(c, d.by_group, 6);
      }
      var tr = d.treats || {};
      if (num(tr.total) > 0) c.appendChild(h('p', { class: 'small' }, 'Treats: ' + money(tr.total) + ' (' + Math.round(num(tr.share) * 100) + '% of this receipt).'));
      var un = (d.unparsed || []).length;
      if (un) c.appendChild(h('p', { class: 'tiny' }, plural(un, 'line', 'lines') + ' could not be read as a product.'));
      simNote(c, d);
      return c;
    },
    spend: function (d) {
      var c = cardShell('Spending', d.period ? fmtRange(d.period) : '');
      c.appendChild(h('div', { class: 'big-num' }, money(d.total)));
      c.appendChild(h('p', { class: 'small muted' }, num(d.count) + (Number(d.count) === 1 ? ' purchase' : ' purchases')));
      labelRows(c, d.by_label);
      var pb = peerBlock(d);
      if (pb) c.appendChild(pb);
      return finishCard(c, d);
    },
    overview: function (d) {
      var c = cardShell('Your month', d.month ? fmtMonth(d.month) : '');
      c.appendChild(h('div', { class: 'stats' }, stat(money(d.income), 'Money in'), stat(money(d.spent), 'Spent'), stat(money(d.surplus), 'Left over')));
      var b = d.baskets || {};
      var keys = ['regular', 'unexpected', 'everyday'];
      var mx = Math.max.apply(null, keys.map(function (k) { return num(b[k]); }).concat([1]));
      keys.forEach(function (k) { c.appendChild(barRow(BASKET_NAMES[k], num(b[k]), mx, 'b-' + k)); });
      if (d.top_labels && d.top_labels.length) {
        c.appendChild(h('p', { class: 'eyebrow' }, 'Biggest areas'));
        labelRows(c, d.top_labels.slice(0, 5));
      }
      return finishCard(c, d);
    },
    baskets: function (d) {
      var c = cardShell('Three baskets', d.period ? fmtRange(d.period) : '');
      c.appendChild(basketsBlock(d, { tops: true }));
      return c;
    },
    safe_to_spend: function (d) {
      var st = STATUS_TEXT[d.status] ? d.status : 'ok';
      var shortNow = num(d.safe_total) < 0 || num(d.per_day) < 0;
      var c = cardShell('Safe to spend', shortNow ? 'Short until payday' : STATUS_TEXT[st]);
      if (shortNow) {
        c.appendChild(h('div', { class: 'big-num' }, '€0 safe to spend'));
        c.appendChild(h('p', null, 'About ' + money(Math.abs(num(d.safe_total)), { hero: true }).replace(/\.00$/, '') + ' short before payday' + (d.next_payday ? ' on ' + fmtDate(d.next_payday) : '') + '.'));
      } else {
        c.appendChild(h('div', { class: 'big-num' }, money(d.per_day, { hero: true }) + ' per day'));
        c.appendChild(h('p', null, money(d.per_week, { hero: true }) + ' this week'));
      }
      c.appendChild(h('div', { class: 'stats' },
        stat(money(d.balance), 'Balance'), stat('-' + money(d.bills_total), 'Upcoming bills'),
        stat('-' + money(d.unexpected_buffer), 'Buffer'), stat('-' + money(d.planned_savings), 'Planned savings')));
      c.appendChild(h('p', { class: 'small muted' }, 'Until ' + (d.next_payday ? fmtDate(d.next_payday) : 'payday') + ', ' + num(d.days_left) + ' days. Safe in total: ' + money(d.safe_total) + '.'));
      return finishCard(c, d);
    },
    what_if: function (d) {
      var c = cardShell('What if...', num(d.months) + ' months');
      c.appendChild(h('div', { class: 'stats' },
        stat(money(d.saved_monthly), 'Saved per month'), stat(money(d.saved_total), 'Saved in ' + num(d.months) + ' months')));
      c.appendChild(h('p', { class: 'small' }, 'Before: ' + money(d.baseline_monthly) + ' a month. After: ' + money(d.new_monthly) + ' a month.'));
      (d.lines || []).forEach(function (l) {
        c.appendChild(h('div', { class: 'trait' }, h('span', null, targetName(l.target)), h('b', null, money(l.baseline) + ' to ' + money(l.new))));
      });
      return finishCard(c, d);
    },
    spender_type: function (d) {
      var c = cardShell('Your spender type');
      c.appendChild(h('div', { class: 'big-num' }, d.title || d.type || ''));
      if (d.summary) c.appendChild(h('p', null, d.summary));
      (d.traits || []).forEach(function (tr) {
        c.appendChild(h('div', null, h('div', { class: 'trait' }, h('span', null, tr.name), h('b', null, String(tr.value))), tr.note ? h('div', { class: 'tiny' }, tr.note) : null));
      });
      return finishCard(c, d);
    },
    save_more: function (d) {
      var c = cardShell('Ways to save more', d.surplus_avg != null ? 'Average surplus ' + money(d.surplus_avg) : '');
      var ul = h('ul', { class: 'list' });
      (d.ideas || []).forEach(function (i) {
        ul.appendChild(h('li', null, h('div', { class: 'trait' }, h('b', null, i.title), h('b', null, i.saved_monthly != null ? money(i.saved_monthly) + '/mo' : '')), h('div', { class: 'small muted' }, i.detail || '')));
      });
      c.appendChild(ul);
      return finishCard(c, d);
    },
    mortgage: function (d) {
      var c = cardShell('Mortgage readiness', 'Not a decision');
      c.appendChild(h('div', { class: 'stats' },
        stat(money(d.max_loan, { hero: true }), 'Possible loan'),
        stat(money(d.max_price_with_15pct_equity, { hero: true }), 'Home price with 15% equity'),
        stat(money(d.equity_needed, { hero: true }), 'Equity needed'),
        stat(money(d.savings_now, { hero: true }), 'Savings now')));
      if (d.months_to_equity != null) c.appendChild(h('p', { class: 'small' }, num(d.months_to_equity) > 120 ? 'At ' + money(d.monthly_saving) + ' a month the equity is more than ten years away. A higher monthly saving changes that.' : 'At ' + money(d.monthly_saving) + ' a month, about ' + Math.ceil(num(d.months_to_equity)) + ' months to reach the equity.'));
      if (d.check) {
        var k = d.check;
        c.appendChild(h('p', { class: 'small' }, 'For a ' + money(k.price, { hero: true }) + ' home: loan ' + money(k.loan, { hero: true }) + ', loan-to-value ' + pct(num(k.ltv) <= 1 ? num(k.ltv) * 100 : k.ltv) + '. Income ' + (k.income_ok ? 'looks sufficient' : 'looks too low') + ', equity ' + (k.equity_ok ? 'looks sufficient' : 'looks too low') + '.'));
      }
      if (d.rule) c.appendChild(h('p', { class: 'small' }, d.rule));
      if (d.disclaimer) c.appendChild(h('p', { class: 'disclaimer' }, d.disclaimer));
      return finishCard(c, d);
    },
    benchmarks: function (d) {
      var g = d.group || {};
      var c = cardShell('You and people like you', g.n ? 'Group of ' + g.n : '');
      if (g.description) c.appendChild(h('p', { class: 'small muted' }, g.description));
      benchRows(c, d.rows);
      openDataBlock(c, d.open_data);
      return finishCard(c, d);
    },
    averages: function (d) {
      var g = d.group || {};
      var c = cardShell(d.title || 'What is typical?', g.n ? 'Group of ' + g.n : '');
      c.appendChild(averagesBody(d));
      return finishCard(c, d);
    },
    invest: function (d) {
      var c = cardShell('Investing basics', 'Education only');
      if (d.buffer_months != null) c.appendChild(h('p', { class: 'small' }, 'Your buffer covers about ' + (Math.round(num(d.buffer_months) * 10) / 10) + ' months of spending' + (d.buffer_ok ? '.' : ', which is less than a comfortable buffer.')));
      var ul = h('ul', { class: 'list' });
      (d.points || []).forEach(function (p) { ul.appendChild(h('li', null, String(p))); });
      c.appendChild(ul);
      if (d.disclaimer) c.appendChild(h('p', { class: 'disclaimer' }, d.disclaimer));
      return finishCard(c, d);
    },
    goal: function (d) {
      var c = cardShell('Savings goal');
      c.appendChild(h('div', { class: 'big-num' }, d.months != null ? Math.ceil(num(d.months)) + ' months' : 'Not reachable yet'));
      c.appendChild(h('p', { class: 'small' }, (d.date ? 'Around ' + fmtMonth(String(d.date).slice(0, 7)) + '. ' : '') + (d.monthly != null ? 'Saving ' + money(d.monthly) + ' a month.' : '')));
      return finishCard(c, d);
    },
    transactions: function (d) {
      var c = cardShell('Transactions', num(d.count) + ' found');
      var rows = (d.rows || []).slice(0, 6);
      c.appendChild(txList({ count: d.count, total: d.total, rows: rows, truncated: (d.rows || []).length > rows.length || d.truncated }));
      var ev = evidenceLink(d.evidence && d.evidence.length ? d.evidence : null, 'Transactions');
      if (ev) c.appendChild(ev);
      return c;
    },
    table: function (d) {
      var c = cardShell('Your data');
      var cols = d.columns || [];
      var rows = d.rows || [];
      var thead = h('tr');
      cols.forEach(function (col) { thead.appendChild(h('th', { scope: 'col' }, String(col))); });
      var tbody = h('tbody');
      rows.forEach(function (r) {
        var tr = h('tr');
        cols.forEach(function (col, i) {
          var v = Array.isArray(r) ? r[i] : (r && r[col]);
          tr.appendChild(h('td', null, v == null ? '' : String(v)));
        });
        tbody.appendChild(tr);
      });
      c.appendChild(h('div', { class: 'table-wrap' }, h('table', { class: 'data' }, h('thead', null, thead), tbody)));
      if (d.truncated) c.appendChild(h('p', { class: 'tiny' }, 'Showing the first rows only.'));
      return finishCard(c, d);
    },
    afford: function (d) {
      var c = cardShell('Can I afford this?', d.item ? String(d.item) + (d.price != null ? ', ' + money(d.price) : '') : '');
      c.appendChild(affordResult(d));
      return c;
    },
    leaks: function (d) {
      var c = cardShell('Leak finder', d.period ? fmtPeriod(d.period) : '');
      c.appendChild(leaksBody(d));
      return c;
    },
    alerts: function (d) {
      var c = cardShell('Worth a look');
      var list = (d.alerts || []).slice(0, 5);
      if (!list.length) c.appendChild(h('p', { class: 'small' }, 'Nothing unusual this month.'));
      list.forEach(function (a) { c.appendChild(alertNode(a, null)); });
      var ex = explainNode(d);
      if (ex) c.appendChild(ex);
      return c;
    },
    savings_leak: function (d) {
      var c = cardShell('Your savings', d.flag === false ? 'No pattern found' : '');
      c.appendChild(savingsLeakBody(d));
      return finishCard(c, d, 'Investment withdrawals');
    },
    challenge: function (d) {
      var c = cardShell('Challenge');
      var inner = h('div');
      c.appendChild(inner);
      function fill(data) {
        inner.replaceChildren();
        var shaped = data;
        if (data && data.status && data.title && data.active === undefined) shaped = { enabled: true, active: data };
        var n = challengeNode(shaped, function () {
          api('/api/challenge').then(fill, function () {});
        });
        if (n) {
          n.classList.remove('card');
          inner.appendChild(n);
        } else {
          inner.appendChild(h('p', { class: 'small' }, (shaped && shaped.enabled === false)
            ? 'Challenges are off. If you would like an optional weekly one, you can switch them on in Settings.'
            : 'No challenge right now.'));
          if (shaped && shaped.enabled === false) inner.appendChild(h('p', { class: 'small' }, settingsLink('Open Settings')));
        }
      }
      fill(d);
      return c;
    },
    quiz_stats: function (d) {
      var c = cardShell('Your guessing');
      var n = quizStatsNode(d);
      if (n) c.appendChild(n);
      else c.appendChild(h('p', { class: 'small' }, d.text ? ht(d.text) : 'Answer a quiz question and your awareness score shows up here.'));
      return c;
    },
    forecast: function (d) {
      var c = cardShell('Until payday', d.to ? fmtDate(d.to) : '');
      c.appendChild(forecastBody(d));
      return finishCard(c, d, 'Where this comes from');
    },
    payday_plan: function (d) {
      var c = cardShell('Your payday plan', d.next_payday ? fmtDate(d.next_payday) : '');
      c.appendChild(planBody(d));
      return c;
    },
    area: function (d) {
      var c = cardShell('Your area', d.area_name || '');
      c.appendChild(areaBody(d));
      return c;
    },
    explain: function (d) { return explainCard(d); },
    purchase: function (d) { return purchaseCard(d); },
    patterns: function (d) {
      var c = cardShell('Spending patterns');
      c.appendChild(patternsBody(d));
      return c;
    },
    goal_plan: function (d) { return goalPlanCard(d); },
    override: function (d) {
      var c = cardShell('Remembered');
      var text = d.text || d.message || d.reply || 'Remembered. I will use that category from now on.';
      c.appendChild(h('p', null, ht(text)));
      var id = d.override && d.override.id != null ? d.override.id : d.id;
      var msg = h('div', { 'aria-live': 'polite' });
      if (id != null) {
        var undo = h('button', { type: 'button', class: 'btn secondary small-btn' }, 'Undo');
        undo.addEventListener('click', function () {
          undo.disabled = true;
          api('/api/overrides/remove', { method: 'POST', body: { id: id } }).then(function () {
            undo.remove();
            msg.replaceChildren(h('p', { class: 'notice ok', role: 'status' }, 'Undone. Svinkki has forgotten that.'));
          }, function (e) {
            undo.disabled = false;
            if (!e.handled) msg.replaceChildren(errorNode(e));
          });
        });
        c.appendChild(undo);
      }
      c.appendChild(msg);
      return c;
    }
  };

  var OPEN_CARDS = { help: 1, baskets: 1, forecast: 1, payday_plan: 1, receipts: 1, receipt_parsed: 1, challenge: 1,
    goal_plan: 1, override: 1, explain: 1, transactions: 1, table: 1 };

  function renderChatCard(c) {
    if (!c || typeof c !== 'object') return null;
    var fn = CARDS[c.type];
    var d = c.data || {};
    if (!fn) return null;
    if (!d.evidence && c.evidence) d = Object.assign({}, d, { evidence: c.evidence });
    return fn(d);
  }

  var TARGETS = {
    night_out: 'Night out', Restaurant: 'Restaurants', 'Fast food': 'Fast food', Bar: 'Bars', Taxi: 'Taxis', Groceries: 'Groceries',
    regular: 'Regular essentials', unexpected: 'Unexpected necessities', everyday: 'Everyday spending'
  };
  function targetName(t) { return TARGETS[t] || String(t == null ? '' : t); }

  function benchRows(c, rows) {
    rows = rows || [];
    rows.forEach(function (r) {
      var mx = Math.max(num(r.you), num(r.median), num(r.p75), 1);
      var pos = r.position;
      var posText = typeof pos === 'string' ? pos : (typeof pos === 'number' ? 'Higher than ' + Math.round(pos <= 1 ? pos * 100 : pos) + '% of the group' : '');
      var wrap = h('div', { class: 'bench' });
      wrap.appendChild(h('div', { class: 'trait' }, h('b', null, r.name || r.metric), posText ? h('span', { class: 'tiny' }, posText) : null));
      wrap.appendChild(barRow('You', num(r.you), mx, 'you'));
      wrap.appendChild(barRow('Typical', num(r.median), mx, 'median'));
      c.appendChild(wrap);
    });
    if (!rows.length) c.appendChild(h('p', { class: 'muted small' }, 'No comparison is available yet.'));
  }

  // ---------- averages ("How do I compare?") ----------
  function fmtByUnit(v, unit) {
    if (v == null || !isFinite(Number(v))) return '-';
    v = Number(v);
    var d1 = (Math.round(v * 10) / 10).toFixed(1);
    switch (unit) {
      case 'eur_per_month': return money(v) + ' / mo';
      case 'eur': return money(v);
      case 'count_per_month': return d1 + ' / mo';
      case 'count_per_year': return d1 + ' / yr';
      case 'share': return Math.round(v * 100) + '%';
      case 'months': return d1 + ' mo';
      default: return d1;
    }
  }

  function averagesBody(d) {
    var box = h('div', { class: 'avg' });
    if (d.headline) box.appendChild(h('p', { class: 'avg-headline' }, ht(d.headline)));
    var rows = d.rows || [];
    rows.forEach(function (r) {
      var mx = Math.max(num(r.you), num(r.typical), 0.0001);
      var row = h('div', { class: 'avg-row' });
      row.appendChild(h('b', { class: 'avg-name' }, r.name || r.metric || ''));
      row.appendChild(barRow('You', num(r.you), mx, 'you', fmtByUnit(r.you, r.unit)));
      row.appendChild(barRow('Typical', num(r.typical), mx, 'median', fmtByUnit(r.typical, r.unit)));
      if (r.sentence) row.appendChild(h('p', { class: 'tiny' }, ht(r.sentence)));
      box.appendChild(row);
    });
    if (!rows.length) box.appendChild(h('p', { class: 'muted small' }, 'No comparison is available yet.'));
    if (d.note) box.appendChild(h('p', { class: 'tiny' }, ht(d.note)));
    var g = d.group || {};
    if (g.description) box.appendChild(h('p', { class: 'tiny' }, ht(g.description) + (g.n ? ' (' + g.n + ' customers)' : '')));
    var ex = explainNode(d);
    if (ex) box.appendChild(ex);
    return box;
  }

  // Explore section with topic chips. Needs benchmark consent.
  function typicalSection(box, t) {
    var c = card('What is typical?');
    box.appendChild(c);
    if (!(me && me.consent && me.consent.benchmarks)) {
      c.appendChild(h('p', { class: 'small' }, 'See how your spending and habits compare with groups of at least 20 similar customers. Only group statistics are used, never other people\'s data. This needs the "Compare me with people like me" switch.'));
      c.appendChild(h('button', { type: 'button', class: 'btn secondary', onclick: function () { openSettings(); } }, 'Open Settings'));
      return;
    }
    var chipsBox = h('div', { class: 'chips chips-row', role: 'group', 'aria-label': 'Topics' });
    var body = h('div');
    c.appendChild(chipsBox);
    c.appendChild(body);
    var topicsDrawn = false;
    function draw(topic) {
      var path = '/api/averages' + (topic ? '?topic=' + encodeURIComponent(topic) : '');
      load(body, t, function () { return api(path); }, function (d) {
        if (!topicsDrawn && d.topics && d.topics.length) {
          topicsDrawn = true;
          d.topics.forEach(function (tp) {
            var b = h('button', { type: 'button', class: 'chip', 'data-topic': tp.key, 'aria-pressed': String(tp.key === d.topic) }, tp.title || tp.key);
            b.addEventListener('click', function () {
              chipsBox.querySelectorAll('.chip').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
              draw(tp.key);
            });
            chipsBox.appendChild(b);
          });
        } else {
          chipsBox.querySelectorAll('.chip').forEach(function (x) { x.setAttribute('aria-pressed', String(x.getAttribute('data-topic') === d.topic)); });
        }
        body.appendChild(averagesBody(d));
      });
    }
    draw(null);
  }

  function openDataBlock(c, od) {
    if (!od || !od.rows || !od.rows.length) return;
    var box = h('div', { class: 'open-data' });
    box.appendChild(h('p', { class: 'eyebrow' }, 'Finland on average (Statistics Finland, ' + (od.year || '') + ')'));
    if (od.note) box.appendChild(h('p', { class: 'small muted' }, od.note));
    od.rows.forEach(function (r) {
      var mx = Math.max(num(r.you), num(r.national), 1);
      var w = h('div', { class: 'bench' });
      w.appendChild(h('div', { class: 'trait' }, h('b', null, r.name), h('span', { class: 'tiny' }, 'a month')));
      w.appendChild(barRow('You', num(r.you), mx, 'you'));
      w.appendChild(barRow('Finland', num(r.national), mx, 'median'));
      box.appendChild(w);
    });
    var src = [od.source, od.unit].filter(Boolean).join('. ');
    if (src) box.appendChild(h('p', { class: 'tiny' }, 'Source: ' + src + (od.url ? ' (' + od.url + ')' : '') + '.'));
    c.appendChild(box);
  }

  // ---------- EXPLORE ----------
  var WHATIF_TARGETS = [
    ['Restaurant', 'Restaurants'], ['Fast food', 'Fast food'], ['Bar', 'Bars'], ['night_out', 'Night out'], ['Taxi', 'Taxis'],
    ['Groceries', 'Groceries'], ['Clothing', 'Clothing'], ['Hobbies', 'Hobbies'], ['Entertainment', 'Entertainment'],
    ['Shopping', 'Shopping'], ['Events', 'Events'], ['Gym & sports', 'Gym & sports']
  ];
  var FILTER_LABELS = [
    'Groceries', 'Restaurant', 'Fast food', 'Bar', 'Taxi', 'Public transport', 'Fuel', 'Parking', 'Pharmacy', 'Doctor', 'Dentist',
    'Other health', 'Home improvement', 'Electronics', 'Furniture', 'Clothing', 'Hobbies', 'Books', 'Shopping', 'Events', 'Cinema',
    'Gym & sports', 'Entertainment', 'Flights', 'Hotels', 'Travel agency', 'Car rental', 'Travel', 'Housing', 'Utilities'
  ];

  function monthOptions() {
    var today = (me && me.today) || new Date().toISOString().slice(0, 10);
    var y = Number(today.slice(0, 4)), m = Number(today.slice(5, 7));
    var list = [];
    for (var i = 0; i < 13; i++) {
      var mm = m - i, yy = y;
      while (mm < 1) { mm += 12; yy -= 1; }
      list.push(yy + '-' + (mm < 10 ? '0' + mm : mm));
    }
    return list;
  }

  // What-if sliders: pct is the percentage to REDUCE the spending by (positive number).
  function whatIfBlock(box, t) {
    var selected = [];       // [{target, pct}]
    var c = card('What if I spent less?', 'Live estimate');
    c.appendChild(h('p', { class: 'small muted' }, 'Pick up to three areas, then slide to see what a cut would save.'));
    var chipBox = h('div', { class: 'chips', role: 'group', 'aria-label': 'Areas to cut' });
    var sliders = h('div');
    var out = h('div', { 'aria-live': 'polite' });
    var timer = null, seq = 0;
    var chipBtns = {};

    WHATIF_TARGETS.forEach(function (tt) {
      var b = h('button', { type: 'button', class: 'chip', 'aria-pressed': 'false' }, tt[1]);
      b.addEventListener('click', function () {
        var idx = selected.findIndex(function (s) { return s.target === tt[0]; });
        if (idx >= 0) selected.splice(idx, 1);
        else if (selected.length < 3) selected.push({ target: tt[0], pct: 20 });
        else { out.replaceChildren(h('p', { class: 'notice' }, 'You can compare up to three areas. Tap one to remove it first.')); return; }
        paint(); schedule();
      });
      chipBtns[tt[0]] = b;
      chipBox.appendChild(b);
    });

    function paint() {
      Object.keys(chipBtns).forEach(function (k) {
        chipBtns[k].setAttribute('aria-pressed', String(selected.some(function (s) { return s.target === k; })));
      });
      sliders.replaceChildren();
      selected.forEach(function (s) {
        var id = 'wi-' + s.target.replace(/\W/g, '');
        var val = h('b', null, s.pct + '% less');
        var r = h('input', { type: 'range', class: 'range', id: id, min: '0', max: '100', step: '5' });
        r.value = String(s.pct);
        r.addEventListener('input', function () { s.pct = Number(r.value); val.textContent = s.pct + '% less'; schedule(); });
        sliders.appendChild(h('div', null, h('div', { class: 'trait' }, h('label', { for: id }, targetName(s.target)), val), r));
      });
    }

    function schedule() {
      clearTimeout(timer);
      if (!selected.length) { out.replaceChildren(); return; }
      timer = setTimeout(calc, 250);
    }

    function calc() {
      var my = ++seq;
      var body = { changes: selected.map(function (s) { return { target: s.target, pct: s.pct }; }), months: 12 };
      out.replaceChildren(loadingNode('Calculating...'));
      api('/api/what-if', { method: 'POST', body: body }).then(function (d) {
        if (!alive(t) || my !== seq) return;
        out.replaceChildren();
        out.appendChild(h('div', { class: 'stats' },
          stat(money(d.saved_monthly), 'Saved per month'), stat(money(d.saved_total), 'Saved in ' + num(d.months || 12) + ' months')));
        out.appendChild(h('p', { class: 'small' }, 'Before: ' + money(d.baseline_monthly) + ' a month. After: ' + money(d.new_monthly) + ' a month.'));
        (d.lines || []).forEach(function (l) {
          out.appendChild(h('div', { class: 'trait' }, h('span', null, targetName(l.target)), h('b', null, money(l.baseline) + ' to ' + money(l.new))));
        });
        var ex = explainNode(d); if (ex) out.appendChild(ex);
        var ev = evidenceLink(d.evidence, 'What this is based on');
        if (ev) out.appendChild(ev);
      }, function (e) {
        if (!alive(t) || my !== seq || e.handled) return;
        out.replaceChildren(errorNode(e, calc));
      });
    }

    c.appendChild(chipBox); c.appendChild(sliders); c.appendChild(out);
    box.appendChild(c);
  }

  // ---------- SETTINGS: goal and learned categories ----------
  function goalBlock(box, t, flash, done) {
    api('/api/goal').then(function (res) {
      if (!alive(t)) return;
      var g = (res && res.goal) || null;
      if (!g) return;
      var c = h('section', { class: 'card' }, h('h2', null, 'Your savings goal'),
        h('p', { class: 'small muted' }, 'Used to say what a purchase does to your goal. Nothing is moved automatically.'));
      var name = h('input', { type: 'text', class: 'input', id: 'goal-name', maxlength: '40', placeholder: 'A flat', autocomplete: 'off' });
      var target = h('input', { type: 'number', class: 'input', id: 'goal-target', min: '0', step: '100', inputmode: 'decimal' });
      var saved = h('input', { type: 'number', class: 'input', id: 'goal-saved', min: '0', step: '100', inputmode: 'decimal' });
      if (g) { name.value = g.name || ''; target.value = String(num(g.target)); saved.value = String(num(g.saved)); }
      var save = h('button', { type: 'button', class: 'btn' }, 'Save');
      var clear = h('button', { type: 'button', class: 'btn secondary' }, 'Clear');
      function after(r, text) {
        var ng = (r && r.goal) || null;
        if (!ng) box.replaceChildren();
        flash(text);
      }
      save.addEventListener('click', function () {
        var tg = Number(target.value), sv = Number(saved.value || 0);
        if (!name.value.trim()) { flash('Give your goal a name.', true); return; }
        if (!isFinite(tg) || tg <= 0) { flash('Enter a target above zero.', true); return; }
        if (!isFinite(sv) || sv < 0) { flash('Saved so far must be zero or more.', true); return; }
        flash('Saving...');
        api('/api/goal', { method: 'POST', body: { name: name.value.trim(), target: tg, saved: sv } }).then(function (r) { after(r, 'Saved. Your goal is updated.'); },
          function (e) { if (!e.handled) flash(e.message, true); });
      });
      clear.addEventListener('click', function () {
        api('/api/goal', { method: 'POST', body: { clear: true } }).then(function (r) { after(r, 'Goal cleared. Tell me in the chat when you have a new one.'); },
          function (e) { if (!e.handled) flash(e.message, true); });
      });
      c.appendChild(h('div', { class: 'form-grid' },
        h('div', { class: 'wide' }, h('label', { for: 'goal-name' }, 'Name'), name),
        h('div', null, h('label', { for: 'goal-target' }, 'Target (euros)'), target),
        h('div', null, h('label', { for: 'goal-saved' }, 'Saved so far (euros)'), saved)));
      c.appendChild(h('div', { class: 'btn-row' }, save, clear));
      box.appendChild(c);
      if (done) done();
    }, function () {});
  }

  function overrideText(o) {
    var what = o.description ? String(o.description)
      : (o.scope === 'merchant' ? 'Every purchase from one merchant' : 'One purchase');
    var to = (o.label || 'Other') + (o.context === 'night_out' ? ', part of a night out' : '');
    return what + ' is now ' + to + (o.created ? ' (' + fmtDate(o.created) + ')' : '') + '.';
  }

  function learnedBlock(box, t, done) {
    function draw() {
      api('/api/overrides').then(function (res) {
        if (!alive(t)) return;
        var list = (res && res.overrides) || [];
        var c = h('section', { class: 'card' }, h('h2', null, 'What Svinkki has learned'));
        var msg = h('div', { 'aria-live': 'polite' });
        if (!list.length) { box.replaceChildren(); if (done) done(); return; }
        {
          var ul = h('ul', { class: 'list' });
          list.forEach(function (o) {
            var rm = h('button', { type: 'button', class: 'btn secondary small-btn', 'aria-label': 'Remove: ' + overrideText(o) }, 'Remove');
            rm.addEventListener('click', function () {
              rm.disabled = true;
              api('/api/overrides/remove', { method: 'POST', body: { id: o.id } }).then(draw, function (e) {
                rm.disabled = false;
                if (!e.handled) msg.replaceChildren(errorNode(e));
              });
            });
            ul.appendChild(h('li', { class: 'learned' }, h('span', { class: 'small' }, overrideText(o)), rm));
          });
          c.appendChild(ul);
        }
        c.appendChild(msg);
        box.replaceChildren(c);
        if (done) done();
      }, function () {});
    }
    draw();
  }

  // ---------- SETTINGS ----------
  // ---------- AI model (demo setup) ----------
  // For the person running the demo: choose the Claude model and replace the key. The server never
  // sends the key back; it only says that one is saved and what its last four characters are.
  function aiSetupBlock(box, t, done) {
    var body = h('div', { class: 'ai-setup' });
    box.appendChild(h('section', { class: 'card' }, h('h2', null, 'AI model (demo setup)'),
      h('p', { class: 'small muted' }, 'For the person running the demo. Customers never see this in a real bank app.'), body));

    function setupError(e) {
      if (e && e.code === 'invalid_key') return 'That does not look like a Claude API key. It starts with "sk-ant-".';
      if (e && e.code === 'local_only') return 'The AI setup can only be changed on the computer that runs Svinkki.';
      return (e && e.message) || 'Something went wrong. Please try again.';
    }

    function draw(st, note) {
      body.replaceChildren();
      var connected = st.provider === 'claude';
      body.appendChild(h('p', { class: 'notice' + (connected ? ' ok' : '') },
        connected ? 'Claude is set up to answer the chat.'
          : st.provider === 'gemini' ? 'A Gemini key is in use. Save a Claude key to switch to Claude.'
            : 'No AI model is connected. Answers come from the built-in rules.'));
      var keyLine = st.key_set
        ? 'A Claude key is saved' + (st.key_last4 ? ' (ends in ' + st.key_last4 + ').' : '.')
        : 'No Claude key is saved.';
      if (st.key_source === 'environment') keyLine += ' It comes from the environment, so a key saved here is not used until that one is removed.';
      body.appendChild(h('p', { class: 'small' }, keyLine));
      if (!st.editable) {
        body.appendChild(h('p', { class: 'help' }, 'Open Svinkki at http://localhost on the computer that runs it to change the key or the model.'));
        return;
      }

      var sel = h('select', { class: 'input', id: 'ai-model' });
      (st.models || []).forEach(function (m) {
        var o = h('option', { value: m.id }, m.label);
        if (m.id === st.model) o.selected = true;
        sel.appendChild(o);
      });
      var key = h('input', { type: 'password', class: 'input', id: 'ai-key', autocomplete: 'off', spellcheck: 'false',
        placeholder: st.key_set ? 'Leave empty to keep the saved key' : 'sk-ant-...' });
      var msg = h('p', { class: 'help', role: 'status', 'aria-live': 'polite' }, note || '');
      var save = h('button', { type: 'button', class: 'btn' }, 'Save');
      var test = h('button', { type: 'button', class: 'btn secondary' }, 'Test the key');
      test.disabled = !st.key_set;

      function busy(on) { save.disabled = on; test.disabled = on || !st.key_set; }
      save.addEventListener('click', function () {
        var req = { model: sel.value };
        var k = key.value.trim();
        if (k) req.key = k;
        busy(true); msg.className = 'help'; msg.textContent = 'Saving...';
        api('/api/demo/ai', { method: 'POST', body: req }).then(function (now) {
          if (!alive(t)) return;
          if (me) me.ai_available = now.provider !== 'offline';
          if (chat) chat.setAiHint();   // the conversation shows whether a model is connected
          draw(now, k ? 'Saved. Use "Test the key" to check that it works.' : 'Saved.');
        }, function (e) {
          if (!alive(t) || (e && e.handled)) return;
          busy(false); msg.className = 'help err-text'; msg.textContent = setupError(e);
        });
      });
      test.addEventListener('click', function () {
        busy(true); msg.className = 'help'; msg.textContent = 'Asking Claude...';
        api('/api/demo/ai/test', { method: 'POST', body: {} }).then(function (r) {
          if (!alive(t)) return;
          busy(false);
          msg.className = 'help' + (r && r.ok ? '' : ' err-text');
          msg.textContent = r && r.ok ? 'Claude answered. The key works.' : 'Claude did not answer: ' + ((r && r.error) || 'unknown error') + '.';
        }, function (e) {
          if (!alive(t) || (e && e.handled)) return;
          busy(false); msg.className = 'help err-text'; msg.textContent = setupError(e);
        });
      });

      body.appendChild(h('div', null, h('label', { for: 'ai-model', class: 'field-label' }, 'Model'), sel,
        h('p', { class: 'help' }, 'Opus gives the best answers. Haiku is the cheapest and the fastest.')));
      body.appendChild(h('div', null, h('label', { for: 'ai-key', class: 'field-label' }, st.key_set ? 'Replace the key' : 'Claude API key'), key,
        h('p', { class: 'help' }, 'Saved in a file on this computer that is not shared. It is never shown again and never sent to the browser.')));
      body.appendChild(h('div', { class: 'btn-row' }, save, test));
      body.appendChild(msg);
    }

    load(body, t, function () { return api('/api/demo/ai'); }, function (st) { draw(st || {}); if (done) done(); });
  }

  // ---------- THE CONVERSATION ----------
  var STARTERS = [
    { label: 'Taxis last month', q: 'How much did I spend on taxis last month?' },
    { label: 'Can I afford a €300 jacket?', q: 'Can I afford a 300 euro jacket?' },
    { label: 'Save for a trip to Japan', q: 'I want to go to Japan in 2027' },
    { label: 'What do I buy most?', q: 'What do I buy most?' }
  ];

  // "What can I ask?" content. q: sent to the chat. act: something Svinkki does instead.
  var ASK_GROUPS = [
    { title: 'My spending', items: [
      { q: 'How much did I spend on taxis last month?' },
      { q: 'How much did I spend at bars last night?' },
      { q: 'Where did my money go?' },
      { q: 'Show my three baskets for last month' },
      { label: 'Browse my transactions', act: 'browse' }
    ] },
    { title: 'Can I afford it?', items: [
      { q: 'What is safe for me to spend this week?' },
      { q: 'Can I afford a 300 euro jacket?' },
      { q: 'Will I make it to payday?' },
      { q: 'How should I split my next salary?' }
    ] },
    { title: 'Save and plan', items: [
      { q: 'How can I save more?' },
      { q: 'How much could I save if I reduced dining out by 20%?' },
      { q: 'I want to go to Japan in 2027' },
      { q: 'What kind of mortgage can I get approved for?' },
      { q: 'What should I invest in?' }
    ] },
    { title: 'Am I normal?', items: [
      { q: 'What kind of spender am I?' },
      { q: 'Is my taxi spending normal?' },
      { q: 'How do I compare with people my age?' },
      { q: 'What is my area like?' }
    ] },
    { title: 'Leaks and habits', items: [
      { q: 'Where is my money leaking?' },
      { q: 'Anything unusual this month?' },
      { q: 'Any spending patterns?' },
      { q: 'Give me a challenge' }
    ] },
    { title: 'My receipts', items: [
      { q: 'What do I buy most?' },
      { q: 'How much do I spend on energy drinks?' },
      { q: 'Show my receipts' },
      { label: 'Read a receipt I paste', act: 'receipt' }
    ] },
    { title: 'More', items: [
      { label: 'This week\'s quiz', act: 'quiz' },
      { label: 'My check-in', act: 'checkin' },
      { label: 'Explain a loan or fund text', act: 'explain' }
    ] }
  ];

  var HELP_PHRASES = ['help', 'what can i ask', 'what can you do', 'apua', 'mitä voin kysyä', 'mita voin kysya'];
  function isHelpRequest(text) {
    var s = String(text || '').toLowerCase().replace(/[?!.\s]+$/, '').replace(/\s+/g, ' ').trim();
    return HELP_PHRASES.indexOf(s) >= 0;
  }

  function offCard(text) {
    var c = cardShell('Svinkki');
    c.appendChild(h('p', null, text));
    c.appendChild(settingsLink('Open Settings'));
    return c;
  }

  // Fill a thread card from one endpoint. 404 means the feature is off.
  function fillCard(holder, t, fetcher, render, loadingText, offText) {
    holder.replaceChildren(loadingNode(loadingText));
    fetcher().then(function (d) {
      if (!alive(t)) return;
      holder.replaceChildren();
      render(d);
    }, function (e) {
      if (!alive(t) || (e && e.handled)) return;
      holder.replaceChildren();
      if (e && e.status === 404 && offText) holder.appendChild(offCard(offText));
      else holder.appendChild(errorNode(e));
    });
  }

  function affordCard() {
    var c = card('Can I afford this?');
    var out = h('div', { 'aria-live': 'polite' });
    c.appendChild(h('p', { class: 'small muted' }, 'Check a purchase against what is safe to spend until payday.'));
    c.appendChild(affordForm(out));
    c.appendChild(out);
    return c;
  }

  function showApp() {
    mode = 'app';
    clearView();
    setChrome(true, '');
    chat = buildChat();
    viewEl.appendChild(chat.el);
    chat.start();
  }

  function buildChat() {
    var t = token;
    var msgs = h('div', { class: 'msgs', role: 'log', 'aria-live': 'polite', 'aria-label': 'Conversation' });
    var input = h('textarea', { class: 'input chat-text', rows: '1', maxlength: '2000', placeholder: 'Ask Svinkki', 'aria-label': 'Your question', autocomplete: 'off', enterkeyhint: 'send' });
    var sendBtn = h('button', { type: 'submit', class: 'btn' }, 'Send');
    var form = h('form', { class: 'chat-input' }, input, sendBtn);
    var hint = h('p', { class: 'chat-hint' }, 'AI model not connected: answers come from built-in rules. Numbers are the same either way.');
    var busy = false;
    var shown = {};    // key -> thread message already holding that card

    function bubble(who, node) {
      var m = h('div', { class: 'msg ' + who }, h('div', { class: 'bubble' }, node));
      msgs.appendChild(m);
      return m;
    }
    function toBottom() { msgs.scrollTop = msgs.scrollHeight; }
    // Show the START of a message, not the end of a long card.
    function toStartOf(el) { msgs.scrollTop = Math.max(0, el.offsetTop - 8); }
    function autosize() {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 120) + 'px';
      input.classList.toggle('tall', input.scrollHeight > 120);
    }
    function setAiHint() { hint.hidden = !(me && me.ai_available === false); }

    function send(text) {
      text = String(text || '').trim();
      if (!text || busy) return;
      if (isHelpRequest(text)) { input.value = ''; autosize(); openAsk(); return; }
      busy = true; sendBtn.disabled = true;
      bubble('user', h('p', null, text));
      input.value = '';
      autosize();
      input.focus({ preventScroll: true });
      var wait = h('div', { class: 'msg bot' }, h('div', { class: 'bubble' }, h('span', { class: 'typing', role: 'status', 'aria-label': 'Svinkki is thinking' }, h('i'), h('i'), h('i'))));
      msgs.appendChild(wait);
      toBottom();
      api('/api/chat', { method: 'POST', body: { message: text } }).then(function (res) {
        wait.remove();
        toStartOf(botReply(res || {}));
      }, function (e) {
        wait.remove();
        if (e.handled) return;
        var m = h('div', { class: 'msg bot' }, h('div', { class: 'bubble' }, errorNode(e)));
        msgs.appendChild(m);
        toStartOf(m);
      }).then(function () { busy = false; sendBtn.disabled = false; input.focus({ preventScroll: true }); });
    }

    // Entries from "What can I ask?": send now, or put the question in the box while an answer is pending.
    function ask(q) {
      if (busy) { input.value = q; autosize(); input.focus(); return; }
      send(q);
    }

    // An answer is one short bubble. The card and the transactions sit behind two small buttons.
    function botReply(res) {
      var inner = h('div');
      inner.appendChild(richText(res.reply));
      var m = bubble('bot', inner);
      var acts = h('div', { class: 'reply-acts' });
      var nodes = [], openNow = false;
      (res.cards || []).forEach(function (c) {
        var node = null;
        try { node = renderChatCard(c); } catch (e) { node = null; }
        if (node) { nodes.push(node); if (OPEN_CARDS[c.type]) openNow = true; }
      });
      var used = null;
      try { used = usedParts(res.used); } catch (e) { used = null; }
      var wrap = null;
      if (nodes.length) {
        wrap = h('div', { class: 'msg-cards' + (used ? ' has-used' : ''), id: 'det-' + Math.random().toString(36).slice(2, 8) });
        nodes.forEach(function (n) { wrap.appendChild(n); });
        wrap.hidden = !openNow;
        var det = h('button', { type: 'button', class: 'act-btn', 'aria-expanded': String(openNow), 'aria-controls': wrap.id }, openNow ? 'Hide details' : 'Details');
        det.addEventListener('click', function () {
          var open = wrap.hidden;
          wrap.hidden = !open;
          det.setAttribute('aria-expanded', String(open));
          det.textContent = open ? 'Hide details' : 'Details';
          m.classList.toggle('has-cards', open || (used && !used.body.hidden));
        });
        acts.appendChild(det);
        if (openNow) m.classList.add('has-cards');
      }
      if (used) {
        acts.appendChild(used.btn);
        used.btn.addEventListener('click', function () {
          m.classList.toggle('has-cards', !used.body.hidden || (wrap && !wrap.hidden));
        });
      }
      var ai = isAiMode(res.mode);
      acts.appendChild(h('span', { class: 'mode-tag', title: ai ? 'Worded by the AI model. The figures come from the app.' : 'Answered by built-in rules, without an AI model.' }, ai ? 'AI' : 'Rules'));
      m.appendChild(acts);
      if (res.notice) m.appendChild(h('p', { class: 'tiny reply-note' }, ht(String(res.notice))));
      if (wrap) m.appendChild(wrap);
      if (used) m.appendChild(used.body);
      return m;
    }

    // A card the coach "sends" on request. key: one copy per card; asking again scrolls back to it.
    function insertCard(key, build) {
      var old = shown[key];
      if (old && document.contains(old)) { toStartOf(old); return old; }
      var holder = h('div', { class: 'msg-cards' });
      var m = h('div', { class: 'msg bot has-cards' }, h('div', { class: 'attrib' }, 'Svinkki'), holder);
      msgs.appendChild(m);
      build(holder);
      toStartOf(m);
      shown[key] = m;
      return m;
    }

    function insert(name, pre) {
      function src(path) { return pre ? function () { return Promise.resolve(pre); } : function () { return api(path); }; }
      if (name === 'afford') return insertCard('afford', function (hd) { hd.appendChild(affordCard()); });
      if (name === 'whatif') return insertCard('whatif', function (hd) { whatIfBlock(hd, t); });
      if (name === 'typical') return insertCard('typical', function (hd) { typicalSection(hd, t); });
      if (name === 'quiz') {
        return insertCard('quiz', function (hd) {
          fillCard(hd, t, src('/api/quiz'), function (q) { hd.appendChild(quizCard(q)); },
            'Finding this week\'s question...', 'The weekly quiz is switched off. You can turn it back on in Settings.');
        });
      }
      if (name === 'checkin') {
        return insertCard('checkin', function (hd) {
          fillCard(hd, t, src('/api/checkin'), function (r) {
            if (r && r.due && r.checkin) hd.appendChild(checkinCard(r.checkin));
            else hd.appendChild(offCard('Check-ins are switched off. You can choose how often you want one in Settings.'));
          }, 'Preparing your check-in...');
        });
      }
      if (name === 'challenge') {
        return insertCard('challenge', function (hd) {
          fillCard(hd, t, src('/api/challenge'), function (d) { hd.appendChild(CARDS.challenge(d || {})); }, 'Loading...');
        });
      }
      if (name === 'alerts') {
        return insertCard('alerts', function (hd) { hd.appendChild(CARDS.alerts(pre || {})); });
      }
      return null;
    }

    function openExplain() {
      openExplainSheet(function (text, data) {
        var shownText = text.length > 200 ? text.slice(0, 200) + '...' : text;
        bubble('user', h('p', null, 'Explain this text: ' + shownText));
        var m = bubble('bot', h('div', null, h('p', null, 'Here is that text in plain words.'),
          h('div', { class: 'msg-cards' }, explainCard(data))));
        toStartOf(m);
      });
    }

    // ---- the Today card and the quiet "ready when you are" line ----
    function todayNode() {
      var box = h('button', { type: 'button', class: 'today-mini', hidden: true });
      api('/api/safe-to-spend').then(function (d) {
        if (!alive(t) || !d) return;
        var short = num(d.safe_total) < 0 || num(d.per_day) < 0;
        box.appendChild(h('span', { class: 'tm-label' }, 'Safe to spend'));
        box.appendChild(h('span', { class: 'tm-num' }, short ? '€0' : money(d.per_day, { hero: true })));
        box.appendChild(h('span', { class: 'tm-sub' }, short ? 'You are short until payday. Tap to see why.'
          : 'a day, ' + money(d.per_week, { hero: true }) + ' this week. Tap to see why.'));
        box.hidden = false;
      }, function () {});
      box.addEventListener('click', function () { ask('What is safe for me to spend this week?'); });
      return box;
    }

    function readyNode() {
      var row = h('div', { class: 'ready-row', role: 'group', 'aria-label': 'Ready when you are' });
      var slots = {};
      function slot(key, text, onTap) {
        var b = h('button', { type: 'button', class: 'ready-btn', hidden: true }, text);
        b.addEventListener('click', onTap);
        slots[key] = b;
        row.appendChild(b);
      }
      var data = {};
      slot('checkin', 'Your check-in is ready', function () { insert('checkin', data.checkin); });
      slot('quiz', 'This week\'s quiz', function () { insert('quiz', data.quiz); });
      slot('challenge', 'Your challenge', function () { insert('challenge', data.challenge); });
      var alertsBtn = h('button', { type: 'button', class: 'ready-btn alerts-line', hidden: true }, '');
      var wrap = h('div', { class: 'ready' }, row, alertsBtn);

      api('/api/checkin').then(function (r) {
        if (!alive(t) || !r || !r.due || !r.checkin) return;
        data.checkin = r; slots.checkin.hidden = false;
      }, function () {});
      api('/api/quiz').then(function (q) {
        if (!alive(t) || !q || !q.quiz_id) return;
        data.quiz = q; slots.quiz.hidden = false;
      }, function () {});
      api('/api/challenge').then(function (d) {
        if (!alive(t) || !d || !d.active) return;
        data.challenge = d; slots.challenge.hidden = false;
      }, function () {});
      api('/api/alerts').then(function (d) {
        var list = (d && Array.isArray(d.alerts)) ? d.alerts : [];
        if (!alive(t) || !list.length) return;
        alertsBtn.textContent = list.length === 1 ? '1 thing worth a look' : list.length + ' things worth a look';
        alertsBtn.hidden = false;
        alertsBtn.addEventListener('click', function () { insert('alerts', { alerts: list, explain: d.explain }); });
      }, function () {});
      return wrap;
    }

    function start() {
      var first = me && me.name ? String(me.name).split(',')[0] : '';
      bubble('bot', h('div', null,
        h('p', null, 'Hi' + (first ? ' ' + first : '') + '! I am Svinkki, your money coach. Ask me anything about your money.'),
        h('p', null, 'You can also tell me things and I will remember them: a savings goal ("I am saving for Japan in 2027") or a correction ("that kebab was lunch"). What you set up can be changed later behind the gear.')));
      var starters = h('div', { class: 'chips starters', role: 'group', 'aria-label': 'Things to try' });
      STARTERS.forEach(function (st) {
        starters.appendChild(h('button', { type: 'button', class: 'chip', onclick: function () { ask(st.q); } }, st.label));
      });
      starters.appendChild(h('button', { type: 'button', class: 'chip more', 'aria-haspopup': 'dialog', onclick: function () { openAsk(); } }, 'More ideas'));
      msgs.appendChild(h('div', { class: 'msg bot wide' }, todayNode(), starters, readyNode()));
      msgs.scrollTop = 0;
    }

    form.addEventListener('submit', function (e) { e.preventDefault(); send(input.value); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(input.value); }
    });
    input.addEventListener('input', autosize);
    setAiHint();

    var el = h('div', { class: 'chat' }, h('h1', { class: 'sr-only' }, 'Svinkki conversation'), hint, msgs, h('div', { class: 'chat-foot' }, form));
    return { el: el, start: start, send: send, ask: ask, insert: insert, openExplain: openExplain, setAiHint: setAiHint };
  }

  // ---------- "What can I ask?" ----------
  function runAsk(entry) {
    if (!chat) return;
    if (entry.q) { chat.ask(entry.q); return; }
    var a = entry.act;
    if (a === 'browse') openBrowse();
    else if (a === 'explain') chat.openExplain();
    else if (a === 'receipt') openReceiptSheet();
    else if (a.indexOf('set:') === 0) openSettings(a.slice(4));
    else chat.insert(a);
  }

  function openAsk() {
    var body = openSheet('What can I ask?', { full: true });
    body.appendChild(h('p', { class: 'muted' }, 'Pick a topic and tap a question. Or just type your own.'));
    var all = [];
    ASK_GROUPS.forEach(function (g, gi) {
      var det = h('details', { class: 'ask-topic' });
      if (gi === 0) det.open = true;
      det.appendChild(h('summary', null, g.title));
      var list = h('div', { class: 'ask-list' });
      g.items.forEach(function (it) {
        var b = h('button', { type: 'button', class: 'ask-entry' }, it.label || it.q);
        b.addEventListener('click', function () { closeSheet(); runAsk(it); });
        list.appendChild(b);
      });
      det.appendChild(list);
      det.addEventListener('toggle', function () {
        if (!det.open) return;
        all.forEach(function (o) { if (o !== det) o.open = false; });
      });
      all.push(det);
      body.appendChild(det);
    });
  }

  // ---------- transactions browser ----------
  var BROWSE_BASKETS = [
    { value: '', label: 'All' },
    { value: 'regular', label: 'Regular essentials' },
    { value: 'unexpected', label: 'Unexpected necessities' },
    { value: 'everyday', label: 'Everyday spending' }
  ];

  function chipRow(label, options, value, onPick) {
    var row = h('div', { class: 'chips', role: 'group', 'aria-label': label });
    var btns = options.map(function (o) {
      var b = h('button', { type: 'button', class: 'chip', 'aria-pressed': String(o.value === value) }, o.label);
      if (o.aria) b.setAttribute('aria-label', o.aria);
      b.addEventListener('click', function () {
        btns.forEach(function (x, i) { x.setAttribute('aria-pressed', String(options[i].value === o.value)); });
        onPick(o.value);
      });
      row.appendChild(b);
      return b;
    });
    return row;
  }

  function openBrowse() {
    var body = openSheet('Browse my transactions', { full: true });
    var t = token;
    var months = monthOptions().slice(0, 6);
    var f = { month: months[1] || months[0], basket: '', label: '', night: false, q: '' };
    var monthOpts = months.map(function (m, i) {
      var parts = m.split('-');
      return { value: m, label: MON[Number(parts[1]) - 1] + ' ' + parts[0], aria: fmtMonth(m) + (i === 0 ? ', so far' : '') };
    });
    monthOpts.push({ value: '', label: 'All' });

    var results = h('div', { 'aria-live': 'polite' });
    var seq = 0, note = '', timer = null;

    function run() {
      var my = ++seq;
      var flt = {};
      if (f.month) { flt.from = f.month + '-01'; flt.to = lastDayOfMonth(f.month); }
      if (f.basket) flt.basket = f.basket;
      if (f.label) flt.label = f.label;
      if (f.night) flt.context = 'night_out';
      if (f.q) flt.q = f.q;
      results.replaceChildren(loadingNode('Searching...'));
      api('/api/transactions?' + filterQuery(flt, 100)).then(function (res) {
        if (!alive(t) || my !== seq) return;
        var n = note; note = '';
        results.replaceChildren(txList(res, { note: n, reload: function (msg) { note = msg; run(); } }));
      }, function (e) {
        if (!alive(t) || my !== seq || e.handled) return;
        results.replaceChildren(errorNode(e, run));
      });
    }

    var q = h('input', { type: 'search', class: 'input', id: 'br-q', placeholder: 'Merchant or word', autocomplete: 'off' });
    q.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(function () { f.q = q.value.trim(); run(); }, 350); });
    var sel = h('select', { class: 'input', id: 'br-label' }, h('option', { value: '' }, 'All categories'));
    function fillLabels(list) {
      list.forEach(function (l) { sel.appendChild(h('option', { value: l }, l)); });
      sel.value = f.label;
    }
    loadLabels().then(fillLabels, function () { fillLabels(FILTER_LABELS); });
    sel.addEventListener('change', function () { f.label = sel.value; run(); });
    var night = switchRow('br-night', 'Nights out only', 'Only purchases that were part of a night out.', false, function (v) { f.night = v; run(); });

    body.appendChild(h('div', { class: 'browse-filters' },
      h('div', null, h('span', { class: 'field-label' }, 'Month'), chipRow('Month', monthOpts, f.month, function (v) { f.month = v; run(); })),
      h('div', null, h('span', { class: 'field-label' }, 'Basket'), chipRow('Basket', BROWSE_BASKETS, '', function (v) { f.basket = v; run(); })),
      h('div', null, h('label', { for: 'br-label', class: 'field-label' }, 'Category'), sel),
      night.el,
      h('div', null, h('label', { for: 'br-q', class: 'field-label' }, 'Search'), q)));
    body.appendChild(results);
    run();
  }

  // ---------- SETTINGS (a full-height sheet) ----------
  function openSettings(anchor) {
    var root = openSheet('Settings', { full: true });
    var t = token;
    var settleUntil = Date.now() + 2500;
    function toAnchor() {
      if (!anchor || Date.now() > settleUntil) return;
      var el = document.getElementById(anchor);
      if (el) el.scrollIntoView({ block: 'start' });
    }
    var saved = h('p', { class: 'saved', role: 'status', 'aria-live': 'polite' });
    root.appendChild(saved);
    var consent = (me && me.consent) || {};
    var settings = (me && me.settings) || {};
    var timer = null;
    function flash(text, isErr) {
      saved.textContent = text || '';
      saved.className = 'saved' + (isErr ? ' notice err' : '');
      clearTimeout(timer);
      if (!isErr) timer = setTimeout(function () { saved.textContent = ''; }, 3500);
    }
    function sec(id, title, open) {
      var d = h('details', { class: 'set-sec anchor', id: id });
      if (open || anchor === id) d.open = true;
      var b = h('div', { class: 'set-body' });
      d.appendChild(h('summary', null, title));
      d.appendChild(b);
      root.appendChild(d);
      return b;
    }

    // What the customer has set up in the conversation comes first, and only when it exists.
    var goalBox = h('div', { class: 'anchor', id: 'set-goal' });
    var learnBox = h('div', { class: 'anchor', id: 'set-learned' });
    root.appendChild(goalBox); root.appendChild(learnBox);
    goalBlock(goalBox, t, flash, toAnchor);
    learnedBlock(learnBox, t, toAnchor);

    var pc = prefControls(settings, function (s) { saveSettings(s); });
    function saveSettings(s) {
      flash('Saving...');
      api('/api/settings', { method: 'POST', body: s }).then(function (r) {
        me.settings = (r && r.settings) || s;
        flash('Saved.');
      }, function (e) { if (!e.handled) flash(e.message, true); });
    }
    sec('set-checkin', 'How often I check in', !anchor).appendChild(pc.el);

    if (num(settings.monthly_saving_target) > 0) {
      var target = h('input', { type: 'number', class: 'input', id: 'save-target', min: '0', step: '10', inputmode: 'decimal' });
      target.value = String(num(settings.monthly_saving_target));
      var tBtn = h('button', { type: 'button', class: 'btn' }, 'Save');
      tBtn.addEventListener('click', function () {
        var v = Number(target.value);
        if (!isFinite(v) || v < 0) { flash('Enter a savings target of zero or more.', true); return; }
        pc.setTarget(v);
        saveSettings(pc.get());
      });
      var tb = sec('set-target', 'Monthly saving target');
      tb.appendChild(h('p', { class: 'small muted' }, 'Set aside first when I work out what is safe to spend. Nothing is moved automatically.'));
      tb.appendChild(h('label', { for: 'save-target', class: 'field-label' }, 'Euros per month'));
      tb.appendChild(h('div', { class: 'btn-row' }, target, tBtn));
    }

    var cc = consentControls(consent, function (key, st) {
      flash('Saving...');
      api('/api/consent', { method: 'POST', body: st }).then(function (r) {
        me.consent = (r && r.consent) || st;
        if (!me.consent.analysis) { showConsent(); return; }
        flash('Saved.');
      }, function (e) { if (!e.handled) flash(e.message, true); });
    });
    sec('set-consent', 'What Svinkki may do').appendChild(cc.el);

    var payloadBox = h('div');
    var showBtn = h('button', { type: 'button', class: 'btn secondary' }, 'Show what the AI saw');
    showBtn.addEventListener('click', function () {
      load(payloadBox, t, function () { return api('/api/privacy/ai-payload'); }, function (p) {
        if (p == null || (typeof p === 'object' && !Object.keys(p).length)) {
          payloadBox.appendChild(h('p', { class: 'notice ok' }, 'Nothing has been sent to an AI model in this session.'));
        } else {
          payloadBox.appendChild(h('pre', { class: 'payload', tabindex: '0', 'aria-label': 'Data sent to the AI model' }, JSON.stringify(p, null, 2)));
        }
      });
    });
    var aiSaw = sec('set-ai-saw', 'What the AI saw');
    aiSaw.appendChild(h('p', { class: 'small muted' }, 'Exactly what was last sent to the AI model, with no names or account details.'));
    aiSaw.appendChild(showBtn);
    aiSaw.appendChild(payloadBox);

    aiSetupBlock(sec('set-ai-setup', 'AI model (demo setup)'), t, toAnchor);

    var eraseBox = h('div');
    var eraseBtn = h('button', { type: 'button', class: 'btn danger block' }, 'Erase my data');
    eraseBtn.addEventListener('click', function () {
      eraseBtn.hidden = true;
      var yes = h('button', { type: 'button', class: 'btn danger solid' }, 'Yes, erase everything');
      var no = h('button', { type: 'button', class: 'btn secondary' }, 'Cancel');
      var msg = h('div');
      eraseBox.replaceChildren(h('p', { class: 'notice' }, 'This deletes your choices, goal, quiz answers and everything else Svinkki has stored about you. It cannot be undone. Your bank transactions are not touched.'),
        h('div', { class: 'btn-row' }, yes, no), msg);
      no.addEventListener('click', function () { eraseBox.replaceChildren(); eraseBtn.hidden = false; eraseBtn.focus(); });
      yes.addEventListener('click', function () {
        yes.disabled = true;
        api('/api/privacy/erase', { method: 'POST', body: {} }).then(function () {
          boot();
        }, function (e) { yes.disabled = false; if (!e.handled) msg.replaceChildren(errorNode(e)); });
      });
    });
    var dataBox = sec('set-data', 'Your data');
    dataBox.appendChild(h('ul', { class: 'store-list' },
      h('li', null, 'Your transactions stay in the bank data. Svinkki only reads your own rows.'),
      h('li', null, 'Your choices, goal and quiz answers are saved so the app can use them.'),
      h('li', null, 'Chat messages are not stored.')));
    dataBox.appendChild(eraseBtn);
    dataBox.appendChild(eraseBox);

    // Demo: back to the very beginning
    var resetBox = h('div');
    var resetBtn = h('button', { type: 'button', class: 'btn secondary block' }, 'Reset demo');
    resetBtn.addEventListener('click', function () {
      resetBtn.hidden = true;
      var yes = h('button', { type: 'button', class: 'btn danger solid' }, 'Yes, start over');
      var no = h('button', { type: 'button', class: 'btn secondary' }, 'Cancel');
      var msg = h('div');
      resetBox.replaceChildren(h('p', { class: 'notice' }, 'This takes the demo back to the very beginning. Every demo customer\'s choices, goals, learned categories, quiz answers and challenges are forgotten, and you are logged out. The AI key and model are kept.'),
        h('div', { class: 'btn-row' }, yes, no), msg);
      no.addEventListener('click', function () { resetBox.replaceChildren(); resetBtn.hidden = false; resetBtn.focus(); });
      yes.addEventListener('click', function () {
        yes.disabled = true;
        api('/api/demo/reset', { method: 'POST', body: {} }).then(function () {
          me = null; closeSheet(); showLogin();
        }, function (e) { yes.disabled = false; if (!e.handled) msg.replaceChildren(errorNode(e)); });
      });
    });
    var logout = h('button', { type: 'button', class: 'btn secondary block' }, 'Log out');
    logout.addEventListener('click', function () {
      logout.disabled = true;
      api('/api/logout', { method: 'POST', body: {} }).then(function () { me = null; showLogin(); },
        function (e) { logout.disabled = false; if (!e.handled) flash(e.message, true); });
    });
    root.appendChild(h('div', { class: 'set-end' }, logout, resetBtn, resetBox));
    root.appendChild(h('p', { class: 'tiny center' }, 'Hackathon prototype for the S-Pankki challenge. Synthetic data.'));
    toAnchor();
  }

  // ---------- start ----------
  function init() {
    viewEl = document.getElementById('view');
    document.querySelectorAll('[data-icon]').forEach(function (el) {
      el.appendChild(icon(el.getAttribute('data-icon'), 20));
    });
    document.getElementById('ask-btn').addEventListener('click', function () { openAsk(); });
    document.getElementById('gear-btn').addEventListener('click', function () { openSettings(); });
    boot();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
