# Svinkki: two-minute pitch and demo

## 1. The problem

Banking apps still show statements and transaction lists. Customers, especially young adults, cannot easily see where their money goes, what is safe to spend, or what a change would do.

## 2. The solution

Svinkki is a coach who knows you, not a nag and not a generic chatbot. You talk with your own money in one conversation inside S-mobiili. Before every answer the coach is handed a short, checked picture of you (your month, your usual month, your habits, your receipts, your goal), so it answers you, not an average customer, and ends with one concrete next step when your data gives one. Every figure is computed by code from your own transactions, with those transactions shown under it. Spending is sorted into regular essentials, unexpected necessities and everyday spending. You decide how often it speaks to you, and whether an AI model is involved at all.

## 3. Live demo

Where to run it:

- **Public copy: https://svinkki.onrender.com.** There is no "Reset demo" there. Every visitor gets a private copy of the persona, so nobody else's questions, goals or notes show up. Logging out and logging in again starts fresh. The free Render plan sleeps after 15 idle minutes and takes about a minute to wake: open the page a few minutes before you start.
- **Your own computer:** server running on the demo date (26 Sep 2026), browser at phone width, Claude key saved (Settings, "AI model (demo setup)"). Press "Reset demo" in Settings before you start, so the front page is empty.

The figures below were checked with the live model (Claude Opus 5.5) as Veeti on 14 Nov, demo date 26 Sep 2026. The figures are computed by the app and do not change. The wording is the model's and changes from one run to the next, so do not read it out as a quote. Claude answers run from one to three short paragraphs and take 3 to 15 seconds; fill the wait by saying what the coach is doing. Without a key the built-in rules give the same figures in shorter answers.

