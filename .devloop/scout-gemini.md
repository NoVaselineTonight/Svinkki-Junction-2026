# Google Gemini API: scout result

## (a) Recommended low-cost general model
- Model: Gemini 3.5 Flash-Lite
- Model ID: `gemini-3.5-flash-lite` (Stable)
- Source: https://ai.google.dev/gemini-api/docs/models (redirects to https://aistudio.google.com/docs/models). The page describes it as "Our fastest, most cost-effective 3.5 model for high-throughput execution" and marks it recommended for new projects. The phrase "general use" is an inference.
- Other IDs: `gemini-3.1-flash-lite` (Stable, recommendation status unconfirmed), `gemini-2.5-flash-lite` (not deprecated, but the page points new projects to 3.5 Flash-Lite). `gemini-3.1-flash-lite-preview` is shut down.

## (b) REST function calling
Partly confirmed, with differences.
- Endpoint: `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` is confirmed by https://aistudio.google.com/api-reference/generate-content (path only; base URL not shown on the page).
- Auth header `x-goog-api-key`: NOT confirmed on the fetched pages. Unconfirmed.
- `tools` with `functionDeclarations`: confirmed (camelCase).
- `system_instruction`: NOT confirmed. The reference uses camelCase `systemInstruction`. The snake_case form appears nowhere on the page. Use `systemInstruction` in REST bodies.
- `functionCall` and `functionResponse` part names: confirmed (camelCase). `functionCall` has `name`, optional `id` and `args`. `functionResponse` has `name` and `response`, plus optional `id` and `parts`.
- Difference to note: the function-calling guide at https://aistudio.google.com/docs/function-calling documents a newer Interactions endpoint, `POST https://generativelanguage.googleapis.com/v1beta/interactions`, with the model in the body, a flat `tools` list (no `functionDeclarations` wrapper), and steps of type `function_call` / `function_result`. If the project uses `generateContent`, follow the generate-content reference, not that guide.

## (c) Price and data use
- Standard paid tier, USD per 1M tokens, from https://aistudio.google.com/docs/pricing (redirected from https://ai.google.dev/gemini-api/docs/pricing):
  - `gemini-3.5-flash-lite`: input $0.30 (text/image/video/audio), output $2.50 (incl. thinking)
  - `gemini-3.1-flash-lite`: input $0.25 (text/image/video), $0.50 (audio); output $1.50
  - `gemini-2.5-flash-lite`: input $0.10 (text/image/video), $0.30 (audio); output $0.40
- Batch and priority prices for 3.5 Flash-Lite were seen only in a search snippet (batch $0.15 / $1.25; priority $0.54 / $4.50). Unconfirmed on the primary page.
- Data use, same pricing page: Free tier "Content used to improve our products" = Yes for all three Flash-Lite models. Paid tier "Content not used to improve our products" = No.
- Note: the pricing page was read only up to character 100000 of 111617. Later content was not checked.

## (d) Vertex AI in europe-north1 (Finland)
Not confirmed. The Vertex AI locations page (https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/locations) lists "Finland (europe-north1)" and an "European Union multi-region (eu)" table. The Gemini Flash-Lite rows (2.5, 3.1, 3.5) show empty cells in both the Finland column and the EU column, so the page does not confirm availability there. Check the Vertex console or this page again before relying on it.

## Unconfirmed
- Auth header `x-goog-api-key` on generateContent.
- `system_instruction` naming (reference says `systemInstruction`).
- Vertex europe-north1 / eu availability for Flash-Lite models.
- Batch and priority prices.
- Recommendation status of `gemini-3.1-flash-lite`.
