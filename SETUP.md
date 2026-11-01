# Setup: from zero to your first Claude Code prompt (about 30 minutes)

Commands are for **Windows PowerShell**. macOS/Linux versions are under each step.
You need a Claude Pro or Max plan. The free plan doesn't include Claude Code.

**Claude Code already installed?** In step 1, run only the Git, Python and GitHub CLI installs you're
missing, then the `--version` checks and the `git config` lines, and carry on from step 2.
If you unzipped the first kit, delete that folder and use this one: it adds the commit guard and the revised plan.

## 1. Install the tools

Open PowerShell (Start menu, type "PowerShell"). Run these one at a time:

```powershell
winget install -e --id Git.Git
winget install -e --id Python.Python.3.12
winget install -e --id GitHub.cli
irm https://claude.ai/install.ps1 | iex
```

macOS: `brew install git python@3.12 gh` and then `curl -fsSL https://claude.ai/install.sh | bash`

**Close PowerShell and open a new window**, then check that each tool works:

```powershell
git --version
python --version
gh --version
claude --version
```

Tell git who you are (once per laptop):

```powershell
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

If `claude` isn't recognized, see https://code.claude.com/docs/en/troubleshoot-install.
If `python` opens the Microsoft Store, turn off the "App execution aliases" for python in Windows Settings.

## 2. Create the project folder from this kit

```powershell
mkdir $HOME\projects -Force
Expand-Archive -Path $HOME\Downloads\platecount-kit.zip -DestinationPath $HOME\projects\platecount
cd $HOME\projects\platecount
dir -Force
```

You should see `CLAUDE.md`, `PLAN.md`, `PROMPTS.md` and a `.claude` folder.

macOS: `mkdir -p ~/projects && unzip ~/Downloads/platecount-kit.zip -d ~/projects/platecount && cd ~/projects/platecount`

## 3. Run the setup script

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

This creates `.venv`, installs the packages, creates `.env`, and makes the first git commit.
macOS: `bash setup.sh`

## 4. Add your Meta API key

```powershell
notepad .env
```

Paste your key after `MODEL_API_KEY=` and save. `.env` is gitignored and Claude Code is blocked
from reading it (see `.claude/settings.json`).

## 5. Put the AGAR sample in place

Unzip `AGAR_demo.zip` from https://agar.neurosys.com into `data\agar_sample\`.
`data\` is gitignored, so the images never reach GitHub.

## 6. Create the public GitHub repo

```powershell
gh auth login
gh repo create platecount --public --source . --push
```

## 7. Start Claude Code

```powershell
.\.venv\Scripts\Activate.ps1
claude
```

If PowerShell says running scripts is disabled, run this once and try again:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

macOS: `source .venv/bin/activate && claude`

On first launch, log in through the browser and choose to trust the folder.
Then type `/agents` to check that five project agents are listed, and type `/` to check that
`/gate`, `/bench`, `/log-progress` and `/ship-check` appear.

## 8. Install plugins (inside Claude Code)

Install only these. Every plugin adds to Claude's context, and more is not better.

**Now:**
```
/plugin install superpowers@claude-plugins-official
/plugin install security-guidance@claude-plugins-official
/plugin install context7@claude-plugins-official
```

**On Day 4 (app and deploy):**
```
/plugin install playwright@claude-plugins-official
/plugin install frontend-design@claude-plugins-official
/plugin install render@claude-plugins-official
```
(Use `railway@claude-plugins-official` instead if you deploy on Railway.)

If Claude Code says the marketplace isn't found, add it first:
`/plugin marketplace add anthropics/claude-plugins-official`

| Plugin | What it does for PlateCount |
|---|---|
| superpowers (by obra) | Skills for test-first development, systematic debugging, and checking before claiming done. Its brainstorming step is slow, so tell Claude "skip brainstorming, the plan is in PLAN.md". |
| security-guidance (Anthropic) | Warns when code contains hardcoded secrets or injection risks, which matters because the repo is public. |
| context7 | Current docs for FastAPI, Pydantic and httpx. It probably won't cover Meta's API, so that stays in docs/meta-api.md. |
| playwright | Lets Claude open your mobile page in a browser and test it. |
| frontend-design (Anthropic) | Makes the demo page look designed instead of default. |
| render / railway | Deploy and read logs from inside Claude Code. |

Skipped on purpose: Anthropic's `document-skills` and `example-skills` bundles (you don't need
Word, PowerPoint or art skills, and example-skills loads about 12 skills at once), and the
unvetted "awesome" lists. Plugins can run code on your laptop, so read one before you install it.

## 9. Keep images, data and keys safe

Five layers, from the one you never think about to the one you must do by hand:

| Layer | What it stops | Where |
|---|---|---|
| `.gitignore` | `data/`, `.env`, caches and images never show up in `git status` | `.gitignore` |
| Commit guard | Blocks any commit with an image outside `docs/img/`, anything in `data/`, `.env`, a file over 5 MB, or your real key pasted into code | `scripts/hooks/pre-commit` (setup turns it on) |
| Claude Code settings | Claude can't read `.env`, can't edit `data/`, can't skip the guard with `--no-verify`, can't force-push | `.claude/settings.json` |
| Claude Code rules | Claude treats data as read-only, ships no AGAR files, deletes visitor photos within 24 hours | `.claude/rules/data.md` |
| You | Licence, permission and metadata, which no tool can decide | the checklist below |

Check the guard works (should print BLOCKED):
```powershell
Copy-Item (Get-ChildItem data\agar_sample -Recurse -Filter *.jpg | Select-Object -First 1).FullName test.jpg
git add -f test.jpg
git commit -m test
git restore --staged test.jpg
Remove-Item test.jpg
```

Your checklist:
- **AGAR** is CC BY-NC 2.0: non-commercial use, credit it in the README, never upload it to GitHub.
- **Lab photos**: get the lab's permission in writing (a WhatsApp message is enough) before using them in the video or README.
- **Any image you publish** (README, video, X post): strip its metadata first, because phone photos carry GPS location:
  `python scripts\strip_exif.py data\lab_plates docs\img`
- **Meta API tier**: use the standard tier, never the contributor tier, which lets Meta train on your images.
- **GitHub**: open the repo's Settings, then Code security, and check that secret scanning push protection is on.
- **If a key ever leaks**: delete it on dev.meta.ai immediately and create a new one. Deleting the commit isn't enough.

## 10. How to work with Claude Code

- **You decide, Claude types.** Read every plan before saying "go". In the live final you must be able
  to explain every module.
- **Plan mode first** (Shift+Tab until it says plan) for anything touching more than one file.
- **One prompt from PROMPTS.md per session**, then `/log-progress` and `/clear`.
- **Demand proof.** "Show me the test output" and "run it on 3 plates and show the table" beat "is it done?".
- **Press Esc** the moment it goes the wrong way. Esc twice rewinds.
- **Subagents for side jobs**: "use the api-debugger subagent on this error", "use the code-reviewer subagent".
- **Your Pro plan has usage limits.** Keep sessions short, `/clear` often, and don't paste whole files or logs.
  If you hit the limit, the reset time is shown. Meanwhile, do the non-code work (lab messages, README text, video script).

## 11. Your daily routine

1. `cd $HOME\projects\platecount`, then `.\.venv\Scripts\Activate.ps1`, then `claude`
2. Open PROMPTS.md and paste the next prompt for today
3. After each task: `/log-progress`, then `/clear`
4. At the gate time: `/gate A` (or B or C)
5. Before sleeping: `git push`

Start now with prompt 1 in PROMPTS.md.
