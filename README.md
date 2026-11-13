# Svinkki: a personal economic trainer

Svinkki is a prototype for the S-Pankki challenge at Junction 2026. It lets a bank customer talk with their own money: ask "How much did I spend on taxis last month?" or "What kind of spender am I?" and get a number worked out from their own transactions, with the transactions shown under the answer. It sorts spending into the brief's three baskets (regular essentials, unexpected necessities, everyday spending), shows what is safe to spend until payday, simulates what-if changes and compares the customer with people of the same age using group statistics and Statistics Finland open data. It is a web app with a phone-width layout and no build step, so it can be embedded in a mobile app.

Python 3.13, standard library only. Nothing is installed. Nothing moves money.

## Run it

The synthetic dataset is not in this repository. Download it from https://github.com/hackjunction/Junction-2026-S-pankki (the transactions file is stored with Git LFS, so use `git lfs` or the browser's "Download raw file" button), then:

```bash
SVINKKI_DATA_DIR=/path/to/dataset-folder python -m app.ingest   # builds data/svinkki.db
python -m app.server                                            # serves the app
```

Open http://127.0.0.1:8000 (the port comes from `SVINKKI_PORT`; `python -m app.server --port N` overrides it). Use `python`, not `python3`, on Windows.

The team uses a filtered copy that removes customers who move their salary out right after payday and customers with little activity (286 of 5,100, so 4,814 remain). `app.ingest` reads whatever folder it is given; it does not do this filtering itself.

Settings come from the environment or a git-ignored `.env` in the repository root (the environment wins). Defaults are in `app/config.py`:

| Variable | Default | Meaning |
|---|---|---|
| `SVINKKI_DATA_DIR` | a folder on the author's machine | Folder with the dataset CSV files |
| `SVINKKI_DB` | `data/svinkki.db` | Database built by ingest |
| `SVINKKI_STATE_DB` | `data/state.db` | Consent, settings and other app state |
| `SVINKKI_TODAY` | `2026-09-26` | The demo's "today". Rows after it are invisible |
| `SVINKKI_PORT` | `8000` | Server port |
| `GEMINI_API_KEY` | empty | Turns on the AI model |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Model name |

## Optional: the AI model

Copy `.env.example` to `.env`, set `GEMINI_API_KEY` and restart the server. Never commit `.env`; it is git-ignored. With a key, chat uses Google Gemini, which calls the app's tools to get every number. Without a key, or when the customer switches AI off in Settings, built-in rules answer the same questions, and the reply is labelled "On-device rules". The model only receives anonymised summaries, and only with the customer's consent. Note that `.env.example` shows other example values for `SVINKKI_TODAY` and `GEMINI_MODEL` than the code defaults above; set what you want.

## What is in it

Core from the brief:

- Chat with your own money, with the transactions behind each answer under it ("Transactions used").
- Three baskets, with context-aware labels: a kebab or taxi in the middle of a night out counts as "Night out", not food or transport.
- Safe to spend this week and until payday, with the working shown and a day-by-day balance forecast.
- What-if: "What if I cut dining out by 20%?", in chat and with sliders.
- Spender type and ways to save more.
- Benchmarks against groups of similar customers (age band, widened when the group is small) and Statistics Finland open data.
- Free exploration of your own data: filter transactions by period, label, basket and text.

Added by the team:

- Consent switches (analyse, AI model, comparison, suggestions) and the customer's own choice of how often check-ins, suggestions, the quiz and challenges arrive.
- Weekly quiz ("Guess how much you spent on X this week") with an awareness score over time.
- Monthly check-in with opt-in suggestions. Accepting one records the intent and never moves money.
- "Can I afford this?" with the effect on a savings goal; goals by date in chat ("I want to go to Japan in 2027").
- Learning: recategorise a transaction and Svinkki remembers it, for one purchase or every purchase from that merchant.
- Leak finder (small purchases, weekday and hour patterns, payday week, repeating charges), quiet alerts, spending patterns and a light note on the latest purchase.
- Payday plan across the baskets, and easy opt-in challenges tracked from your transactions.
- Finance-text explainer for pasted loan or fund text, and a mortgage readiness check (a check, not a credit decision).
- "Try as a random customer" login, for demonstrating on data nobody picked.

