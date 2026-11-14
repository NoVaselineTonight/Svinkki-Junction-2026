# Junction Platform submission (draft)

Draft text for the project submission form. Draft deadline Friday 23:59, final Sunday 10:00.
Fields marked TODO need a link or a fact that does not exist yet.

## Project name

Svinkki: talk with your own money

## One-line pitch

A money coach you talk to: ask about your own spending in plain English or Finnish, get
numbers computed from your transactions with the purchases shown, and let an AI model see only the
anonymised results you agreed to share.

## Challenge

Personal Economic Trainer (S-Pankki)

## Description

Banking apps stop at statements. Svinkki is a coach, not a nag: inside S-mobiili an S-Bank
customer starts a conversation and asks their money questions in plain English or Finnish: "How much did I
spend on taxis last month?", "Can I afford a 300 euro jacket?", "Will I make it to payday?", "How
much could I save if I cut dining out by 20%?". A "What can I ask?" page lists everything it can do,
so there are no menus to learn. The front page holds previous conversations and "Your things":
the savings goal, a challenge and answers the customer chose to keep.

**Every number is computed by code, never by the AI model.** Claude chooses which of the app's
read-only tools to call and explains the result. Each answer carries the transactions it was added
up from, under "Transactions used", so the customer can check it. If the model is unavailable, the
same questions are answered by built-in rules with the same figures, and the reply says so.

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
- A daily quiz: a personal round of six questions about your money and money skills, picked and
  worded by the AI, with the right answers computed by code.
- A monthly check-in with opt-in suggestions ("You had €307 left over. Set it aside?"). "Approve and
  move" moves the money inside the simulated S-mobiili account, only after the customer approves that
  exact move; nothing can leave S-mobiili.
- Benchmarks against similar customers (groups of at least 20) and Statistics Finland open data.
- A plain-language explainer for pasted loan or fund text, and a mortgage readiness check (a check,
  not a credit decision).

**Trust and privacy by design (MyData):** the customer switches on each use of their data
separately (analysis, AI model, comparison, suggestions) and chooses how often the app speaks.
The AI model never receives a name, customer id, postal code or exact age, and "What the AI saw"
shows the exact payload of the last turn. With the AI switched off, built-in rules answer the same
questions.

**Ready for S-mobiili:** a phone-width web app with no build step and no external requests, made to
sit in a WebView. Python standard library only on the server.

## How it meets the judging criteria

| Criterion | What Svinkki does |
|---|---|
| Financial literacy | Three baskets on every purchase, quiz, check-in, what-if, plain-language explainer |
| Originality of AI integration | The model plans and explains, code calculates, every figure is traceable to transactions, the customer sees what the model saw |
| Mobile UX | Phone-width; a front page with conversations and "Your things", everything else asked in chat; "What can I ask?" page; consent and frequency in two screens |
| Feasibility | Runs on the provided dataset today; checked live with Claude Opus 5.5 (the default); about $0.06 per answer on Opus 5.5 and about 0.15 cents on Haiku 5.5 at list price; tests: `python -m unittest discover -s tests` |
| S-mobiili integration | No build step, embeddable in a WebView, identity held server-side, ready for bank login |

## AI model and cost

Claude through the Anthropic Messages API over plain HTTP (no dependencies), with the app's own
read-only tools. The default model is Claude Opus 5.5, checked live on 14 Nov 2026 in an audit of
about 230 answers: "How much did I spend on taxis last month?" gives €92.85 and the two
transactions, computed by the app's tool. Opus 5.5 costs about $0.06 per answered question at list
price; Haiku 5.5 costs about 0.15 cents and is selectable in Settings. Calculation in
`submission/SLIDES.md`.

## Links

- Source code: https://github.com/NoVaselineTonight/Svinkki-Junction-2026 (TODO: the repository is
  private; make it public or add the judges before submitting)
- Live demo: https://svinkki.onrender.com (free plan: sleeps when idle; see `docs/DEPLOY.md`)
- Demo video (public, at most 2 minutes): TODO
- Pitch deck: TODO (share link from the deck's Share menu)

## Team

TODO: names
