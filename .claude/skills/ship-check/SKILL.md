---
name: ship-check
description: Run the full pre-submission audit for PlateCount.
disable-model-invocation: true
---

1. Run `python -m pytest -q` and show the result.
2. Delegate to the submission-checker subagent.
3. Delegate to the code-reviewer subagent on `git diff v0..HEAD` if a v0 tag exists, else on the last 20 commits.
4. Merge both reports into one list: blockers first, then fixes worth doing if time allows.
