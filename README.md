# Svinkki: a personal economic trainer

**Pitch decks:** [8-slide deck (PDF)](submission/deck/Svinkki-deck.pdf) · [5-slide short deck (PDF)](submission/deck/Svinkki-60s.pdf) · [HTML versions and notes](submission/deck/)

Svinkki is a prototype for the S-Pankki challenge at Junction 2026. It lets a bank customer talk with their own money: ask "How much did I spend on taxis last month?" or "What kind of spender am I?" and get a number worked out from their own transactions, with the transactions shown under the answer. It sorts spending into the brief's three baskets (regular essentials, unexpected necessities, everyday spending), shows what is safe to spend until payday, simulates what-if changes and compares the customer with people of the same age using group statistics and Statistics Finland open data. It works like an AI assistant app: a front page with a "New conversation" button, the customer's earlier conversations, and "Your things" (a savings goal, a challenge, answers the customer chose to keep), which appear once they have been created in a conversation. A "What can I ask?" button lists everything the coach can do. It is a web app with a phone-width layout and no build step, and it can be embedded in a host app such as S-mobiili: a local stand-in for S-mobiili shows the identity handover and the iframe (see "Inside S-mobiili" below).

Python 3.13, standard library only. Nothing is installed. Money moves only inside S-mobiili (your own savings account or an S-Bank fund) and only after you approve that exact move.

## Run it

The synthetic dataset is not in this repository. Download it from https://github.com/hackjunction/Junction-2026-S-pankki (the transactions file is stored with Git LFS, so use `git lfs` or the browser's "Download raw file" button) and put the CSV files in a folder named `dataset/` in the repository root (git-ignored), or point `SVINKKI_DATA_DIR` at another folder. Then:

```bash
python -m app.ingest    # reads dataset/ (or SVINKKI_DATA_DIR), builds data/svinkki.db
python -m app.server    # serves the app
```

`python -m app.ingest` stops with a message naming `SVINKKI_DATA_DIR` when the folder is missing.

Open http://127.0.0.1:8000 (the port comes from `SVINKKI_PORT`; `python -m app.server --port N` overrides it). Use `python`, not `python3`, on Windows.

The team uses a filtered copy that removes customers who move their salary out right after payday and customers with little activity (286 of 5,100, so 4,814 remain). `app.ingest` reads whatever folder it is given; it does not do this filtering itself.

Settings come from the environment or a git-ignored `.env` in the repository root (the environment wins). Defaults are in `app/config.py`:

| Variable | Default | Meaning |
|---|---|---|
| `SVINKKI_DATA_DIR` | `dataset` | Folder with the dataset CSV files (relative to the repository root) |
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
| `SVINKKI_HOST_SECRET` | a built-in demo secret, accepted only from this computer | Shared secret the host app (S-mobiili) uses for the identity handover |
| `SVINKKI_FRAME_ANCESTORS` | `'self' http://127.0.0.1:8031 http://localhost:8031` | Pages allowed to show the app in an iframe (CSP `frame-ancestors`) |

## Optional: the AI model

The AI model is Claude. There are three ways to give the app the key; none of them needs a restart, because the key is read on every request:

1. In the app: open http://localhost:8000 on the computer that runs the server, go to Settings, and use the block "AI model (demo setup)". Paste the key, choose the model (Opus 5.5, Sonnet 5.5 or Haiku 5.5) and press "Test the key". The server writes the key to `claude_api_key.txt`, never sends it back (it only shows the last four characters) and refuses the change from any other computer or through a proxy or tunnel.
2. Put the key on one line in `claude_api_key.txt` in the repository root.
3. Set `ANTHROPIC_API_KEY` in the environment or in `.env` (copy `.env.example`). This wins over the file.

Never commit a key: `claude_api_key.txt` and `.env` are git-ignored. With a key, chat and the text explainer use Claude, which calls the app's tools to get every number. Without a key, or when the customer switches AI off in Settings, built-in rules answer the same questions. Every answer says where it came from, in small text under it: "On-device rules", or the name of the Claude model. If Claude fails, declines or does not finish within 60 seconds (a hard cap on the whole turn, every request included), the built-in rules answer and the reply says so. The model receives only what is listed under "What the model receives" below, and only with the customer's consent.

Measured live on 14 Nov 2026 on the real dataset as Veeti, one question at a time with a warm prompt cache (`.devloop/live-check/harness.py`):

| Model | Turns | Median | Slowest | Mean cost per turn (USD, list price) |
|---|---|---|---|---|
| Claude Opus 5.5 (default) | 12 | 6.5 s | 13.0 s | $0.034 |
| Claude Sonnet 5.5 | 3 | 3.5 s | 4.6 s | $0.024 (one of the three turns wrote the cache) |
| Claude Haiku 5.5 | 3 | 3.8 s | 4.4 s | $0.0014 |

A lookup takes two requests; a goal plan or a receipt takes four. Sonnet and Haiku were measured on three questions only. TODO(cost): final cost per turn after the number-grounding change.

