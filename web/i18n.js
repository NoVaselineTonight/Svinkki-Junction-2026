/* Svinkki add-on: the interface language (Finnish or English).
   window.SvI18n = { lang, t(str), add(map, patterns), set(lang) }.
   - lang: the stored choice (localStorage 'svinkki.lang'), else 'fi' for a Finnish browser, else 'en'.
   - t(str): English interface text -> Finnish when lang is 'fi'; unknown text comes back unchanged. It is called
     for every text node app.js draws, so it is a plain lookup first and never throws.
   - add(map, patterns): add-ons register their strings. map = {'English': 'Suomi'}; patterns = [[/^anchored (x)$/, 'y $1']]
     (the replacement is a string with $1.. or a function, as in String.replace).
   - set(lang): stores the choice and reloads the page.
   The Finnish dictionary itself is in i18n-fi.js. A MutationObserver also translates text that is written straight
   into the page (textContent) rather than built with h(). Text nodes only, never markup. */
(function () {
  'use strict';

  var KEY = 'svinkki.lang';
  var lang = 'en';
  try {
    var stored = window.localStorage && window.localStorage.getItem(KEY);
    if (stored === 'fi' || stored === 'en') lang = stored;
    else if (window.navigator && /^fi/i.test(String(window.navigator.language || ''))) lang = 'fi';
  } catch (e) {
    try { if (window.navigator && /^fi/i.test(String(window.navigator.language || ''))) lang = 'fi'; } catch (e2) { /* en */ }
  }

  var dict = Object.create(null);     // exact English text -> Finnish
  var patterns = [];                  // [[anchored regex, replacement string or function]]
  var cache = new Map();              // text -> result, for the repeated texts of a long list
  var CACHE_MAX = 4000;
  var LETTER = /[A-Za-zÀ-ÿ]/;

  function lookup(s) {
    var v = dict[s];
    return typeof v === 'string' ? v : undefined;
  }

  function byPattern(s) {
    for (var i = 0; i < patterns.length; i++) {
      var p = patterns[i];
      if (p[0].test(s)) {
        var out = s.replace(p[0], p[1]);
        if (typeof out === 'string' && out !== s) return out;
      }
    }
    return undefined;
  }

  // The part of a long text that is a sentence: "Text. More text!" -> ["Text.", "More text!"].
  function sentences(s) {
    var parts = s.match(/[\s\S]+?[.!?](?=\s+|$)|[\s\S]+$/g) || [];
    return parts.map(function (x) { return x.trim(); }).filter(Boolean);
  }

  // One piece of text without surrounding blanks: exact, then patterns, then its sentences, then " · " parts.
  function core(s, depth) {
    var v = lookup(s);
    if (v !== undefined) return v;
    v = byPattern(s);
    if (v !== undefined) return v;
    if (depth > 2) return undefined;
    if (s.indexOf(' · ') > 0) {
      var segs = s.split(' · '), changed = false;
      var outSegs = segs.map(function (x) {
        var r = core(x.trim(), depth + 1);
        if (r !== undefined) { changed = true; return r; }
        return x;
      });
      if (changed) return outSegs.join(' · ');
    }
    var sen = sentences(s);
    if (sen.length > 1 && sen.length <= 8) {
      var all = [];
      for (var i = 0; i < sen.length; i++) {
        var r2 = core(sen[i], depth + 1);
        if (r2 === undefined) return undefined;     // never a half-translated paragraph
        all.push(r2);
      }
      return all.join(' ');
    }
    return undefined;
  }

  function translate(s) {
    var m = /^(\s*)([\s\S]*?)(\s*)$/.exec(s);
    var body = m ? m[2] : s;
    if (!body) return s;
    var v = core(body, 0);
    if (v === undefined) return s;
    return m ? m[1] + v + m[3] : v;
  }

  function t(s) {
    try {
      if (lang !== 'fi' || typeof s !== 'string') return s;
      if (s.length > 400 || !LETTER.test(s)) return s;
      var v = dict[s];
      if (typeof v === 'string') return v;
      if (cache.has(s)) return cache.get(s);
      var out = translate(s);
      if (cache.size >= CACHE_MAX) cache.clear();
      cache.set(s, out);
      return out;
    } catch (e) {
      return s;
    }
  }

  function add(map, pats) {
    try {
      if (map && typeof map === 'object') {
        Object.keys(map).forEach(function (k) {
          if (typeof map[k] === 'string') dict[k] = map[k];
        });
      }
      if (Array.isArray(pats)) {
        pats.forEach(function (p) {
          if (Array.isArray(p) && Object.prototype.toString.call(p[0]) === '[object RegExp]' && (typeof p[1] === 'string' || typeof p[1] === 'function')) patterns.push(p);
        });
      }
      cache.clear();
    } catch (e) { /* a bad registration must not break the page */ }
  }

  function set(next) {
    if (next !== 'fi' && next !== 'en') return;
    try { window.localStorage.setItem(KEY, next); } catch (e) { /* no storage: the reload still follows the browser */ }
    if (next === lang) return;
    try { window.location.reload(); } catch (e) { /* ignore */ }
  }

  var api = { lang: lang, t: t, add: add, set: set };
  window.SvI18n = api;

  // ---------- the page itself ----------
  var doc = window.document;
  try { if (doc && doc.documentElement) doc.documentElement.setAttribute('lang', lang); } catch (e) { /* ignore */ }

  var ATTRS = ['placeholder', 'aria-label', 'title', 'alt'];
  var SKIP = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, PRE: 1, CODE: 1, NOSCRIPT: 1 };

  function skipped(el) {
    // the coach's own words (.rich) and anything marked translate="no" are left alone
    for (var n = el; n && n.nodeType === 1; n = n.parentNode) {
      if (SKIP[n.nodeName]) return true;
      if (n.classList && n.classList.contains('rich')) return true;
      if (n.getAttribute && n.getAttribute('translate') === 'no') return true;
    }
    return false;
  }

  function fixText(node) {
    var v = node.nodeValue;
    if (!v || !LETTER.test(v)) return;
    var out = t(v);
    if (out !== v) node.nodeValue = out;
  }

  function fixAttrs(el) {
    for (var i = 0; i < ATTRS.length; i++) {
      var a = ATTRS[i];
      if (!el.hasAttribute(a)) continue;
      var v = el.getAttribute(a);
      var out = t(v);
      if (out !== v) el.setAttribute(a, out);
    }
  }

  function walk(root) {
    if (!root) return;
    if (root.nodeType === 3) { if (root.parentNode && !skipped(root.parentNode)) fixText(root); return; }
    if (root.nodeType !== 1 || skipped(root)) return;
    fixAttrs(root);
    var kids = root.childNodes;
    for (var i = 0; i < kids.length; i++) walk(kids[i]);
  }

  function watch() {
    if (lang !== 'fi' || !doc || !doc.body || typeof window.MutationObserver !== 'function') return;
    var obs = new window.MutationObserver(function (list) {
      try {
        for (var i = 0; i < list.length; i++) {
          var m = list[i];
          if (m.type === 'childList') {
            for (var j = 0; j < m.addedNodes.length; j++) walk(m.addedNodes[j]);
          } else if (m.type === 'characterData') {
            if (m.target.parentNode && !skipped(m.target.parentNode)) fixText(m.target);
          } else if (m.type === 'attributes') {
            if (!skipped(m.target)) fixAttrs(m.target);
          }
        }
      } catch (e) { /* never break the page */ }
    });
    obs.observe(doc.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
    walk(doc.body);
    try { var ti = t(doc.title); if (ti !== doc.title) doc.title = ti; } catch (e) { /* ignore */ }
  }

  // ---------- the language switch: always visible, also on the login screen ----------
  function buildSwitch() {
    var bar = doc.querySelector('.topbar');
    if (!bar || doc.querySelector('.lang-switch')) return;
    var wrap = doc.createElement('div');
    wrap.className = 'lang-switch';
    wrap.setAttribute('role', 'group');
    wrap.setAttribute('aria-label', lang === 'fi' ? 'Kieli' : 'Language');
    wrap.setAttribute('translate', 'no');
    [['fi', 'FI', 'Suomeksi'], ['en', 'EN', 'In English']].forEach(function (o) {
      var b = doc.createElement('button');
      b.type = 'button';
      b.className = 'seg-btn';
      b.setAttribute('lang', o[0]);
      b.setAttribute('aria-label', o[2]);
      b.setAttribute('aria-pressed', String(lang === o[0]));
      b.appendChild(doc.createTextNode(o[1]));
      b.addEventListener('click', function () { set(o[0]); });
      wrap.appendChild(b);
    });
    var actions = doc.getElementById('top-actions');
    if (actions && actions.parentNode === bar) bar.insertBefore(wrap, actions); else bar.appendChild(wrap);
  }

  function start() {
    try { buildSwitch(); } catch (e) { /* the page works without the switch */ }
    try { watch(); } catch (e) { /* and without the observer */ }
  }
  if (doc) {
    if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', start); else start();
  }

  api._test = { dict: dict, patterns: patterns, core: core };
})();
