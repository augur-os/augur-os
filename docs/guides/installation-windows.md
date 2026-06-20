# Windows Installation Guide

Augur is in soft launch. Get to know your AI setup, build your local second brain, and talk with your projects. Native Windows architecture is implemented, but Windows validation is still pending before any firmer support claim.

This guide covers the current native Windows bootstrap path for Augur on Windows 10/11.

## Prerequisites

### Required

1. **Git for Windows**
   ```powershell
   # Option A: Using winget (Windows 11 / Windows 10 with App Installer)
   winget install Git.Git

   # Option B: Download from https://git-scm.com/download/win
   ```

2. **Python 3.11+** (but < 3.14)
   ```powershell
   # Option A: Using winget
   winget install Python.Python.3.11

   # Option B: Download from https://www.python.org/downloads/
   ```

   > **Important**: During installation, check **"Add Python to PATH"**

3. **Node.js 22 LTS** (for dashboard)
   ```powershell
   # Option A: Using winget
   winget install OpenJS.NodeJS.LTS

   # Option B: Download from https://nodejs.org/
   ```

### Recommended (for offline OCR and ASR)

Install Ollama and pull the OCR model:

```powershell
winget install Ollama.Ollama
ollama pull glm-ocr
```

For accelerated local audio transcription on Intel AI PCs, install the current Intel NPU driver and use Augur's `ai-pc-demo` Python extra. Augur's active OCR ladder no longer uses Tesseract; scanned PDFs and image-heavy imports route through Ollama GLM-OCR first, then passive-agent cloud OCR when policy allows.

## Installation

The public first-run path starts from a desktop AI chat: paste the Augur install prompt, choose a folder by answering "Which folder should I initialize?", let the agent run `uv run aug onboard run` followed by `uv run aug init --project <folder>` from the Augur install directory, and review the read-only AI artifact inventory. This guide documents the current native Windows validation path for that installer flow, not a broader public-ready installer promise.

### Recommended: one command (`aug onboard run`)

Install prerequisites (PowerShell):

```powershell
# uv
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
# Node 22+ and Git
winget install OpenJS.NodeJS
winget install Git.Git
```

Then install Augur:

```powershell
git clone https://github.com/augur-os/augur-os.git
cd augur-os
uv run aug onboard run
```

`uv run aug onboard run` checks prerequisites (and prints the exact per-OS install command if `uv` or Node 22+ is missing — it does not install system tooling for you), installs dependencies, builds the dashboard, wires MCP, seeds a local brain, and verifies the system is up at <http://localhost:3000/browse>. `scripts\onboard.ps1` is the equivalent thin PowerShell launcher for the same engine. Then `uv run aug init --project <folder>` produces the read-only AI artifact inventory.

### One-click setup from augur.run

Preferred v1 path:

1. Open `https://augur.run` on the Windows machine.
2. Copy the Windows onboarding prompt.
3. Paste it into ChatGPT or Codex.
4. Answer the first folder question: "Which folder should I initialize?"
5. After the folder answer is collected, let the agent run the bootstrap. If the active ChatGPT surface cannot run local commands, run the PowerShell command it prints.

The command downloads `scripts/windows-one-click-bootstrap.ps1`, installs missing prerequisites with `winget` where supported, installs Codex CLI through the current official npm channel, clones or updates Augur, and hands off to Codex for verification.

Codex sign-in may require a browser interaction after the folder answer. If setup reports `Needs sign-in`, run `codex login`, complete OpenAI authentication, then rerun the bootstrap command.

After the bootstrap is ready, let the agent run `uv run aug init --project <folder>` from the Augur install directory using the already selected folder. The expected first success report is the project brain id, project-brain metadata folder, inventory count, warning count, inventory path, chosen-folder write boundary, and Browse URL: `http://localhost:3000/browse`. Next action: Ask Augur about this project. The first project question is answer-only by default; Augur does not save or retain anything unless you ask.

### Direct PowerShell bootstrap

If you are not copying the prompt from `augur.run`, first choose the folder for Augur to initialize, then use the same bootstrapper directly from PowerShell:

```powershell
$script = "$env:TEMP\windows-one-click-bootstrap.ps1"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/augur-os/augur-os/main/scripts/windows-one-click-bootstrap.ps1" -OutFile $script
powershell -NoProfile -ExecutionPolicy Bypass -File $script
```

This is the current quick path because it uses the same bootstrap, Codex CLI, authentication, repo update, and verification handoff described above. It is still part of the pending Windows validation path, not a fully validated Windows installer promise.

### Custom bootstrap options

Set environment variables before running:

