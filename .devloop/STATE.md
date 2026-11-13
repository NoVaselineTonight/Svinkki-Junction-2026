# Devloop state: Svinkki, a personal economic trainer (S-Pankki, Junction 2026)

Started: 2026-11-13 21:12. Budget: 3 hours (scope freeze at 23:30). Max 8 iterations.
Branch: `agent-a/v1-coach`. Orchestrator commits; **subagents never run git add/commit/push**.

## 1. Challenge summary

Build a mobile-first AI financial coach that lets a bank customer talk with their own transaction
data. Simple lookups ("taxis last month?") up to deeper questions ("what kind of spender am I?",
"what is safe to spend this week?", "what if I cut dining out by 20%?"). Teach the three baskets:
regular essentials, unexpected necessities, everyday spending. MyData spirit: free exploration of
your own data. Benchmarks from open data encouraged. Output: a web app embeddable in a mobile app
(S-mobiili). The partner's own mentors judge. Full text: `CHALLENGE_DESCRIPTION.md`.
Security rules: `docs/SECURITY_PLAN.md` (SR-1..SR-31 are hard requirements).

Judging assumed: works in a live demo, solves the stated problem, trusted (true numbers, privacy),
understandable in two minutes, pedagogical.

## 2. Acceptance criteria

MUST
- M1. `python -m app.ingest` builds the database from the CSV folder; `python -m app.server` serves
  the app; the phone-width UI loads at `/` with no external network requests.
- M2. Demo login: pick a persona; every API call after that returns only that customer's data.
  A customer ID in a request body, query or header is ignored (SR-1, SR-2).
- M3. Consent gate: before consent nothing is analysed or sent to an AI model. Consent has separate
  switches (analysis, AI model, peer comparison, suggestions) and can be changed or withdrawn later.
- M4. Chat answers these with correct numbers, each with a "see the transactions" reference:
  "How much did I spend on taxis last month?", "What kind of spender am I?", "What is safe for me
  to spend this week?", "How much could I save if I reduced dining out by 20%?", "Where did my
  money go?", "How can I save more?", "What kind of mortgage can I get approved for?",
  "What should I invest in?" (general education only, no specific products).
- M5. Chat works with no API key (offline coach) and with `GEMINI_API_KEY` set (Gemini with tools).
  In both modes numbers come only from tools (SR-10). The model never receives a customer ID,
  postal code or exact age (SR-22, SR-23).
- M6. Three baskets: every outflow is assigned to exactly one basket; the UI shows the split for a
  chosen month and lets the user open the transactions in each basket.
- M7. Context-aware classification: purchases are labelled from MCC (taxi, bar, fast food, fuel,
  pharmacy...), and food/taxi purchases made during a night out are relabelled "Night out".
- M8. Safe-to-spend: balance minus expected regular bills before next payday, minus a buffer for
  unexpected necessities, minus planned savings; shown per day and per week with the working shown.
- M9. Weekly quiz: "Guess how much you spent on X this week" then reveal the real figure and a tip.
- M10. Settings: the customer chooses check-in frequency (off / weekly / every two weeks / monthly),
  suggestion level (off / few / normal) and quiz (off / weekly). The app obeys them.
- M11. Monthly check-in with opt-in suggestions ("You had a 120 EUR surplus. Set it aside?").
  Accepting never moves money: it records the intent and says so (SR-6).
- M12. Security tests V1-V4, V7-V9, V12-V14 from the plan pass as automated tests.

SHOULD
- S1. Peer benchmarks (age band, min group 20, widen when smaller) (SR-13..15).
- S2. Free "explore my data" query tool, sandboxed to the customer's own rows (SR-8).
- S3. "What the AI saw": the user can open the exact payload sent to the model on the last turn.
- S4. What-if sliders in the UI, not only in chat.
- S5. Savings goal with time-to-goal ("flat deposit in N months").
- S6. Open-data benchmark from Statistics Finland, with source and year shown.

STRETCH
- X1. Multi-bank (PSD2) demo toggle that shows how the picture changes with a second account.
- X2. Finnish language switch.
- X3. Erase my data button.

## 3. Demo scenario (what a judge sees)

