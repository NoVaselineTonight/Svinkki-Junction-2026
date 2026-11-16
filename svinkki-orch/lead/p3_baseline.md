# P3 repros on main 2925f5e, offline (no key), Veeti, 2026-09-26 — run by agent-s
- "what did i spend at restaurants between june and august 2026" -> "You spent €71.42 on restaurants in June (6 payments). In May you spent nothing on restaurants."  (June only, silently) CONFIRMED
- "how much on coffee in the last 3 months" -> help text (not understood) CONFIRMED
- "Send 200 euros to my friend's account FI21 1234 5600 0007 85" -> REFUSAL_OTHER text CONFIRMED
- "Should I buy bitcoin?" -> "How much does the bitcoin cost?..." CONFIRMED
- "did I pay 12 for a ticket to the airport?" -> offline: generic last-month total €2,029.17 (not refused offline, but wrong answer; with model on the guardrail path may differ)
- "Did Anna pay me back?" -> answered in Finnish ("Käytit 2 029,17 € viime kuussa") CONFIRMED (and wrong content)
- taxi: "€92.85 on taxis last month (2 payments)"
- /api/account next_payday 2026-10-15 (PR 29 fixed payday; verify card label "Safe to spend until 15 Oct" in UI)
