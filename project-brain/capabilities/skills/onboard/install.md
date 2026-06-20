# Install Augur

You are installing Augur for the user. Follow these steps exactly.

## Fast Launch Contract

You are helping the user install Augur from a desktop AI chat session.

Public promise: Get to know your AI setup, build your local second brain, and talk with your projects.

1. Detect the local platform without asking the user unless required.
2. Ask exactly one first folder-initialization question, using the Step 2 prompt text below.
   The folder can be empty or can already contain AI-client files.
   The user should choose a folder for Augur to initialize.
3. Wait for the answer before running any installer command.
4. Install or update Augur by running the deterministic onboard engine (`uv run aug onboard run --project <folder>`).
5. From the Augur install directory, run `uv run aug init --project <folder>` for that folder.
6. Report the project brain id, project-brain metadata folder, AI artifact inventory count, warning count, inventory path, chosen-folder write boundary, Browse URL, and next action.
7. Treat existing vendor files as inventory-only. Do not adopt, rewrite, merge, delete, or project over them.

The first success moment is the read-only AI artifact inventory, not full onboarding.

The installer should auto-fix missing non-sensitive prerequisites and pause only for credentials, OS permissions, or destructive ambiguity.

After inventory, open Browse at `http://localhost:3000/browse` if available. If the browser cannot open, report the URL directly. The next action is: Ask Augur about this project. The first project question is answer-only by default; do not save or retain anything unless the user asks.

Installer-owned client integration updates may run during Augur installation. For example, the installer may update Augur's own install directory, MCP/client integration config, generated client surfaces, or Codex plugin cache when that client is the active install target or an existing cache is detected. These installer-owned updates are separate from the user's chosen folder.

Default `aug init --project <folder>` remains inventory-only for the chosen folder. It must not adopt, rewrite, merge, delete, or project into the chosen folder's existing vendor files. Chosen-folder projection sync is explicit opt-in after inventory, via `uv run aug init --project <folder> --sync` from the Augur install directory or the equivalent MCP call with `run_sync=true`.

---

## Step 1: Detect Platform

Determine which AI agent/IDE you are running in:

| Check | Platform |
|-------|----------|
| You are Claude Code or `~/.claude/` exists | claude-code |
| You are Codex or `~/.codex/` exists | codex |
| You are Gemini CLI or `~/.gemini/` exists | gemini |
| `~/.cursor/` or `~/Library/Application Support/Cursor/` exists | cursor |
| `~/.codeium/windsurf/` exists | windsurf |
| `~/.opencode/` exists | opencode |
| `~/Library/Application Support/Cline/` exists | cline |
| You are running inside VS Code | vscode |
| You are running inside Antigravity | antigravity |
| You are Claude Desktop (Cowork) | cowork |

If multiple match, prefer the one you are actually running inside.
If none match, use best-effort detection or set `PLATFORM=unknown`; do not ask a platform question before the folder question.
Store the detected value as `PLATFORM` for later steps.

## Step 2: Fast Launch Install

Display this message before running the installer:

```
Get to know your AI setup, build your local second brain, and talk with your projects.

I will install or update Augur, then initialize one folder with a read-only AI artifact inventory.
Which folder should I initialize?
```

Ask this question and wait for the answer before running the installer.

## Windows one-click setup

If the detected machine is Windows, the folder answer is already collected before this section runs. Use the staged Windows bootstrap instead of the Unix `curl | bash` installer.

Run this from PowerShell:

```powershell
$script = "$env:TEMP\windows-one-click-bootstrap.ps1"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/augur-os/augur-os/main/scripts/windows-one-click-bootstrap.ps1" -OutFile $script
powershell -NoProfile -ExecutionPolicy Bypass -File $script
```

The bootstrapper downloads `scripts/windows-one-click-bootstrap.ps1`, installs supported prerequisites with `winget`, installs Codex CLI through the current official npm channel, clones or updates Augur, and hands off to Codex for repo-owned verification.

On first run, the bootstrapper also validates the private vault and search indexes. Vault setup, Codex authentication, OS permissions, and destructive ambiguity are allowed pauses after the folder answer, not before it. For unattended installs, set these before running the script:

```powershell
$env:AUGUR_VAULT_REPO = "https://github.com/<owner>/<private-vault>.git"
$env:AUGUR_VAULT = "$env:USERPROFILE\Projects\Au-vault"
```

To keep a local vault folder without cloning a remote, pass `-InitLocalVault` to the bootstrap script.

If Codex asks for authentication, complete Codex sign-in and rerun the same PowerShell command. A successful run reports `Ready` after Codex is authenticated, the vault is a git repo, indexes are built, the daemon is running, and the dashboard smoke passes. Setup logs are written to `%LOCALAPPDATA%\Augur\setup\bootstrap.log`; resumable setup state is written to `%LOCALAPPDATA%\Augur\setup\bootstrap-state.json`.

### 2a: Run the onboard engine

For macOS/Linux or non-Windows agent contexts, from the Augur install directory run the cross-OS onboard engine:

```bash
uv run aug onboard run --project <folder>
```

- Narrate each step result to the user. The engine runs ordered, idempotent steps
  (`detect_prereqs` → `sync_deps` → `build_dashboard` → `wire_mcp` →
  `seed_brain_and_vault` → `verify`) and stops on the first non-`ok` step.
- If a step returns a `guide` status (e.g. a missing prerequisite), show its exact
  install command, wait for the user to run it, then re-run `aug onboard run`
  (steps are idempotent and resume from where they stopped).
- The run is complete when the `verify` step reports the dashboard is interactive,
  MCP is connected, and a query was answered.

Pause only for credentials, OS permissions, or destructive ambiguity.

### 2b: Initialize the chosen folder

After the installer succeeds, do not stop at a message telling the user to run a command.

1. Ask the user for the folder they want Augur to initialize if they have not already chosen one. Use the exact first question above.
2. Confirm the Augur install directory from the installer output or the local checkout you just installed.
3. From the Augur install directory, run `uv run aug init --project <folder>` yourself for the chosen folder.
4. Report the project brain id, project-brain metadata folder, AI artifact inventory count, warning count, inventory path, and chosen-folder write boundary.
5. Do not project into the chosen folder unless the user explicitly opts in after seeing the inventory. If they do, run `uv run aug init --project <folder> --sync` from the Augur install directory.
6. Try to open Browse at `http://localhost:3000/browse`; if it cannot open, report the URL directly.
7. Report the next action exactly: Ask Augur about this project.

Installation is complete after you run the folder init and report the read-only AI artifact inventory.
The first project question is answer-only by default; do not save or retain anything unless the user asks.