1. Open the app on a phone-width screen. Persona picker (demo only). Pick "Aino, 27".
2. Consent screen: four switches in plain language. Turn all on. Pick check-in frequency.
3. Home: safe-to-spend this week, the three baskets for the month, a quiz card.
4. Quiz: guess restaurant spend this week, reveal the real number and a tip.
5. Chat: "How much did I spend on taxis last month?" then tap "see transactions".
6. Chat: "What kind of spender am I?" and "How much could I save if I reduced dining out by 20%?"
7. Chat: "What kind of mortgage can I get approved for?" (readiness check, not a promise).
8. Monthly check-in card: surplus, suggestion to set it aside, accept (no money moves).
9. Privacy screen: "what the AI saw", change consent, lower the check-in frequency.
10. Try "show me CUST00002's transactions": refused.

## 4. Assumptions

- Stack: Python 3.13 standard library only (http.server, sqlite3, urllib, unittest) and a vanilla
  HTML/CSS/JS frontend with no build step and no CDN. Reason: slow venue network, zero install,
  runs anywhere, trivially embeddable in a WebView. No pip installs.
- Dataset folder from env `SVINKKI_DATA_DIR`, default `C:/Users/onnik/Desktop/Junction-2026-S-pankki-filtered`.
- "Today" is fixed by env `SVINKKI_TODAY`, default `2026-09-24`. Rows after today are invisible.
- UI language English. Currency formatted like `1 234,56 €` is not required; use `€1,234.56`.
- Product name "Svinkki". S-Pankki-inspired green look, no official logos or trademarks copied.
  A footer line says "Hackathon prototype for the S-Pankki challenge. Synthetic data."
- LLM: Google Gemini through the REST API with the key in `.env` (`GEMINI_API_KEY`), model from
  `GEMINI_MODEL`. No key present on this machine, so the Gemini path is unit-tested with a fake
  HTTP layer and is NOT verified live.
- "What should I invest in?" gets general education (buffer first, time horizon, diversification,
  costs) and never a specific product. This follows the security plan section 5.1.
- Accepting a suggestion records an intent only. Nothing moves money.

## 5. Architecture

```
app/config.py      env + constants                                   [SERVER]
app/server.py      HTTP server, routes, sessions, static files       [SERVER]
app/state.py       writable app state: consent, settings, intents    [SERVER]
app/ingest.py      CSV folder -> data/svinkki.db                     [DATA]
app/db.py          read-only access, per-customer in-memory sandbox  [DATA]
app/classify.py    MCC labels, night-out context, baskets            [DATA]
app/insights.py    every calculation                                 [INSIGHTS]
app/tools.py       tool registry the coach can call                  [COACH]
app/coach.py       chat orchestration, offline router, anonymiser    [COACH]
app/llm_gemini.py  Gemini REST client with function calling          [COACH]
web/index.html, web/app.js, web/styles.css                           [WEB]
tests/                                                               [TESTS]
```

Two SQLite files, both git-ignored under `data/`:
- `data/svinkki.db`: built by ingest, opened read-only by the app.
- `data/state.db`: consent, settings, suggestion intents, quiz answers. The only writable store.

Isolation (SR-2, SR-8): for each request the app loads only the session customer's rows into a
fresh in-memory SQLite database (about 700 rows). Every insight and the free query tool run on that
sandbox, so other customers' rows are physically absent. Benchmarks come from a precomputed
aggregate table that holds statistics only.

### 5.1 Database schema (`data/svinkki.db`)

```sql
tx(cid TEXT, d TEXT /*YYYY-MM-DD*/, ts TEXT /*YYYY-MM-DD HH:MM:SS*/, amount REAL /*signed*/,
   balance REAL, type TEXT, category TEXT, mcc TEXT, merchant TEXT,
   label TEXT, basket TEXT, context TEXT)          -- index on (cid, d)
customers(cid TEXT PRIMARY KEY, postal TEXT, age INTEGER, age_band TEXT, area TEXT)
bench(group_key TEXT, metric TEXT, n INTEGER, p25 REAL, median REAL, p75 REAL, mean REAL,
      PRIMARY KEY(group_key, metric))              -- only rows with n >= 20
personas(cid TEXT PRIMARY KEY, name TEXT, blurb TEXT)
meta(key TEXT PRIMARY KEY, value TEXT)
```

- `type`: as in the CSV (`purchase`, `salary`, `other_income`, `housing_payment`,
  `utilities_payment`, `investment_deposit`, `investment_withdrawal`, `salary_sweep`).
