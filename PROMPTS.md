# Prompt playbook for Claude Code

Copy each prompt into Claude Code in order. One prompt = one task. Type `/clear` between tasks
so each one starts with a clean context; CLAUDE.md and PLAN.md reload automatically.

## How to work (read once)

1. **Plan, then build.** For any task touching more than one file, press Shift+Tab until the mode
   shows "plan", paste the prompt, read the plan, fix it, then switch back and say "go".
2. **Make it prove things.** Never accept "done" without test output or a real run.
3. **Stop it early.** Press Esc the moment it heads the wrong way. Esc twice opens the rewind menu.
4. **Commit after every working step** (`/log-progress` does this). A commit is your undo button.
5. **Watch context.** `/context` shows how full it is. Over about 60 percent: `/compact` or `/clear`.
6. **Use subagents for side jobs**: "use the code-reviewer subagent", "use the api-debugger subagent".
   They work in their own context and report back, so your main session stays clean.
7. **When stuck for 20 minutes**: `/clear`, then the "Stuck" prompt at the bottom.

---

## Sun Nov 1 (today): prompts 1-5, then 10 from the next section

**1. Scaffold**
```
Read CLAUDE.md and PLAN.md. Create the package layout from CLAUDE.md with empty modules,
requirements.txt pinned to current versions, pyproject.toml so `src/` imports work,
and one passing smoke test. Don't write any feature code yet. Show me the tree, then commit.
```

**2. Find the AGAR count field**
```
Look in data/agar_sample/. Find the annotation format: which file holds the colony count for
each image, which field it is, and whether the labels include non-colony classes such as defects.
Show three examples. Don't write code yet; tell me what the loader should read.
```

**3. SAM 3.1 client (plan mode)**
```
Read docs/meta-api.md and fetch the two SAM 3.1 doc pages it links. Plan meta/client.py and
meta/sam.py following .claude/rules/meta-api.md. Step 1 of the plan must be a tiny script that
sends ONE small image from data/agar_sample with prompt "bacterial colony" and saves the raw
response to tests/fixtures/sam_raw_1.txt. We write the parser only after we see that file.
```

**4. Parser and first count**
```
Using tests/fixtures/sam_raw_1.txt, write Pydantic models and a parser that returns boxes with
confidence. Write tests against the fixture. Then add an AGAR loader for the count field we
found and run SAM on 10 sample plates (cached). Print a table: image, true count, predicted,
error, and total cost.
```

**5. Gate**
```
/gate A
```

---

## Mon Nov 2 morning: prompts 6-9 (10 was done Sunday), then 11

**6. Benchmark harness (plan mode)**
```
Plan bench/split.py, bench/metrics.py and bench/run.py from PLAN.md Day 2. The split is frozen
with a fixed seed and saved to bench/split.json. Metrics: sMAPE, MAE, within-10%, by density band.
run.py writes results/<timestamp>/summary.json and per_plate.csv and prints the cost.
```

**7. Baseline**
```
/bench 50 whole-image
```

**8. Tiling (plan mode)**
```
Plan counting.py: overlapping tiles (start with 3x3 and 20 percent overlap), merge duplicate
boxes across tile edges, drop boxes larger than 5 percent of the plate or touching the dish rim.
Each step is a pure function with tests. Then make it a variant in bench/run.py.
```

**9. Compare**
```
/bench 50 tiled
```

**10. CFU math**
```
Write cfu.py per CLAUDE.md lab facts and .claude/rules/tests.md: compute CFU/mL from count,
dilution and volume, and return flags for below 15, above 300 and spreader (spreader is an input
flag for now). Pure Python, no network. Use the test-writer subagent for the tests.
```

**11. Log**
```
/log-progress
```

---

## Mon Nov 2 afternoon and evening

**12. Muse Spark call (plan mode)**
```
Read the Muse Spark 1.3 docs on dev.meta.ai: model ID, image input, tool calling, structured
output. Update docs/meta-api.md with what you verify. Then record one real tool-calling
response to tests/fixtures/ before writing meta/spark.py.
```

**13. Tools and events**
```
Write agent/tools.py and agent/events.py following .claude/rules/agent.md. Tools: segment_plate,
segment_region, visual_audit, compute_cfu, flag_for_review. Each tool logs to the event log
before returning. Tests use fixtures only.
```

**14. Loop and verifier (plan mode)**
```
Plan agent/loop.py and agent/verifier.py. Spark picks the next tool, max 6 steps. The verifier
rejects any report number that doesn't equal a logged tool output. Include a test where a fake
Spark reply invents a count, and show the verifier rejecting it.
```

**15. Agent vs SAM alone**
```
/bench 50 agent
```

**16. Gate**
```
/gate B
```

---

## Tue Nov 3

**17. API**
```
Write api/app.py: POST /plates (photo, dilution, volume) runs the agent and returns the report
with the event log; GET /plates/{id}. Rate limit and upload limit from .claude/rules/web.md.
Test with FastAPI's test client and a fixture-backed fake client.
```

**18. Mobile page (plan mode)**
```
Plan web/ per .claude/rules/web.md: camera input, dilution and volume fields, outlines drawn over
the photo, the agent's steps as a list, CFU/mL with flags, CSV download. Plain HTML, CSS, JS.
```

**19. Voice - CUT, skip this prompt**
```
Read the Voice Transcribe docs, record one real response to tests/fixtures/, then add a
hold-to-talk button: transcribe, then Spark extracts sample ID, dilution and volume into the form.
```

**20. Deploy**
```
I'm deploying to <Render or Railway>. Write the config, the start command and a checklist of
environment variables. The key must be set in the host's dashboard, never in the repo.
```

**21. Gate**
```
/gate C
```

---

## Tue Nov 3 evening and Wed Nov 4 morning

**22. Real plates**
```
Run the agent on the plates in data/lab_plates/ against data/lab_plates/counts.csv and write
results/lab_plates.md: a table, the error per plate and two sentences on what went wrong.
```

**23. Test split, once**
```
Run the test split. I confirm: run the test split. Then hand results to the eval-analyst subagent.
```

**24. README**
```
Write README.md for judges: problem, who it's for, results table (held-out number, how measured,
cost per plate), the architecture diagram as Mermaid, which Meta model does what, how to run it,
limitations, "Built during the hackathon (Oct 30 - Nov 4, 2026)", and "Built with Claude Code".
```

**25. Audit**
```
/ship-check
```

---

## Wed Nov 4

**26. Final fixes**
```
Fix only the blockers from the last /ship-check. No new features. Run tests, commit, tag v1.0.
```

---

## Prompts for any day

**Stuck**
```
I've been stuck on <problem> for 20 minutes. What I tried: <list>. The error: <paste>.
Don't write code yet. Give me the three most likely causes, ranked, and the quickest check for each.
```

**API error**
```
Use the api-debugger subagent on this error: <paste status and body>
```

**Review before commit**
```
Use the code-reviewer subagent on the current diff.
```

**Behind schedule**
```
Read PLAN.md and PROGRESS.md. It's <time> on <day>. What should I cut so the never-cut items
still ship by Wed 11 PM IST? Give the new list for today only.
```
