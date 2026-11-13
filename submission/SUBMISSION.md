# Junction Platform submission (draft)

Draft text for the project submission form. Draft deadline Friday 23:59, final Sunday 10:00.
Fields marked TODO need a link or a fact that does not exist yet.

## Project name

Svinkki: talk with your own money

## One-line pitch

A mobile-first money coach that answers questions from your own transactions, shows the purchases
behind every number, and only lets an AI model see anonymised data you agreed to share.

## Challenge

Personal Economic Trainer (S-Pankki)

## Description

Banking apps stop at statements. Svinkki lets an S-Bank customer ask their money questions in plain
language: "How much did I spend on taxis last month?", "What kind of spender am I?", "What can I
safely spend this week?", "How much could I save if I cut dining out by 20%?".

**Every number is computed by code, never by the AI model.** The model chooses which of the app's
read-only tools to call and explains the result. Each answer carries the transactions it was added
up from, under "Transactions used", so the customer can check it.

**The three baskets are the teaching frame.** Every outflow lands in exactly one basket: regular
essentials, unexpected necessities, everyday spending. Classification uses context: a kebab or a
taxi in the middle of a night out counts as "Night out", not food or transport.

**Built for financial literacy:**
- Safe to spend this week and until payday, with the working shown and a day-by-day forecast.
- What-if simulations in chat and with sliders.
- A weekly quiz: "Guess how much you spent on X this week", then the real figure and a tip.
- A monthly check-in with opt-in suggestions ("You had €307 left over. Set it aside?"). Accepting
  records the intent; no money moves.
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
| Mobile UX | Phone-width, chat-first, cards on Home, consent and frequency in two screens |
| Feasibility | Runs on the provided dataset today; TODO test count; Claude via the Messages API with a per-turn cost estimate |
| S-mobiili integration | No build step, embeddable in a WebView, identity held server-side, ready for bank login |

## AI model and cost

Claude through the Anthropic Messages API, with the app's own tools. Claude Haiku 5.5 for everyday
questions costs about €0.002 per chat turn at list price; see `submission/SLIDES.md` for the
calculation. TODO: confirm once the Claude integration is merged and a live call has been made.

## Links

- Source code: https://github.com/NoVaselineTonight/Svinkki-Junction-2026 (TODO: the repository is
  private; make it public or add the judges before submitting)
- Demo video (public, at most 2 minutes): TODO
- Pitch deck: TODO (share link from the deck's Share menu)

## Team

TODO: names
