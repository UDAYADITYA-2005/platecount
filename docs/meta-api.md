# Meta Model API notes

Tags: [verified] = read in Meta's docs; [unverified] = check before relying on it.
When anything here conflicts with the live docs, the live docs win: update this file.

## Access
- Key from https://dev.meta.ai, stored in `.env` as `MODEL_API_KEY`. [verified]
- A card must be on the account to use the $150 hackathon credit; set a spend limit on Billing. [verified]
- Use the standard tier. The cheaper "contributor" tier lets Meta train on inputs, and AGAR's
  CC BY-NC licence may not allow that. [verified tier exists; licence question is a judgement call]

## SAM 3.1 (segmentation)
- Endpoint: `POST https://api.meta.ai/v1/responses` with model `sam-3.1`. [verified Oct 23]
- Input: an image plus a text prompt, or box/point prompts. "bacterial colony" finds nothing: see
  the prompt results below. [verified 2026-11-01]
- Output: a stream (SSE) or JSON containing box tokens and mask payloads; a confidence
  option (`include_confidence`) adds per-instance scores. [verified Oct 23; exact field names unverified]
- Docs to read before writing the client:
  - https://dev.meta.ai/docs/sam/segmenting
  - https://dev.meta.ai/docs/sam/reading-segmentation
- Price: $2.50 per 1,000 images. [verified]
- Image size limit: not documented. Downscale to 2048 px longest side by default. [unverified]
- First task: save one real response (stream and JSON if both exist) to `tests/fixtures/` and
  write the parser against that file, not against these notes.

### Verified live, 25 calls on `data/test_plate.jpg` (fixtures in `tests/fixtures/`)
- No threshold, score cut-off, top-k or max-instances option exists. `include_confidence` only
  reports scores; it does not filter. Checked: SAM pages and the `CreateResponse` schema. [verified 2026-11-01]
- Text and box prompts can't be combined. Sending both returns 400:
  `invalid prompt: object prompts cannot be combined with a phrase`. [verified 2026-11-01]
- Box/point prompts segment only the prompted objects, not similar ones (not exemplars): 2 boxes
  returned 2 instances. Max 16 prompted objects per the docs; 17 was not sent. Text prompts have
  no stated cap: "speck" returned 56. [verified 2026-11-01]
- `store: false` is accepted and echoed back in the response. The SAM pages don't mention it and
  the default is `true`, so always send it. [verified 2026-11-01]
- Prompts: "colony", "bacterial colony", "bacterial colonies", "bacteria", "mold" and "circle"
  returned 0. "dot", "speck", "white dot" and "round spot" found colonies: 49-56 on the full image,
  31 on a dense crop; boxes checked by eye only. "blob" finds large colonies (14, full image only).
  One plate, no ground truth. "colony" was not sent on the dense crop. [verified 2026-11-01]
- Masks are box-sized: 370 of 371 had `H,W` equal to the box height and width. The exception was
  a 1546x1489 box with a 1024x986 mask, which suggests a 1024 px cap on the longer side (one case
  only). Scale each mask to its box; don't assume 1:1. [verified 2026-11-01]

## Muse Spark 1.3 (agent, visual audit, voice parsing)
- Price: $1.25 per million input tokens, $4.25 per million output tokens. [verified]

Tags in this section mean read in the docs on 2026-11-02, unless they say "live" (agent run on 16 dev plates, 63 calls).

- Model ID: `muse-spark-1.3`. Never use `muse-spark-1.3-contributor` (it allows training on inputs). [verified 2026-11-02]
- Endpoint: `POST https://api.meta.ai/v1/responses`, same as SAM. Chat Completions also exists; these notes
  cover Responses only. [verified 2026-11-02]
- Cached input: $0.15 per million. Limits: 3,000 requests and 4,000,000 tokens per minute. [verified 2026-11-02]
- Image: `{"type": "input_image", "image_url": "<https URL or data:image/jpeg;base64,...>"}` in the `content`
  of a `user` message. `image_url` is a plain string here (an object on Chat Completions). [verified 2026-11-02]
