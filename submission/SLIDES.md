# Pitch deck: status and cost slides

## Ready-made decks (14 Nov 2026)

`submission/deck/` holds two short decks built from real screenshots of the app on the synthetic
data (Veeti, 32; Mikko, 54 for the consent screen). Open the HTML in a browser: arrow keys or click
to move, F for full screen. The PDFs are the same slides, one per page.

| File | Slides | Story |
|---|---|---|
| `index.html`, `Svinkki-deck.pdf` | 8 | Not a chatbot · the problem (a statement vs an answer) · proves / acts / teaches · ask it the hard questions (afford, goal by date, payday warning) · it plans with you (salary split, what-if, mortgage readiness) · trust (the AI explains, code counts) · cost and fit · the four brief questions |
| `lightning.html`, `Svinkki-60s.pdf` | 5 | Ask your money anything · proves / acts / teaches · the hard questions · it plans with you · why it can ship |

The answers on the two question slides come from the app's built-in rules (no AI key) for Veeti,
Joonas and Helmi; with Claude on, the figures are the same and the wording is the model's.

Facts on the slides to re-check before the pitch: the test count (TODO(tests): final count), the
cost figures below, and that the screenshots still match the app (the web UX changed on 14 Nov:
Back button, the answer's source under each answer, cents on looked-up amounts). To refresh a screenshot, replace the PNG in
`submission/deck/img/` (390 px wide phone at 2x) and re-export the PDF with Chrome's print to PDF.

## Older text deck

The first deck was a claude.ai artifact owned by the team lead; it has 4 slides. These are the
texts for the two slides that change as the build moves. Re-check the bracketed facts
just before the pitch and do not round them up.

## Slide: Status (what works today)

**Works today**
- A start page with the account card (balance, safe to spend until payday), four example
  questions, last month in the three baskets, the check-in and the quiz; earlier conversations and
  "Your things" (goal, challenge, notes, kept answers) when they exist. Follow-up questions under
  each answer (written by the model when it is on); "Everything I can do" lists every topic.
- Chat with your own money, three baskets, safe to spend, what-if, payday forecast, goals,
  benchmarks, quiz, check-in, consent, "What the AI saw".
- Money moves to the customer's own S-Bank savings account or an S-Bank fund, only after they
  approve the exact move.
- Investment plans from 45 named Finnish and EU sources.
- Embedding in S-mobiili: signed identity handover and a local S-mobiili stand-in.
- Receipt-level questions ("How much do I spend on beer?") on simulated receipt lines.
- Answers in Finnish as well as English.

**Verified**
- Live with Claude Opus 5.5 on 14 Nov 2026 on the real dataset: the 12 demo turns answered with
  the app's figures (taxis €92.85 with the two rides; the €300 jacket fits with about €35 a day to
  payday on 15 Oct), median 6.5 s, slowest 13 s. Sonnet 5.5 and Haiku 5.5 checked on 3 questions each.
- TODO(tests): [N] automated tests pass, on every pull request. Tests never see a real key.
- Two independent evaluations; [N of 15] major findings fixed. [List any that remain open.]

**Not yet**
- Bank login (demo picker today; the S-mobiili handover is shown with a local stand-in).
- Real S Group receipt data (simulated lines today).
- Legal review of the privacy plan.

## Slide: Production cost (Claude)

List prices per million tokens, 3 Nov 2026 (USD):

| Model | Input | Output | Cached input |
|---|---|---|---|
| Claude Haiku 5.5 | $0.10 | $0.50 | |
| Claude Sonnet 5.5 | $2 | $10 | $0.10 |
| Claude Opus 5.5 | $4 | $20 | $0.20 |

Measured live on 14 Nov 2026 (real dataset, demo customer, warm prompt cache; the fixed
instructions and tool list, about 17,000 tokens, are read from the cache in every request). A lookup
is two requests, a goal plan or a receipt four.

| Model | Turns measured | Mean per chat turn | 1 million turns |
|---|---|---|---|
| Claude Haiku 5.5 | 3 | $0.0014 | $1,400 |
| Claude Sonnet 5.5 | 3 (one wrote the cache) | $0.024 | $24,000 |
| Claude Opus 5.5 | 12 | $0.034 | $34,000 |

Scale example: if 10% of S-Bank's 3.5 million customers each ask 10 questions a month, that is
3.5 million turns a month: about $4,900 on Haiku, $83,000 on Sonnet, $119,000 on Opus.

Suggested line: "The demo runs on Opus, about 3 cents a turn; Haiku answers the same lookups for
about a seventh of a cent. Code computes every number, so a cheaper model does not mean less
accurate figures." Haiku and Sonnet were measured on three questions only.

TODO(cost): final cost per turn after the number-grounding change.
