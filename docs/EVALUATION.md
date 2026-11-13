# Independent evaluation (agent-a's evaluator)

Run on 13 Nov 2026 against commit `946f02f` (the state merged in PR 4, before the Claude switch).
A fresh evaluator drove the app over HTTP, recomputed figures with its own SQL on the built
database, and read the code. It had no builder reports. This file is its findings, condensed.
Another evaluation exists in `.devloop/eval-1.md`; the two were run separately.

## Verdict: ITERATE

Every MUST passed except M5 (numbers only from tools, in AI-model mode). The demo scenario ran
cleanly twice from a clean state.

| Score | 0 to 10 | Why |
|---|---|---|
| Correctness | 8 | 96 figures across 6 personas and 4 random customers matched independent SQL, except two rounding differences (largest 6 cents). Some wording is wrong. |
| Completeness against the MUSTs | 8 | 11 of 12 pass. |
| Robustness | 8 | 21 functions on 253 customers with no exception; 108 concurrent requests from 6 sessions, none saw another session's data; odd inputs get clean 4xx; state survives a restart. |
| Demo readiness | 7 | Runs cleanly, but see D2. |
| Fit to the brief | 7 | Talks with your own money with true numbers, baskets, safe to spend, what-if, benchmarks. Held back by D3 and D5, and "explore my data" means typing SQL. |

## What was verified and passed

- Identity: a customer id in the query, body or headers is ignored; a login with a raw id is
  rejected; another customer's `tx_id` on `/api/overrides` returns 404.
- Consent: each of the four switches gates its own endpoints; withdrawal closes 9 data endpoints.
- Sandbox: `sqlite_master`, `pragma_*`, ATTACH, writes, multiple statements, `load_extension`,
  other customers' ids all denied; 50-row cap; runaway queries stop after 2 seconds.
- Group statistics: smallest stored group has 29 customers; none under 20.
- Safe to spend, baskets, what-if, quiz, check-in, afford, learning from a recategorised
  transaction, leak finder, alerts, challenges (the "met in N of 8 weeks" claim matched for 10 of
  10 offers), quiz stats, area, forecast, payday plan, redaction in the text explainer, purchase
  insight, patterns, goal by date: all ran on real customers with correct spot-checked numbers.
- No special-casing of fixture ids or values in `app/`.

## Defects, ranked

### Major

**D1. An invented figure can reach the customer in AI-model mode (fails M5 and SR-10).**
`app/coach.py`, `numbers_grounded`. A model reply "You can safely spend €19 a day" passes when
19 appears anywhere in a tool result as a whole number (here `days_left`). "You spent 412 on
restaurants and could save 950 in a year" passes because amounts without a euro sign are never
checked; percentages, counts and months are not checked either. Expected: match each figure
against a figure of the same kind (money against money fields) and check unlabelled numbers too.

**D2. The demo can miss the headline.** The quiz can pick "Other health" and then frames a health
cost as something to cut (`insights.quiz`): limit quiz labels to everyday spending. The scenario in
`.devloop/STATE.md` names Aino, who has no taxi spending last month; the first persona (Veeti) was
since chosen to have a taxi ride and a bar visit, so demo with Veeti.

**D3. Basket rules put health and repairs in "everyday spending".** `classify.basket_for`: doctor,
dentist and other health purchases under 150 EUR (83 % of them) and home improvement under 150 EUR
(57 %) land in the brief's "slips through your fingers" basket. Expected: unexpected necessities
at any amount. Changing this needs a database rebuild and will move test expectations.

**D4. Area information reaches the AI model (SR-22, SR-23).** `get_area_context` sends
`area_name` (for example "Kannelmäki (Helsinki)"), which maps one to one to the postal code.
`get_benchmarks` sends `group_key` such as `age:18-24|area:00` and the words "postal area 00",
although the plan says the area is masked. The quiz comparison already masks it as `area:*`.

**D5. The offline coach does not understand Finnish.** "Paljonko käytin takseihin viime kuussa?"
and "Mitä voin turvallisesti käyttää tällä viikolla?" get the English help text. Only the newest
phrases (goals, patterns, explain) have Finnish patterns. Add Finnish patterns for the brief's six
questions.

### Minor

- D6. `insights._norm_pct`: a what-if percentage between 0 and 1 is read as a fraction
  (`0.5` saves 50 %), and a negative one is silently treated as 0.
- D7. `insights.what_if`: `saved_total` is computed from the rounded monthly figure (6 cents off
  over a year in one case).
- D9. `features.afford` wording when the customer is already short: "pizza is €1,524 more than
  the €0 you can safely spend" (the figure is the existing gap, not the price), and the sentence
  repeats.
- D10. `features.forecast`: says "you would dip below zero around 27 Sep" when the balance is
  already negative.
- D11. Guardrail gaps: "What did my neighbour spend last month?" is answered with the customer's
  own spending; `<script>alert(1)</script>` is routed to the alerts tool.
- D12. `web/app.js` `usedCount`: "Transactions used (N)" counts only the rows shown (at most 20
  per group), not the rows used (41 shown for 163 used in one case).
- D13. Challenges: turning them off keeps an active one on screen; on a Saturday a weekly
  challenge is offered with one day left.
- D14. `insights.quiz_answer`: the tip compares a partial week with a full usual week.
- D15. Session cookie has no `Secure` flag (acceptable on localhost; needed behind HTTPS).
- D16. Wording: "no taxis spending", "Cutting night_out by 50%", "in last month",
  "balance €-316.94", "how much do you think you spent on other health".
- D17. `explore_my_data` in offline chat needs SQL that starts with SELECT (a WITH query falls
  through), and an aliased merchant column (`select merchant as m`) reaches the model because
  `anonymise` drops columns by exact name only.
- D18. A weekly check-in for a week with no payday says "you earned €0".
- D20. `features.payday_plan` ignores a current shortfall: it still sets money aside for savings
  when the forecast reaches payday below zero.

## Not verified by this evaluation

- Any live AI model call (no key was configured for the evaluator). Request shape and payload were
  checked with a scripted fake model only.
- The user interface by eye. Claims about it come from the code and API field names.
- A real savings-leak case (the synthetic data has almost none).
- Secrets in git history (V16) and provider terms (SR-24).
- Test quality notes: most tests check independently derived values; a few only restate a formula
  or accept more than one reading; tests run on a made-up fixture, so real-data correctness rests
  on the checks above.

## The three changes that would help most with the partner's mentors

1. Make the three baskets right and central: health and repairs as unexpected necessities (D3),
   demo on a persona with taxis and nights out, quiz only on everyday categories (D2).
2. Make the trust claim hold in the AI mode the pitch describes: close the number-check gap (D1),
   stop sending the area name and code to the model (D4), and show a real "What the AI saw"
   payload from one live run.
3. Speak the customer's language and let them explore without SQL: Finnish patterns for the
   brief's questions (D5), plain filter chips for exploring transactions, and a Home screen that
   stays on safe to spend, the baskets and the chat.
