import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:90]
    s = s.replace(old, new)


rep('''numbers computed from your transactions with the purchases shown, and let an AI model see only the
anonymised results you agreed to share.''',
'''numbers computed from your transactions with the purchases shown, move money to your own savings
only after you approve it, and let an AI model see only the anonymised results you agreed to share.''')

rep('''**Every number is computed by code, never by the AI model.** Claude chooses which of the app's
read-only tools to call and explains the result. Each answer carries the transactions it was added
up from, under "Transactions used", so the customer can check it. If the model is unavailable, the
same questions are answered by built-in rules with the same figures, and the reply says so.''',
'''**Every number about your money is computed by code, never by the AI model.** Claude chooses which
of the app's tools to call and explains the result. Each answer carries the transactions it was added
up from, under "Transactions used", so the customer can check it, and says where it came from
("On-device rules" or the model's name). If the model is unavailable or has not answered within 60
seconds, the same questions are answered by built-in rules with the same figures, and the reply says
so. TODO(grounding): one sentence on the slot-based number check once it is merged.''')

rep('''- A monthly check-in with opt-in suggestions ("You had €307 left over. Set it aside?"). Accepting
  records the intent; no money moves.''',
'''- A monthly check-in with opt-in suggestions ("Move €307 to your S-Bank savings account?"). An
  approval card shows the amount, from, to and the balance after; nothing moves until the customer
  taps "Approve", only to their own S-Bank savings account or an S-Bank fund, and never money needed
  for bills before payday. Payments and transfers to anyone else are refused.
- "How should I invest my money?" gets a plan worked out by code for this customer (buffer first,
  then a monthly split with a global index fund), using 38 statements and 13 figures from 45 named
  Finnish and EU sources (Pörssisäätiö, Finanssivalvonta, Verohallinto, Suomen Pankki, S-Pankki and
  others); the answer names its source.''')

rep('''The AI model never receives a name, customer id, postal code or exact age, and "What the AI saw"
shows the exact payload of the last turn. With the AI switched off, built-in rules answer the same
questions.''',
'''The AI model never receives a name, customer id, merchant, account number, postal code or exact
age. It gets totals and at most 25 trimmed transaction rows (date, amount, category), its own SQL runs
on a copy of the customer's rows that has no merchant column, and first names the customer types
("Did Anna pay me back?") are replaced with "[name]" when they are on a built-in list of common
Finnish and English names. "What the AI saw" shows the exact payload of the last turn. With the AI
switched off, built-in rules answer the same questions.''')

rep('''**Ready for S-mobiili:** a phone-width web app with no build step and no external requests, made to
sit in a WebView. Python standard library only on the server.''',
'''**Ready for S-mobiili:** a phone-width web app with no build step, made to sit in a WebView or an
iframe. A local S-mobiili stand-in (`python -m app.host_demo`) shows the integration: the host's
server hands over the customer it has already authenticated with a shared secret, Svinkki answers
with a signed single-use token that lasts 60 seconds and names no customer, and the embedded page
trades it for a session. Only allowed host pages may frame the app, and requests from other sites
that change anything are refused. Python standard library only on the server; the tests run on every
pull request.''')

rep('''| Feasibility | Runs on the provided dataset today; checked live with Claude Haiku 5.5; TODO final test count; about 0.15 cents per answer on Haiku |
| S-mobiili integration | No build step, embeddable in a WebView, identity held server-side, ready for bank login |''',
'''| Feasibility | Runs on the provided dataset today; checked live with Claude Opus 5.5 on 12 demo turns (median 6.5 s, slowest 13 s, about $0.034 a turn); TODO(tests) final test count, run on every pull request; TODO(cost) final cost per turn |
| S-mobiili integration | No build step; embeds in a host app through a signed identity handover (demo stand-in included); identity held server-side; money moves only inside S-mobiili after approval |''')

rep('''Claude through the Anthropic Messages API over plain HTTP (no dependencies), with the app's own
read-only tools. Checked live on 13 Nov 2026: Claude Haiku 5.5 answered "How much did I spend on
taxis last month?" with €92.85 and the two transactions, computed by the app's tool. Haiku costs
about 0.15 cents (USD) per answered question at list price; Opus 5.5 is selectable in Settings for
harder questions. Calculation in `submission/SLIDES.md`.''',
'''Claude through the Anthropic Messages API over plain HTTP (no dependencies), with the app's own
tools. Opus 5.5 is the default; Sonnet 5.5 and Haiku 5.5 can be chosen in Settings. Measured live on
14 Nov 2026 on the real dataset as the demo customer, with a warm prompt cache, at list prices:

| Model | Turns measured | Median | Slowest | Mean cost per turn (USD) |
|---|---|---|---|---|
| Opus 5.5 | 12 | 6.5 s | 13.0 s | $0.034 |
| Sonnet 5.5 | 3 | 3.5 s | 4.6 s | $0.024 |
| Haiku 5.5 | 3 | 3.8 s | 4.4 s | $0.0014 |

Opus answered "How much did I spend on taxis last month?" with €92.85 and the two transactions,
computed by the app's tool. A whole turn is capped at 60 seconds. TODO(cost): final cost per turn.''')
open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
