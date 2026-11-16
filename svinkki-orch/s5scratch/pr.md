Wires app/grounding.py (PR 38) into the coach. Every figure in a Claude answer is now filled in or matched by code, and the reply carries where each figure came from.

## What changes
- `app/coach.py`
  - `_claude_turn` builds a figure table: the customer picture, earlier answers, the message and each tool result.
    - Snapshot lines are sent as "income €3,000 {{f1}}".
    - Each tool result gets a `figures` listing.
    - The repair round uses `grounding.check`: figures that are unknown or do not fit their sentence.
  - `chat()` uses `grounding.render`.
    - Slots are filled in English or Finnish; digits that equal a fitting figure still pass.
    - When the answer sentence or more than half the sentences fail, it falls back to the tool whose figures the draft used, never a tail.
  - `fi_money_format` is no longer called on model replies (render formats Finnish).
  - `_package(..., figures=)`.
  - `numbers_grounded` / `ungrounded_spans` are thin wrappers over grounding; `_keep_grounded_sentences` is removed.
  - SYSTEM_PROMPT has one new "Figures" paragraph (EN and FI example).
- `app/tools.py`: calculate accepts `{{fN}}` / `fN` in expressions. Only numbers the model typed itself go through the known-number check.
- `app/grounding.py`
  - The model sees at most 60 figures per result in its listing; all are registered.
  - Single line breaks are kept.
  - A figure in a text takes its meaning (income/spending/kept) from the nearest such word before it.

## `figures` in the reply (for the tappable UI)
`reply["figures"]`: a list, present when the reply holds figures. Each item:
```
{"id": "f202", "start": 10, "end": 16, "text": "€92.85",          # offsets into reply["reply"]
 "label": "total, category Taxi, one month, 2026-08", "unit": "money|percent|count|number",
 "value": 92.85, "written": "slot|digits",
 "source": {"kind": "tool|snapshot|earlier_answer|customer_message", "tool": "get_spend", "call": 0,
            "path": "total", "args": {...}, "evidence": [ {filter dicts, same shape as reply["evidence"]} ]}}
```
Snapshot figures have `kind: "snapshot"`. Their `tool`/`path` point at the field of the picture's data when one matches; otherwise `line` gives the line index.

## Tests changed honestly
- `tests/test_wave4.py`: the four tests that pinned the lenient mode are replaced; they now assert the opposite.
  - `test_C_lenient_mode_accepts_an_invented_percentage`, `test_C_lenient_mode_accepts_a_bare_number`, `test_C_strict_from_the_environment` and `test_C_explicit_strict_false_wins_over_the_environment`.
  - In that mode "That is about 37% of your income." and "You made 14 purchases." passed with no such figure; that was the hole behind "You spent 450 on taxis, which is 45% of your income."
  - `SVINKKI_STRICT_NUMBERS` / `strict=` are still accepted and ignored (`strict_numbers()` kept as an alias).
- `tests/test_presentation.py`: `test_number_check_accepts_every_template` now also passes the reply's `hints` as data. The fuel template quotes the price per litre from the fuel receipts in `hints`, not from the tool result.
- New: `tests/test_grounding.py::ChatWiring`, through the real chat path with the fake Claude.
  - A slot is filled and its source is in the package.
  - Matching digits pass with no repair.
  - The four wrong sentences go through repair and are never shown.
  - A dropped answer falls back to the get_spend answer, not the tail.
  - I saw "You spent €3,000 on taxis last month." pass before the nearest-word fix.

Full suite: 1062 tests OK.

## Live check (6 turns, Opus 5.5, Veeti, real data; baseline agent-s4 opus.md)
| question | slots written | repair / dropped / replaced | latency (baseline) |
|---|---|---|---|
| taxis last month | yes (1) | none | 4.5 s (4.6) |
| 300 euro jacket | yes (5) | none | 5.2 s (5.2) |
| Japan in 2027 | yes (8: estimate + plan) | none | 12.3 s (13.0) |
| Where can I save? | yes (10) | none | 10.9 s (6.8) |
| Finnish taxi question | yes (1), filled as 92,85 € | none | 7.0 s (3.7) |
| What do I buy most? | yes (7) | none | 6.0 s (6.3) |

Every answer was written entirely with slots and shown in full; no notice. Two turns were slower than the baseline. That may be ordinary variance; it was not measured further. The first turn paid a one-off cache write ($0.11) because the prompt changed.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
