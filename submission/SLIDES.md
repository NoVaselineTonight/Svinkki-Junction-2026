# Pitch deck: status and cost slides

## Ready-made decks (14 Nov 2026)

`submission/deck/` holds two short decks built from real screenshots of the app on the synthetic
data (Veeti, 32; Mikko, 54 for the consent screen). Open the HTML in a browser: arrow keys or click
to move, F for full screen. The PDFs are the same slides, one per page.

| File | Slides | Story |
|---|---|---|
| `index.html`, `Svinkki-deck.pdf` | 6 | Not a chatbot · the problem (a statement vs an answer) · proves / acts / teaches · trust (the AI explains, code counts) · cost and fit · the four brief questions |
| `lightning.html`, `Svinkki-60s.pdf` | 3 | Ask your money anything · proves / acts / teaches · why it can ship |

Facts on the slides to re-check before the pitch: the test count (765 on `main` on 14 Nov), the
cost figures below, and that the screenshots still match the app. To refresh a screenshot, replace the PNG in
`submission/deck/img/` (390 px wide phone at 2x) and re-export the PDF with Chrome's print to PDF.

## Older text deck

The first deck was a claude.ai artifact owned by the team lead; it has 4 slides. These are the
texts for the two slides that change as the build moves. Re-check the bracketed facts
just before the pitch and do not round them up.

## Slide: Status (what works today)

**Works today**
- A start page with the account card (balance, safe to spend until payday), four example
  questions, last month in the three baskets, the check-in and the quiz; earlier conversations and
  "Your things" (goal, challenge, notes, kept answers) when they exist. Two follow-up questions under
  each answer; "Everything I can do" lists every topic.
- Chat with your own money, three baskets, safe to spend, what-if, payday forecast, goals,
  benchmarks, quiz, check-in, consent, "What the AI saw".
- Receipt-level questions ("How much do I spend on beer?") on simulated receipt lines.
- Answers in Finnish as well as English.

**Verified**
- Live with Claude: on 13 Nov 2026, Claude Haiku 5.5 answered "How much did I spend on taxis last
  month?" through the app's own tool: €92.85, two transactions shown, on the merged code.
- [N] automated tests pass (765 on `main` on 14 Nov). Tests never see a real key.
- Live with Claude on 14 Nov 2026 on the real dataset: personal answers with the numbers right, but
  too long (up to 7 sentences); agent-d is shortening them.
- Two independent evaluations; [N of 15] major findings fixed. [List any that remain open.]

**Not yet**
- Bank login (demo picker today).
- Real S Group receipt data (simulated lines today).
- Legal review of the privacy plan.

## Slide: Production cost (Claude)

List prices per million tokens, 3 Nov 2026 (USD):

| Model | Input | Output | Cached input |
|---|---|---|---|
| Claude Haiku 5.5 | $0.10 | $0.50 | |
| Claude Sonnet 5.5 | $2 | $10 | $0.10 |
| Claude Opus 5.5 | $4 | $20 | $0.20 |

One chat turn is about 10,000 input tokens across two calls. Output is assumed at about 1,000
tokens including the model's thinking.

| Model | Per chat turn | 1 million turns |
|---|---|---|
| Claude Haiku 5.5 | $0.0015 | $1,500 |
| Claude Sonnet 5.5 | $0.03 | $30,000 |
| Claude Opus 5.5 | $0.06 | $60,000 |

Scale example: if 10% of S-Bank's 3.5 million customers each ask 10 questions a month, that is
3.5 million turns a month: about $5,000 on Haiku, $105,000 on Sonnet, $210,000 on Opus.

Suggested line: "Haiku for everyday questions, about 0.15 cents a turn; the live demo runs on it.
The fixed instructions and tool list repeat in every call, so prompt caching cuts the input cost
further. Code computes every number, so a cheaper model does not mean less accurate figures."

[Before the pitch: replace the 1,000-token output assumption with the usage of a measured live
turn, if one is logged.]