- Image limits: `user` messages only, 50 per request, 50 MB inline. JPEG, PNG, GIF, WebP, ICO. [verified 2026-11-02]
- Image tokens scale with resolution: about 1,300-1,500 for a ~1280 px image, so about $0.002 each at the
  input price. Exact count: `POST /v1/responses/input_tokens`. [verified 2026-11-02]
- Tool definition: flat, `{"type": "function", "name", "description", "parameters", "strict"}`, not nested under
  `function` (that is Chat Completions). `name` and `parameters` are required. [verified 2026-11-02]
- `strict` default conflicts: the tool-calling guide says false, the schema page says true. Always send it. With
  true, every object needs `additionalProperties: false` and all properties in `required`. [verified 2026-11-02]
- `tool_choice`: only `"auto"`. `"none"`, `"required"` and named tools return 400, so a tool can't be forced
  and the loop must handle a plain-text reply. [verified 2026-11-02]
- Tool call comes back as an `output` item: `{"type": "function_call", "call_id", "name", "arguments", "status"}`.
  `arguments` is a JSON string. Validate it in our code whatever `strict` says. [verified 2026-11-02]
- `parallel_tool_calls` defaults to true: several calls can arrive in one turn, each needing one result.
  Set false for one call per turn. [verified 2026-11-02]
- Tool result: `{"type": "function_call_output", "call_id", "output"}` in the next request's `input`. `call_id` is
  1-64 chars. [verified 2026-11-02]
- `store`: default true; `store: false` is documented and is the recommended stateless mode, which rules out
  `previous_response_id` for us. Accepted live for SAM and Spark. [verified live 2026-11-02]
- Stateless loop: send `store: false` with `include: ["reasoning.encrypted_content"]` and resend the conversation
  each turn. Reasoning items need `summary` (`[]` is fine) and `encrypted_content`. Every `function_call_output`
  needs its `function_call` in the same request, else 400. A reasoning item must be followed by an assistant
  message or `function_call` before any user message, else 400. `include` plus `previous_response_id` is 400.
  [verified 2026-11-02]
- Keep `phase: "commentary"` on assistant text that precedes a `function_call` when replaying it, else 400. [verified 2026-11-02]
- Replay on a tool turn: the `output` items from `response.completed`, unchanged and in order, then the
  `function_call_output`s, then any `user` message. Accepted on up to 6 turns per plate. [verified live 2026-11-02]
- Structured output: `text: {"format": {"type": "json_schema", "name", "schema", "strict"}}`, flat under `format`
  per the schema page. `response_format` is accepted here but does nothing. Works with tools and images. Schema limits:
  depth 10, no recursive `$ref`. [verified 2026-11-02]
- No Responses example of structured output exists in the docs, and the result shape is assumed to be the usual
  `message` item holding an `output_text` block. Record one before parsing it. [unverified]
- An overlay image in a `user` message right after a `function_call_output` is accepted. [verified live 2026-11-02]
  Sending it inside `function_call_output` conflicts with "images only in `user` messages"; not tried. [unverified]
- `max_output_tokens` counts reasoning tokens too; minimum 16. `reasoning.effort`: none, minimal, low, medium,
  high, xhigh, max. [verified 2026-11-02]
- Usage for cost: `usage.input_tokens`, `usage.output_tokens`, `usage.input_tokens_details.cached_tokens`,
  `usage.output_tokens_details.reasoning_tokens`. `reasoning_tokens` is part of `output_tokens`: input + output =
  total in the recorded responses. [verified 2026-11-02] Our counter charges them at the output rate; Meta doesn't
  state the billing rate. [unverified]
- Refusal handling: not documented. [unverified]

## Muse Voice Transcribe
- $3 per 1,000 minutes; 25 validated languages. [verified]
- Request format: [unverified] - read its docs page.

## Error handling
- 400/401/403/404: fail fast, print the response body.
- 429/5xx: retry with exponential backoff, max 4 tries.
