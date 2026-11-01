# PlateCount project setup for Windows PowerShell.
# Run from inside the project folder:  powershell -ExecutionPolicy Bypass -File .\setup.ps1
$ErrorActionPreference = "Stop"

Write-Host "1/5 Checking tools..."
foreach ($cmd in @("python", "git")) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
    Write-Host "Missing: $cmd. Install it (see SETUP.md step 1), open a new PowerShell, rerun." -ForegroundColor Red
    exit 1
  }
}
python --version

Write-Host "2/5 Creating virtual environment .venv..."
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt --quiet

Write-Host "3/5 Creating .env from .env.example..."
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

Write-Host "4/5 Initialising git..."
if (-not (Test-Path ".git")) {
  git init -b main | Out-Null
  git config core.hooksPath scripts/hooks
  git add -A
  git commit -m "Start PlateCount from Claude Code kit" | Out-Null
}

git config core.hooksPath scripts/hooks
Write-Host "Commit guard on: images, data/ and .env are blocked from commits."
Write-Host "5/5 Done." -ForegroundColor Green
Write-Host "Next: open .env in Notepad and paste your key after MODEL_API_KEY="
Write-Host "Then run:  .\.venv\Scripts\Activate.ps1   and then:  claude"
