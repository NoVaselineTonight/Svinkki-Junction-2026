# Wave 2: eight added features (contract)

Requested by the team after the first build. Read `.devloop/STATE.md` first; the same rules apply:
Python standard library only, vanilla frontend, `docs/SECURITY_PLAN.md` is binding, orchestrator
commits, subagents never run git add/commit/push.

## Acceptance criteria

- W1. "Can I afford this?": an item and a price are checked against safe-to-spend, and the answer
  says what it does to the savings goal ("delays your flat by about three weeks").
- W2. Learning: when the customer reclassifies a transaction, it is remembered and applied from
  then on (optionally to every purchase from that merchant).
- W3. Leak finder: small purchases under 10 EUR added up, spending by weekday and hour, the share
  spent in the first week after payday, and repeating charges that may be forgotten subscriptions.
- W4. Unusual-spend alerts: a category far above the customer's own usual level, or above people
  of the same age (needs comparison consent), and price creep on repeating charges.
- W5. Savings leakage: flags when investment withdrawals are covering the end of the month.
- W6. Micro-challenges: opt-in, built from the customer's own habits, easy to reach, at most one
  active at a time, tracked automatically from transactions. Never nagging.
- W7. Quiz accuracy over time: an awareness score from how close past guesses were.
- W8. Area context: Statistics Finland postal-code open data (Paavo) for local income and housing.

## 1. `app/features.py` (new file, owner FEATURES)

Pure functions with no file or network access. All take a sandbox `conn` (table `tx`, see STATE.md
5.1, plus an integer `id` column) and `today`. All return JSON-serialisable dicts that include
`explain` (one plain sentence) and `evidence` (filter objects as in `app/insights.py`).
User-facing text uses human dates (reuse `insights.human_range` / `insights.human_month`).

```python
def afford(conn, today, item: str, price: float, goal: dict | None = None,
           monthly_saving_target: float = 0.0) -> dict
```
- `goal` is `{"name": str, "target": float, "saved": float}` or None.
- Returns `{"item", "price", "safe_total", "days_left", "next_payday", "after", "per_day_after",
  "verdict": "yes"|"tight"|"no", "verdict_text", "share_of_safe", "typical_month_share",
  "goal_effect", "alternatives": [str], "explain", "evidence"}`.
- `after` = safe_total - price (safe-to-spend from `insights.safe_to_spend`, passing the saving
  target). Verdict: `no` when after < 0; `tight` when after / days_left is under 10 EUR a day;
  otherwise `yes`. `share_of_safe` is None when safe_total <= 0.
- `typical_month_share` = price / average monthly everyday-basket spending (last 6 full months).
- `goal_effect` is None without a goal, else `{"name", "monthly_saving", "delay_days",
  "delay_text"}` where monthly_saving is the saving target if above 0, else average monthly income
  minus spending over the last 6 full months; delay_days = price / monthly_saving * 30.44 and
  delay_text reads like "delays your flat by about three weeks". If monthly_saving <= 0, delay_days
  is None and delay_text says the goal has no regular saving yet.
- `alternatives`: 0 to 2 plain suggestions (wait until payday on 15 Oct; split over two months).

```python
def leaks(conn, today, months: int = 3) -> dict
```
Returns `{"period", "small": {"threshold": 10, "count", "total", "per_month", "top_labels"},
"by_weekday": [{"day": "Mon".."Sun", "total", "count"}], "by_hour": [{"hour": 0..23, "total",
"count"}], "peak": {"day", "hour_range", "text"}, "payday_week": {"share", "total", "text"},
"subscriptions": [{"merchant_ref", "label", "amount", "every": "month", "months_seen", "yearly",
"last_seen", "text"}], "headline", "explain", "evidence"}`.
- Weekday and hour use everyday-basket purchases. `payday_week` is everyday spending within 7 days
  (0 to 7 inclusive) after a salary payment, as a share of all everyday spending in the period.
- A repeating charge is the same merchant in at least 3 of the last 6 full months, about one
  charge a month, amounts within 15 % of each other. `merchant_ref` is a short opaque hash of the
  merchant id (never the id itself). If none are found, `subscriptions` is `[]` and the text says
  so plainly.

```python
def alerts(conn, today, profile=None, bench_lookup=None) -> dict
```
Returns `{"alerts": [{"id", "kind", "severity": "info"|"notice", "title", "detail", "amount",
"evidence"}], "explain", "evidence"}` with at most 5 alerts, most relevant first.
- `above_own_usual`: a label or bill type in the last full month at least 40 % and 25 EUR above
  the customer's own average of the six months before.
- `above_peers`: only when `bench_lookup` is given (the caller passes it only with comparison
  consent): last full month at least 40 % and 25 EUR above the group median for the age band
  (`label:<Label>` metrics, groups tried age+area, age, all; mask the area as in
  `insights.peer_compare`).
