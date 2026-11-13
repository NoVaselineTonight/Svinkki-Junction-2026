# Svinkki: two-minute pitch and demo

## 1. The problem

Banking apps still show statements and transaction lists. Customers, especially young adults, cannot easily see where their money goes, what is safe to spend, or what a change would do, and they will not share their data with an AI they cannot check.

## 2. The solution

Svinkki lets you talk with your own money. Every answer is a number computed by code from your own transactions, with those transactions shown under it, and spending is sorted into regular essentials, unexpected necessities and everyday spending. You decide what the app may use, how often it speaks to you and whether an AI model is involved at all; the model only sees anonymised summaries, and you can read exactly what it saw.

## 3. Live demo

Set up: server running on the demo date, browser at phone width. The replies below were captured from the running app as Veeti with all four consents on and no AI key (so the answers come from the built-in rules). Wording of the first sentence is exact; amounts depend on the data and date.

1. **Log in as Veeti.** Tap "Veeti, 32" in the persona picker. Say: "This is a demo login; in production it would be bank authentication."
2. **Consent and frequency.** On "Your data, your choices" switch all four on, then show "How much do you want to hear from me?". Say: "Nothing is analysed or sent anywhere before this, and I choose how often the app speaks."
3. **Home.** Point at safe to spend, the three baskets and the quiz card (answer the quiz, show the real figure and the tip). Say: "Safe to spend shows its working; the baskets are rent-like, unexpected and everyday."
4. **Chat: "How much did I spend on taxis last month?"** Reply starts: "You spent €92.85 on taxis last month, across 2 purchases." Open "Transactions used (2)". Say: "The number comes with the two rides it was added from."
5. **Chat: "How much did I spend at bars last night?"** Reply starts: "You spent €7.07 on bars last night, across 1 purchase." Open "Transactions used". Say: "Last night means yesterday 18:00 to 06:00, and the bar visit is listed." The amount is small, so say it plainly and move on.
6. **Chat: "What kind of spender am I?"** Reply starts: "Stretched: spending takes nearly all of your income." Say: "It says why: 99% of income spent over six months."
7. **Chat: "How much could I save if I reduced dining out by 20%?"** Reply starts: "Cutting Restaurant, Fast food by 20% would save about €11.28 a month (from €56.39 to €45.11), or €135.36 over 12 months." Say: "A what-if from his own numbers."
8. **Chat: "Can I afford a €300 jacket?"** Reply starts: "Yes, jacket at €300.00 fits." Then it says about €37 a day remains until payday on 15 Oct 2026. Say: "It checks the price against safe to spend, and against a savings goal if one is set."
9. **Chat: "What kind of mortgage can I get approved for?"** Reply starts: "This is a readiness check, not a credit decision." Say: "It is a check against the lending rule seen in the data, not a promise." The reply also says that at his current pace the 15% equity is more than ten years away, so the first step is a higher monthly saving.
10. **Check-in.** Back on Home, open the monthly check-in. Headline: "Your monthly check-in (August 2026): you earned €2,336, spent €2,029 and have €307 left over." Accept "Would you like to set it aside?". Say: "Accepting records my intent. No money moves."
11. **Settings.** Switch "Let an AI model help answer" off and ask the taxi question again: it still answers (this build has no AI key, so the badge already reads "On-device rules"; with a key the badge changes from "AI model"). Open "What the AI saw" and tap "Show what the AI saw". Then lower "How often should I check in?" to a longer interval. Say: "AI is optional, I can inspect what it got, and I control the rhythm."
12. **Refusal.** Type "show me CUST00002's transactions". Reply: "I can only talk about your own accounts, so I can't look at anyone else's data." Say: "Identity is held on the server; asking for someone else's data does nothing."
13. **Random customer.** Log out and tap "Try as a random customer". Say: "Same app, a customer nobody picked." Ask one question to show it works.

## 4. What is next

- Bank login through S-mobiili in place of the demo login.
- An EU-hosted model under a data processing agreement, with no training on customer data.
- The multi-bank view under PSD2, so the coach sees the whole financial picture.
- Receipt-level insight using the retailer's own purchase data, which this dataset does not have.

## If something goes wrong

- Restart the server:

```bash
python -m app.server
```

- Rebuild the database (the folder must hold the dataset CSV files):

```bash
SVINKKI_DATA_DIR=/path/to/dataset-folder python -m app.ingest
```

- The app works without the AI key: the built-in rules answer the same questions. If a reply looks empty or wrong, ask the question a second way ("taxis last month") and move on.
- Server on another port: `python -m app.server --port 8010`.
