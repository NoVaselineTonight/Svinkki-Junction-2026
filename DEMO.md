# Svinkki: two-minute pitch and demo

## 1. The problem

Banking apps still show statements and transaction lists. Customers, especially young adults, cannot easily see where their money goes, what is safe to spend, or what a change would do.

## 2. The solution

Svinkki is a coach who knows you, not a nag and not a generic chatbot. You talk with your own money in one conversation inside S-mobiili. Before every answer the coach is handed a short, checked picture of you (your month, your usual month, your habits, your receipts, your goal), so it answers you, not an average customer, and ends with one concrete next step when your data gives one. Every figure is computed by code from your own transactions, with those transactions shown under it. Spending is sorted into regular essentials, unexpected necessities and everyday spending. You decide how often it speaks to you, and whether an AI model is involved at all.

## 3. Live demo

Set up: server running on the demo date (26 Sep 2026), browser at phone width, Claude key saved (Settings, "AI model (demo setup)"). Press "Reset demo" in Settings before you start, so the front page is empty. The figures below were captured from the running app as Veeti on 14 Nov, before the coach was made personal. Since then (same day) the Claude answers are two to four sentences: the figure, what it means for him, one next step. That version has NOT been run with a live key yet, so read the answers once before presenting: ask steps 5, 7 and 8 and check they are personal, short and compare with nobody. The figures do not change, because the app computes them. Without a key the built-in rules give the same figures and add one sentence about his own previous month.

1. **Log in as Veeti.** Tap "Veeti, 32". Say: "This is a demo login; in production S-mobiili has already authenticated the customer."
2. **Welcome.** One screen, one button: "Start". Open "Your choices" for a second to show the switches and "how often I check in". Say: "I choose what it may use and how often it speaks. That is the 'not a nag' part."
3. **The front page.** At the top is his simulated S-Bank account: the current account balance (€2,227.52), savings and investments, and what is safe to spend until payday. Tap it for the latest transactions and "Move money". Say: "This is his account as the bank sees it; everything below works from these numbers." Below it: an "Ask Svinkki" box and six tiles under "I can help with" (afford, save, receipts, goal, payday, contract). "For you" holds the check-in and the weekly quiz as closed rows. "Your things" and "Conversations" appear once there is something in them. Say: "Nothing to learn. You ask, or you tap what you need."
4. **"Everything I can do"** Tap it and scroll once. Say: "Everything it can do is here. Tap one and it is asked for you."
5. **Ask: "How much did I spend on taxis last month?"** The answer leads with €92.85 on taxis in August (2 payments), then says what that means for him. Open "Transactions used (2)". Say: "The number comes with the two rides it was added from. It only compares me with other people when I ask: try 'How does that compare with people my age?'"
6. **Follow up: "and the month before?"** It says he spent nothing on taxis in July. Say: "It is a conversation, not a search box."
7. **Ask: "Can I afford a 300 euro jacket?"** Reply: yes, with about €16 a day left until payday on 31 October. (Veeti's salary day alternates between the 15th and month end, so Svinkki plans for the later one.)
8. **Receipts: "What do I buy most?"** It answers from the receipts of his grocery payments (meat and fish is the biggest group). Then "Show my last receipt": S-market, 19 September, €93.04, with the lines. Say: "S Group knows what was in the basket, not only what was paid. The receipt lines here are simulated, because the challenge data has amounts only; with real S Group purchase data this is the same code."
9. **Goal: "I want to go to Japan in 2027"**, then "3000 euros", then "ok set it". Reply: "Saved: Japan, €3,000 by June 2027. You'll find it under Your things." Tap the back arrow: "Japan" is now on the front page under "Your things", and the conversations are listed below it.
10. **Finnish: "Paljonko käytin takseihin viime kuussa?"** It answers in Finnish with the same 92,85 €.
11. **Settings (the gear).** Lower "How often I check in". Open "What the AI saw". Say: "I control the rhythm, and I can read exactly what the model was given: results, never my name or account."
12. **The coach knows him: "Where can I save?"** It names ideas from his own spending with a euro amount a month, not general advice. Then open Settings, "What the AI saw": the lines under `what_the_coach_knows` are the whole picture the model was given. Say: "This is why it sounds like it knows me. And this is all it knows: totals, never my name, my account or a shop."
12b. **Random customer.** Log out and tap "Try as a random customer". Ask one question. Say: "Same app, a customer nobody picked."

13. **Save it, with permission.** Back on the front page, open "Your check-in" under "For you": it says what was left over and offers "Move €307 to savings" (the amount never exceeds what is safe before payday). Tap it: an approval card shows €307, from the current account to the S-Bank savings account, and the balance after. Tap "Approve and move". Say: "It can move money, but only inside S-mobiili and only after I approve the exact move." The savings account now shows under "Your things". Or ask: "Invest 50 euros in the index fund"; the card adds a plain risk note.
14. **Think twice.** Ask "Can I afford a 300 euro payday loan?" Reply: it is borrowing, not a purchase, and Svinkki would not take it.

For a two-minute slot do steps 1, 3, 5, 8, 9, 12 and 13.

Other questions that work well: "Will I make it to payday?", "What if I stopped taking taxis?" (about €39 a month), "What kind of spender am I?", "Where is my money leaking?", "What kind of mortgage can I get approved for?", "what's my balance", "that kebab was lunch".

## 4. What is next

- Bank login through S-mobiili in place of the demo login.
- Real S Group purchase data, with consent, in place of the simulated receipt lines.
- An EU-hosted model under a data processing agreement, with no training on customer data.
- The multi-bank view under PSD2, so the coach sees the whole financial picture.

## If something goes wrong

- Restart the server:

```bash
python -m app.server
```

- Rebuild the database (the folder must hold the dataset CSV files):

```bash
SVINKKI_DATA_DIR=/path/to/dataset-folder python -m app.ingest
```

- The app works without the AI key: the built-in rules answer the same questions, and the reply is labelled "On-device rules". If Claude is slow or fails, the app falls back to the rules by itself and says so.
- If a reply looks wrong, ask the question a second way ("taxis last month") and move on.
- Server on another port: `python -m app.server --port 8010`.
