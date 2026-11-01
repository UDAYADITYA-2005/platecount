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
- Input: an image plus a text prompt such as "bacterial colony". [verified]
- Output: a stream (SSE) or JSON containing box tokens and mask payloads; a confidence
  option (`include_confidence`) adds per-instance scores. [verified Oct 23; exact field names unverified]
- Docs to read before writing the client:
  - https://dev.meta.ai/docs/sam/segmenting
  - https://dev.meta.ai/docs/sam/reading-segmentation
- Price: $2.50 per 1,000 images. [verified]
- Image size limit: not documented. Downscale to 2048 px longest side by default. [unverified]
- First task: save one real response (stream and JSON if both exist) to `tests/fixtures/` and
  write the parser against that file, not against these notes.

## Muse Spark 1.3 (agent, visual audit, voice parsing)
- Price: $1.25 per million input tokens, $4.25 per million output tokens. [verified]
- Exact model ID, image input format, tool-calling format and structured-output format:
  [unverified] - read the model list and API fundamentals pages on https://dev.meta.ai/docs first.
- Image token cost is not published. Track real token usage from responses.

## Muse Voice Transcribe
- $3 per 1,000 minutes; 25 validated languages. [verified]
- Request format: [unverified] - read its docs page.

## Error handling
- 400/401/403/404: fail fast, print the response body.
- 429/5xx: retry with exponential backoff, max 4 tries.
