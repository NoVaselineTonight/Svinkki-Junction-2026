/* Svinkki add-on: what is behind each figure of an answer.
   app.js calls window.SvinkkiExtras.afterReply(messageElement, apiResponse) for every answer it draws.
   Every figure in a model answer is a slot filled in by code (app/grounding.py) and comes back as res.figures.
   Here each one becomes a tappable figure that says, in plain words, where it comes from.
   Defensive on purpose: any problem leaves the answer exactly as it was. Text nodes only, never markup. */
(function () {
  'use strict';

  // ---------- pure helpers (also exported for tests) ----------
  var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
    'November', 'December'];
  var MON3 = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  function isStr(x) { return typeof x === 'string' && x.length > 0; }

  function parseDay(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || ''));
    if (!m) return null;
    var y = +m[1], mo = +m[2], d = +m[3];
    if (mo < 1 || mo > 12 || d < 1 || d > 31) return null;
    return { y: y, m: mo, d: d };
  }
  function lastDay(y, m) { return new Date(Date.UTC(y, m, 0)).getUTCDate(); }

  // "August 2026" for a whole month, "1 Aug to 14 Aug 2026" otherwise, '' when unknown.
  function periodText(from, to) {
    var a = parseDay(from), b = parseDay(to);
    if (!a || !b) return '';
    if (a.y === b.y && a.m === b.m && a.d === 1 && b.d === lastDay(b.y, b.m)) return MONTHS[a.m - 1] + ' ' + a.y;
    if (a.y === b.y && a.m === b.m && a.d === b.d) return a.d + ' ' + MON3[a.m - 1] + ' ' + a.y;
    return a.d + ' ' + MON3[a.m - 1] + (a.y !== b.y ? ' ' + a.y : '') + ' to ' + b.d + ' ' + MON3[b.m - 1] + ' ' + b.y;
  }

  // The label is written by code for tools ("total, category Taxi, one month, 2026-08"). Drop what looks like a
  // field path or a bare technical word and keep what a customer can read.
  function cleanLabel(label) {
    if (!isStr(label)) return '';
    var keep = [];
    String(label).split(',').forEach(function (p) {
      p = p.trim();
      if (!p || /[\[\]_{}.]/.test(p) && !/^\d/.test(p)) return;
      if (/^(total|share|low|high|mid|value|count|avg|average|sum)$/i.test(p)) return;
      if (/^\d{4}-\d{2}$/.test(p)) {
        var d = parseDay(p + '-01');
        if (d) p = MONTHS[d.m - 1] + ' ' + d.y;
      }
      p = p.replace(/^category\s+/i, '');
      keep.push(p);
    });
    return keep.join(', ');
  }

  var TOOL_HOW = {
    calculate: 'Worked out by the app\'s calculator.',
    general_estimate: 'A rough estimate from general knowledge, not from your account.',
    customer_snapshot: 'Taken from the checked summary of your account.',
    earlier_answer: 'Taken from an earlier answer in this conversation.',
    customer_message: 'The number you gave me.'
  };
  var KIND_HOW = {
    snapshot: 'Taken from the checked summary of your account.',
    earlier_answer: 'Taken from an earlier answer in this conversation.',
    customer_message: 'The number you gave me.'
  };

  // -> { lead, how, estimate }  (plain sentences, never raw keys or tool names)
  function phrase(fig) {
    var src = fig && typeof fig.source === 'object' && fig.source ? fig.source : {};
    var kind = String(src.kind || ''), tool = String(src.tool || '');
    var estimate = tool === 'general_estimate';
    var subject = '';
    var ev = Array.isArray(src.evidence) && src.evidence.length ? src.evidence[0] : null;
    var per = '';
    if (ev && typeof ev === 'object') {
      per = periodText(ev.from, ev.to);
      if (isStr(ev.title)) subject = ev.title;
    }
    var cl = cleanLabel(fig && fig.label);
    if (!subject && cl && !estimate) subject = cl;
    if (estimate && src.args && isStr(src.args.what)) subject = String(src.args.what);
    var how;
    if (KIND_HOW[kind]) how = KIND_HOW[kind];
    else if (TOOL_HOW[tool]) how = TOOL_HOW[tool];
    else if (kind === 'tool') how = 'Added up by the app from your transactions.';
    else how = 'Filled in by the app from your data.';
    var lead = String(fig && fig.text || '');
    if (estimate) lead += ' is an estimate' + (subject ? ' for ' + subject : '');
    else if (subject) lead += ' – ' + subject + (per && subject.indexOf(per) < 0 ? ', ' + per : '');
    else if (per) lead += ' – ' + per;
    return { lead: lead, how: how, estimate: estimate };
  }

  // Walk text nodes: tell, for each figure in order, which node and offset holds its text. nodes: [{value}].
  // Returns [{fig, node, at}] with node an index; skips figures that cannot be found. Figures are matched in
  // reading order, so a repeated number lands on its own occurrence.
  function matchFigures(values, figs) {
    var out = [], ni = 0, off = 0;
    for (var i = 0; i < figs.length; i++) {
      var f = figs[i], t = f && f.text;
      if (!isStr(t)) continue;
      var n = ni, o = off, found = false;
      while (n < values.length) {
        var at = String(values[n]).indexOf(t, o);
        if (at >= 0) { out.push({ fig: f, node: n, at: at }); ni = n; off = at + t.length; found = true; break; }
        n++; o = 0;
      }
      if (!found) continue;
    }
    return out;
  }

  function figureList(res) {
    var list = res && res.figures;
    if (!Array.isArray(list)) return [];
    var ok = list.filter(function (f) { return f && typeof f === 'object' && isStr(f.text); });
    ok.sort(function (a, b) { return (+a.start || 0) - (+b.start || 0); });
    return ok;
  }

  // ---------- DOM ----------
  var uid = 0;
  var openState = null;   // { btn, pop }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function closeOpen() {
    var s = openState;
    openState = null;
    if (!s) return;
    try {
      if (s.btn) { s.btn.setAttribute('aria-expanded', 'false'); }
      if (s.pop && s.pop.parentNode) s.pop.parentNode.removeChild(s.pop);
    } catch (e) { /* nothing to undo */ }
  }

  document.addEventListener('click', function (ev) {
    if (!openState) return;
    var t = ev.target;
    if (openState.pop && openState.pop.contains(t)) return;
    if (openState.btn && openState.btn.contains(t)) return;
    closeOpen();
  });
  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape' && openState) {
      var b = openState.btn;
      closeOpen();
      try { if (b && b.focus) b.focus(); } catch (e) { /* ignore */ }
    }
  });

  // anchor: block element after which the popover is put. build(pop) fills it.
  function toggle(btn, anchor, build) {
    if (openState && openState.btn === btn) { closeOpen(); return; }
    closeOpen();
    var pop = el('div', 'fig-pop');
    pop.id = 'fig-pop-' + (++uid);
    pop.setAttribute('role', 'note');
    build(pop);
    if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(pop, anchor.nextSibling);
    else return;
    btn.setAttribute('aria-expanded', 'true');
    btn.setAttribute('aria-controls', pop.id);
    openState = { btn: btn, pop: pop };
  }

  function blockOf(node, root) {
    var n = node;
    while (n && n.parentNode && n.parentNode !== root) n = n.parentNode;
    return n && n.parentNode === root ? n : null;
  }

  function wrapFigures(textBox, figs) {
    var nodes = [];
    (function walk(n) {
      for (var c = n.firstChild; c; c = c.nextSibling) {
        if (c.nodeType === 3) nodes.push(c);
        else if (c.nodeType === 1 && c.className !== 'fig') walk(c);
      }
    })(textBox);
    var hits = matchFigures(nodes.map(function (n) { return n.nodeValue; }), figs);
    // Work from the last hit backwards so earlier offsets and node indexes stay valid.
    var made = 0;
    for (var i = hits.length - 1; i >= 0; i--) {
      try {
        var hit = hits[i], node = nodes[hit.node], v = node.nodeValue, t = hit.fig.text;
        if (v.substr(hit.at, t.length) !== t || !node.parentNode) continue;
        var btn = el('button', 'fig', t);
        btn.type = 'button';
        btn.setAttribute('aria-expanded', 'false');
        var parent = node.parentNode;
        var after = v.slice(hit.at + t.length);
        node.nodeValue = v.slice(0, hit.at);
        parent.insertBefore(btn, node.nextSibling);
        if (after) {
          var tail = document.createTextNode(after);
          parent.insertBefore(tail, btn.nextSibling);
          // A later hit in the same node now lives in the shortened head: it stays valid (smaller offsets).
        }
        bind(btn, hit.fig, textBox);
        made++;
      } catch (e) { /* skip this figure */ }
    }
    return made;
  }

  function bind(btn, fig, textBox) {
    btn.addEventListener('click', function (ev) {
      ev.preventDefault();
      var anchor = blockOf(btn, textBox) || btn;
      toggle(btn, anchor, function (pop) {
        var p = phrase(fig);
        pop.appendChild(el('p', 'fig-pop-lead', p.lead));
        pop.appendChild(el('p', 'fig-pop-how', p.how));
        pop.appendChild(el('p', 'fig-pop-who', p.estimate
          ? 'The AI wrote the sentence; this number is a guess, so treat it as a rough range.'
          : 'The AI wrote the sentence, not the number.'));
      });
    });
  }

  // "What I was given for this answer": only the latest answer is kept by the server.
  function bindTag(m, tag) {
    tag.setAttribute('role', 'button');
    tag.setAttribute('tabindex', '0');
    tag.setAttribute('aria-expanded', 'false');
    tag.classList.add('source-tag-btn');
    function open() {
      var anchor = m.querySelector('.reply-acts') || tag;
      if (openState && openState.btn === tag) { closeOpen(); return; }
      toggle(tag, anchor, function (pop) {
        pop.appendChild(el('p', 'fig-pop-lead', 'What I was given for this answer'));
        // The server keeps this for the newest answer only: never show it under an older one.
        var all = m.parentNode ? m.parentNode.querySelectorAll('.msg.bot') : [];
        if (all.length && all[all.length - 1] !== m) {
          pop.appendChild(el('p', 'fig-pop-who', 'I only keep this for my latest answer. You can see it under that one.'));
          return;
        }
        var slot = el('div', 'fig-pop-body', 'Looking…');
        pop.appendChild(slot);
        fetch('/api/privacy/ai-payload', { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (d) {
            var lines = d && Array.isArray(d.what_the_coach_knows)
              ? d.what_the_coach_knows.filter(function (x) { return typeof x === 'string' && x; }) : [];
            slot.textContent = '';
            if (!lines.length) {
              slot.textContent = 'Nothing to show for this answer.';
              return;
            }
            var ul = el('ul', 'fig-pop-list');
            lines.slice(0, 30).forEach(function (l) { ul.appendChild(el('li', null, l)); });
            slot.appendChild(ul);
            slot.appendChild(el('p', 'fig-pop-who', 'Not given: your name, your account number, shop names.'));
          })
          .catch(function () { slot.textContent = 'I could not load that just now.'; });
      });
    }
    tag.addEventListener('click', function (ev) { ev.preventDefault(); open(); });
    tag.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); open(); }
    });
  }

  function afterReply(m, res) {
    try {
      if (!m || !m.querySelector || !res) return;
      var textBox = m.querySelector('.bot-text');
      if (!textBox) return;
      var model = res.mode && res.mode !== 'offline';
      var figs = figureList(res);
      var made = figs.length ? wrapFigures(textBox, figs) : 0;
      if (made && model) {
        var note = el('p', 'fig-note', made === 1
          ? '1 figure, filled in by code from your data. Tap it to see where it comes from.'
          : made + ' figures, each filled in by code from your data. Tap one to see where it comes from.');
        textBox.parentNode.insertBefore(note, textBox.nextSibling);
      }
      var tag = m.querySelector('.source-tag');
      if (tag && model && !m.getAttribute('data-restored')) bindTag(m, tag);
    } catch (e) {
      if (window.console) console.error(e);
    }
  }

  window.SvinkkiExtras = {
    afterReply: afterReply,
    _test: { phrase: phrase, matchFigures: matchFigures, periodText: periodText, cleanLabel: cleanLabel }
  };
})();