- `price_creep`: a repeating charge whose latest amount is at least 10 % above its amount six or
  more months ago. Also check the monthly `Housing` payment and total monthly `Utilities` the same
  way (these have no merchant id).

```python
def savings_leakage(conn, today, months: int = 6) -> dict
```
Returns `{"withdrawals": [{"d", "amount", "days_before_payday", "balance_before"}], "count",
"total", "month_end_count", "flag": bool, "text", "explain", "evidence"}`. `flag` is true when at
least 2 withdrawals (`type = 'investment_withdrawal'`) in the period fall in the 10 days before a
payday or happen when the balance before them was under 100 EUR.

```python
def challenge_options(conn, today) -> dict
def challenge_progress(conn, today, challenge: dict) -> dict
```
- Options: `{"options": [{"id", "kind", "title", "why", "target", "unit", "baseline",
  "difficulty": "easy"|"medium", "label", "context", "period": {"from", "to"}, "evidence"}],
  "explain"}`. At most 3, built from the customer's own last 8 full weeks, only for habits the
  customer actually has. Targets are easy on purpose: about 15 to 25 % under the usual weekly
  level, or one fewer occasion than usual; never zero unless the usual is one or fewer a week.
  Period: the current week (Monday to Sunday). Kinds: `under_amount` (keep a label under X this
  week), `fewer_times` (at most N purchases of a label this week), `free_days` (N days this week
  with no everyday purchases), `none_this_week` (only for something done about once a week or
  less, for example a taxi-free week). `id` is stable for the same kind, label and week.
- Progress: `{"id", "title", "target", "unit", "current", "remaining", "days_left", "status":
  "on_track"|"done"|"missed"|"at_risk", "text", "evidence"}`. Wording is encouraging and never
  scolding; a missed challenge says what went well and offers nothing more.

```python
def quiz_stats(history: list[dict]) -> dict
```
History items are `{"at": ISO datetime, "label", "guess", "actual"}`. Returns `{"count",
"awareness_score": 0..100 or None, "trend": "improving"|"steady"|"slipping"|None, "points":
[{"at", "label", "guess", "actual", "accuracy"}], "best", "text"}` with accuracy = max(0, 100 -
100 * |guess - actual| / max(actual, 10)) and the score = mean accuracy of the last 5 answers.
Trend compares the last 3 with the 3 before (needs at least 4 answers).

## 2. Storage and learning (`app/state.py`, `app/db.py`, owner SERVER2)

`app/state.py` additions, all per customer and all removed by `erase`:

```python
get_goal(cid) -> dict | None            # {"name", "target", "saved"}
set_goal(cid, d | None) -> dict | None
list_overrides(cid) -> list[dict]       # {"id", "scope": "tx"|"merchant", "tx_id", "merchant",
                                        #  "label", "basket", "context", "created"}
add_override(cid, d) -> dict
remove_override(cid, override_id) -> None
get_challenge(cid) -> dict | None       # the one active challenge: an option plus "accepted_at"
set_challenge(cid, d | None) -> None
add_quiz_result(cid, d) -> None         # {"at", "label", "guess", "actual"}
quiz_history(cid) -> list[dict]         # oldest first
```
Settings gain `challenges`: `off` (default) or `on`.

`app/db.py`: `sandbox(cid, today, overrides=None)` adds an integer column `id` (the row's rowid in
the main table) to the sandbox `tx` table and applies overrides before the sandbox becomes
read-only. A `tx` override changes label, basket and context of that one row; a `merchant`
override changes every row with that merchant. Valid labels come from `classify.ALL_LABELS`; the
basket is derived with the classify module's rules unless given; `context` is `night_out` or `''`.
`insights.transactions()` must return `id` in each row (add it there if it selects columns by name;
that one-line change in `app/insights.py` belongs to SERVER2).

## 3. HTTP additions (`app/server.py`, owner SERVER2)

All need a session and analysis consent. Every sandbox is opened with the customer's overrides.

