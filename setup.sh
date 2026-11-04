#!/usr/bin/env bash
# PlateCount project setup for macOS / Linux / WSL. Run from inside the project folder: bash setup.sh
set -euo pipefail
for cmd in python3 git; do
  command -v "$cmd" >/dev/null || { echo "Missing: $cmd"; exit 1; }
done
python3 --version
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip --quiet
.venv/bin/python -m pip install -r requirements.txt --quiet
[ -f .env ] || cp .env.example .env
if [ ! -d .git ]; then
  git init -b main >/dev/null
  git config core.hooksPath scripts/hooks
  chmod +x scripts/hooks/pre-commit
  git add -A
  git commit -m "Start PlateCount" >/dev/null
fi
git config core.hooksPath scripts/hooks
echo "Commit guard on: images, data/ and .env are blocked from commits."
echo "Done. Put your key in .env (MODEL_API_KEY=...), then: source .venv/bin/activate"
