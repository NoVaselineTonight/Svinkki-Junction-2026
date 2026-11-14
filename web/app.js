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
    chat: ['M21 12a8 8 0 0 1-11.5 7.2L4 20l1.1-4.4A8 8 0 1 1 21 12z'],
    chev: ['M9 6l6 6-6 6'],
    back: ['M15 18l-6-6 6-6'],
    plus: ['M12 5v14', 'M5 12h14'],
    send: ['M5 12h14', 'M13 6l6 6-6 6'],
    x: ['M6 6l12 12', 'M18 6L6 18'],
    trash: ['M4 7h16', 'M10 11v6', 'M14 11v6', 'M6 7l1 13h10l1-13', 'M9 7V4h6v3'],
    pin: ['M6 3h12v18l-6-4-6 4z'],
    flag: ['M5 21V4', 'M5 4h12l-2.5 4 2.5 4H5'],
    target: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8z', 'M12 12h.01'],
    coin: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M14.5 9H11a1.75 1.75 0 0 0 0 3.5h2a1.75 1.75 0 0 1 0 3.5H9.5', 'M12 7.5V9', 'M12 16v1.5'],
    tag: ['M3 12V3h9l9 9-9 9z', 'M7.5 7.5h.01'],
    list: ['M8 6h13', 'M8 12h13', 'M8 18h13', 'M3 6h.01', 'M3 12h.01', 'M3 18h.01'],
    receipt: ['M6 3h12v18l-3-2-3 2-3-2-3 2z', 'M9 8h6', 'M9 12h6'],
    sliders: ['M4 6h10', 'M18 6h2', 'M4 12h4', 'M12 12h8', 'M4 18h12', 'M20 18h0', 'M16 4v4', 'M10 10v4', 'M18 16v4'],
    people: ['M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z', 'M3 21v-1a6 6 0 0 1 12 0v1', 'M16 3.5a4 4 0 0 1 0 7', 'M21 21v-1a6 6 0 0 0-3-5.2'],
    wallet: ['M3 7h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z', 'M3 7l12-4v4', 'M16 13.5h.01'],
    calendar: ['M4 5h16v16H4z', 'M4 10h16', 'M9 3v4', 'M15 3v4'],
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
    svg.setAttribute('class', 'ico');
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
    // House rule: whole euros from €20 up, cents only below. opts.exact keeps the cents (single payments).
    var dec = opts.exact ? 2 : (abs >= 20 || (opts.hero && abs >= 1000) ? 0 : 2);
    if (!opts.exact && dec === 2 && abs === 0) dec = 0;
    var s = abs.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec });
    var isZero = Number(abs.toFixed(dec)) === 0;
    var sign = (n < 0 && !isZero) ? '-' : (opts.plus && n > 0 ? '+' : '');
    return sign + '€' + s;
  }
  // Whole euros for figures where cents are noise: "€445".
  function euros(n) { return money(Math.round(num(n)), { hero: true }).replace(/\.00$/, ''); }

  // The current year is left out of dates: "15 Oct", but "30 Jun 2027".
  function yearPart(y) { return (me && me.today && String(me.today).slice(0, 4) === y) ? '' : ' ' + y; }
  function fmtDate(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || ''));
    if (!m) return s ? String(s) : '';
    return Number(m[3]) + ' ' + MON[Number(m[2]) - 1] + yearPart(m[1]);
  }
  function fmtMonth(ym) {
    var m = /^(\d{4})-(\d{2})/.exec(String(ym || ''));
    if (!m) return String(ym || '');
    return MONTHS[Number(m[2]) - 1] + yearPart(m[1]);
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
      return MONTHS[Number(a[2]) - 1] + yearPart(a[1]);
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
  function round1(n) { return String(Math.round(num(n) * 10) / 10); }

  function lastDayOfMonth(ym) {
    var m = /^(\d{4})-(\d{2})/.exec(ym);
    var d = new Date(Date.UTC(Number(m[1]), Number(m[2]), 0)).getUTCDate();
    return ym.slice(0, 7) + '-' + (d < 10 ? '0' + d : String(d));
  }

  function pad2(n) { return n < 10 ? '0' + n : String(n); }
  // "Today 14:05", "Yesterday 09:12", "12 Nov", "12 Nov 2025".
  function humanWhen(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return fmtDate(iso);
    var now = new Date();
    var start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    var hm = pad2(d.getHours()) + ':' + pad2(d.getMinutes());
    if (d.getTime() >= start) return 'Today ' + hm;
    if (d.getTime() >= start - 86400000) return 'Yesterday ' + hm;
    return d.getDate() + ' ' + MON[d.getMonth()] + (d.getFullYear() !== now.getFullYear() ? ' ' + d.getFullYear() : '');
  }

  function plural(n, one, many) { return n + ' ' + (n === 1 ? one : many); }
  function cap(s) { s = String(s || ''); return s.charAt(0).toUpperCase() + s.slice(1); }

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
    if (status === 404) return 'That\'s no longer available.';
    if (status === 413) return 'That message is too long.';
    if (status === 400 || status === 422) return 'I couldn\'t handle that. Try asking in a different way.';
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
          throw new ApiError(403, code, 'Turn on "Analyse my transactions" in Settings to use this.', true);
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
  var chat = null;         // the open conversation; null on other screens
  var mode = 'boot';       // boot | login | consent | home | conv
  var viewEl = null;
  var convApi = null;      // true once the server keeps conversations, false when it does not
  var localConv = null;    // {title, turns, updated}: the one unsaved conversation when the server keeps none

  function alive(t) { return t === token; }
  function firstName() { return me && me.name ? String(me.name).split(',')[0] : ''; }

  // screen: home | conv | anything else (login, consent, boot).
  function setChrome(screen, sub) {
    var inApp = screen === 'home' || screen === 'conv';
    document.getElementById('top-actions').hidden = !inApp;
    document.getElementById('back-btn').hidden = screen !== 'conv';
    document.body.classList.toggle('chat-screen', screen === 'conv');
    document.body.classList.toggle('home-screen', screen === 'home');
    document.getElementById('topbar-sub').textContent = inApp ? '' : (sub || '');
  }

  function clearView() {
    token++;
    chat = null;
    viewEl.replaceChildren();
    viewEl.scrollTop = 0;
    window.scrollTo(0, 0);
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

  // Something under "Your things" changed: redraw Home when it is the screen.
  function thingsChanged() {
    if (mode === 'home' && !sheetState) showHome();
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

  // One card language: a short title (and a quiet subtitle), a key figure or a picture,
  // at most three rows, and everything else behind one "More".
  function cardShell(title, sub, cls) {
    var c = h('section', { class: 'card' + (cls ? ' ' + cls : '') });
    c.appendChild(h('div', { class: 'card-head' },
      h('div', { class: 'card-titles' }, h('h3', { class: 'card-title' }, title), sub ? h('span', { class: 'card-sub' }, sub) : null)));
    return c;
  }
  var card = cardShell;

  function keyFig(c, value, label, cls) {
    c.appendChild(h('div', { class: 'key' + (cls ? ' ' + cls : '') }, h('span', { class: 'key-num' }, value), label ? h('span', { class: 'key-label' }, label) : null));
  }

  function rowsNode(list) {
    var box = h('div', { class: 'rows' });
    (list || []).filter(Boolean).forEach(function (r) {
      box.appendChild(h('div', { class: 'row' }, h('span', { class: 'row-label' }, r[0]), h('span', { class: 'row-val' }, r[1])));
    });
    return box.childNodes.length ? box : null;
  }
  function addRows(c, list) { var n = rowsNode((list || []).filter(Boolean).slice(0, 3)); if (n) c.appendChild(n); }

  // The one disclosure control used everywhere.
  function disclosure(label, cls, open) {
    var body = h('div', { class: 'disc-body' });
    var d = h('details', { class: 'disc' + (cls ? ' ' + cls : '') },
      h('summary', null, h('span', { class: 'disc-label' }, label), icon('chev', 18)), body);
    if (open) d.open = true;
    return { el: d, body: body };
  }

  function flat(list, out) {
    out = out || [];
    (list || []).forEach(function (x) {
      if (x == null || x === false) return;
      if (Array.isArray(x)) flat(x, out); else out.push(x);
    });
    return out;
  }
  // Everything secondary: notes, method, long lists, the transactions link. The method text
  // (`explain`) is added only where a card passes it in on purpose.
  function more(c, nodes, d, evTitle) {
    var list = flat([nodes, d ? evidenceLink(d.evidence, evTitle) : null]);
    if (!list.length) return c;
    var m = disclosure('More', 'more');
    append(m.body, list);
    c.appendChild(m.el);
    return c;
  }

  function eyebrow(text) { return h('p', { class: 'eyebrow' }, text); }
  function para(text, cls) { return text ? h('p', { class: cls || 'small' }, ht(text)) : null; }

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
      h('span', { class: 'sw-text' }, titleEl, desc ? h('span', { class: 'sw-desc' }, desc) : null),
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
      h('span', { class: 'bar-label' }, label),
      h('div', { class: 'bar-track', 'aria-hidden': 'true' }, fill),
      h('span', { class: 'bar-val' }, valueText != null ? valueText : money(value))
    );
  }

  function labelBars(list, mx, cls) {
    var box = h('div', { class: 'bars' });
    (list || []).forEach(function (x) {
      var v = num(x.total != null ? x.total : x.amount);
      box.appendChild(barRow(x.label || x.name || x.target || '?', v, mx, cls));
    });
    return box;
  }
  function maxOf(list) {
    return Math.max.apply(null, (list || []).map(function (x) { return Math.abs(num(x.total != null ? x.total : x.amount)); }).concat([1]));
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
        eyebrow('Compared with people like you'),
        barRow('You', num(p.you), mx, 'you'),
        barRow(p.basis === 'mean' ? 'Average' : 'Typical', num(p.peer_typical), mx, 'median'),
        g.description ? h('p', { class: 'tiny' }, g.description + (g.n ? ' (' + g.n + ' customers)' : '') + (p.approximate ? ', approximate' : '')) : null);
    }
    if (d.peer_hint) {
      var b = h('button', { type: 'button', class: 'link-btn' }, d.peer_hint);
      b.addEventListener('click', function () { openSettings(); });
      return b;
    }
    return null;
  }

  function stat(value, label) { return h('div', { class: 'stat' }, h('b', null, value), h('span', null, label)); }

  function explainNode(d) {
    return d && d.explain ? h('p', { class: 'explain' }, ht(d.explain)) : null;
  }

  // ---------- sheets ----------
  var sheetState = null;
  var FOCUSABLE = 'button, input, select, textarea, summary, a[href], [tabindex]:not([tabindex="-1"])';

  // opts.full: a full-height page instead of a bottom sheet.
  function openSheet(title, opts) {
    closeSheet();
    opts = opts || {};
    var previous = document.activeElement;
    var app = document.getElementById('app');
    var body = h('div', { class: 'sheet-body' });
    var closeBtn = h('button', { type: 'button', class: 'sheet-close', 'aria-label': 'Close' }, icon('x', 20));
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
    document.body.classList.add('sheet-open');
    if (app) app.inert = true;     // the screen behind the sheet cannot be reached
    sheetState = { overlay: overlay, onKey: onKey, previous: previous, onClose: opts.onClose || null };
    closeBtn.focus();
    return body;
  }

  function closeSheet() {
    if (!sheetState) return;
    var st = sheetState;
    document.removeEventListener('keydown', st.onKey);
    st.overlay.remove();
    document.body.classList.remove('sheet-open');
    var app = document.getElementById('app');
    if (app) app.inert = false;
    sheetState = null;
    var p = st.previous;
    if (p && p.focus && document.contains(p)) p.focus();
    if (st.onClose) st.onClose();
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

  var LEARNED_THING = { id: 'learned', kind: 'learned', title: 'What I have learned' };

  // Inline picker under one purchase row. Sends only tx_id, label, context and apply_to_merchant.
  function categoryPicker(r, holder, opts) {
    holder.replaceChildren(loadingNode('Loading categories...'));
    loadLabels().then(function (labels) {
      if (!labels.length) { holder.replaceChildren(h('p', { class: 'small muted' }, 'Categories are not available right now.')); return; }
      var uid = 'cp-' + r.id + '-' + Math.random().toString(36).slice(2, 6);
      var sel = h('select', { class: 'input', id: uid + '-l' });
      labels.forEach(function (l) { sel.appendChild(h('option', { value: l }, l)); });
      if (r.label && labels.indexOf(r.label) >= 0) sel.value = r.label;
      var night = switchRow(uid + '-n', 'Part of a night out', '', r.context === 'night_out', function () {});
      var chk = h('input', { type: 'checkbox', id: uid + '-m' });
      var msg = h('div', { 'aria-live': 'polite' });
      var save = h('button', { type: 'button', class: 'btn' }, 'Save');
      var cancel = h('button', { type: 'button', class: 'link-btn' }, 'Cancel');
      cancel.addEventListener('click', function () { holder.replaceChildren(); });
      save.addEventListener('click', function () {
        save.disabled = true;
        msg.replaceChildren(loadingNode('Saving...'));
        api('/api/overrides', { method: 'POST', body: {
          tx_id: r.id, label: sel.value, context: night.input.checked ? 'night_out' : '', apply_to_merchant: !!chk.checked
        } }).then(function (res) {
          var n = res && res.affected != null ? num(res.affected) : 1;
          var note = 'Remembered. ' + plural(n, 'purchase', 'purchases') + ' updated.';
          thingsChanged();
          if (opts && opts.reload) opts.reload(note);
          else holder.replaceChildren(h('p', { class: 'notice ok', role: 'status' }, note), thingChip(LEARNED_THING));
        }, function (e) {
          save.disabled = false;
          if (e.handled) return;
          msg.replaceChildren(errorNode(e));
        });
      });
      holder.replaceChildren(h('div', { class: 'picker' },
        h('label', { for: uid + '-l', class: 'field-label' }, 'Category'), sel, night.el,
        h('label', { class: 'check-row', for: uid + '-m' }, chk, h('span', null, 'Every purchase from this merchant')),
        h('div', { class: 'btn-row' }, save, cancel), msg));
      sel.focus();
    }, function (e) {
      if (e && e.handled) return;
      holder.replaceChildren(h('p', { class: 'small muted' }, 'Categories are not available right now.'));
    });
  }

  // opts: { reload(note), note, bare }. reload is given when the list can redraw itself.
  function txList(res, opts) {
    opts = opts || {};
    var rows = (res && res.rows) || [];
    var box = h('div', { class: 'tx-box' });
    if (opts.note) box.appendChild(h('p', { class: 'notice ok', role: 'status' }, opts.note));
    if (!opts.bare) {
      box.appendChild(h('p', { class: 'small muted' },
        plural(res.count != null ? num(res.count) : rows.length, 'transaction', 'transactions') + ', ' + money(Math.abs(num(res.total)))
        + (res.truncated ? ' (showing the first ' + rows.length + ')' : '')));
    }
    if (!rows.length) {
      if (!opts.bare) box.appendChild(h('p', { class: 'muted' }, 'No transactions match.'));
      return box;
    }
    var list = h('div', { role: 'list', class: 'tx-list' });
    rows.forEach(function (r) {
      var amt = num(r.amount);
      // The row is named by what it was (Bar, Taxi, Groceries), not by the merchant's internal id.
      var title = String(r.label || r.display_label || r.category || 'Transaction');
      var time = (r.ts && String(r.ts).length >= 16) ? String(r.ts).slice(11, 16) : '';
      var sub = h('span', { class: 'tx-sub' }, fmtDate(r.d || r.ts) + (time ? ', ' + time : '') +
        (r.context === 'night_out' ? ' · Night out' : ''));
      var main = h('div', { class: 'tx-main' }, h('span', { class: 'tx-title' }, title), sub);
      var line = h('div', { class: 'tx-line' }, main, h('span', { class: 'tx-amt' + (amt > 0 ? ' in' : '') }, money(amt, { plus: true, exact: true })));
      var item = h('div', { class: 'tx', role: 'listitem' }, line);
      if (canRelabel(r)) {
        var holder = h('div', { class: 'tx-extra' });
        var btn = h('button', { type: 'button', class: 'link-btn tx-fix', 'aria-label': 'Change category for ' + title + ' ' + fmtDate(r.d || r.ts) }, 'Change category');
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
    var body = openSheet(ht(title) || 'Transactions', { full: true });
    var t = token;
    var tabs = h('div', { class: 'chips' });
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
    } else if (filters[0].from && !/\d{4}/.test(String(filters[0].title || ''))) {
      body.appendChild(h('p', { class: 'small muted' }, fmtRange(filters[0])));
    }
    body.appendChild(out);
    show(0);
  }

  function evidenceLink(evidence, title) {
    if (!evidenceList(evidence).length) return null;
    return h('button', { type: 'button', class: 'link-btn ev-link', onclick: function () { openEvidence(evidence, title || 'Transactions'); } }, 'See the transactions');
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
    setChrome('login', '');
    localConv = null;
    var t = token;
    var list = h('div', { class: 'persona-list' });
    var status = h('div', { 'aria-live': 'polite' });
    var randomBtn = h('button', { type: 'button', class: 'persona random' },
      h('strong', null, 'Try as a random customer'),
      h('span', null, 'Picks a random synthetic customer who uses the bank as their main account.'));
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
    viewEl.appendChild(h('div', { class: 'login' },
      h('div', null,
        h('span', { class: 'demo-tag' }, 'Demo only'),
        h('h1', { class: 'login-title' }, 'Who are you today?'),
        h('p', { class: 'muted' }, 'A prototype with synthetic data. In the bank app you would already be signed in.')),
      randomBtn, status,
      h('h2', { class: 'section-title' }, 'Or pick an example'),
      list));
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
    { value: 'off', label: 'None' },
    { value: 'few', label: 'One' },
    { value: 'normal', label: 'Up to three' }
  ];
  var ONOFF = [
    { value: 'on', label: 'On' },
    { value: 'off', label: 'Off' }
  ];

  function normFreq(v) {
    if (v === 'fortnightly' || v === 'every_two_weeks' || v === 'two_weeks' || v === 'every2weeks') return 'biweekly';
    return v || 'monthly';
  }

  // The full settings object the server expects, with changes applied.
  function settingsWith(changes) {
    var s = (me && me.settings) || {};
    return Object.assign({
      checkin_frequency: normFreq(s.checkin_frequency),
      suggestion_level: s.suggestion_level || 'few',
      quiz: s.quiz || 'weekly',
      monthly_saving_target: num(s.monthly_saving_target),
      challenges: s.challenges === 'on' ? 'on' : 'off'
    }, changes || {});
  }
  function saveSettings(changes) {
    var body = settingsWith(changes);
    return api('/api/settings', { method: 'POST', body: body }).then(function (r) {
      if (me) me.settings = (r && r.settings) || body;
      return me && me.settings;
    });
  }

  function consentControls(consent, onChange) {
    var state = {
      analysis: !!consent.analysis, ai: !!consent.ai,
      benchmarks: !!consent.benchmarks, suggestions: !!consent.suggestions
    };
    var wrap = h('div', { class: 'switches' });
    function fire(key) { return function (v) { state[key] = v; onChange(key, state); }; }
    var rows = [
      switchRow('sw-analysis', 'Analyse my transactions', 'Needed for every answer. Only your own rows.', state.analysis, fire('analysis'), { tag: 'needed' }),
      switchRow('sw-ai', 'Let an AI help with the wording', 'It sees results only, never your name, account or raw transactions.', state.ai, fire('ai')),
      switchRow('sw-bench', 'Compare me with people like me', 'Compare your spending with groups of 20+ similar customers. Only group totals are used.', state.benchmarks, fire('benchmarks')),
      switchRow('sw-sugg', 'Give me suggestions', 'Svinkki may suggest things, like putting leftover money aside. Nothing happens unless you say so.', state.suggestions, fire('suggestions'))
    ];
    rows.forEach(function (r) { wrap.appendChild(r.el); });
    return { el: wrap, get: function () { return Object.assign({}, state); } };
  }

  function prefControls(settings, onChange) {
    var s = {
      checkin_frequency: normFreq(settings.checkin_frequency),
      suggestion_level: settings.suggestion_level || 'few',
      quiz: settings.quiz === 'off' ? 'off' : 'weekly',
      monthly_saving_target: num(settings.monthly_saving_target),
      challenges: settings.challenges === 'on' ? 'on' : 'off'
    };
    var wrap = h('div', { class: 'prefs' });
    function fire() { onChange(Object.assign({}, s)); }
    function field(title, ctl, help) {
      wrap.appendChild(h('div', { class: 'pref' }, h('span', { class: 'field-label' }, title), ctl.el, help ? h('p', { class: 'help' }, help) : null));
    }
    field('Check-in', segmented('Check-in', FREQ, s.checkin_frequency, function (v) { s.checkin_frequency = v; fire(); }),
      'A short summary of your money with a few ideas.');
    field('Ideas in a check-in', segmented('Ideas in a check-in', LEVELS, s.suggestion_level, function (v) { s.suggestion_level = v; fire(); }),
      'None, at most one idea, or up to three.');
    field('Weekly challenge', segmented('Weekly challenge', ONOFF, s.challenges, function (v) { s.challenges = v; fire(); }),
      'One small optional challenge from your own habits.');
    field('Weekly quiz', segmented('Weekly quiz', ONOFF, s.quiz === 'off' ? 'off' : 'on', function (v) { s.quiz = v === 'on' ? 'weekly' : 'off'; fire(); }),
      'Guess what you spent. It helps you notice habits.');
    return { el: wrap, get: function () { return Object.assign({}, s); } };
  }

  function showConsent() {
    mode = 'consent';
    closeSheet();
    clearView();
    setChrome('consent', me && me.name ? me.name : '');
    var consent = (me && me.consent) || {};
    var settings = (me && me.settings) || {};
    // A new customer starts with everything on and can switch parts off before starting.
    var fresh = !consent.analysis && !consent.ai && !consent.benchmarks && !consent.suggestions;
    if (fresh) consent = { analysis: true, ai: true, benchmarks: true, suggestions: true };
    var first = firstName();
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
    var choose = disclosure('Your choices', 'section');
    choose.body.appendChild(cc.el);
    choose.body.appendChild(pc.el);
    viewEl.appendChild(h('div', { class: 'welcome' },
      h('h1', null, first ? 'Hi ' + first + '!' : 'Hi!'),
      h('p', null, 'I\'m Svinkki, your money coach. I read your own transactions to answer your questions. An AI helps with the wording; it never sees your name or account.'),
      h('p', { class: 'muted' }, 'Money only moves when you approve it, and only to your own S-Bank savings or funds. You can change these choices any time in Settings.'),
      go, hint, status, choose.el));
  }

  // ---------- boot ----------
  function boot() {
    mode = 'boot';
    closeSheet();
    clearView();
    setChrome('boot', '');
    viewEl.appendChild(loadingNode('Loading...'));
    return api('/api/me').then(function (m) {
      me = m;
      if (!me.consent || !me.consent.analysis) { showConsent(); return; }
      showHome();
    }, function (e) {
      if (e.handled) return;
      clearView();
      viewEl.appendChild(errorNode(e, boot));
    });
  }

  var STATUS_TEXT = { ok: 'On track', tight: 'Tight', over: 'Over budget' };

  function basketKeyOf(b) {
    var k = String(b.key || '').toLowerCase();
    if (BASKET_NAMES[k]) return k;
    return 'other';
  }

  // The three baskets: a split bar and one row per basket (each opens its transactions).
  function basketsParts(d) {
    var items = (d.baskets || []).filter(function (b) { return ['regular', 'unexpected', 'everyday'].indexOf(String(b.key)) >= 0; });
    var total = items.reduce(function (s, b) { return s + Math.max(0, num(b.total)); }, 0);
    var main = h('div', { class: 'baskets' });
    var stack = h('div', { class: 'stack', role: 'img', 'aria-label': 'Spending split between the three baskets' });
    items.forEach(function (b) {
      var seg = h('span', { class: 'b-' + basketKeyOf(b) });
      seg.style.width = (total > 0 ? (Math.max(0, num(b.total)) / total) * 100 : 0) + '%';
      stack.appendChild(seg);
    });
    main.appendChild(stack);
    var extra = [];
    items.forEach(function (b) {
      var k = basketKeyOf(b);
      var share = total > 0 ? (Math.max(0, num(b.total)) / total) * 100 : 0;
      var row = h('button', { type: 'button', class: 'basket-row', 'aria-label': (b.name || BASKET_NAMES[k]) + ', ' + money(b.total) + '. Open transactions.' },
        h('span', { class: 'dot b-' + k, 'aria-hidden': 'true' }),
        h('span', { class: 'basket-name' }, b.name || BASKET_NAMES[k]),
        h('span', { class: 'basket-amt' }, money(b.total), h('span', null, pct(share))),
        h('span', { class: 'chev' }, icon('chev', 18)));
      row.addEventListener('click', function () { openEvidence(b.evidence, b.name || BASKET_NAMES[k]); });
      main.appendChild(row);
      if (b.top && b.top.length) {
        extra.push(eyebrow((b.name || BASKET_NAMES[k]) + ': ' + (BASKET_BLURB[k] || '').toLowerCase()));
        extra.push(labelBars(b.top.slice(0, 4), maxOf(b.top), 'b-' + k));
      }
    });
    if (d.rules) extra.push(h('p', { class: 'explain' }, ht(d.rules)));
    return { main: main, more: extra };
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
    var c = cardShell('Weekly quiz', q.period ? fmtRange(q.period) : '');
    c.appendChild(h('p', { class: 'quiz-q' }, q.question || 'Guess your spending this week.'));
    var mid = Math.round((min + max) / 2 / stepV) * stepV;
    var out = h('div', { class: 'quiz-guess', 'aria-live': 'polite' }, money(mid));
    var slider = h('input', { type: 'range', class: 'range', min: min, max: max, step: stepV, 'aria-label': 'Your guess in euros' });
    slider.value = String(mid);
    slider.addEventListener('input', function () { out.textContent = money(slider.value); });
    var btn = h('button', { type: 'button', class: 'btn block' }, 'Lock in my guess');
    var result = h('div', { class: 'quiz-result', 'aria-live': 'polite' });
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
        var line = r.verdict || (Math.abs(diff) < 0.5 ? 'Spot on.' : (diff > 0 ? 'You guessed ' + money(diff) + ' too high.' : 'You guessed ' + money(-diff) + ' too low.'));
        result.appendChild(h('div', { class: 'reveal' },
          h('div', { class: 'key-label' }, 'You spent'), big,
          h('p', { class: 'small' }, 'Your guess: ' + money(guess) + '. ' + line)));
        animateNumber(big, actual, 900);
        var again = h('button', { type: 'button', class: 'btn secondary block' }, 'Try another');
        var statsBox = h('div', { 'aria-live': 'polite' });
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
        var extra = h('div');
        more(extra, [r.tip ? h('p', { class: 'small' }, r.tip) : null, peerBlock(r)], { evidence: r.evidence }, 'The transactions behind the quiz');
        result.appendChild(extra);
        api('/api/quiz/stats').then(function (s) {
          if (s && num(s.count)) {
            statsBox.replaceChildren(thingChip({ id: 'quiz', kind: 'quiz', title: 'Quiz score' }, 'Score saved to Your things'));
            thingsChanged();
          }
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
    var sec = cardShell('Your check-in', fmtPeriod(c.period));
    // A week without a payday has no "money in": show what was spent, not a shortfall against nothing.
    if (num(c.income) > 0) {
      keyFig(sec, money(c.surplus), num(c.surplus) >= 0 ? 'left over' : 'more out than in');
      addRows(sec, [['Money in', money(c.income)], ['Spent', money(c.spent)]]);
    } else {
      keyFig(sec, money(c.spent), 'spent');
    }
    var sug = c.suggestions || [];
    if (sug.length) sec.appendChild(suggestionBlock(sug[0]));
    var hl = (c.highlights || []).filter(Boolean);
    more(sec, [
      hl.length ? h('ul', { class: 'plain-list' }, hl.map(function (x) { return h('li', null, ht(x)); })) : null,
      sug.slice(1).map(function (s) { return suggestionBlock(s); })
    ], c, 'The period in transactions');
    return sec;
  }

  function suggestionBlock(s) {
    var box = h('div', { class: 'tip' });
    box.appendChild(h('b', { class: 'tip-title' }, ht(s.title) || 'Suggestion'));
    var det = disclosure('Why', 'more');
    if (s.detail) { det.body.appendChild(h('p', { class: 'small' }, ht(s.detail))); }
    var msg = h('div', { 'aria-live': 'polite' });
    var row = h('div', { class: 'btn-row' });
    function act(action) {
      row.querySelectorAll('button').forEach(function (b) { b.disabled = true; });
      api('/api/suggestions/action', { method: 'POST', body: { id: s.id, action: action } }).then(function (r) {
        row.hidden = true;
        if (r && r.proposal) { msg.replaceChildren(moneyProposalCard(r.proposal)); return; }
        msg.replaceChildren(h('p', { class: 'notice ' + (r && r.ok === false ? '' : 'ok') }, (r && r.message) ? ht(r.message) : (action === 'accept' ? 'Noted.' : 'Okay, we will leave it for now.')));
      }, function (e) {
        row.querySelectorAll('button').forEach(function (b) { b.disabled = false; });
        if (!e.handled) msg.replaceChildren(errorNode(e));
      });
    }
    row.appendChild(h('button', { type: 'button', class: 'btn small-btn', onclick: function () { act('accept'); } }, s.action_label || 'Accept'));
    row.appendChild(h('button', { type: 'button', class: 'link-btn', onclick: function () { act('snooze'); } }, 'Not now'));
    box.appendChild(row); box.appendChild(msg);
    if (s.detail) box.appendChild(det.el);
    return box;
  }

  // --- The simulated bank account at the top of the start page ---
  function accountCard(a) {
    var cur = a.current || {}, sav = a.savings || {};
    var btn = h('button', { type: 'button', class: 'acct-card', 'aria-label': 'Your accounts: current account balance ' + money(cur.balance, { exact: true }) },
      h('span', { class: 'acct-top' }, h('span', { class: 'acct-name' }, cur.name || 'Current account'), h('span', { class: 'acct-num' }, cur.number || '')),
      h('span', { class: 'acct-bal' }, money(cur.balance, { exact: true })),
      h('span', { class: 'acct-rows' },
        h('span', { class: 'acct-row' }, h('span', null, sav.name || 'Savings and investments'), h('b', null, money(sav.balance, { exact: true }))),
        a.safe_to_spend != null ? h('span', { class: 'acct-row' }, h('span', null, 'Safe to spend' + (a.next_payday ? ' until ' + fmtDate(a.next_payday) : '')),
          h('b', null, num(a.safe_to_spend) > 0 ? money(a.safe_to_spend) : 'Nothing')) : null),
      h('span', { class: 'acct-demo' }, 'Demo account · synthetic data'));
    btn.addEventListener('click', function () { openAccount(); });
    return btn;
  }

  function openAccount() {
    var body = openSheet('Your accounts');
    var t = token;
    load(body, t, function () { return api('/api/account'); }, function (a) {
      var cur = a.current || {}, sav = a.savings || {};
      var box = h('div', { class: 'thing-body' });
      box.appendChild(rowsNode([[cur.name + ' ' + (cur.number || ''), money(cur.balance, { exact: true })],
        [sav.name, money(sav.balance, { exact: true })]].concat((sav.parts || []).map(function (p) { return ['  ' + p.name, money(p.amount, { exact: true })]; }))));
      if (a.safe_to_spend != null) box.appendChild(h('p', { class: 'small' }, 'Safe to spend' + (a.next_payday ? ' until payday on ' + fmtDate(a.next_payday) : '') + ': ' + (num(a.safe_to_spend) > 0 ? money(a.safe_to_spend) : 'nothing') + '.'));
      box.appendChild(eyebrow('Latest transactions'));
      var txBox = h('div', null, loadingNode('Loading...'));
      box.appendChild(txBox);
      api('/api/transactions?limit=5').then(function (r) { if (alive(t)) txBox.replaceChildren(txList(r || {}, { bare: true })); },
        function (e) { if (!e.handled) txBox.replaceChildren(errorNode(e)); });
      box.appendChild(eyebrow('Move money'));
      var out = h('div', { 'aria-live': 'polite' });
      box.appendChild(moneyMoveForm(out, a.destinations, a.can_move));
      box.appendChild(out);
      box.appendChild(h('p', { class: 'tiny' }, ht(a.note || '')));
      body.appendChild(box);
    });
  }

  // --- Moving money inside S-mobiili: always an explicit approval of one exact move ---
  function moneyProposalCard(pr) {
    var c = cardShell('Approve this move?', 'Inside S-mobiili', 'money-card');
    keyFig(c, money(pr.amount), 'to your ' + (pr.to || 'savings'));
    c.appendChild(rowsNode([['From', pr.from || 'Your current account'], ['To', pr.to || ''],
      pr.balance_after != null ? ['Balance after', money(pr.balance_after)] : null].filter(Boolean)));
    if (pr.about) c.appendChild(h('p', { class: 'small' }, ht(pr.about)));
    if (pr.risk) c.appendChild(h('p', { class: 'notice' }, ht(pr.risk)));
    c.appendChild(h('p', { class: 'tiny' }, ht(pr.note || 'Nothing moves until you approve.')));
    var msg = h('div', { 'aria-live': 'polite' });
    var row = h('div', { class: 'btn-row' });
    var yes = h('button', { type: 'button', class: 'btn' }, 'Approve and move ' + money(pr.amount));
    var no = h('button', { type: 'button', class: 'btn secondary' }, 'Cancel');
    function answer(approve) {
      yes.disabled = true; no.disabled = true;
      msg.replaceChildren(loadingNode(approve ? 'Moving...' : 'Cancelling...'));
      api('/api/money/confirm', { method: 'POST', body: { proposal_id: pr.id, approve: approve, amount: pr.amount, dest: pr.dest } }).then(function (r) {
        row.hidden = true;
        var ok = r && r.ok !== false;
        msg.replaceChildren(h('p', { class: 'notice ' + (ok && r.moved ? 'ok' : (ok ? '' : 'err')) }, ht((r && r.message) || (approve ? 'Done.' : 'Nothing was moved.'))));
        if (r && r.moved) thingsChanged();
      }, function (e) {
        yes.disabled = false; no.disabled = false;
        if (!e.handled) msg.replaceChildren(errorNode(e));
      });
    }
    yes.addEventListener('click', function () { answer(true); });
    no.addEventListener('click', function () { answer(false); });
    row.appendChild(yes); row.appendChild(no);
    c.appendChild(row); c.appendChild(msg);
    return c;
  }

  // A small form for moving money yourself: pick where, pick how much, then approve on the next card.
  function moneyMoveForm(out, dests, available) {
    var uid = 'mv-' + Math.random().toString(36).slice(2, 7);
    var sel = h('select', { class: 'input', id: uid + '-d' });
    (dests || []).forEach(function (d) { sel.appendChild(h('option', { value: d.id }, d.name)); });
    var amt = h('input', { type: 'number', class: 'input', id: uid + '-a', min: '5', step: '1', inputmode: 'decimal', placeholder: '50' });
    var btn = h('button', { type: 'button', class: 'btn block' }, 'Show the move');
    btn.addEventListener('click', function () {
      var v = Number(amt.value);
      if (!isFinite(v) || v <= 0) { out.replaceChildren(h('p', { class: 'notice' }, 'Enter an amount above zero.')); return; }
      btn.disabled = true;
      api('/api/money/propose', { method: 'POST', body: { dest: sel.value, amount: v } }).then(function (r) {
        btn.disabled = false;
        if (r && r.proposal) out.replaceChildren(moneyProposalCard(r.proposal));
        else out.replaceChildren(h('p', { class: 'notice' }, ht((r && r.message) || 'That move is not possible.')));
      }, function (e) { btn.disabled = false; if (!e.handled) out.replaceChildren(errorNode(e)); });
    });
    return h('div', { class: 'form' },
      available != null ? h('p', { class: 'small' }, 'You can move up to ' + money(Math.floor(num(available))) + ' now without touching money for bills.') : null,
      h('div', { class: 'form-grid' },
        h('div', null, h('label', { for: uid + '-d' }, 'Where to'), sel),
        h('div', null, h('label', { for: uid + '-a' }, 'Amount in euros'), amt)),
      btn);
  }

  // --- Can I afford this? ---
  var VERDICT_WORDS = { yes: 'Yes', tight: 'Tight', no: 'Not right now', caution: 'Think twice' };

  function affordInto(c, d) {
    var v = VERDICT_WORDS[d.verdict] ? d.verdict : 'tight';
    c.appendChild(h('div', { class: 'verdict v-' + v }, VERDICT_WORDS[v]));
    if (v === 'caution' && d.verdict_text) c.appendChild(h('p', { class: 'small' }, ht(d.verdict_text)));
    addRows(c, [
      d.per_day_after != null ? ['Left a day after it', money(d.per_day_after)] : null,
      d.next_payday ? ['Until payday', fmtDate(d.next_payday)] : null
    ]);
    var ge = d.goal_effect;
    var alts = (d.alternatives || []).filter(function (a) { return typeof a === 'string' && a; });
    more(c, [
      alts.length ? h('ul', { class: 'plain-list' }, alts.map(function (a) { return h('li', null, ht(a)); })) : null,
      ge && ge.delay_text ? h('p', { class: 'goal-line' }, ht(ge.delay_text)) : null,
      rowsNode([d.safe_total != null ? ['Safe to spend before it', money(d.safe_total)] : null, d.after != null ? ['Left until payday', money(d.after)] : null])
    ], d, 'Where this comes from');
    return c;
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
        var box = h('div', { class: 'afford-out' });
        affordInto(box, d || {});
        out.replaceChildren(box);
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
    return h('div', { class: 'form' },
      h('div', { class: 'form-grid' },
        h('div', null, h('label', { for: uid + '-i' }, 'What is it?'), item),
        h('div', null, h('label', { for: uid + '-p' }, 'Price in euros'), price)),
      btn);
  }

  // --- Challenges ---
  function isMoneyUnit(u) { return /eur|€/i.test(String(u || '')); }

  function progressNode(p, onStop) {
    var money_ = isMoneyUnit(p.unit);
    var cur = num(p.current), tgt = num(p.target);
    var fmt = function (v) { return money_ ? money(v) : String(Math.round(v * 10) / 10); };
    var status = ['on_track', 'done', 'missed', 'at_risk'].indexOf(p.status) >= 0 ? p.status : 'on_track';
    var fill = h('div', { class: 'prog-fill s-' + status });
    fill.style.width = (tgt > 0 ? Math.max(0, Math.min(100, cur / tgt * 100)) : (status === 'done' ? 100 : 0)) + '%';
    var box = h('div', { class: 'challenge' });
    box.appendChild(h('p', { class: 'quiz-q' }, ht(p.title) || 'Your challenge'));
    box.appendChild(h('div', { class: 'prog-track', role: 'img', 'aria-label': fmt(cur) + ' of ' + fmt(tgt) }, fill));
    box.appendChild(h('p', { class: 'small muted' }, (p.text ? ht(p.text) : fmt(cur) + ' of ' + fmt(tgt))));
    var row = h('div', { class: 'link-row' });
    var ev = evidenceLink(p.evidence, p.title || 'Your challenge');
    if (ev) row.appendChild(ev);
    if (onStop) row.appendChild(h('button', { type: 'button', class: 'link-btn quiet', onclick: onStop }, 'Stop challenge'));
    if (row.childNodes.length) box.appendChild(row);
    return box;
  }

  function optionsNode(options, onPick) {
    var box = h('div', { class: 'options' });
    options.forEach(function (o) {
      var btn = h('button', { type: 'button', class: 'btn secondary small-btn', 'aria-label': 'Start: ' + (o.title || 'challenge') }, 'Start');
      btn.addEventListener('click', function () { btn.disabled = true; onPick(o, btn); });
      box.appendChild(h('div', { class: 'opt' }, h('b', { class: 'opt-text' }, ht(o.title) || 'Challenge'), btn));
    });
    var whys = options.filter(function (o) { return o.why; });
    if (whys.length) {
      var m = disclosure('Why these', 'more');
      whys.forEach(function (o) { m.body.appendChild(h('p', { class: 'small' }, h('b', null, ht(o.title) + ': '), ht(o.why))); });
      box.appendChild(m.el);
    }
    return box;
  }

  // d: {enabled, active, options}. onChange(newData, accepted) after an action.
  function challengeBody(d, onChange) {
    d = d || {};
    if (d.status && d.title && d.active === undefined) d = { enabled: true, active: d };
    var box = h('div', { class: 'challenge-body' });
    var msg = h('div', { 'aria-live': 'polite' });
    function reload(accepted) {
      return api('/api/challenge').then(function (nd) { onChange(nd || {}, accepted); thingsChanged(); });
    }
    function post(body, btn, accepted) {
      api('/api/challenge', { method: 'POST', body: body }).then(function () { return reload(accepted); }).then(null, function (e) {
        if (btn) btn.disabled = false;
        if (e && !e.handled) msg.replaceChildren(errorNode(e));
      });
    }
    var opts = Array.isArray(d.options) ? d.options.slice(0, 3) : [];
    if (d.active) {
      box.appendChild(progressNode(d.active, function () { post({ stop: true }); }));
    } else if (d.enabled && opts.length) {
      box.appendChild(h('p', { class: 'small muted' }, 'Pick one if you like. Skipping is fine.'));
      box.appendChild(optionsNode(opts, function (o, btn) { post({ id: o.id }, btn, true); }));
    } else if (d.enabled === false) {
      var on = h('button', { type: 'button', class: 'btn block' }, 'Turn on weekly challenges');
      on.addEventListener('click', function () {
        on.disabled = true;
        saveSettings({ challenges: 'on' }).then(function () { return reload(false); }).then(null, function (e) {
          on.disabled = false;
          if (e && !e.handled) msg.replaceChildren(errorNode(e));
        });
      });
      box.appendChild(h('p', { class: 'small muted' }, 'Challenges are off. One small optional challenge a week, built from your own habits.'));
      box.appendChild(on);
    } else {
      box.appendChild(h('p', { class: 'small muted' }, 'No challenge right now. New ones come each week.'));
    }
    box.appendChild(msg);
    return box;
  }

  // --- Charts ---
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

  function quizStatsInto(c, s) {
    if (!s || !num(s.count)) {
      c.appendChild(h('p', { class: 'small muted' }, s && s.text ? ht(s.text) : 'Answer a quiz question and your score shows up here.'));
      return c;
    }
    if (s.awareness_score != null) keyFig(c, Math.round(num(s.awareness_score)) + '/100', 'awareness score');
    var pts = (s.points || []).map(function (p) { return p && p.accuracy; }).filter(function (v) { return v != null; });
    if (pts.length > 1) c.appendChild(sparkline(pts));
    addRows(c, [['Questions answered', String(num(s.count))]]);
    more(c, [para(s.text)]);
    return c;
  }

  // --- Transactions used under a chat answer ---
  function usedCount(used) {
    // The number of transactions used, not the number of rows on screen.
    return (used || []).reduce(function (s, g) {
      if (!g || typeof g !== 'object') return s;
      return s + (g.count != null ? num(g.count) : (Array.isArray(g.rows) ? g.rows.length : 0));
    }, 0);
  }

  // The transactions behind an answer: a quiet button and the list it opens.
  function usedParts(used) {
    if (!Array.isArray(used) || !used.length) return null;
    var n = usedCount(used);
    if (!n) return null;
    var id = 'used-' + Math.random().toString(36).slice(2, 8);
    var body = h('div', { class: 'used-body', id: id, hidden: true });
    var btn = h('button', { type: 'button', class: 'act-btn', 'aria-expanded': 'false', 'aria-controls': id },
      icon('list', 16), h('span', null, 'Transactions used (' + n + ')'), icon('chev', 16));
    used.forEach(function (g) {
      if (!g || typeof g !== 'object') return;
      var rows = Array.isArray(g.rows) ? g.rows : [];
      var cnt = g.count != null ? num(g.count) : rows.length;
      var grp = h('div', { class: 'used-group' });
      grp.appendChild(h('div', { class: 'used-head' }, h('b', null, ht(g.title) || 'Transactions'),
        h('span', { class: 'tiny' }, plural(cnt, 'transaction', 'transactions') + ', ' + money(Math.abs(num(g.spent != null && num(g.spent) > 0 ? g.spent : g.total))))));
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
    var W = 300, H = 110, padL = 4, padR = 4, padT = 8, padB = 8;
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

  // ---------- explain a text ----------
  var EXPLAIN_MIN = 40, EXPLAIN_MAX = 6000;

  function isAiMode(mode) { return mode === 'claude' || mode === 'gemini'; }

  function explainCard(d) {
    var c = cardShell('In plain words');
    if (d.summary) c.appendChild(h('p', { class: 'lead' }, String(d.summary)));
    var kp = (d.key_points || []).filter(function (x) { return typeof x === 'string' && x; });
    var wo = (d.watch_out || []).filter(function (x) { return typeof x === 'string' && x; });
    var terms = (d.terms || []).filter(function (x) { return x && x.term; });
    if (terms.length) {
      var tl = h('dl', { class: 'terms' });
      terms.forEach(function (x) {
        tl.appendChild(h('dt', null, String(x.term)));
        tl.appendChild(h('dd', null, String(x.meaning || '')));
      });
      c.appendChild(tl);
    }
    var red = num(d.redactions);
    more(c, [
      kp.length ? [eyebrow('Key points'), h('ul', { class: 'plain-list' }, kp.map(function (x) { return h('li', null, x); }))] : null,
      wo.length ? h('div', { class: 'notice watch' }, h('b', null, 'Watch out for'), h('ul', { class: 'plain-list' }, wo.map(function (x) { return h('li', null, x); }))) : null,
      h('p', { class: 'tiny' }, (isAiMode(d.mode) ? 'Explained by the AI model.' : 'Explained by built-in rules.') + (red > 0 ? ' ' + plural(red, 'personal detail was', 'personal details were') + ' removed first.' : '')),
      d.notice ? h('p', { class: 'tiny' }, ht(d.notice)) : null,
      d.disclaimer ? h('p', { class: 'disclaimer' }, String(d.disclaimer)) : null
    ]);
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
    var body = openSheet('Explain a text', { full: true });
    var uid = 'ex-' + Math.random().toString(36).slice(2, 7);
    var ta = h('textarea', { class: 'input explain-text', id: uid + '-t', rows: '9', maxlength: String(EXPLAIN_MAX + 2000), placeholder: 'Paste text from a loan agreement or a fund prospectus', autocomplete: 'off', 'aria-describedby': uid + '-c ' + uid + '-p' });
    var count = h('p', { class: 'tiny', id: uid + '-c' });
    var form = h('div', { class: 'form' },
      h('label', { for: uid + '-t', class: 'field-label' }, 'Text to explain'), ta, count,
      h('p', { class: 'tiny', id: uid + '-p' }, 'Identity codes, account numbers, e-mail addresses and phone numbers are removed before anything is sent to an AI model.'));
    var go_ = h('button', { type: 'button', class: 'btn block' }, 'Explain');
    var out = h('div', { 'aria-live': 'polite' });
    form.appendChild(go_);
    body.appendChild(form);
    body.appendChild(out);
    function len() { return ta.value.trim().length; }
    function paint() {
      var n = len();
      var ok = n >= EXPLAIN_MIN && n <= EXPLAIN_MAX;
      count.textContent = n.toLocaleString('en-US') + ' of ' + EXPLAIN_MAX.toLocaleString('en-US') + ' characters'
        + (n < EXPLAIN_MIN ? ' (at least ' + EXPLAIN_MIN + ')' : (n > EXPLAIN_MAX ? ' (too long)' : ''));
      go_.disabled = !ok;
    }
    ta.addEventListener('input', paint);
    paint();
    go_.addEventListener('click', function () {
      var text = ta.value.trim();
      if (text.length < EXPLAIN_MIN || text.length > EXPLAIN_MAX) { paint(); return; }
      go_.disabled = true; ta.disabled = true;
      out.replaceChildren(loadingNode('Reading your text…'));
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

  function deadlineText(dl) {
    if (!dl) return '';
    if (/^\d{4}-\d{2}-\d{2}/.test(dl)) return fmtDate(dl);
    if (/^\d{4}-\d{2}$/.test(dl)) return fmtMonth(dl);
    return String(dl);
  }

  // ---------- rich text in a reply ----------
  // Plain text with line breaks, **bold** and simple bullet lines. Built from nodes only.
  function richText(text) {
    var box = h('div', { class: 'rich' });
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

  // ---------- receipts: what was bought, not only what was paid ----------
  function qtyText(l) {
    var q = num(l.qty);
    if (l.unit === 'kg') return round1(q) + ' kg';
    if (l.unit === 'l') return round1(q) + ' l';
    return q > 1 ? q + ' x' : '';
  }
  function receiptLines(lines, limit) {
    var ul = h('ul', { class: 'rc-lines' });
    (lines || []).slice(0, limit || 40).forEach(function (l) {
      var q = qtyText(l);
      ul.appendChild(h('li', null,
        h('span', { class: 'rc-name' }, (q ? q + ' ' : '') + (l.name || 'Item')),
        h('span', { class: 'rc-sum' }, money(l.line_total, { exact: true }))));
    });
    return ul;
  }
  function receiptNode(r) {
    var sub = fmtDate(r.d);
    if (r.kind === 'fuel' && r.fuel && r.fuel.litres != null) sub += ', ' + round1(r.fuel.litres) + ' l';
    var dd = disclosure('', 'rc');
    var sum = dd.el.querySelector('summary');
    sum.replaceChildren(
      h('span', { class: 'rc-head' }, h('b', null, r.store || 'Receipt'), h('span', { class: 'tiny' }, sub)),
      h('b', { class: 'rc-total' }, money(r.total, { exact: true })), icon('chev', 18));
    dd.body.appendChild(receiptLines(r.lines));
    if (r.bonus && r.bonus.amount != null) {
      dd.body.appendChild(h('p', { class: 'tiny' }, 'Bonus ' + num(r.bonus.rate_pct) + '%: ' + money(r.bonus.amount)));
    }
    return dd.el;
  }
  function groupBars(groups, limit) {
    groups = (groups || []).filter(function (g) { return num(g.total) > 0; }).slice(0, limit || 6);
    var mx = Math.max.apply(null, groups.map(function (g) { return num(g.total); }).concat([1]));
    var box = h('div', { class: 'bars' });
    groups.forEach(function (g) {
      box.appendChild(barRow(g.name || g.group || '?', num(g.total), mx, 'you', money(g.total)));
    });
    return box;
  }
  // One "Demo receipts" tag in the card head instead of notes on every receipt (R6).
  function demoTag(c) {
    var head = c.querySelector('.card-titles');
    if (head) head.appendChild(h('span', { class: 'demo-pill', title: 'The receipt lines are simulated for this demo.' }, 'Demo receipts'));
  }
  function openReceiptSheet() {
    var body = openSheet('Read a receipt', { full: true });
    var ta = h('textarea', { class: 'input explain-text', id: 'rc-text', rows: '9', maxlength: '1900', placeholder: 'PRISMA\nKevytmaito 1 l   1,29\nBanaani   1,05\nYHTEENSÄ   2,34', autocomplete: 'off' });
    var go_ = h('button', { type: 'button', class: 'btn block' }, 'Read this receipt');
    body.appendChild(h('div', { class: 'form' },
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

  // ---------- chat card renderers (shapes: STATE.md 5.3) ----------
  var TARGETS = {
    night_out: 'Night out', Restaurant: 'Restaurants', 'Fast food': 'Fast food', Bar: 'Bars', Taxi: 'Taxis', Groceries: 'Groceries',
    regular: 'Regular essentials', unexpected: 'Unexpected necessities', everyday: 'Everyday spending'
  };
  function targetName(t) { return TARGETS[t] || String(t == null ? '' : t); }

  function benchNode(r) {
    var mx = Math.max(num(r.you), num(r.median), num(r.p75), 1);
    var pos = r.position;
    var posText = typeof pos === 'string' ? cap(pos) : (typeof pos === 'number' ? 'Higher than ' + Math.round(pos <= 1 ? pos * 100 : pos) + '% of the group' : '');
    return h('div', { class: 'bench' },
      h('div', { class: 'bench-head' }, h('b', null, r.name || r.metric), posText ? h('span', { class: 'tiny' }, posText) : null),
      barRow('You', num(r.you), mx, 'you'),
      barRow('Typical', num(r.median), mx, 'median'));
  }

  function fmtByUnit(v, unit) {
    if (v == null || !isFinite(Number(v))) return '-';
    v = Number(v);
    var d1 = (Math.round(v * 10) / 10).toFixed(1);
    switch (unit) {
      case 'eur_per_month': return money(v) + ' a month';
      case 'eur': return money(v);
      case 'count_per_month': return d1 + ' a month';
      case 'count_per_year': return d1 + ' a year';
      case 'share': return Math.round(v * 100) + '%';
      case 'months': return d1 + ' months';
      default: return d1;
    }
  }

  function avgRowNode(r) {
    var mx = Math.max(num(r.you), num(r.typical), 0.0001);
    return h('div', { class: 'bench' },
      h('div', { class: 'bench-head' }, h('b', null, r.name || r.metric || '')),
      barRow('You', num(r.you), mx, 'you', fmtByUnit(r.you, r.unit)),
      barRow('Typical', num(r.typical), mx, 'median', fmtByUnit(r.typical, r.unit)));
  }

  // Averages: the first comparison shows, the rest sit behind More.
  function averagesInto(c, d) {
    // A share row where nearly everyone takes part says nothing ("100% use taxis").
    var rows = (d.rows || []).filter(function (r) { return !(r.unit === 'share' && num(r.typical) >= 0.95 && num(r.you) >= 0.95); });
    if (!rows.length) { c.appendChild(h('p', { class: 'muted small' }, 'No comparison is available yet.')); return c; }
    var r0 = rows[0];
    var dir = String(r0.direction || '').toLowerCase();
    var verdict = /same|typical|line/.test(dir) ? 'About the same as most people like you'
      : /more|higher|above/.test(dir) ? 'More than most people like you'
        : /less|lower|below|fewer/.test(dir) ? 'Less than most people like you' : '';
    if (verdict) c.appendChild(h('p', { class: 'verdict-line' }, verdict));
    c.appendChild(avgRowNode(r0));
    var g = d.group || {};
    more(c, [rows.slice(1, 3).map(avgRowNode),
      g.description ? h('p', { class: 'tiny' }, ht(g.description) + (g.n ? ' (' + g.n + ' customers)' : '')) : null], d);
    return c;
  }

  function openDataNode(od) {
    if (!od || !od.rows || !od.rows.length) return null;
    var box = h('div', { class: 'open-data' });
    box.appendChild(eyebrow('Finland on average (Statistics Finland' + (od.year ? ', ' + od.year : '') + ')'));
    od.rows.forEach(function (r) {
      var mx = Math.max(num(r.you), num(r.national), 1);
      box.appendChild(h('div', { class: 'bench' },
        h('div', { class: 'bench-head' }, h('b', null, r.name), h('span', { class: 'tiny' }, 'a month')),
        barRow('You', num(r.you), mx, 'you'),
        barRow('Finland', num(r.national), mx, 'median')));
    });
    if (od.note) box.appendChild(h('p', { class: 'tiny' }, od.note));
    return box;
  }

  function areaValue(r) {
    var v = r.value, u = String(r.unit || '');
    if (v == null || v === '') return '-';
    if (/eur/i.test(u)) return euros(v) + (/year/i.test(u) ? ' a year' : (/month/i.test(u) ? ' a month' : ''));
    if (u === 'share') return Math.round(num(v) <= 1 ? num(v) * 100 : num(v)) + '%';
    if (u === '%' || /percent/i.test(u)) return round1(v) + '%';
    if (u === 'm2') return round1(v) + ' m²';
    return String(v) + (u ? ' ' + u : '');
  }

  function traitValue(tr) {
    if (/percent/i.test(String(tr.note || ''))) return round1(tr.value) + '%';
    return String(tr.value);
  }

  var CARDS = {
    help: function (d) {
      var c = cardShell('Things to ask');
      (d.groups || []).slice(0, 6).forEach(function (g) {
        var chips = h('div', { class: 'chips' });
        (g.items || []).slice(0, 4).forEach(function (it) {
          var q = it && (it.question || it.q);
          if (!q) return;
          chips.appendChild(h('button', { type: 'button', class: 'chip', onclick: function () { if (chat) chat.ask(q); } }, it.label || q));
        });
        if (chips.childNodes.length) { c.appendChild(eyebrow(g.title || '')); c.appendChild(chips); }
      });
      c.appendChild(h('button', { type: 'button', class: 'link-btn', 'aria-haspopup': 'dialog', onclick: function () { openAsk(); } }, 'See everything I can do'));
      return c;
    },
    // Shown as the "Saved to Your things" chip only, never as a card.
    goal_saved: function (d) {
      thingsChanged();
      return thingChip({ id: 'goal', kind: 'goal', title: d.name || 'Savings goal' });
    },
    receipts: function (d) {
      var c = cardShell('Your receipts', d.period ? fmtPeriod(d.period) : '');
      demoTag(c);
      var list = d.receipts || [];
      if (!list.length) { c.appendChild(h('p', { class: 'small muted' }, 'No receipts in this period.')); return c; }
      var box = h('div', { class: 'rc-list' });
      list.slice(0, 3).forEach(function (r) { box.appendChild(receiptNode(r)); });
      c.appendChild(box);
      var rest = list.slice(3).map(receiptNode);
      more(c, [rest.length ? h('div', { class: 'rc-list' }, rest) : null,
        rowsNode([
          d.grocery_total != null && num(d.fuel_total) > 0 ? ['Groceries', money(d.grocery_total)] : null,
          d.fuel_total != null && num(d.fuel_total) > 0 ? ['Fuel', money(d.fuel_total)] : null,
          ['In total', money(d.total)]
        ])]);
      return c;
    },
    receipt_insights: function (d) {
      var c = cardShell('What you buy', d.period ? fmtPeriod(d.period) : '');
      demoTag(c);
      var groups = (d.by_group || []).filter(function (g) { return num(g.total) > 0; });
      var top = (d.top_products || []);
      var tr = d.treats || {};
      var g0 = groups.filter(function (g) { return !/^other/i.test(String(g.group || g.name)); })[0];
      addRows(c, [
        top[0] ? ['Most often', (top[0].name || 'Item') + ' (' + plural(num(top[0].times), 'time', 'times') + ')'] : null,
        g0 ? ['Biggest group', g0.name + (g0.share != null ? ', ' + Math.round(num(g0.share) * 100) + '%' : '')] : null,
        tr.monthly != null ? ['Treats', money(tr.monthly) + ' a month'] : null
      ]);
      var f = d.fuel;
      more(c, [
        groups.length ? [eyebrow('By product group'), groupBars(groups, 8)] : null,
        top.length > 1 ? [eyebrow('Also bought often'), rowsNode(top.slice(1, 5).map(function (p) {
          return [p.name || 'Item', plural(num(p.times), 'time', 'times') + ', ' + money(p.total)];
        }))] : null,
        f && num(f.total) > 0 ? [eyebrow('Fuel'), rowsNode([['Spent', money(f.total)],
          f.litres != null ? ['Litres', String(Math.round(num(f.litres)))] : null,
          f.avg_price_per_litre != null ? ['A litre on average', money(f.avg_price_per_litre)] : null])] : null
      ]);
      return c;
    },
    product_habit: function (d) {
      var m = d.matched;
      var c = cardShell(m && m.name ? cap(m.name) : 'From your receipts', m && d.period ? fmtPeriod(d.period) : '');
      demoTag(c);
      if (!m || !num(d.times)) return null;   // the reply already says it was not found
      addRows(c, [['Bought', plural(num(d.times), 'time', 'times')], ['Spent', money(d.total)], ['A year at this pace', euros(d.yearly)]]);
      var rw = (d.receipts_with_it || []);
      more(c, [rowsNode([d.per_purchase != null ? ['Each time', money(d.per_purchase)] : null]),
        rw.length ? [eyebrow('On these receipts'), rowsNode(rw.slice(0, 6).map(function (r) { return [(r.store || 'Receipt') + (r.d ? ', ' + fmtDate(r.d) : ''), money(r.total != null ? r.total : r.line_total)]; }))] : null]);
      return c;
    },
    receipt_parsed: function (d) {
      var c = cardShell(d.store || 'Your receipt', d.date ? fmtDate(d.date) : '');
      keyFig(c, money(d.total != null ? d.total : d.lines_total), plural((d.lines || []).length, 'line', 'lines'));
      var g0 = (d.by_group || []).filter(function (g) { return num(g.total) > 0 && !/^other/i.test(String(g.group || g.name)); })[0];
      addRows(c, [g0 ? ['Biggest group', g0.name + ', ' + money(g0.total)] : null]);
      if (d.matches_total === false && d.lines_total != null) {
        c.appendChild(h('p', { class: 'notice' }, 'The lines add up to ' + money(d.lines_total) + ', not the receipt total.'));
      }
      var un = (d.unparsed || []).length;
      more(c, [
        receiptLines(d.lines),
        (d.by_group || []).length ? [eyebrow('By product group'), groupBars(d.by_group, 6)] : null,
        un ? h('p', { class: 'tiny' }, plural(un, 'line', 'lines') + ' could not be read as a product.') : null
      ]);
      return c;
    },
    spend: function (d) {
      var c = cardShell('Spending', d.period ? fmtRange(d.period) : '');
      keyFig(c, money(d.total), plural(num(d.count), 'payment', 'payments'));
      var labels = (d.by_label || []).filter(function (x) { return num(x.total) > 0; });
      var np = d.night_out_part;
      more(c, [labels.length > 1 ? labelBars(labels.slice(0, 8), maxOf(labels)) : null, peerBlock(d),
        np && num(np.total) > 0 ? h('p', { class: 'small' }, 'Of this, ' + money(np.total) + ' was on nights out.') : null], d);
      return c;
    },
    overview: function (d) {
      var c = cardShell('Your month', d.month ? fmtMonth(d.month) : '');
      keyFig(c, money(d.surplus), num(d.surplus) >= 0 ? 'left over' : 'more out than in');
      addRows(c, [['Money in', money(d.income)], ['Spent', money(d.spent)]]);
      var b = d.baskets || {};
      var keys = ['regular', 'unexpected', 'everyday'];
      var bmx = Math.max.apply(null, keys.map(function (k) { return num(b[k]); }).concat([1]));
      var bars = h('div', { class: 'bars' }, keys.map(function (k) { return barRow(BASKET_NAMES[k], num(b[k]), bmx, 'b-' + k); }));
      var tl = (d.top_labels || []).slice(0, 3);
      more(c, [eyebrow('By basket'), bars, tl.length ? [eyebrow('Biggest areas'), labelBars(tl, maxOf(tl))] : null]);
      return c;
    },
    baskets: function (d) {
      var c = cardShell('Three baskets', d.period ? fmtRange(d.period) : '');
      var parts = basketsParts(d);
      c.appendChild(parts.main);
      more(c, parts.more);
      return c;
    },
    safe_to_spend: function (d) {
      var st = STATUS_TEXT[d.status] ? d.status : 'ok';
      var shortNow = num(d.safe_total) < 0 || num(d.per_day) < 0;
      var c = cardShell('Safe to spend', shortNow ? 'Short until payday' : STATUS_TEXT[st]);
      if (shortNow) {
        keyFig(c, '€0', 'safe to spend before payday', 'warn');
        addRows(c, [['Short by about', euros(Math.abs(num(d.safe_total)))], d.next_payday ? ['Next payday', fmtDate(d.next_payday)] : null]);
      } else {
        keyFig(c, euros(d.per_week), 'this week');
        addRows(c, [['A day', money(d.per_day, { hero: true })], d.next_payday ? ['Next payday', fmtDate(d.next_payday) + (d.days_left != null ? ', in ' + plural(num(d.days_left), 'day', 'days') : '')] : null]);
      }
      var bills = d.upcoming_bills || [];
      more(c, [eyebrow('How it is worked out'), rowsNode([
        ['Money in your account', money(d.balance)],
        ['Bills before payday', '-' + money(d.bills_total)],
        ['Buffer for surprises', '-' + money(d.unexpected_buffer)],
        num(d.planned_savings) > 0 ? ['Planned savings', '-' + money(d.planned_savings)] : null,
        ['Safe to spend', money(d.safe_total)]
      ]), bills.length ? [eyebrow('Bills before payday'), rowsNode(bills.map(function (b) { return [(b.label || 'Bill') + (b.due ? ', ' + fmtDate(b.due) : ''), money(b.expected)]; }))] : null], d);
      return c;
    },
    what_if: function (d) {
      var months = num(d.months) || 12;
      if (d.direction === 'increase' || num(d.saved_monthly) < 0) {
        var ci = cardShell('If you spent more');
        keyFig(ci, euros(-num(d.saved_monthly) * 12), 'extra a year');
        addRows(ci, [['A month', money(-num(d.saved_monthly)) + ' more'], ['Spending a month', euros(d.baseline_monthly) + ' to ' + euros(d.new_monthly)]]);
        more(ci, [rowsNode((d.lines || []).map(function (l) { return [targetName(l.target), euros(l.baseline) + ' to ' + euros(l.new) + ' a month']; }))], d);
        return ci;
      }
      var c = cardShell('If you spent less');
      keyFig(c, euros(d.saved_monthly * 12), 'saved a year');
      var lines = d.lines || [];
      addRows(c, [['A month', money(d.saved_monthly)], ['Spending a month', euros(d.baseline_monthly) + ' to ' + euros(d.new_monthly)]]);
      more(c, [rowsNode(lines.map(function (l) { return [targetName(l.target), euros(l.baseline) + ' to ' + euros(l.new) + ' a month']; })),
        months !== 12 ? h('p', { class: 'small' }, money(d.saved_total) + ' over ' + months + ' months.') : null], d);
      return c;
    },
    spender_type: function (d) {
      var c = cardShell('Your spender type');
      var title = String(d.title || '');
      var why = title.indexOf(':') > 0 ? cap(title.slice(title.indexOf(':') + 1).trim()) : '';
      keyFig(c, d.type || title, why);
      var traits = d.traits || [];
      // each trait is a share of income; the three biggest are shown, the rest sit behind More
      var rows = traits.map(function (tr) { return [tr.note || tr.name, round1(tr.value) + '% of income']; });
      addRows(c, rows.slice(0, 3));
      more(c, [rows.length > 3 ? rowsNode(rows.slice(3)) : null, explainNode(d)], d);
      return c;
    },
    save_more: function (d) {
      var c = cardShell('Ways to save more');
      var ideas = d.ideas || [];
      addRows(c, ideas.slice(0, 3).map(function (i) { return [i.title, i.saved_monthly != null ? money(i.saved_monthly) + ' a month' : '']; }));
      more(c, [ideas.map(function (i) { return h('div', { class: 'idea' }, h('b', null, i.title), para(i.detail)); })], d);
      return c;
    },
    mortgage: function (d) {
      var c = cardShell('Mortgage readiness', 'Not a decision');
      keyFig(c, euros(d.max_loan), 'possible loan');
      addRows(c, [['Home price with 15% down', euros(d.max_price_with_15pct_equity)], ['Your own money needed', euros(d.equity_needed)]]);
      var k = d.check;
      more(c, [
        rowsNode([['Money in your account', euros(d.account_balance != null ? d.account_balance : d.savings_now)]]),
        d.months_to_equity != null ? h('p', { class: 'small' }, num(d.months_to_equity) > 120
          ? 'At ' + money(d.monthly_saving) + ' a month, saving the ' + euros(d.equity_needed) + ' would take over 10 years.'
          : 'At ' + money(d.monthly_saving) + ' a month, saving the ' + euros(d.equity_needed) + ' takes about ' + plural(Math.ceil(num(d.months_to_equity)), 'month', 'months') + '.') : null,
        k ? h('p', { class: 'small' }, 'For a ' + euros(k.price) + ' home: loan ' + euros(k.loan) + ', loan-to-value ' + pct(num(k.ltv) <= 1 ? num(k.ltv) * 100 : k.ltv) + '. Income ' + (k.income_ok ? 'looks enough' : 'looks too low') + ', down payment ' + (k.equity_ok ? 'looks enough' : 'looks too low') + '.') : null,
        para(d.rule, 'explain'),
        d.disclaimer ? h('p', { class: 'disclaimer' }, d.disclaimer) : null
      ], d);
      return c;
    },
    benchmarks: function (d) {
      var g = d.group || {};
      var c = cardShell('You and people like you', g.n ? g.n + ' people' : '');
      var rows = d.rows || [];
      if (!rows.length) c.appendChild(h('p', { class: 'muted small' }, 'No comparison is available yet.'));
      rows.slice(0, 3).forEach(function (r) { c.appendChild(benchNode(r)); });
      more(c, [rows.slice(3).map(benchNode), g.description ? h('p', { class: 'tiny' }, g.description) : null, openDataNode(d.open_data)], d);
      return c;
    },
    averages: function (d) {
      var g = d.group || {};
      var c = cardShell(d.title || 'What is typical?', g.n ? g.n + ' people' : '');
      return averagesInto(c, d);
    },
    invest: function (d) {
      var c = cardShell('Investing basics', 'Education only');
      if (d.buffer_months != null) keyFig(c, round1(d.buffer_months) + ' months', 'of costs in your account. 3–6 months is a common aim.', d.buffer_ok ? '' : 'warn');
      if (d.buffer_ok === false) addRows(c, [['Next step', 'Build the buffer first']]);
      var pts = (d.points || []).map(String).slice(1);
      more(c, [pts.length ? h('ul', { class: 'plain-list' }, pts.map(function (p) { return h('li', null, p); })) : null,
        d.disclaimer ? h('p', { class: 'disclaimer' }, d.disclaimer) : null], d);
      return c;
    },
    goal: function (d) {
      var c = cardShell('Savings goal');
      keyFig(c, d.months != null ? plural(Math.ceil(num(d.months)), 'month', 'months') : 'Not reachable yet', d.months != null ? 'to go' : '');
      addRows(c, [d.monthly != null ? ['Saving a month', money(d.monthly)] : null, d.date ? ['Around', fmtMonth(String(d.date).slice(0, 7))] : null]);
      return more(c, [], d);
    },
    transactions: function (d) {
      var c = cardShell('Transactions', plural(num(d.count), 'found', 'found'));
      var rows = (d.rows || []).slice(0, 5);
      c.appendChild(txList({ rows: rows }, { bare: true }));
      var rest = (d.rows || []).slice(5);
      if (rest.length) more(c, [txList({ rows: rest }, { bare: true })]);
      return c;
    },
    table: function (d) {
      var c = cardShell(d.title ? cap(String(d.title)) : 'Results');
      var cols = d.columns || [];
      var rows = d.rows || [];
      var HEAD = { d: 'Date', date: 'Date', ts: 'Date', label: 'What', display_label: 'What', category: 'What', amount: 'Amount', total: 'Amount', spent: 'Amount', count: 'Count', merchant: 'Where' };
      var thead = h('tr');
      cols.forEach(function (col) {
        var k = String(col);
        thead.appendChild(h('th', { scope: 'col' }, HEAD[k.toLowerCase()] || cap(k.replace(/_/g, ' '))));
      });
      var tbody = h('tbody');
      rows.forEach(function (r) {
        var tr = h('tr');
        cols.forEach(function (col, i) {
          var v = Array.isArray(r) ? r[i] : (r && r[col]);
          var lc = String(col).toLowerCase();
          var txt = v == null ? '' : String(v);
          if (/^\d{4}-\d{2}-\d{2}/.test(txt)) txt = fmtDate(txt);
          else if (/amount|total|spent|sum/.test(lc) && isFinite(Number(v)) && v !== '') txt = money(Math.abs(Number(v)));
          tr.appendChild(h('td', { class: /amount|total|spent|sum|count/.test(lc) ? 'num' : null }, txt));
        });
        tbody.appendChild(tr);
      });
      c.appendChild(h('div', { class: 'table-wrap', tabindex: '0', role: 'region', 'aria-label': 'Table' }, h('table', { class: 'data' }, h('thead', null, thead), tbody)));
      if (d.truncated) c.appendChild(h('p', { class: 'tiny' }, 'Showing the first rows only.'));
      return c;
    },
    afford: function (d) {
      var c = cardShell('Can I afford it?', d.item ? cap(String(d.item)) + (d.price != null ? ', ' + money(d.price) : '') : '');
      return affordInto(c, d);
    },
    leaks: function (d) {
      var c = cardShell('Small leaks', d.period ? fmtPeriod(d.period) : '');
      var sm = d.small || {};
      var thr = sm.threshold != null ? sm.threshold : 10;
      keyFig(c, money(sm.per_month != null ? sm.per_month : sm.total), (sm.per_month != null ? 'a month' : 'in total') + ' on purchases under ' + euros(thr));
      var tops = (sm.top_labels || []).map(function (x) { return typeof x === 'string' ? x : (x && (x.label || x.name)); }).filter(Boolean);
      var subs = d.subscriptions || [];
      addRows(c, [['Forgotten subscriptions', subs.length ? plural(subs.length, 'repeating charge', 'repeating charges') : 'None found']]);
      var wd = d.by_weekday || [], hr = d.by_hour || [];
      more(c, [
        rowsNode([['Small buys', String(num(sm.count))], tops.length ? ['Mostly', tops.slice(0, 3).join(', ').toLowerCase()] : null]),
        wd.length ? [eyebrow('By weekday'), colChart(wd, function (x) { return x.day; }, function (x) { return x.total; },
          function (x) { return x.day + ': ' + money(x.total) + ', ' + plural(num(x.count), 'purchase', 'purchases'); }, false, 'Everyday spending by weekday')] : null,
        hr.length ? [eyebrow('By hour of the day'), colChart(hr, function (x) { return (x.hour % 6 === 0) ? String(x.hour) : ''; }, function (x) { return x.total; },
          function (x) { return x.hour + ':00: ' + money(x.total); }, true, 'Everyday spending by hour of the day')] : null,
        d.peak && d.peak.text ? para(d.peak.text) : null,
        d.payday_week && d.payday_week.text ? para(d.payday_week.text) : null,
        subs.length ? [eyebrow('Repeating charges'), rowsNode(subs.map(function (s) { return [s.label || 'Repeating charge', money(s.amount) + ' a month']; }))] : null
      ], d);
      return c;
    },
    money_proposal: function (d) {
      if (d.refused || !d.proposal) {
        var c0 = cardShell('Move money');
        c0.appendChild(h('p', { class: 'notice' }, ht(d.message || 'That move is not possible.')));
        return c0;
      }
      return moneyProposalCard(d.proposal);
    },
    money_holdings: function (d) {
      var c = cardShell('Savings and investments', 'In S-mobiili');
      var held = d.holdings || [];
      if (held.length) addRows(c, held.map(function (x) { return [x.name, money(x.amount)]; }));
      else c.appendChild(h('p', { class: 'small muted' }, 'Nothing moved yet.'));
      var out = h('div', { 'aria-live': 'polite' });
      more(c, [moneyMoveForm(out, d.destinations, d.available_to_move), out]);
      return c;
    },
    alerts: function (d) {
      var c = cardShell('Worth a look');
      var list = (d.alerts || []).slice(0, 5);
      if (!list.length) { c.appendChild(h('p', { class: 'small muted' }, 'Nothing unusual this month.')); return c; }
      c.appendChild(h('ul', { class: 'alert-list' }, list.slice(0, 3).map(function (a) {
        return h('li', { class: 'alert-row' + (a.severity === 'notice' ? ' warn' : '') }, ht(a.title) || 'Something to look at');
      })));
      more(c, list.map(function (a, i) {
        return h('div', { class: 'idea' }, i >= 3 ? h('b', null, ht(a.title)) : null, a.detail ? para(a.detail) : null, evidenceLink(a.evidence, a.title));
      }));
      return c;
    },
    savings_leak: function (d) {
      var c = cardShell('Your savings', d.flag === false ? 'No pattern found' : '');
      var ws = d.withdrawals || [];
      if (ws.length) {
        keyFig(c, String(ws.length), ws.length === 1 ? 'withdrawal from savings' : 'withdrawals from savings');
        addRows(c, ws.slice(0, 3).map(function (w) { return [fmtDate(w.d), money(w.amount)]; }));
      } else {
        c.appendChild(h('p', { class: 'small muted' }, 'No withdrawals from savings found.'));
      }
      more(c, [ws.map(function (w) {
        var extra = [];
        if (w.days_before_payday != null) extra.push(num(w.days_before_payday) + ' days before payday');
        if (w.balance_before != null) extra.push('balance before ' + money(w.balance_before));
        return extra.length ? h('p', { class: 'tiny' }, fmtDate(w.d) + ': ' + extra.join(', ')) : null;
      })], d, 'Investment withdrawals');
      return c;
    },
    challenge: function (d) {
      var c = cardShell('Weekly challenge');
      var inner = h('div');
      c.appendChild(inner);
      function fill(data, accepted) {
        inner.replaceChildren(challengeBody(data, fill));
        if (accepted && data && data.active) inner.appendChild(thingChip({ id: 'challenge', kind: 'challenge', title: data.active.title || 'Your challenge' }));
      }
      fill(d);
      return c;
    },
    quiz_stats: function (d) {
      return quizStatsInto(cardShell('Your guessing'), d);
    },
    forecast: function (d) {
      var c = cardShell('Until payday');
      var ev = [];
      (d.points || []).forEach(function (p) { (p.events || []).forEach(function (e) { ev.push({ d: p.d, label: e.label, amount: e.amount }); }); });
      var low = d.lowest && d.lowest.d ? d.lowest : null;
      if (!low && (d.points || []).length) {
        d.points.forEach(function (p) { if (!low || num(p.balance) < num(low.balance)) low = { d: p.d, balance: p.balance }; });
      }
      if (low) keyFig(c, euros(low.balance), 'lowest balance, ' + fmtDate(low.d), num(low.balance) < 0 ? 'warn' : '');
      addRows(c, [d.to ? ['Payday', fmtDate(d.to)] : null, low ? ['Goes below zero', num(low.balance) < 0 ? 'Yes' : 'No'] : null]);
      more(c, [forecastChart(d), explainNode(d),
        ev.length ? [eyebrow('Bills on the way'), rowsNode(ev.map(function (e) { return [fmtDate(e.d) + ', ' + (e.label || 'Bill'), money(e.amount)]; }))] : null], d, 'Where this comes from');
      return c;
    },
    payday_plan: function (d) {
      var c = cardShell('Your payday plan', d.next_payday ? fmtDate(d.next_payday) : '');
      var lines = d.lines || [];
      var total = lines.reduce(function (s, l) { return s + Math.max(0, num(l.amount)); }, 0);
      if (lines.length && total > 0) {
        var stack = h('div', { class: 'stack', role: 'img', 'aria-label': 'Suggested split of your next salary' });
        lines.forEach(function (l) {
          var seg = h('span', { class: 'b-' + (BASKET_NAMES[l.key] ? l.key : 'other') });
          seg.style.width = (Math.max(0, num(l.amount)) / total * 100) + '%';
          stack.appendChild(seg);
        });
        c.appendChild(stack);
      }
      c.appendChild(h('div', { class: 'legend' }, lines.map(function (l) {
        var k = BASKET_NAMES[l.key] ? l.key : 'other';
        return h('div', { class: 'legend-item' }, h('span', { class: 'dot b-' + k, 'aria-hidden': 'true' }),
          h('span', { class: 'legend-name' }, l.name || BASKET_NAMES[k] || l.key), h('b', null, euros(l.amount)));
      })));
      var g = d.goal_line;
      more(c, [
        rowsNode(lines.filter(function (l) { return l.why; }).map(function (l) { return [l.name || l.key, ht(l.why)]; })),
        d.everyday_per_week != null ? h('p', { class: 'small' }, 'Everyday spending: ' + money(d.everyday_per_week) + ' a week' + (d.everyday_per_day != null ? ', ' + money(d.everyday_per_day) + ' a day.' : '.')) : null,
        g && g.name ? h('p', { class: 'small' }, 'Towards ' + g.name + ': ' + money(g.amount) + ' a month' + (g.months_to_goal != null ? ', about ' + Math.ceil(num(g.months_to_goal)) + ' months to go.' : '.')) : null,
        h('p', { class: 'tiny' }, 'This is a plan. Nothing is transferred.')
      ], d);
      return c;
    },
    area: function (d) {
      var c = cardShell('Your area', d.area_name || '');
      var rows = (d.rows || []).filter(function (r) { return r.key !== 'average_income'; });
      var byKey = {};
      rows.forEach(function (r) { byKey[r.key] = r; });
      var med = byKey.median_income;
      var rent = rows.filter(function (r) { return /rent/i.test(String(r.key)); })[0];
      var own = byKey.owner_occupied_share;
      var first = [];
      var mine = (d.compare || []).filter(function (x) { return x && /income/i.test(String(x.name)) && x.you != null; })[0];
      if (med) first.push(['Typical income here', euros(num(med.value) / 12) + ' a month']);
      if (mine) first.push(['Yours', euros(mine.you) + ' a month']);
      if (rent) first.push(['Rented homes', areaValue(rent)]);
      else if (own && own.value != null) first.push(['Rented homes', Math.round(100 - (num(own.value) <= 1 ? num(own.value) * 100 : num(own.value))) + '%']);
      if (!first.length) first = rows.slice(0, 2).map(function (r) { return [r.name || r.key, areaValue(r)]; });
      addRows(c, first);
      var used = [med, rent, own];
      more(c, [
        rowsNode(rows.filter(function (r) { return used.indexOf(r) < 0; }).map(function (r) { return [r.name || r.key, areaValue(r)]; })),
        para(d.note, 'tiny'),
        rows.length ? h('p', { class: 'tiny' }, 'Source: Statistics Finland, Paavo' + (d.year ? ' (' + d.year + ')' : '') + '.') : null
      ], d);
      return c;
    },
    explain: function (d) { return explainCard(d); },
    purchase: function (d) {
      var tx = d.tx || {};
      var c = cardShell('Latest purchase', tx.d ? fmtDate(tx.d) : '');
      keyFig(c, money(Math.abs(num(tx.amount)), { exact: true }), String(tx.display_label || tx.label || ''));
      var hb = d.habit;
      if (hb && hb.yearly != null) addRows(c, [['A year at this pace', euros(hb.yearly)]]);
      var eq = (d.equivalents || []).filter(function (x) { return typeof x === 'string' && x; });
      more(c, [eq.map(function (x) { return para(x); }), hb && hb.avg_amount != null ? rowsNode([['Each time, on average', money(hb.avg_amount)]]) : null], d, 'Where this comes from');
      return c;
    },
    patterns: function (d) {
      var list = (d && d.patterns) || [];
      if (!list.length) return null;
      var c = cardShell('Spending patterns');
      list.slice(0, 3).forEach(function (p) {
        c.appendChild(h('div', { class: 'idea' },
          h('div', { class: 'idea-head' }, h('b', null, ht(p.title) || 'A pattern'), p.uplift_pct != null ? h('span', { class: 'pill' }, '+' + Math.round(num(p.uplift_pct)) + '%') : null),
          para(p.text)));
      });
      more(c, list.slice(0, 3).map(function (p) {
        var why = (p.why || []).filter(function (x) { return typeof x === 'string' && x; });
        return why.length || evidenceList(p.evidence).length ? h('div', { class: 'idea' }, h('b', null, ht(p.title)),
          why.length ? h('ul', { class: 'plain-list' }, why.map(function (x) { return h('li', null, ht(x)); })) : null,
          evidenceLink(p.evidence, p.title)) : null;
      }));
      return c;
    },
    goal_plan: function (d) {
      var needs = Array.isArray(d.needs) ? d.needs : [];
      if (needs.length || d.monthly_needed == null) return null;   // the reply asks for what is missing
      var c = cardShell('Goal plan', d.name ? String(d.name) : '');
      var months = Math.max(0, Math.ceil(num(d.months_left)));
      keyFig(c, euros(Math.ceil(num(d.monthly_needed))), 'a month for ' + plural(months, 'month', 'months'));
      addRows(c, [['Goal', euros(d.target) + (d.deadline ? ' by ' + deadlineText(d.deadline) : '')]]);
      var g = d.goal;
      if (g && g.name && num(g.target) > 0) {
        var msg = h('div', { 'aria-live': 'polite' });
        var save = h('button', { type: 'button', class: 'btn block' }, 'Save as my goal');
        save.addEventListener('click', function () {
          save.disabled = true;
          msg.replaceChildren(loadingNode('Saving...'));
          api('/api/goal', { method: 'POST', body: { name: g.name, target: num(g.target), saved: num(g.saved) } }).then(function (r) {
            var ng = (r && r.goal) || g;
            msg.replaceChildren();
            save.replaceWith(thingChip({ id: 'goal', kind: 'goal', title: ng.name || g.name }));
            thingsChanged();
          }, function (e) {
            save.disabled = false;
            if (e.handled) return;
            msg.replaceChildren(errorNode(e));
          });
        });
        c.appendChild(save); c.appendChild(msg);
        // An old conversation: when this goal is saved already, show the chip instead of the button.
        api('/api/goal').then(function (r) {
          var cur = r && r.goal;
          if (cur && cur.name === g.name && num(cur.target) === num(g.target) && save.isConnected && !save.disabled) {
            save.replaceWith(thingChip({ id: 'goal', kind: 'goal', title: cur.name }));
          }
        }, function () {});
      }
      var ways = (d.ways || []).filter(function (w) { return w && w.title; });
      more(c, [
        rowsNode([['You save now', money(Math.max(0, num(d.current_monthly_saving))) + ' a month'],
          d.gap != null && num(d.gap) > 0 ? ['Still to find', euros(d.gap) + ' a month'] : null]),
        ways.length ? [eyebrow('Ways to close the gap'), rowsNode(ways.slice(0, 2).map(function (w) {
          return [ht(w.title), w.saved_monthly != null ? money(w.saved_monthly) + ' a month' : ''];
        }))] : null], d, 'Where this comes from');
      return c;
    },
    override: function (d) {
      var c = cardShell('Remembered');
      var id = d.override && d.override.id != null ? d.override.id : d.id;
      var msg = h('div', { 'aria-live': 'polite' });
      var row = h('div', { class: 'link-row' }, thingChip(LEARNED_THING));
      if (id != null) {
        var undo = h('button', { type: 'button', class: 'link-btn quiet' }, 'Undo');
        undo.addEventListener('click', function () {
          undo.disabled = true;
          api('/api/overrides/remove', { method: 'POST', body: { id: id } }).then(function () {
            row.remove();
            msg.replaceChildren(h('p', { class: 'notice ok', role: 'status' }, 'Undone. I have forgotten that.'));
            thingsChanged();
          }, function (e) {
            undo.disabled = false;
            if (!e.handled) msg.replaceChildren(errorNode(e));
          });
        });
        row.appendChild(undo);
      }
      c.appendChild(row);
      c.appendChild(msg);
      return c;
    }
  };

  // Cards that can be kept under "Your things". The others are things already, or tools.
  var NOT_KEEPABLE = { help: 1, override: 1, challenge: 1, goal_plan: 1, goal_saved: 1, quiz_stats: 1, money_proposal: 1 };

  function renderChatCard(c) {
    if (!c || typeof c !== 'object') return null;
    var fn = CARDS[c.type];
    var d = c.data || {};
    if (!fn) return null;
    // Nothing was spent: the sentence already says so, an empty card adds nothing.
    if (c.type === 'spend' && !num(d.total) && !num(d.count)) return null;
    if (!d.evidence && c.evidence) d = Object.assign({}, d, { evidence: c.evidence });
    return fn(d);
  }

  function cardTitleOf(node) {
    var t = node.querySelector('.card-title');
    var s = node.querySelector('.card-sub');
    // Keep a period or date ("August", "15 Oct") in the title, but not a status word ("On track").
    return (t ? t.textContent : 'Answer') + (s && /\d|January|February|March|April|May|June|July|August|September|October|November|December/.test(s.textContent) ? ', ' + s.textContent : '');
  }

  // "Keep": pins one answer card under Your things.
  function addKeep(node, c, after) {
    var head = node.querySelector('.card-head');
    if (!head) return;
    var title = cardTitleOf(node).slice(0, 80);
    var b = h('button', { type: 'button', class: 'keep-btn', 'aria-label': 'Keep in Your things: ' + title }, icon('pin', 16), h('span', null, 'Keep'));
    b.addEventListener('click', function () {
      b.disabled = true;
      var data = c.data || {};
      if (!data.evidence && c.evidence) data = Object.assign({}, data, { evidence: c.evidence });
      api('/api/pins', { method: 'POST', body: { title: title, card: { type: c.type, data: data } } }).then(function (r) {
        b.replaceWith(h('span', { class: 'kept-tag' }, icon('pin', 16), 'Kept'));
        var chip = thingChip({ id: r && r.id, kind: 'pin', title: (r && r.title) || title });
        if (after && after.parentNode) after.parentNode.insertBefore(chip, after.nextSibling);
        thingsChanged();
      }, function (e) {
        b.disabled = false;
        if (e.handled) return;
        var note = h('p', { class: 'notice err', role: 'alert' }, e.status === 404 ? 'Keeping answers is not available yet.' : e.message);
        node.appendChild(note);
        setTimeout(function () { note.remove(); }, 4000);
      });
    });
    head.appendChild(b);
  }

  // ---------- "Your things" ----------
  var KIND = {
    goal: { name: 'Savings goal', icon: 'flag' },
    challenge: { name: 'Challenge', icon: 'target' },
    target: { name: 'Saving target', icon: 'coin' },
    learned: { name: 'Learned categories', icon: 'tag' },
    quiz: { name: 'Quiz score', icon: 'help' },
    money: { name: 'Savings and investments', icon: 'coin' },
    note: { name: 'Note', icon: 'doc' },
    pin: { name: 'Kept answer', icon: 'pin' }
  };
  function kindOf(t) { return KIND[t && t.kind] || KIND[String(t && t.id || '').split(':')[0]] || KIND.pin; }

  // The compact "Saved to Your things" chip shown where a thing was made.
  function thingChip(thing, verb) {
    var k = kindOf(thing);
    return h('button', { type: 'button', class: 'thing-chip', onclick: function () { openThing(thing); } },
      icon(k.icon, 16), h('span', null, (verb || 'Saved to Your things') + ': ', h('b', null, thing.title || k.name)), icon('chev', 16));
  }

  // Opens one thing in a sheet where it can be changed or removed.
  function openThing(thing) {
    var k = kindOf(thing);
    var kind = thing.kind || String(thing.id || '').split(':')[0];
    var body = openSheet(kind === 'note' ? k.name : (thing.title || k.name));
    var t = token;
    var done = function () { closeSheet(); thingsChanged(); };
    if (kind === 'goal') goalThing(body, t, done);
    else if (kind === 'challenge') {
      load(body, t, function () { return api('/api/challenge'); }, function (d) {
        function fill(nd) { body.replaceChildren(challengeBody(nd, fill)); }
        fill(d);
      });
    } else if (kind === 'money') {
      load(body, t, function () { return api('/api/money'); }, function (m) {
        var box = h('div', { class: 'thing-body' });
        var held = m.holdings || [];
        box.appendChild(rowsNode(held.map(function (x) { return [x.name, money(x.amount)]; })) || h('p', { class: 'muted' }, 'Nothing moved yet.'));
        box.appendChild(h('p', { class: 'tiny' }, 'Demo: fund values do not change here. Money only moves after you approve it, and it stays in S-mobiili.'));
        var out = h('div', { 'aria-live': 'polite' });
        box.appendChild(eyebrow('Move more'));
        box.appendChild(moneyMoveForm(out, m.destinations, m.available));
        box.appendChild(out);
        body.appendChild(box);
      });
    } else if (kind === 'note') {
      // A note in the customer's own words; the coach is given it with every question until it is removed.
      var nb = h('div', { class: 'thing-body' });
      nb.appendChild(h('p', null, cap(thing.title || '')));
      nb.appendChild(h('p', { class: 'tiny' }, 'You asked me to remember this' + (thing.updated ? ' ' + humanWhen(thing.updated).replace(/^(Today|Yesterday) /, function (m, w) { return w.toLowerCase() + ' at '; }) : '') + '. I keep it in mind when I answer.'));
      var forget = h('button', { type: 'button', class: 'link-btn danger-link' }, icon('trash', 18), 'Forget this');
      forget.addEventListener('click', function () {
        forget.disabled = true;
        api('/api/notes/remove', { method: 'POST', body: { id: thing.id } }).then(done, function (e) {
          if (e.status === 404) { done(); return; }   // already gone
          forget.disabled = false;
          if (!e.handled) nb.appendChild(errorNode(e));
        });
      });
      nb.appendChild(forget);
      body.appendChild(nb);
    } else if (kind === 'target') targetThing(body, done);
    else if (kind === 'learned') learnedThing(body, t);
    else if (kind === 'quiz') {
      load(body, t, function () { return api('/api/quiz/stats'); }, function (s) {
        var box = h('div', { class: 'thing-body' });
        quizStatsInto(box, s);
        box.appendChild(h('button', { type: 'button', class: 'btn block', onclick: function () { closeSheet(); openConversation({ insert: 'quiz' }); } }, 'Play this week\'s quiz'));
        body.appendChild(box);
      });
    } else {
      load(body, t, function () { return api('/api/pin?id=' + encodeURIComponent(thing.id)); }, function (p) {
        var node = null;
        try { node = renderChatCard(p && p.card); } catch (e) { node = null; }
        if (p && p.created) body.appendChild(h('p', { class: 'tiny' }, 'Kept ' + humanWhen(p.created).replace(/^(Today|Yesterday) /, function (m, w) { return w.toLowerCase() + ' at '; }) + '. The figures are from that day.'));
        body.appendChild(node || h('p', { class: 'muted' }, 'This answer cannot be shown any more.'));
        var rm = h('button', { type: 'button', class: 'link-btn danger-link' }, icon('trash', 18), 'Remove from Your things');
        rm.addEventListener('click', function () {
          rm.disabled = true;
          api('/api/pins/remove', { method: 'POST', body: { id: thing.id } }).then(done, function (e) {
            if (e.status === 404) { done(); return; }   // already gone
            rm.disabled = false;
            if (!e.handled) body.appendChild(errorNode(e));
          });
        });
        body.appendChild(rm);
      });
    }
  }

  function goalThing(body, t, done) {
    load(body, t, function () { return api('/api/goal'); }, function (res) {
      var g = (res && res.goal) || null;
      if (!g) {
        body.appendChild(h('p', { class: 'muted' }, 'You have no savings goal right now. Tell me about one in a conversation, for example "I am saving for Japan in 2027".'));
        return;
      }
      var box = h('div', { class: 'thing-body' });
      var tg = num(g.target), sv = num(g.saved);
      keyFig(box, euros(sv) + ' of ' + euros(tg), 'saved so far');
      var fill = h('div', { class: 'prog-fill' });
      fill.style.width = (tg > 0 ? Math.min(100, sv / tg * 100) : 0) + '%';
      box.appendChild(h('div', { class: 'prog-track', role: 'img', 'aria-label': pct(tg > 0 ? sv / tg * 100 : 0) + ' of the goal' }, fill));
      // A goal planned with a date shows the date and what it needs each month.
      if (g.deadline) {
        addRows(box, [['By', fmtMonth(String(g.deadline).slice(0, 7))],
          num(g.monthly_needed) > 0 ? ['Needs about', euros(g.monthly_needed) + ' a month'] : null]);
      }
      var name = h('input', { type: 'text', class: 'input', id: 'goal-name', maxlength: '40', autocomplete: 'off' });
      var target = h('input', { type: 'number', class: 'input', id: 'goal-target', min: '0', step: '100', inputmode: 'decimal' });
      var saved = h('input', { type: 'number', class: 'input', id: 'goal-saved', min: '0', step: '50', inputmode: 'decimal' });
      name.value = g.name || ''; target.value = String(tg); saved.value = String(sv);
      var msg = h('p', { class: 'help', role: 'status', 'aria-live': 'polite' });
      var save = h('button', { type: 'button', class: 'btn block' }, 'Save changes');
      var clear = h('button', { type: 'button', class: 'link-btn danger-link' }, 'Remove goal');
      save.addEventListener('click', function () {
        var tv = Number(target.value), svv = Number(saved.value || 0);
        if (!name.value.trim()) { msg.textContent = 'Give your goal a name.'; return; }
        if (!isFinite(tv) || tv <= 0) { msg.textContent = 'Enter a target above zero.'; return; }
        if (!isFinite(svv) || svv < 0) { msg.textContent = 'Saved so far must be zero or more.'; return; }
        save.disabled = true; msg.textContent = 'Saving...';
        api('/api/goal', { method: 'POST', body: { name: name.value.trim(), target: tv, saved: svv } }).then(done, function (e) {
          save.disabled = false;
          if (!e.handled) msg.textContent = e.message;
        });
      });
      clear.addEventListener('click', function () {
        clear.disabled = true;
        api('/api/goal', { method: 'POST', body: { clear: true } }).then(done, function (e) {
          clear.disabled = false;
          if (!e.handled) msg.textContent = e.message;
        });
      });
      box.appendChild(h('div', { class: 'form-grid' },
        h('div', { class: 'wide' }, h('label', { for: 'goal-name' }, 'Name'), name),
        h('div', null, h('label', { for: 'goal-target' }, 'Target (€)'), target),
        h('div', null, h('label', { for: 'goal-saved' }, 'Saved so far (€)'), saved)));
      box.appendChild(save);
      box.appendChild(msg);
      box.appendChild(clear);
      box.appendChild(h('p', { class: 'tiny' }, 'Used to say what a purchase does to your goal. Nothing moves automatically.'));
      body.appendChild(box);
    });
  }

  function targetThing(body, done) {
    var box = h('div', { class: 'thing-body' });
    var cur = num(me && me.settings && me.settings.monthly_saving_target);
    keyFig(box, money(cur), 'set aside each month');
    var input = h('input', { type: 'number', class: 'input', id: 'save-target', min: '0', step: '10', inputmode: 'decimal' });
    input.value = String(cur);
    var msg = h('p', { class: 'help', role: 'status', 'aria-live': 'polite' });
    var save = h('button', { type: 'button', class: 'btn block' }, 'Save');
    var rm = h('button', { type: 'button', class: 'link-btn danger-link' }, 'Remove target');
    function put(v) {
      save.disabled = true; rm.disabled = true; msg.textContent = 'Saving...';
      saveSettings({ monthly_saving_target: v }).then(done, function (e) {
        save.disabled = false; rm.disabled = false;
        if (!e.handled) msg.textContent = e.message;
      });
    }
    save.addEventListener('click', function () {
      var v = Number(input.value);
      if (!isFinite(v) || v < 0) { msg.textContent = 'Enter zero or more.'; return; }
      put(v);
    });
    rm.addEventListener('click', function () { put(0); });
    box.appendChild(h('div', null, h('label', { for: 'save-target', class: 'field-label' }, 'Euros a month'), input));
    box.appendChild(save); box.appendChild(msg); box.appendChild(rm);
    box.appendChild(h('p', { class: 'tiny' }, 'Taken off first when I work out what is safe to spend. Nothing moves automatically.'));
    body.appendChild(box);
  }

  function overrideText(o) {
    var what = o.description ? String(o.description)
      : (o.scope === 'merchant' ? 'Every purchase from one merchant' : 'One purchase');
    return { what: what, to: (o.label || 'Other') + (o.context === 'night_out' ? ', night out' : '') };
  }

  function learnedThing(body, t) {
    function draw() {
      load(body, t, function () { return api('/api/overrides'); }, function (res) {
        var list = (res && res.overrides) || [];
        if (!list.length) {
          body.appendChild(h('p', { class: 'muted' }, 'Nothing learned yet. Tell me when a purchase is in the wrong category, for example "that kebab was lunch".'));
          thingsChanged();
          return;
        }
        var msg = h('div', { 'aria-live': 'polite' });
        var ul = h('ul', { class: 'learned-list' });
        list.forEach(function (o) {
          var tx = overrideText(o);
          var rm = h('button', { type: 'button', class: 'link-btn danger-link', 'aria-label': 'Forget: ' + tx.what + ' is ' + tx.to }, 'Forget');
          rm.addEventListener('click', function () {
            rm.disabled = true;
            api('/api/overrides/remove', { method: 'POST', body: { id: o.id } }).then(function () { draw(); thingsChanged(); }, function (e) {
              rm.disabled = false;
              if (!e.handled) msg.replaceChildren(errorNode(e));
            });
          });
          ul.appendChild(h('li', { class: 'learned' },
            h('span', { class: 'learned-text' }, h('span', { class: 'small' }, tx.what), h('b', null, tx.to)), rm));
        });
        body.appendChild(ul);
        body.appendChild(msg);
      });
    }
    draw();
  }

  // When the server has no /api/home yet, build the same list from the endpoints that exist.
  function fallbackHome() {
    function safe(p) { return p.then(function (x) { return x; }, function () { return null; }); }
    return Promise.all([safe(api('/api/goal')), safe(api('/api/challenge')), safe(api('/api/overrides')), safe(api('/api/quiz/stats'))]).then(function (r) {
      var things = [];
      var g = r[0] && r[0].goal;
      if (g) things.push({ id: 'goal', kind: 'goal', title: g.name || 'Savings goal', summary: euros(g.saved) + ' of ' + euros(g.target) });
      var ch = r[1] && r[1].active;
      if (ch) things.push({ id: 'challenge', kind: 'challenge', title: ch.title || 'Your challenge', summary: 'This week' });
      var tg = num(me && me.settings && me.settings.monthly_saving_target);
      if (tg > 0) things.push({ id: 'target', kind: 'target', title: 'Saving target', summary: money(tg) + ' a month' });
      var ov = (r[2] && r[2].overrides) || [];
      if (ov.length) things.push({ id: 'learned', kind: 'learned', title: 'What I have learned', summary: plural(ov.length, 'correction', 'corrections') });
      var qs = r[3];
      if (qs && num(qs.count)) things.push({ id: 'quiz', kind: 'quiz', title: 'Quiz score', summary: qs.awareness_score != null ? Math.round(num(qs.awareness_score)) + '/100' : plural(num(qs.count), 'answer', 'answers') });
      var convs = [];
      if (localConv && localConv.turns.length) convs.push({ id: null, local: true, title: localConv.title, updated: localConv.updated, turns: localConv.turns.length });
      return { name: me && me.name, things: things, conversations: convs };
    });
  }

  // ---------- HOME ----------
  // What Svinkki can do, shown on the start page. q: asked right away. act: a tool. fill: starts the sentence for you.
  var HOME_TOOLS = [
    { label: 'Can I afford it?', hint: 'Check before you buy', act: 'afford', icon: 'wallet' },
    { label: 'Where can I save?', hint: 'Ideas from your spending', q: 'How can I save more?', icon: 'coin' },
    { label: 'Analyse receipts', hint: 'Down to single products', q: 'What do I buy most?', icon: 'receipt' },
    { label: 'Plan a goal', hint: 'A trip, a home, a buffer', fill: 'I want to save for ', icon: 'target' },
    { label: 'Until payday', hint: 'Your balance day by day', q: 'Will I make it to payday?', icon: 'calendar' },
    { label: 'Explain a contract', hint: 'A loan or fund text', act: 'explain', icon: 'doc' }
  ];

  // A closed row on the start page that opens in place: title, one line of summary, the card inside.
  function fold(ico, title, summary, node) {
    var body = h('div', { class: 'fold-body' }, node);
    return h('details', { class: 'fold' },
      h('summary', null,
        h('span', { class: 'thing-ico' }, icon(ico, 20)),
        h('span', { class: 'thing-text' }, h('b', null, title), summary ? h('span', { class: 'tiny' }, summary) : null),
        h('span', { class: 'chev' }, icon('chev', 18))),
      body);
  }

  // The message box. onSend(text) gets the trimmed text.
  function composer(placeholder, label, onSend) {
    var input = h('textarea', { class: 'composer-text', rows: '1', maxlength: '2000', placeholder: placeholder, 'aria-label': label, autocomplete: 'off', enterkeyhint: 'send' });
    var send = h('button', { type: 'submit', class: 'send-btn', 'aria-label': 'Send' }, icon('send', 20));
    var form = h('form', { class: 'composer' }, input, send);
    var busy = false;
    function autosize() {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 120) + 'px';
      input.classList.toggle('tall', input.scrollHeight > 120);
    }
    function go() {
      var v = input.value.trim();
      if (!v || busy) return;
      input.value = '';
      autosize();
      onSend(v);
    }
    form.addEventListener('submit', function (e) { e.preventDefault(); go(); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); go(); }
    });
    input.addEventListener('input', autosize);
    return {
      el: form, input: input,
      setBusy: function (b) { busy = b; send.disabled = b; },
      set: function (v) { input.value = v; autosize(); input.focus(); }
    };
  }

  function sectionHead(title, extra) {
    return h('div', { class: 'sec-head' }, h('h2', null, title), extra || null);
  }

  function showHome() {
    mode = 'home';
    closeSheet();
    clearView();
    setChrome('home');
    var t = token;
    var first = firstName();
    var comp = composer('Ask Svinkki', 'Ask Svinkki a question', function (text) { openConversation({ message: text }); });
    var askLink = h('button', { type: 'button', class: 'link-btn ask-link', 'aria-haspopup': 'dialog', onclick: function () { openAsk(); } }, icon('help', 18), 'Everything I can do');
    var toolGrid = h('div', { class: 'tool-grid home-tools' }, HOME_TOOLS.map(function (it) {
      return h('button', { type: 'button', class: 'tool', onclick: function () {
        if (it.fill) { comp.set(it.fill); return; }
        openConversation({ entry: it });
      } },
        h('span', { class: 'tool-ico' }, icon(it.icon, 20)),
        h('span', { class: 'tool-text' }, h('b', null, it.label), h('span', { class: 'tool-hint' }, it.hint)));
    }));
    var toolsBox = h('div', { class: 'home-sec' }, sectionHead('I can help with'), toolGrid, askLink);
    var forYou = h('div', { class: 'for-you-cards', role: 'group', 'aria-label': 'Ready for you' });
    var thingsBox = h('div', { class: 'home-sec', hidden: true });
    var convBox = h('div', { class: 'home-sec' });
    var acctBox = h('div', { class: 'acct-slot' });
    var greetLine = h('p', { class: 'muted', 'aria-live': 'polite' }, 'Ask me anything about your money.');
    viewEl.appendChild(h('div', { class: 'home' },
      acctBox,
      h('div', { class: 'greet' }, h('h1', null, first ? 'Hi ' + first + '!' : 'Hi!'), greetLine),
      comp.el, toolsBox, forYou, convBox, thingsBox));
    api('/api/account').then(function (a) { if (alive(t) && a && a.current) acctBox.replaceChildren(accountCard(a)); }, function () {});

    // Ready for you: the check-in, this week's quiz and anything worth a look, each closed until tapped.
    var slots = { checkin: h('div'), quiz: h('div'), alerts: h('div') };
    forYou.appendChild(slots.checkin); forYou.appendChild(slots.quiz); forYou.appendChild(slots.alerts);
    function place(key, node) {
      if (!alive(t) || !node) return;
      slots[key].replaceChildren(node);
      if (!forYou.querySelector('.sec-head')) forYou.insertBefore(sectionHead('For you'), forYou.firstChild);
    }
    api('/api/checkin').then(function (r) {
      if (!(r && r.due && r.checkin)) return;
      var c = r.checkin, sur = num(c.surplus);
      var when = fmtPeriod(c.period);
      // One line that shows the coach has looked at this customer's own month.
      if (alive(t) && when && num(c.income) > 0) {
        greetLine.textContent = sur >= 0
          ? 'You kept ' + money(sur) + ' in ' + when + '. What shall we look at?'
          : 'In ' + when + ' ' + money(-sur) + ' more went out than came in. Shall we look at why?';
      }
      place('checkin', fold('calendar', 'Your check-in',
        (num(c.income) <= 0 ? money(c.spent) + ' spent' : (sur >= 0 ? money(sur) + ' left over' : money(-sur) + ' more out than in')) +
        (when ? ' · ' + when : ''), checkinCard(c)));
    }, function () {});
    api('/api/quiz').then(function (q) {
      if (q && q.quiz_id) place('quiz', fold('help', 'Weekly quiz', 'One guess about your own spending', quizCard(q)));
    }, function () {});
    api('/api/alerts').then(function (d) {
      var list = (d && Array.isArray(d.alerts)) ? d.alerts : [];
      if (list.length) place('alerts', fold('flag', 'Worth a look', plural(list.length, 'thing', 'things') + ' in your recent spending',
        CARDS.alerts({ alerts: list, explain: d.explain })));
    }, function () {});

    function render(d) {
      if (!alive(t)) return;
      d = d || {};
      var things = Array.isArray(d.things) ? d.things : [];
      thingsBox.replaceChildren(sectionHead('Your things'));
      thingsBox.hidden = !things.length;      // nothing to show yet: no empty box on the start page
      if (things.length) {
        var tl = h('div', { class: 'list-card' });
        things.forEach(function (th) {
          var k = kindOf(th);
          tl.appendChild(h('button', { type: 'button', class: 'thing-row', onclick: function () { openThing(th); } },
            h('span', { class: 'thing-ico' }, icon(k.icon, 20)),
            h('span', { class: 'thing-text' }, h('b', null, th.title || k.name), h('span', { class: 'tiny' },
              k.name + (th.kind === 'pin' && th.updated ? ' · ' + humanWhen(th.updated) : (th.summary ? ' · ' + ht(th.summary) : '')))),
            h('span', { class: 'chev' }, icon('chev', 18))));
        });
        thingsBox.appendChild(tl);
      }
      var convs = (Array.isArray(d.conversations) ? d.conversations : []).slice().sort(function (a, b) { return String(b.updated || '').localeCompare(String(a.updated || '')); });
      convBox.replaceChildren();
      if (convs.length) {
        convBox.appendChild(sectionHead('Conversations'));
        var cl = h('div', { class: 'list-card' });
        var SHOW = 4;
        convs.forEach(function (cv, i) {
          var row = convRow(cv);
          if (i >= SHOW) row.hidden = true;
          cl.appendChild(row);
        });
        convBox.appendChild(cl);
        if (convs.length > SHOW) {
          var all = h('button', { type: 'button', class: 'link-btn' }, 'Show all (' + convs.length + ')');
          all.addEventListener('click', function () {
            Array.prototype.forEach.call(cl.children, function (r) { r.hidden = false; });
            all.remove();
          });
          convBox.appendChild(all);
        }
      }
    }

    api('/api/home').then(function (d) { convApi = true; render(d); }, function (e) {
      if (e && e.handled) return;
      fallbackHome().then(render);
    });
  }

  function convRow(cv) {
    var title = cv.title || 'Conversation';
    var openBtn = h('button', { type: 'button', class: 'conv-open', onclick: function () { openConversation(cv.local ? { local: true } : { id: cv.id }); } },
      h('span', { class: 'thing-ico' }, icon('chat', 18)),
      h('span', { class: 'thing-text' }, h('b', null, title),
        h('span', { class: 'tiny' }, humanWhen(cv.updated) + (cv.local ? ' · not saved' : ''))));
    var del = h('button', { type: 'button', class: 'icon-btn quiet', 'aria-label': 'Delete conversation: ' + title }, icon('trash', 18));
    var row = h('div', { class: 'conv-row' }, openBtn, del);
    del.addEventListener('click', function () {
      var yes = h('button', { type: 'button', class: 'btn danger solid small-btn' }, 'Delete');
      var no = h('button', { type: 'button', class: 'link-btn' }, 'Cancel');
      var confirm = h('div', { class: 'conv-confirm' }, h('span', { class: 'small' }, 'Delete "' + title + '"?'), h('span', { class: 'btn-row' }, yes, no));
      row.replaceChildren(confirm);
      no.focus();
      no.addEventListener('click', function () { row.replaceChildren(openBtn, del); del.focus(); });
      yes.addEventListener('click', function () {
        yes.disabled = true;
        if (cv.local) { localConv = null; row.remove(); return; }
        api('/api/conversation/delete', { method: 'POST', body: { id: cv.id } }).then(function () { row.remove(); }, function (e) {
          if (e.status === 404) { row.remove(); return; }   // already gone
          yes.disabled = false;
          if (!e.handled) confirm.appendChild(h('span', { class: 'help err-text' }, e.message));
        });
      });
    });
    return row;
  }

  // ---------- THE CONVERSATION ----------
  // opts: {id} an old one, {local} the unsaved one, {message} send now, {insert, pre} a tool card, {entry} from "What can I ask?".
  function openConversation(opts) {
    opts = opts || {};
    mode = 'conv';
    closeSheet();
    clearView();
    setChrome('conv');
    chat = buildChat(opts);
    viewEl.appendChild(chat.el);
    if (opts.id || opts.local) chat.loadHistory(); else chat.start();
    if (opts.message) chat.send(opts.message);
    else if (opts.insert) chat.insert(opts.insert, opts.pre);
    else if (opts.entry) runAsk(opts.entry);
    else if (opts.focus) chat.focus();
  }

  // "What can I ask?": questions and tools. q: sent to the chat. act: something Svinkki does instead.
  var ASK_TOOLS = [
    { label: 'This week\'s quiz', act: 'quiz', icon: 'help' },
    { label: 'My check-in', act: 'checkin', icon: 'calendar' },
    { label: 'Can I afford it?', act: 'afford', icon: 'wallet' },
    { label: 'What if I spent less?', act: 'whatif', icon: 'sliders' },
    { label: 'Compare with others', act: 'typical', icon: 'people' },
    { label: 'Browse transactions', act: 'browse', icon: 'list' },
    { label: 'Read a receipt', act: 'receipt', icon: 'receipt' },
    { label: 'Explain a text', act: 'explain', icon: 'doc' }
  ];
  var ASK_GROUPS = [
    { title: 'My spending', items: [
      { q: 'How much did I spend on taxis last month?' },
      { q: 'Where did my money go?' },
      { q: 'Show my three baskets for last month' },
      { q: 'What was my latest purchase?' }
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
      { q: 'What kind of mortgage can I get approved for?' },
      { q: 'What should I invest in?' }
    ] },
    { title: 'Set something up', items: [
      { q: 'I am saving 4000 euros for Japan by June 2027' },
      { q: 'Give me a challenge' },
      { q: 'Remember that my rent goes up in January' }
    ] },
    { title: 'Compared with others', items: [
      { q: 'What kind of spender am I?' },
      { q: 'Is my taxi spending normal?' },
      { q: 'How do I compare with people my age?' },
      { q: 'What is my area like?' }
    ] },
    { title: 'Leaks and habits', items: [
      { q: 'Where is my money leaking?' },
      { q: 'Anything unusual this month?' },
      { q: 'Any spending patterns?' }
    ] },
    { title: 'My receipts', items: [
      { q: 'What do I buy most?' },
      { q: 'How much do I spend on energy drinks?' },
      { q: 'Show my receipts' }
    ] }
  ];

  var HELP_PHRASES = ['help', 'what can i ask', 'what can you do', 'apua', 'mitä voin kysyä', 'mita voin kysya'];
  function isHelpRequest(text) {
    var s = String(text || '').toLowerCase().replace(/[?!.\s]+$/, '').replace(/\s+/g, ' ').trim();
    return HELP_PHRASES.indexOf(s) >= 0;
  }

  function offCard(text) {
    var c = cardShell('Switched off');
    c.appendChild(h('p', { class: 'small' }, text));
    c.appendChild(h('button', { type: 'button', class: 'link-btn', onclick: function () { openSettings(); } }, 'Open Settings'));
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
    var c = cardShell('Can I afford it?');
    var out = h('div', { 'aria-live': 'polite' });
    c.appendChild(affordForm(out));
    c.appendChild(out);
    return c;
  }

  // What-if sliders: pct is the percentage to REDUCE the spending by (positive number).
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

  function whatIfBlock(box, t) {
    var selected = [];       // [{target, pct}]
    var c = cardShell('What if I spent less?');
    c.appendChild(h('p', { class: 'small muted' }, 'Pick up to three areas, then slide.'));
    var chipBox = h('div', { class: 'chips', role: 'group', 'aria-label': 'Areas to cut' });
    var sliders = h('div', { class: 'sliders' });
    var out = h('div', { 'aria-live': 'polite' });
    var timer = null, seq = 0;
    var chipBtns = {};

    WHATIF_TARGETS.forEach(function (tt) {
      var b = h('button', { type: 'button', class: 'chip', 'aria-pressed': 'false' }, tt[1]);
      b.addEventListener('click', function () {
        var idx = selected.findIndex(function (s) { return s.target === tt[0]; });
        if (idx >= 0) selected.splice(idx, 1);
        else if (selected.length < 3) selected.push({ target: tt[0], pct: 20 });
        else { out.replaceChildren(h('p', { class: 'notice' }, 'Up to three areas. Tap one to remove it first.')); return; }
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
        sliders.appendChild(h('div', null, h('div', { class: 'slider-head' }, h('label', { for: id }, targetName(s.target)), val), r));
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
        var res = h('div', { class: 'whatif-out' });
        keyFig(res, money(d.saved_total), 'saved in ' + num(d.months || 12) + ' months');
        addRows(res, [['A month', money(d.saved_monthly)], ['Now', money(d.baseline_monthly) + ' a month'], ['Then', money(d.new_monthly) + ' a month']]);
        more(res, [rowsNode((d.lines || []).map(function (l) { return [targetName(l.target), money(l.baseline) + ' to ' + money(l.new)]; }))], d, 'What this is based on');
        out.replaceChildren(res);
      }, function (e) {
        if (!alive(t) || my !== seq || e.handled) return;
        out.replaceChildren(errorNode(e, calc));
      });
    }

    c.appendChild(chipBox); c.appendChild(sliders); c.appendChild(out);
    box.appendChild(c);
  }

  // Topic chips over the averages. Needs benchmark consent.
  function typicalSection(box, t) {
    var c = cardShell('What is typical?');
    box.appendChild(c);
    if (!(me && me.consent && me.consent.benchmarks)) {
      c.appendChild(h('p', { class: 'small' }, 'This compares you with groups of at least 20 similar customers. It needs "Compare me with people like me" in Settings.'));
      c.appendChild(h('button', { type: 'button', class: 'btn secondary', onclick: function () { openSettings(); } }, 'Open Settings'));
      return;
    }
    var chipsBox = h('div', { class: 'chips', role: 'group', 'aria-label': 'Topics' });
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
            b.addEventListener('click', function () { draw(tp.key); });
            chipsBox.appendChild(b);
          });
        }
        chipsBox.querySelectorAll('.chip').forEach(function (x) { x.setAttribute('aria-pressed', String(x.getAttribute('data-topic') === d.topic)); });
        var inner = h('div', { class: 'avg' });
        averagesInto(inner, d);
        body.appendChild(inner);
      });
    }
    draw(null);
  }

  function buildChat(opts) {
    var t = token;
    var conv = { id: opts.id || null, local: !!opts.local };
    var msgs = h('div', { class: 'msgs', role: 'log', 'aria-label': 'Conversation' });
    var busy = false;
    var shown = {};    // key -> thread message already holding that card
    var comp = composer('Ask Svinkki', 'Your question', function (text) { send(text); });
    var askBtn = h('button', { type: 'button', class: 'link-btn ask-link', 'aria-haspopup': 'dialog', onclick: function () { openAsk(); } }, icon('help', 18), 'What can I ask?');

    function toBottom() { msgs.scrollTop = msgs.scrollHeight; }
    // Show the START of a message, not the end of a long card.
    function toStartOf(el) { msgs.scrollTop = Math.max(0, el.offsetTop - msgs.offsetTop - 8); }

    function userBubble(text) {
      var m = h('div', { class: 'msg user' }, h('div', { class: 'bubble' }, h('p', null, text)));
      msgs.appendChild(m);
      return m;
    }
    function botText(node) {
      var m = h('div', { class: 'msg bot' }, h('div', { class: 'bot-text' }, node));
      msgs.appendChild(m);
      return m;
    }

    function send(text) {
      text = String(text || '').trim();
      if (!text || busy) return;
      if (isHelpRequest(text)) { openAsk(); return; }
      busy = true; comp.setBusy(true);
      // A pasted receipt shows as one short line, not the whole text.
      userBubble(/^Receipt:\n/.test(text) ? 'Read this receipt (' + plural(text.split('\n').length - 1, 'line', 'lines') + ')' : text);
      var wait = h('div', { class: 'msg bot' }, h('div', { class: 'bot-text' }, h('span', { class: 'typing', role: 'status', 'aria-label': 'Svinkki is thinking' }, h('i'), h('i'), h('i'))));
      msgs.appendChild(wait);
      toBottom();
      storing.then(function () {
        var body = { message: text };
        if (conv.id) body.conversation_id = conv.id;
        return api('/api/chat', { method: 'POST', body: body });
      }).then(function (res) {
        res = res || {};
        wait.remove();
        if (res.conversation_id) { conv.id = res.conversation_id; convApi = true; }
        else if (convApi !== true) {
          // The server keeps no conversations: remember this one until the next "New".
          if (!conv.local || !localConv) { localConv = { title: text.slice(0, 60), turns: [] }; conv.local = true; }
          localConv.turns.push({ user: text, reply: res.reply, cards: res.cards, used: res.used, mode: res.mode, notice: res.notice });
          localConv.updated = new Date().toISOString();
        }
        toStartOf(botReply(res));
      }, function (e) {
        wait.remove();
        if (e.handled) return;
        toStartOf(botText(errorNode(e)));
      }).then(function () { busy = false; comp.setBusy(false); comp.input.focus({ preventScroll: true }); });
    }

    // Entries from "What can I ask?": send now, or put the question in the box while an answer is pending.
    function ask(q) {
      if (busy) { comp.set(q); return; }
      send(q);
    }

    // An answer: the reply text, the cards (always visible), then the transactions it used.
    function botReply(res) {
      var m = h('div', { class: 'msg bot' });
      m.appendChild(h('div', { class: 'bot-text' }, richText(res.reply)));
      var used = null;
      try { used = usedParts(res.used); } catch (e) { used = null; }
      var cards = h('div', { class: 'msg-cards' + (used ? ' has-used' : '') });
      (res.cards || []).forEach(function (c) {
        var node = null;
        try { node = renderChatCard(c); } catch (e) { node = null; if (window.console) console.error(e); }
        if (!node) return;
        cards.appendChild(node);
        if (!NOT_KEEPABLE[c.type]) addKeep(node, c, node);
      });
      if (cards.childNodes.length) m.appendChild(cards);
      var acts = h('div', { class: 'reply-acts' });
      if (used) acts.appendChild(used.btn);
      // Only an AI-worded reply is marked; built-in answers carry no tag.
      if (isAiMode(res.mode)) acts.appendChild(h('span', { class: 'mode-tag', title: 'Worded by an AI model. The figures come from your own transactions.' }, 'AI'));
      if (acts.childNodes.length) m.appendChild(acts);
      if (used) m.appendChild(used.body);
      if (res.notice) m.appendChild(h('p', { class: 'tiny reply-note' }, ht(String(res.notice))));
      msgs.appendChild(m);
      return m;
    }

    // A card the coach "sends" on request. key: one copy per card; asking again scrolls back to it.
    function insertCard(key, build) {
      var old = shown[key];
      if (old && document.contains(old)) { toStartOf(old); return old; }
      var holder = h('div', { class: 'msg-cards' });
      var m = h('div', { class: 'msg bot' }, holder);
      msgs.appendChild(m);
      build(holder);
      toStartOf(m);
      shown[key] = m;
      return m;
    }

    // A tool card opened in this conversation is remembered by name, so the conversation is kept and listed.
    var STORED_TOOLS = { quiz: 1, checkin: 1, afford: 1, whatif: 1, typical: 1, challenge: 1, alerts: 1 };
    var storing = Promise.resolve();
    function rememberTool(name) {
      if (!STORED_TOOLS[name] || conv.local || convApi === false) return;
      storing = storing.then(function () {
        var body = { tool: name };
        if (conv.id) body.conversation_id = conv.id;
        return api('/api/conversation/tool', { method: 'POST', body: body }).then(function (r) {
          if (r && r.conversation_id) { conv.id = r.conversation_id; convApi = true; }
        }, function () {});
      });
    }

    function insert(name, pre, stored) {
      if (!stored && !(shown[name] && document.contains(shown[name]))) rememberTool(name);
      function src(path) { return pre ? function () { return Promise.resolve(pre); } : function () { return api(path); }; }
      if (name === 'afford') return insertCard('afford', function (hd) { hd.appendChild(affordCard()); });
      if (name === 'whatif') return insertCard('whatif', function (hd) { whatIfBlock(hd, t); });
      if (name === 'typical') return insertCard('typical', function (hd) { typicalSection(hd, t); });
      if (name === 'quiz') {
        return insertCard('quiz', function (hd) {
          fillCard(hd, t, src('/api/quiz'), function (q) { hd.appendChild(quizCard(q)); },
            'Finding this week\'s question...', 'The weekly quiz is off. You can turn it on in Settings.');
        });
      }
      if (name === 'checkin') {
        return insertCard('checkin', function (hd) {
          fillCard(hd, t, src('/api/checkin'), function (r) {
            if (r && r.due && r.checkin) hd.appendChild(checkinCard(r.checkin));
            else hd.appendChild(offCard('Check-ins are off, or none is due yet. You can choose how often in Settings.'));
          }, 'Preparing your check-in...');
        });
      }
      if (name === 'challenge') {
        return insertCard('challenge', function (hd) {
          fillCard(hd, t, src('/api/challenge'), function (d) { hd.appendChild(CARDS.challenge(d || {})); }, 'Loading...');
        });
      }
      if (name === 'alerts') {
        return insertCard('alerts', function (hd) {
          fillCard(hd, t, src('/api/alerts'), function (d) { hd.appendChild(CARDS.alerts(d || {})); }, 'Loading...');
        });
      }
      return null;
    }

    function openExplain() {
      openExplainSheet(function (text, data) {
        var shownText = text.length > 120 ? text.slice(0, 120) + '...' : text;
        userBubble('Explain this text: ' + shownText);
        var m = h('div', { class: 'msg bot' }, h('div', { class: 'msg-cards' }, explainCard(data)));
        msgs.appendChild(m);
        toStartOf(m);
      });
    }

    function start() {
      var first = firstName();
      botText(h('div', { class: 'rich intro' },
        h('p', null, 'Hi' + (first ? ' ' + first : '') + '! I\'m Svinkki, your money coach. Ask me anything, or tell me about a goal.')));
    }

    function renderTurns(turns) {
      (turns || []).forEach(function (tn) {
        if (tn.tool) { insert(tn.tool, null, true); return; }    // drawn fresh from today's data
        if (tn.user) userBubble(/^Receipt:\n/.test(tn.user) ? 'Read this receipt' : tn.user);
        botReply(tn);
      });
      toBottom();
    }

    function loadHistory() {
      if (conv.local) { renderTurns(localConv ? localConv.turns : []); return; }
      var holder = h('div', { class: 'msg bot' }, loadingNode('Opening the conversation...'));
      msgs.appendChild(holder);
      api('/api/conversation?id=' + encodeURIComponent(conv.id)).then(function (c) {
        if (!alive(t)) return;
        holder.remove();
        if (c && c.id) conv.id = c.id;
        renderTurns(c && c.turns);
      }, function (e) {
        if (!alive(t) || e.handled) return;
        holder.replaceChildren(h('div', { class: 'notice err', role: 'alert' }, e.status === 404 ? 'This conversation is no longer here.' : e.message),
          h('button', { type: 'button', class: 'link-btn', onclick: function () { openConversation({ focus: true }); } }, 'Start a new conversation'));
      });
    }

    var el = h('div', { class: 'chat' }, h('h1', { class: 'sr-only' }, 'Conversation with Svinkki'), msgs,
      h('div', { class: 'chat-foot' }, askBtn, comp.el));
    return {
      el: el, start: start, send: send, ask: ask, insert: insert, openExplain: openExplain, loadHistory: loadHistory,
      focus: function () { comp.input.focus(); }, setAiHint: function () {}
    };
  }

  // ---------- "What can I ask?" ----------
  function runAsk(entry) {
    if (entry.act === 'browse') { openBrowse(); return; }
    if (!chat) { openConversation({ entry: entry }); return; }
    if (entry.q) { chat.ask(entry.q); return; }
    var a = entry.act;
    if (a === 'explain') chat.openExplain();
    else if (a === 'receipt') openReceiptSheet();
    else chat.insert(a);
  }

  function openAsk() {
    var body = openSheet('Everything I can do', { full: true });
    body.appendChild(h('p', { class: 'muted' }, 'Tap one to start. Or type your own question, in English or Finnish.'));
    var tools = h('div', { class: 'tool-grid' });
    ASK_TOOLS.forEach(function (it) {
      tools.appendChild(h('button', { type: 'button', class: 'tool', onclick: function () { closeSheet(); runAsk(it); } },
        h('span', { class: 'tool-ico' }, icon(it.icon, 20)), h('span', null, it.label)));
    });
    body.appendChild(h('div', { class: 'ask-sec' }, h('h3', null, 'Tools'), tools));
    ASK_GROUPS.forEach(function (g) {
      var list = h('div', { class: 'list-card' });
      g.items.forEach(function (it) {
        list.appendChild(h('button', { type: 'button', class: 'ask-entry', onclick: function () { closeSheet(); runAsk(it); } },
          h('span', null, it.label || it.q), icon('chev', 16)));
      });
      body.appendChild(h('div', { class: 'ask-sec' }, h('h3', null, g.title), list));
    });
  }

  // ---------- transactions browser ----------
  var BROWSE_BASKETS = [
    { value: '', label: 'All' },
    { value: 'regular', label: 'Regular' },
    { value: 'unexpected', label: 'Unexpected' },
    { value: 'everyday', label: 'Everyday' }
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
    var body = openSheet('Browse transactions', { full: true });
    var t = token;
    var months = monthOptions().slice(0, 6);
    var f = { month: months[1] || months[0], basket: '', label: '', night: false, q: '' };
    var monthOpts = months.map(function (m, i) {
      var parts = m.split('-');
      return { value: m, label: MON[Number(parts[1]) - 1], aria: fmtMonth(m) + (i === 0 ? ', so far' : '') };
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

    var q = h('input', { type: 'search', class: 'input', id: 'br-q', placeholder: 'Search, for example taxi', autocomplete: 'off', 'aria-label': 'Search transactions' });
    q.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(function () { f.q = q.value.trim(); run(); }, 350); });
    var sel = h('select', { class: 'input', id: 'br-label' }, h('option', { value: '' }, 'All categories'));
    function fillLabels(list) {
      list.forEach(function (l) { sel.appendChild(h('option', { value: l }, l)); });
      sel.value = f.label;
    }
    loadLabels().then(fillLabels, function () { fillLabels(FILTER_LABELS); });
    sel.addEventListener('change', function () { f.label = sel.value; run(); });
    var night = switchRow('br-night', 'Nights out only', '', false, function (v) { f.night = v; run(); });

    var filters = disclosure('Filters', 'section');
    filters.body.appendChild(h('div', { class: 'browse-filters' },
      h('div', null, h('span', { class: 'field-label' }, 'Basket'), chipRow('Basket', BROWSE_BASKETS, '', function (v) { f.basket = v; run(); })),
      h('div', null, h('label', { for: 'br-label', class: 'field-label' }, 'Category'), sel),
      night.el));
    body.appendChild(q);
    body.appendChild(chipRow('Month', monthOpts, f.month, function (v) { f.month = v; run(); }));
    body.appendChild(filters.el);
    body.appendChild(results);
    run();
  }

  // ---------- AI model (demo setup) ----------
  // For the person running the demo: choose the Claude model and replace the key. The server never
  // sends the key back; it only says that one is saved and what its last four characters are.
  function aiSetupBlock(box, t) {
    var body = h('div', { class: 'ai-setup' });
    box.appendChild(h('p', { class: 'small muted' }, 'For the person running the demo. Customers never see this in the bank app.'));
    box.appendChild(body);

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
        h('p', { class: 'help' }, 'Saved in a file on this computer. It is never shown again and never sent to the browser.')));
      body.appendChild(h('div', { class: 'btn-row' }, save, test));
      body.appendChild(msg);
    }

    load(body, t, function () { return api('/api/demo/ai'); }, function (st) { draw(st || {}); });
  }

  // ---------- SETTINGS (a full-height sheet) ----------
  function openSettings() {
    var root = openSheet('Settings', { full: true });
    var t = token;
    var saved = h('p', { class: 'saved', role: 'status', 'aria-live': 'polite' });
    var consent = (me && me.consent) || {};
    var settings = (me && me.settings) || {};
    var timer = null;
    function flash(text, isErr) {
      saved.textContent = text || '';
      saved.className = 'saved' + (isErr ? ' err-text' : '');
      clearTimeout(timer);
      if (!isErr) timer = setTimeout(function () { saved.textContent = ''; }, 3000);
    }
    function sec(title, open) {
      var d = disclosure(title, 'section', open);
      root.appendChild(d.el);
      return d.body;
    }

    var pc = prefControls(settings, function (s) {
      flash('Saving...');
      api('/api/settings', { method: 'POST', body: Object.assign(settingsWith(), s, { monthly_saving_target: num(me && me.settings && me.settings.monthly_saving_target) }) }).then(function (r) {
        me.settings = (r && r.settings) || s;
        flash('Saved.');
      }, function (e) { if (!e.handled) flash(e.message, true); });
    });
    var ck = sec('How often I check in', true);
    ck.appendChild(pc.el);
    ck.appendChild(saved);

    var cc = consentControls(consent, function (key, st) {
      flash('Saving...');
      api('/api/consent', { method: 'POST', body: st }).then(function (r) {
        me.consent = (r && r.consent) || st;
        if (!me.consent.analysis) { showConsent(); return; }
        flash('Saved.');
      }, function (e) { if (!e.handled) flash(e.message, true); });
    });
    sec('What Svinkki may do').appendChild(cc.el);

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
    var aiSaw = sec('What the AI saw');
    aiSaw.appendChild(h('p', { class: 'small muted' }, 'Exactly what was last sent to the AI model, with no names or account details.'));
    aiSaw.appendChild(showBtn);
    aiSaw.appendChild(payloadBox);

    aiSetupBlock(sec('AI model (demo setup)'), t);

    var eraseBox = h('div');
    var eraseBtn = h('button', { type: 'button', class: 'btn danger block' }, 'Erase my data');
    eraseBtn.addEventListener('click', function () {
      eraseBtn.hidden = true;
      var yes = h('button', { type: 'button', class: 'btn danger solid' }, 'Yes, erase everything');
      var no = h('button', { type: 'button', class: 'btn secondary' }, 'Cancel');
      var msg = h('div');
      eraseBox.replaceChildren(h('p', { class: 'notice' }, 'This deletes your choices, Your things, your conversations and everything else Svinkki has stored about you. It cannot be undone. Your bank transactions are not touched.'),
        h('div', { class: 'btn-row' }, yes, no), msg);
      no.addEventListener('click', function () { eraseBox.replaceChildren(); eraseBtn.hidden = false; eraseBtn.focus(); });
      yes.addEventListener('click', function () {
        yes.disabled = true;
        api('/api/privacy/erase', { method: 'POST', body: {} }).then(function () {
          localConv = null;
          boot();
        }, function (e) { yes.disabled = false; if (!e.handled) msg.replaceChildren(errorNode(e)); });
      });
    });
    var dataBox = sec('Your data');
    dataBox.appendChild(h('ul', { class: 'plain-list small muted' },
      h('li', null, 'Your transactions stay in the bank. Svinkki only reads your own rows.'),
      h('li', null, 'Your choices and Your things are saved so the app can use them.'),
      h('li', null, 'Your conversations are saved so you can return to them. "Erase my data" removes them too.')));
    dataBox.appendChild(eraseBtn);
    dataBox.appendChild(eraseBox);

    // Demo: back to the very beginning
    var resetBox = h('div');
    var resetBtn = h('button', { type: 'button', class: 'link-btn' }, 'Reset demo');
    resetBtn.addEventListener('click', function () {
      resetBtn.hidden = true;
      var yes = h('button', { type: 'button', class: 'btn danger solid' }, 'Yes, start over');
      var no = h('button', { type: 'button', class: 'btn secondary' }, 'Cancel');
      var msg = h('div');
      resetBox.replaceChildren(h('p', { class: 'notice' }, 'This takes the demo back to the very beginning for every demo customer and logs you out. The AI key and model are kept.'),
        h('div', { class: 'btn-row' }, yes, no), msg);
      no.addEventListener('click', function () { resetBox.replaceChildren(); resetBtn.hidden = false; resetBtn.focus(); });
      yes.addEventListener('click', function () {
        yes.disabled = true;
        api('/api/demo/reset', { method: 'POST', body: {} }).then(function () {
          me = null; localConv = null; closeSheet(); showLogin();
        }, function (e) { yes.disabled = false; if (!e.handled) msg.replaceChildren(errorNode(e)); });
      });
    });
    var logout = h('button', { type: 'button', class: 'btn secondary block' }, 'Log out');
    logout.addEventListener('click', function () {
      logout.disabled = true;
      api('/api/logout', { method: 'POST', body: {} }).then(function () { me = null; localConv = null; showLogin(); },
        function (e) { logout.disabled = false; if (!e.handled) flash(e.message, true); });
    });
    root.appendChild(h('div', { class: 'set-end' }, logout, resetBtn, resetBox));
    root.appendChild(h('p', { class: 'tiny center' }, 'Hackathon prototype for the S-Pankki challenge. Synthetic data.'));
  }

  // ---------- start ----------
  function init() {
    viewEl = document.getElementById('view');
    document.querySelectorAll('[data-icon]').forEach(function (el) {
      el.appendChild(icon(el.getAttribute('data-icon'), 20));
    });
    document.getElementById('back-btn').addEventListener('click', function () { showHome(); });
    document.getElementById('new-btn').addEventListener('click', function () { openConversation({ focus: true }); });
    document.getElementById('gear-btn').addEventListener('click', function () { openSettings(); });
    boot();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
