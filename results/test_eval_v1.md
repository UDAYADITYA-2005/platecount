# Held-out test split, eval-v1

Code: tag `eval-v1` (`ecd4c39`) plus one change, `--split test` allowed (`64dba3e`, reverted after this run).
Run once, 23 test plates, Mon Nov 2 2026. Dilution and volume are nominal (AGAR records none); only counts are scored.

```
python -m bench.run --split test --variant policy --limit 23
python -m bench.run --split test --variant agent --limit 23   # MAX_RUN_USD set to 2.615 from the command line
```

Spend: policy $0.3850 (154 API calls), agent $0.6394 (90 API calls, 295 cache hits), total $1.0244. The $3 stop did not fire.

## Overall and per band

| band | variant | result |
|---|---|---|
| all | policy | 23 plates, MAE 5.57, sMAPE 11.1%, within 10% 69.6%, precision 0.85, recall 0.90 |
| all | agent | 23 plates, MAE 3.78, sMAPE 8.7%, within 10% 73.9%, precision 0.90, recall 0.91 |
| <15 | policy | 5 plates, MAE 1.00, sMAPE 12.9%, within 10% 80.0%, precision 0.87, recall 1.00 |
| <15 | agent | 5 plates, MAE 1.00, sMAPE 12.9%, within 10% 80.0%, precision 0.87, recall 1.00 |
| 15-150 | policy | 18 plates, MAE 6.83, sMAPE 10.7%, within 10% 66.7%, precision 0.85, recall 0.90 |
| 15-150 | agent | 18 plates, MAE 4.56, sMAPE 7.5%, within 10% 72.2%, precision 0.90, recall 0.91 |
| 151-300 | policy | no plates |
| 151-300 | agent | no plates |

| band | plates | agent status | tiled | recheck_cell | flag | view_overlay |
|---|---|---|---|---|---|---|
| <15 | 5 | 5 verified | 0 | 0 | 1 | 5 |
| 15-150 | 18 | 18 verified | 4 | 4 | 4 | 18 |
| 151-300 | 0 | 0 verified | 0 | 0 | 0 | 0 |

## Per plate

| plate | true | policy path | policy count | err | prec | rec | agent count | err | prec | rec | status | cost | tools |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 11764 | 41 | whole | 34 | -7 | 0.97 | 0.80 | 34 | -7 | 0.97 | 0.80 | verified | 0.0272 | whole, view_overlay, compute_cfu, finish |
| 11773 | 5 | whole | 8 | +3 | 0.62 | 1.00 | 8 | +3 | 0.62 | 1.00 | verified | 0.0209 | whole, view_overlay, compute_cfu, finish |
| 11884 | 31 | whole | 30 | -1 | 1.00 | 0.97 | 30 | -1 | 1.00 | 0.97 | verified | 0.0163 | whole, view_overlay, compute_cfu, finish |
| 11890 | 3 | whole | 3 | +0 | 1.00 | 1.00 | 3 | +0 | 1.00 | 1.00 | verified | 0.0137 | whole, view_overlay, compute_cfu, finish |
| 11924 | 58 | tiled | 91 | +33 | 0.60 | 0.95 | 56 | -2 | 0.95 | 0.91 | verified | 0.0232 | whole, view_overlay, compute_cfu, finish |
| 11955 | 4 | whole | 4 | +0 | 1.00 | 1.00 | 4 | +0 | 1.00 | 1.00 | verified | 0.0134 | whole, view_overlay, compute_cfu, finish |
| 12028 | 41 | whole | 31 | -10 | 1.00 | 0.76 | 31 | -10 | 1.00 | 0.76 | verified | 0.0130 | whole, view_overlay, compute_cfu, finish |
| 13895 | 19 | whole | 20 | +1 | 0.95 | 1.00 | 20 | +1 | 0.95 | 1.00 | verified | 0.0182 | whole, view_overlay, flag, compute_cfu, finish |
| 13938 | 32 | whole | 33 | +1 | 0.97 | 1.00 | 33 | +1 | 0.97 | 1.00 | verified | 0.0140 | whole, view_overlay, compute_cfu, finish |
| 14380 | 34 | whole | 33 | -1 | 0.97 | 0.94 | 33 | -1 | 0.97 | 0.94 | verified | 0.0150 | whole, view_overlay, compute_cfu, finish |
| 14512 | 15 | whole | 16 | +1 | 0.94 | 1.00 | 16 | +1 | 0.94 | 1.00 | verified | 0.0194 | whole, view_overlay, compute_cfu, finish |
| 14581 | 125 | tiled | 112 | -13 | 0.95 | 0.85 | 115 | -10 | 0.95 | 0.87 | verified | 0.0530 | whole, tiled, view_overlay, recheck_cell, compute_cfu, finish |
| 14618 | 40 | whole | 41 | +1 | 0.98 | 1.00 | 41 | +1 | 0.98 | 1.00 | verified | 0.0173 | whole, view_overlay, compute_cfu, finish |
| 4826 | 11 | whole | 12 | +1 | 0.92 | 1.00 | 12 | +1 | 0.92 | 1.00 | verified | 0.0270 | whole, view_overlay, flag, compute_cfu, finish |
| 4904 | 22 | whole | 22 | +0 | 1.00 | 1.00 | 22 | +0 | 1.00 | 1.00 | verified | 0.0117 | whole, view_overlay, compute_cfu, finish |
| 5206 | 101 | tiled | 109 | +8 | 0.92 | 0.99 | 109 | +8 | 0.92 | 0.99 | verified | 0.0370 | whole, tiled, view_overlay, flag, compute_cfu, finish |
| 5212 | 42 | whole | 43 | +1 | 0.98 | 1.00 | 43 | +1 | 0.98 | 1.00 | verified | 0.0355 | whole, view_overlay, recheck_cell, compute_cfu, finish |
| 525 | 83 | tiled | 85 | +2 | 0.68 | 0.70 | 96 | +13 | 0.72 | 0.83 | verified | 0.0848 | whole, tiled, view_overlay, recheck_cell, compute_cfu, finish |
| 5270 | 35 | whole | 34 | -1 | 0.94 | 0.91 | 34 | -1 | 0.94 | 0.91 | verified | 0.0248 | whole, view_overlay, flag, compute_cfu, finish |
| 5271 | 43 | whole | 42 | -1 | 0.98 | 0.95 | 42 | -1 | 0.98 | 0.95 | verified | 0.0171 | whole, view_overlay, compute_cfu, finish |
| 5308 | 10 | whole | 11 | +1 | 0.91 | 1.00 | 11 | +1 | 0.91 | 1.00 | verified | 0.0156 | whole, view_overlay, compute_cfu, finish |
| 734 | 54 | tiled | 79 | +25 | 0.51 | 0.74 | 61 | +7 | 0.67 | 0.76 | verified | 0.0806 | whole, view_overlay, recheck_cell, flag, compute_cfu, finish |
| 971 | 130 | tiled | 146 | +16 | 0.83 | 0.93 | 146 | +16 | 0.83 | 0.93 | verified | 0.0408 | whole, tiled, view_overlay, compute_cfu, finish |

## Reading it

- The agent's count differs from the policy's on 4 of 23 plates: 11924 (+33 to -2), 14581 (-13 to -10), 525 (+2 to +13), 734 (+25 to +7).
- Most of the MAE gain comes from 2 plates, 11924 and 734, where the policy tiled and the agent stayed whole. On 525 the agent got worse.
- No test plate is in the 151-300 band (largest true count 130), so this says nothing about dense plates.
- `verified` means every reported number matches a tool output. It does not mean the count is right: 971 is verified and 16 too high.
