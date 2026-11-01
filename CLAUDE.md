# PlateCount

A phone-first tool that counts bacterial colonies on agar plate photos and reports CFU/mL.
An agent (Muse Spark 1.3) plans the checks, SAM 3.1 does all segmentation, plain Python does
all arithmetic, and a verifier rejects any reported number that no tool produced.
Built solo for the Meta Global AI Developer Hackathon (Indie track). Deadline: Wed Nov 4, 11 PM IST.
Time is short: prefer the simplest version that works, then improve it.

Plan and gates: @PLAN.md
Meta API facts: @docs/meta-api.md
Progress log: `PROGRESS.md` (append, never rewrite)

## Hackathon rules (breaking any of these disqualifies the project)

- All code is written during the event, from Oct 30, 2026. Never paste, rebuild from memory or
  imitate `pilot.py` or the FreightAudit codebase. They are not in this repo and must stay out.
- The repo is public. Never commit `.env`, API keys, AGAR images or other dataset files.
  AGAR is CC BY-NC: ship `scripts/get_agar.py` instructions instead of data.
- "Simple image analyzers" are a banned project type. Every feature must strengthen the agent
  loop, the verifier, or the measured accuracy. Photo-in, number-out with nothing in between is a failure.
- No medical or clinical advice anywhere: no diagnoses, no health conclusions, no "safe to eat".
  Output is a lab measurement with flags for a person to review.
- The product must genuinely use Meta models: SAM 3.1 and Muse Spark 1.3. Voice is cut; don't build it.
- Data and images: follow .claude/rules/data.md. data/ is read-only; never bypass the pre-commit guard.

## Architecture

```
photo ──> agent loop (Muse Spark 1.3 decides next step)
            ├─ segment_plate   -> SAM 3.1, whole image + overlapping tiles
            ├─ segment_region  -> SAM 3.1 on a crop the audit flagged
            ├─ visual_audit    -> Spark looks at the outline overlay, names missed/merged regions
            ├─ compute_cfu     -> pure Python, FDA BAM Ch. 3 rules
            └─ flag_for_review -> spreader, too-many-to-count, low confidence
          verifier: every number in the report must equal a logged tool output, else reject + flag
          event log: append-only JSONL of every tool call, input hash, output, cost
```

## Layout

```
src/platecount/meta/      client.py (HTTP, retries, cache, cost), sam.py, spark.py
src/platecount/counting.py   tiling, duplicate merge, rim/glare filters
src/platecount/cfu.py        CFU/mL math and FDA flags (no network, fully unit-tested)
src/platecount/agent/        loop.py, tools.py, verifier.py, events.py
src/platecount/api/app.py    FastAPI
web/                         static mobile page (plain HTML/JS/CSS, no build step)
bench/                       split.py, run.py, metrics.py
tests/                       pytest; tests/fixtures/ holds real recorded API responses
data/  .cache/  results/     gitignored
```

## Commands

- Setup: `python -m venv .venv`, activate, `pip install -r requirements.txt`
- Tests: `python -m pytest -q`
- App: `uvicorn platecount.api.app:app --reload --app-dir src`
- Dev benchmark: `python -m bench.run --split dev --limit 50`
- Test split: `python -m bench.run --split test`. Only run it when I explicitly say "run the test split".

## Lab facts

- CFU/mL = colonies / (dilution x volume plated in mL). 27 colonies at 10^-2 with 1 mL -> 2,700 CFU/mL.
- FDA BAM Chapter 3 (revised March 2025): countable range 15-300 colonies per plate.
  Below 15 or above 300: still report, but flag. Spreader: flag for review.

## Code rules

- Python 3.10+, type hints everywhere, Pydantic models for every API response and report.
- `httpx` for HTTP. Every Meta call goes through `meta/client.py`: disk cache keyed by
  (model, prompt, image hash), retry 429/5xx with backoff, fail fast on 400/401/403/404,
  and add the call's cost to a running counter that is printed at the end of every run.
- The LLM never does arithmetic and never invents counts. Counts come from SAM boxes + code.
- Read the API key only from the `MODEL_API_KEY` environment variable (loaded from `.env`).
- Small pure functions; no global mutable state; no new dependency without asking me.
- Mobile page: works at 360 px width, one primary action per screen, large tap targets.

## How to work with me

- Anything touching more than one file: plan first, wait for my OK, then build.
- One task per session. When a task is done, I will `/clear`.
- Never say "done" until `python -m pytest -q` passes and you have shown me real output.
- When an API call fails, show the status code and response body, then check docs/meta-api.md
  and the live Meta docs before guessing.
- Before adding a feature, check PLAN.md. If it is not in today's list, ask first.
- At the end of a task, append 2-4 lines to PROGRESS.md: date/time IST, what was built, the number it produced.
- Commit after each working step with a clear message. Never push with `--force`.

## Spending

- Meta credit is $150 with a $60 spend limit. A single run must not exceed $5 without asking me.
- Always use the cache. Never hit the API inside unit tests: use `tests/fixtures/`.
