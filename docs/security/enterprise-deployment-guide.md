---
title: Enterprise Deployment Guide
status: customer-review
date: 2026-05-12
owner: platform-admin
adr: ADR-725
---

# Enterprise Deployment Guide

This guide describes how to deploy Augur on a managed device for review. It favors explicit verification over convenience. It does not assume the future enterprise policy mode exists.

## Supported Review Shape

Use this guide for a single-user managed workstation pilot:

- One Augur repo checkout.
- One configured vault root.
- One configured documents root.
- Reviewed shared skills.
- Private skills disabled or manually reviewed.
- Optional providers explicitly approved.
- Daemon enabled only after service health is clean.

## Preflight

Windows:

```powershell
git --version
py -0p
corepack --version
uv --version
```

Expected: Git, Python 3.11 through 3.13, Corepack/pnpm, and uv are available. The ADR-725 session confirmed Python 3.14 can fail dependency resolution for packages such as `onnxruntime`; use Python 3.12 or another supported project version for enterprise review.

macOS/Linux:

```bash
git --version
python3 --version
corepack --version
uv --version
```

## Install Or Update

Windows:

```powershell
$env:AUGUR_DIR = "$env:USERPROFILE\Projects\Augur"
Set-Location $env:AUGUR_DIR
.\scripts\install.ps1 -SkipTests
```

macOS/Linux:

```bash
AUGUR_DIR="$HOME/Projects/Augur" RUN_TESTS=0 ./scripts/install.sh
```

For enterprise builds, prefer an internal Git mirror and package mirrors. The default public installers can contact GitHub, Astral, npm, PyPI, and platform package repositories.

## Configure Data Roots

Review `project.yaml`:

```powershell
Get-Content project.yaml
```

Expected:

```yaml
name: Augur
port: 3000
paths:
  vault: ~/Projects/Au-vault
  documents: ~/Projects/Au-docs
```

Enterprise deployments should replace these with approved local or managed storage paths. Code should resolve them through `src.config.paths`.

## Configure MCP

Review the topology:

```powershell
Get-Content config\system\mcp_servers.yaml
```

Expected: project-tier servers `augur-core` and `augur-framework`, plus only approved vault-tier bundle servers. Unapproved private bundle servers should not be listed.

After changes, regenerate client configuration through the owning Augur command or sync adapter. Do not hand-edit generated client files unless the adapter is unavailable and the change is explicitly documented.

## Configure Network Policy

Minimum allowlist for a default online install window:

- Git remote host.
- Python package index or enterprise mirror.
- npm package index or enterprise mirror.
- Astral uv installer host if uv is not preinstalled.
- Platform package manager endpoints if OCR system packages are installed.

Runtime allowlist should be narrower:

- Loopback for dashboard/MCP/local model backends.
- Approved OAuth endpoints during setup.
- Approved AI/OCR provider endpoints only for approved data classes.

Run the proof commands in [Network Egress Proof](network-egress-proof.md) after setup.

## Configure Daemon

Install only when persistence is approved.

Windows status:

```powershell
$env:AUGUR_DIR = (Get-Location).Path
schtasks /query /tn "com.augur.daemon" /fo LIST /v
& "$env:AUGUR_DIR\.venv\Scripts\python.exe" project-brain\capabilities\skills\daemon\scripts\service_healer.py status
```

Windows uninstall:

```powershell
$env:AUGUR_DIR = (Get-Location).Path
& "$env:AUGUR_DIR\.venv\Scripts\python.exe" project-brain\capabilities\skills\daemon\scripts\service_healer.py uninstall
```

macOS status:

```bash
launchctl print "gui/$(id -u)/com.augur.daemon"
python project-brain/capabilities/skills/daemon/scripts/service_healer.py status
```

macOS uninstall:

```bash
python project-brain/capabilities/skills/daemon/scripts/service_healer.py uninstall
```

Expected: the daemon command, arguments, and working directory point at the approved checkout. If the status command reports mismatch, stale PID, or stale status file, remediate before enabling the daemon in a pilot.

## Configure Skills

For Phase 1, use a manual allowlist:

```powershell
$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
  throw "Run uv sync first; missing Python environment: $python"
}
$vaultRoot = & $python -c "from src.config.paths import get_vault_dir; print(get_vault_dir())"
$vaultSkills = Join-Path $vaultRoot "skills"
if (-not (Test-Path -LiteralPath $vaultSkills -PathType Container)) {
  throw "Configured vault skills directory not found: $vaultSkills"
}
Get-ChildItem -LiteralPath project-brain\capabilities\skills -Directory | Select-Object Name,FullName
Get-ChildItem -LiteralPath $vaultSkills -Directory | Select-Object Name,FullName
```

Expected: only reviewed skills are enabled or referenced by MCP/client configuration. Private skills should be treated as executable code.

Future target: ADR-735 enterprise policy mode should make this allowlist enforceable instead of advisory.

## Verify Dependencies

Dashboard production dependencies:

```powershell
Push-Location apps\dashboard
corepack pnpm audit --prod
Pop-Location
```

Python installed environment:

```powershell
$python312 = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
uv sync --python $python312
uv tool run --python $python312 pip-audit --progress-spinner off --desc off --path .venv\Lib\site-packages
```

Expected: no known vulnerabilities, except local editable packages that cannot be audited through PyPI and must be source-reviewed. If the audit reports a package version older than `uv.lock`, rerun `uv sync` and audit again.

## Handoff Checklist

- `git status --short --branch` is clean on the approved commit.
- Data roots are approved and outside the repo.
- MCP topology contains only approved servers.
- Runtime network snapshot has no unexplained non-loopback connections.
- Dashboard production audit passes.
- Python installed environment audit passes after `uv sync`.
- Daemon status is healthy or daemon is explicitly uninstalled.
- Enabled skills are reviewed.
- Optional provider endpoints are approved.
- Enterprise policy gaps are accepted or tracked against ADR-735.