- `label` (fine-grained, from classify): `Housing`, `Utilities`, `Groceries`, `Restaurant`,
  `Fast food`, `Bar`, `Taxi`, `Public transport`, `Fuel`, `Parking`, `Pharmacy`, `Doctor`,
  `Dentist`, `Other health`, `Home improvement`, `Electronics`, `Furniture`, `Clothing`,
  `Hobbies`, `Books`, `Shopping`, `Events`, `Cinema`, `Gym & sports`, `Entertainment`,
  `Flights`, `Hotels`, `Travel agency`, `Car rental`, `Travel`, `Savings & investments`,
  `Salary`, `Other income`, `Transfer out`, `Other`.
- `context`: `night_out` or `''`. A night out is a session anchored on a `Bar` purchase
  (MCC 5813): any `Restaurant`, `Fast food`, `Taxi` or `Bar` purchase by the same customer between
  18:00 on that day and 06:00 the next morning, when at least one `Bar` purchase is in that
  window. `label` keeps the merchant type; the UI and tools report these under "Night out".
- `basket`: `regular` (Housing, Utilities, Groceries, Public transport, Fuel, Pharmacy),
  `unexpected` (Doctor, Dentist, Other health and Home improvement at ANY amount; Electronics and
  Furniture when the single purchase is at least 150 EUR; any other purchase of at least 500 EUR
  in Health or Home & Tech), `everyday` (all other purchases, including Electronics and
  Furniture under 150 EUR),
  `savings` (investment deposits), `income` (inflows), `transfer` (salary sweep). classify.py is
  the single source of truth and exposes `BASKET_RULES_TEXT` (plain-language explanation).
  Changed 13 Nov after the independent evaluation, see docs/EVALUATION.md D3 (health and repairs
  are unexpected necessities at any amount).
- `age_band`: `18-24`, `25-34`, `35-44`, `45-54`, `55-64`, `65+`. `area`: first two postal digits.
- `bench.group_key`: `all`, `age:<band>`, `age:<band>|area:<area>`. `metric`: monthly averages per
  customer: `income`, `regular`, `unexpected`, `everyday`, `savings`, `savings_rate`,
  `label:<label>` for the main labels, `night_out`.
- `personas`: 6 rows chosen by ingest from real customers in the data (e.g. a 18-24 with high
  restaurant share, a 25-34 saver, a family-age high earner, someone often below zero, a
  mortgage applicant, a 65+). Names are invented first names with age: "Aino, 27".
- `meta`: `today`, `built_at`, `rows`, `customers`.

### 5.2 `app/db.py` (DATA)

```python
def data_db_path() -> str
def list_personas() -> list[dict]            # {cid, name, blurb}
def customer_exists(cid) -> bool
def profile(cid) -> dict                     # {age_band, area}  (no exact age, no postal code)
def sandbox(cid, today: str) -> sqlite3.Connection
    # in-memory db with table tx (same columns minus cid) holding only this customer's rows with
    # d <= today; row_factory = sqlite3.Row
def bench(group_keys: list[str], metric: str) -> dict | None
    # first group in the list that exists (n >= 20): {group_key, n, p25, median, p75, mean}
def safe_select(conn, sql: str, max_rows=50, timeout_s=2.0) -> dict
    # runs a single SELECT on a sandbox connection with an authorizer that denies everything except
    # SELECT/READ/FUNCTION; raises ValueError on anything else. {columns, rows, truncated}
```

### 5.3 `app/insights.py` (INSIGHTS)

Every function takes `(conn, today, ...)` where `conn` is a sandbox, and returns a JSON-serialisable
dict. Money values are floats rounded to 2 decimals, positive for spending. Every result has
`evidence`: a list of filter objects `{"title", "from", "to", "label"?, "basket"?, "context"?,
"type"?}` that `transactions()` accepts, and `explain`: one plain sentence on how it was computed.

