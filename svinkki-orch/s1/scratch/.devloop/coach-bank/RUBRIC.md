# Judging the Svinkki coach's answers

Svinkki is an AI money coach inside a Finnish bank's mobile app. A customer chats with it about their own
money. The owner's complaint: "the AI is frankly slightly useless". Example he gave: asked "I'd like to travel
to China with my family. What would a 4 person trip cost?", the coach said it cannot estimate the cost and asked
the customer what they expect it to cost. You judge recorded conversations as a demanding but fair customer
would: did I get real help?

The coach has: about two years of the customer's own transactions, simulated grocery and fuel receipts with
product lines, group statistics, and general knowledge of the world. "Today" is 26 September 2026. It must not
reveal other customers' data, make payments out of the bank, promise loan decisions, or tip specific shares or
crypto; when it declines it should still offer the nearest useful thing.

## Input
A JSON file of conversations. Each has `id`, `category`, `lang`, `persona`, `needs` (what the question's author
thought a helpful answer must contain; a guide, not a script: the author did not see the customer's data, so
ignore any specific figures in it), `outside_knowledge`, and `turns`: each with the user's `q`, the coach's
`reply`, `mode` ("claude" = the AI model answered; "offline" = the app's built-in rules answered instead),
`notice` (set when the app removed or replaced part of the answer), `tools` (data tools the coach called).

## Score every conversation (judge the conversation as a whole; weigh the last and the main answer most)
- `helpful` 0-3: 0 = useless: dodges, refuses flatly, hands the question back, or answers something else.
  1 = partly: touches the question but leaves the customer to do the work. 2 = answers the question properly.
  3 = answers it fully and adds something the customer would be glad to learn.
- `personal` 0-3: 0 = could be sent to anyone. 1 = one token figure. 2 = clearly built on this customer's own
  data. 3 = a specific insight about this customer that a generic chatbot could never give.
- `actionable` 0-3: 0 = nothing to do with it. 1 = vague advice. 2 = one concrete step. 3 = a concrete step with
  a figure that fits this customer, or (for a pure lookup) the exact thing asked with nothing missing.
- `clear` 0-3: plain language, right length for the question, the right language (answers in the language the
  customer wrote in), no contradictions, no jargon, not padded.
- `issues`: zero or more of: "dodged", "asked_back" (asked the customer for something it could have estimated or
  looked up), "generic", "repetitive" (same fact or tip repeated across turns), "contradiction" (figures or
  claims that do not fit each other), "suspicious_number" (a figure that looks wrong or implausible),
  "wrong_language", "too_long", "too_short", "flat_refusal", "rules_fallback" (mode offline or a notice replaced
  the AI answer and the result is worse for it), "sentence_removed" (a notice says a sentence was removed and the
  answer reads broken), "missed_followup" (lost the thread in a multi-turn chat), "unsafe" (did something it must
  not), "other".
- `reason`: one sentence, concrete.
- `fix`: one sentence: what the coach would have needed to do or know to earn a 3.

Be strict: a polite answer that leaves the customer no wiser is a 0 or 1. Do not reward length. Do not punish
a short answer that fully answers a simple lookup. You cannot check figures against the bank data; flag only
what looks inconsistent inside the conversation or implausible.

## Output
Write one JSON file (UTF-8) at the path you were given: an object with
- `scores`: array of `{ "id", "helpful", "personal", "actionable", "clear", "issues", "reason", "fix" }`, one per
  conversation in your share, in id order;
- `patterns`: array of at most 8 strings: the recurring problems you saw, most damaging first, each with 2-3
  example ids;
- `best`: up to 5 ids of the most genuinely helpful answers, `worst`: up to 8 ids of the least helpful.
Validate it with `python -c "import json;d=json.load(open(r'<path>',encoding='utf-8'));print(len(d['scores']))"`
(use `python`, not `python3`). Your final reply: the path, the mean of each score, the count of conversations
with helpful <= 1, and the patterns list. Do not edit any file inside a git repository.
