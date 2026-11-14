# Demo video script (at most 2:00)

Public video, required for the final submission on Sunday 10:00. Record `main` at phone width, as
Veeti, on the demo date (26 Sep 2026), with the Claude key saved (Opus 5.5, the default). It follows
`DEMO.md` (steps 1, 3, 4, 5, 7, 8, 11, 13). Narration is about 270 words. A model turn took 4 to 13
seconds live on 14 Nov; cut the waits. TODO(defects): re-check after agent-s1's demo fixes.

With Claude the wording varies a little between runs; the figures do not, because code
computes them. Check every amount below on the recording machine before recording.

| Time | On screen | Narration |
|---|---|---|
| 0:00-0:10 | Title card, then a plain transaction list | "Banking apps show you a list. They don't tell you where your money goes, what's safe to spend, or what a change would do." |
| 0:10-0:22 | Log in as Veeti; "Your data, your choices"; "How much do you want to hear from me?" | "Svinkki is a coach, not a nag. I choose what it may use, whether an AI model is involved, and how often it speaks." |
| 0:22-0:32 | Front page: account card (balance €2,227.52, safe to spend until payday), the question box with four example questions, last month in three baskets | "This is my front page: my account, what's safe to spend, and last month in three baskets. Everything else, I just ask." |
| 0:32-0:45 | Tap "Goals, receipts, contracts and more", scroll "Everything I can do" once, tap a question | "No menus to learn. Everything it can do is listed here; tap one and it's asked for you." |
| 0:45-1:05 | Ask "How much did I spend on taxis last month?"; open "Transactions used (2)" | "€92.85 on taxis, across two rides, and here are the two rides. Claude chooses the tool and explains; code does the maths. Every number shows where it came from." |
| 1:05-1:15 | Ask "Can I afford a 300 euro jacket?" | "Yes, and about €35 a day is still left until payday on the 15th. It checks against what's safe to spend, and against my savings goal." |
| 1:15-1:30 | Ask "What do I buy most?", then "Show my last receipt" (S-market, €93.04) | "S Group knows what was in the basket, not only what was paid. Here it answers from receipt lines. In this demo they're simulated; with real S Group purchase data it's the same code." |
| 1:30-1:42 | Front page, "Your check-in": "Move €307 to savings", the approval card, "Approve and move" | "It can move money, but only to my own savings or an S-Bank fund, and only after I approve the exact move." |
| 1:42-1:52 | Settings (gear): open "What the AI saw" | "And I can read exactly what the model was given: totals and a few anonymised rows, never my name, account or a shop." |
| 1:52-2:00 | Logo and one line | "Svinkki. Talk with your own money, inside S-mobiili." |

## Recording notes

- Before recording, press "Test the key" in Settings: the small label under each answer should show
  the model's name, not "On-device rules". If Claude is down, the app answers from its rules and says so; the
  narration still fits, but re-record when Claude is back if time allows.
- Say "simulated" for the receipt lines every time; the dataset has amounts, not basket contents.
- Phone-width window (about 390 px), other tabs closed, notifications off.
- Upload so that anyone with the link can watch without signing in (check the Junction rules on
  what counts as public) and paste the link into `SUBMISSION.md`.
