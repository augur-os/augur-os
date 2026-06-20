---
name: onboard
x-augur-type: command
x-augur-group: augur_core
x-augur-release: mvp
x-augur-license: MIT
x-augur-tags: []
description: Setup wizard for fresh installs, migrations, full onboarding, and multi-platform
  connection. Use --migrate for upgrades, --full for complete setup, --connect to
  add platforms, --status to check install state.
x-augur-tab: system
x-augur-mcp-tools:
- get-local-backend-status
- get-setup-status
- set-setup-skipped
- update-preference
---













# /onboard

## Augur Onboarding

## Environment (auto-detected)

```
!`(python3 --version 2>&1 && node --version 2>&1 && pnpm --version 2>&1 && uv --version 2>&1 && (command -v direnv >/dev/null 2>&1 && echo "direnv: installed" || echo "direnv: NOT INSTALLED")) || echo "DEPS_MISSING"`
```

```
!`cat "$HOME/Library/Application Support/Augur/state/onboard-complete.json" 2>/dev/null || echo "NOT_ONBOARDED"`
```

**If all deps present and state JSON shows `configured_clients`**: Returning user. Skip install steps, jump to relevant mode.
**If `NOT_ONBOARDED`**: Fresh install. Run default mode.
**If `DEPS_MISSING`**: Flag missing prerequisites before proceeding.

## Usage

- `/onboard` — Interactive step-by-step setup (default)
- `/onboard --migrate` — Migration-focused onboarding for existing installations
- `/onboard --full` — Complete onboarding: fresh install + migration + verification
- `/onboard --connect <platform>` — Add a platform to an existing installation
- `/onboard --templates` — Template-based onboarding: pick dashboard templates, auto-enable required plugins
- `/onboard --status` — Show install state and connected platforms

## Options

| Flag | Description |
|------|-------------|
| `--help` | Show usage and stop |
| `--evolve` | Launch the `/evolve` skill-creation pipeline after onboarding |
| `--migrate` | Run migration-focused onboarding (legacy paths, vault migration, plugin verification) |
| `--full` | Run complete onboarding (fresh install + migration + verification) |
| `--connect <platform>` | Add a platform (vault, vscode, cursor, claude-code) to existing install |
| `--status` | Show install state: install source, connected platforms, vault status |
| `--cloud` | Show read-only cloud execution readiness for Codex, Claude, Gemini, and Copilot |
| `--cloud --client copilot` | Filter read-only cloud execution status to one client |
| `--cloud --mode review` | Check read/review/plan readiness without enabling writes |
| `--cloud --mode write` | Check write/fix/PR prerequisites and mark write enabled for selected status rows only; does not store secrets |
| `--templates` | Template-based onboarding: show template catalog grouped by hub, auto-derive and enable required plugins from selections |

## Mode Selection

Parse arguments to determine mode. Read the reference file for the selected mode and follow its instructions.

| Argument | Reference File | What runs |
|----------|---------------|-----------|
| *(none)* | `references/mode-default.md` | Interactive setup: Steps 1-6 + Post-Onboarding Checklist |
| `--migrate` | `references/mode-migrate.md` | Legacy detection, vault migration, plugin/MCP verification |
| `--full` | `references/mode-full.md` | Default steps + migration steps + verification |
| `--connect <platform>` | `references/mode-connect.md` | MCP wiring + platform-specific setup |
| `--status` | `references/mode-status.md` | Read-only state display |
| `--cloud` | `references/mode-status.md` | Read-only cloud execution readiness |
| `--templates` | `references/mode-templates.md` | Template catalog, auto-derive and enable plugins |

## `augur init` — Create a New Project

Before onboarding, you can scaffold a new Augur project from the template repo:

```bash
python project-brain/capabilities/skills/onboard/scripts/augur_init.py <project-name> [--port PORT] [--repo URL]
```

| Flag | Default | Description |
|------|---------|-------------|
| `<project-name>` | *(required)* | Short project identifier (used for directory name and external dirs) |
| `--port` | `3000` | Dashboard port |
| `--repo` | `https://github.com/augur-os/augur-os` | Template repository URL |

This clones the augur-os repo, writes `project.yaml`, creates scoped external directories (`~/Vault/<name>`, `~/Documents/<name>`, etc.), and generates `.claude/mcp.json`. After `augur init` completes, run `/onboard` inside the new project to finish setup.

## New User Prompt

Copy this into Claude Code on a fresh Windows/macOS machine:

```
Set up Augur on my Windows machine.

1. Clone the repo:
   git clone https://github.com/augur-os/augur-os.git ~/Projects/Augur

2. Then run: `/onboard`
```

## AI Agent Install

For users coming from AI agents (Claude Code, Codex, Gemini, Cursor, etc.),
a universal install prompt is available at `project-brain/capabilities/skills/onboard/install.md`.

The user copies this prompt and pastes it into their agent session. The agent
auto-detects the platform and runs the full Augur installer.

Once onboarding is complete, use `/evolve` for new skill creation or extension.
`/onboard` handles setup and installation; `/evolve` handles the guided
intake-to-verified-skill pipeline.

## MCP tools exposed

- `get-setup-status` — aggregate status for the Setup widget.
- `set-setup-skipped` — mark or unmark setup items as skipped in preferences.

### Local Mode Setup (Optional)

Detect and configure Ollama for offline operation.

1. Check if Ollama is installed: `which ollama`
2. If installed:
   - Check server status: `ollama list`
   - Show available models
   - Ask user which model to use as default
   - Ask which agent to use (claude recommended)
   - Save preferences via:
     ```
     Tool: update-preference
     Args: { "key": "local_backends", "value": { "default": "ollama", "ollama": { "binary": "<path>", "model": "<chosen>", "agent": "<chosen>", "context_length": 32768, "extra_args": [] } } }
     ```
   - Display: "Local mode configured. Use `/local launch` to start, `/airplane on` for offline mode."
3. If not installed:
   - Display: "Ollama not found. Install with `brew install ollama` for local model support. Skip for now? (y/n)"
   - If skip, continue onboarding. If install, run `brew install ollama` and repeat from step 2.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `python` not found | Use `python3` on macOS/Linux |
| `python` uses wrong version / missing deps | Install direnv (`brew install direnv`), run `direnv allow` in project root |
| Claude Desktop doesn't show MCP | Restart Claude Desktop after running configure_mcp.py |
| Dashboard build fails | Run `pnpm install` again, check Node version (22+) |
| Permission denied (Python) | Run `uv sync` instead of pip |

## Examples

- `/onboard` — Interactive step-by-step setup (default)
- `/onboard --migrate` — Migration-focused onboarding for existing installations
- `/onboard --full` — Complete onboarding: fresh install + migration + verification
- `/onboard --connect <platform>` — Add a platform to an existing installation

## Additional resources
- [install.md](install.md)
- [evals/rank.json](evals/rank.json)
- [references/platform-detection.md](references/platform-detection.md)
- [references/mode-connect.md](references/mode-connect.md)
- [references/mode-default.md](references/mode-default.md)
- [references/mode-full.md](references/mode-full.md)
- [references/mode-migrate.md](references/mode-migrate.md)
- [references/mode-status.md](references/mode-status.md)
- [references/mode-templates.md](references/mode-templates.md)
