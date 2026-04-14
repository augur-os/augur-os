# Windows Installation Guide

Augur is in soft launch. Native Windows architecture is implemented, but Windows validation is still pending before any firmer support claim.

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

3. **Node.js 20 LTS** (for dashboard)
   ```powershell
   # Option A: Using winget
   winget install OpenJS.NodeJS.LTS

   # Option B: Download from https://nodejs.org/
   ```

### Optional (for OCR/document processing)

Using [Chocolatey](https://chocolatey.org/install):
```powershell
choco install tesseract poppler ghostscript
```

Or download manually:
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)
- [Ghostscript](https://www.ghostscript.com/releases/gsdnld.html)
- [Poppler](https://github.com/oschwartz10612/poppler-windows/releases)

## Installation

This guide documents the current native Windows validation path. It should be read together with the repo-first setup in [../getting-started.md](../getting-started.md), not as a broader public-ready installer promise.

### Quick Install

Open PowerShell and run:

```powershell
# Download and run installer
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/augur-os/augur-os/main/scripts/install.ps1" -OutFile "install.ps1"
.\install.ps1
```

### Custom Installation

Set environment variables before running:

```powershell
# Custom installation directory
$env:AUGUR_DIR = "D:\Projects\augur"

# Skip tests during install
.\install.ps1 -SkipTests
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

### 2. Start the Dashboard

```powershell
$installDir = if ($env:AUGUR_DIR) { $env:AUGUR_DIR } else { Join-Path $env:USERPROFILE "Projects\augur" }
cd $installDir
corepack enable
pnpm install
pnpm --filter dashboard dev
```

Open http://localhost:3000 in your browser.

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
├── scripts\                # Repo scripts
├── skills\                 # Skills and onboarding flows
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

### OCR tests fail

This is expected if Tesseract isn't installed. OCR features are optional.

### npm install fails

Ensure Node.js is installed and in PATH:
```powershell
node --version  # Should show v20.x.x
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
