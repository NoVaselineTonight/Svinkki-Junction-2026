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
    chev: ['M9 6l6 6-6 6']
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
  var currentTab = 'home';
  var token = 0;           // increments on every screen change; stale async work checks it
  var chatCache = null;    // the chat view survives tab switches
  var mode = 'boot';       // boot | login | consent | app
  var viewEl = null;
  var pendingScroll = null; // section id to scroll to after the next screen draws

  function alive(t) { return t === token; }

  function setChrome(showTabs, sub) {
    document.getElementById('tabbar').hidden = !showTabs;
    document.body.classList.toggle('no-tabs', !showTabs);
    if (!showTabs) document.body.classList.remove('chat-screen');
    document.getElementById('topbar-sub').textContent = sub || '';
  }

  function clearView() {
    token++;
    viewEl.replaceChildren();
  }

  function onUnauthorised() {
    if (mode === 'login') return;
    me = null; chatCache = null;
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
    var titleEl = h('span', { class: 'sw-title' }, title);
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
      b.addEventListener('click', function () { go('settings'); });
      return h('p', { class: 'small' }, b);
    }
    return null;
  }

  function stat(value, label) { return h('div', { class: 'stat' }, h('b', null, value), h('span', null, label)); }

  function explainNode(d) {
    return d && d.explain ? h('p', { class: 'explain' }, ht(d.explain)) : null;
  }

  // ---------- bottom sheet ----------
  var sheetState = null;

  function openSheet(title) {
    closeSheet();
    var previous = document.activeElement;
    var body = h('div', { class: 'sheet-body' });
    var closeBtn = h('button', { type: 'button', class: 'sheet-close', 'aria-label': 'Close' }, '×');
    var sheet = h('div', { class: 'sheet', role: 'dialog', 'aria-modal': 'true', 'aria-label': title },
      h('div', { class: 'grabber', 'aria-hidden': 'true' }),
      h('div', { class: 'sheet-head' }, h('h2', null, title), closeBtn),
      body);
    var overlay = h('div', { class: 'overlay' }, sheet);
    function onKey(e) {
      if (e.key === 'Escape') { closeSheet(); return; }
      if (e.key === 'Tab') {
        var f = sheet.querySelectorAll('button, input, select, a[href], [tabindex]:not([tabindex="-1"])');
        if (!f.length) return;
        var first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    }
    closeBtn.addEventListener('click', closeSheet);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) closeSheet(); });
    document.addEventListener('keydown', onKey);
    document.body.appendChild(overlay);
    sheetState = { overlay: overlay, onKey: onKey, previous: previous };
    closeBtn.focus();
    return body;
  }

  function closeSheet() {
    if (!sheetState) return;
    document.removeEventListener('keydown', sheetState.onKey);
    sheetState.overlay.remove();
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

  function txList(res) {
    var rows = (res && res.rows) || [];
    var box = h('div');
    box.appendChild(h('p', { class: 'small muted' },
      (res.count != null ? res.count : rows.length) + ' transactions, total ' + money(Math.abs(num(res.total)))
      + (res.truncated ? ' (showing the first ' + rows.length + ')' : '')));
    if (!rows.length) {
      box.appendChild(h('p', { class: 'muted' }, 'No transactions match.'));
      return box;
    }
    var list = h('div', { role: 'list' });
    rows.forEach(function (r) {
      var amt = num(r.amount);
      var title = r.merchant ? String(r.merchant) : labelText(r);
      var sub = h('span', { class: 'tx-sub' }, fmtDate(r.d || r.ts) + ' · ' + labelText(r));
      if (r.basket && BASKET_NAMES[r.basket]) sub.appendChild(h('span', { class: 'pill' }, BASKET_NAMES[r.basket]));
      list.appendChild(h('div', { class: 'tx', role: 'listitem' },
        h('div', { class: 'tx-main' }, h('span', { class: 'tx-title' }, title), sub),
        h('span', { class: 'tx-amt' + (amt > 0 ? ' in' : '') }, money(amt, { plus: true }))));
    });
    box.appendChild(list);
    return box;
  }

  function openEvidence(evidence, title) {
    var filters = (evidence || []).filter(function (f) { return f && typeof f === 'object'; });
    if (!filters.length) return;
    var body = openSheet(ht(title) || 'Transactions');
    var t = token;
    var tabs = h('div', { class: 'tabs-mini' });
    var out = h('div');
    var btns = [];
    function show(i) {
      btns.forEach(function (b, j) { b.setAttribute('aria-pressed', String(i === j)); });
      load(out, t, function () { return api('/api/transactions?' + filterQuery(filters[i], 100)); }, function (res) {
        out.appendChild(txList(res));
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
    if (!Array.isArray(evidence) || !evidence.length) return null;
    return h('button', { type: 'button', class: 'link-btn', onclick: function () { openEvidence(evidence, title); } }, 'See the transactions');
  }

  // ---------- login ----------
  function showLogin() {
    mode = 'login';
    currentTab = 'home';
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
      monthly_saving_target: num(settings.monthly_saving_target)
    };
    var wrap = h('div', { class: 'prefs' });
    var summary = h('p', { class: 'pref-summary', 'aria-live': 'polite' });
    function describe() {
      if (s.checkin_frequency === 'off') { summary.textContent = 'Check-ins are off. You can still ask anything in chat.'; return; }
      var every = { weekly: 'week', biweekly: 'two weeks', monthly: 'month' }[s.checkin_frequency] || 'month';
      var tail = { off: ' with no suggestions.', few: ' with at most one suggestion.', normal: ' with up to three suggestions.' }[s.suggestion_level] || '.';
      summary.textContent = 'You will get a check-in every ' + every + tail;
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
    var status = h('div');
    var cc = consentControls(consent, function (key, st) {
      go.disabled = !st.analysis;
      hint.hidden = st.analysis;
    });
    var pc = prefControls(settings, function () {});
    var hint = h('p', { class: 'help', id: 'consent-hint' }, 'Turn on "Analyse my transactions" to continue. The other switches are optional.');
    var go = h('button', { type: 'button', class: 'btn block', 'aria-describedby': 'consent-hint' }, 'Save and continue');
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
    viewEl.appendChild(h('div', null,
      h('h1', null, 'Your data, your choices'),
      h('p', { class: 'muted' }, 'Svinkki helps you understand your own money. You decide what it may do, and you can change or withdraw any of this later in Settings.')));
    viewEl.appendChild(h('section', { class: 'card' }, cc.el));
    viewEl.appendChild(h('section', { class: 'card' },
      h('h2', null, 'How much do you want to hear from me?'), pc.el));
    viewEl.appendChild(status);
    viewEl.appendChild(hint);
    viewEl.appendChild(go);
  }

  // ---------- boot ----------
  function showTabs() {
    mode = 'app';
    setChrome(true, me && me.name ? me.name : '');
  }

  function boot() {
    mode = 'boot';
    clearView();
    setChrome(false, '');
    viewEl.appendChild(loadingNode('Loading...'));
    return api('/api/me').then(function (m) {
      me = m;
      if (!me.consent || !me.consent.analysis) { showConsent(); return; }
      showTabs();
      go('home');
    }, function (e) {
      if (e.handled) return;
      clearView();
      viewEl.appendChild(errorNode(e, boot));
    });
  }

  function go(tab) {
    if (mode !== 'app') return;
    closeSheet();
    currentTab = tab;
    clearView();
    document.body.classList.toggle('chat-screen', tab === 'chat');
    var buttons = document.querySelectorAll('.tab');
    for (var i = 0; i < buttons.length; i++) {
      if (buttons[i].getAttribute('data-tab') === tab) buttons[i].setAttribute('aria-current', 'page');
      else buttons[i].removeAttribute('aria-current');
    }
    var t = token;
    var views = { home: renderHome, chat: renderChat, explore: renderExplore, settings: renderSettings };
    (views[tab] || renderHome)(viewEl, t);
    window.scrollTo(0, 0);
    if (pendingScroll) {
      var id = pendingScroll;
      pendingScroll = null;
      setTimeout(function () {
        var el = document.getElementById(id);
        if (el) el.scrollIntoView({ block: 'start' });
      }, 0);
    }
  }

  // ---------- HOME ----------
  function renderHome(root, t) {
    root.appendChild(h('h1', null, 'Hi' + (me && me.name ? ', ' + String(me.name).split(',')[0] : '')));
    var sts = h('div'); var baskets = h('div'); var quiz = h('div'); var checkin = h('div'); var peers = h('div');
    root.appendChild(sts); root.appendChild(baskets); root.appendChild(quiz); root.appendChild(checkin); root.appendChild(peers);
    homeSafe(sts, t); homeBaskets(baskets, t); homeQuiz(quiz, t); homeCheckin(checkin, t); homePeers(peers, t);
  }

  function homeSafe(box, t) {
    load(box, t, function () { return api('/api/safe-to-spend'); }, function (d) { box.appendChild(safeHero(d)); });
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
    toggle.addEventListener('click', function () {
      var open = calc.hidden;
      calc.hidden = !open;
      toggle.setAttribute('aria-expanded', String(open));
      toggle.textContent = open ? 'Hide the calculation' : 'How this is calculated';
    });
    var ev = evidenceLink(d.evidence, 'Where your balance comes from');
    var sec = h('section', { class: 'card hero', 'aria-label': 'Safe to spend' },
      h('div', { class: 'card-head' }, h('span', { class: 'eyebrow' }, 'Safe to spend'), h('span', { class: 'status-pill ' + status }, STATUS_TEXT[status])),
      h('div', { class: 'hero-big' }, money(d.per_day, { hero: true }), h('small', null, ' per day')),
      h('div', { class: 'hero-sub' }, money(d.per_week, { hero: true }) + ' this week'),
      toggle, calc);
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
    if (d.rules) {
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

  function homeBaskets(box, t) {
    load(box, t, function () { return api('/api/baskets?period=last_month'); }, function (d) {
      var c = card('Your three baskets', d.period ? fmtRange(d.period) : 'Last month');
      c.appendChild(h('p', { class: 'small muted' }, 'Every euro you spend lands in one of three baskets. Tap one to see what is inside.'));
      c.appendChild(basketsBlock(d));
      box.appendChild(c);
    });
  }

  // Small teaser: only with benchmark consent; silent when the endpoint is missing or fails.
  function homePeers(box, t) {
    if (!(me && me.consent && me.consent.benchmarks)) return;
    api('/api/averages').then(function (d) {
      if (!alive(t) || !d || !d.headline) return;
      var c = card('Compared with people like you');
      c.appendChild(h('p', null, ht(d.headline)));
      c.appendChild(h('button', { type: 'button', class: 'link-btn', onclick: function () { pendingScroll = 'typical'; go('explore'); } }, 'See more'));
      box.appendChild(c);
    }, function () {});
  }

  function homeQuiz(box, t) {
    api('/api/quiz').then(function (q) {
      if (!alive(t) || !q) return;
      box.appendChild(quizCard(q));
    }, function (e) {
      if (!alive(t) || e.handled || e.status === 404) return; // quiz off: no card
      box.appendChild(errorNode(e, function () { box.replaceChildren(); homeQuiz(box, t); }));
    });
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
      }, function (e) {
        btn.disabled = false; slider.disabled = false;
        if (e.handled) return;
        result.replaceChildren(errorNode(e));
      });
    });
    c.appendChild(out); c.appendChild(slider); c.appendChild(btn); c.appendChild(result);
    return c;
  }

  function homeCheckin(box, t) {
    api('/api/checkin').then(function (r) {
      if (!alive(t) || !r || !r.due || !r.checkin) return;
      box.appendChild(checkinCard(r.checkin));
    }, function (e) {
      if (!alive(t) || e.handled) return;
      box.appendChild(errorNode(e, function () { box.replaceChildren(); homeCheckin(box, t); }));
    });
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

  // ---------- CHAT ----------
  var DEMO_QUESTIONS = [
    'How much did I spend on taxis last month?',
    'Is my taxi spending normal?',
    'What kind of spender am I?',
    'What is safe for me to spend this week?',
    'How much could I save if I reduced dining out by 20%?',
    'What kind of mortgage can I get approved for?',
    'How can I save more?',
    'What should I invest in?',
    'Where did my money go?'
  ];

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

  function renderChat(root, t) {
    if (chatCache) {
      root.appendChild(chatCache.el);
      chatCache.msgs.scrollTop = chatCache.scroll || 0;
      chatCache.input.focus({ preventScroll: true });
      return;
    }
    var msgs = h('div', { class: 'msgs', role: 'log', 'aria-live': 'polite', 'aria-label': 'Conversation' });
    var input = h('textarea', { class: 'input chat-text', rows: '1', maxlength: '2000', placeholder: 'Ask about your money...', 'aria-label': 'Your question', autocomplete: 'off', enterkeyhint: 'send' });
    var sendBtn = h('button', { type: 'submit', class: 'btn' }, 'Send');
    var form = h('form', { class: 'chat-input' }, input, sendBtn);
    var chips = h('div', { class: 'chips chips-row', role: 'group', 'aria-label': 'Suggested questions' });
    var busy = false;

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
    }

    function send(text) {
      text = String(text || '').trim();
      if (!text || busy) return;
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
        var m = botReply(res || {});
        toStartOf(m);
      }, function (e) {
        wait.remove();
        if (e.handled) return;
        var m = h('div', { class: 'msg bot' }, h('div', { class: 'bubble' }, errorNode(e)));
        msgs.appendChild(m);
        toStartOf(m);
      }).then(function () { busy = false; sendBtn.disabled = false; input.focus({ preventScroll: true }); });
    }

    function botReply(res) {
      var inner = h('div');
      inner.appendChild(richText(res.reply));
      var m = bubble('bot', inner);
      var meta = h('div', { class: 'meta' });
      if (res.mode === 'gemini') meta.appendChild(h('span', { class: 'badge ai' }, 'AI model'));
      else meta.appendChild(h('span', { class: 'badge' }, 'On-device rules'));
      var longNotice = res.notice && typeof res.notice === 'string' && res.notice.length > 40;
      if (res.notice && !longNotice) meta.appendChild(h('span', { class: 'badge' }, String(res.notice)));
      m.appendChild(meta);
      var cards = res.cards || [];
      if (cards.length) {
        var wrap = h('div', { class: 'msg-cards' });
        cards.forEach(function (c) {
          var node = null;
          try { node = renderChatCard(c); } catch (e) { node = null; }
          if (node) wrap.appendChild(node);
        });
        m.appendChild(wrap);
      }
      if (longNotice) m.appendChild(h('p', { class: 'notice' }, ht(res.notice)));
      return m;
    }

    DEMO_QUESTIONS.forEach(function (q) {
      chips.appendChild(h('button', { type: 'button', class: 'chip', onclick: function () { send(q); } }, q));
    });
    form.addEventListener('submit', function (e) { e.preventDefault(); send(input.value); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(input.value); }
    });
    input.addEventListener('input', autosize);

    var parts = [h('h1', { class: 'sr-only' }, 'Ask Svinkki')];
    if (me && me.ai_available === false) {
      parts.push(h('p', { class: 'chat-hint' }, 'AI model not connected: answers come from built-in rules. Numbers are the same either way.'));
    }
    parts.push(msgs, chips, form);
    var el = h('div', { class: 'chat' }, parts);
    chatCache = { el: el, input: input, msgs: msgs, scroll: 0 };
    msgs.addEventListener('scroll', function () { if (chatCache) chatCache.scroll = msgs.scrollTop; });
    bubble('bot', h('p', null, 'Hi! Tap a question below or type your own. I can look at your spending, what is safe to spend, savings ideas and more. Numbers always come from your own transactions, and you can open the transactions behind every answer.'));
    root.appendChild(el);
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

  var CARDS = {
    spend: function (d) {
      var c = cardShell('Spending', d.period ? fmtRange(d.period) : '');
      c.appendChild(h('div', { class: 'big-num' }, money(d.total)));
      c.appendChild(h('p', { class: 'small muted' }, num(d.count) + ' purchases'));
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
      var c = cardShell('Safe to spend', STATUS_TEXT[st]);
      c.appendChild(h('div', { class: 'big-num' }, money(d.per_day, { hero: true }) + ' per day'));
      c.appendChild(h('p', null, money(d.per_week, { hero: true }) + ' this week'));
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
      if (d.months_to_equity != null) c.appendChild(h('p', { class: 'small' }, 'At ' + money(d.monthly_saving) + ' a month, about ' + Math.ceil(num(d.months_to_equity)) + ' months to reach the equity.'));
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
    }
  };

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
    c.id = 'typical';
    box.appendChild(c);
    if (!(me && me.consent && me.consent.benchmarks)) {
      c.appendChild(h('p', { class: 'small' }, 'See how your spending and habits compare with groups of at least 20 similar customers. Only group statistics are used, never other people\'s data. This needs the "Compare me with people like me" switch.'));
      c.appendChild(h('button', { type: 'button', class: 'btn secondary', onclick: function () { go('settings'); } }, 'Open Settings'));
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

  function renderExplore(root, t) {
    var months = monthOptions();
    var month = months[1];
    root.appendChild(h('h1', null, 'Explore your money'));
    var sel = h('select', { class: 'input', id: 'month-pick' });
    months.forEach(function (m, i) { sel.appendChild(h('option', { value: m }, fmtMonth(m) + (i === 0 ? ' (so far)' : ''))); });
    sel.value = month;
    root.appendChild(h('div', { class: 'month-bar' }, h('label', { for: 'month-pick', class: 'field-label' }, 'Month'), sel));
    var bBox = h('div'), lBox = h('div'), tBox = h('div'), wBox = h('div'), kBox = h('div');
    root.appendChild(bBox); root.appendChild(lBox); root.appendChild(tBox); root.appendChild(wBox); root.appendChild(kBox);

    function monthRange() { return { from: month + '-01', to: lastDayOfMonth(month) }; }

    function drawMonth() {
      load(bBox, t, function () { return api('/api/baskets?period=' + encodeURIComponent(month)); }, function (d) {
        var c = card('Three baskets', fmtMonth(month));
        c.appendChild(basketsBlock(d, { tops: true }));
        bBox.appendChild(c);
      });
      load(lBox, t, function () { return api('/api/overview?month=' + encodeURIComponent(month)); }, function (d) {
        var c = card('Where it went', fmtMonth(month));
        c.appendChild(h('div', { class: 'stats' }, stat(money(d.income), 'Money in'), stat(money(d.spent), 'Spent'), stat(money(d.surplus), 'Left over')));
        var labels = d.top_labels || [];
        var mx = Math.max.apply(null, labels.map(function (x) { return num(x.total); }).concat([1]));
        labels.forEach(function (x) {
          var name = x.label || x.name || '?';
          var row = h('button', { type: 'button', class: 'bar-row tap', 'aria-label': name + ', ' + money(x.total) + '. Open transactions.' },
            h('span', null, name),
            h('div', { class: 'bar-track', 'aria-hidden': 'true' }, (function () { var f = h('div', { class: 'bar-fill' }); f.style.width = (mx > 0 ? num(x.total) / mx * 100 : 0) + '%'; return f; })()),
            h('span', { class: 'bar-val' }, money(x.total)));
          row.addEventListener('click', function () {
            var r = monthRange();
            var f = { title: name, from: r.from, to: r.to };
            if (x.label === 'Night out') f.context = 'night_out'; else f.label = x.label || x.name;
            openEvidence([f], name);
          });
          c.appendChild(row);
        });
        var ev = evidenceLink(d.evidence, 'The month in transactions');
        if (ev) c.appendChild(ev);
        lBox.appendChild(c);
      });
    }
    sel.addEventListener('change', function () { month = sel.value; drawMonth(); runSearch(); });

    // transaction search
    var q = h('input', { type: 'search', class: 'input', id: 'tx-q', placeholder: 'Merchant or word', autocomplete: 'off' });
    var lab = h('select', { class: 'input', id: 'tx-label' }, h('option', { value: '' }, 'All types'));
    FILTER_LABELS.forEach(function (l) { lab.appendChild(h('option', { value: l }, l)); });
    var bas = h('select', { class: 'input', id: 'tx-basket' }, h('option', { value: '' }, 'All baskets'),
      h('option', { value: 'regular' }, 'Regular essentials'), h('option', { value: 'unexpected' }, 'Unexpected necessities'),
      h('option', { value: 'everyday' }, 'Everyday spending'), h('option', { value: 'savings' }, 'Savings'), h('option', { value: 'income' }, 'Income'));
    var results = h('div', { 'aria-live': 'polite' });
    var tcard = card('Find transactions', 'Chosen month');
    tcard.appendChild(h('div', { class: 'form-grid' },
      h('div', { class: 'wide' }, h('label', { for: 'tx-q' }, 'Search'), q),
      h('div', null, h('label', { for: 'tx-label' }, 'Type'), lab),
      h('div', null, h('label', { for: 'tx-basket' }, 'Basket'), bas)));
    tcard.appendChild(results);
    tBox.appendChild(tcard);
    var searchTimer = null;
    function runSearch() {
      var r = monthRange();
      var f = { from: r.from, to: r.to, q: q.value.trim(), label: lab.value, basket: bas.value };
      load(results, t, function () { return api('/api/transactions?' + filterQuery(f, 50)); }, function (res) { results.appendChild(txList(res)); }, 'Searching...');
    }
    q.addEventListener('input', function () { clearTimeout(searchTimer); searchTimer = setTimeout(runSearch, 350); });
    lab.addEventListener('change', runSearch);
    bas.addEventListener('change', runSearch);

    drawMonth();
    runSearch();
    whatIfBlock(wBox, t);
    var pBox = h('div');
    root.insertBefore(pBox, kBox);
    typicalSection(pBox, t);
    if (me && me.consent && me.consent.benchmarks) {
      var bc = card('You and people like you');
      var inner = h('div');
      bc.appendChild(inner);
      kBox.appendChild(bc);
      load(inner, t, function () { return api('/api/benchmarks'); }, function (d) {
        var g = d.group || {};
        if (g.description) inner.appendChild(h('p', { class: 'small muted' }, g.description + (g.n ? ' (' + g.n + ' people)' : '')));
        benchRows(inner, d.rows);
        openDataBlock(inner, d.open_data);
        var ex = explainNode(d); if (ex) inner.appendChild(ex);
      });
    }
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

  // ---------- SETTINGS ----------
  function renderSettings(root, t) {
    root.appendChild(h('h1', null, 'Settings and privacy'));
    var saved = h('p', { class: 'saved', role: 'status', 'aria-live': 'polite' });
    root.appendChild(saved);
    var consent = (me && me.consent) || {};
    var settings = (me && me.settings) || {};
    var timer = null;
    function flash(text, isErr) {
      saved.textContent = text;
      saved.className = 'saved' + (isErr ? ' notice err' : '');
      clearTimeout(timer);
      if (!isErr) timer = setTimeout(function () { saved.textContent = ''; }, 3500);
    }

    var cc = consentControls(consent, function (key, st) {
      flash('Saving...');
      api('/api/consent', { method: 'POST', body: st }).then(function (r) {
        me.consent = (r && r.consent) || st;
        if (!me.consent.analysis) { showConsent(); return; }
        flash('Saved. Your choices are updated.');
      }, function (e) { if (!e.handled) flash(e.message, true); });
    });
    root.appendChild(h('section', { class: 'card' }, h('h2', null, 'What Svinkki may do'), cc.el));

    var pc = prefControls(settings, function (s) { saveSettings(s); });
    function saveSettings(s) {
      flash('Saving...');
      api('/api/settings', { method: 'POST', body: s }).then(function (r) {
        me.settings = (r && r.settings) || s;
        flash('Saved. Your check-in settings are updated.');
      }, function (e) { if (!e.handled) flash(e.message, true); });
    }
    root.appendChild(h('section', { class: 'card' }, h('h2', null, 'Check-ins and suggestions'), pc.el));

    var target = h('input', { type: 'number', class: 'input', id: 'save-target', min: '0', step: '10', inputmode: 'decimal' });
    target.value = String(num(settings.monthly_saving_target));
    var tBtn = h('button', { type: 'button', class: 'btn' }, 'Save target');
    tBtn.addEventListener('click', function () {
      var v = Number(target.value);
      if (!isFinite(v) || v < 0) { flash('Enter a savings target of zero or more.', true); return; }
      pc.setTarget(v);
      saveSettings(pc.get());
    });
    root.appendChild(h('section', { class: 'card' }, h('h2', null, 'Monthly saving target'),
      h('p', { class: 'small muted' }, 'Used in "safe to spend" so planned savings are set aside first. Nothing is moved automatically.'),
      h('label', { for: 'save-target', class: 'field-label' }, 'Euros per month'),
      h('div', { class: 'btn-row' }, target, tBtn)));

    // What the AI saw
    var payloadBox = h('div');
    var aiCard = h('section', { class: 'card' }, h('h2', null, 'What the AI saw'),
      h('p', { class: 'small muted' }, 'This is exactly what was last sent to the AI model, with no names or account details.'));
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
    aiCard.appendChild(showBtn); aiCard.appendChild(payloadBox);
    root.appendChild(aiCard);

    root.appendChild(h('section', { class: 'card' }, h('h2', null, 'What is stored'),
      h('ul', { class: 'store-list' },
        h('li', null, 'Your transactions stay in the bank data. Svinkki only reads your own rows.'),
        h('li', null, 'Your consent choices and check-in settings are saved so the app can obey them.'),
        h('li', null, 'Answers to the quiz and the suggestions you accept or skip are saved, as intentions only.'),
        h('li', null, 'Chat messages are not stored. Nothing is ever sent to an AI model without your consent.'))));

    // Erase
    var eraseBox = h('div');
    var eraseBtn = h('button', { type: 'button', class: 'btn danger block' }, 'Erase my data');
    eraseBtn.addEventListener('click', function () {
      eraseBtn.hidden = true;
      var yes = h('button', { type: 'button', class: 'btn danger solid' }, 'Yes, erase everything');
      var no = h('button', { type: 'button', class: 'btn secondary' }, 'Cancel');
      var msg = h('div');
      eraseBox.replaceChildren(h('p', { class: 'notice' }, 'This deletes your consent, settings, quiz answers and suggestion choices stored by Svinkki. It cannot be undone. Your bank transactions are not touched.'),
        h('div', { class: 'btn-row' }, yes, no), msg);
      no.addEventListener('click', function () { eraseBox.replaceChildren(); eraseBtn.hidden = false; eraseBtn.focus(); });
      yes.addEventListener('click', function () {
        yes.disabled = true;
        api('/api/privacy/erase', { method: 'POST', body: {} }).then(function () {
          chatCache = null;
          boot();
        }, function (e) { yes.disabled = false; if (!e.handled) msg.replaceChildren(errorNode(e)); });
      });
    });
    var logout = h('button', { type: 'button', class: 'btn secondary block' }, 'Log out');
    logout.addEventListener('click', function () {
      logout.disabled = true;
      api('/api/logout', { method: 'POST', body: {} }).then(function () { me = null; chatCache = null; showLogin(); },
        function (e) { logout.disabled = false; if (!e.handled) flash(e.message, true); });
    });
    root.appendChild(h('section', { class: 'card' }, h('h2', null, 'Your data'), eraseBtn, eraseBox));
    var switchBtn = h('button', { type: 'button', class: 'btn secondary' }, 'Switch customer');
    switchBtn.addEventListener('click', function () {
      switchBtn.disabled = true;
      api('/api/logout', { method: 'POST', body: {} }).then(function () { me = null; chatCache = null; showLogin(); },
        function (e) { switchBtn.disabled = false; if (!e.handled) flash(e.message, true); });
    });
    logout.classList.remove('block');
    root.appendChild(h('div', { class: 'btn-row' }, logout, switchBtn));
  }

  // ---------- start ----------
  function init() {
    viewEl = document.getElementById('view');
    document.querySelectorAll('.tab-icon').forEach(function (el) {
      el.appendChild(icon(el.getAttribute('data-icon')));
    });
    document.querySelectorAll('.tab').forEach(function (b) {
      b.addEventListener('click', function () { go(b.getAttribute('data-tab')); });
    });
    boot();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
