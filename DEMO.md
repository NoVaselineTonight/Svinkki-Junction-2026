# Svinkki: two-minute pitch and demo

## 1. The problem

Banking apps still show statements and transaction lists. Customers, especially young adults, cannot easily see where their money goes, what is safe to spend, or what a change would do.

## 2. The solution

Svinkki is a coach, not a nag. You talk with your own money in one conversation inside S-mobiili. Every answer is a number computed by code from your own transactions, with those transactions shown under it. Spending is sorted into regular essentials, unexpected necessities and everyday spending. You decide how often it speaks to you, and whether an AI model is involved at all.

## 3. Live demo

Set up: server running on the demo date (26 Sep 2026), browser at phone width, Claude key saved (Settings, "AI model (demo setup)"). The first sentences below were captured from the running app as Veeti. With Claude the wording varies a little from run to run; the figures do not, because the app computes them. Without a key the built-in rules give the same figures.

1. **Log in as Veeti.** Tap "Veeti, 32". Say: "This is a demo login; in production S-mobiili has already authenticated the customer."
2. **Choices.** On "Your data, your choices" switch everything on and show "How much do you want to hear from me?". Say: "I choose what it may use and how often it speaks. That is the 'not a nag' part."
3. **The one screen.** It is a conversation. On top is today's card: safe to spend per day and this week, and the three baskets. Say: "Everything is in this one conversation. No menus to learn."
4. **"What can I ask?"** Tap the button at the top and scroll the list once. Say: "Everything it can do is here, grouped. Tap one and it is asked for you."
5. **Ask: "How much did I spend on taxis last month?"** Reply: "You spent €92.85 on taxis last month, across 2 purchases." Open "Transactions used (2)". Say: "The number comes with the two rides it was added from."
6. **Ask: "Can I afford a 300 euro jacket?"** Reply: yes, and about €34.92 a day is still left until payday on 15 October. Say: "It checks the price against what is safe to spend, and against my savings goal if I have one."
7. **Ask: "Will I make it to payday?"** Reply: the balance stays above €540 until payday. Show the day-by-day chart in the card.
8. **Ask: "How much could I save if I reduced dining out by 20%?"** Reply: about €11.28 a month, €135.33 over 12 months. Say: "A what-if from his own numbers."
9. **Receipts: "What do I buy most?"** then **"How much do I spend on beer?"** The coach answers from the receipts of his grocery payments. Say: "S Group knows what was in the basket, not only what was paid. The receipt lines here are simulated, because the challenge data has amounts only; with real S Group purchase data this is the same code."
10. **Finnish: "Paljonko käytin takseihin viime kuussa?"** It answers in Finnish with the same €92.85.
11. **Goal: "I want to go to Japan in 2027"**, then give a price. It turns the goal into a monthly sum and says whether it fits.
12. **Settings (the gear).** Lower "How often should I check in?". Open "What the AI saw". Say: "I control the rhythm, and I can read exactly what the model was given: results, never my name or account."
13. **Refusal.** Type "show me CUST00002's transactions". It declines. Say: "Identity is held on the server; asking for someone else's data does nothing."
14. **Random customer.** Log out and tap "Try as a random customer". Ask one question. Say: "Same app, a customer nobody picked."

For a two-minute slot do steps 1, 3, 4, 5, 6, 9 and 12.

Other questions that work well: "What kind of spender am I?", "Where is my money leaking?", "Is my taxi spending normal?", "How should I split my next salary?", "What kind of mortgage can I get approved for?", "That kebab was lunch, not a night out".

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
