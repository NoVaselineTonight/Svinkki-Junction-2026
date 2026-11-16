import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:90]
    s = s.replace(old, new)


rep('''Public video, required for the final submission on Sunday 10:00. Record the chat-first build
(branch `agent-a/chat-first` once merged) at phone width, as Veeti, on the demo date
(26 Sep 2026), with the Claude key saved. This follows the two-minute cut in `DEMO.md`
(steps 1, 3, 4, 5, 6, 9, 12), adjusted to agent-a's note of 13 Nov 21:56 UTC: a front page
with "+ New", previous conversations and "Your things"; safe to spend is answered when asked, not
shown on the start page. Narration is about 270 words.''',
'''Public video, required for the final submission on Sunday 10:00. Record `main` at phone width, as
Veeti, on the demo date (26 Sep 2026), with the Claude key saved (Opus 5.5, the default). It follows
`DEMO.md` (steps 1, 3, 4, 5, 7, 8, 11, 13). Narration is about 270 words. A model turn took 4 to 13
seconds live on 14 Nov; cut the waits. TODO(defects): re-check after agent-s1's demo fixes.''')

rep('''| 0:22-0:32 | Front page: "+ New", previous conversations, "Your things" (savings goal, challenge, kept answers) | "This is my front page: my conversations and the things I keep, like my savings goal. Everything else, I just ask." |
| 0:32-0:45 | Tap "+ New", then "What can I ask?", scroll once, tap a question | "No menus to learn. Everything it can do is listed here, from my three spending baskets to what's safe to spend; tap one and it's asked for you." |''',
'''| 0:22-0:32 | Front page: account card (balance €2,227.52, safe to spend until payday), the question box with four example questions, last month in three baskets | "This is my front page: my account, what's safe to spend, and last month in three baskets. Everything else, I just ask." |
| 0:32-0:45 | Tap "Goals, receipts, contracts and more", scroll "Everything I can do" once, tap a question | "No menus to learn. Everything it can do is listed here; tap one and it's asked for you." |''')

rep('''| 1:05-1:20 | Ask "Can I afford a 300 euro jacket?" | "Yes, and about €16 a day is still left until payday. It checks against what's safe to spend, and against my savings goal." |
| 1:20-1:40 | Ask "What do I buy most?", then "How much do I spend on beer?" | "S Group knows what was in the basket, not only what was paid. Here it answers from receipt lines. In this demo they're simulated; with real S Group purchase data it's the same code." |
| 1:40-1:52 | Settings (gear): lower the check-in rhythm; open "What the AI saw" | "I control the rhythm, and I can read exactly what the model was given: results, never my name, account or address." |''',
'''| 1:05-1:15 | Ask "Can I afford a 300 euro jacket?" | "Yes, and about €35 a day is still left until payday on the 15th. It checks against what's safe to spend, and against my savings goal." |
| 1:15-1:30 | Ask "What do I buy most?", then "Show my last receipt" (S-market, €93.04) | "S Group knows what was in the basket, not only what was paid. Here it answers from receipt lines. In this demo they're simulated; with real S Group purchase data it's the same code." |
| 1:30-1:42 | Front page, "Your check-in": "Move €307 to savings", the approval card, "Approve and move" | "It can move money, but only to my own savings or an S-Bank fund, and only after I approve the exact move." |
| 1:42-1:52 | Settings (gear): open "What the AI saw" | "And I can read exactly what the model was given: totals and a few anonymised rows, never my name, account or a shop." |''')

rep('''- Before recording, press "Test the key" in Settings: the replies should show the AI model badge,
  not "On-device rules".''',
'''- Before recording, press "Test the key" in Settings: the small label under each answer should show
  the model's name, not "On-device rules".''')
open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
