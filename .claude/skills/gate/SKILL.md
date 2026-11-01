---
name: gate
description: Check whether today's PlateCount gate is met and say what to cut if it is not.
disable-model-invocation: true
argument-hint: "[A|B|C]"
---

Check gate $ARGUMENTS from PLAN.md.

1. Read PLAN.md and PROGRESS.md.
2. For the gate's condition, run the smallest real check that proves it (tests, a 10-plate dev
   run using the cache, or the hosted URL). Show the output.
3. Answer in this format:
   - Gate: PASS or FAIL, with the evidence in one line
   - If FAIL: the cut PLAN.md prescribes, and the first task for tomorrow morning
   - Hours of work left today on the plan, as an estimate
4. Append the result to PROGRESS.md.
