# Svinkki: independent evaluation (re-run), 13 Nov 2026

Evaluated: the build in this repository (main at 4d8db3c) with `data/svinkki.db` (3,626,755 rows, 5,100 customers, demo pool 2,159, "today" = 2026-09-26), offline coach (no AI key). Driven over HTTP on my own instance (port 8017, own state DB), about 1,800 requests, plus one headless-Chromium walkthrough at 390 px. Numbers recomputed from the raw CSV with my own classifier (`indep.py`) and from SQLite with my own SQL. Nothing in the repo was changed.

## Verdict

The scripted demo works and the arithmetic is right: for 3 personas and 4 random customers every figure I recomputed from the raw CSV (monthly income, the three baskets, taxi spend, month-to-date groceries, night-out spend, yesterday's spend, balance, unexpected buffer, what-if saving, mortgage income and loan ceiling) matched the app to the cent, the peer medians matched my own SQL, and the data-isolation, consent, input-validation, SQL-sandbox and rate-limit controls all held under probing (no 5xx in the whole session, no customer id in any response or log line). The weaknesses are in judgement, not arithmetic. (1) Safe-to-spend is built on two fragile predictions: it drops this month's rent as soon as its usual day has passed unpaid (reproduced on the "Joonas" persona: €701.77 declared safe the day before an €825.07 rent payment takes him to -€123.30), and it guesses the next payday wrongly for about a third of customers because salary days in this dataset alternate between mid-month and month-end. Neither shows at the shipped demo date. (2) The offline chat answers a narrow set of English phrasings; outside it, it silently answers a different question (another period, "everything" instead of the category asked, a rent increase reported as a saving) or returns the help text, and it does not understand the core questions in Finnish. (3) "Can I afford" says "Yes, ... fits" to buying bitcoin, named fund units or a payday loan, and the weekly check-in suggests setting aside a whole salary as "surplus". I found no BLOCKER for the scripted demo at the shipped date; there are 10 MAJOR and 22 MINOR defects. If judges type freely, in Finnish, or ask about investments, they will hit the MAJOR ones within minutes.

Severity used here: BLOCKER = breaks the scripted demo at the shipped configuration, or exposes another customer's data. MAJOR = a wrong or misleading answer on a judged core feature that a judge can plausibly reach, or a breach of a binding requirement. MINOR = everything else that is real.

## Defects

### BLOCKER

None found.

### MAJOR

**MAJ-1. Safe-to-spend drops an unpaid rent (or utility) once its usual day has passed. CONFIRMED.**
- What: `_expected_events` predicts each bill on the median day of month of the last 3 months and then skips any prediction whose day is before today. If this month's rent has not been paid yet and its median day was yesterday, the rent vanishes from "upcoming bills" and safe-to-spend is overstated by the whole rent. The balance forecast inherits it.
- Reproduce over HTTP: start a second instance with `SVINKKI_TODAY=2026-09-06`, log in as "Joonas, 18" (the persona whose blurb says "safe-to-spend matters here"), `GET /api/safe-to-spend` → `{"balance": 701.77, "next_payday": "2026-09-15", "upcoming_bills": [], "bills_total": 0.0, "safe_total": 701.77, "per_day": 77.97, "status": "ok"}`. Chat: "You can safely spend about €545.82 a week (€77.97 a day) ... minus upcoming bills €0.00". `GET /api/forecast` → "At your usual pace your balance stays above €410 until payday on 15 Sep 2026." Raw data: rent -€825.07 on 2026-09-07 (balance -€123.30), lowest balance -€330.65 on 14 Sep. His rent days in the three months before: 4 Jun, 7 Jul, 5 Aug (median 5, so on the 6th it is treated as past).
- Scale (app's own `insights.safe_to_spend` run on 400 sampled demo-pool customers, compared with what was actually paid afterwards): on 2026-08-05, 144 had not yet paid August rent and the app left the rent out for 68 of them (47%); on 2026-09-05, 61 of 121 (50%); on 2026-07-06, 66 of 95 (69%). Example: on 5 Sep, balance €766.57, app safe total €699.11 with no bills, rent €840.29 paid on 7 Sep.
- Not visible at the shipped demo date (26 Sep: September rent is paid, October rent is predicted).
- Where: `app/insights.py:666-677` (`paid_now` logic and `if due < t or due >= win_end: continue`); used by `safe_to_spend` (`insights.py:695-700`), `features.forecast` (`features.py:~893`) and `features.afford`.
- Fix: for the current month, an expected occurrence that has not been paid (`k >= paid_now`) and whose usual day has passed must be kept as due "now" (due = today) instead of being skipped. Add a test with rent usually on the 5th, today the 6th, not yet paid.

**MAJ-2. "Next payday" is wrong for about a third of customers; salary day alternates in this dataset. CONFIRMED (backtest), with one persona affected at the demo date.**
- What: `_usual_payday` takes the most common salary day of the last 6 months and assumes it repeats. In the data, 1,718 of the 2,159 demo-pool customers had salaries on both a mid-month day and a month-end day since March 2026 (e.g. Veeti: 15 Apr, 15 May, 15 Jun, 29 Jul, 31 Aug, 15 Sep). STATE.md's "day 15 for most, end of month for the rest" is not how the data behaves.
- Backtest (the rule re-implemented from the code, run for all 2,159 pool customers against the actual next salary): predicted within 1 day for 63-66% on the 26th of May/Jun/Jul/Aug, and 78% on 5 Jul / 10 Aug. On 10 Aug, 20.4% were predicted at least 7 days too early (payday assumed on the 15th, salary arrived at month end), which shortens `days_left`, inflates the per-day figure and leaves out bills that fall before the real payday. Combined effect with MAJ-1 on 2026-08-05 (300 sampled): commitments before the real next salary were under-predicted by more than €500 for 22% of customers.
- At the demo date: 419 pool customers have no September salary by 26 Sep; all 419 receive it on 27-30 Sep; the app tells 395 of them the next payday is in October. Persona "Aino, 29": app says `next_payday: 2026-10-15, days_left: 19`; her salary (€3,947.33) arrives on 2026-09-30 together with a €635.12 investment deposit that the app shows as `planned_savings: 0.0`.
- Where: `app/insights.py:616-644` (`_usual_payday`, `_next_payday`).
- Fix: if no salary has arrived in the current month and the usual day has passed, assume month end; when the customer has used both patterns recently, plan to the later date (conservative) and say "expected" in the text. Show the assumption in "How this is calculated".

**MAJ-3. The chat silently answers a different question when it does not recognise the period or the category. CONFIRMED.**
- Reproduce as Joonas (all replies `mode=offline`, tool `get_spend`):
  - "How much did I spend on taxis in 2025?" → "I found no taxis spending last month (August 2026)." Actual 2025 taxi spend: €326.66, 7 rides.
  - "How much did I spend between 1 June and 15 July?" → "You spent €2,714 on everything in June 2026". Actual for 1 Jun-15 Jul: €4,197.32.
  - "how much did I spend on restaurants in the last 6 months?" → "You spent €315.20 on restaurants last month".
  - "How much did I spend on coffee last week?" → "You spent €145.77 on everything last week". Same for "at Lidl last month", "on transport last month", "on health last month", "on food this month" (→ "€1,602 on everything this month", which includes €825 rent).
  - "how much did I spend this morning?" → "You spent €22.21 on everything today" (both purchases were at 19:46 and 20:29).
- The figures are true for the period and scope the reply names, so SR-10 holds, but the customer asked something else and is not told the app could not do it (SR-12 in spirit).
- Where: `app/coach.py:283-309` (`period_from_text`: no years, no "last N months" other than 3 and 12, no date ranges), `coach.py:335-376` (`label_from_text`: no transport/health/food groups although `insights._ALIASES` has them), defaults at `coach.py:1003-1021` (`period or "last_month"`, no label → everything).
- Fix: when the message contains a year, a date range, "last N months/weeks" or a noun after "on/at" that no pattern matched, say so ("I can't filter by coffee or by shop; here is everything for last week") instead of answering as if it had been understood; add years, ranges and N-month periods; map transport/health/food to the existing alias groups.

**MAJ-4. What-if treats every change as a cut, so an increase is reported as a saving. CONFIRMED.**
- Reproduce (Joonas): "what if my rent goes up by 10%?" → "Cutting housing by 10% would save about €86.61 a month (from €866.13 to €779.52), or €1,039 over 12 months." (Aino): "What if I increased dining out by 20%?" → "Cutting dining out by 20% would save about €49.31 a month".
- Also: "what if I cut taxis by 50% and bars by 30%?" answers taxis only and drops bars without saying so; "What if I spend 50 euros less on restaurants each month?" ignores the €50 and assumes 20%; "what if I earned 300 more a month?" gets the help text. `POST /api/what-if` with `pct: -50` returns 200 with `saved 0.0` (silently clamped), and `pct: 0.5` is read as 50%.
- Where: `app/coach.py:941-949` (routing: any percentage counts as a cut), `app/insights.py:759-766` (`_norm_pct` clamps to 0..100 and multiplies values below 1 by 100), render at `coach.py:1134`.
- Fix: detect increase words (up, more, rise, increase, higher) and either support a signed change or reply that only cuts can be simulated; parse several targets; reject negative and fractional percentages at the API with 400.

**MAJ-5. "Can I afford" gives a yes to investments and loans. CONFIRMED.**
- Reproduce as Mikko: "should I buy a 2000 euro bitcoin?" → "Yes, bitcoin at €2,000 fits. After it you would still have about €2,198 a day until payday". "Should I buy Nordea fund units for 5000 euros?" → "Yes, Nordea fund units at €5,000 fits." "can I afford a 3000 euro payday loan?" → "Yes, payday loan at €3,000 fits." "Can I afford to borrow 20000 euros?" → "Yes, borrow at €20,000 fits." (a loan is subtracted from safe-to-spend as if it were a purchase).
- Without a price the same route produces nonsense: "which fund should I buy?" → "How much does it cost? Tell me the price for the which fund..."; "Should I buy Nokia shares?" → same. V11 passes only in the narrow sense that no product is recommended.
- This is the T8 risk in the security plan (regulated advice): a bank coach answering "Yes" to "should I buy <named security>" or "<credit product>".
- Where: `app/coach.py:858-866` (any "should/can I buy|get|afford" goes to `can_i_afford`), `coach.py:472-490` (item extraction), reply at `coach.py:1278+`.
- Fix: before the afford route, send messages that mention shares, funds, ETF, crypto, bitcoin, invest, loan, credit, borrow to the investment-education or mortgage/credit wording ("I can't say whether to buy an investment or take credit; here is what your buffer looks like"). Never render "Yes, X fits" for those.

**MAJ-6. Check-in "surplus" suggestions ignore the balance and the timing of the salary. CONFIRMED.**
- Reproduce as Joonas, `POST /api/settings {"checkin_frequency":"weekly","suggestion_level":"normal"}`, `GET /api/checkin` → headline "Your weekly check-in (14-20 Sep 2026): you earned €2,013, spent €146 and have €1,867 left over." and suggestion "You had a €1,867 surplus in 14-20 Sep 2026. Would you like to set it aside?" with button "Set aside €1,867". His balance is €1,424.31, safe-to-spend €558.00, and the same response carries "Your balance was below zero on 1 day, down to -€330.65". Two-week setting: "Set aside €886".
- Monthly variant: Veeti is told "You had a €307 surplus in August 2026. Would you like to set it aside?" although August's salary arrived on 31 Aug, the balance was below zero on 10 days (down to -€424.63) and his 12-month savings rate is -13%.
- Where: `app/insights.py:1222-1231` (surplus = income - spending - deposits inside the period, nothing else checked).
- Fix: cap the suggested amount at what is safe now (for example `min(surplus, safe_total)`), suppress it when the period contained an overdraft or when the period is shorter than a pay cycle, and do not call one week that contains payday a surplus.

**MAJ-7. The offline coach does not understand the brief's core questions in Finnish. CONFIRMED (contract-compliant, judging risk).**
- Reproduce: "Paljonko käytin takseihin viime kuussa?", "Millainen kuluttaja olen?", "Paljonko voin käyttää turvallisesti tällä viikolla?", "Mihin rahani menivät?", "Miten voin säästää enemmän?", "Onko minulla varaa 300 euron takkiin?", "Millaisen asuntolainan voin saada?", "Mihin minun kannattaisi sijoittaa?", "Paljonko tienaan?" all return the English help text. "Siirrä 100 euroa säästötilille" also gets the help text, not the read-only refusal. Only the WAVE3 example phrases work ("Haluan Japaniin 2027", "ostanko heräteostoksia?", "selitä tämä: ...").
- WAVE3 only requires those example phrases and the Finnish switch (X2) is a stretch goal, so this is not a contract failure. It matters because the partner is a Finnish bank, the demo runs without an AI key, and DEMO.md tells the presenter the built-in rules "answer the same questions".
- Where: `app/coach.py:283-376` and `coach.py:770-1021` (English-only patterns).
- Fix: add Finnish stems for the eight M4 questions plus the refusals (paljonko, käytin, taksi, ravintola, ruoka, viime kuussa, tällä viikolla, säästää, varaa, asuntolaina, sijoittaa, siirrä, maksa), or state in the UI and pitch that Finnish needs the AI model.

**MAJ-8. Basic money questions fall through to the help text or a wrong tool. CONFIRMED.**
- Reproduce: "How much do I earn?", "how much is my salary?", "what was my income last month?", "What's my balance?", "when is my next payday?", "how much did I save last month?", "what did I buy last night?", "top 5 merchants", "will the bank approve me for a 200000 loan?" → help text. "what bills are coming up?" → "You spent €68.33 on utilities last month". "compare my spending in July and August" → peer benchmark. "show my last 5 transactions" → "I found 726 transactions totalling €172.97" (a net of income and spending over two years, and 5 is ignored).
- The data for all of these is already computed (overview income, safe-to-spend balance, next payday, upcoming bills).
- Where: `app/coach.py:770-1021` (`route`), fallback at `coach.py:1521-1522`.
- Fix: add routes for income, balance, payday and upcoming bills to the existing tools; make the fallback say "I didn't understand that" before listing examples.

**MAJ-9. In AI mode the model would receive the postal area. CONFIRMED at function level (`coach._model_view` run on real responses); not exercised live because no key is configured.**
- `get_benchmarks`: the model view contains `"key": "age:25-34|area:02"`, `"description": "Customers aged 25-34 living in postal area 02"` and `group_key` on every row. `anonymise` only removes keys named merchant/cid/postal and `CUST...` strings.
- `get_area_context`: `_strip_postal` removes the code but keeps `area_name` ("Henttaa (Espoo)"). In `app/paavo.json` all 195 area names map to exactly one postal code, so the name is the postal code.
- This contradicts M5 ("the model never receives a customer ID, postal code or exact age"), the security plan ("The area is masked in what the model sees") and the README ("no name, id, postal code"). It becomes live as soon as a key is added, which HANDOFF.md lists as the next step.
- Where: `app/coach.py:157-183`, `app/insights.py:1462-1471` and `1510-1514`, `app/tools.py:488-492` and `695-723`.
- Fix: mask the group key and description in `_t_benchmarks` the way `insights.peer_compare` already does (`area:*`, "in your area"), and replace `area_name` with "your area" in the model view (keep the name for the UI card only).

**MAJ-10. Safe-to-spend and the forecast contradict each other, and the status badge ignores the customer's pace. CONFIRMED.**
- Reproduce as Joonas with `monthly_saving_target: 300`: `GET /api/safe-to-spend` → `safe_total 368.0`, `status "ok"` (UI badge "On track"); `GET /api/forecast` on the same card → "At your usual pace you would dip below zero around 15 Oct 2026, about €187 short." Without the target: safe €558.00 "On track", forecast end balance €3.21.
- The status is `ok` whenever the per-day figure is €10 or more; it never compares with usual spending. For high balances the figure is not guidance at all: Mikko is told "You can safely spend about €16,122 a week (€2,303 a day)" because the whole account balance is treated as spendable before payday.
- Where: `app/insights.py:716-724`.
- Fix: derive the status from the forecast (usual pace against safe total), and cap the headline at a multiple of the usual pace or keep a stated cushion ("you have €43,760 available; your usual pace is €X a week").

### MINOR

1. **Two comparison blocks on Explore show different "you" figures for the same metric against the same group. CONFIRMED.** `/api/benchmarks` uses the last 12 full months, `/api/averages` uses all 23 complete months; the group statistics are built over all complete months. Veeti: income €2,436.30 vs €2,479.45, everyday €748.80 vs €660.72. Joonas: unexpected necessities "€0.00, below" vs "about €35 a month". My recomputation confirms both numbers for their own windows. `app/insights.py:1484` vs `app/ingest.py:182-308`. Fix: use one window in both, the one the group statistics use.
2. **Goal plan text contradicts itself when saving is negative. CONFIRMED.** Joonas, `POST /api/goal-plan {"name":"Japan","target":3000,"deadline":"2027"}` → "you need to put aside about €334 a month ... You currently set aside or keep about €0 a month ..., so about €417 a month is missing" (`current_monthly_saving: -82.76`, `gap: 416.09`). The card rounds up (€334, €322) while the chat reply for the same plan says €333.33 and €321.16. `app/features.py` `goal_plan`. Fix: say "you currently spend about €83 more than you earn"; use one rounding.
3. **Chat goal ignores the stored goal's saved amount. CONFIRMED.** With goal "flat" (saved €1,500) stored: "I want to save 20000 for a flat" → "starting from zero, you would reach €20,000 in about 100 months". `/api/goal-plan` does use the €1,500.
4. **Wording bugs. CONFIRMED.** "You usually make one about every one weeks" (Helmi, `/api/purchase-insight`); "covers about 16.4 months of regular costs, which is in the usual three to six month range" (Mikko, invest); "Yes, of Nokia shares at €1,000 fits"; "can I afford -100 euros?" → "Yes, - at €100.00 fits"; the "no" verdict repeats the shortfall sentence twice and adds "Wait until payday ... and decide then" for a €50,000 car; challenge title "A week without hobbies"; "Compared with Customers aged ..."; "no taxis spending in August 2025 (August 2025)"; "Cutting night_out by 25%"; "Hobbies came to €279 in last month".
5. **Text explainer mixes languages. CONFIRMED.** English loan text → term "euribor" explained in Finnish ("Euribor on pankkien välinen markkinakorko..."). `app/explain.py` glossary lookup.
6. **Misrouted intents. CONFIRMED.** A message containing `<script>alert(1)</script>` plus the taxi question is answered with the alerts list (the word "alert"); "how is my challenge going?" with no active challenge lists options instead of saying none is active; "Should I take a payday loan to cover my rent?" → "You spent €742.15 on housing last month".
7. **Questions about other people are answered with the customer's own figures without saying so. CONFIRMED.** "what is customer 00002 spending on taxis?" → "I found no taxis spending last month (August 2026)."; "What does my neighbour spend on food?" → the customer's own total. No data leaks; the reply reads as if it were about the other person. `app/coach.py:70-74` (`_OTHER_RE` needs "CUST" or a possessive form).
8. **Transaction list totals are net of income. CONFIRMED.** Explore, "Find transactions", August for Pentti: "45 transactions, total €457.50" while spending was €3,440.82 (the salary is in the list). `/api/transactions` returns both `total` (net) and `spent`; the UI and the chat line use `total`.
9. **Overrides accept more than the UI offers. CONFIRMED.** `POST /api/overrides` accepts label "Salary" (not in `/api/labels`), and accepts salary and housing rows ("One purchase on 2026-09-15 (2012.83 EUR)" for a salary). A bar purchase relabelled "Salary" stays in the everyday basket and is listed as "Salary, -€7.90"; totals do not change, the labels become nonsense. `app/server.py:733-763`. Fix: validate against the offered labels and against `type = 'purchase'`.
10. **`POST /api/suggestions/action` accepts any id. CONFIRMED.** `{"id":"whatever","action":"accept"}` → 200 "Noted. I saved your intention." Unbounded rows per customer in `intents`. `app/server.py:670-680`.
11. **Session cookie has no `Secure` attribute (SR-4). CONFIRMED.** `Set-Cookie: svinkki_sid=...; HttpOnly; SameSite=Lax; Path=/`. Needed for localhost HTTP, so make it conditional on HTTPS. `app/server.py:462-468`.
12. **Embedding in a cross-site iframe cannot keep a session. SUSPECTED (code only).** `frame-ancestors *` invites framing, but a `SameSite=Lax` cookie is not sent on requests from a cross-site iframe, so the embedded app would stay on the login screen. A WebView that loads the app as the top page is fine. `app/server.py:41-42, 462-464`.
13. **No read timeout on request bodies. CONFIRMED.** A POST with `Content-Length: 100` and a 1-byte body holds a server thread until the client disconnects (8 s in my test, logged as 8007 ms), then a Python traceback (BrokenPipe, file paths only, no customer data) is written to the log. `app/server.py:353`, no `timeout` on the handler.
14. **Anonymous rate limit is keyed by client address. CONFIRMED.** After about 300 unauthenticated requests from one address in a minute (failed logins in my test), `/api/demo/random` and `/api/demo/login` return 429 for everyone at that address for the rest of the window; it locked my own next script out. Behind a shared venue NAT or a reverse proxy this is every user. `app/server.py:396`.
15. **Parallel requests are about ten times slower than the same requests in series. CONFIRMED.** Ten Home-screen requests: 67 ms in series, 621 ms in parallel (each 545-618 ms). 30 simultaneous clients: p50 2.5 s, p95 3.9 s, no errors. Fine for one presenter; relevant if several judges use it at once. Likely thread contention around the per-request sandbox build (`app/db.py:101-128`).
16. **Consent and settings persist per customer across runs. CONFIRMED.** After one rehearsal, logging in as the same persona skips the consent screen that DEMO.md step 2 shows, unless "Erase my data" was pressed or `data/state.db` is deleted. Add this to DEMO.md.
17. **Persona blurb does not match the data. CONFIRMED.** "Veeti, 32: Goes out and eats out regularly: taxis, bars and nights out": social spending is 6% of income, nights out €11.41 a month, "bars last night" is €7.07, no patterns found and no challenge offered (`"options": []` with challenges on). Mikko and Helmi also get no challenge options.
18. **Basket rules that will be questioned. CONFIRMED in data.** A doctor visit under €150 is "everyday spending" (27,872 doctor, 4,632 dentist and 25,725 other-health rows in the everyday basket), while the brief's basket 3 is "spending that slips through your fingers (e.g. coffees)". 75,340 transport purchases without an MCC are labelled "Other" (Veeti: "Other €109.01" this week). These follow the contract; they are a pedagogy risk. `app/classify.py:30-45, 153-170`.
19. **Mortgage reply calls the current-account balance savings. CONFIRMED.** Veeti: "You have €2,228 saved" (the balance, with €1,130 rent due on 4 Oct). `app/insights.py:990-992`.
20. **Explore is one page 13,930 px tall at 390 px width. CONFIRMED** (Chromium full-page capture). About 16 phone screens of scrolling; the transaction list alone prints every row of the month.
21. **Date edge cases in goal plans. CONFIRMED.** Deadline "9999" → "about €1 a month for 95673 months"; deadline tomorrow → "1 month". `GET /api/overview?month=2030-01` returns 200 with zeros.
22. **Redaction misses some phone formats and all names and addresses. CONFIRMED** (`explain.redact` on a sample): "(09) 123 456" stays; "Matti Meikäläinen" and "Mannerheimintie 5 A 12, 00100 Helsinki" stay. The contract lists only identity codes, IBANs, card numbers, e-mails and phone numbers, and the UI privacy line says the same, so only the phone format is a miss; names and addresses in a pasted contract would reach the model in AI mode.

## Acceptance criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| M1 | ingest builds, server serves, UI loads with no external requests | Pass | `python3 -m app.ingest --customers 80 --out <scratch>` built in 0.2 s; Chromium at 390 px: 0 external requests, 0 page errors, no horizontal overflow. Full 5,100-customer build not re-run |
| M2 | Demo login; only own data; ids in requests ignored | Pass | cid in query, body, header and cookie ignored (identical responses); foreign `tx_id` → 404; login with a cid → 400; cid count in responses of 4 random customers: 0 |
| M3 | Consent gate with four switches, changeable | Pass | 403 `consent_required` before consent and after withdrawal; benchmarks/area/averages 403 without comparison consent; junk consent bodies → 400 |
| M4 | Eight named questions with correct numbers and transactions | Pass (English only) | All eight answered; taxi €92.85, what-if €11.28, overview and safe-to-spend parts match my CSV recomputation; every numeric reply has `used` groups |
| M5 | Works offline and with Gemini; model never gets id, postal code, exact age | Offline pass; AI path not verifiable; postal part fails at function level | MAJ-9 |
| M6 | Every outflow in exactly one basket; UI split by month with drill-down | Pass | 0 outflow rows without a basket; 6,189 salary-sweep outflows sit in "transfer" (none in the demo pool) |
| M7 | MCC labels and night-out context | Pass | My independent night-out flags give the same totals (Veeti €11.41 a month, random customer €221.49 over 3 months) |
| M8 | Safe-to-spend with working shown | Pass at the demo date; fails early in a month | MAJ-1, MAJ-2, MAJ-10 |
| M9 | Weekly quiz with reveal and tip | Pass | Quiz, answer, "another", forged quiz id → 404 |
| M10 | Settings obeyed | Pass | Frequency off/weekly/biweekly/monthly, suggestion level 0/1/3, quiz off → 404; invalid values → 400 |
| M11 | Check-in with opt-in suggestions, no money moves | Pass with MAJ-6 | Accept → "No money was moved"; balance unchanged; suggestion not shown again |
| M12 | Security tests automated | Not re-run | Per instructions |
| S1 | Peer benchmarks, min group 20, widening | Pass; widening not exercised | 25 groups stored, smallest n = 37; medians for income, taxi, housing match my SQL exactly |
| S2 | Sandboxed free query | Pass | Other customers, `sqlite_schema`, `pragma_*`, `load_extension`, `ATTACH`, multi-statement, writes rejected; cartesian join cut at 2.0 s; rows after "today" invisible |
| S3 | "What the AI saw" | Not verifiable | Returns `null` offline |
| S4 | What-if sliders in UI | Pass | Present in Explore; API verified |
| S5 | Savings goal with time-to-goal | Pass | MINOR 2, 3 |
| S6 | Statistics Finland benchmark with source and year | Pass (values not checked against the source) | `open_data` block: Household Budget Survey 2022, table 14q4, URL |
| X1 | Multi-bank toggle | Absent | No such control in `web/app.js` |
| X2 | Finnish switch | Absent | MAJ-7 |
| X3 | Erase my data | Pass | Consent, settings, goal, overrides, quiz results cleared; next data call 403 |
| W1 | Can I afford, with goal effect | Pass with MAJ-5 | "delays your flat by about seven weeks" (300 / 200 x 30.44 = 45.7 days) |
| W2 | Learning from reclassification | Pass | One row and merchant-wide; baskets move by the row's amount; survives a new session; removable. MINOR 9 |
| W3 | Leak finder | Pass; subscriptions not exercised | Payday-week share 0.503 and €1,000.71 match my computation; small purchases counted in the everyday basket only (22 of 24) |
| W4 | Unusual-spend alerts | Partly verified | Own-usual verified (fuel €221.29 vs €117.50 average); peer alerts appear only with consent; price creep never triggered |
| W5 | Savings leakage | Pass (function level) | 2 withdrawals, 1 near payday, flag false as specified; no flagged case reached over HTTP |
| W6 | Micro-challenges | Pass | Opt-in, one active, progress from transactions, stop works; off → no options |
| W7 | Quiz awareness score | Pass | Formula as specified (a €11 miss on €9.11 scores 0) |
| W8 | Area context | Pass (values not checked against Paavo) | Needs comparison consent; source line shown |
| W9 | Transactions under every answer | Pass | `used` groups with counts and totals; disclosure opens in the browser |
| W10 | Balance forecast | Pass with MAJ-1 | Uses bills, deposits and weekday averages of regular and everyday purchases |
| W11 | Payday plan | Pass | Four lines sum to the expected salary (Veeti 2,199.43) |
| W12 | Text explainer | Pass offline | Limits 40-6,000 enforced, 24 KB body cap; MINOR 5 |
| W13 | Purchase insight | Pass | "That was your third restaurant purchase this week. At this pace it is about €700 a year." |
| W14 | Patterns with "why" on request | Pass | "why" and "yes" return the reasons |
| W15 | Goals in chat | Pass | Asks for the amount, completes on "about 3000"; does not save from chat |

Security plan tests reachable over HTTP: V1, V2, V3, V4, V5, V10, V12, V14 (rendered as text in Chromium, title unchanged), V15 (429 on the 61st chat request in a minute), V16 (57 tracked files, 8 commits, no data files or key patterns), V17 (log lines hold time, method, path, status, duration and a hashed session id; no chat text, no customer ids) pass. V7 passes for every figure I recomputed (see verdict); MAJ-3 is the caveat. V11 passes narrowly (MAJ-5). V9: no group under 20 exists in the built data. V13: I could not provoke a 5xx. SR-4 `Secure` flag missing (MINOR 11). The plan's logging list (tool called, row count) is not implemented; only request lines are logged.

Brief, as a judge would score it: talk with your own money: works for a fixed set of English phrasings (MAJ-3, 7, 8). Three baskets: yes, clear. Safe to spend: yes at the demo date (MAJ-1, 2, 10). What-if: cuts only (MAJ-4). Benchmarks: peer groups and Statistics Finland, correct. MyData free exploration: filters and typed SQL only. Mobile web: yes. Multi-bank bonus: absent.

## Not verified

- The AI-model path (Gemini or Claude): no key, by instruction. MAJ-9 is confirmed only by running the anonymiser on real responses. V6 (instruction inside tool data) and S3 need a model.
- The 372 unit tests were not re-run, by instruction.
- Full ingest of all 5,100 customers (only an 80-customer build into my scratch folder).
- Session expiry after 2 hours idle (read in code, `server.py:29, 117`, not waited for).
- Cross-site iframe behaviour (MINOR 12): no second origin was set up.
- V8 (forced tool failure): not reachable from outside; the "I couldn't work that out ... so I won't guess" reply was seen on an out-of-range what-if.
- Positive cases for repeating charges, price creep and a flagged savings leak: none occurred for the customers I could log in as.
- Statistics Finland and Paavo figures against their sources: no web access used.
- Visual review: one automated walkthrough as Pentti (picker, consent, Home, 9 chat cards, Explore, Settings, "What the AI saw"), three screenshots inspected by eye. Chat cards were checked for errors, not for layout.
- Data export: no such endpoint exists and none is in the contract.

## Reproduction material

The scripts were kept outside the repository on the evaluating machine (they read the real dataset) and are not committed: `client.py` (HTTP client), `sweep.py` + `sweep_<persona>.json` (every endpoint per persona), `chat.py` + `q_*.txt` + `chat_*.json` (chat batteries), `sec.py`, `sec2.py` (security probes), `flows.py` (quiz, settings, goal, overrides, challenge, erase), `indep.py` (independent CSV recomputation), `rand_check.py` (random customers against the CSV), `bench_check.py` (peer medians), `payday_bt.py`, `bills_bt.py`, `rent_bt.py` (backtests for MAJ-1 and MAJ-2), `pw_run.js` + `shots/` (browser walkthrough), `server.err`, `server2.err` (server logs).
