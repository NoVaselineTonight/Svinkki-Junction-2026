# Svinkki: a personal economic trainer

Svinkki is a prototype for the S-Pankki challenge at Junction 2026. It lets a bank customer talk with their own money: ask "How much did I spend on taxis last month?" or "What kind of spender am I?" and get a number worked out from their own transactions, with the transactions shown under the answer. It sorts spending into the brief's three baskets (regular essentials, unexpected necessities, everyday spending), shows what is safe to spend until payday, simulates what-if changes and compares the customer with people of the same age using group statistics and Statistics Finland open data. It works like an AI assistant app: a front page with a "New conversation" button, the customer's earlier conversations, and "Your things" (a savings goal, a challenge, answers the customer chose to keep), which appear once they have been created in a conversation. A "What can I ask?" button lists everything the coach can do. It is a web app with a phone-width layout and no build step, so it can be embedded in a mobile app such as S-mobiili.

Python 3.13, standard library only. Nothing is installed. Money moves only inside S-mobiili (your own savings account or an S-Bank fund) and only after you approve that exact move.

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
| `ANTHROPIC_API_KEY` | empty | Claude key. Turns on the AI model |
| `SVINKKI_AI_KEY_FILE` | `claude_api_key.txt` | Git-ignored one-line file with the Claude key, read when `ANTHROPIC_API_KEY` is empty |
| `CLAUDE_MODEL` | `claude-opus-5-5` | Claude model, until one is chosen in Settings |
| `SVINKKI_AI_SETTINGS_FILE` | `data/ai_settings.json` | Where the model chosen in Settings is remembered |
| `GEMINI_API_KEY` | empty | Gemini key. Used only when there is no Claude key |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Gemini model name |

## Optional: the AI model

The AI model is Claude. There are three ways to give the app the key; none of them needs a restart, because the key is read on every request:

1. In the app: open http://localhost:8000 on the computer that runs the server, go to Settings, and use the block "AI model (demo setup)". Paste the key, choose the model (Opus 5.5, Sonnet 5.5 or Haiku 5.5) and press "Test the key". The server writes the key to `claude_api_key.txt`, never sends it back (it only shows the last four characters) and refuses the change from any other computer or through a proxy or tunnel.
2. Put the key on one line in `claude_api_key.txt` in the repository root.
3. Set `ANTHROPIC_API_KEY` in the environment or in `.env` (copy `.env.example`). This wins over the file.

Never commit a key: `claude_api_key.txt` and `.env` are git-ignored. With a key, chat and the text explainer use Claude, which calls the app's tools to get every number. Without a key, or when the customer switches AI off in Settings, built-in rules answer the same questions, and the reply is labelled "On-device rules". If Claude fails, declines or is slow, the built-in rules answer and the reply says so. The model only receives anonymised summaries, and only with the customer's consent. Google Gemini (`GEMINI_API_KEY`) is still supported and is used only when no Claude key exists. Note that `.env.example` shows other example values for `SVINKKI_TODAY` and `GEMINI_MODEL` than the code defaults above; set what you want.

## What is in it

Core from the brief:

- Chat with your own money, with the transactions behind each answer under it ("Transactions used").
- Three baskets, with context-aware labels: a kebab or taxi in the middle of a night out counts as "Night out", not food or transport.
- Safe to spend this week and until payday, with the working shown and a day-by-day balance forecast.
- What-if: "What if I cut dining out by 20%?", in chat and with sliders.
- Spender type and ways to save more.
- Benchmarks against groups of similar customers, only when the customer asks for a comparison (age band, widened when the group is small) and Statistics Finland open data.
- Free exploration of your own data: filter transactions by period, label, basket and text.
- Questions in English or Finnish ("Paljonko käytin takseihin viime kuussa?").

Added by the team:

