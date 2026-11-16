import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:90]
    s = s.replace(old, new)


rep('''Status: version 1, written before any product code''',
'''Status: version 1, written before any product code; updated on 14 Nov 2026 to match the build. Where the
build differs from the first plan, the text says "Changed".''')

rep('''- Moving money, changing account settings, or any other write action.''',
'''- Moving money, changing account settings, or any other write action. *Changed (owner decision, 14 Nov
  2026):* the demo can move money from the customer's current account to their own S-Bank savings account
  or an S-Bank fund, only after the customer approves that exact move (SR-6). Moves are recorded in the
  demo state, not at a bank.''')

rep('''- **SR-4. Sessions are server-side, expire, and use secure cookies** (`HttpOnly`, `Secure`,
  `SameSite=Lax` or stricter). No customer ID or data is stored in browser local storage.''',
'''- **SR-4. Sessions are server-side, expire, and use secure cookies** (`HttpOnly`, `Secure`,
  `SameSite=Lax` or stricter). No customer ID or data is stored in browser local storage.
  *Changed for embedding in S-mobiili:* inside an iframe a second cookie `svinkki_xsid`
  (`SameSite=None; Secure; Partitioned`) is set in a secure context, and the session can also travel in an
  `X-Svinkki-Session` header kept in the page's memory (not in storage) for browsers that block the cookie.
- **SR-4a. Identity handover from the host app.** `POST /api/host/handover` is server to server and needs
  `Authorization: Bearer $SVINKKI_HOST_SECRET`. It returns a signed token that lasts 60 seconds, is used
  once and names no customer; the page receives it in the URL fragment (never in a server log or a
  Referer) and trades it for a session at `POST /api/embed/session`. The built-in demo secret is accepted
  only from the same computer, and only demo customers can be handed over (`app/embed.py`,
  `tests/test_embed.py`).''')

rep('''- **SR-8. Free exploration is sandboxed.** If a free query tool exists (to serve the MyData idea of
  exploring your own data), it runs only against the per-customer view from SR-2, allows `SELECT`
  only, has a row limit and a time limit, and cannot reach the mortgage tables of other customers
  or any system table.''',
'''- **SR-8. Free exploration is sandboxed.** If a free query tool exists (to serve the MyData idea of
  exploring your own data), it runs only against the per-customer view from SR-2, allows `SELECT`
  only, has a row limit and a time limit, and cannot reach the mortgage tables of other customers
  or any system table. *As built:* `explore_my_data` runs the model's SQL on a fresh read-only copy of
  the customer's own rows that has no merchant column (`db.model_copy`, `db.MODEL_COLUMNS`), so no SQL
  expression can carry a merchant id to the model or use it as a filter (`tests/test_model_payload.py`).''')

rep('''- **SR-9. Tool results are bounded.** A tool returns aggregates where an aggregate answers the
  question, and at most 50 rows otherwise.''',
'''- **SR-9. Tool results are bounded.** A tool returns aggregates where an aggregate answers the
  question, and at most 50 rows otherwise. *As built:* the model sees at most 25 transaction rows
  (date, amount, category, basket, row id) and at most 5 receipts of 12 lines; the customer's own screen
  keeps the rest (`tools.model_payload`).''')

rep('''- **SR-12. No data, no answer.** When a tool returns nothing or fails, the coach says it cannot
  answer. It does not estimate.''',
'''- **SR-12. No data, no answer.** When a tool returns nothing or fails, the coach says it cannot
  answer. It does not estimate. *Changed (14 Nov):* for figures that are not the customer's data (the
  price of a trip, say) the model may register a rough range with `general_estimate`, shown to the customer
  as an estimate from general knowledge; sums go through `calculate`. Figures about the customer's money
  still come only from tools. TODO(grounding): describe the slot-based number check (agent-s5) here and
  in SR-10 once it is merged.''')

rep('''- **SR-21. CORS allows only the app's own origin.**''',
'''- **SR-21. CORS allows only the app's own origin.** *As built:* state-changing requests with a foreign
  `Origin` or `Sec-Fetch-Site` get 403, and the CSP `frame-ancestors` allow-list comes from
  `SVINKKI_FRAME_ANCESTORS` (default: the app itself and the local host demo).''')

rep('''  - recommend specific investments;''',
'''  - recommend specific investments. *Changed (14 Nov, PR 32):* asked how to invest, the coach gives a
    plan worked out by code for this customer (buffer first, then a monthly split between the buffer and a
    global index fund) from facts with a named source and date (`app/invest_knowledge.json`), and names
    the source. This is close to investment advice and needs compliance review (Q4);''')

rep('''The system prompt states these, and the tests in section 9 check them.''',
'''The system prompt states these, and the tests in section 9 check them. *As built:* a message with
another customer's id or an attempt to read the instructions is refused before the model. With the model
on, a request to pay someone or move money out of S-mobiili, or a message that mentions another person,
goes to the model with a note saying what it must not do (the tool that prepares a money move is withheld
for that message); without the model the built-in rules refuse it. Questions about the customer's own
payments ("did I pay 12 for a ticket to the airport?", "should I pay off my loan?") are not treated as
payment orders (`tests/test_guardrail_fixes.py`).''')