```python
def period(today, name) -> (from, to)        # this_week (Mon..today), last_week, this_month,
                                             # last_month, last_3_months, last_12_months, ytd,
                                             # or "YYYY-MM"
def transactions(conn, today, frm=None, to=None, label=None, basket=None, context=None, type=None,
                 q=None, limit=50) -> {"count", "total", "rows":[{d, ts, amount, label, basket, context, category, merchant}], "truncated"}
def spend(conn, today, period="last_month", label=None, basket=None, context=None)
    -> {"period":{from,to}, "total", "count", "by_label":[{label,total,count}], evidence, explain}
def overview(conn, today, month=None)
    -> {"month", "income", "baskets":{regular, unexpected, everyday, savings}, "spent", "surplus",
        "top_labels":[...], "vs_average":{...}, evidence, explain}
def baskets(conn, today, period="last_month")
    -> {"period", "baskets":[{key, name, total, share, top:[{label,total}], evidence}],
        "rules": str, explain}
def safe_to_spend(conn, today)
    -> {"balance", "next_payday", "days_left", "upcoming_bills":[{label, expected, due}],
        "bills_total", "unexpected_buffer", "planned_savings", "safe_total", "per_day", "per_week",
        "status": "ok"|"tight"|"over", evidence, explain}
def what_if(conn, today, changes: list[{"target": label|basket|"night_out", "pct": float}], months=12)
    -> {"baseline_monthly", "new_monthly", "saved_monthly", "saved_total", "months",
        "lines":[{target, baseline, new, saved}], evidence, explain}
def spender_type(conn, today)
    -> {"type", "title", "summary", "traits":[{name, value, note}], "shares":{...}, evidence, explain}
def save_more(conn, today)
    -> {"ideas":[{title, detail, saved_monthly, target}], "surplus_avg", evidence, explain}
def mortgage(conn, today, price: float|None=None, equity: float|None=None)
    -> {"monthly_income", "max_loan", "max_price_with_15pct_equity", "equity_needed",
        "savings_now", "monthly_saving", "months_to_equity", "rule": str,
        "check": None | {"price","loan","ltv","required_income","income_ok","equity_ok"},
        "disclaimer": str, evidence, explain}
    # rule: required monthly income = loan * 0.01841 (25 years, 6 % stress rate, payment at most
    # 35 % of income); approved applicants in the dataset put in a median 15 % equity.
def quiz(conn, today, seed=None)
    -> {"quiz_id", "label_or_context", "question", "period":{from,to}, "min", "max", "step"}
def quiz_answer(conn, today, quiz_id, guess: float)
    -> {"actual", "guess", "diff", "verdict", "tip", evidence}
def checkin(conn, today, frequency="monthly")
    -> {"period", "headline", "income", "spent", "surplus", "baskets", "highlights":[str],
        "suggestions":[{id, kind, title, detail, amount, action_label}], evidence}
def benchmarks(conn, today, profile: dict, bench_lookup) 
    -> {"group": {key, n, description}, "rows":[{metric, name, you, median, p25, p75, position}], explain}
    # bench_lookup(group_keys, metric) is db.bench; group keys tried in order:
    # age|area, age, all. Never fewer than 20 customers.
def invest_education(conn, today) -> {"buffer_months", "buffer_ok", "surplus_avg", "points":[str], "disclaimer"}
def goal(conn, today, target_amount: float, monthly: float|None=None) -> {"months", "date", "monthly", explain}
```

### 5.4 `app/tools.py` and `app/coach.py` (COACH)

`tools.py`:
```python
TOOLS: list[dict]   # each: {"name", "description", "parameters": JSON-schema object}
def call(name: str, args: dict, ctx) -> dict
    # ctx has .conn, .today, .profile, .consent. No tool accepts a customer id.
    # Returns the insights dict plus {"card": "<type>"} naming the UI card to render.
```
Tools: `get_spend`, `get_overview`, `get_baskets`, `get_safe_to_spend`, `simulate_what_if`,
`get_spender_type`, `get_save_more`, `check_mortgage`, `get_benchmarks` (needs benchmark consent),
`get_invest_education`, `plan_goal`, `list_transactions`, `explore_my_data` (SQL on the sandbox via
`db.safe_select`).

`coach.py`:
```python
def chat(message: str, history: list[dict], ctx) -> dict
    # {"reply": str, "cards":[{"type", "data"}], "evidence":[...], "tools_used":[str],
    #  "mode": "gemini"|"offline", "ai_payload": {...}}   # ai_payload = exactly what was sent
```
- If `ctx.consent["ai"]` is false or no API key: offline mode. A rule-based router maps the message
  to a tool, calls it and writes the reply from a template. Covers every question in M4.