- Consent switches (analyse, AI model, comparison, suggestions) and the customer's own choice of how often check-ins, suggestions, the quiz and challenges arrive.
- Weekly quiz ("Guess how much you spent on X this week") with an awareness score over time.
- A simulated S-Bank account at the top of the start page: current account balance, savings and investments, and what is safe to spend until payday; tap it for the latest transactions and "Move money" (`GET /api/account`).
- The start page shows what the coach can do as six tiles under the question box ("Can I afford it?", "Where can I save?", "Analyse receipts", "Plan a goal", "Until payday", "Explain a contract") and a link to everything else. The monthly check-in, this week's quiz and "Worth a look" sit below as closed rows that open when tapped.
- Notes: say "Remember that my rent goes up in January" (or "Muista, että ...") and the app keeps it in your own words. It shows under "Your things", the coach is given it with every question as information (never as instructions), and "Forget this" removes it (`state.add_note`, `GET /api/notes`, `POST /api/notes/remove`).
- A coach that knows the customer: with the AI model on, every turn carries a short, checked picture of the customer (last month, usual month, biggest categories, balance and payday, saving opportunities, goal), so answers are personal and end with one concrete next step when the data gives one. Aggregates only, no ids, merchants or other people; the exact lines are shown under "What the AI saw". Without a model, answers add one sentence about the customer's own previous or usual month (`coach.customer_snapshot`, `coach._personal_note`).
- Save and invest inside S-mobiili: the coach or a check-in suggestion offers a move to your own S-Bank savings account or an S-Bank fund; an approval card shows the amount, from, to and the balance after, and nothing moves until you tap "Approve". A move never takes money needed for bills before payday, and nothing can go outside S-mobiili (`app/money.py`).
- "Can I afford this?" with the effect on a savings goal; goals by date in chat ("I want to go to Japan in 2027").
- Learning: recategorise a transaction and Svinkki remembers it, for one purchase or every purchase from that merchant.
- Leak finder (small purchases, weekday and hour patterns, payday week, repeating charges), quiet alerts, spending patterns and a light note on the latest purchase.
- Payday plan across the baskets, and easy opt-in challenges tracked from your transactions.
- Finance-text explainer for pasted loan or fund text, and a mortgage readiness check (a check, not a credit decision).
- Receipts from S Group stores as material: "What do I buy most?", "How much do I spend on energy drinks?", "Show my receipts", or paste the text of a receipt and have it read. The challenge data has payment amounts only, so the receipt lines are simulated from each grocery and fuel payment (they add up to the payment to the cent) and the answer says so. Groceries come from Prisma, S-market, Alepa and Sale, fuel from ABC stations. `python -m app.receipts` (also run at the end of `app.ingest`) writes the receipts of the six demo customers to `data/receipts/` as one JSON file and one CSV per customer, and the app reads them from there.
- "Try as a random customer" login, for demonstrating on data nobody picked.
- "Reset demo" in Settings: forgets every demo customer's choices, goals, conversations and kept answers and returns to the login screen. The AI key and model are kept.

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
| `app/receipts.py` | Simulated S Group receipts for grocery payments, receipt insights, and a reader for pasted receipt text |
| `app/tools.py` | The read-only tools the coach can call |
| `app/coach.py` | Chat orchestration, guardrails, built-in rule router, Claude and Gemini tool loops |
| `app/llm_claude.py` | Minimal Claude Messages API client (urllib) |
| `app/llm_gemini.py` | Minimal Gemini REST client (urllib) |
| `app/explain.py` | Finance-text explainer and redaction of personal details |
| `app/state.py` | Writable state: consent, settings, goal, learned categories, quiz results, conversations, kept answers |
| `web/` | `index.html`, `app.js`, `styles.css`, `brand/`: the vanilla frontend (front page, conversation, sheets) |
| `tests/` | `unittest` suite on an invented population, see `tests/README.md` |

## Privacy and security

- Moving money (owner decision, 14 Nov 2026, for the demo): the AI model and the built-in rules can only
  *propose* a move. Money moves only when the customer approves that one proposal in the app, naming its
  amount and destination, within 15 minutes, once. Destinations are a fixed list inside S-mobiili; payments,
  rent, IBANs and transfers to other people or banks are refused. Moves are recorded in the demo state, not at
  a bank, and "Reset demo" undoes them.

- The customer id lives only in the server-side session. An id in a request is ignored.
- Each request works on an in-memory copy holding only that customer's rows, so other customers' data is not reachable.
- Every number is computed by code and carries the transactions it came from. The model explains; it does not calculate. A reply with a euro amount the code did not produce loses that sentence, or is replaced by the built-in answer (`SVINKKI_STRICT_NUMBERS=1` also checks percentages and plain numbers).
- The model gets an anonymised payload (no name, id, postal code or exact age) and only with consent. Settings has "What the AI saw", which shows the last payload exactly.
- Comparisons use group statistics only, never fewer than 20 customers.

The full plan, including what a real launch would still need, is in `docs/SECURITY_PLAN.md`.

## Tests

```bash
python -m unittest discover -s tests
```

The last run printed `Ran 755 tests in 47.9s` and `OK`. The tests use an invented population, need no network and no real dataset, and cannot see a real key: the fixture empties `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` and points `.env` and the key file at files that do not exist. More in `tests/README.md`.

## Honest limits

- The data is synthetic.
- Login is a demo picker, not bank authentication.
- The Claude path was checked live on 13 Nov 2026 with Claude Haiku 5.5 on a handful of questions. The automated tests use a fake HTTP layer. Gemini has not been tried live.
- The coach prompt was rewritten on 14 Nov (personal answers, the customer picture, medium effort, Opus 5.5 unless another model is chosen in Settings). That version has NOT been run against the live model yet: only the fake HTTP layer has seen it. Ask five questions with a key before a demo.
- Receipt lines are simulated: the dataset has merchants and amounts, not basket contents. A real version would read the customer's S Group purchase data with consent.
- The S-Pankki name and logo are used with S-Pankki's permission for this demo and pitch only.
- Repeating charges and investment withdrawals are rare in the synthetic data, so subscription detection and the savings-leakage alert often have nothing to show.
- This is a hackathon prototype. See "What a real launch would still need" in `docs/SECURITY_PLAN.md`.

## Data sources and licences

- Challenge dataset: Junction 2026 S-Pankki synthetic data, https://github.com/hackjunction/Junction-2026-S-pankki. Not redistributed here.
- Statistics Finland, Household Budget Survey 2022, table 14q4, household consumption expenditure by age of reference person (`app/open_data.json`). https://pxdata.stat.fi/PxWeb/pxweb/en/StatFin/StatFin__ktutk/statfin_ktutk_pxt_14q4.px/
- Statistics Finland, Paavo open data by postal code area, data year 2024, licence CC BY 4.0 (`app/paavo.json`). https://pxdata.stat.fi/PxWeb/pxweb/en/Postinumeroalueittainen_avoin_tieto/Postinumeroalueittainen_avoin_tieto__2026/
