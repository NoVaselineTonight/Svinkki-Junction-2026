# Junction Platform submission (draft)

Draft text for the project submission form. Draft deadline Friday 23:59, final Sunday 10:00.
Fields marked TODO need a link or a fact that does not exist yet.

## Project name

Svinkki: talk with your own money

## One-line pitch

A money coach you talk to: ask about your own spending in plain English or Finnish, get
numbers computed from your transactions with the purchases shown, move money to your own savings
only after you approve it, and let an AI model see only the anonymised results you agreed to share.

## Challenge

Personal Economic Trainer (S-Pankki)

## Description

Banking apps stop at statements. Svinkki is a coach, not a nag: inside S-mobiili an S-Bank
customer starts a conversation and asks their money questions in plain English or Finnish: "How much did I
spend on taxis last month?", "Can I afford a 300 euro jacket?", "Will I make it to payday?", "How
much could I save if I cut dining out by 20%?". A "What can I ask?" page lists everything it can do,
so there are no menus to learn. The front page holds previous conversations and "Your things":
the savings goal, a challenge and answers the customer chose to keep.

**Every number about your money is computed by code, never by the AI model.** Claude chooses which
of the app's tools to call and explains the result. Each answer carries the transactions it was added
up from, under "Transactions used", so the customer can check it, and says where it came from
("On-device rules" or the model's name). If the model is unavailable or has not answered within 60
seconds, the same questions are answered by built-in rules with the same figures, and the reply says
so. TODO(grounding): one sentence on the slot-based number check once it is merged.

**Receipt-level insight.** S Group knows what was in the basket, not only what was paid. Svinkki
answers "What do I buy most?" or "How much do I spend on beer?" from receipt lines. In this
prototype the receipt lines are simulated, because the challenge data has amounts only; with real
S Group purchase data and the customer's consent, it is the same code.

**The three baskets are the teaching frame.** Every outflow lands in exactly one basket: regular
essentials, unexpected necessities, everyday spending. Classification uses context: a kebab or a
taxi in the middle of a night out counts as "Night out", not food or transport.

**Built for financial literacy:**
- Safe to spend this week and until payday, with the working shown and a day-by-day forecast.
- What-if simulations in chat and with sliders.
- A weekly quiz: "Guess how much you spent on X this week", then the real figure and a tip.
- A monthly check-in with opt-in suggestions ("Move €307 to your S-Bank savings account?"). An
  approval card shows the amount, from, to and the balance after; nothing moves until the customer
  taps "Approve", only to their own S-Bank savings account or an S-Bank fund, and never money needed
  for bills before payday. Payments and transfers to anyone else are refused.
- "How should I invest my money?" gets a plan worked out by code for this customer (buffer first,
  then a monthly split with a global index fund), using 38 statements and 13 figures from 45 named
  Finnish and EU sources (Pörssisäätiö, Finanssivalvonta, Verohallinto, Suomen Pankki, S-Pankki and
  others); the answer names its source.
- Benchmarks against similar customers (groups of at least 20) and Statistics Finland open data.
- A plain-language explainer for pasted loan or fund text, and a mortgage readiness check (a check,
  not a credit decision).

**Trust and privacy by design (MyData):** the customer switches on each use of their data
separately (analysis, AI model, comparison, suggestions) and chooses how often the app speaks.
The AI model never receives a name, customer id, merchant, account number, postal code or exact
age. It gets totals and at most 25 trimmed transaction rows (date, amount, category), its own SQL runs
on a copy of the customer's rows that has no merchant column, and first names the customer types
("Did Anna pay me back?") are replaced with "[name]" when they are on a built-in list of common
Finnish and English names. "What the AI saw" shows the exact payload of the last turn. With the AI
switched off, built-in rules answer the same questions.

**Ready for S-mobiili:** a phone-width web app with no build step, made to sit in a WebView or an
iframe. A local S-mobiili stand-in (`python -m app.host_demo`) shows the integration: the host's
server hands over the customer it has already authenticated with a shared secret, Svinkki answers
with a signed single-use token that lasts 60 seconds and names no customer, and the embedded page
trades it for a session. Only allowed host pages may frame the app, and requests from other sites
that change anything are refused. Python standard library only on the server; the tests run on every
pull request.

## How it meets the judging criteria

| Criterion | What Svinkki does |
|---|---|
| Financial literacy | Three baskets on every purchase, quiz, check-in, what-if, plain-language explainer |
| Originality of AI integration | The model plans and explains, code calculates, every figure is traceable to transactions, the customer sees what the model saw |
| Mobile UX | Phone-width; a front page with conversations and "Your things", everything else asked in chat; "What can I ask?" page; consent and frequency in two screens |
| Feasibility | Runs on the provided dataset today; checked live with Claude Opus 5.5 on 12 demo turns (median 6.5 s, slowest 13 s, about $0.034 a turn); TODO(tests) final test count, run on every pull request; TODO(cost) final cost per turn |
| S-mobiili integration | No build step; embeds in a host app through a signed identity handover (demo stand-in included); identity held server-side; money moves only inside S-mobiili after approval |

## AI model and cost

Claude through the Anthropic Messages API over plain HTTP (no dependencies), with the app's own
tools. Opus 5.5 is the default; Sonnet 5.5 and Haiku 5.5 can be chosen in Settings. Measured live on
14 Nov 2026 on the real dataset as the demo customer, with a warm prompt cache, at list prices:

| Model | Turns measured | Median | Slowest | Mean cost per turn (USD) |
|---|---|---|---|---|
| Opus 5.5 | 12 | 6.5 s | 13.0 s | $0.034 |
| Sonnet 5.5 | 3 | 3.5 s | 4.6 s | $0.024 |
| Haiku 5.5 | 3 | 3.8 s | 4.4 s | $0.0014 |

Opus answered "How much did I spend on taxis last month?" with €92.85 and the two transactions,
computed by the app's tool. A whole turn is capped at 60 seconds. TODO(cost): final cost per turn.

## Links

- Source code: https://github.com/NoVaselineTonight/Svinkki-Junction-2026 (TODO: the repository is
  private; make it public or add the judges before submitting)
- Demo video (public, at most 2 minutes): TODO
- Pitch deck: TODO (share link from the deck's Share menu)

## Team

TODO: names
