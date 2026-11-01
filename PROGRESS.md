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
- 20:57 IST, counting.py merge step (no tiling): drop boxes over 5% of image or touching the border, then merge
  across prompts by IoU > 0.5 or centre inside, keeping higher confidence. data/test_plate.jpg from cache: dot 55,
  speck 56, blob 14, merged 69, $0.0000. No ground truth. Known miss: yellow blob (0.66) lost to a dot (0.75)
  at IoU 0.05, so the centre rule undercounts by 1 here. pytest: 51 passed.
- 21:49 IST, merge rule tightened (IoU > 0.5, or centre inside and areas within 2.5x); small boxes inside large ones are
  kept and returned as "nested". data/test_plate.jpg from cache: merged 70, nested 3 (was 69). AGAR loader and frozen
  split: 39 plates, 16 dev / 23 test, seed 20261101, committed before any benchmark call. Minimal bench/run.py on the
  first 10 dev plates, whole image at 2048 px: MAE 4.6, total 344 found vs 376 true, 7 under, 3 over, $0.0750. "blob"
  returned 0 on all 10. pytest: 68 passed.
- 21:54 IST, baseline "whole-image, dot+speck": default prompts now dot + speck ("blob" dropped), all 16 dev plates at
  2048 px. All plates: MAE 18.88, sMAPE 21.8%, within 10% 31.2%. True >= 15 (13 plates): MAE 22.77, sMAPE 21.2%,
  within 10% 38.5%. Plate 518 (298 true, 63 found) is 235 of the 302 total error. $0.0300, 12 calls, 20 cache hits.
  bench/metrics.py added. pytest: 72 passed.

  | plate | true | dot | speck | merged | nested | error |
  |---|---|---|---|---|---|---|
  | 349 | 99 | 89 | 87 | 89 | 0 | -10 |
  | 11761 | 54 | 48 | 48 | 49 | 0 | -5 |
  | 14627 | 12 | 16 | 0 | 16 | 0 | +4 |
  | 356 | 4 | 0 | 3 | 3 | 0 | -1 |
  | 14130 | 18 | 15 | 0 | 15 | 2 | -3 |
  | 5207 | 6 | 7 | 6 | 7 | 0 | +1 |
  | 12031 | 56 | 51 | 35 | 52 | 4 | -4 |
  | 5312 | 25 | 27 | 19 | 27 | 0 | +2 |
  | 736 | 28 | 11 | 27 | 27 | 0 | -1 |
  | 735 | 74 | 58 | 52 | 59 | 0 | -15 |
  | 14684 | 55 | 56 | 0 | 55 | 0 | +0 |
  | 12033 | 24 | 21 | 20 | 21 | 0 | -3 |
  | 14410 | 37 | 35 | 6 | 33 | 0 | -4 |
  | 510 | 69 | 62 | 57 | 61 | 0 | -8 |
  | 518 | 298 | 62 | 36 | 63 | 0 | -235 |
  | 8386 | 24 | 18 | 0 | 18 | 0 | -6 |
- 21:56 IST, Gate A check (due 23:00): PASS. bench.run on 10 dev AGAR plates from cache returned a count for all 10:
  MAE 4.60, 0 API calls, $0.0000. pytest: 72 passed. Replaces the 17:03 FAIL.
