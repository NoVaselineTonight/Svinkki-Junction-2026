import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:90]
    s = s.replace(old, new)


rep('''It is a web app with a phone-width layout and no build step, so it can be embedded in a mobile app such as S-mobiili.''',
'''It is a web app with a phone-width layout and no build step, and it can be embedded in a host app such as S-mobiili: a local stand-in for S-mobiili shows the identity handover and the iframe (see "Inside S-mobiili" below).''')

rep('''The synthetic dataset is not in this repository. Download it from https://github.com/hackjunction/Junction-2026-S-pankki (the transactions file is stored with Git LFS, so use `git lfs` or the browser's "Download raw file" button), then:

```bash
SVINKKI_DATA_DIR=/path/to/dataset-folder python -m app.ingest   # builds data/svinkki.db
python -m app.server                                            # serves the app
```''',
'''The synthetic dataset is not in this repository. Download it from https://github.com/hackjunction/Junction-2026-S-pankki (the transactions file is stored with Git LFS, so use `git lfs` or the browser's "Download raw file" button) and put the CSV files in a folder named `dataset/` in the repository root (git-ignored), or point `SVINKKI_DATA_DIR` at another folder. Then:

```bash
python -m app.ingest    # reads dataset/ (or SVINKKI_DATA_DIR), builds data/svinkki.db
python -m app.server    # serves the app
```

`python -m app.ingest` stops with a message naming `SVINKKI_DATA_DIR` when the folder is missing.''')

rep('''| `SVINKKI_DATA_DIR` | a folder on the author's machine | Folder with the dataset CSV files |''',
'''| `SVINKKI_DATA_DIR` | `dataset` | Folder with the dataset CSV files (relative to the repository root) |''')
rep('''| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Gemini model name |''',
'''| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Gemini model name |
| `SVINKKI_HOST_SECRET` | a built-in demo secret, accepted only from this computer | Shared secret the host app (S-mobiili) uses for the identity handover |
| `SVINKKI_FRAME_ANCESTORS` | `'self' http://127.0.0.1:8031 http://localhost:8031` | Pages allowed to show the app in an iframe (CSP `frame-ancestors`) |''')

rep('''Never commit a key: `claude_api_key.txt` and `.env` are git-ignored. With a key, chat and the text explainer use Claude, which calls the app's tools to get every number. Without a key, or when the customer switches AI off in Settings, built-in rules answer the same questions, and the reply is labelled "On-device rules". If Claude fails, declines or is slow, the built-in rules answer and the reply says so. The model only receives anonymised summaries, and only with the customer's consent.''',
'''Never commit a key: `claude_api_key.txt` and `.env` are git-ignored. With a key, chat and the text explainer use Claude, which calls the app's tools to get every number. Without a key, or when the customer switches AI off in Settings, built-in rules answer the same questions. Every answer says where it came from, in small text under it: "On-device rules", or the name of the Claude model. If Claude fails, declines or does not finish within 60 seconds (a hard cap on the whole turn, every request included), the built-in rules answer and the reply says so. The model receives only what is listed under "What the model receives" below, and only with the customer's consent.

Measured live on 14 Nov 2026 on the real dataset as Veeti, one question at a time with a warm prompt cache (`.devloop/live-check/harness.py`):

| Model | Turns | Median | Slowest | Mean cost per turn (USD, list price) |
|---|---|---|---|---|
| Claude Opus 5.5 (default) | 12 | 6.5 s | 13.0 s | $0.034 |
| Claude Sonnet 5.5 | 3 | 3.5 s | 4.6 s | $0.024 (one of the three turns wrote the cache) |
| Claude Haiku 5.5 | 3 | 3.8 s | 4.4 s | $0.0014 |

A lookup takes two requests; a goal plan or a receipt takes four. Sonnet and Haiku were measured on three questions only. TODO(cost): final cost per turn after the number-grounding change.''')

rep('''- Chat with your own money, with the transactions behind each answer under it ("From 2 transactions"), and two short follow-up questions under the latest answer.''',
'''- Chat with your own money, with the transactions behind each answer under it ("From 2 transactions"), and follow-up questions under the latest answer (written by the model when it is on, in English or Finnish; a fixed list otherwise).''')

rep('''An empty conversation shows the same examples; after each answer two follow-up questions are offered, chosen by the answer's card (none for Finnish questions).''',
'''An empty conversation shows the same examples; after each answer follow-up questions are offered (the model's own when it is on, otherwise two chosen by the answer's card). The phone's or browser's Back button closes a sheet, then leaves a conversation for the start page, and leaves the app only from the start page.''')

rep('''- Save and invest inside S-mobiili:''', '''- Investment guidance from named Finnish sources: "How should I invest my money?" gets a plan worked out by code for this customer (what being below zero costs, a buffer of one to three months of spending, a monthly split between the buffer and a global index fund, an illustration at the long-run real return). The facts and rates come from `app/invest_knowledge.json`: 38 statements, 13 figures and 7 products read on 14 Nov 2026 from 45 named pages (Pörssisäätiö, Takuusäätiö, Finanssivalvonta, Verohallinto, Suomen Pankki, S-Pankki and others), each with its source and date; the answer names the source. Rates go stale and several are from secondary pages. This works with the AI model on; without it the built-in rules give a shorter, education-only answer.
- Save and invest inside S-mobiili:''')

