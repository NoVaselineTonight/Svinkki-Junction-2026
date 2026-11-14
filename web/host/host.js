/* S-mobiili demo host: asks its own backend for a Svinkki handover and opens the app in the frame. */
(function () {
  'use strict';
  var frame = document.getElementById('svinkki');
  var status = document.getElementById('status');
  var who = document.getElementById('who');

  function show(text, err) {
    status.textContent = text;
    status.className = err ? 'status err' : 'status';
    status.hidden = !text;
  }

  function open(name) {
    show('Opening Svinkki...');
    frame.removeAttribute('src');
    fetch('/api/open-svinkki', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ customer: name })
    }).then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
      .then(function (d) {
        frame.addEventListener('load', function onload() { show(''); frame.removeEventListener('load', onload); });
        frame.src = d.src;
      })
      .catch(function () { show('Svinkki is not available. Is the app running?', true); });
  }

  fetch('/api/customers').then(function (r) { return r.json(); }).then(function (d) {
    d.customers.forEach(function (n) {
      var o = document.createElement('option');
      o.value = n;
      o.textContent = n.split(',')[0];
      if (n === d['default']) o.selected = true;
      who.appendChild(o);
    });
    if (d['default']) open(d['default']);
  }).catch(function () { show('Customer list not available.', true); });

  who.addEventListener('change', function () { open(who.value); });

  Array.prototype.forEach.call(document.querySelectorAll('.tabs button'), function (b) {
    b.addEventListener('click', function () {
      Array.prototype.forEach.call(document.querySelectorAll('.tabs button'), function (x) {
        var on = x === b;
        x.classList.toggle('on', on);
        if (on) x.setAttribute('aria-current', 'page'); else x.removeAttribute('aria-current');
        document.getElementById('tab-' + x.getAttribute('data-tab')).hidden = !on;
      });
    });
  });
})();