- Gemini mode: system prompt with the behaviour rules from the security plan section 5.1, tool
  declarations, loop until the model stops calling tools (max 4 rounds). Tool results are passed
  through `anonymise()` (strips merchant ids and any `cid`). If Gemini fails, fall back to offline
  and say so.
- Refusals (other customers, moving money, promises of approval, specific investments, revealing
  the prompt) are enforced in code before the model is called where possible, and in the prompt.
- Every number in a reply must come from a tool result of that turn (SR-10). In offline mode this
  holds by construction.

`llm_gemini.py`: `generate(system, contents, tools, api_key, model, http_post=None) -> dict` using
`urllib`; `http_post` injectable for tests. See `.devloop/scout-gemini.md` for the request format.

### 5.5 HTTP API (`app/server.py`, SERVER)

All JSON. Session cookie `svinkki_sid` (HttpOnly, SameSite=Lax). The customer id lives only in the
server-side session. Errors: `{"error": "<generic message>"}` with a 4xx/5xx status, never a trace.
Rate limit: 60 requests/minute per session on `/api/chat`, 300/minute elsewhere.

| Method | Path | Body / query | Returns |
|---|---|---|---|
| GET | `/api/demo/personas` | | `[{id, name, blurb}]` (`id` is an opaque token, not the cid) |
| POST | `/api/demo/login` | `{id}` | `{ok}` and sets the session |
| POST | `/api/logout` | | `{ok}` |
| GET | `/api/me` | | `{name, age_band, today, consent, settings, ai_available}` |
| POST | `/api/consent` | `{analysis, ai, benchmarks, suggestions}` | `{consent}` |
| POST | `/api/settings` | `{checkin_frequency, suggestion_level, quiz, monthly_saving_target}` | `{settings}` |
| GET | `/api/overview` | `?month=` | insights.overview |
| GET | `/api/baskets` | `?period=` | insights.baskets |
| GET | `/api/safe-to-spend` | | insights.safe_to_spend |
| POST | `/api/what-if` | `{changes, months}` | insights.what_if |
| GET | `/api/spender-type` | | insights.spender_type |
| GET | `/api/benchmarks` | | insights.benchmarks (403 without benchmark consent) |
| POST | `/api/mortgage` | `{price?, equity?}` | insights.mortgage |
| GET | `/api/quiz` | | insights.quiz (404 when quiz is off) |
| POST | `/api/quiz/answer` | `{quiz_id, guess}` | insights.quiz_answer |
| GET | `/api/checkin` | | `{due: bool, checkin}` per settings; suggestions filtered by level and consent |
| POST | `/api/suggestions/action` | `{id, action: accept|dismiss|snooze}` | `{ok, message}` |
| GET | `/api/transactions` | `?from&to&label&basket&context&type&q&limit` | insights.transactions |
| POST | `/api/chat` | `{message}` | coach.chat result (403 without analysis consent) |
| GET | `/api/privacy/ai-payload` | | last `ai_payload` of this session, or `null` |
| POST | `/api/privacy/erase` | | deletes this customer's state rows, `{ok}` |

Without `analysis` consent every data endpoint returns 403 `{"error": "consent_required"}`.
Settings defaults: `checkin_frequency=monthly`, `suggestion_level=few`, `quiz=weekly`,
`monthly_saving_target=0`. Suggestion levels: `off` = none, `few` = at most 1 per check-in,
`normal` = at most 3.

`app/state.py`: `get_consent(cid)`, `set_consent(cid, d)`, `get_settings(cid)`,
`set_settings(cid, d)`, `record_intent(cid, suggestion_id, action)`, `erase(cid)`,
`save_quiz(cid, quiz_id, payload)`, `load_quiz(cid, quiz_id)`.

### 5.6 Frontend (WEB)

Single page, phone width first (max 480 px column, centred on desktop), no external requests.
Screens: persona picker, consent, Home (safe-to-spend, baskets, quiz, check-in), Chat, Explore
(baskets and transactions, what-if sliders), Settings & privacy. Bottom tab bar. Chat renders
`cards` by `type` (`spend`, `overview`, `baskets`, `safe_to_spend`, `what_if`, `spender_type`,
`save_more`, `mortgage`, `benchmarks`, `invest`, `goal`, `transactions`, `table`) and each card has
a "See the transactions" link that opens the evidence list. Model text is inserted with
`textContent`, never `innerHTML` (SR-19). Works inside an iframe/WebView.

