# Data and image rules (always loaded)

- `data/` is read-only for you. Never move, rename, edit or delete files in it.
- Never `git add` anything under data/, .cache/ or results/raw/, any image outside docs/img/, or `.env`.
  The pre-commit guard in scripts/hooks/ will block it anyway; if it fires, fix the cause, never bypass it
  (never use `--no-verify`).
- AGAR is CC BY-NC 2.0: the README must credit it and link to its site; we ship no AGAR files.
- Lab photos in data/lab_plates/ are used only with the lab's written permission. Any image that goes
  into docs/img/ or the video must have EXIF removed (`scripts/strip_exif.py`).
- Images from demo visitors: keep in memory or a temp folder, delete within 24 hours, never log them,
  never add them to any dataset. The page tells visitors their photo is sent to Meta's API for counting.
- Use the standard Meta API tier, never the contributor tier (it allows training on inputs).
