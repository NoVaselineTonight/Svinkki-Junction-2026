import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:90]
    s = s.replace(old, new)


rep('''Set up: server running on the demo date (26 Sep 2026), browser at phone width, Claude key saved (Settings, "AI model (demo setup)"). Press "Reset demo" in Settings before you start, so the front page is empty. The figures below were captured from the running app as Veeti on 14 Nov, before the coach was made personal. Since then (same day) the Claude answers are two to four sentences: the figure, what it means for him, one next step. That version has NOT been run with a live key yet, so read the answers once before presenting: ask steps 5, 7 and 8 and check they are personal, short and compare with nobody. The figures do not change, because the app computes them. Without a key the built-in rules give the same figures and add one sentence about his own previous month.''',
'''Set up: server running on the demo date (26 Sep 2026), browser at phone width, Claude key saved (Settings, "AI model (demo setup)"; Opus 5.5 is the default). Press "Reset demo" in Settings before you start, so the front page is empty. To show it inside S-mobiili instead, run `python -m app.server --port 8030` and `python -m app.host_demo`, open http://127.0.0.1:8031 and tap the Svinkki tab: the stand-in hands Veeti over without the login picker (see README, "Inside S-mobiili").

The figures below were checked on 14 Nov on the real dataset as Veeti with no key (built-in rules). Steps 5 to 12 were also run live with Opus 5.5 the same day: the figures were the same, the wording was the model's, and a turn took 4 to 13 seconds (median 6.5 s). Under every answer a small label says where it came from: "On-device rules" or the model's name. If the model has not answered within 60 seconds, the built-in rules answer and say so. TODO(defects): re-check the steps after agent-s1's demo fixes.''')

rep('''3. **The front page.** At the top is his simulated S-Bank account: the current account balance (€2,227.52), savings and investments, and what is safe to spend until payday. Tap it for the latest transactions and "Move money". Say: "This is his account as the bank sees it; everything below works from these numbers." Below it: an "Ask Svinkki" box and six tiles under "I can help with" (afford, save, receipts, goal, payday, contract). "For you" holds the check-in and the weekly quiz as closed rows. "Your things" and "Conversations" appear once there is something in them. Say: "Nothing to learn. You ask, or you tap what you need."
4. **"Everything I can do"** Tap it and scroll once. Say: "Everything it can do is here. Tap one and it is asked for you."''',
'''3. **The front page.** At the top is his simulated S-Bank account: the current account balance (€2,227.52) and what is safe to spend until payday (€963); savings show only once there are some. Tap it for the latest transactions and "Move money". Say: "This is his account as the bank sees it; everything below works from these numbers." Below it: the question box with four example questions ("What can I spend this week?", "What kind of spender am I?", "Can I afford it?", "How can I save more?"), last month in the three baskets, and "For you" with the check-in, the weekly quiz and "Worth a look" as closed rows. "Your things" and "Conversations" appear once there is something in them. Say: "Nothing to learn. You ask, or you tap what you need."
4. **"Goals, receipts, contracts and more"** Tap the link under the question box: the sheet "Everything I can do" opens. Scroll once. Say: "Everything it can do is here. Tap one and it is asked for you." The phone's Back button closes the sheet.''')

rep('''5. **Ask: "How much did I spend on taxis last month?"** The answer leads with €92.85 on taxis in August (2 payments), then says what that means for him.''',
'''5. **Ask: "How much did I spend on taxis last month?"** The answer leads with €92.85 on taxis in August (2 payments); the built-in rules add that he spent nothing on taxis in July, the model says what it means for him.''')

rep('''6. **Follow up: "and the month before?"** It says he spent nothing on taxis in July. Say: "It is a conversation, not a search box."''',
'''6. **Follow up: "and the month before?"** It says he spent nothing on taxis in July (the built-in rules add: €17 less than in June). Say: "It is a conversation, not a search box."''')

rep('''7. **Ask: "Can I afford a 300 euro jacket?"** Reply: yes, with about €16 a day left until payday on 31 October. (Veeti's salary day alternates between the 15th and month end, so Svinkki plans for the later one.)''',
'''7. **Ask: "Can I afford a 300 euro jacket?"** Reply: yes, with about €35 a day left until payday on 15 October.''')

rep('''8. **Receipts: "What do I buy most?"** It answers from the receipts of his grocery payments (meat and fish is the biggest group).''',
'''8. **Receipts: "What do I buy most?"** It answers from the receipts of his grocery payments: oat drink (Kaurajuoma 1 l), 5 times in 3 months; meat and fish is the biggest group (23%).''')

rep('''Reply: "Saved: Japan, €3,000 by June 2027. You'll find it under Your things." Tap the back arrow:''',
'''The built-in rules plan for June 2027 (about €334 a month for 9 months) and reply "Saved: Japan, €3,000 by June 2027. You'll find it under Your things." The model may offer a different month (live on 14 Nov it offered September 2027 at about €250 a month); the saved goal says which. Tap the back arrow:''')

rep('''12. **The coach knows him: "Where can I save?"** It names ideas from his own spending with a euro amount a month, not general advice.''',
'''12. **The coach knows him: "Where can I save?"** It names ideas from his own spending with a euro amount a month, not general advice (built-in rules: 5% less everyday spending, about €30 a month, and 15% less on hobbies, about €16; live Opus led with small purchases under €10, about €39 a month).''')

rep('''Say: "This is why it sounds like it knows me. And this is all it knows: totals, never my name, my account or a shop."''',
'''Say: "This is why it sounds like it knows me. And this is all it knows: totals, never my name, my account or a shop." (What the model receives, tool by tool, is in the README.)''')

rep('''Tap "Approve and move". Say: "It can move money, but only inside S-mobiili and only after I approve the exact move." The savings account now shows under "Your things". Or ask: "Invest 50 euros in the index fund"; the card adds a plain risk note.''',
'''Tap "Approve and move". Say: "It can move money, but only inside S-mobiili and only after I approve the exact move." The savings account now shows under "Your things". Or ask: "Invest 50 euros in the index fund"; the card adds a plain risk note ("Fund value goes up and down; you can get back less than you put in"). A payment out ("Pay my electricity bill of 80 euros") is refused: it can only move money to his own savings account or an S-Bank fund, after he approves.''')

rep('''- The app works without the AI key: the built-in rules answer the same questions, and the reply is labelled "On-device rules". If Claude is slow or fails, the app falls back to the rules by itself and says so.''',
'''- The app works without the AI key: the built-in rules answer the same questions, and the reply is labelled "On-device rules". If Claude fails or has not answered within 60 seconds, the app falls back to the rules by itself and says so.''')

rep('''- Rebuild the database (the folder must hold the dataset CSV files):

```bash
SVINKKI_DATA_DIR=/path/to/dataset-folder python -m app.ingest
```''',
'''- Rebuild the database (reads `dataset/` in the repository root, or the folder in `SVINKKI_DATA_DIR`):

```bash
python -m app.ingest
```''')
open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
