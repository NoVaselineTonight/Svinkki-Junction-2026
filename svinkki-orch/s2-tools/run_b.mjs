// PR B click-through as Veeti at 390x844 on real data (server on :8020, no key).
import { readFileSync } from 'node:fs';
const OUT = 'C:/Users/onnik/Desktop/svinkki-orch/s2-tools/';
const ok = (c, msg) => { console.log((c ? 'PASS ' : 'FAIL ') + msg); if (!c) process.exitCode = 1; };
const STORY = readFileSync(OUT + 'story.json', 'utf8');

export default async function (b) {
  const B = 'http://127.0.0.1:8020/';
  await b.go(B);
  await b.until("[...document.querySelectorAll('.persona')].some(x => /Veeti/.test(x.textContent)) || document.body.classList.contains('home-screen')");
  if (!(await b.eval("document.body.classList.contains('home-screen')"))) {
    await b.eval("[...document.querySelectorAll('.persona')].find(x => /Veeti/.test(x.textContent)).click()");
  }
  await b.until("document.body.classList.contains('home-screen')");
  await b.eval("document.querySelector('.home .chip.ready').click()");   // opens a conversation with a quick answer
  await b.until("document.body.classList.contains('chat-screen') && document.querySelectorAll('.source-tag').length >= 1", 20000);

  // h. a slow turn: progress line, seconds, send disabled
  await b.eval(`window.__f = window.fetch; window.fetch = function (u, i) {
    if (/api\\/chat/.test(String(u))) return new Promise(function (r) { setTimeout(function () { r(window.__f(u, i)); }, 12000); });
    return window.__f(u, i); }; true`);
  await b.eval("(function(){var t=document.querySelector('.chat .composer-text'); t.value='Where is my money leaking?'; t.form.requestSubmit();})()");
  await b.sleep(4500);
  const w1 = await b.eval("(document.querySelector('.wait')||{}).innerText || ''");
  ok(/Checking your numbers/.test(w1) && /\d+ s/.test(w1), 'h. waiting shows a plain line and seconds: ' + JSON.stringify(w1));
  ok(await b.eval("document.querySelector('.chat .send-btn').disabled && document.querySelector('.chat .send-btn').getAttribute('aria-label') === 'Waiting for the answer'"), 'h. send is disabled while waiting');
  await b.shot(OUT + 'b1-wait.png');
  await b.sleep(7000);
  const w2 = await b.eval("(document.querySelector('.wait')||{}).innerText || ''");
  ok(/Looking through/.test(w2), 'h. the line changes over time: ' + JSON.stringify(w2));
  await b.until("!document.querySelector('.wait') && [...document.querySelectorAll('.card-title')].some(x => /Small leaks/.test(x.textContent))", 10000);
  ok(await b.eval("!document.querySelector('.chat .send-btn').disabled"), 'h. send is back after the answer');

  // j. tap a chart column to see its value
  await b.eval("[...document.querySelectorAll('.msg-cards details.more summary')].pop().click()");
  await b.sleep(200);
  await b.eval("document.querySelectorAll('.col-chart .col')[2].click()");
  const ro = await b.eval("document.querySelector('.col-readout').textContent");
  ok(/€/.test(ro), 'j. tapping a column shows its value: ' + JSON.stringify(ro));
  await b.shot(OUT + 'b2-tap.png');

  // h. network error with a retry
  await b.eval("window.fetch = function (u, i) { if (/api\\/chat/.test(String(u))) return Promise.reject(new TypeError('offline')); return window.__f(u, i); }; true");
  await b.eval("(function(){var t=document.querySelector('.chat .composer-text'); t.value='Will I make it to payday?'; t.form.requestSubmit();})()");
  await b.until("!!document.querySelector('.msg .notice.err')", 5000);
  const er = await b.eval("[...document.querySelectorAll('.msg .notice.err')].pop().innerText");
  ok(/could not reach the server/i.test(er) && /Try again/.test(er), 'h. network error is plain with a retry: ' + JSON.stringify(er));
  const users = await b.eval("document.querySelectorAll('.msg.user').length");
  await b.eval("window.fetch = window.__f; [...document.querySelectorAll('.msg .notice.err button')].pop().click(); true");
  await b.until("[...document.querySelectorAll('.card-title')].some(x => /Until payday/.test(x.textContent))", 15000);
  ok(await b.eval("document.querySelectorAll('.msg.user').length") === users && !(await b.eval("!!document.querySelector('.msg .notice.err')")), 'h. Try again answers in place of the failed attempt');

  // h. the client timeout (110 s): a request that never answers
  if (process.env.TIMEOUT) {
    await b.eval(`window.fetch = function (u, i) { if (/api\\/chat/.test(String(u))) return new Promise(function (r, j) { i.signal.addEventListener('abort', function () { j(new DOMException('aborted', 'AbortError')); }); }); return window.__f(u, i); }; true`);
    await b.eval("(function(){var t=document.querySelector('.chat .composer-text'); t.value='What kind of spender am I?'; t.form.requestSubmit();})()");
    await b.sleep(58000);
    ok(/Almost there/.test(await b.eval("(document.querySelector('.wait')||{}).innerText || ''")), 'h. still waiting at 58 s');
    await b.until("!!document.querySelector('.msg .notice.err')", 25000);
    const to = await b.eval("[...document.querySelectorAll('.msg .notice.err')].pop().innerText");
    ok(/took too long/.test(to), 'h. timeout message: ' + JSON.stringify(to));
    await b.eval("window.fetch = window.__f; true");
  }

  // k. the story cards (a reply as the model would send it, built from Veeti's real tool results)
  await b.eval(`window.fetch = function (u, i) { if (/api\\/chat/.test(String(u))) return Promise.resolve(new Response(${JSON.stringify(STORY)}, { status: 200, headers: { 'Content-Type': 'application/json' } })); return window.__f(u, i); }; true`);
  await b.eval("(function(){var t=document.querySelector('.chat .composer-text'); t.value='How has my money changed over the year?'; t.form.requestSubmit();})()");
  await b.until("[...document.querySelectorAll('.card-title')].some(x => /Your year in money/.test(x.textContent))", 5000);
  const titles = await b.eval("[...document.querySelectorAll('.msg-cards')].pop().innerText");
  console.log('story cards:\n' + titles);
  ok(/Your year in money/.test(titles) && /Your month explained/.test(titles) && /Where groceries could give/.test(titles), 'k. three story cards drawn');
  ok(/Claude/.test(await b.eval("[...document.querySelectorAll('.source-tag')].pop().textContent")), 'f. a model answer is labelled with Claude');
  await b.eval("window.fetch = window.__f; true");
  await b.eval("(function(){var x=[...document.querySelectorAll('.card-title')].find(x => /Your year in money/.test(x.textContent)); x.closest('.msg').scrollIntoView();})()");
  await b.shot(OUT + 'b3-story.png');
  // j. the demo pill opens by tap
  await b.eval("[...document.querySelectorAll('.demo-pill')].pop().click()");
  ok(await b.eval("![...document.querySelectorAll('.demo-note')].pop().hidden"), 'j. tapping "Demo receipts" shows why');

  // i. keyboard: the visible viewport shrinks to 844 - 336 = 508 px
  await b.eval("document.querySelector('.chat .composer-text').focus(); true");
  await b.send('Emulation.setDeviceMetricsOverride', { width: 390, height: 508, deviceScaleFactor: 2, mobile: true });
  await b.sleep(500);
  const geo = await b.eval("(function(){var r=document.querySelector('.chat .composer').getBoundingClientRect(); return {bottom: r.bottom, vv: visualViewport.height, vvh: getComputedStyle(document.documentElement).getPropertyValue('--vvh')};})()");
  console.log('keyboard geometry', JSON.stringify(geo));
  ok(geo.bottom <= geo.vv && geo.bottom > geo.vv - 120, 'i. composer sits just above the keyboard edge');
  await b.shot(OUT + 'b4-keyboard.png');
  await b.send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
  await b.sleep(400);
  const geo2 = await b.eval("(function(){var r=document.querySelector('.chat .composer').getBoundingClientRect(); return {bottom: r.bottom, vv: visualViewport.height};})()");
  ok(geo2.bottom <= geo2.vv && geo2.bottom > geo2.vv - 120, 'i. composer back at the bottom when the keyboard closes ' + JSON.stringify(geo2));
}