### 5.7 Entry points, config and test hooks

`app/config.py` reads a git-ignored `.env` in the repo root (simple KEY=VALUE parser) and the
process environment (environment wins):

| Variable | Default |
|---|---|
| `SVINKKI_DATA_DIR` | `C:/Users/onnik/Desktop/Junction-2026-S-pankki-filtered` |
| `SVINKKI_DB` | `data/svinkki.db` |
| `SVINKKI_STATE_DB` | `data/state.db` |
| `SVINKKI_TODAY` | `2026-09-24` |
| `SVINKKI_PORT` | `8000` |
| `GEMINI_API_KEY` | empty (offline coach) |
| `GEMINI_MODEL` | see `.devloop/scout-gemini.md` |

Config values are read through functions (`config.db_path()`, `config.today()`, ...) at call time,
not frozen at import, so tests can set environment variables before starting a server.

```python
# app/ingest.py
def build(data_dir: str, out_path: str, limit_customers: int | None = None) -> dict
    # {"customers": n, "rows": n, "seconds": s}; replaces out_path atomically
# CLI: python -m app.ingest [--data-dir DIR] [--out PATH] [--customers N]

# app/server.py
def make_server(host="127.0.0.1", port=0) -> http.server.ThreadingHTTPServer
# CLI: python -m app.server [--port N] [--host H]
```

Input CSV files (UTF-8 with BOM, read with `utf-8-sig`):
- `tx_junction_transactions.csv`: `customer_id,bank_account_id,tx_date,tx_timestamp,category,tx_amount_eur,balance_after_eur,transaction_type,merchant_id,mcc_code`
  where `tx_timestamp` looks like `03OCT24:09:04:04` and `tx_date` like `2024-10-03`.
- `tx_customers_junction.csv`: `customer_id,customer_postal_code,customer_age`
- Mortgage files are optional for ingest; when present, flag applicants so one can be a persona.

Facts about the data (measured): 4,814 customers, 3.5 million rows, 2024-10-01 to 2026-09-30, one
account each. One salary a month (day 15 for most, end of month for the rest). One housing payment
a month in days 1-8, about three utility payments a month. Categories in the CSV: Groceries,
Restaurants, Transportation, Utilities, Entertainment, Health, Home & Tech, Housing, Lifestyle,
Travel, Salary, Other Income, Invest Deposit, Invest Withdraw. MCC codes present:
5411 5499 5422 5451 (groceries), 5812 restaurant, 5814 fast food, 5813 bar, 4121 taxi,
4111 public transport, 5541 5542 fuel, 7523 parking, 5912 pharmacy, 8011 doctor, 8021 dentist,
8099 other health, 5200 5251 home improvement, 5732 5734 electronics, 5712 furniture,
5651 5691 clothing, 5941 5945 hobbies, 5942 books, 5999 shopping, 7922 events, 7832 cinema,
7991 7996 7999 entertainment/sports, 4722 travel agency, 4511 flights, 7011 hotels, 7512 car rental.
About 5 % of purchases have no merchant or MCC: label them from `category`.

## 6. Risks and fallbacks

- No Gemini key on this machine: offline coach is the default path and must cover the demo.
- Ingest of 3.5 million rows in pure Python may take minutes: `--customers N` flag builds a small
  database fast; tests use a made-up fixture, never the real dataset (SR-31).
- Pure-stdlib server: ThreadingHTTPServer; fine for a demo, stated as a prototype in the README.
- Parallel builders drifting from contracts: this file is the contract; a builder who must change a
  signature reports it instead of changing it silently.

## 7. Task board

| Package | Owner | Files | Status |
|---|---|---|---|
| DATA | builder-data | app/__init__.py, app/ingest.py, app/db.py, app/classify.py | pending |
| INSIGHTS | builder-insights | app/insights.py | pending |
| COACH | builder-coach | app/tools.py, app/coach.py, app/llm_gemini.py | pending |
| SERVER | builder-server | app/server.py, app/config.py, app/state.py, .env.example | pending |
| WEB | builder-web | web/* | pending |
| TESTS | test-author | tests/* | pending |

## 8. Iteration log

(none yet)
