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

## Where the material is

On the owner's machine, outside git, under the session scratchpad of agent-d: `bank/bank_goals.json`,
`bank/bank_data.json`, `bank/bank_messy.json`, `run_bank.py` (runner), `judge_rubric.md`, `runs/*.json`
(answers and judgements per round), `data_scout.md` (what the data supports, findings per demo customer).