Google Gemini (`GEMINI_API_KEY`) is still supported and is used only when no Claude key exists. Note that `.env.example` shows other example values for `SVINKKI_TODAY` and `GEMINI_MODEL` than the code defaults above; set what you want.

## What is in it

Core from the brief:

- Chat with your own money, with the transactions behind each answer under it ("From 2 transactions"), and follow-up questions under the latest answer (written by the model when it is on, in English or Finnish; a fixed list otherwise).
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
- A simulated S-Bank account at the top of the start page: current account balance and what is safe to spend until payday (savings only when there are some); tap it for the latest transactions and "Move money" (`GET /api/account`).
- The start page is kept short (owner's criteria, 14 Nov: useful, clear what you can do, approachable). Under the question box are four example questions the way a customer would ask them ("What can I spend this week?", "What kind of spender am I?", "Can I afford it?", "How can I save more?") and one link, "Goals, receipts, contracts and more", to every topic. Below is last month in the three baskets, each with one line on what goes in it; tap a basket for its transactions. The monthly check-in, this week's quiz and "Worth a look" are closed rows of one list. An empty conversation shows the same examples; after each answer follow-up questions are offered (the model's own when it is on, otherwise two chosen by the answer's card). The phone's or browser's Back button closes a sheet, then leaves a conversation for the start page, and leaves the app only from the start page.
- Notes: say "Remember that my rent goes up in January" (or "Muista, että ...") and the app keeps it in your own words. It shows under "Your things", the coach is given it with every question as information (never as instructions), and "Forget this" removes it (`state.add_note`, `GET /api/notes`, `POST /api/notes/remove`).
- A coach that knows the customer: with the AI model on, every turn carries a short, checked picture of the customer (last month, usual month, biggest categories, balance and payday, saving opportunities, goal), so answers are personal and end with one concrete next step when the data gives one. Aggregates only, no ids, merchants or other people; the exact lines are shown under "What the AI saw". Without a model, answers add one sentence about the customer's own previous or usual month (`coach.customer_snapshot`, `coach._personal_note`).
- Investment guidance from named Finnish sources: "How should I invest my money?" gets a plan worked out by code for this customer (what being below zero costs, a buffer of one to three months of spending, a monthly split between the buffer and a global index fund, an illustration at the long-run real return). The facts and rates come from `app/invest_knowledge.json`: 38 statements, 13 figures and 7 products read on 14 Nov 2026 from 45 named pages (Pörssisäätiö, Takuusäätiö, Finanssivalvonta, Verohallinto, Suomen Pankki, S-Pankki and others), each with its source and date; the answer names the source. Rates go stale and several are from secondary pages. This works with the AI model on; without it the built-in rules give a shorter, education-only answer.
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
| `app/invest.py`, `app/invest_knowledge.json` | Investment plan and sourced facts |
| `app/embed.py`, `app/host_demo.py`, `web/embed.js` | Embedding in a host app: identity handover, iframe sessions, the S-mobiili stand-in |
| `app/state.py` | Writable state: consent, settings, goal, learned categories, quiz results, conversations, kept answers |
| `web/` | `index.html`, `app.js`, `styles.css`, `brand/`: the vanilla frontend (front page, conversation, sheets) |
| `tests/` | `unittest` suite on an invented population, see `tests/README.md` |

## Inside S-mobiili (host demo)

S-mobiili would show Svinkki in a WebView or iframe and hand over the customer it has already authenticated. To see it on one computer:

```bash
python -m app.server --port 8030    # Svinkki
python -m app.host_demo             # a phone-width S-mobiili stand-in on port 8031
```

Open http://127.0.0.1:8031 and tap the Svinkki tab. The handover works like this: the host's server calls `POST /api/host/handover` with `Authorization: Bearer $SVINKKI_HOST_SECRET` and the customer; Svinkki returns a signed token that lasts 60 seconds, can be used once and names no customer. The host opens `/embed#handover=<token>` (the fragment never reaches a server log or a Referer), and the page trades the token for a session (`POST /api/embed/session`). The built-in demo secret is accepted only from this computer, and only the demo customers can be handed over. Inside the iframe the session works with a partitioned cookie or, when the browser blocks cookies, with a header kept in the page's memory. Only the pages in `SVINKKI_FRAME_ANCESTORS` may frame the app. 127.0.0.1 and localhost are different sites, so the demo is really cross-site. Checked in headless Chrome on the real dataset without a key, also with all cookies blocked.

## Privacy and security

- Moving money (owner decision, 14 Nov 2026, for the demo): the AI model and the built-in rules can only
  *propose* a move. Money moves only when the customer approves that one proposal in the app, naming its
  amount and destination, within 15 minutes, once. Destinations are a fixed list inside S-mobiili; payments,
  rent, IBANs and transfers to other people or banks are refused. Moves are recorded in the demo state, not at
  a bank, and "Reset demo" undoes them.

- The customer id lives only in the server-side session. An id in a request is ignored.
- Each request works on an in-memory copy holding only that customer's rows, so other customers' data is not reachable.
- Every number about the customer's money is computed by code and carries the transactions it came from. The model explains; sums go through the `calculate` tool, and a rough figure from general knowledge (the price of a trip, say) comes from `general_estimate` and is shown as an estimate. A reply with a euro amount the code did not produce gets one chance to be corrected; then that sentence is removed, or the built-in answer replaces the reply (`SVINKKI_STRICT_NUMBERS=1` also checks percentages and plain numbers). TODO(grounding): replace this with the slot-based check once agent-s5's change is merged.
- The model gets an anonymised payload (no name, customer id, merchant, postal code or exact age) and only with consent. Settings has "What the AI saw", which shows the last payload exactly. Details in the next section.
- State-changing requests from another site are refused (`Origin` and `Sec-Fetch-Site` checks), and the app can be framed only by the pages in `SVINKKI_FRAME_ANCESTORS`.
- Comparisons use group statistics only, never fewer than 20 customers.

The full plan, including what a real launch would still need, is in `docs/SECURITY_PLAN.md`.

### What the model receives

Every turn: the rules prompt (the same for everyone), the customer's age band and today's date, a short picture of the customer built from the same tools (totals, never single purchases, merchants or other people; the newest six notes; the goal), the conversation so far, the message, and the result of each tool the model calls. Before anything is sent, `coach.anonymise` removes customer, merchant and account ids, postal codes and the area name, and in the customer's own words (the message, earlier turns, notes, the goal name) a first name from a built-in list of about 200 Finnish and English names becomes `[name]`. Names not on that list, and Finnish forms that change the stem (Matti, Matin), are sent as typed. Both the Claude and the Gemini path do this.

| Tool | The model receives | Kept only on the customer's own screen |
|---|---|---|
| `list_transactions` | count, total, spent; at most 25 rows of date, amount, category and label, basket, night-out flag, row id | time of day, all 50 rows |
| `explore_my_data` | the result of its SQL on a copy of the customer's own rows with only date, time, amount, balance, type, category, MCC, label, basket, context and row id; there is no merchant column to read | |
| `get_receipts` | at most 5 receipts with store chain (Prisma, S-market, Alepa, Sale, ABC), date, total and at most 12 simulated lines each | time of day, transaction id, the other receipts and lines |
| `find_leaks` | the patterns and repeating charges by category and amount | the merchant reference |
| every other tool | its result, anonymised as above | |

The row id is kept so the model can recategorise one purchase for the customer. "What the AI saw" shows exactly this.

## Tests

```bash
python -m unittest discover -s tests
```

TODO(tests): the last run printed `Ran N tests` and `OK`. The same suite runs on GitHub for every pull request and every push to `main` (Python 3.13, no key, no dataset). The tests use an invented population, need no network and no real dataset, and cannot see a real key: the fixture empties `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` and points `.env` and the key file at files that do not exist. More in `tests/README.md`.

## Honest limits

- The data is synthetic.
- Login is a demo picker, not bank authentication.
- The Claude path was checked live on 14 Nov 2026 with Opus 5.5 (12 turns of the demo script), Sonnet 5.5 and Haiku 5.5 (3 turns each); see the table above. The automated tests use a fake HTTP layer. Gemini has not been tried live.
- TODO(grounding): how the number check works after agent-s5's change (slots filled by code), and what it was checked on.
- TODO(defects): the demo defects agent-s1 fixed, and any still open.
- Receipt lines are simulated: the dataset has merchants and amounts, not basket contents. A real version would read the customer's S Group purchase data with consent.
- The host demo is a stand-in: no real S-mobiili, no real bank login. The handover secret in the code is a demo secret.
- Investment guidance gives a plan with named sources, which is close to regulated advice; this needs S-Pankki's compliance view before real use.
- The S-Pankki name and logo are used with S-Pankki's permission for this demo and pitch only.
- Repeating charges and investment withdrawals are rare in the synthetic data, so subscription detection and the savings-leakage alert often have nothing to show.
- This is a hackathon prototype. See "What a real launch would still need" in `docs/SECURITY_PLAN.md`.

## Data sources and licences

- Challenge dataset: Junction 2026 S-Pankki synthetic data, https://github.com/hackjunction/Junction-2026-S-pankki. Not redistributed here.
- Statistics Finland, Household Budget Survey 2022, table 14q4, household consumption expenditure by age of reference person (`app/open_data.json`). https://pxdata.stat.fi/PxWeb/pxweb/en/StatFin/StatFin__ktutk/statfin_ktutk_pxt_14q4.px/
- Statistics Finland, Paavo open data by postal code area, data year 2024, licence CC BY 4.0 (`app/paavo.json`). https://pxdata.stat.fi/PxWeb/pxweb/en/Postinumeroalueittainen_avoin_tieto/Postinumeroalueittainen_avoin_tieto__2026/
