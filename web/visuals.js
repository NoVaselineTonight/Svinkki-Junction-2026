/* Svinkki add-on: answer cards become a picture and one sentence.
   A small chart library for the five chart kinds (bars, hbars, line, split, progress) of the chart block a tool
   result may carry ({chart, caption, caption_fi}), and a visual card for every card type that can carry one:
   cardShell -> chart -> ONE sentence -> at most one key figure -> everything else behind "More".
   A card without a chart block returns null here and the built-in renderer draws it (story cards are tidied anyway).
   ES5, text nodes only, never markup. Defensive on purpose: any problem returns null and the old card is drawn. */
(function () {
  'use strict';

  // ---------- helpers ----------
  function A() { return window.SvinkkiApp || null; }
  function isFi() { try { var a = A(); return !!(a && a.isFi && a.isFi()); } catch (e) { return false; } }
  function T(s) { var a = A(); try { return a && a.T ? a.T(s) : s; } catch (e) { return s; } }
  function num(n) { n = Number(n); return isFinite(n) ? n : 0; }
  function isNum(n) { return n !== null && n !== undefined && n !== '' && isFinite(Number(n)); }
  function isStr(x) { return typeof x === 'string' && x.length > 0; }
  function cap(s) { s = String(s || ''); return s.charAt(0).toUpperCase() + s.slice(1); }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function f1(v) { return (Math.round(v * 10) / 10).toFixed(1); }
  function h() { var a = A(); return a.h.apply(null, arguments); }
  function svg(name, attrs) { return A().svgEl(name, attrs || {}); }
  function svgText(attrs, text) { var t = svg('text', attrs); t.textContent = text; return t; }

  // Text the server wrote in two languages: the Finnish one in Finnish mode, else the English one.
  function pickLang(en, fi) { return isFi() ? (isStr(fi) ? fi : '') : (isStr(en) ? en : ''); }

  // ---------- pure maths and labels (exported for tests) ----------
  // "August 2025" / "elokuu" -> "Aug" / "elo": the first word, three letters.
  function shortMonth(name) {
    var w = String(name || '').trim().split(/\s+/)[0] || '';
    return w.length > 3 ? w.slice(0, 3) : w;
  }

  function monthLabel(ym) {
    var a = A();
    if (!/^\d{4}-\d{2}/.test(String(ym || ''))) return '';
    return shortMonth(a && a.fmtMonth ? a.fmtMonth(ym) : ym);
  }

  function pointLabel(p) {
    if (!p) return '';
    if (isStr(p.ym)) return monthLabel(p.ym);
    var fi = isFi() && isStr(p.label_fi) ? p.label_fi : p.label;
    return isStr(fi) ? T(String(fi)) : '';
  }

  function fmtVal(v, unit) {
    var a = A();
    if (!isNum(v)) return '';
    if (unit === 'count') return String(Math.round(num(v)));
    if (unit === 'pct') return Math.round(num(v)) + (isFi() ? ' %' : '%');
    return a && a.money ? a.money(num(v)) : String(Math.round(num(v)));
  }

  // The largest value a scale must reach (never zero, so a division is always safe).
  function scaleMax(values) {
    var mx = 0;
    values.forEach(function (v) { if (isNum(v) && num(v) > mx) mx = num(v); });
    return mx > 0 ? mx : 1;
  }

  // Columns: slot width, bar width and the x of each bar for n points, one or two bars per point.
  function barGeometry(n, width, pad, two) {
    n = Math.max(1, n);
    var slot = (width - 2 * pad) / n;
    var bw = Math.min(two ? slot * 0.4 : slot * 0.62, 34);
    var gap = two ? 2 : 0;
    var groupW = two ? bw * 2 + gap : bw;
    function x(i, second) { return pad + i * slot + (slot - groupW) / 2 + (second ? bw + gap : 0); }
    return { slot: slot, bw: bw, x: x, centre: function (i) { return pad + i * slot + slot / 2; } };
  }

  // Which month labels are drawn under the columns: all up to 8, else every second one plus the marked and the last.
  function showLabelAt(i, n, marked) { return n <= 8 || marked || i === n - 1 || ((n - 1 - i) % 2 === 0); }

  // Smooth path through points [[x, y], ...]: cubic curves, control heights held between the neighbours so the
  // line never swings past a point (a balance that does not go below zero must not be drawn below zero).
  function smoothPath(pts) {
    if (!pts.length) return '';
    var d = 'M' + f1(pts[0][0]) + ',' + f1(pts[0][1]);
    for (var i = 0; i < pts.length - 1; i++) {
      var p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      var c1x = p1[0] + (p2[0] - p0[0]) / 6, c1y = p1[1] + (p2[1] - p0[1]) / 6;
      var c2x = p2[0] - (p3[0] - p1[0]) / 6, c2y = p2[1] - (p3[1] - p1[1]) / 6;
      var lo = Math.min(p1[1], p2[1]), hi = Math.max(p1[1], p2[1]);
      c1y = clamp(c1y, lo, hi); c2y = clamp(c2y, lo, hi);
      d += ' C' + f1(c1x) + ',' + f1(c1y) + ' ' + f1(c2x) + ',' + f1(c2y) + ' ' + f1(p2[0]) + ',' + f1(p2[1]);
    }
    return d;
  }

  // The tone class of a point: marked points stand out, the rest of a marked chart is muted.
  function toneOf(p, anyMark) {
    var t = p && p.tone;
    if (t === 'good' || t === 'warn' || t === 'muted') return t;
    if (anyMark) return p && p.mark ? 'main' : 'muted';
    return 'main';
  }

  var KINDS = { bars: 1, hbars: 1, line: 1, split: 1, progress: 1 };

  // A chart block is drawn only when it is a known kind with enough data; anything else -> null (old card).
  function validChart(ch) {
    if (!ch || typeof ch !== 'object' || !KINDS[ch.kind]) return null;
    var s = Array.isArray(ch.series) ? ch.series.filter(function (p) { return p && typeof p === 'object' && isNum(p.value); }) : [];
    if (ch.kind === 'progress') {
      var now = isNum(ch.now) ? num(ch.now) : (s.length ? num(s[0].value) : null);
      return now !== null && num(ch.target) > 0 ? { kind: 'progress', unit: ch.unit, now: now, target: num(ch.target), series: s, legend: ch.legend } : null;
    }
    if ((ch.kind === 'bars' || ch.kind === 'line') && s.length < 2) return null;
    if (ch.kind === 'hbars' && s.length < 1) return null;
    if (ch.kind === 'split') {
      s = s.filter(function (p) { return num(p.value) > 0; });
      if (s.length < 2) return null;
    }
    var max = ch.kind === 'bars' || ch.kind === 'line' ? 12 : (ch.kind === 'hbars' ? 6 : 5);
    return { kind: ch.kind, unit: ch.unit, series: s.slice(0, max), legend: ch.legend, target: isNum(ch.target) ? num(ch.target) : null };
  }

  function captionOf(d) { return pickLang(d && d.caption, d && d.caption_fi); }

  // A spoken summary of the data: "Aug: 93 €, Sep: 120 €".
  function summaryOf(ch) {
    return ch.series.map(function (p) {
      var l = pointLabel(p);
      return (l ? l + ': ' : '') + fmtVal(p.value, ch.unit) + (isNum(p.value2) ? ' / ' + fmtVal(p.value2, ch.unit) : '');
    }).join(', ');
  }

  // ---------- charts ----------
  var uid = 0;
  var W = 280;

  function legendNode(items) {
    return h('div', { class: 'vz-legend' }, items.map(function (it) {
      return h('span', { class: 'vz-leg-item' }, h('span', { class: 'vz-dot ' + it[0], 'aria-hidden': 'true' }), it[1]);
    }));
  }

  function legendText(ch, key) {
    var lg = ch.legend || {};
    return pickLang(lg[key], lg[key + '_fi']) || (isFi() ? '' : String(lg[key] || ''));
  }

  function barsChart(ch, label) {
    var s = ch.series, n = s.length;
    var two = s.some(function (p) { return isNum(p.value2); });
    var anyMark = s.some(function (p) { return p.mark; });
    var H = 144, top = 24, base = 120, plot = base - top;
    var vals = [];
    s.forEach(function (p) { vals.push(p.value); if (two) vals.push(p.value2); });
    if (ch.target !== null) vals.push(ch.target);
    var mx = scaleMax(vals);
    var g = barGeometry(n, W, 6, two);
    var el = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, class: 'vz-svg vz-bars', role: 'img', 'aria-label': label, focusable: 'false' });
    function Y(v) { return base - clamp(num(v), 0, mx) / mx * plot; }
    el.appendChild(svg('line', { x1: 0, x2: W, y1: base, y2: base, class: 'vz-axis' }));
    var labelled = anyMark ? -1 : n - 1;
    s.forEach(function (p, i) {
      var tone = toneOf(p, anyMark);
      var y = Y(p.value), hgt = Math.max(num(p.value) > 0 ? 2 : 0, base - y);
      var r = svg('rect', { x: f1(g.x(i, false)), y: f1(base - hgt), width: f1(g.bw), height: f1(hgt), rx: 3, class: 'vz-bar vz-t-' + tone + (p.mark ? ' vz-mark' : '') });
      var tt = svg('title', {}); tt.textContent = pointLabel(p) + ' ' + fmtVal(p.value, ch.unit);
      r.appendChild(tt);
      el.appendChild(r);
      if (two && isNum(p.value2)) {
        var y2 = Y(p.value2), h2 = Math.max(num(p.value2) > 0 ? 2 : 0, base - y2);
        el.appendChild(svg('rect', { x: f1(g.x(i, true)), y: f1(base - h2), width: f1(g.bw), height: f1(h2), rx: 3, class: 'vz-bar vz-two' }));
      }
      var cx = g.centre(i);
      if (p.mark || i === labelled) {
        var txt = fmtVal(p.value, ch.unit), tw = txt.length * 7.2;
        var tx = clamp(cx, tw / 2 + 2, W - tw / 2 - 2);
        el.appendChild(svgText({ x: f1(tx), y: f1(Math.max(13, y - 5)), 'text-anchor': 'middle', class: 'vz-val' }, txt));
      }
      var lab = pointLabel(p);
      if (lab && showLabelAt(i, n, p.mark)) {
        el.appendChild(svgText({ x: f1(cx), y: H - 6, 'text-anchor': 'middle', class: 'vz-lab' + (p.mark ? ' vz-lab-strong' : '') }, lab));
      }
    });
    if (ch.target !== null) {
      var ty = Y(ch.target);
      el.appendChild(svg('line', { x1: 0, x2: W, y1: f1(ty), y2: f1(ty), class: 'vz-target' }));
      el.appendChild(svgText({ x: 2, y: f1(Math.max(12, ty - 4)), 'text-anchor': 'start', class: 'vz-lab vz-target-lab' }, fmtVal(ch.target, ch.unit)));
    }
    var wrap = h('div', { class: 'vz vz-bars-wrap' }, el);
    if (two) wrap.appendChild(legendNode([['vz-c-main', legendText(ch, 'value')], ['vz-c-two', legendText(ch, 'value2')]]));
    return wrap;
  }

  function hbarsChart(ch, label) {
    var s = ch.series;
    var vals = [];
    s.forEach(function (p) { vals.push(p.value); if (isNum(p.value2)) vals.push(p.value2); });
    var mx = scaleMax(vals);
    var two = s.some(function (p) { return isNum(p.value2); });
    var wrap = h('div', { class: 'vz vz-hbars', role: 'group', 'aria-label': label });
    s.forEach(function (p, i) {
      var tone = toneOf(p, false);
      var pctv = clamp(num(p.value) / mx * 100, num(p.value) > 0 ? 1.5 : 0, 100);
      var bar = svg('svg', { viewBox: '0 0 100 10', preserveAspectRatio: 'none', class: 'vz-hbar-svg', 'aria-hidden': 'true', focusable: 'false' });
      bar.appendChild(svg('rect', { x: 0, y: 0, width: 100, height: 10, class: 'vz-hbar-track' }));
      bar.appendChild(svg('rect', { x: 0, y: 0, width: f1(pctv), height: 10, class: 'vz-bar vz-t-' + (tone === 'muted' && !p.tone ? 'main' : tone) }));
      if (isNum(p.value2)) {
        var mxp = clamp(num(p.value2) / mx * 100, 0, 99.4);
        bar.appendChild(svg('line', { x1: f1(mxp), x2: f1(mxp), y1: -1, y2: 11, class: 'vz-hmark', 'vector-effect': 'non-scaling-stroke' }));
      }
      wrap.appendChild(h('div', { class: 'vz-hrow' },
        h('span', { class: 'vz-hlabel' }, pointLabel(p) || ('#' + (i + 1))),
        h('span', { class: 'vz-hbar' }, bar),
        h('span', { class: 'vz-hval' }, fmtVal(p.value, ch.unit))));
    });
    if (two) wrap.appendChild(h('div', { class: 'vz-legend' },
      h('span', { class: 'vz-leg-item' }, h('span', { class: 'vz-dot vz-c-main', 'aria-hidden': 'true' }), legendText(ch, 'value') || 'You'),
      h('span', { class: 'vz-leg-item' }, h('span', { class: 'vz-tick', 'aria-hidden': 'true' }), legendText(ch, 'value2') || 'Typical')));
    return wrap;
  }

  function lineChart(ch, label) {
    var s = ch.series, n = s.length;
    var H = 134, padX = 10, top = 26, bot = 112;
    var vals = s.map(function (p) { return num(p.value); });
    if (ch.target !== null) vals.push(ch.target);
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
    var neg = lo < 0;
    var span = (hi - lo) || 1;
    lo -= span * 0.06; hi += span * 0.06;
    if (neg && hi < 0) hi = 0;
    function X(i) { return padX + i * (W - 2 * padX) / (n - 1); }
    function Y(v) { return top + (bot - top) * (1 - (v - lo) / (hi - lo)); }
    var pts = s.map(function (p, i) { return [X(i), Y(num(p.value))]; });
    var el = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, class: 'vz-svg vz-line-svg', role: 'img', 'aria-label': label, focusable: 'false' });
    var d = smoothPath(pts);
    var zy = Y(0);
    if (neg) {
      uid++;
      var idA = 'vzc-a' + uid, idB = 'vzc-b' + uid;
      var defs = svg('defs', {});
      var cpA = svg('clipPath', { id: idA }); cpA.appendChild(svg('rect', { x: 0, y: 0, width: W, height: f1(zy) }));
      var cpB = svg('clipPath', { id: idB }); cpB.appendChild(svg('rect', { x: 0, y: f1(zy), width: W, height: f1(H - zy) }));
      defs.appendChild(cpA); defs.appendChild(cpB);
      el.appendChild(defs);
      el.appendChild(svg('line', { x1: 0, x2: W, y1: f1(zy), y2: f1(zy), class: 'vz-zero' }));
      el.appendChild(svgText({ x: W - 2, y: f1(Math.min(bot + 10, zy - 4)), 'text-anchor': 'end', class: 'vz-lab vz-zero-lab' }, fmtVal(0, ch.unit)));
      el.appendChild(svg('path', { d: d, class: 'vz-line', 'clip-path': 'url(#' + idA + ')' }));
      el.appendChild(svg('path', { d: d, class: 'vz-line vz-line-neg', 'clip-path': 'url(#' + idB + ')' }));
    } else {
      el.appendChild(svg('path', { d: d, class: 'vz-line' }));
    }
    if (ch.target !== null) {
      var ty = Y(ch.target);
      el.appendChild(svg('line', { x1: 0, x2: W, y1: f1(ty), y2: f1(ty), class: 'vz-target' }));
      el.appendChild(svgText({ x: 2, y: f1(Math.max(12, ty - 4)), 'text-anchor': 'start', class: 'vz-lab vz-target-lab' }, fmtVal(ch.target, ch.unit)));
    }
    s.forEach(function (p, i) {
      if (p.mark) el.appendChild(svg('circle', { cx: f1(pts[i][0]), cy: f1(pts[i][1]), r: 4.5, class: 'vz-pt vz-pt-mark' }));
    });
    function endLabel(i, anchor) {
      var neg1 = num(s[i].value) < 0;
      el.appendChild(svg('circle', { cx: f1(pts[i][0]), cy: f1(pts[i][1]), r: 3.5, class: 'vz-pt' + (neg1 ? ' vz-pt-neg' : '') }));
      var ty = pts[i][1] - 8;
      if (ty < 12) ty = pts[i][1] + 16;
      el.appendChild(svgText({ x: f1(pts[i][0]), y: f1(ty), 'text-anchor': anchor, class: 'vz-val' }, fmtVal(s[i].value, ch.unit)));
    }
    endLabel(0, 'start');
    endLabel(n - 1, 'end');
    [0, n >= 5 ? Math.floor((n - 1) / 2) : -1, n - 1].forEach(function (i, k) {
      if (i < 0) return;
      var l = pointLabel(s[i]);
      if (l) el.appendChild(svgText({ x: f1(pts[i][0]), y: H - 4, 'text-anchor': k === 0 ? 'start' : (k === 2 ? 'end' : 'middle'), class: 'vz-lab' }, l));
    });
    return h('div', { class: 'vz vz-line-wrap' }, el);
  }

  function splitChart(ch, label) {
    var s = ch.series;
    var total = 0;
    s.forEach(function (p) { total += num(p.value); });
    var el = svg('svg', { viewBox: '0 0 ' + W + ' 18', preserveAspectRatio: 'none', class: 'vz-svg vz-split-bar', role: 'img', 'aria-label': label, focusable: 'false' });
    var x = 0;
    var cls = [];
    s.forEach(function (p, i) {
      var w = num(p.value) / total * W;
      var c = p.tone === 'good' || p.tone === 'warn' || p.tone === 'muted' ? 'vz-t-' + p.tone : 'vz-c' + (i % 5);
      cls.push(c);
      el.appendChild(svg('rect', { x: f1(x), y: 0, width: f1(Math.max(0, w)), height: 18, class: 'vz-seg ' + c }));
      x += w;
    });
    var list = h('ul', { class: 'vz-split-list' });
    s.forEach(function (p, i) {
      list.appendChild(h('li', null,
        h('span', { class: 'vz-dot ' + cls[i], 'aria-hidden': 'true' }),
        h('span', { class: 'vz-hlabel' }, pointLabel(p) || ('#' + (i + 1))),
        h('span', { class: 'vz-hval' }, fmtVal(p.value, ch.unit)),
        h('span', { class: 'vz-share' }, Math.round(num(p.value) / total * 100) + (isFi() ? ' %' : '%'))));
    });
    return h('div', { class: 'vz vz-split' }, h('div', { class: 'vz-split-wrap' }, el), list);
  }

  function progressChart(ch, label) {
    var frac = clamp(ch.now / ch.target, 0, 1);
    var R = 40, C = 2 * Math.PI * R;
    var el = svg('svg', { viewBox: '0 0 100 100', class: 'vz-svg vz-ring', role: 'img', 'aria-label': label, focusable: 'false' });
    el.appendChild(svg('circle', { cx: 50, cy: 50, r: R, class: 'vz-ring-track' }));
    if (frac > 0) {
      el.appendChild(svg('circle', { cx: 50, cy: 50, r: R, class: 'vz-ring-fill', 'stroke-dasharray': f1(frac * C) + ' ' + f1(C), transform: 'rotate(-90 50 50)' }));
    }
    el.appendChild(svgText({ x: 50, y: 57, 'text-anchor': 'middle', class: 'vz-ring-num' }, Math.round(frac * 100) + (isFi() ? ' %' : '%')));
    return h('div', { class: 'vz vz-progress' }, el,
      h('div', { class: 'vz-progress-text' },
        h('span', { class: 'vz-progress-now' }, fmtVal(ch.now, ch.unit)),
        h('span', { class: 'vz-progress-of' }, (isFi() ? 'tavoite ' : 'of ') + fmtVal(ch.target, ch.unit))));
  }

  // drawChart(chart, opts) -> DOM node or null. opts.caption is the sentence the picture is labelled with.
  function drawChart(chart, opts) {
    var ch = validChart(chart);
    if (!ch) return null;
    opts = opts || {};
    var label = (opts.caption ? opts.caption + ' ' : '') + (ch.kind === 'progress' ? fmtVal(ch.now, ch.unit) + ' / ' + fmtVal(ch.target, ch.unit) : summaryOf(ch));
    try {
      if (ch.kind === 'bars') return barsChart(ch, label);
      if (ch.kind === 'hbars') return hbarsChart(ch, label);
      if (ch.kind === 'line') return lineChart(ch, label);
      if (ch.kind === 'split') return splitChart(ch, label);
      return progressChart(ch, label);
    } catch (e) { if (window.console) console.error(e); return null; }
  }

  // ---------- the visual card ----------
  var STORY = {
    money_story: 'Your year in money', season_outlook: 'The months ahead', category_story: 'One category over time',
    explain_month: 'Your month explained', low_points: 'Your lowest points', income_profile: 'Your income',
    receipt_trends: 'What your receipts show', basket_profile: 'Your grocery trips', cut_ideas: 'Where groceries could give',
    findings: 'Worth knowing'
  };

  function rowsNode(list) {
    var box = h('div', { class: 'rows' });
    (list || []).filter(Boolean).forEach(function (r) {
      box.appendChild(h('div', { class: 'row' }, h('span', { class: 'row-label' }, r[0]), h('span', { class: 'row-val' }, r[1])));
    });
    return box.childNodes.length ? box : null;
  }
  function eyebrow(text) { return h('p', { class: 'eyebrow' }, text); }
  function money(v, exact) { return A().money(num(v), exact ? { exact: true } : null); }
  function euros(v) { return A().euros(num(v)); }
  function labelOf(x) {
    if (!x) return '';
    var l = isFi() && isStr(x.label_fi) ? x.label_fi : (x.label || x.name || '');
    return T(String(l));
  }

  function periodSub(p) {
    var a = A();
    if (!p || !p.from) return '';
    var f = String(p.from).slice(0, 10), t = String(p.to || p.from).slice(0, 10);
    if (f === t) return a.fmtDate(f);
    var m = /^(\d{4})-(\d{2})-01$/.exec(f), m2 = /^(\d{4})-(\d{2})-(\d{2})$/.exec(t);
    if (m && m2 && m[1] === m2[1] && m[2] === m2[2] && Number(m2[3]) === new Date(Date.UTC(Number(m2[1]), Number(m2[2]), 0)).getUTCDate()) return a.fmtMonth(m[1] + '-' + m[2]);
    return a.fmtDate(f) + (isFi() ? '–' : ' to ') + a.fmtDate(t);
  }

  // Per card type: title, sub (quiet line), key (the one figure) and more (the old rows and notes).
  var VERDICT = { yes: ['Yes', 'v-yes'], tight: ['Tight', 'v-tight'], no: ['Not right now', 'v-no'], caution: ['Think twice', 'v-caution'] };
  var SPECS = {
    spend: {
      title: function (d) {
        var ls = (d.by_label || []).filter(function (x) { return num(x.total) > 0; });
        return ls.length === 1 && ls[0].label ? cap(labelOf(ls[0])) : 'Spending';
      },
      sub: function (d) { return periodSub(d.period); },
      key: function (d) { return [money(d.total, true), num(d.count) + (num(d.count) === 1 ? ' payment' : ' payments')]; },
      more: function (d) {
        var ls = (d.by_label || []).filter(function (x) { return num(x.total) > 0; }).slice(0, 8);
        return ls.length > 1 ? [rowsNode(ls.map(function (x) { return [labelOf(x), money(x.total)]; }))] : [];
      }
    },
    overview: {
      title: function () { return 'Your month'; },
      sub: function (d) { return d.month ? A().fmtMonth(d.month) : ''; },
      key: function (d) { return [money(d.surplus), num(d.surplus) >= 0 ? 'left over' : 'more out than in']; },
      more: function (d) {
        var tl = (d.top_labels || []).slice(0, 3);
        return [rowsNode([['Money in', money(d.income)], ['Spent', money(d.spent)], num(d.saved) > 0 ? ['Saved', money(d.saved)] : null]),
          tl.length ? [eyebrow('Biggest areas'), rowsNode(tl.map(function (x) { return [labelOf(x), money(x.total)]; }))] : null];
      }
    },
    baskets: {
      title: function () { return 'Three baskets'; },
      sub: function (d) { return periodSub(d.period); },
      key: null,
      more: function (d) {
        var bs = (d.baskets || []).filter(function (b) { return b && isNum(b.total); });
        return [rowsNode(bs.map(function (b) { return [T(String(b.name || b.key || '')), money(b.total)]; }))];
      }
    },
    safe_to_spend: {
      title: function () { return 'Safe to spend'; },
      sub: function (d) { return d.next_payday ? ('Next payday ' + A().fmtDate(d.next_payday)) : ''; },
      key: function (d) {
        if (num(d.safe_total) < 0 || num(d.per_day) < 0) return ['€0', 'safe to spend before payday', 'warn'];
        return [euros(d.per_week), 'this week'];
      },
      more: function (d) {
        var bills = d.upcoming_bills || [];
        return [rowsNode([['A day', A().money(num(d.per_day), { hero: true })], ['Money in your account', money(d.balance, true)],
          ['Bills before payday', '-' + money(d.bills_total)], ['Buffer for surprises', '-' + money(d.unexpected_buffer)],
          num(d.planned_savings) > 0 ? ['Planned savings', '-' + money(d.planned_savings)] : null, ['Safe to spend', money(d.safe_total)]]),
          bills.length ? [eyebrow('Bills before payday'), rowsNode(bills.map(function (b) { return [T(String(b.label || 'Bill')) + (b.due ? ', ' + A().fmtDate(b.due) : ''), money(b.expected)]; }))] : null];
      }
    },
    afford: {
      title: function () { return 'Can I afford it?'; },
      sub: function (d) { return d.item ? cap(T(String(d.item))) + (isNum(d.price) ? ', ' + money(d.price, Math.round(num(d.price) * 100) % 100 !== 0) : '') : ''; },
      key: function (d) { var v = VERDICT[d.verdict] || VERDICT.tight; return [v[0], '', '', v[1]]; },
      more: function (d) {
        var alts = (d.alternatives || []).filter(isStr);
        var ge = d.goal_effect;
        return [rowsNode([d.per_day_after != null && d.risk !== 'loan' ? ['Left a day after it', money(d.per_day_after)] : null,
          d.next_payday ? ['Until payday', A().fmtDate(d.next_payday)] : null,
          d.safe_total != null ? ['Safe to spend before it', money(d.safe_total)] : null, d.after != null ? ['Left until payday', money(d.after)] : null]),
          d.verdict_text ? h('p', { class: 'small' }, d.verdict_text) : null,
          alts.length ? h('ul', { class: 'plain-list' }, alts.map(function (a) { return h('li', null, a); })) : null,
          ge && ge.delay_text ? h('p', { class: 'goal-line' }, ge.delay_text) : null];
      }
    },
    what_if: {
      title: function (d) { return d.direction === 'increase' || num(d.saved_monthly) < 0 ? 'If you spent more' : 'If you spent less'; },
      sub: function () { return ''; },
      key: function (d) {
        var more = d.direction === 'increase' || num(d.saved_monthly) < 0;
        return more ? [euros(-num(d.saved_monthly) * 12), 'extra a year'] : [euros(num(d.saved_monthly) * 12), 'saved a year'];
      },
      more: function (d) {
        return [rowsNode([['A month', money(Math.abs(num(d.saved_monthly)))], ['Spending a month', euros(d.baseline_monthly) + ' → ' + euros(d.new_monthly)]]),
          rowsNode((d.lines || []).map(function (l) { return [T(String(l.target || '')), euros(l.baseline) + ' → ' + euros(l.new)]; }))];
      }
    },
    save_more: {
      title: function () { return 'Ways to save more'; },
      sub: function () { return ''; },
      key: null,
      more: function (d) {
        var ideas = d.ideas || [];
        return [ideas.map(function (i) {
          return h('div', { class: 'idea' }, h('b', null, i.title), i.saved_monthly != null ? h('p', { class: 'small' }, money(i.saved_monthly) + ' a month') : null);
        })];
      }
    },
    spender_type: {
      title: function () { return 'Your spender type'; },
      sub: function () { return ''; },
      key: function (d) { return [T(String(d.type || d.title || '')), '']; },
      more: function (d) {
        return [rowsNode((d.traits || []).map(function (tr) { return [T(String(tr.note || tr.name || '')), (Math.round(num(tr.value) * 10) / 10) + '% of income']; })),
          isFi() ? null : (d.summary ? h('p', { class: 'small' }, d.summary) : null)];
      }
    },
    averages: {
      title: function (d) { return d.title ? T(String(d.title)) : 'What is typical?'; },
      sub: function (d) { var g = d.group || {}; return g.n ? g.n + ' people' : ''; },
      key: null,
      more: function (d) {
        return [rowsNode((d.rows || []).slice(0, 4).map(function (r) {
          var eur = /eur/i.test(String(r.unit || ''));
          var f = function (v) { return eur ? euros(v) : String(Math.round(num(v) * 10) / 10); };
          return [T(String(r.name || '')), f(r.you) + ' / ' + f(r.typical)];
        }))];
      }
    },
    benchmarks: {
      title: function () { return 'You and people like you'; },
      sub: function (d) { var g = d.group || {}; return g.n ? g.n + ' people' : ''; },
      key: null,
      more: function (d) {
        return [rowsNode((d.rows || []).map(function (r) { return [T(String(r.name || '')), euros(r.you) + ' / ' + euros(r.median)]; }))];
      }
    },
    leaks: {
      title: function () { return 'Small leaks'; },
      sub: function (d) { return periodSub(d.period); },
      key: function (d) {
        var sm = d.small || {};
        return [money(sm.per_month != null ? sm.per_month : sm.total), (sm.per_month != null ? 'a month' : 'in total') + ' on purchases under ' + euros(sm.threshold != null ? sm.threshold : 10)];
      },
      more: function (d) {
        var sm = d.small || {}, subs = d.subscriptions || [];
        return [rowsNode([['Small buys', String(num(sm.count))],
          ['Forgotten subscriptions', subs.length ? subs.length + (subs.length === 1 ? ' repeating charge' : ' repeating charges') : 'None found']]),
          subs.length ? [eyebrow('Repeating charges'), rowsNode(subs.map(function (x) { return [T(String(x.label || 'Repeating charge')), money(x.amount) + ' a month']; }))] : null];
      }
    },
    receipt_insights: {
      title: function () { return 'What you buy'; },
      sub: function (d) { return d.period && d.period.label ? '' : periodSub(d.period); },
      key: null,
      more: function (d) {
        var gs = (d.by_group || []).filter(function (g) { return num(g.total) > 0; }).slice(0, 8);
        return [gs.length ? [eyebrow('By product group'), rowsNode(gs.map(function (g) { return [T(String(g.name || g.group || '')), money(g.total)]; }))] : null];
      }
    }
  };
  Object.keys(STORY).forEach(function (k) {
    SPECS[k] = { story: true, title: function (d) { return k === 'category_story' && d.label ? cap(labelOf({ label: d.label, label_fi: d.label_fi })) + ' over time' : STORY[k]; },
      sub: function (d) { return k === 'explain_month' && d.month ? A().fmtMonth(d.month) : ''; }, key: null, more: function () { return []; } };
  });

  // The short sentences a story card carries: highlights, or the texts of findings, or idea titles.
  function highlightsOf(d, fi) {
    var list = fi ? d.highlights_fi : d.highlights;
    var out = [];
    (Array.isArray(list) ? list : []).forEach(function (x) { if (isStr(x)) out.push(x); });
    if (!out.length && !fi) {
      (Array.isArray(d.findings) ? d.findings : []).forEach(function (f) { if (f && isStr(f.text)) out.push(f.text); });
      if (!out.length) (Array.isArray(d.ideas) ? d.ideas : []).forEach(function (f) { if (f && isStr(f.title)) out.push(f.title + (isStr(f.detail) ? ': ' + f.detail : '')); });
    }
    return out;
  }

  function visualCard(type, d, card) {
    var spec = SPECS[type], a = A();
    if (!spec || !a || !d || typeof d !== 'object') return null;
    var caption = captionOf(d);
    var fi = isFi();
    var drawn = d.chart ? drawChart(d.chart, { caption: caption }) : null;
    var hl = [];
    if (spec.story) {
      hl = fi && highlightsOf(d, true).length ? highlightsOf(d, true) : highlightsOf(d, false);
      if (!drawn && !hl.length) return null;
    } else if (!drawn) {
      return null;
    }
    if (!d.evidence && card && card.evidence) d = Object.assign({}, d, { evidence: card.evidence });

    var c = a.cardShell(spec.title(d), spec.sub(d) || '', 'visual-card vz-card' + (drawn ? '' : ' vz-textcard'));
    if (drawn) c.appendChild(h('div', { class: 'vz-figure' }, drawn));

    // ONE sentence. Finnish mode never shows an English server sentence here.
    var sentence = caption;
    var detail = hl.slice();
    if (!sentence && spec.story && hl.length) {
      var hlFi = highlightsOf(d, true), shownFi = fi && hlFi.length;
      if (!fi || shownFi) { sentence = hl[0]; detail = hl.slice(1); }
    }
    if (sentence) c.appendChild(h('p', { class: 'vz-caption' }, sentence));

    var k = spec.key ? spec.key(d) : null;
    if (k) {
      if (k[3]) c.appendChild(h('div', { class: 'verdict ' + k[3] }, k[0]));
      else a.keyFig(c, k[0], k[1] ? k[1] : null, k[2] || '');
    }

    var nodes = [];
    try { nodes = spec.more(d) || []; } catch (e) { nodes = []; }
    if (detail.length) nodes.push(h('ul', { class: 'plain-list' }, detail.map(function (x) { return h('li', null, x); })));
    if (spec.story && d.note && !fi) nodes.push(h('p', { class: 'tiny' }, String(d.note)));
    a.more(c, nodes, d);
    return c;
  }

  // ---------- Finnish for what this file writes ----------
  var FI = {
    'More': 'Lisää', 'Spending': 'Kulutus', 'Safe to spend': 'Käyttövara', 'The months ahead': 'Tulevat kuukaudet',
    'Your month explained': 'Kuukautesi selitettynä', 'Your year in money': 'Vuotesi rahassa', 'Your month': 'Kuukautesi',
    'Three baskets': 'Kolme koria', 'Can I afford it?': 'Onko siihen varaa?', 'If you spent less': 'Jos kuluttaisit vähemmän',
    'If you spent more': 'Jos kuluttaisit enemmän', 'Ways to save more': 'Tapoja säästää enemmän',
    'Your spender type': 'Kuluttajatyyppisi', 'You and people like you': 'Sinä ja samanlaiset ihmiset',
    'What is typical?': 'Mikä on tavallista?', 'Small leaks': 'Pienet vuodot', 'What you buy': 'Mitä ostat',
    'One category over time': 'Luokka ajan mittaan', 'Your lowest points': 'Alimmat pisteesi', 'Your income': 'Tulosi',
    'What your receipts show': 'Mitä kuittisi kertovat', 'Your grocery trips': 'Ruokakauppakäyntisi',
    'Where groceries could give': 'Mistä ruokakuluista voisi joustaa', 'Worth knowing': 'Hyvä tietää',
    'Yes': 'Kyllä', 'Tight': 'Tiukka', 'Not right now': 'Ei juuri nyt', 'Think twice': 'Harkitse tarkkaan',
    'left over': 'jää yli', 'more out than in': 'enemmän ulos kuin sisään', 'this week': 'tällä viikolla',
    'safe to spend before payday': 'käyttövaraa ennen palkkapäivää', 'extra a year': 'ylimääräistä vuodessa',
    'saved a year': 'säästyy vuodessa', 'a month': 'kuukaudessa', 'in total': 'yhteensä',
    'payment': 'maksu', 'payments': 'maksua', 'Money in': 'Tulot', 'Spent': 'Menot', 'Saved': 'Säästetty',
    'Biggest areas': 'Suurimmat osiot', 'A day': 'Päivässä', 'Money in your account': 'Tilillä oleva raha',
    'Bills before payday': 'Laskut ennen palkkapäivää', 'Buffer for surprises': 'Puskuri yllätyksille',
    'Planned savings': 'Suunnitellut säästöt', 'Left a day after it': 'Päivässä jäljellä sen jälkeen',
    'Until payday': 'Palkkapäivään', 'Safe to spend before it': 'Käyttövara ennen sitä', 'Left until payday': 'Jäljellä palkkapäivään',
    'A month': 'Kuukaudessa', 'Spending a month': 'Kulutus kuukaudessa', 'Small buys': 'Pienostokset',
    'Forgotten subscriptions': 'Unohtuneet tilaukset', 'None found': 'Ei löytynyt', 'Repeating charges': 'Toistuvat veloitukset',
    'Repeating charge': 'Toistuva veloitus', 'repeating charge': 'toistuva veloitus', 'repeating charges': 'toistuvaa veloitusta',
    'By product group': 'Tuoteryhmittäin', 'Bill': 'Lasku', 'Next payday': 'Seuraava palkkapäivä',
    'Groceries': 'Ruokaostokset', 'Restaurant': 'Ravintolat', 'Fast food': 'Pikaruoka', 'Taxi': 'Taksit', 'Housing': 'Asuminen',
    'Utilities': 'Käyttömaksut', 'Fuel': 'Polttoaine', 'Public transport': 'Julkinen liikenne', 'Travel': 'Matkustus',
    'Events': 'Tapahtumat', 'Parking': 'Pysäköinti', 'Hobbies': 'Harrastukset', 'Home improvement': 'Kodin remontointi',
    'Regular essentials': 'Perusmenot', 'Unexpected necessities': 'Odottamattomat menot',
    'Everyday spending': 'Arkikulutus', 'Savings': 'Säästöt', 'Saver': 'Säästäjä', 'Kept': 'Jäänyt käteen',
    'Going out': 'Menot', 'Social spending': 'Seurallinen kulutus'
  };
  var FI_PATTERNS = [
    [/^(.+) over time$/, '$1 ajan mittaan'],
    [/^(\d+) people$/, '$1 ihmistä'],
    [/^(\d+(?:\.\d+)?)% of income$/, '$1 % tuloista'],
    [/^(\d+) payments?$/, '$1 maksua'],
    [/^(.+) a month$/, '$1 kuukaudessa'],
    [/^(\d+) repeating charges?$/, '$1 toistuvaa veloitusta'],
    [/^Next payday (.+)$/, 'Seuraava palkkapäivä $1'],
    [/^(.+) on purchases under (.+)$/, '$1 alle $2 ostoksiin'],
    [/^(.+) a month on purchases under (.+)$/, '$1 kuukaudessa alle $2 ostoksiin']
  ];
  try { if (window.SvI18n && window.SvI18n.add) window.SvI18n.add(FI, FI_PATTERNS); } catch (e) { /* the interface stays English */ }

  // ---------- register ----------
  window.SvinkkiCards = window.SvinkkiCards || {};
  Object.keys(SPECS).forEach(function (type) {
    if (window.SvinkkiCards[type]) return;
    window.SvinkkiCards[type] = function (data, card) { return visualCard(type, data, card); };
  });

  window.SvinkkiVisuals = {
    drawChart: drawChart,
    visualCard: visualCard,
    _test: {
      shortMonth: shortMonth, monthLabel: monthLabel, fmtVal: fmtVal, scaleMax: scaleMax, barGeometry: barGeometry,
      showLabelAt: showLabelAt, smoothPath: smoothPath, toneOf: toneOf, validChart: validChart, summaryOf: summaryOf,
      captionOf: captionOf, highlightsOf: highlightsOf, FI: FI, FI_PATTERNS: FI_PATTERNS, SPECS: SPECS
    }
  };
})();
