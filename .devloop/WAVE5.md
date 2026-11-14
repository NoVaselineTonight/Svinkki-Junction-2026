# Wave 5: a coach that is useful

Started 14 Nov 2026, about 08:30 UTC, by agent-d on the owner's brief: "The AI is frankly slightly useless.
Make it as useful and helpful as possible: data usage, system prompt, tools. Another agent does the GUI."
The owner's example: asked "I'd like to travel to China with my family. What would a 4 person trip cost?",
the coach answered "I can't estimate the cost myself. What would you expect the trip to cost?".

## How usefulness is measured

- A bank of 180 conversations (238 customer messages) in three files, written by three agents from different
  angles: goals, plans and decisions (G); the customer's own spending and receipts (D); messy phrasing, vague
  or emotional openers, follow-up chains and requests at the boundary (M). 136 English, 44 Finnish or mixed,
  49 multi-turn, spread over the six demo customers.
- Each conversation is asked through the real app with the live model (Claude Opus 5.5, the demo's model),
  starting from a clean customer state.
- Independent judges (one per file, told nothing about the changes) score every conversation 0 to 3 on
  helpful, personal, actionable and clear, and tag what went wrong. The rubric is fixed across rounds.
- The bank, the runner, the rubric and every run are outside the repository (they hold answers built on the
  dataset); see "Where the material is" at the end.

## Baseline (main at 96e3abd, before this wave)

| File | helpful | personal | actionable | clear | conversations with helpful 0 or 1 |
|---|---|---|---|---|---|
| G goals and plans | 1.40 | 1.65 | 1.27 | 1.98 | 31 of 60 |
| D own data | 1.98 | 2.02 | 1.27 | 2.65 | 12 of 60 |
| M messy and boundary | 2.25 | 2.07 | 1.75 | 2.72 | 7 of 60 |
| All | 1.88 | 1.91 | 1.43 | 2.45 | 50 of 180 |

What the judges found, most damaging first, and the cause in the code:

1. Refuses to estimate what it could know (trips, cars, weddings, tax limits, a savings projection) and asks
   the customer for the figure. Cause: the prompt said "never estimate", "never suggest a number", and the
   number check deletes any euro amount that is not in a tool result.
2. Canned refusals on ordinary questions: a message that mentions a partner or a friend got "I can't look at
   anyone else's data"; a payment request got a flat no. Cause: the keyword guardrail answered before the model.
3. Follow-ups, "help" and "what can you do" were answered by the built-in rules although the model was on.
4. The same two facts in most answers ("trim everyday spending by 5%", "half your spending lands after
   payday"). Cause: the picture of the customer was the same nine lines every turn.
5. Figures that contradict each other: "you keep €12 a month" and "you spend €196 more than comes in", from
   two different six-month windows, one of them last month's income against another period's spending.
6. "Next payday 31 October" on 26 September for customers paid on the 15th: safe to spend, the forecast and
   can-I-afford were all too gloomy.
7. "I have no comparison data" when the customer asked in Finnish or in a follow-up.
8. A sentence removed by the number check left a broken answer.
9. Nothing looked further back than six months: a balance that fell from €6,655 to €2,228 in a year, or a
   winter that cost €4,719 more than came in, was never mentioned.

## What was changed

Prompt (`coach.SYSTEM_PROMPT`): the job is to be useful; general knowledge is to be used; a cost question is
never handed back; the customer section is a pool, not a script; no repeats within a conversation; length
follows the question (a lookup is short, a plan may take two short paragraphs); a human sentence first when
the customer is worried; a no is one sentence followed by the nearest useful thing.

Outside knowledge, with the number check kept honest:
- `general_estimate`: the model registers a rough range from general knowledge, with what it assumes and
  optional parts. Only then may it quote those figures, always as a rough estimate.
- `calculate`: arithmetic by code. Every amount in an expression must already be known in the turn (a tool
  result, the customer picture, the customer's message, an earlier answer) or be a small whole number.
- `project_savings`, `loan_payment`: what regular saving grows to, and what a loan costs a month.
- `save_goal`: saves the last complete plan when the customer agrees in their own words.
- Earlier answers in the conversation count as known figures.
- One repair round: when a draft holds an amount the app cannot trace, the model is told which and may fetch
  it or rewrite, instead of the sentence being deleted.

The long view (new modules `app/trends.py`, `app/cashflow.py`, additions to `app/receipts.py`):
`get_money_story`, `get_season_outlook`, `get_category_story`, `explain_month`, `get_low_points`,
`get_income_profile`, `receipt_trends`, `grocery_basket_profile`, `grocery_cut_ideas`. Each returns ready
sentences (`highlights`) with their figures.

The picture of the customer (`coach.customer_snapshot`): one usual month (income and spending over the same 12
full months); a ranked pool of findings (`app/findings.py`) shown in two groups, "not yet mentioned" and
"already told in this conversation"; saving ideas, habits and the receipts line demoted to background.
`coach.mark_said` records which findings a reply used.

Routing with the model on: follow-ups, "help" and "what can you do" go to the model; a message that mentions
another person, or asks for a payment, goes to the model with a note (and without the tool that prepares a
money move); another customer's id and attempts to read the instructions are still refused before the model.
Comparison tools stay on for a follow-up to a comparison, and the Finnish and "is that a lot" forms are known.

Payday (`insights._usual_payday`, `_next_payday`): the most common pay day of the last 12 months. Against the
real later salaries of 400 customers on four dates: within 3 days in 82% of cases (was 55%), more than a week
too late in 0.3% (was 33%), more than a week too early in 17.5% (was 12%): pay comes at month end in about a
fifth of months with no pattern, so the picture also says "their pay has sometimes come up to N days later".

Receipts (`receipts.receipt_insights`): highlights ranked by euros a month with a €5 floor (a customer was
told about energy drinks at €0.79 a month while beer at €177 a month was dropped).

Finnish answers: money written the Finnish way (1 107,64 €) whatever the model wrote.

## What the simulated receipts cannot support (do not build)

Price changes, per-unit outliers, brand swaps and per-chain comparisons: every such difference is an artefact
of how the lines are generated. Product-group shares do not trend by construction. Euros per group per month
are sound, because they follow the real grocery payments. Details: the scout's notes (see below).

## Known limits

- The coach's estimates come from the model's general knowledge. They are labelled as rough estimates and the
  payload under "What the AI saw" shows them as `general_estimate` results, but nothing checks them against a
  price source.
- A model answer that still holds an untraceable amount after the repair round loses that sentence, as before.
- The new tools have no card in the web app yet (their figures are in the answer; the transactions used are
  still listed). The GUI is agent-c's.
- Answers take longer when several tools are needed: about 8 to 15 seconds for a plan, 3 to 6 for a lookup.

## Rounds

| Round | Code | helpful | personal | actionable | clear | helpful 0 or 1 |
|---|---|---|---|---|---|---|
| Baseline | 96e3abd | 1.88 | 1.91 | 1.43 | 2.45 | 50 of 180 |
| Round 1, all 180 | c5f7039 | 2.65 | 2.66 | 2.07 | 2.73 | 3 of 180 |

Round 1 by file: G 1.40 to 2.65, D 1.98 to 2.55, M 2.25 to 2.75. Conversations scored 3 for helpful: 44 to
121. The judge of the boundary file (M) found nothing unsafe: no payment offered, nothing about another
person's money, no loan promise, no share tip, no instructions revealed, no claimed save without the app
doing it. The judge of the goals file checked the estimates against prices in Finland and found them
realistic, with two Finnish rules stated wrongly (since corrected in the prompt).

What the round 1 judges still found, and what round 2 did about it:
- Two "left over" figures in one answer (the 12-month usual month next to a 6-month tool figure). The prompt
  now asks for one figure per thing with its period named. Not fully solved: `plan_goal_by_date` and
  `get_spender_type` still word their own 6-month figure, and the model sometimes quotes it.
- Offering to work something out instead of doing it; long single blocks; half-answered multi-part
  questions: prompt rules added.
- A note ("remember that ...") was answered by the built-in rules with a bare confirmation: the app still
  saves it, and the model now says what it means for the customer's money.
- The mortgage check's own-money figure included investments without saying so: it now says what it is made of.
- Round 2 re-asked the 33 flagged conversations and 15 others (48 conversations, 64 messages). Its judging is
  recorded in the pull request.

Live calls used in this wave: about 85 (first evaluation), 238 (baseline), 238 (round 1), 64 (round 2) and a
handful of single checks: about 630 customer messages, each one or more model requests.

## Investment guidance and follow-up questions (14 Nov, later)

The owner's complaint: asked "How should I invest my money?" the coach said "I wouldn't invest yet", sent the
buffer to a savings account, quoted "three to six months of costs" from the model's memory, and showed
follow-up buttons unrelated to the answer.

- `app/invest_knowledge.json`: 38 statements, 13 figures and 7 products gathered on 14 Nov 2026 from 45 named
  pages (Pörssisäätiö, Takuusäätiö, Marttaliitto, Finanssivalvonta, Verohallinto, Rahoitusvakausvirasto,
  Suomen Pankki, S-Pankki, Evli, ESMA and others). Each entry names its source and link; each figure says
  whether it was read on the provider's own page (`primary`) or on a third party's (`secondary`), and its date.
  Rates go stale: refresh the file before relying on it.
- `app/invest.py`: `get_investment_plan` works out, by code, what this customer could do in order: what being
  below zero costs (S-Pankki card credit 14.6%), a buffer of one to three months of spending and where it
  earns more (S-Tuottotili pays 0.01% under 5,000 euros; S-Pankki Lyhyt Korko returned 2.1% over the last
  12 months; new fixed-term deposits averaged 2.85%), a monthly amount split between buffer and index fund,
  an illustration at 5.2% a year after inflation, and idle money above the buffer. `get_invest_facts(topic)`
  returns the sourced statements on one topic (index funds, taxes, crypto, leverage ...).
  The tools are declared and run through `coach.call_tool`, not `app/tools.py` (held by another agent at the
  time); they replace `get_invest_education` for the model.
- Prompt rule 7 rewritten: recommend from the plan, "don't invest yet" is never the whole answer, name the
  source, never state a rate or rule from memory, crypto and leverage get facts and a sensible alternative.
- What the sources do NOT say, and the plan therefore does not claim: no source says a short-term interest
  fund is THE place for a buffer (Takuusäätiö says a separate account; Pörssisäätiö's guide puts money for the
  next couple of years in such a fund): the plan compares the rates and says the fund has no deposit
  guarantee. No source gives a percentage for speculative holdings. Takuusäätiö says buffer first, Pörssisäätiö
  says start early with small sums: the plan splits the monthly amount between the two.
- The in-app "S-Bank global index fund" is a demo product: no global passive S-Pankki fund was found; its facts
  are those of S-Pankki Passiivinen USA ESG Osake A.
- Follow-up questions: the model ends each answer with a line `NEXT: a | b | c`; `coach.split_followups` takes
  it off the answer and `/api/chat` returns it as `followups`. The web app must show `res.followups` in place
  of its static table (web/app.js `followUps`, held by agent-s2 when this was written).
- The built-in rules (no model) still answer investing questions with the old education-only text.
- Checked live with seven questions on three demo customers; not run on the question bank.

## Where the material is

In the repository: `.devloop/coach-bank/` holds the three bank files, `RUBRIC.md` (the judging rubric) and
`run_bank.py` (the runner; `python .devloop/coach-bank/run_bank.py live NAME` makes real, paid calls).
Runs are written to `data/coach-runs/` (git-ignored). The runs and judgements of this wave, and the scout's
notes on what the data supports (`data_scout.md`), are on the owner's machine in agent-d's session scratchpad.