| Method | Path | Body / query | Returns |
|---|---|---|---|
| POST | `/api/afford` | `{item, price}` | `features.afford` (uses the stored goal and saving target) |
| GET | `/api/goal` | | `{goal}` |
| POST | `/api/goal` | `{name, target, saved}` or `{clear: true}` | `{goal}` |
| GET | `/api/leaks` | `?months=` (1 to 12) | `features.leaks` |
| GET | `/api/alerts` | | `features.alerts`, plus the savings-leakage flag as one more alert of kind `savings_leak`; peer alerts only with comparison consent; `{"alerts": []}` when `suggestion_level` is `off` or suggestions consent is off |
| GET | `/api/savings-leakage` | | `features.savings_leakage` |
| GET | `/api/overrides` | | `{overrides}` (without merchant ids: show `scope`, `label`, `created`, a short description) |
| POST | `/api/overrides` | `{tx_id, label, context?, apply_to_merchant?}` | `{override, affected}`; the merchant is looked up server-side from the customer's own row, the client never sends a merchant id |
| POST | `/api/overrides/remove` | `{id}` | `{ok}` |
| GET | `/api/challenge` | | `{enabled, active, options}`: `active` is `features.challenge_progress` or null; `options` is empty unless settings `challenges` is `on` |
| POST | `/api/challenge` | `{id}` (one of the current options) or `{stop: true}` | `{active}` |
| GET | `/api/quiz/stats` | | `features.quiz_stats(state.quiz_history(cid))` |
| GET | `/api/quiz` | `?another=1` | as before; with `another` it picks a different category from the last one answered (pass a different `seed`) |
| GET | `/api/area` | | `area.area_context` for the customer's postal code; needs comparison consent (403 otherwise) |
| GET | `/api/labels` | | `{labels: [...]}` the labels a transaction can be moved to |

`/api/quiz/answer` also stores `{at, label, guess, actual}` with `state.add_quiz_result`.
The chat context gains `goal`, `settings`, `quiz_history` (list), `challenge` (active or None),
`area_lookup` (callable returning the area context) and `remember(tx_id, label, context,
apply_to_merchant) -> dict`, which performs the same action as `POST /api/overrides`.

## 4. Coach (`app/tools.py`, `app/coach.py`, owner COACH2)

New tools: `can_i_afford(item, price)`, `find_leaks(months?)`, `get_alerts()`,
`check_savings_leakage()`, `get_challenge()` (options and progress, read-only),
`get_quiz_stats()`, `get_area_context()` (needs comparison consent) and
`remember_category(tx_id, label, apply_to_merchant?)`. The last one is the only tool that writes,
and only to the customer's own preferences through `ctx.remember`; if `ctx.remember` is missing it
returns an error. The coach confirms what it changed and says it can be undone in Settings.

Offline router covers at least: "can I afford a 300 euro jacket?", "where is my money leaking?",
"any forgotten subscriptions?", "anything unusual this month?", "am I dipping into my savings?",
"give me a challenge", "how is my challenge going?", "how good are my guesses?", "what is my area
like?", and corrections such as "that kebab was lunch, not a night out" (when it is unclear which
transaction is meant, reply with the latest matching ones as a `transactions` card so the customer
can pick, and say how).

Card types: `afford`, `leaks`, `alerts`, `savings_leak`, `challenge`, `quiz_stats`, `area`,
`override`. The postal code never goes to the AI model: the area tool result carries no code.

## 5. Area context (`app/area.py`, `app/paavo.json`, owner AREA)

`app/paavo.json`: Statistics Finland Paavo open data for the postal codes present in the dataset.

```python
def area_context(postal: str, customer: dict | None = None) -> dict
```
Returns `{"area_name", "year", "source", "url", "rows": [{"key", "name", "value", "unit",
"text"}], "compare": [{"name", "you", "area", "text"}], "note", "explain"}` covering median and
average income of residents, share of owner-occupied and rented dwellings, average dwelling size,
population and average age. With `customer` (`{"monthly_income", "housing_cost"}`), `compare`
sets the customer's income beside the area's median (converted to a monthly figure, stating that
Paavo incomes are yearly and from the survey year). Unknown postal code: rows `[]` with a note.

## 6. Frontend (`web/*`, owner WEB2)

- Home: a "Can I afford this?" quick card (item, price, button) showing the verdict, what is left
  per day afterwards and the goal effect; an alerts strip (at most 2, dismissible, never modal);
  the active challenge with a progress bar, or, only when challenges are on, a small "Try a
  challenge" card with the options.
- Explore: "Leak finder" section (small purchases total, weekday bars, hour bars, payday-week
  share, repeating charges list) and "Your area" section (Paavo rows with the source line).
- Transactions sheet: each row has a "Change category" action opening a small picker (labels from
  `/api/labels`, a "this was part of a night out" switch, and "apply to every purchase from this
  merchant"); after saving, the list reloads and a line says it is remembered.
- Quiz card: after answering, "Try another" and an awareness-score line with a small sparkline of
  past accuracy from `/api/quiz/stats`.
- Settings: savings goal (name, target, saved so far), challenges on/off in the same block as the
  check-in and suggestion controls with the same live summary line, and "What Svinkki has learned"
  listing remembered categories with a remove button.
- Chat: cards for the eight new types and chips for "Can I afford a €300 jacket?" and "Where is my
  money leaking?".
