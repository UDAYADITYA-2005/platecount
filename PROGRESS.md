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
- 22:01 IST, tiling added to counting.py: 3x3, 20% overlap, boxes touching a tile edge dropped, then mapped to full-image
  coordinates and merged with the same rule. Plate 518 only, 3775x4000, 9 tiles of 1452x1539: merged 256 vs true 298
  (-42), was 63 (-235) whole-image. 247 of 256 boxes match an AGAR label; 51 labels missed, 9 boxes unmatched. "dot"
  did most of the work ("speck" returned 0 on 5 of 9 tiles). $0.0450, 18 calls. pytest: 80 passed.

## 2026-11-02
- 02:54 IST, box matching (IoU > 0.3 or centre inside, one-to-one, greedy) and bench.run --variant whole|tiled|both, all 16
  dev plates. Whole: MAE 18.88, sMAPE 21.8%, precision 0.97, recall 0.65. Tiled: MAE 22.19, sMAPE 54.8%, precision 0.64,
  recall 0.81: better only on 518. Tiled false positives are specks (median side 9-18 px on 15 of 16 plates; colonies 39-334 px).
  Rule from dev: tile when whole count >= 56 gives MAE 6.19, sMAPE 13.4%, within 10% 37.5%, fitted on these same plates and
  not built yet. Image size as the rule: MAE 21.50. $0.6750, 270 calls. pytest: 94 passed.

  | plate | true | whole | tiled | tiled prec | tiled rec |
  |---|---|---|---|---|---|
  | 349 | 99 | 89 | 109 | 0.84 | 0.93 |
  | 11761 | 54 | 49 | 97 | 0.53 | 0.94 |
  | 14627 | 12 | 16 | 27 | 0.41 | 0.92 |
  | 356 | 4 | 3 | 27 | 0.00 | 0.00 |
  | 14130 | 18 | 15 | 15 | 0.73 | 0.61 |
  | 5207 | 6 | 7 | 44 | 0.14 | 1.00 |
  | 12031 | 56 | 52 | 79 | 0.63 | 0.89 |
  | 5312 | 25 | 27 | 69 | 0.35 | 0.96 |
  | 736 | 28 | 27 | 14 | 0.86 | 0.43 |
  | 735 | 74 | 59 | 85 | 0.68 | 0.78 |
  | 14684 | 55 | 55 | 59 | 0.73 | 0.78 |
  | 12033 | 24 | 21 | 78 | 0.26 | 0.83 |
  | 14410 | 37 | 33 | 37 | 0.68 | 0.68 |
  | 510 | 69 | 61 | 71 | 0.85 | 0.87 |
  | 518 | 298 | 63 | 256 | 0.96 | 0.83 |
  | 8386 | 24 | 18 | 53 | 0.09 | 0.21 |
- 06:37 IST, count_plate() in counting.py: whole image first, tile when the whole count is >= 56, returns path and reason. bench.run
  --variant policy, per-prompt and signed error columns back. 16 dev plates: MAE 6.19, sMAPE 13.4%, within 10% 37.5%,
  precision 0.91, recall 0.87; threshold fitted on these same plates. No min-size filter: on the 4 tiled plates 20 px cut
  54 false boxes but lost 5 real colonies, MAE 16.25 to 19.50. $0.0000, 0 API calls. pytest: 96 passed.
- 12:22 IST, load_labels now leaves out Contamination boxes: box scoring only, truth stays colonies_number. Decided before any
  test split run. Plate 734 (test, the only plate with these labels): 78 labels, 24 Contamination, colonies_number 54, so
  truth already excludes them. No dev plate has any, so dev numbers don't move. post_stream can now take cost from the response.