## How it is built

| Path | Role |
|---|---|
| `app/server.py` | HTTP server, sessions, JSON API, static files. No business logic |
| `app/config.py` | Environment and `.env` settings, read at call time |
| `app/ingest.py` | Builds the database from the CSV folder |
| `app/db.py` | Read-only access and the per-customer in-memory sandbox |
| `app/classify.py` | Labels from merchant category codes, baskets, night-out context |
| `app/insights.py` | The core calculations (spend, baskets, safe to spend, what-if, mortgage, check-in) |
| `app/features.py` | Affordability, leaks, alerts, challenges, forecast, payday plan, patterns, goal plans |
| `app/averages.py` | Compares one customer with group statistics (groups of 20 or more) |
| `app/area.py`, `app/paavo.json` | Public postal-code-area context |
| `app/open_data.json` | Statistics Finland household spending by age group |
| `app/tools.py` | The read-only tools the coach can call |
| `app/coach.py` | Chat orchestration, guardrails, built-in rule router, Gemini tool loop |
| `app/llm_gemini.py` | Minimal Gemini REST client (urllib) |
| `app/explain.py` | Finance-text explainer and redaction of personal details |
| `app/state.py` | Writable state: consent, settings, goal, learned categories, quiz results |
| `web/` | `index.html`, `app.js`, `styles.css`, `mark.svg`: the vanilla frontend |
| `tests/` | `unittest` suite on an invented population, see `tests/README.md` |

## Privacy and security

- The customer id lives only in the server-side session. An id in a request is ignored.
- Each request works on an in-memory copy holding only that customer's rows, so other customers' data is not reachable.
- Every number is computed by code and carries the transactions it came from. The model explains; it does not calculate.
- The model gets an anonymised payload (no name, id, postal code or exact age) and only with consent. Settings has "What the AI saw", which shows the last payload exactly.
- Comparisons use group statistics only, never fewer than 20 customers.

The full plan, including what a real launch would still need, is in `docs/SECURITY_PLAN.md`.

## Tests

```bash
python -m unittest discover -s tests
```

The last run printed `Ran 372 tests in 26.946s` and `OK`. The tests use an invented population, need no network and no real dataset, and do not read `.env` keys (they set `GEMINI_API_KEY` empty). More in `tests/README.md`.

## Honest limits

- The data is synthetic.
- Login is a demo picker, not bank authentication.
- The AI-model path has only been tested against a fake HTTP layer, not live.
- Item-level receipt analysis is not possible: the dataset has merchants and categories, not basket contents.
- Repeating charges and investment withdrawals are rare in the synthetic data, so subscription detection and the savings-leakage alert often have nothing to show.
- This is a hackathon prototype. See "What a real launch would still need" in `docs/SECURITY_PLAN.md`.

## Data sources and licences

- Challenge dataset: Junction 2026 S-Pankki synthetic data, https://github.com/hackjunction/Junction-2026-S-pankki. Not redistributed here.
- Statistics Finland, Household Budget Survey 2022, table 14q4, household consumption expenditure by age of reference person (`app/open_data.json`). https://pxdata.stat.fi/PxWeb/pxweb/en/StatFin/StatFin__ktutk/statfin_ktutk_pxt_14q4.px/
- Statistics Finland, Paavo open data by postal code area, data year 2024, licence CC BY 4.0 (`app/paavo.json`). https://pxdata.stat.fi/PxWeb/pxweb/en/Postinumeroalueittainen_avoin_tieto/Postinumeroalueittainen_avoin_tieto__2026/
