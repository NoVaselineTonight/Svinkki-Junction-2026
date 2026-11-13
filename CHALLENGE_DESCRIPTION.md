# Challenge: Personal Economic Trainer (S-Pankki, Junction 2026)

Source: the challenge page on the Junction Platform and the S-Pankki brief PDF. Reproduced here so
every agent works from the same text.

## The challenge

Explore how AI can turn personal banking data into a trusted financial coach for everyday life.

S-Bank is Finland's fourth-largest bank, with 3.5 million customers, and its S-mobiili app is used
weekly by one in three Finnish adults. We want to reimagine personal finance by letting people talk
with their own financial data through AI. Banking today often stops at statements and transaction
lists. We want to make it conversational, insightful, and personalised.

Using a large synthetic transaction dataset modelled on real S-Bank data, build an AI experience
that lets people chat with their own money, from simple questions like "How much did I spend on
taxis last month?" to deeper ones like "What kind of spender am I?", "What is safe for me to spend
this week?" or "How much could I save if I reduced dining out by 20%?".

We value a pedagogical angle: everyone's spending falls into three baskets:

1. mandatory and regular (e.g. rent)
2. mandatory and irregular (e.g. a broken washing machine)
3. everyday spending that slips through your fingers (e.g. coffees)

Solutions that help people understand where their money really goes will go far with us.

Think in the spirit of MyData: let users explore their own data freely rather than showing fixed
charts the bank has picked for them. You can enhance these insights with open data sources (e.g.
Statistics Finland) to offer meaningful benchmarks.

Recommended output: a mobile app, or a web app that can be embedded in a mobile app. Our customers
are on mobile.

## Extra details

To our knowledge, no Finnish bank yet lets customers chat with their own financial data. The
challenge ties directly to S-Bank's strategy of serving customers increasingly digitally and to our
vision for S-mobiili. Money matters touch everyone, and we believe AI can play a key role in
improving financial literacy, especially among young adults.

We are especially interested in conversational AI that explains financial concepts in plain
language, simulates "what if" scenarios, and guides users toward healthier money habits, for
example through safe-to-spend and safe-to-save guidance. Benchmarking personal data against open
population data is encouraged but not mandatory.

Optional bonus angle (not required): multi-bank view. Under PSD2, customers can let their bank
fetch account data from other banks. How could an AI coach use the customer's full financial
picture?

## From the brief PDF

Ask your money:

- Where did my money go?
- What kind of spender am I?
- What can I safely spend this week?
- How could I save more?

Make spending easy to understand: regular essentials, unexpected necessities, everyday spending.

## Data

Synthetic dataset: https://github.com/hackjunction/Junction-2026-S-pankki (not stored in this
repository, see `docs/SECURITY_PLAN.md` SR-26).

| File | Fields |
|---|---|
| `tx_junction_transactions.csv` | `customer_id`, `bank_account_id`, `tx_date`, `tx_timestamp`, `category`, `tx_amount_eur` (negative for outflows), `balance_after_eur`, `transaction_type`, `merchant_id`, `mcc_code` |
| `tx_customers_junction.csv` | `customer_id`, `customer_postal_code` (text, leading zeros matter), `customer_age` |
| `mtg_negotiation_history.csv` | mortgage application events: `mortgage_customer_id`, `timestamp`, `event_type`, property, loan, equity, collateral, `decision`, `rejection_reason`, expenses, `note` |
| `mtg_tx_customer_link_and_final_mtg_infio.csv` | links `mortgage_customer_id` to `customer_id`, with the final decision |

The team works on a filtered copy that removes customers who move their salary out right after
payday and customers with little activity (286 of 5,100).

## Team requirements on top of the brief

- Web-based and mobile-first, easy to embed in S-mobiili.
- The demo may use a Google AI Studio key; the pitch needs a concrete, cost-effective and secure
  production setup.
- The AI model only receives anonymous data.
- The customer gives consent before any data is shared.
- Weekly quiz: "Guess how much you spent on X this week" then the real figure and a tip.
- Smarter classification: a kebab bought during a night out counts as night out, not food.
- Questions such as "What kind of mortgage can I get approved for?", "How can I save more?" and
  "What should I invest in?".
- Opt-in suggestions with the monthly check-in ("You had a 120 EUR surplus. Should we invest it?").
- The customer chooses how often check-ins and suggestions arrive.