```powershell
# Custom installation directory
$env:AUGUR_DIR = "D:\Projects\augur"

# Custom branch
$env:AUGUR_BRANCH = "main"

$script = "$env:TEMP\windows-one-click-bootstrap.ps1"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/augur-os/augur-os/main/scripts/windows-one-click-bootstrap.ps1" -OutFile $script
powershell -NoProfile -ExecutionPolicy Bypass -File $script
```

## Post-Installation

### 1. Activate Virtual Environment

```powershell
$installDir = if ($env:AUGUR_DIR) { $env:AUGUR_DIR } else { Join-Path $env:USERPROFILE "Projects\augur" }

# PowerShell
& "$installDir\.venv\Scripts\Activate.ps1"

# Command Prompt
"$installDir\.venv\Scripts\activate.bat"
```

### 1.1 Verify document capability

```powershell
$installDir = if ($env:AUGUR_DIR) { $env:AUGUR_DIR } else { Join-Path $env:USERPROFILE "Projects\augur" }
cd $installDir
uv run aug get-extraction-status
```

Look for:
- `document_parsing_ready: true`
- `text_pdf_extraction_ready: true`
- `ocr_engine: glm-ocr`
- `ocr_engine_available: true` after `ollama pull glm-ocr`

### 2. Start the Dashboard For Contributor Validation

`uv run aug onboard run` already installs dashboard dependencies and builds it.

<details>
<summary>Manual setup (contributors who bootstrapped without the onboard engine)</summary>

```powershell
$installDir = if ($env:AUGUR_DIR) { $env:AUGUR_DIR } else { Join-Path $env:USERPROFILE "Projects\augur" }
cd $installDir
corepack enable
pnpm install
```
</details>

Use the managed dev workflow (`uv run aug dev build`) when you need the dashboard for contributor validation, then open http://localhost:3000 in your browser.

### 3. Configure MCP

```powershell
$installDir = if ($env:AUGUR_DIR) { $env:AUGUR_DIR } else { Join-Path $env:USERPROFILE "Projects\augur" }
cd $installDir
python scripts\configure_mcp.py --list-ides
python scripts\configure_mcp.py --client cursor --auto
```

This configures the selected IDE to use Augur MCP servers.

## Directory Structure

After installation, the repo lives at the install root:

```
$installDir\
├── .venv\                  # Python virtual environment
├── apps\dashboard\         # Dashboard app
├── config\                 # System configuration
├── docs\                   # Documentation and ADRs
├── project-brain\capabilities\skills\  # Shared skills and onboarding flows
├── scripts\                # Repo scripts
└── .github\                # CI/CD workflows
```

User data is not stored in a second companion repo. Vault, documents, runtime state, logs, and cache are resolved by Augur from project config and platform-native application-data locations. To inspect the actual paths on your machine, run:

```powershell
python -c "from src.config.paths import get_vault_dir, get_documents_dir, get_runtime_dir; print(get_vault_dir()); print(get_documents_dir()); print(get_runtime_dir())"
```

## Troubleshooting

### "python is not recognized"

Python wasn't added to PATH. Either:
1. Reinstall Python and check "Add Python to PATH"
2. Or add manually: Settings > System > About > Advanced system settings > Environment Variables

### "Execution of scripts is disabled"

Run PowerShell as Administrator and execute:
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Virtual environment activation fails

Use the full path:
```powershell
$installDir = if ($env:AUGUR_DIR) { $env:AUGUR_DIR } else { Join-Path $env:USERPROFILE "Projects\augur" }
& "$installDir\.venv\Scripts\Activate.ps1"
```

### OCR enhancement is unavailable

This usually means Ollama is not running or `glm-ocr` has not been pulled yet. Baseline document parsing and text PDF extraction should still work, but scanned PDFs and image-heavy documents need:

```powershell
ollama pull glm-ocr
```

### Text PDF extraction is unavailable

This means the baseline Python document stack did not install correctly. Re-run:

```powershell
$installDir = if ($env:AUGUR_DIR) { $env:AUGUR_DIR } else { Join-Path $env:USERPROFILE "Projects\augur" }
cd $installDir
uv sync --group dev --extra windows
```

### npm install fails

Ensure Node.js is installed and in PATH:
```powershell
node --version  # Should show v22.x.x
npm --version   # Should show 10.x.x
```

## Known Limitations

Features not yet available on Windows:
- **Voice Recording**: The meeting recorder requires a Python rewrite (coming soon)
- **Apple Notes Integration**: Use local markdown files instead
- **iMessage**: Not applicable on Windows

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AUGUR_DIR` | `%USERPROFILE%\Projects\augur` | Installation directory |
| `AUGUR_BRANCH` | `main` | Git branch to install |

## Getting Help

- GitHub Issues: https://github.com/augur-os/augur-os/issues
- Use `/help` in Claude Code for command reference