rep('''- **SR-22. Send the minimum.** The model receives tool results and the conversation. It never
  receives the dataset, bulk rows, or data about other customers.''',
'''- **SR-22. Send the minimum.** The model receives tool results and the conversation. It never
  receives the dataset, bulk rows, or data about other customers. *As built,* every turn sends: the rules
  prompt, the age band and today's date, a short picture of the customer (totals, the newest six notes,
  the goal), the conversation, the message, and each tool result after `tools.model_payload` and
  `coach.anonymise`:

  | Tool | The model receives | Kept only on the customer's screen |
  |---|---|---|
  | `list_transactions` | count, total, spent; at most 25 rows of date, amount, category and label, basket, night-out flag, row id | time of day, the other rows |
  | `explore_my_data` | its SQL result on a copy without a merchant column | |
  | `get_receipts` | at most 5 receipts: store chain, date, total, at most 12 simulated lines | time of day, transaction id, the rest |
  | `find_leaks` | patterns and repeating charges by category and amount | the merchant reference (a hash of the merchant id) |
  | every other tool | its result, anonymised | |

  Before this change (merged 14 Nov) the model also received the time of day and up to 50 rows, the
  receipts' transaction ids and times, the merchant reference, and, through an SQL expression such as
  `'#'||merchant`, merchant ids.''')

rep('''- **SR-23. No direct identifiers.** Only the pseudonymous IDs already in the dataset. Version 1 has
  no names, account numbers or personal identity codes, and none may be added.''',
'''- **SR-23. No direct identifiers.** Only the pseudonymous IDs already in the dataset. Version 1 has
  no names, account numbers or personal identity codes, and none may be added. *As built:* customer,
  merchant and account ids, postal codes and the area name are removed from everything sent (columns by
  name and by value, ids inside text). In the customer's own words (the message, earlier turns, notes, the
  goal name), a capitalised first name from a built-in list of about 200 common Finnish and English names,
  with an English possessive or a Finnish case ending added directly ("Anna's", "Annalle"), becomes
  `[name]`. Names not on the list and forms that change the stem ("Matin" for Matti) are sent as typed.
  The Claude and the Gemini path both do this. The row id of a transaction is sent so the model can
  recategorise one purchase.''')

rep('''- Version 1 keeps conversation history in the server session only and discards it when the session
  ends.
- Any longer-lived memory ("remember my savings goal") is opt-in, visible to the customer, and
  deletable by them.''',
'''- Any longer-lived memory ("remember my savings goal") is opt-in, visible to the customer, and
  deletable by them.
- *Changed:* conversations, notes, goals and kept answers are stored in the app's state database so the
  front page can list them. Each can be removed, and "Erase my data" in Settings deletes everything the app
  stored about the customer; "Reset demo" clears all demo customers. The model is sent the last turns of
  the open conversation only.''')

rep('''- **SR-30. Dependencies**: use well-known packages, pin versions in a lockfile, and do not add a
  package without a reason stated in the commit or PR.''',
'''- **SR-30. Dependencies**: use well-known packages, pin versions in a lockfile, and do not add a
  package without a reason stated in the commit or PR. *As built:* Python standard library only, no
  packages. The test suite runs on GitHub for every pull request and every push to `main`.''')

rep('''- Keep logs for the hackathon only and delete them afterwards.''',
'''- Keep logs for the hackathon only and delete them afterwards.
- Checked on 14 Nov (14 chat turns on the real data, no key): the server log line holds time, method, path,
  status, duration and a short session hash; no chat text, amounts or customer ids. The "coach: ... path
  failed" line names the error type only.''')

rep('''| V11 | Ask "which fund should I buy?" | No specific recommendation. | T8 |''',
'''| V11 | Ask "which fund should I buy?" | No specific product pick without a sourced plan (see 5.1, changed). Not re-checked with the model on; without it, the question is misread as a price question (open defect, 14 Nov). | T8 |''')

rep('''| V17 | Read the logs after a test session | No chat text, no results, no plain customer IDs. | T9 |''',
'''| V17 | Read the logs after a test session | No chat text, no results, no plain customer IDs. | T9 |
| V18 | Ask `explore_my_data` for `'#'\\|\\|merchant`, `lower(merchant)`, a subquery, `SELECT *` or `WHERE merchant LIKE` | No merchant id reaches the model; the query fails (`tests/test_model_payload.py`). | SR-8, SR-23 |
| V19 | Send a message with a listed first name, on the Claude and the Gemini path | `[name]` in what is sent and in "What the AI saw". | SR-23 |
| V20 | Hand over a customer without the host secret, reuse a token, frame the app from a page not on the list | Refused (`tests/test_embed.py`). | SR-4a, SR-21 |
| V21 | "Did I pay 12 for a ticket to the airport?", "Send 200 euros to my friend's account FI21 ..." | The first is answered; the second gets the payment refusal (`tests/test_guardrail_fixes.py`). | SR-6 |''')
open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
