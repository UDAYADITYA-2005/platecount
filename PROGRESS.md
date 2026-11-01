# Progress log

Append only. Each entry: date and time (IST), what was built, any number it produced.
This file is part of the proof that all work happened during the hackathon.

## 2026-10-30
- Project created from the PlateCount Claude Code kit. No feature code yet.

## 2026-11-01
- 17:03 IST, Gate A check (due 23:00): FAIL. 0 of 10 plates counted: no src/ code, 0 AGAR images,
  no SAM fixture, pytest collected 0 tests. Also found: venv is Python 3.10.11 (3.11+ required),
  no git remote, scripts/get_agar.py missing. .env exists; key contents not checked.
- 17:17 IST, package scaffold: empty modules for the CLAUDE.md layout, pyproject.toml, exact pins in
  requirements.txt, Python rule changed to 3.10+. No feature code. pytest: 1 passed (imports every module).
- 17:24 IST, cfu.py: compute_cfu and FDA range/spreader flags, exact fractions so no float noise reaches
  the verifier. 27 colonies at 10^-2 with 1 mL -> 2,700.0 CFU/mL. pytest: 19 passed (tests/test_cfu.py + smoke).
- 19:30 IST, SAM 3.1 prompt experiments: 25 live calls on data/test_plate.jpg, about $0.06. No parser yet.
  "colony" wording returned 0; "dot" found 55 on the full image and 31 on a dense 1024x1024 crop. Boxes
  checked by eye only (one plate, no ground truth); AGAR test not run because data/agar_sample/ is empty.

  | Prompt | Full image (2048x1536) | Crop (1024x1024) |
  |---|---|---|
  | bacterial colony (with and without options) | 0 | not run |
  | bacterial colonies | 0 | not run |
  | colony | 0 | 0 (centre crop) |
  | circle | 0 | not run |
  | petri dish | 2 (both dishes) | not run |
  | spot | 19 | 0 |
  | dot | 55 | 31 |
  | white dot | 49 | 31 |
  | blob | 14 | 0 |
  | speck | 56 | 31 |
  | round spot | 50 | 31 |
  | bacteria | 0 | 0 |
  | mold | 0 | 0 |
  | "colony" + 2 boxes | 400 rejected | not run |
  | 2 boxes, no text | 2 | not run |

  Crop column is the dense crop unless noted.
- 19:54 IST, meta/client.py and meta/sam.py: retries, disk cache, run cost, store:false always, parser built
  from real fixtures. Live segment() on data/test_plate.jpg: dot 55, speck 56, blob 14, unmerged, $0.0075.
  Second run: 3 cache hits, $0.0000. pytest: 36 passed. Removed scripts/record_sam_fixture.py.
