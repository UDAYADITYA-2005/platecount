---
name: bench
description: Run the PlateCount dev benchmark with a cost check, then summarise results.
disable-model-invocation: true
argument-hint: "[limit, default 50] [variant name]"
---

Run the dev benchmark. Arguments: $ARGUMENTS

1. Estimate the cost first: plates x tiles per plate x $0.0025, plus Spark calls if the agent runs.
   If over $5, stop and ask me.
2. Run `python -m bench.run --split dev` with the given limit and variant. Never use the test split here.
3. Hand the results to the eval-analyst subagent.
4. Append to PROGRESS.md: time IST, variant, sMAPE, MAE, within-10%, cost.
