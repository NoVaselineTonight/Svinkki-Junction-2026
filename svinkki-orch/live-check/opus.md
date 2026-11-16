| # | model | question | latency s | req | per-request s | in / out / cache r / cache w | cost $ | mode | number check | reply |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | opus-5-5 | How much did I spend on taxis last month? | 4.6 | 2 | 2.4 2.0 | 2315 / 176 / 33792 / 0 | 0.0195 | claude | ok | You spent €92.85 on taxis in August (2 rides), and none of it was part of a night out. That put taxis fourth among your biggest categories last month, after ho... |
| 2 | opus-5-5 | and the month before? | 4.1 | 2 | 2.1 1.9 | 2422 / 138 / 33792 / 0 | 0.0192 | claude | ok | In July you spent nothing on taxis: no rides at all. So the €92.85 in August was a jump from zero, not part of a steady habit. |
| 3 | opus-5-5 | Can I afford a 300 euro jacket? | 5.2 | 2 | 2.0 3.1 | 2678 / 268 / 33792 / 0 | 0.0228 | claude | ok | Yes, the €300 jacket fits: you'd still have about €35 a day until payday on 15 October. That's after your €1,177 of bills due before then. It would use about a... |
| 4 | opus-5-5 | What do I buy most? | 6.3 | 2 | 2.2 4.1 | 4534 / 423 / 33792 / 0 | 0.0333 | claude | ok | Your most frequent buy is oat drink (Kaurajuoma 1 l): 5 times over the last 3 months, €11.38 in total. The receipt lines are simulated for this demo. Measured ... |
| 5 | opus-5-5 | Show my last receipt | 10.3 | 4 | 1.9 3.9 2.0 2.4 | 10747 / 523 / 67584 / 0 | 0.0670 | claude | repaired: €9.89 | Your last receipt is from S-market last Saturday evening and came to €93.04. The biggest item was two packs of chicken breast at €16.98, which matches the chic... |
| 6 | opus-5-5 | I want to go to Japan in 2027 | 13.0 | 4 | 4.8 1.6 3.0 3.6 | 10128 / 1037 / 67584 / 0 | 0.0748 | claude | ok | Japan is doable, but going in spring 2027 would mean putting aside about €515 a month for 7 months. That's a rough estimate of €3,600 for two weeks for one per... |
| 7 | opus-5-5 | 3000 euros | 9.1 | 2 | 3.4 5.7 | 4833 / 799 / 33792 / 0 | 0.0421 | claude | ok | With a €3,000 budget, you'd need to put aside about €250 a month to go in September 2027, or about €429 a month to go in April 2027. Even €250 a month is a lot... |
| 8 | opus-5-5 | ok set it | 0.0 | 0 |  | 0 / 0 / 0 / 0 | 0.0000 | offline | ok | Saved: Japan, €3,000 by September 2027. You'll find it under Your things. |
| 9 | opus-5-5 | Paljonko käytin takseihin viime kuussa? | 3.7 | 2 | 1.4 2.3 | 2407 / 199 / 33792 / 0 | 0.0204 | claude | ok (tidied) | Käytit elokuussa takseihin 92,85 € (2 maksua). Taksit olivat elokuun neljänneksi suurin menoeräsi asumisen, polttoaineen ja ruokaostosten jälkeen. |
| 10 | opus-5-5 | Where can I save? | 6.8 | 2 | 1.9 4.7 | 4102 / 448 / 33792 / 0 | 0.0321 | claude | ok | Your clearest leak is small stuff: purchases under €10 add up to about €39 a month (22 of them over the last 4 months), and most of them are quick restaurant a... |
| 11 | opus-5-5 | Remember that my rent goes up to 950 in January | 11.9 | 3 | 2.9 5.8 3.0 | 5247 / 756 / 50688 / 0 | 0.0462 | claude | ok | Got it, I'll remember that your rent goes up to €950 in January. One thing doesn't add up yet: your housing payment has averaged about €1,128 a month over the ... |
| 12 | opus-5-5 | Can I afford a 300 euro payday loan? | 6.6 | 2 | 2.8 3.8 | 3585 / 475 / 33792 / 0 | 0.0306 | claude | ok | A payday loan is borrowing, not a purchase: you pay it back with interest and fees, often much more than you borrowed. I would not take it. The good news is yo... |

| model | turns | median s | max s | mean cost $ | total $ |
|---|---|---|---|---|---|
| claude-opus-5-5 | 12 | 6.5 | 13.0 | 0.0340 | 0.4081 |