1. **Log in as Veeti.** Tap "Veeti, 32". Say: "This is a demo login; in production S-mobiili has already authenticated the customer."
2. **Welcome.** One screen, one button: "Start". Open "Your choices" for a second to show the switches and "how often I check in". Say: "I choose what it may use and how often it speaks. That is the 'not a nag' part."
3. **The front page is the centre.** In order: his simulated S-Bank account (balance €2,227.52 and what is safe to spend until payday), the question box, then his **widgets**: savings plans as cards with a progress ring and a projection chart, and anything he added from a chat answer ("Add to home page"). With no plan yet the page offers three ready starts (a buffer, a trip or purchase, something of his own). Under the widgets, **"Svinkki suggests"**: up to three proposals worked out from his own data, each with one button (start a buffer plan, move last month's leftover, a saving idea). Then the four example questions, "Where your money went in August" (the three baskets), and "For you" (check-in, Daily quiz). Say: "The home page is where everything lives. He does not need to know what to ask: the coach proposes, and one tap puts a plan here."
4. **"Goals, receipts, contracts and more".** Tap it and scroll once. The sheet is titled "Everything I can do". Say: "Everything it can do is here. Tap one and it is asked for you."
5. **Ask: "How much did I spend on taxis last month?"** The answer leads with €92.85 on taxis in August (2 payments), then says what that means for him. Open "From 2 transactions". Say: "The number comes with the two rides it was added from." If you want the comparison, ask it in full: "How does my taxi spending compare with people my age?" (the live coach answers about taxis; the built-in rules answer about income and essentials if you only say "that").
6. **Show where a figure comes from.** Tap the €92.85 in the answer. It should show what it is, that code added it up from 2 payments, and that the AI did not write it. Say: "The AI wrote the sentence; the app filled in the number. It never typed it." Invite the audience to try to make it invent one.
7. **Follow up: "and the month before?"** It says he spent nothing on taxis in July. Say: "It is a conversation, not a search box."
8. **Ask: "Can I afford a 300 euro jacket?"** Reply: yes, with about €35 a day left until payday on 15 October. It takes about 31% of the €963 that is safe to spend before then. (Veeti's pay has sometimes come at the end of the month instead, and the coach says so.) These figures hold only before the money moves in step 14: after the €307 move the safe amount is €656.
9. **Receipts: "What do I buy most?"** It answers from the receipts of his grocery payments (meat and fish is the biggest group, €151 or 23%). Then "Show my last receipt": S-market, 19 September, €93.04, with the lines. Say: "S Group knows what was in the basket, not only what was paid. The receipt lines here are simulated, because the challenge data has amounts only; with real S Group purchase data this is the same code."
10. **A savings plan, built in the chat: "I want to go to Japan, it costs about 3000".** The answer is a plan card first: name, target, one slider for the monthly amount (moving it changes the date and the chart at once) and a line that says whether it fits his month. Under it the coach says in two sentences what it would do. Tap **"Add to home page"**; the card answers "On your home page". Tap the back arrow: the plan is a widget on the home page with its chart, "Move €N now" and "Adjust". Typing "yes" instead of tapping gets "Tap 'Add to home page' on the plan above": the coach never claims to have saved anything itself. Money moved from the widget (approval card, as in step 14) counts toward the plan.
11. **Finnish: tap "FI" in the top bar.** The whole interface switches (it starts in Finnish in a Finnish browser): home page, widgets, suggestions, cards, charts and settings. Ask "Paljonko käytin takseihin viime kuussa?": the card shows six months of bars and "Takseihin meni elokuussa 92,85 €, 2 maksua.", and the coach answers in Finnish in one sentence. Spoken Finnish works too ("Mihin mun rahat menee?").
12. **The coach knows him: "Where can I save?"** It names ideas from his own spending with a euro amount a month, not general advice; the live run found that half of his everyday spending lands in the 8 days after pay arrives. Then open Settings, "What the AI saw": the lines under `what_the_coach_knows` are the whole picture the model was given. Say: "This is why it sounds like it knows me. And this is all it knows: totals, never my name, my account or a shop."
13. **It remembers what you tell it: "Remember that my rent goes up by 60 euros in January".** The note is saved and shows under "Your things", where you can open it and tap "Forget this". The reply says it will keep that in mind and adds what it means for him. Say: "A coach should know what is coming, not only what happened. I told it once; it knows from now on, and I can make it forget."
14. **Save it, with permission.** Back on the front page, open "Your check-in" under "For you": it says what was left over (€307) and offers "Move €307 to savings" (the amount never exceeds what is safe before payday). Tap it: an approval card shows €307, from the current account to the S-Bank savings account, and the balance after (€1,920.52). Tap "Approve and move". Say: "It can move money, but only inside S-mobiili and only after I approve the exact move." The savings account now shows under "Your things". Or ask "Invest 50 euros in the index fund"; the card adds a plain risk note and the balance after is €1,870.52.
15. **Think twice.** Ask "Can I afford a 300 euro payday loan?" Reply: it is borrowing, not a purchase, and Svinkki would not take it.
16. **Random customer.** Log out and tap "Try as a random customer". Ask one question. Say: "Same app, a customer nobody picked."

## After the judges' feedback (14 Nov): the two-minute path in Finnish

The judges asked for six things: Finnish, more steering towards saving, savings plans you can create and see, widgets that stay on a home page that is the centre, the picture before the words, and proposals for a customer who knows little about money. This path shows all six. Checked live as Joonas with the interface in Finnish.

1. Log in as Joonas with "FI" selected. The home page offers "Aloita säästösuunnitelma" with three ready starts and, under "Svinkki ehdottaa", a buffer of one month's spending (2 200 €, 80 € a month).
2. Tap "Aloita tämä suunnitelma". The plan "Puskuri" appears on the home page with its ring and chart. One tap, no typing.
3. Ask "Mihin mun rahat menee?". First the picture (August in the three baskets and what was left, 290 €), then two sentences that end with what the coach would do, pointing at his Puskuri plan.
4. Ask "Haluun säästää Japanin matkaan, se maksaa varmaan 3000". A plan card with a slider; move it and watch the date change; tap "Lisää etusivulle".
5. Back on the home page: two plans. Tap "Siirrä 80 € nyt" on Puskuri and approve: nothing moves without the approval card.
6. Ask "Mitä talvi yleensä maksaa mulle?": a bar chart of last winter's spending and income per month and one line of text, where there used to be three bullet sentences.

Answers on this path ran 13 to 38 words in the last live check. The figures are computed by the app; the wording is the model's and changes between runs.

## Two-minute path (Veeti, live model)

1. Log in; stay on the front page. "You kept €307 in August" and the three baskets: it is personal before any question.
2. "How much did I spend on taxis last month?" €92.85. Open "From 2 transactions". Tap the figure.
3. The feeling question: "Honestly I'm a bit stressed about money this month. Am I doing okay?" In the audit this was the warmest answer, and the coach apologises for the heavy month, then gives the facts. It was seen for Helmi only, so ask it for Veeti once beforehand.
4. "Where can I save?" The best insight in the audit: half of everyday spending falls in the 8 days after pay arrives, and no statement shows it.
5. Open "Your check-in" on the front page and tap "Move €307 to savings", then "Approve and move €307". It acts only with permission. (In chat, "Move 20 euros to my savings account" gives the same approval card.)
6. Open "What the AI saw": "This is all it knew: totals, no name, no shop."

Skip receipts and the three-turn goal in two minutes. In the audit "What kind of spender am I and what should I do about it?" also worked well: "stretched", 99% of income, then the €30 step.

Rehearse one thing: Veeti's picture says he was below zero on 80 days last year, while "Can I afford a 300 euro jacket?" says yes. Both are true; be ready to say why the jacket still fits (safe to spend until payday is €963).

Insight questions that worked in the audit (describe the reply, do not read it out): Joonas, "What's the one thing I should understand about my money?" (his money runs to zero every month, below zero on 135 days last year); Veeti, "How much did I spend on groceries last month?" then "Why is it that much?" (the gap comes from how often he shops, about 8 trips against 6.5, not what he buys each time).

Other questions that work well: "Will I make it to payday?", "What if I stopped taking taxis?" (about €39 a month), "What kind of spender am I?", "Where is my money leaking?", "What kind of mortgage can I get approved for?".

Do not demo: "What don't I know about my spending?", "Why does it matter when my payday is?", (the audit found wrong or inconsistent answers; the causes were fixed in the same run but these two were not asked again), "that kebab was lunch" (it asks which purchase, shows three transaction lists, and needs a second answer), and "what's my balance" (the sentence reads as a subtraction that does not add up).

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

- The app works without the AI key: the built-in rules answer the same questions, and the reply is labelled "On-device rules". If Claude is slow or fails, the app falls back to the rules by itself and says so. On the public copy the model also stops after a daily cap and the rules take over.
- If a reply looks wrong, ask the question a second way ("taxis last month") and move on.
- Server on another port: `python -m app.server --port 8010`.
