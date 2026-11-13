# Tests

Standard library only (`unittest`). No network, no real dataset: every test builds an invented population
(52 customers, 2024-10 to 2026-09, deterministic) in a temp folder, runs `app.ingest.build` on it and points
the app at it through `SVINKKI_DB`, `SVINKKI_STATE_DB`, `SVINKKI_TODAY` (2026-09-24, a Thursday),
`SVINKKI_DATA_DIR`, empty `GEMINI_API_KEY` and `ANTHROPIC_API_KEY`, and `SVINKKI_ENV_FILE` /
`SVINKKI_AI_KEY_FILE` pointing at files that do not exist, so no real key can reach a test (SR-31).

## Run

From the repository root (Git Bash, PowerShell, anything; use `python`, not `python3`):

```
python -m unittest discover -s tests -v          # everything (about 15 s)
python -m unittest discover -s tests -p "test_insights.py" -v
python -m unittest discover -s tests -k V13 -v   # one plan item, by name
```

Each test module imports `app.*` inside `setUpClass` or the test method, so a missing or broken module fails
only its own test classes, not collection of the others.

## Files

| File | What it holds |
|---|---|
| `fixture.py` | The invented dataset and its **oracle** (expected labels, baskets, contexts and sums computed from the generator, never from the code under test), CSV writer, env setup, `Server`, cookie client, `login`, `consent_all`, `session`, `FakeGemini`. |
| `test_data.py` | Ingest, classification, sandbox, `safe_select`, `bench`, repository hygiene. |
| `test_insights.py` | Every calculation in `app/insights.py` against hand-checkable numbers. |
| `test_coach.py` | Tool registry, offline coach, refusals, Gemini mode through a fake HTTP layer. |
| `fixture_claude.py` | `FakeClaude` (Messages API replies, with thinking blocks), `patched_claude`, a fake key. |
| `test_claude.py` | Claude: the client's request and error handling, the coach's tool loop, the explainer, the demo setup endpoints (local only, key never returned or logged), and that the suite cannot see a real key. |
| `test_http.py` | Sessions, consent, settings, isolation, chat flow, validation, errors, logs, rate limit, headers, static files. |

### Customer A (CUST00001) is known to the cent

Salary 3,000 on the 15th; rent 900 on the 2nd; utilities 40 + 55.50 + 30; four grocery shops (62.40 + 1.10
cycling by month, 48.10, 75.25, 54.30) plus a 10 EUR one without merchant or MCC; restaurant lunch 16 on a
Wednesday and dinner 32 on the 10th (48.00 a month); a Friday night out (bar 24 at 21:30, kebab 11.50 at 01:10,
taxi 28 at 01:40 the next morning = 63.50 a month); a daytime taxi 14.20 and an evening taxi 19.90 on the 24th
(62.10 of taxis a month, constant); fast food 9.90; pharmacy 18.40 + 22.60; fuel 45; bus 3.10; clothing 49.90;
invest deposit 200 on the 16th; one 600 EUR appliance on 2026-06-20; rows dated after "today" (25-30 Sep),
including a 77.77 taxi on the 30th that must stay invisible. B (CUST00002, salary 2,600, 27.00 of taxis a month,
a 01:10 kebab and 01:40 taxi with no bar anywhere) is the "other customer"; D (CUST00003) is permanently below zero.
The picker is given these three by the fixture (it inserts them into `personas` after ingest), because ingest
chooses its own six.

Population shape: 22 customers aged 25-34 (4 in area 00, 18 in area 20), exactly 20 aged 35-44 (all area 33),
and small groups elsewhere, so benchmarks must widen for A and a group of exactly 20 must be allowed.

## Mapping to acceptance criteria and the security plan

