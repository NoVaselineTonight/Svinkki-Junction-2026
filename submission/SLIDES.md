# Pitch deck: missing and outdated slides

The deck itself is a claude.ai artifact owned by the team lead. These are the texts to paste in.

## Slide: Status (what works today)

Fill in the bracketed facts just before the pitch; do not round them up.

**Works today**
- Runs on the full synthetic dataset: chat, three baskets, safe to spend, what-if, benchmarks,
  quiz, check-in, consent, "What the AI saw".
- [N] automated tests pass (372 on 13 Nov; [N] with the Claude integration).
- Every number traceable to its transactions; other customers' data unreachable (tested).

**Verified**
- [Claude live: "answered real questions on [date]" / "tested against a fake HTTP layer only"]
- [Independent evaluation: verdict and open defects, from `.devloop/eval-1.md`]

**Not yet**
- Bank login (demo picker today).
- Legal review of the privacy plan.
- Subscription and savings-leak detection rarely trigger on synthetic data.

## Slide: Production cost (Claude), replaces the Gemini figures

List prices per million tokens, 3 Nov 2026 (USD):

| Model | Input | Output | Cached input |
|---|---|---|---|
| Claude Haiku 5.5 | $0.10 | $0.50 | |
| Claude Sonnet 5.5 | $2 | $10 | $0.10 |
| Claude Opus 5.5 | $4 | $20 | $0.20 |

One chat turn is about 10,000 input tokens across two calls (from the handoff notes). Output
is assumed at about 1,000 tokens including the model's thinking; measure it from the API's
`usage` field once the integration runs.

| Model | Per chat turn | 1 million turns |
|---|---|---|
| Claude Haiku 5.5 | $0.0015 | $1,500 |
| Claude Sonnet 5.5 | $0.03 | $30,000 |
| Claude Opus 5.5 | $0.06 | $60,000 |

Scale example: if 10% of S-Bank's 3.5 million customers each ask 10 questions a month, that is
3.5 million turns a month: about $5,000 on Haiku, $105,000 on Sonnet, $210,000 on Opus.

Suggested line for the slide: "Haiku for everyday questions, about 0.15 cents a turn. The fixed
instructions and tool list are the same in every call, so prompt caching cuts the input cost
further. Numbers are computed by code, so a cheaper model does not mean less accurate figures."

Before the pitch: replace the per-turn assumption with a measured turn from the live integration.
