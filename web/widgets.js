/* Svinkki add-on: the home page dashboard. Savings plans with a progress and projection chart, the plan builder
   (used on the home page and in chat), "Svinkki suggests" and "Add to home page" on answer cards.
   app.js calls SvinkkiWidgets.home(box) on every home refresh and SvinkkiWidgets.afterCard(node, card) for every
   card of an answer, and asks SvinkkiCards[type](data, card) before its own renderer.
   Defensive on purpose: a missing endpoint, field or helper hides that part and never breaks the page.
   Text nodes only (through SvinkkiApp.h), never markup. Everything that needs SvinkkiApp is used lazily. */
(function () {
  'use strict';

  // ---------- language ----------
  function app() { return window.SvinkkiApp || null; }
  function isFi() {
    try {
      var a = app();
      if (a && a.isFi) return !!a.isFi();
      return !!(window.SvI18n && window.SvI18n.lang === 'fi');
    } catch (e) { return false; }
  }
  function L(en, fi) { return isFi() ? fi : en; }
  function pick(en, fi) { return isFi() && fi ? fi : en; }

  // Static interface strings: the Finnish for text that goes through SvinkkiApp.h() as English.
  try {
    if (window.SvI18n && window.SvI18n.add) {
      window.SvI18n.add({
        'Savings plans': 'Säästösuunnitelmat',
        'Add to home page': 'Lisää etusivulle',
        'On your home page': 'Etusivullasi',
        'Adjust': 'Muokkaa',
        'Svinkki suggests': 'Svinkki ehdottaa',
        'Not now': 'Ei nyt',
        'Start a savings plan': 'Aloita säästösuunnitelma',
        'Remove': 'Poista',
        'Remove plan': 'Poista suunnitelma',
        'Save changes': 'Tallenna muutokset',
        'a month': 'kuukaudessa'
      }, []);
    }
  } catch (e) { /* the page works without it */ }

  // ---------- pure helpers (also exported for tests) ----------
  function n0(x) { x = Number(x); return isFinite(x) ? x : 0; }
  function isStr(x) { return typeof x === 'string' && x.length > 0; }

  // Same maths as the server: months = ceil((target - saved) / monthly).
  function monthsFor(target, saved, monthly) {
    var rest = n0(target) - n0(saved);
    if (rest <= 0) return 0;
    if (n0(monthly) <= 0) return Infinity;
    return Math.ceil(rest / n0(monthly) - 1e-9);
  }

  function ymOf(s) {
    var m = /^(\d{4})-(\d{2})/.exec(String(s || ''));
    return m ? m[1] + '-' + m[2] : null;
  }
  function addMonths(ym, n) {
    var m = /^(\d{4})-(\d{2})$/.exec(String(ym || ''));
    if (!m) return null;
    var idx = (+m[1]) * 12 + (+m[2]) - 1 + Math.round(n0(n));
    var y = Math.floor(idx / 12), mo = idx % 12 + 1;
    return y + '-' + (mo < 10 ? '0' : '') + mo;
  }
  function monthsBetween(fromYm, toYm) {
    var a = /^(\d{4})-(\d{2})$/.exec(String(fromYm || '')), b = /^(\d{4})-(\d{2})$/.exec(String(toYm || ''));
    if (!a || !b) return 0;
    return ((+b[1]) * 12 + (+b[2])) - ((+a[1]) * 12 + (+a[2]));
  }
  function todayYm() {
    try {
      var a = app();
      var me = a && a.me ? a.me() : null;
      var y = me && me.today ? ymOf(me.today) : null;
      if (y) return y;
    } catch (e) { /* use the clock */ }
    var d = new Date();
    return d.getFullYear() + '-' + (d.getMonth() + 1 < 10 ? '0' : '') + (d.getMonth() + 1);
  }

  function roundUp(x, step) { return Math.ceil(x / step - 1e-9) * step; }

  // The slider: from 10 up to a sensible maximum for this plan, and a step that suits it.
  function sliderRange(target, saved, monthly) {
    var rest = Math.max(n0(target) - n0(saved), 0);
    var max = roundUp(Math.max(rest / 3, 100), 10);
    if (n0(monthly) > max) max = roundUp(n0(monthly), 10);
    if (max > 20000) max = 20000;
    var step = max <= 3000 ? 5 : 50;     // fine enough to show the coach's own figure (125, 230...)
    max = roundUp(max, step);
    return { min: 10, max: Math.max(max, 20), step: step };
  }
  function clampMonthly(v, range) {
    v = n0(v);
    if (v < range.min) v = range.min;
    if (v > range.max) v = range.max;
    return Math.round(v / range.step) * range.step || range.min;
  }

  // A first suggestion for the slider: from the date when there is one, otherwise about a year.
  function defaultMonthly(target, saved, deadline, nowYm) {
    var rest = Math.max(n0(target) - n0(saved), 0);
    var months = 12;
    var dl = ymOf(deadline);
    if (dl) { var k = monthsBetween(nowYm || todayYm(), dl); if (k >= 1) months = k; }
    if (rest <= 0) return 10;
    return Math.max(10, Math.ceil(rest / months));
  }

  // The points of the projection: [{i, planned}], 0..months, straight from "saved" to the target.
  function projection(target, saved, monthly) {
    var t = n0(target), s = Math.min(n0(saved), t), m = monthsFor(t, s, monthly);
    if (!isFinite(m) || m <= 0) return [{ i: 0, planned: s }];
    var out = [], step = Math.max(1, Math.ceil(m / 36));
    for (var i = 0; i < m; i += step) out.push({ i: i, planned: Math.min(s + n0(monthly) * i, t) });
    out.push({ i: m, planned: t });
    return out;
  }

  function plural(n, one, many) { return n === 1 ? one : many; }
  function monthsText(n) {
    if (!isFinite(n)) return '';
    return isFi() ? n + (n === 1 ? ' kuukausi' : ' kuukautta') : n + ' ' + plural(n, 'month', 'months');
  }

  function eur(x) {
    var a = app();
    try { if (a && a.euros) return a.euros(x); } catch (e) { /* fall through */ }
    var v = Math.round(n0(x));
    return isFi() ? String(v).replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + ' €' : '€' + String(v).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }
  function moneyText(x) {
    var a = app();
    try { if (a && a.money) return a.money(x); } catch (e) { /* fall through */ }
    return eur(x);
  }
  function monthName(ym) {
    var a = app();
    try { if (a && a.fmtMonth) return a.fmtMonth(ym); } catch (e) { /* fall through */ }
    return String(ym || '');
  }
  function monthShort(ym) {
    var s = monthName(ym).split(' ')[0];
    return s.length > 4 ? s.slice(0, 3) : s;
  }

  var STATUS_TEXT = {
    done: ['Done', 'Valmis'], ahead: ['Ahead of plan', 'Edellä suunnitelmaa'], on_track: ['On track', 'Aikataulussa'],
    behind: ['A little behind', 'Hieman jäljessä'], not_started: ['Not started yet', 'Ei vielä aloitettu']
  };
  function statusLine(d) {
    var t = isFi() ? d.status_text_fi : d.status_text;
    if (isStr(t)) return t;
    var s = STATUS_TEXT[d.status];
    return s ? L(s[0], s[1]) : '';
  }

  // ---------- small DOM helpers ----------
  var SVG_NS = 'http://www.w3.org/2000/svg';
  function h() {
    var a = app();
    return a.h.apply(null, arguments);
  }
  function svg(name, attrs) {
    var a = app();
    if (a && a.svgEl) return a.svgEl(name, attrs || {});
    var el = document.createElementNS(SVG_NS, name);
    for (var k in attrs) if (Object.prototype.hasOwnProperty.call(attrs, k)) el.setAttribute(k, String(attrs[k]));
    return el;
  }
  function svgText(x, y, anchor, txt, cls) {
    var t = svg('text', { x: x, y: y, 'text-anchor': anchor, 'class': cls || 'wg-axis' });
    t.textContent = String(txt);
    return t;
  }
  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); }
  function notice(text, cls) { return h('p', { class: 'notice ' + (cls || ''), role: 'status' }, text); }
  function failText(e) {
    var m = e && e.message ? String(e.message) : '';
    return m || L('That did not work just now. Please try again.', 'Tämä ei onnistunut juuri nyt. Yritä uudelleen.');
  }
  function post(path, body) { return app().api(path, { method: 'POST', body: body || {} }); }

  // ---------- the projection chart of a plan (inline SVG) ----------
  // m: {target, saved, series: [{ym, planned, actual}] | null, startYm, months, monthly}
  function planChart(m) {
    var W = 300, H = 128, padL = 6, padR = 6, padT = 12, padB = 22;
    var target = Math.max(n0(m.target), 1);
    var pts = [];   // {x: 0..1, planned, actual|null, label}
    var series = Array.isArray(m.series) ? m.series.filter(function (p) { return p && typeof p === 'object'; }) : [];
    if (series.length >= 2) {
      series.forEach(function (p, i) {
        pts.push({ x: i / (series.length - 1), planned: n0(p.planned), actual: p.actual == null ? null : n0(p.actual), ym: p.ym });
      });
    } else {
      var pr = projection(m.target, m.saved, m.monthly);
      var last = pr[pr.length - 1].i || 1;
      pr.forEach(function (p) { pts.push({ x: p.i / last, planned: p.planned, actual: null, i: p.i }); });
      if (pts.length < 2) pts = [{ x: 0, planned: n0(m.saved), actual: null, i: 0 }, { x: 1, planned: target, actual: null, i: 0 }];
    }
    var hi = target;
    pts.forEach(function (p) { if (p.planned > hi) hi = p.planned; if (p.actual != null && p.actual > hi) hi = p.actual; });
    function X(f) { return padL + f * (W - padL - padR); }
    function Y(v) { return padT + (1 - Math.max(0, Math.min(v, hi)) / hi) * (H - padT - padB); }
    var root = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, 'class': 'wg-chart', role: 'img', preserveAspectRatio: 'xMidYMid meet' });
    root.setAttribute('aria-label', L('Savings plan: ', 'Säästösuunnitelma: ') + eur(m.saved) + L(' of ', ' / ') + eur(m.target));
    // The goal line.
    root.appendChild(svg('line', { x1: padL, x2: W - padR, y1: Y(target), y2: Y(target), 'class': 'wg-goal-line' }));
    root.appendChild(svgText(W - padR, Y(target) - 4, 'end', eur(target), 'wg-axis'));
    // Planned: the area under it, then the line.
    var d = pts.map(function (p, i) { return (i ? 'L' : 'M') + X(p.x).toFixed(1) + ' ' + Y(p.planned).toFixed(1); }).join(' ');
    root.appendChild(svg('path', { d: d + ' L' + X(pts[pts.length - 1].x).toFixed(1) + ' ' + (H - padB) + ' L' + X(0).toFixed(1) + ' ' + (H - padB) + ' Z', 'class': 'wg-area' }));
    root.appendChild(svg('path', { d: d, 'class': 'wg-planned', fill: 'none' }));
    // Actual so far.
    var act = pts.filter(function (p) { return p.actual != null; });
    if (act.length >= 2) {
      root.appendChild(svg('path', {
        d: act.map(function (p, i) { return (i ? 'L' : 'M') + X(p.x).toFixed(1) + ' ' + Y(p.actual).toFixed(1); }).join(' '),
        'class': 'wg-actual', fill: 'none'
      }));
    }
    // Where you are now.
    var nowPt = act.length ? act[act.length - 1] : pts[0];
    var nowVal = act.length ? nowPt.actual : n0(m.saved);
    root.appendChild(svg('circle', { cx: X(nowPt.x).toFixed(1), cy: Y(nowVal).toFixed(1), r: 5, 'class': 'wg-now' }));
    // Month labels at both ends.
    var first = pts[0], lastP = pts[pts.length - 1];
    var startYm = first.ym || m.startYm, endYm = lastP.ym || (m.startYm && isFinite(m.months) ? addMonths(m.startYm, m.months) : null);
    if (startYm) root.appendChild(svgText(padL, H - 6, 'start', monthShort(startYm), 'wg-axis'));
    if (endYm) root.appendChild(svgText(W - padR, H - 6, 'end', monthName(endYm), 'wg-axis'));
    return root;
  }

  // ---------- chart blocks of other widgets (Contract B), a small local drawer ----------
  var TONES = { main: '#007841', muted: '#949494', good: '#00AA46', warn: '#CF8300' };
  var CYCLE = ['#004628', '#CF8300', '#00AA46', '#006E87', '#949494'];
  function toneColor(t, i) { return TONES[t] || CYCLE[i % CYCLE.length]; }
  function seriesLabel(p) {
    if (p && p.ym) return monthShort(p.ym);
    return String(pick(p && p.label, p && p.label_fi) || '');
  }
  function unitText(v, unit) {
    if (unit === 'count') return String(Math.round(n0(v)));
    if (unit === 'pct') return Math.round(n0(v)) + (isFi() ? ' %' : '%');
    return n0(v) >= 20 ? eur(v) : moneyText(v);
  }
  function drawChart(c) {
    try {
      if (!c || typeof c !== 'object' || !Array.isArray(c.series) || !c.series.length) return null;
      var s = c.series.filter(function (p) { return p && isFinite(Number(p.value)); });
      if (!s.length) return null;
      var kind = c.kind, unit = c.unit || 'eur';
      var legend = null;
      if (kind === 'split' || kind === 'progress') {
        var total = 0;
        s.forEach(function (p) { total += Math.max(n0(p.value), 0); });
        if (kind === 'progress') {
          var goal = n0(c.target) || total, now = c.now != null ? n0(c.now) : n0(s[0].value);
          var pct = goal > 0 ? Math.max(0, Math.min(now / goal, 1)) * 100 : 0;
          var bar = h('div', { class: 'wg-bar', role: 'img', 'aria-label': unitText(now, unit) + ' / ' + unitText(goal, unit) });
          var fill = h('div', { class: 'wg-bar-fill' });
          fill.style.width = pct.toFixed(1) + '%';
          bar.appendChild(fill);
          return bar;
        }
        if (total <= 0) return null;
        var wrap = h('div', { class: 'wg-split' });
        var stack = h('div', { class: 'wg-stack', role: 'img' });
        var list = h('ul', { class: 'wg-legend' });
        var aria = [];
        s.forEach(function (p, i) {
          var v = Math.max(n0(p.value), 0);
          if (v <= 0) return;
          var seg = h('div', { class: 'wg-seg' });
          seg.style.width = (v / total * 100).toFixed(2) + '%';
          seg.style.background = toneColor(p.tone, i);
          stack.appendChild(seg);
          var sw = h('span', { class: 'wg-sw' });
          sw.style.background = toneColor(p.tone, i);
          list.appendChild(h('li', null, sw, h('span', { class: 'wg-lg-label' }, seriesLabel(p)), h('span', { class: 'wg-lg-val' }, unitText(v, unit))));
          aria.push(seriesLabel(p) + ' ' + unitText(v, unit));
        });
        stack.setAttribute('aria-label', aria.join(', '));
        wrap.appendChild(stack); wrap.appendChild(list);
        return wrap;
      }
      if (kind === 'hbars') {
        var rows = s.slice(0, 6), mx = 0;
        rows.forEach(function (p) { if (n0(p.value) > mx) mx = n0(p.value); });
        if (mx <= 0) return null;
        var hb = h('div', { class: 'wg-hbars' });
        rows.forEach(function (p, i) {
          var f = h('div', { class: 'wg-hb-fill' });
          f.style.width = Math.max(n0(p.value) / mx * 100, 2).toFixed(1) + '%';
          f.style.background = toneColor(p.tone, i);
          hb.appendChild(h('div', { class: 'wg-hb' },
            h('span', { class: 'wg-hb-label' }, seriesLabel(p)),
            h('span', { class: 'wg-hb-track' }, f),
            h('span', { class: 'wg-hb-val' }, unitText(p.value, unit))));
        });
        return hb;
      }
      if (kind === 'bars' || kind === 'line') {
        var pts = s.slice(-12);
        if (pts.length < 2) return null;
        var W = 300, H = 120, padT = 14, padB = 20, padX = 6;
        var top = 0;
        pts.forEach(function (p) { top = Math.max(top, n0(p.value), n0(p.value2)); });
        if (c.target != null) top = Math.max(top, n0(c.target));
        if (top <= 0) return null;
        var root = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, 'class': 'wg-chart', role: 'img', preserveAspectRatio: 'xMidYMid meet' });
        root.setAttribute('aria-label', pts.map(function (p) { return seriesLabel(p) + ' ' + unitText(p.value, unit); }).join(', '));
        var inner = W - padX * 2, slot = inner / pts.length, base = H - padB;
        function Yv(v) { return padT + (1 - Math.max(n0(v), 0) / top) * (base - padT); }
        if (c.target != null && n0(c.target) > 0) {
          root.appendChild(svg('line', { x1: padX, x2: W - padX, y1: Yv(c.target), y2: Yv(c.target), 'class': 'wg-goal-line' }));
        }
        if (kind === 'line') {
          root.appendChild(svg('path', {
            d: pts.map(function (p, i) { return (i ? 'L' : 'M') + (padX + slot * (i + .5)).toFixed(1) + ' ' + Yv(p.value).toFixed(1); }).join(' '),
            'class': 'wg-planned', fill: 'none'
          }));
        }
        var two = pts.some(function (p) { return p.value2 != null; });
        pts.forEach(function (p, i) {
          var cx = padX + slot * (i + .5);
          if (kind === 'bars') {
            var bw = Math.min(slot * (two ? .38 : .62), 26);
            var xs = two ? [cx - bw - 1, cx + 1] : [cx - bw / 2];
            [p.value, p.value2].forEach(function (v, k) {
              if (k && !two) return;
              if (v == null) return;
              var y = Yv(v);
              root.appendChild(svg('rect', {
                x: xs[k].toFixed(1), y: y.toFixed(1), width: bw.toFixed(1), height: Math.max(base - y, 1).toFixed(1), rx: 2,
                fill: k ? TONES.muted : (p.mark ? TONES.good : (TONES[p.tone] || TONES.main)), 'class': 'wg-col'
              }));
            });
          } else if (p.mark) {
            root.appendChild(svg('circle', { cx: cx.toFixed(1), cy: Yv(p.value).toFixed(1), r: 4, 'class': 'wg-now' }));
          }
          if (pts.length <= 7 || i % 2 === (pts.length - 1) % 2) root.appendChild(svgText(cx.toFixed(1), H - 5, 'middle', seriesLabel(p), 'wg-axis'));
        });
        if (two && c.legend) {
          // Two series: say which is which under the chart.
          var lg = h('ul', { class: 'wg-legend inline' },
            h('li', null, (function () { var x = h('span', { class: 'wg-sw' }); x.style.background = TONES.main; return x; })(),
              h('span', { class: 'wg-lg-label' }, pick(c.legend.value, c.legend.value_fi) || '')),
            h('li', null, (function () { var x = h('span', { class: 'wg-sw' }); x.style.background = TONES.muted; return x; })(),
              h('span', { class: 'wg-lg-label' }, pick(c.legend.value2, c.legend.value2_fi) || '')));
          legend = lg;
        }
        if (!legend) return root;
        var box = h('div', null, root, legend);
        return box;
      }
    } catch (e) { if (window.console) console.error(e); }
    return null;
  }

  // ---------- the plan builder ----------
  // opts: {name, target, saved, monthly, deadline, note, widgetId (edit), submitLabel, onDone(widget)}
  function builder(opts) {
    opts = opts || {};
    var a = app();
    var uid = 'wb-' + Math.random().toString(36).slice(2, 7);
    var nowYm = todayYm();
    var saved = Math.max(n0(opts.saved), 0);
    var editing = !!opts.widgetId;
    var st = {
      name: isStr(opts.name) ? String(opts.name).slice(0, 60) : '',
      target: n0(opts.target) > 0 ? Math.round(n0(opts.target)) : 0,
      monthly: n0(opts.monthly) > 0 ? n0(opts.monthly) : 0
    };
    if (!st.monthly && st.target > 0) st.monthly = defaultMonthly(st.target, saved, opts.deadline, nowYm);
    if (!st.monthly) st.monthly = 50;
    var range = sliderRange(st.target || 600, saved, st.monthly);
    st.monthly = clampMonthly(st.monthly, range);

    var nameIn = h('input', { type: 'text', class: 'input', id: uid + '-n', maxlength: '60', autocomplete: 'off', placeholder: L('What are you saving for?', 'Mihin säästät?') });
    nameIn.value = st.name;
    var targetIn = h('input', { type: 'number', class: 'input', id: uid + '-t', min: '10', step: '10', inputmode: 'numeric', placeholder: '1000' });
    if (st.target) targetIn.value = String(st.target);
    var slider = h('input', { type: 'range', class: 'wg-slider', id: uid + '-m', min: String(range.min), max: String(range.max), step: String(range.step) });
    slider.value = String(st.monthly);
    slider.setAttribute('aria-label', L('Amount a month', 'Summa kuukaudessa'));
    var bigVal = h('span', { class: 'wg-big' });
    var dateLine = h('p', { class: 'wg-date' });
    var chartBox = h('div', { class: 'wg-chart-box' });
    var fitLine = h('p', { class: 'wg-fit', 'aria-live': 'polite', hidden: true });
    var msg = h('div', { 'aria-live': 'polite' });
    var submit = h('button', { type: 'button', class: 'btn block wg-submit' }, opts.submitLabel || L('Add to home page', 'Lisää etusivulle'));
    var root = h('div', { class: 'wg-builder' });
    var form = h('div', { class: 'wg-form' },
      h('div', { class: 'wg-field' }, h('label', { for: uid + '-n', class: 'field-label' }, L('Name', 'Nimi')), nameIn),
      h('div', { class: 'wg-field' }, h('label', { for: uid + '-t', class: 'field-label' }, L('Target in euros', 'Tavoite euroina')), targetIn),
      h('div', { class: 'wg-field' },
        h('label', { for: uid + '-m', class: 'field-label' }, L('How much a month', 'Kuinka paljon kuukaudessa')),
        h('div', { class: 'wg-big-row' }, bigVal), slider),
      dateLine, chartBox, fitLine, msg, submit);
    root.appendChild(form);

    var previewSeq = 0, timer = null, noteFromServer = isStr(opts.note) ? opts.note : null;
    if (noteFromServer) { fitLine.textContent = noteFromServer; fitLine.hidden = false; }

    function redraw() {
      bigVal.textContent = eur(st.monthly) + L(' a month', ' kuukaudessa');
      var m = monthsFor(st.target, saved, st.monthly);
      if (st.target <= 0) {
        dateLine.textContent = L('Pick a target and I will show when you get there.', 'Valitse tavoite, niin näytän milloin pääset perille.');
        clear(chartBox);
        return;
      }
      if (!isFinite(m) || m <= 0) {
        dateLine.textContent = m === 0 ? L('This target is already reached.', 'Tämä tavoite on jo saavutettu.') : '';
      } else {
        dateLine.textContent = isFi() ? 'Perillä ' + monthsText(m) + ' päästä, ' + monthName(addMonths(nowYm, m))
          : 'Reached in ' + monthsText(m) + ', ' + monthName(addMonths(nowYm, m));
      }
      clear(chartBox);
      try { chartBox.appendChild(planChart({ target: st.target, saved: saved, monthly: st.monthly, startYm: nowYm, months: m })); } catch (e) { /* no chart */ }
    }

    function schedulePreview() {
      if (timer) clearTimeout(timer);
      timer = setTimeout(askPreview, 450);
    }
    function askPreview() {
      timer = null;
      if (st.target <= 0) { fitLine.hidden = true; return; }
      var seq = ++previewSeq;
      post('/api/plan/preview', { name: st.name || undefined, target: st.target, monthly: st.monthly }).then(function (r) {
        if (seq !== previewSeq) return;
        var t = r ? (isFi() ? (r.note_fi || r.note) : r.note) : '';
        if (isStr(t)) {
          fitLine.textContent = t; fitLine.hidden = false;
          fitLine.className = 'wg-fit' + (r.fits === false ? ' warn' : (r.fits === true ? ' ok' : ''));
        } else fitLine.hidden = true;
      }, function () { if (seq === previewSeq) fitLine.hidden = true; });
    }

    slider.addEventListener('input', function () {
      st.monthly = n0(slider.value);
      noteFromServer = null; fitLine.hidden = true;
      redraw(); schedulePreview();
    });
    slider.addEventListener('change', function () { if (timer) clearTimeout(timer); askPreview(); });
    targetIn.addEventListener('input', function () {
      var v = Math.round(n0(targetIn.value));
      st.target = v > 0 ? v : 0;
      if (st.target > 0) {
        range = sliderRange(st.target, saved, st.monthly);
        slider.min = String(range.min); slider.max = String(range.max); slider.step = String(range.step);
        st.monthly = clampMonthly(st.monthly, range);
        slider.value = String(st.monthly);
      }
      noteFromServer = null; fitLine.hidden = true;
      redraw(); schedulePreview();
    });
    nameIn.addEventListener('input', function () { st.name = nameIn.value; });

    submit.addEventListener('click', function () {
      st.name = String(nameIn.value || '').trim().slice(0, 60);
      if (st.target <= 0) { msg.replaceChildren(notice(L('Enter a target above zero.', 'Anna tavoite, joka on yli nolla.'))); targetIn.focus(); return; }
      var params = { name: st.name || L('My savings', 'Säästöni'), target: st.target, monthly: st.monthly };
      submit.disabled = true;
      msg.replaceChildren(h('p', { class: 'tiny' }, L('Saving...', 'Tallennetaan...')));
      var req = editing ? post('/api/widgets/update', { id: opts.widgetId, params: params }) : post('/api/widgets', { type: 'plan', params: params });
      req.then(function (r) {
        var w = r && r.widget ? r.widget : null;
        if (!w) { submit.disabled = false; msg.replaceChildren(notice(L('That did not work just now. Please try again.', 'Tämä ei onnistunut juuri nyt. Yritä uudelleen.'))); return; }
        if (typeof opts.onDone === 'function') { try { opts.onDone(w); } catch (e) { /* ignore */ } }
        else done(w);
        try { a.refreshHome(); } catch (e) { /* ignore */ }
      }, function (e) { submit.disabled = false; msg.replaceChildren(notice(failText(e), 'err')); });
    });

    function done(w) {
      clear(root);
      var d = w && w.data ? w.data : {};
      root.appendChild(h('div', { class: 'wg-done', role: 'status' },
        h('span', { class: 'wg-done-mark', 'aria-hidden': 'true' }, a.icon ? a.icon('target', 22) : null),
        h('div', null,
          h('p', { class: 'wg-done-title' }, L('On your home page', 'Etusivullasi')),
          h('p', { class: 'tiny' }, (d.name || st.name || '') + (d.name || st.name ? ': ' : '') + eur(st.monthly) + L(' a month', ' kuukaudessa')))));
    }

    redraw();
    return root;
  }

  // ---------- widget cards on the home page ----------
  function ring(pct) {
    var R = 26, C = 2 * Math.PI * R, p = Math.max(0, Math.min(n0(pct), 100));
    var s = svg('svg', { viewBox: '0 0 64 64', 'class': 'wg-ring', 'aria-hidden': 'true' });
    s.appendChild(svg('circle', { cx: 32, cy: 32, r: R, 'class': 'wg-ring-bg', fill: 'none' }));
    s.appendChild(svg('circle', {
      cx: 32, cy: 32, r: R, 'class': 'wg-ring-fg', fill: 'none',
      'stroke-dasharray': (C * p / 100).toFixed(1) + ' ' + C.toFixed(1), transform: 'rotate(-90 32 32)'
    }));
    var t = svg('text', { x: 32, y: 37, 'text-anchor': 'middle', 'class': 'wg-ring-text' });
    t.textContent = Math.round(p) + '%';
    s.appendChild(t);
    return s;
  }

  function hasPlan(w) { return w && w.type === 'plan' && w.data && n0(w.data.target) > 0; }

  function openBuilder(title, bopts) {
    var a = app();
    var body = a.openSheet(title);
    bopts.onDone = function (w) {
      // The sheet closes at once on a change; refreshHome redraws the dashboard behind it.
      try { a.closeSheet(); } catch (e) { /* ignore */ }
    };
    body.appendChild(builder(bopts));
    return body;
  }

  function planCard(w) {
    var a = app(), d = w.data;
    var title = isStr(w.title) ? w.title : (isStr(d.name) ? d.name : L('Savings plan', 'Säästösuunnitelma'));
    var c = h('section', { class: 'card wg wg-plan', 'data-wid': String(w.id) });
    var chip = statusLine(d);
    c.appendChild(h('div', { class: 'card-head' }, h('div', { class: 'card-titles' },
      h('h3', { class: 'card-title' }, title),
      chip ? h('span', { class: 'wg-status s-' + String(d.status || 'x') }, chip) : null)));
    var saved = n0(d.saved), target = n0(d.target);
    var pct = d.pct != null ? n0(d.pct) : (target > 0 ? saved / target * 100 : 0);
    c.appendChild(h('div', { class: 'wg-top' }, ring(pct),
      h('div', { class: 'wg-top-text' },
        h('p', { class: 'wg-amount' }, eur(saved), h('span', { class: 'wg-of' }, L(' of ', ' / ') + eur(target))),
        d.monthly != null && n0(d.monthly) > 0 ? h('p', { class: 'tiny' }, eur(d.monthly) + L(' a month', ' kuukaudessa') +
          (d.months_left != null && n0(d.months_left) > 0 ? ', ' + L(monthsText(Math.round(n0(d.months_left))) + ' to go', monthsText(Math.round(n0(d.months_left))) + ' jäljellä') : '') +
          (d.deadline ? ' (' + (a.fmtDate ? a.fmtDate(d.deadline) : d.deadline) + ')' : '')) : null)));
    try {
      c.appendChild(planChart({ target: target, saved: saved, series: d.series, monthly: d.monthly, startYm: todayYm(), months: n0(d.months_left) }));
    } catch (e) { /* no chart */ }
    var nm = d.next_move;
    var line = nm ? pick(nm.text, nm.text_fi) : null;
    if (isStr(line)) c.appendChild(h('p', { class: 'small wg-next' }, line));
    var note = pick(d.note, d.note_fi);
    if (isStr(note) && note !== line) c.appendChild(h('p', { class: 'tiny' }, note));
    var slot = h('div', { class: 'wg-slot', 'aria-live': 'polite' });
    var row = h('div', { class: 'btn-row wg-actions' });
    if (nm && nm.ok && n0(nm.amount) > 0 && d.status !== 'done') {
      var mv = h('button', { type: 'button', class: 'btn small-btn' }, L('Move ' + eur(nm.amount) + ' now', 'Siirrä ' + eur(nm.amount) + ' nyt'));
      mv.addEventListener('click', function () { doMove(w.id, nm.amount, mv, slot); });
      row.appendChild(mv);
    }
    var adj = h('button', { type: 'button', class: 'btn secondary small-btn' }, 'Adjust');
    adj.addEventListener('click', function () {
      try {
        var body = openBuilder(L('Adjust plan', 'Muokkaa suunnitelmaa'), {
          widgetId: w.id, name: d.name || title, target: target, saved: saved, monthly: d.monthly, deadline: d.deadline,
          submitLabel: L('Save changes', 'Tallenna muutokset')
        });
        body.appendChild(removeButton(w.id, L('Remove plan', 'Poista suunnitelma')));
      } catch (e) { if (window.console) console.error(e); }
    });
    row.appendChild(adj);
    c.appendChild(row); c.appendChild(slot);
    return c;
  }

  function doMove(id, amount, btn, slot) {
    var a = app();
    btn.disabled = true;
    slot.replaceChildren(h('p', { class: 'tiny' }, L('One moment...', 'Hetki...')));
    post('/api/widgets/move', { id: id, amount: amount }).then(function (r) {
      btn.disabled = false;
      if (r && r.proposal) slot.replaceChildren(a.moneyProposalCard(r.proposal));
      else slot.replaceChildren(notice(pick(r && r.message, r && r.message_fi) || L('That move is not possible right now.', 'Tämä siirto ei onnistu juuri nyt.')));
    }, function (e) { btn.disabled = false; slot.replaceChildren(notice(failText(e), 'err')); });
  }

  // Two taps: the first asks "Sure?", the second removes. No dialog needed.
  function removeButton(id, label, onGone) {
    var a = app();
    var b = h('button', { type: 'button', class: 'btn danger block wg-remove' }, label);
    var armed = false, box = h('div', { class: 'wg-remove-box' });
    b.addEventListener('click', function () {
      if (!armed) {
        armed = true;
        b.textContent = L('Tap again to remove', 'Napauta uudelleen poistaaksesi');
        setTimeout(function () { if (b.isConnected) { armed = false; b.textContent = label; } }, 5000);
        return;
      }
      b.disabled = true;
      post('/api/widgets/remove', { id: id }).then(function () {
        try { a.closeSheet(); } catch (e) { /* ignore */ }
        if (typeof onGone === 'function') onGone();
        try { a.refreshHome(); } catch (e) { /* ignore */ }
      }, function (e) { b.disabled = false; armed = false; b.textContent = label; box.appendChild(notice(failText(e), 'err')); });
    });
    box.appendChild(b);
    return box;
  }

  function miniCard(w) {
    var d = w.data || {};
    var title = isStr(w.title) ? w.title : '';
    var c = h('section', { class: 'card wg wg-mini', 'data-wid': String(w.id) });
    var menu = h('button', { type: 'button', class: 'wg-x', 'aria-label': L('Remove from home page', 'Poista etusivulta'), title: L('Remove from home page', 'Poista etusivulta') }, L('Remove', 'Poista'));
    var armed = false;
    menu.addEventListener('click', function () {
      if (!armed) { armed = true; menu.textContent = L('Sure?', 'Varmasti?'); setTimeout(function () { if (menu.isConnected) { armed = false; menu.textContent = L('Remove', 'Poista'); } }, 4000); return; }
      menu.disabled = true;
      post('/api/widgets/remove', { id: w.id }).then(function () { try { app().refreshHome(); } catch (e) { /* ignore */ } },
        function () { menu.disabled = false; armed = false; menu.textContent = L('Remove', 'Poista'); });
    });
    c.appendChild(h('div', { class: 'card-head' }, h('div', { class: 'card-titles' }, h('h3', { class: 'card-title' }, title)), menu));
    var ch = null;
    try { ch = drawChart(d.chart); } catch (e) { ch = null; }
    if (ch) c.appendChild(ch);
    var cap = pick(d.caption, d.caption_fi);
    if (isStr(cap)) c.appendChild(h('p', { class: 'small wg-cap' }, cap));
    if (!ch && !isStr(cap)) return null;
    return c;
  }

  // ---------- empty state and presets ----------
  function emptyState() {
    var c = h('section', { class: 'card wg wg-empty' });
    c.appendChild(h('div', { class: 'card-head' }, h('div', { class: 'card-titles' },
      h('h3', { class: 'card-title' }, L('Start a savings plan', 'Aloita säästösuunnitelma')),
      h('span', { class: 'card-sub' }, L('Pick one. You can change everything after.', 'Valitse yksi. Voit muuttaa kaiken jälkeenpäin.')))));
    var opts = [
      { en: 'Buffer for surprises', fi: 'Puskuri yllätyksiin', target: 1000,
        sub_en: 'A buffer is money set aside for surprises, like a broken phone, so you do not need a loan.',
        sub_fi: 'Puskuri on sivuun pantua rahaa yllätyksiä varten, esimerkiksi rikkoutunutta puhelinta varten, ettei tarvitse lainaa.' },
      { en: 'A trip or purchase', fi: 'Matka tai hankinta', target: 800,
        sub_en: 'Something you look forward to, saved a little each month.', sub_fi: 'Jotain odotettavaa, johon säästät vähän kerrallaan.' },
      { en: 'Something of my own', fi: 'Jotain omaa', target: 0,
        sub_en: 'Name it and choose the amount yourself.', sub_fi: 'Anna sille nimi ja valitse summa itse.' }
    ];
    var list = h('div', { class: 'wg-presets' });
    opts.forEach(function (o) {
      var b = h('button', { type: 'button', class: 'wg-preset' },
        h('span', { class: 'wg-preset-t' }, L(o.en, o.fi)),
        h('span', { class: 'wg-preset-s' }, L(o.sub_en, o.sub_fi)));
      b.addEventListener('click', function () {
        try { openBuilder(L('New savings plan', 'Uusi säästösuunnitelma'), { name: o.target ? L(o.en, o.fi) : '', target: o.target }); }
        catch (e) { if (window.console) console.error(e); }
      });
      list.appendChild(b);
    });
    c.appendChild(list);
    return c;
  }

  function addRow(canAdd, have) {
    var kinds = [];
    if (canAdd.indexOf('plan') >= 0) kinds.push({ type: 'plan', label: L('Another plan', 'Toinen suunnitelma') });
    if (canAdd.indexOf('safe') >= 0 && !have.safe) kinds.push({ type: 'safe', label: L('Safe to spend', 'Käyttövara') });
    if (canAdd.indexOf('baskets') >= 0 && !have.baskets) kinds.push({ type: 'baskets', label: L('Where money goes', 'Minne raha menee') });
    if (!kinds.length) return null;
    var row = h('div', { class: 'wg-add-home' }, h('span', { class: 'tiny' }, L('Add to this page', 'Lisää tälle sivulle')));
    var chips = h('div', { class: 'chips' });
    kinds.forEach(function (k) {
      var b = h('button', { type: 'button', class: 'chip ready' }, '+ ' + k.label);
      b.addEventListener('click', function () {
        if (k.type === 'plan') {
          try { openBuilder(L('New savings plan', 'Uusi säästösuunnitelma'), {}); } catch (e) { if (window.console) console.error(e); }
          return;
        }
        b.disabled = true;
        post('/api/widgets', { type: k.type }).then(function () { try { app().refreshHome(); } catch (e) { /* ignore */ } },
          function () { b.disabled = false; });
      });
      chips.appendChild(b);
    });
    row.appendChild(chips);
    return row;
  }

  // ---------- Svinkki suggests ----------
  function suggestCard(s, section) {
    var a = app();
    var c = h('article', { class: 'wg-suggest' });
    var fig = s.figure && s.figure.value != null ? s.figure : null;
    c.appendChild(h('div', { class: 'wg-sg-head' },
      fig ? h('span', { class: 'wg-sg-fig' }, fig.unit === 'eur' || !fig.unit ? eur(fig.value) : String(fig.value)) : null,
      h('h4', { class: 'wg-sg-title' }, pick(s.title, s.title_fi) || '')));
    var why = pick(s.why, s.why_fi);
    if (isStr(why)) c.appendChild(h('p', { class: 'small wg-sg-why' }, why));
    var slot = h('div', { class: 'wg-slot', 'aria-live': 'polite' });
    var act = s.action || {};
    var label = pick(act.label, act.label_fi) || L('Do it', 'Tee se');
    var go = h('button', { type: 'button', class: 'btn small-btn' }, label);
    var no = h('button', { type: 'button', class: 'btn secondary small-btn' }, 'Not now');
    go.addEventListener('click', function () {
      try {
        if (act.type === 'ask') {
          var text = pick(act.message, act.message_fi) || pick(s.title, s.title_fi);
          if (isStr(text)) a.ask(text);
        } else if (act.type === 'create_widget' && act.widget) {
          go.disabled = true;
          post('/api/widgets', { type: act.widget.type, params: act.widget.params || {} }).then(function () {
            try { a.refreshHome(); } catch (e) { /* ignore */ }
          }, function (e) { go.disabled = false; slot.replaceChildren(notice(failText(e), 'err')); });
        } else if (act.type === 'move') {
          go.disabled = true;
          var req = act.widget_id ? post('/api/widgets/move', { id: act.widget_id, amount: act.amount }) : post('/api/money/propose', { amount: act.amount });
          req.then(function (r) {
            go.disabled = false;
            if (r && r.proposal) slot.replaceChildren(a.moneyProposalCard(r.proposal));
            else slot.replaceChildren(notice(pick(r && r.message, r && r.message_fi) || L('That move is not possible right now.', 'Tämä siirto ei onnistu juuri nyt.')));
          }, function (e) { go.disabled = false; slot.replaceChildren(notice(failText(e), 'err')); });
        }
      } catch (e) { if (window.console) console.error(e); }
    });
    no.addEventListener('click', function () {
      no.disabled = true;
      post('/api/next-steps/dismiss', { id: s.id }).then(function () {
        c.remove();
        if (section && !section.querySelector('.wg-suggest')) section.hidden = true;
      }, function () { no.disabled = false; });
    });
    c.appendChild(h('div', { class: 'btn-row wg-actions' }, go, no));
    c.appendChild(slot);
    return c;
  }

  // ---------- the home page ----------
  var homeSeq = 0;
  function fetchJson(path) {
    try { return app().api(path).then(function (r) { return r; }, function () { return null; }); } catch (e) { return Promise.resolve(null); }
  }

  function home(box) {
    try {
      if (!box || !app()) return;
      var seq = ++homeSeq;
      Promise.all([fetchJson('/api/widgets'), fetchJson('/api/next-steps')]).then(function (res) {
        if (seq !== homeSeq || !box.isConnected) return;
        var frag = document.createDocumentFragment();
        try { drawWidgets(frag, res[0]); } catch (e) { if (window.console) console.error(e); }
        try { drawSuggest(frag, res[1]); } catch (e) { if (window.console) console.error(e); }
        clear(box);
        box.appendChild(frag);
        box.hidden = !box.firstChild;
      }).catch(function (e) { if (window.console) console.error(e); });
    } catch (e) { if (window.console) console.error(e); }
  }

  function drawWidgets(frag, data) {
    if (!data || !Array.isArray(data.widgets)) return;
    var ws = data.widgets.filter(function (w) { return w && typeof w === 'object' && w.data && typeof w.data === 'object'; });
    var plans = ws.filter(hasPlan), others = ws.filter(function (w) { return w.type !== 'plan'; });
    var have = {};
    ws.forEach(function (w) { have[w.type] = true; });
    var sec = h('section', { class: 'wg-section wg-plans', 'aria-label': L('Savings plans', 'Säästösuunnitelmat') });
    if (plans.length) {
      sec.appendChild(h('h2', { class: 'wg-h' }, 'Savings plans'));
      plans.forEach(function (w) { try { sec.appendChild(planCard(w)); } catch (e) { if (window.console) console.error(e); } });
    } else {
      sec.appendChild(emptyState());
    }
    if (others.length) {
      var grid = h('div', { class: 'wg-grid' });
      others.forEach(function (w) {
        try { var m = miniCard(w); if (m) grid.appendChild(m); } catch (e) { if (window.console) console.error(e); }
      });
      if (grid.firstChild) sec.appendChild(grid);
    }
    var canAdd = Array.isArray(data.can_add) ? data.can_add : [];
    var add = plans.length || canAdd.length ? addRow(plans.length ? canAdd : canAdd.filter(function (k) { return k !== 'plan'; }), have) : null;
    if (add) sec.appendChild(add);
    if (sec.firstChild) frag.appendChild(sec);
  }

  function drawSuggest(frag, data) {
    if (!data || !Array.isArray(data.steps)) return;
    var steps = data.steps.filter(function (s) { return s && s.id != null && s.action && (isStr(s.title) || isStr(s.title_fi)); }).slice(0, 3);
    if (!steps.length) return;
    var sec = h('section', { class: 'wg-section wg-suggests', 'aria-label': L('Svinkki suggests', 'Svinkki ehdottaa') });
    sec.appendChild(h('h2', { class: 'wg-h' }, 'Svinkki suggests'));
    steps.forEach(function (s) { try { sec.appendChild(suggestCard(s, sec)); } catch (e) { if (window.console) console.error(e); } });
    frag.appendChild(sec);
  }

  // ---------- chat: builder cards and "Add to home page" ----------
  window.SvinkkiCards = window.SvinkkiCards || {};
  function planCardFromData(d, subtitle) {
    var a = app();
    var needs = Array.isArray(d.needs) ? d.needs : [];
    if (needs.length) return null;
    var g = d.goal && typeof d.goal === 'object' ? d.goal : {};
    var target = n0(d.target) || n0(g.target);
    if (target <= 0) return null;
    var monthly = n0(d.monthly) || n0(d.monthly_needed);
    var c = h('section', { class: 'card wg wg-chat-plan' });
    c.appendChild(h('div', { class: 'card-head' }, h('div', { class: 'card-titles' },
      h('h3', { class: 'card-title' }, L('Savings plan', 'Säästösuunnitelma')),
      (d.name || g.name) ? h('span', { class: 'card-sub' }, String(d.name || g.name)) : null)));
    c.appendChild(builder({
      name: d.name || g.name || '', target: target, saved: n0(g.saved), monthly: monthly || undefined, deadline: d.deadline,
      note: pick(d.note, d.note_fi)
    }));
    return c;
  }
  window.SvinkkiCards.goal_plan = function (d) { try { return planCardFromData(d || {}); } catch (e) { return null; } };
  window.SvinkkiCards.plan_offer = function (d) { try { return planCardFromData(d || {}); } catch (e) { return null; } };

  function widgetFor(card) {
    var d = card && card.data ? card.data : {};
    var t = card && card.type;
    if (t === 'safe_to_spend') return { type: 'safe' };
    if (t === 'baskets' || t === 'overview') return { type: 'baskets' };
    if (t === 'spend') {
      var labels = (Array.isArray(d.by_label) ? d.by_label : []).filter(function (x) { return x && n0(x.total) > 0; });
      if (labels.length === 1 && isStr(labels[0].label)) return { type: 'category', params: { label: labels[0].label } };
    }
    return null;
  }

  function afterCard(node, card) {
    try {
      if (!node || !node.appendChild || !app()) return;
      var spec = widgetFor(card);
      if (!spec || node.querySelector('.wg-add-card')) return;
      var b = h('button', { type: 'button', class: 'btn secondary small-btn wg-add-card' }, 'Add to home page');
      b.addEventListener('click', function () {
        b.disabled = true;
        post('/api/widgets', spec).then(function (r) {
          if (r && r.widget) {
            b.textContent = L('On your home page', 'Etusivullasi');
            try { app().refreshHome(); } catch (e) { /* ignore */ }
          } else { b.disabled = false; }
        }, function () { b.disabled = false; });
      });
      node.appendChild(h('div', { class: 'wg-add-row' }, b));
    } catch (e) { if (window.console) console.error(e); }
  }

  window.SvinkkiWidgets = {
    home: home,
    afterCard: afterCard,
    _test: {
      monthsFor: monthsFor, addMonths: addMonths, monthsBetween: monthsBetween, sliderRange: sliderRange,
      clampMonthly: clampMonthly, defaultMonthly: defaultMonthly, projection: projection, widgetFor: widgetFor,
      hasPlan: hasPlan, statusLine: statusLine, ymOf: ymOf
    }
  };
})();