| Test class (file) | Acceptance | Plan items |
|---|---|---|
| `IngestTests` (data) | M1, M7 (timestamps), S1 (bands) | SR-26, SR-31 |
| `IngestRowOrderTests` (data) | M1 (robustness) | |
| `ClassifyTests` (data) | M6, M7 | |
| `SandboxTests` (data) | M2 | SR-2, SR-23 (no exact age or postal in `profile`) |
| `SafeSelectTests` (data) | S2 | SR-6, SR-8, V3, V4 |
| `BenchTests` (data) | S1 | SR-13, SR-14, SR-15, V9 |
| `RepositoryHygieneTests` (data) | | SR-25, SR-26, SR-31, V16 (lite) |
| `PeriodTests`, `TransactionsTests` (insights) | M4 | SR-9, SR-11 |
| `SpendTests` (insights) | M4, M7 | SR-10, SR-11, V7 |
| `OverviewTests`, `BasketsTests` (insights) | M4, M6 | SR-11, V7 |
| `SafeToSpendTests` (insights) | M8 | SR-10 |
| `WhatIfTests` (insights) | M4 | SR-10, V7 |
| `SpenderTypeAndSaveMoreTests` (insights) | M4 | |
| `MortgageTests` (insights) | M4 | 5.2, V10 |
| `QuizTests` (insights) | M9 | |
| `CheckinTests` (insights) | M11 | |
| `BenchmarkInsightTests` (insights) | S1 | SR-13..SR-15, V9 |
| `InvestAndGoalTests` (insights) | M4 (invest), S5 | 5.1, V11 |
| `EveryResultIsSerialisableAndExplained` (insights) | M4 | SR-11 |
| `ToolLayerTests` (coach) | M5, S2 | SR-5, SR-6, SR-8, SR-9, V3, V4 |
| `OfflineCoachM4Tests` (coach) | M4, M5, M7 | SR-10, SR-11, V10, V11 |
| `OfflineRefusalTests` (coach) | M4 | SR-12, T1, T2, V1, V5, V8, V12 |
| `GeminiCoachTests` (coach) | M3, M5 | SR-10, SR-12, SR-22, SR-23, V3, V4 |
| `LoginAndSessionTests` (http) | M2 | SR-1, SR-3, SR-4, V1 |
| `ConsentAndSettingsTests` (http) | M3, M10, X3 | SR-6 |
| `DataEndpointTests` (http) | M4, M9 | SR-16, SR-18 |
| `IsolationTests` (http) | M2, M12 | SR-1, SR-2, V1, V2 |
| `ChatTests` (http) | M4, M12 | SR-16, SR-19, V5, V7, V10, V11, V12, V14 |
| `CheckinAndSuggestionTests` (http) | M10, M11 | SR-6 |
| `GeminiOverHttpTests` (http) | M3, M5, S3 | SR-10, SR-22 |
| `ErrorHandlingAndLoggingTests` (http) | M12 | SR-18, V13, V17, section 8 |
| `RateLimitTests` (http) | | SR-17, V15 |
| `StaticFileAndHeaderTests` (http) | M1 | SR-3, SR-19, SR-21, V14 (static check is a heuristic) |

M12 asks for V1-V4, V7-V9 and V12-V14 as automated tests: V1/V2 are in `IsolationTests`, V3/V4 in
`SafeSelectTests`, `ToolLayerTests` and `GeminiCoachTests`, V7 in `ChatTests` (15 questions) and
`SpendTests`, V8 in `OfflineRefusalTests`, V9 in `BenchTests` and `BenchmarkInsightTests` and the HTTP benchmark
test, V12 in `OfflineRefusalTests` and `ChatTests`, V13 in `ErrorHandlingAndLoggingTests`, V14 in
`ChatTests` and `StaticFileAndHeaderTests`. V6 (injection through data) has no test: the data has no free-text
fields. V16 is only the hygiene miniature; run a real secret scan before the demo.

## Known limits of the tests

* The Claude path is exercised through a fake `urllib.request.urlopen` returning Messages-API-shaped JSON.
  The fake accepts any request, so a field the real service would reject is only caught by a live call.
* The Gemini path is exercised through a fake `urllib.request.urlopen` returning `generateContent`-shaped
  JSON; it is not verified live. An implementation that bypasses `urllib.request.urlopen` would not be
  intercepted and those tests would fail.
* V13 injects a crash by patching `insights.overview`, `db.sandbox` and `state.get_consent`; if the server
  binds those names at import time the test skips instead of passing.
* V17 captures stdout, stderr and the `logging` module; a server that logs to its own file is not seen.
* The V14 static check is a heuristic (regex over `web/*.js` and `web/*.html`).
* Rate-limit tests send 100 chat and 330 data requests, so they take a few seconds.

## Changes

* `test_http.py`: expected settings defaults gained `"challenges": "off"`, and `challenges` validation (on/off only) was added, because `.devloop/WAVE2.md` section 2 added that setting after the tests were written (contract change, not a code defect).
