import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:90]
    s = s.replace(old, new)


rep('''Facts on the slides to re-check before the pitch: the test count (765 on `main` on 14 Nov), the
cost figures below, and that the screenshots still match the app.''',
'''Facts on the slides to re-check before the pitch: the test count (TODO(tests): final count), the
cost figures below, and that the screenshots still match the app (the web UX changed on 14 Nov:
Back button, the answer's source under each answer, cents on looked-up amounts).''')

rep('''- A start page with the account card (balance, safe to spend until payday), four example
  questions, last month in the three baskets, the check-in and the quiz; earlier conversations and
  "Your things" (goal, challenge, notes, kept answers) when they exist. Two follow-up questions under
  each answer; "Everything I can do" lists every topic.
- Chat with your own money, three baskets, safe to spend, what-if, payday forecast, goals,
  benchmarks, quiz, check-in, consent, "What the AI saw".''',
'''- A start page with the account card (balance, safe to spend until payday), four example
  questions, last month in the three baskets, the check-in and the quiz; earlier conversations and
  "Your things" (goal, challenge, notes, kept answers) when they exist. Follow-up questions under
  each answer (written by the model when it is on); "Everything I can do" lists every topic.
- Chat with your own money, three baskets, safe to spend, what-if, payday forecast, goals,
  benchmarks, quiz, check-in, consent, "What the AI saw".
- Money moves to the customer's own S-Bank savings account or an S-Bank fund, only after they
  approve the exact move.
- Investment plans from 45 named Finnish and EU sources.
- Embedding in S-mobiili: signed identity handover and a local S-mobiili stand-in.''')

rep('''- Live with Claude: on 13 Nov 2026, Claude Haiku 5.5 answered "How much did I spend on taxis last
  month?" through the app's own tool: €92.85, two transactions shown, on the merged code.
- [N] automated tests pass (765 on `main` on 14 Nov). Tests never see a real key.
- Live with Claude on 14 Nov 2026 on the real dataset: personal answers with the numbers right, but
  too long (up to 7 sentences); agent-d is shortening them.''',
'''- Live with Claude Opus 5.5 on 14 Nov 2026 on the real dataset: the 12 demo turns answered with
  the app's figures (taxis €92.85 with the two rides; the €300 jacket fits with about €35 a day to
  payday on 15 Oct), median 6.5 s, slowest 13 s. Sonnet 5.5 and Haiku 5.5 checked on 3 questions each.
- TODO(tests): [N] automated tests pass, on every pull request. Tests never see a real key.''')

rep('''**Not yet**
- Bank login (demo picker today).''',
'''**Not yet**
- Bank login (demo picker today; the S-mobiili handover is shown with a local stand-in).''')

rep('''One chat turn is about 10,000 input tokens across two calls. Output is assumed at about 1,000
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
turn, if one is logged.]''',
'''Measured live on 14 Nov 2026 (real dataset, demo customer, warm prompt cache; the fixed
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

TODO(cost): final cost per turn after the number-grounding change.''')
open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
