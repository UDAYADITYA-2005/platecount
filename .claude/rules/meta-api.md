---
paths:
  - "src/platecount/meta/**/*.py"
---

# Meta API client rules

- Every request goes through `meta/client.py`. No other module imports httpx.
- Cache key = sha256(model + prompt + image bytes + options). Cache lives in `.cache/meta/`.
- Record cost per call (SAM: $0.0025 per image; Spark: from returned token usage) into the run's cost counter.
- Parse responses with Pydantic models built from a real recorded response in `tests/fixtures/`,
  never from guesses. If a field is missing, raise a clear error that prints the raw response.
- Never log the API key or full request headers.
