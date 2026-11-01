---
paths:
  - "src/platecount/agent/**/*.py"
---

# Agent rules

- Spark chooses the next tool; tools do the work. Spark's text is never a source of numbers.
- Every tool call is written to the event log before its result is used: tool, args, input hash, output, cost, ms.
- The verifier runs on every final report. A number that does not equal a logged tool output
  makes the report "rejected" with the reason shown to the user. No silent fixes.
- Hard stop at 6 tool steps per plate; on stop, return the best verified result plus a flag.
- If Spark returns malformed tool arguments, retry once with the validation error, then flag.