rep('''| `app/state.py` |''', '''| `app/invest.py`, `app/invest_knowledge.json` | Investment plan and sourced facts |
| `app/embed.py`, `app/host_demo.py`, `web/embed.js` | Embedding in a host app: identity handover, iframe sessions, the S-mobiili stand-in |
| `app/state.py` |''')

rep('''## Privacy and security
''', '''## Inside S-mobiili (host demo)

S-mobiili would show Svinkki in a WebView or iframe and hand over the customer it has already authenticated. To see it on one computer:

```bash
python -m app.server --port 8030    # Svinkki
python -m app.host_demo             # a phone-width S-mobiili stand-in on port 8031
```

Open http://127.0.0.1:8031 and tap the Svinkki tab. The handover works like this: the host's server calls `POST /api/host/handover` with `Authorization: Bearer $SVINKKI_HOST_SECRET` and the customer; Svinkki returns a signed token that lasts 60 seconds, can be used once and names no customer. The host opens `/embed#handover=<token>` (the fragment never reaches a server log or a Referer), and the page trades the token for a session (`POST /api/embed/session`). The built-in demo secret is accepted only from this computer, and only the demo customers can be handed over. Inside the iframe the session works with a partitioned cookie or, when the browser blocks cookies, with a header kept in the page's memory. Only the pages in `SVINKKI_FRAME_ANCESTORS` may frame the app. 127.0.0.1 and localhost are different sites, so the demo is really cross-site. Checked in headless Chrome on the real dataset without a key, also with all cookies blocked.

## Privacy and security
''')

rep('''- The model gets an anonymised payload (no name, id, postal code or exact age) and only with consent. Settings has "What the AI saw", which shows the last payload exactly.''',
'''- The model gets an anonymised payload (no name, customer id, merchant, postal code or exact age) and only with consent. Settings has "What the AI saw", which shows the last payload exactly. Details in the next section.
- State-changing requests from another site are refused (`Origin` and `Sec-Fetch-Site` checks), and the app can be framed only by the pages in `SVINKKI_FRAME_ANCESTORS`.''')

rep('''The full plan, including what a real launch would still need, is in `docs/SECURITY_PLAN.md`.''',
'''The full plan, including what a real launch would still need, is in `docs/SECURITY_PLAN.md`.

### What the model receives

Every turn: the rules prompt (the same for everyone), the customer's age band and today's date, a short picture of the customer built from the same tools (totals, never single purchases, merchants or other people; the newest six notes; the goal), the conversation so far, the message, and the result of each tool the model calls. Before anything is sent, `coach.anonymise` removes customer, merchant and account ids, postal codes and the area name, and in the customer's own words (the message, earlier turns, notes, the goal name) a first name from a built-in list of about 200 Finnish and English names becomes `[name]`. Names not on that list, and Finnish forms that change the stem (Matti, Matin), are sent as typed. Both the Claude and the Gemini path do this.

| Tool | The model receives | Kept only on the customer's own screen |
|---|---|---|
| `list_transactions` | count, total, spent; at most 25 rows of date, amount, category and label, basket, night-out flag, row id | time of day, all 50 rows |
| `explore_my_data` | the result of its SQL on a copy of the customer's own rows with only date, time, amount, balance, type, category, MCC, label, basket, context and row id; there is no merchant column to read | |
| `get_receipts` | at most 5 receipts with store chain (Prisma, S-market, Alepa, Sale, ABC), date, total and at most 12 simulated lines each | time of day, transaction id, the other receipts and lines |
| `find_leaks` | the patterns and repeating charges by category and amount | the merchant reference |
| every other tool | its result, anonymised as above | |

The row id is kept so the model can recategorise one purchase for the customer. "What the AI saw" shows exactly this.''')

rep('''The last run printed `Ran 761 tests in 49.1s` and `OK`.''',
'''TODO(tests): the last run printed `Ran N tests` and `OK`. The same suite runs on GitHub for every pull request and every push to `main` (Python 3.13, no key, no dataset).''')

rep('''- The Claude path was checked live on 13 Nov 2026 with Claude Haiku 5.5 on a handful of questions. The automated tests use a fake HTTP layer. Gemini has not been tried live.
- The coach prompt was rewritten on 14 Nov (personal answers, the customer picture, medium effort, Opus 5.5 unless another model is chosen in Settings). That version has NOT been run against the live model yet: only the fake HTTP layer has seen it. Ask five questions with a key before a demo.''',
'''- The Claude path was checked live on 14 Nov 2026 with Opus 5.5 (12 turns of the demo script), Sonnet 5.5 and Haiku 5.5 (3 turns each); see the table above. The automated tests use a fake HTTP layer. Gemini has not been tried live.
- TODO(grounding): how the number check works after agent-s5's change (slots filled by code), and what it was checked on.
- TODO(defects): the demo defects agent-s1 fixed, and any still open.''')

rep('''- The S-Pankki name and logo''', '''- The host demo is a stand-in: no real S-mobiili, no real bank login. The handover secret in the code is a demo secret.
- Investment guidance gives a plan with named sources, which is close to regulated advice; this needs S-Pankki's compliance view before real use.
- The S-Pankki name and logo''')
open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
