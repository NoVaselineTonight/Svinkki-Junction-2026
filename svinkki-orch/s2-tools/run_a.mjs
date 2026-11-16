// PR A click-through as Veeti at 390x844 on real data (server on :8020, no key).
const OUT = 'C:/Users/onnik/Desktop/svinkki-orch/s2-tools/';
const ok = (c, msg) => { console.log((c ? 'PASS ' : 'FAIL ') + msg); if (!c) process.exitCode = 1; };

export default async function (b) {
  const B = 'http://127.0.0.1:8020/';
  await b.go(B);
  await b.until("document.querySelector('.persona') && [...document.querySelectorAll('.persona')].some(x => /Veeti/.test(x.textContent))");
  await b.eval("[...document.querySelectorAll('.persona')].find(x => /Veeti/.test(x.textContent)).click()");
  await b.until("document.body.classList.contains('home-screen') && document.querySelector('.month-card')");
  await b.sleep(800);
  await b.shot(OUT + 'a1-home.png');
  const h0 = await b.history();
  console.log('history entries at Home:', h0.entries.length, 'index', h0.currentIndex);

  // c. conversation + Back
  await b.eval("(function(){var t=document.querySelector('.home .composer-text'); t.value='How much did I spend on taxis last month?'; t.form.requestSubmit();})()");
  await b.until("document.body.classList.contains('chat-screen') && document.querySelectorAll('.msg.bot .bot-text .rich').length >= 2", 30000);
  await b.sleep(300);
  const reply = await b.eval("[...document.querySelectorAll('.msg.bot')].pop().innerText");
  console.log('reply block:\n' + reply);
  ok(/On-device rules/.test(reply), 'f. answer says On-device rules');
  ok(/€92\.85/.test(await b.eval("document.querySelector('.msg-cards .key-num').textContent")), 'g. taxi card shows €92.85');
  await b.shot(OUT + 'a2-taxi.png');
  // a sheet inside the conversation, then Back twice
  await b.eval("document.querySelector('.ask-btn').click()");
  await b.until("!!document.querySelector('.sheet')");
  await b.back();
  ok(!(await b.eval("!!document.querySelector('.sheet')")) && await b.eval("document.body.classList.contains('chat-screen')"), 'c. Back closes the sheet and stays in the conversation');
  await b.back();
  await b.until("document.body.classList.contains('home-screen')", 5000).catch(() => {});
  ok(await b.eval("document.body.classList.contains('home-screen')"), 'c. Back leaves the conversation to Home');
  // the conversation now lists on Home
  await b.until("[...document.querySelectorAll('.conv-row')].length > 0", 5000).catch(() => {});
  ok(await b.eval("document.querySelectorAll('.conv-row').length > 0"), 'Home lists the conversation');

  // c. a sheet on Home, closed with Back and with X
  await b.eval("document.getElementById('gear-btn').click()");
  await b.until("!!document.querySelector('.sheet')");
  await b.back();
  ok(await b.eval("!document.querySelector('.sheet') && document.body.classList.contains('home-screen')"), 'c. Back closes Settings on Home');
  await b.eval("document.getElementById('gear-btn').click()");
  await b.until("!!document.querySelector('.sheet')");
  await b.eval("document.querySelector('.sheet-close').click()");
  await b.sleep(400);
  const h1 = await b.history();
  ok(h1.currentIndex === h0.currentIndex, 'c. closing a sheet by X takes its history entry back off (index ' + h1.currentIndex + ' vs ' + h0.currentIndex + ')');

  // a. quiz on Home: the result stays visible
  await b.eval("[...document.querySelectorAll('.fold summary')].find(x => /Weekly quiz/.test(x.textContent)).click()");
  await b.until("!!document.querySelector('.fold[open] .quiz-q')");
  await b.eval("[...document.querySelectorAll('.fold[open] button')].find(x => /Lock in/.test(x.textContent)).click()");
  await b.until("!!document.querySelector('.reveal')", 10000);
  await b.sleep(2500);
  ok(await b.eval("!!document.querySelector('.reveal') && document.body.classList.contains('home-screen')"), 'a. quiz result still on screen 2.5 s later');
  ok(await b.eval("[...document.querySelectorAll('.thing-row')].some(x => /Quiz score/.test(x.textContent))"), 'a. Your things shows the quiz score without a redraw');
  await b.shot(OUT + 'a3-quiz.png');

  // b. edit the saving target in a sheet; Home shows it when the sheet closes
  await b.eval("document.getElementById('gear-btn').click()");
  await b.until("!!document.querySelector('.sheet')");
  await b.eval("[...document.querySelectorAll('.sheet summary')].find(x => /check in/i.test(x.textContent)).click()");
  await b.eval("[...document.querySelectorAll('.sheet .seg[aria-label=\"Weekly quiz\"] button')].find(x => x.textContent === 'Off').click()");
  await b.until("/Saved/.test(document.querySelector('.sheet .saved').textContent)", 5000);
  await b.eval("document.querySelector('.sheet-close').click()");
  await b.sleep(1200);
  ok(await b.eval("![...document.querySelectorAll('.fold summary')].some(x => /Weekly quiz/.test(x.textContent))"), 'b. quiz turned off in Settings: Home no longer shows it');
  // turn it back on
  await b.eval("document.getElementById('gear-btn').click()");
  await b.until("!!document.querySelector('.sheet')");
  await b.eval("[...document.querySelectorAll('.sheet summary')].find(x => /check in/i.test(x.textContent)).click()");
  await b.eval("[...document.querySelectorAll('.sheet .seg[aria-label=\"Weekly quiz\"] button')].find(x => x.textContent === 'On').click()");
  await b.until("/Saved/.test(document.querySelector('.sheet .saved').textContent)", 5000);
  await b.back();
  await b.sleep(1200);
  ok(await b.eval("[...document.querySelectorAll('.fold summary')].some(x => /Weekly quiz/.test(x.textContent))"), 'b. quiz back on after Back from Settings');

  // b. a note made in chat, forgotten from its sheet: Home drops it
  await b.eval("(function(){var t=document.querySelector('.home .composer-text'); t.value='Remember that my rent goes up in January'; t.form.requestSubmit();})()");
  await b.until("document.querySelectorAll('.msg.bot .bot-text .rich').length >= 2", 30000);
  await b.eval("document.getElementById('back-btn').click()");
  await b.until("[...document.querySelectorAll('.thing-row')].some(x => /rent/i.test(x.textContent))", 8000);
  const before = await b.eval("document.querySelectorAll('.thing-row').length");
  await b.eval("[...document.querySelectorAll('.thing-row')].find(x => /rent/i.test(x.textContent)).click()");
  await b.until("!!document.querySelector('.sheet .danger-link')");
  await b.eval("document.querySelector('.sheet .danger-link').click()");
  await b.until("!document.querySelector('.sheet')", 5000);
  await b.sleep(1000);
  ok(await b.eval("![...document.querySelectorAll('.thing-row')].some(x => /rent/i.test(x.textContent))"), 'b. forgotten note leaves Home (' + before + ' rows before)');
  const h2 = await b.history();
  ok(h2.currentIndex === h0.currentIndex, 'c. history back at the bottom after all that (index ' + h2.currentIndex + ')');

  // d. Home with the network down, then retry
  await b.eval("window.__f = window.fetch; window.fetch = function () { return Promise.reject(new TypeError('offline')); }; true");
  await b.eval("(function(){var t=document.querySelector('.home .composer-text'); t.value='hi'; t.form.requestSubmit();})()");
  await b.sleep(600);
  await b.eval("document.getElementById('back-btn').click()");
  await b.sleep(800);
  const err = await b.eval("(document.querySelector('.home-err')||{}).innerText || ''");
  ok(/could not load/.test(err) && /Try again/.test(err), 'd. Home shows a short error with a retry: ' + JSON.stringify(err));
  await b.shot(OUT + 'a4-error.png');
  await b.eval("window.fetch = window.__f; [...document.querySelectorAll('.home-err button')][0].click(); true");
  await b.until("!!document.querySelector('.month-card')", 8000);
  ok(await b.eval("!document.querySelector('.home-err')"), 'd. Try again loads Home');

  // c. Back from Home leaves the app
  await b.back();
  await b.sleep(600);
  const url = await b.eval('location.href');
  ok(!/8020/.test(url), 'c. Back from Home leaves the app (now at ' + url + ')');

  // e. welcome for a customer who has not started yet
  await b.go(B);
  await b.until("!!document.querySelector('.persona, .home')");
  if (await b.eval("!!document.getElementById('gear-btn') && !document.getElementById('top-actions').hidden")) {
    await b.eval("fetch('/api/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(()=>location.reload())");
    await b.sleep(1200);
  }
  await b.until("[...document.querySelectorAll('.persona')].some(x => /Pentti/.test(x.textContent))");
  await b.eval("[...document.querySelectorAll('.persona')].find(x => /Pentti/.test(x.textContent)).click()");
  await b.until("!!document.querySelector('.welcome, .home')");
  const wel = await b.eval("(document.querySelector('.welcome')||{}).innerText || 'NO WELCOME (already consented)'");
  console.log('welcome:\n' + wel);
  ok(!/An AI helps/.test(wel) && /No AI model is connected/.test(wel), 'e. welcome is true without a model');
  await b.shot(OUT + 'a5-welcome.png');
}