- 12:47 IST, agent built: meta/spark.py (stateless loop, cost from token usage), agent/tools.py, events.py, verifier.py, loop.py, bench.run
  --variant agent. 16 dev plates, live Spark: 16 of 16 verified, 0 fallbacks. Agent MAE 6.12, sMAPE 13.0%, within 10% 37.5%, precision
  0.91, recall 0.87. Policy MAE 6.19, sMAPE 13.4%, within 10% 37.5%, precision 0.91, recall 0.87. So no real gain: 15 of 16 counts
  match the policy; the one change is plate 8386 (18 to 19, a recheck_cell). Spark tiled the same 4 plates the 56 rule tiles, and that
  rule was fitted on these plates, so all of this is in-sample. Run $0.49, about $0.03 a plate, 63 API calls; rerun $0.0000. pytest: 156 passed.

  | plate | true | policy | agent | a_prec | a_rec | status | cost | tools |
  |---|---|---|---|---|---|---|---|---|
  | 349 | 99 | 109 | 109 | 0.84 | 0.93 | verified | 0.0000 | whole,tiled,view_overlay,flag,compute_cfu,finish |
  | 11761 | 54 | 49 | 49 | 1.00 | 0.91 | verified | 0.0329 | whole,view_overlay,compute_cfu,finish |
  | 14627 | 12 | 16 | 16 | 0.75 | 1.00 | verified | 0.0277 | whole,view_overlay,flag,compute_cfu,finish |
  | 356 | 4 | 3 | 3 | 1.00 | 0.75 | verified | 0.0378 | whole,view_overlay,recheck_cell,compute_cfu,finish |
  | 14130 | 18 | 15 | 15 | 1.00 | 0.83 | verified | 0.0262 | whole,view_overlay,flag,compute_cfu,finish |
  | 5207 | 6 | 7 | 7 | 0.86 | 1.00 | verified | 0.0189 | whole,view_overlay,flag,compute_cfu,finish |
  | 12031 | 56 | 52 | 52 | 0.98 | 0.91 | verified | 0.0162 | whole,view_overlay,compute_cfu,finish |
  | 5312 | 25 | 27 | 27 | 0.93 | 1.00 | verified | 0.0315 | whole,view_overlay,flag,compute_cfu,finish |
  | 736 | 28 | 27 | 27 | 1.00 | 0.96 | verified | 0.0269 | whole,view_overlay,compute_cfu,finish |
  | 735 | 74 | 85 | 85 | 0.68 | 0.78 | verified | 0.0569 | whole,tiled,view_overlay,flag,compute_cfu,finish |
  | 14684 | 55 | 55 | 55 | 0.98 | 0.98 | verified | 0.0203 | whole,view_overlay,compute_cfu,finish |
  | 12033 | 24 | 21 | 21 | 1.00 | 0.88 | verified | 0.0142 | whole,view_overlay,compute_cfu,finish |
  | 14410 | 37 | 33 | 33 | 0.97 | 0.86 | verified | 0.0406 | whole,view_overlay,flag,compute_cfu,finish |
  | 510 | 69 | 71 | 71 | 0.85 | 0.87 | verified | 0.0410 | whole,view_overlay,tiled,flag,compute_cfu,finish |
  | 518 | 298 | 256 | 256 | 0.96 | 0.83 | verified | 0.0609 | whole,view_overlay,tiled,view_overlay,compute_cfu,finish |
  | 8386 | 24 | 18 | 19 | 1.00 | 0.79 | verified | 0.0383 | whole,view_overlay,recheck_cell,flag,compute_cfu,finish |

  Correction to the cost above: plate 349 shows $0.0000 because a one-plate trial had just run it for $0.0341, so the agent's real spend
  was $0.52 for 16 plates (the 63 calls are the $0.49 part).

- Mon Nov 2, 7:45 AM IST: code review of counting, meta, agent and bench. 6 fixes, one commit each: verifier requires a real segmentation,
  bad dilution or volume refused before any paid call, non-completed responses never cached, cost printed on early stops, no Spark text
  in the report reason, recheck_cell can't lower the count. Dev replay from cache unchanged: 16 of 16 verified, agent MAE 6.12, policy
  MAE 6.19, $0.0000, 0 API calls, 292 cache hits. pytest: 172 passed.

- Mon Nov 2, IST: held-out test split run once at eval-v1 (23 plates). Agent MAE 3.78, sMAPE 8.7%, within 10% 73.9%, precision 0.90, recall
  0.91, 23 of 23 verified. Policy MAE 5.57, sMAPE 11.1%, within 10% 69.6%, precision 0.85, recall 0.90. $1.02 total. Most of the gain is 2
  plates (11924, 734), and no test plate is in the 151-300 band. Full table in results/test_eval_v1.md. --split is back to dev-only.
