# Build plan (IST) - revised Sun Nov 1

Submit by Wed Nov 4, 11 PM IST. Hard cutoff Thu Nov 5, 7:30 AM IST.
Office hours (#office-hours, text): Mon Nov 2 to Wed Nov 4, 8:30-9:30 PM IST. None today (Sunday).
Voice logging is cut. Do not build it.

## Sun Nov 1 (4 PM to midnight): setup, first live count, CFU math - PROMPTS 1-5, 10
- Project set up from the kit, pre-commit guard installed, repo public on GitHub
- Meta credit claimed, key in `.env`, $60 spend limit set
- AGAR sample in `data/agar_sample/`; count field identified
- `meta/client.py` + `meta/sam.py`: one real SAM 3.1 response saved to `tests/fixtures/`
- `cfu.py` with unit tests (no network, quick win)
- GATE A (11 PM): SAM 3.1 returns a count for 10 AGAR sample plates
  - Fails: Monday morning goes to fixing the API (office hours 8:30 PM); cut the visual audit

## Mon Nov 2: counting engine, benchmark, agent - PROMPTS 6-9, 12-16
- Morning: frozen split (if the sample has under 60 plates: 40 percent dev, 60 percent test),
  metrics, whole-image vs tiled on dev
- Afternoon and evening: Spark tool loop, tools, event log, verifier; agent vs SAM alone on dev
- 8:30 PM: office hours with any blocker
- GATE B (11 PM): agent runs end to end on 10 plates
  - Fails: replace visual_audit with a rule (re-segment any tile above a density threshold); keep the verifier

## Tue Nov 3: app, deploy, final number, README - PROMPTS 17, 18, 20-25
- Morning: FastAPI + mobile page
- Afternoon: deploy; GATE C (6 PM): hosted link counts a plate photo from my phone
  - Fails: deploy the simplest page that uploads and shows the report; no styling
- Evening: test split run once; README; rough backup video uploaded unlisted

## Wed Nov 4: real plates, video, submit - PROMPTS 22, 26
- Morning: any lab plates that arrived (fallback: 15 hand-counted Dryad phone photos)
- Afternoon: final 3-minute video; captions; plays while logged out
- Evening: blockers only; tag v1.0; submit on Cerebral Valley by 11 PM IST; screenshot
- X post with video, one number and repo link; link entered for Most Viral

## Cut order (when a gate fails, cut from the top)
1. Visual audit (keep rule-based re-check)
2. CSV export
3. Page styling

## Never cut
- Agent loop + verifier
- One held-out benchmark number
- Hosted demo judges can open
- 3-minute video
