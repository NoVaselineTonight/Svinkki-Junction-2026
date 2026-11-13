# Pitch deck: status and cost slides

The deck is a claude.ai artifact owned by the team lead; it has all 15 slides. These are the
current texts for the two slides that change as the build moves. Re-check the bracketed facts
just before the pitch and do not round them up.

## Slide: Status (what works today)

**Works today**
- One conversation for everything, with a "What can I ask?" page. [Confirm the chat-first build
  is merged.]
- Chat with your own money, three baskets, safe to spend, what-if, payday forecast, goals,
  benchmarks, quiz, check-in, consent, "What the AI saw".
- Receipt-level questions ("How much do I spend on beer?") on simulated receipt lines.
- Answers in Finnish as well as English.

**Verified**
- Live with Claude: on 13 Nov 2026, Claude Haiku 5.5 answered "How much did I spend on taxis last
  month?" through the app's own tool: €92.85, two transactions shown, on the merged code.
- [N] automated tests pass (419 on `main` on 13 Nov; 600 on the chat-first branch while in
  progress). Tests never see a real key.
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
