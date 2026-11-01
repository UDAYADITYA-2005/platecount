---
paths:
  - "tests/**/*.py"
---

# Test rules

- Tests never call the network. Use recorded responses in `tests/fixtures/`.
- `cfu.py` tests include: 27 colonies at 10^-2 with 1 mL -> 2,700 CFU/mL; counts of 14, 15, 300 and 301
  to check range flags; volume 0.1 mL; zero colonies.
- Verifier tests include a report with a number no tool produced; it must be rejected.
- Keep each test under one second.
