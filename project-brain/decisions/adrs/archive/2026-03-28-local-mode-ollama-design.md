# Local Mode: Ollama Integration & Airplane Mode

**Date**: 2026-03-28
**Status**: Draft
**Scope**: Ollama as local LLM backend for existing CLI agents, with airplane mode for offline operation

## Overview

Add local mode support to Augur so users can run their existing CLI agents (Claude Code, Codex, OpenCode, etc.) against a local Ollama model server instead of cloud APIs. Airplane mode automatically switches to local mode when connectivity is lost, or can be manually forced.

Ollama is an **infrastructure backend**, not a client. The agent is still Claude Code or Codex — Ollama just serves the model locally. This means skill sync, MCP wiring, and agent formats are unchanged.

## Current Environment

- Ollama v0.17.6 at `/opt/homebrew/bin/ollama`
- Installed model: `qwen3.5:9b` (6.6 GB)
- Ollama supports 7 agent integrations: claude, cline, codex, droid, opencode, openclaw, pi

## Architecture

```
Cloud mode:   Claude Code / Codex  →  Anthropic API / OpenAI API
Local mode:   Claude Code / Codex  →  Ollama (localhost:11434)
```

Ollama has two roles:
1. **Model server** — serves local LLMs via Anthropic-compatible and OpenAI-compatible APIs
2. **Agent launcher** — `ollama launch <agent>` starts the real CLI agent pointed at local models

### Launch Commands

| Agent | Command |
|-------|---------|
| Claude Code | `ollama launch claude --model qwen3.5:9b` |
| Codex | `ollama launch codex --model qwen3.5:9b` |
| OpenCode | `ollama launch opencode --model qwen3.5:9b` |
| With extra args | `ollama launch claude --model qwen3.5:9b -- --mcp-config .claude/mcp.json` |

Manual equivalent (what `ollama launch claude` does under the hood):
```bash
ANTHROPIC_AUTH_TOKEN=ollama \
ANTHROPIC_BASE_URL=http://localhost:11434 \
claude --model qwen3.5:9b
```

## Local Backend Configuration

Stored in Augur preferences (via `update-preference` MCP tool).

```yaml
local_backends:
  default: "ollama"

  ollama:
    binary: "/opt/homebrew/bin/ollama"   # auto-detected, user can override
    model: "qwen3.5:9b"                  # default model
    agent: "claude"                       # claude|codex|opencode|cline|droid|openclaw|pi
    context_length: 32768                 # recommended minimum for coding
    extra_args: []                        # passed after -- to the agent CLI (e.g., --mcp-config)

airplane_mode:
  enabled: false
  auto_detect: true
  fallback_tools:
    - "web-search"
    - "web-fetch"
    - "knowledge-summarize-url"
```

Key decisions:
- One backend config block per backend type (ollama today, lm-studio/vllm later)
- `agent` field lets user pick which CLI to run through Ollama
- `fallback_tools` is an exclusion list (easier to maintain than inclusion)
- Auto-detection defaults to on

## Airplane Mode

### Three Triggers

1. **Manual** — `/airplane on` or `/airplane off`
2. **Auto-detect** — connectivity watchdog checks reachability periodically
3. **Dashboard toggle** — preference UI switch

### Connectivity Detection

```
1. Try DNS resolve api.anthropic.com (fast, low overhead)
2. If fails → mark offline, activate airplane mode
3. If succeeds → mark online, deactivate airplane mode (unless manually forced)
4. Check interval: 30 seconds when online, 10 seconds when offline (faster recovery)
```

### Manual Override Rules

- `/airplane on` — forces airplane mode regardless of connectivity, stays on until `/airplane off`
- `/airplane off` — disables, re-enables auto-detect
- Manual force takes priority over auto-detect

### Behavior Changes in Airplane Mode

| Aspect | Online | Airplane |
|--------|--------|----------|
| CLI command | User's configured default (e.g., `claude`) | `ollama launch <agent> --model <model>` |
| MCP tools | All available | External-dependent tools filtered out |
| Notification | None | "Airplane mode active — using local model `qwen3.5:9b`" |
| Skills/agents | Full sync | Same sync, no change |

### What Does NOT Change

- MCP server (still Python, still local)
- Skill sync format (same client format — Ollama just runs them)
- File ops, memory, vault access — all local

## Integration Dashboard & Health Checks

### Config Entry

New `local_backends` section in `config/agents/ide_integrations.yaml`:

```yaml
local_backends:
  ollama:
    enabled: true
    health_checks:
      binary_present: "which ollama"
      server_running: "ollama list"
      models_available: "ollama list --json"
    managed_by: "augur"
```

### MCP Tool: `get-local-backend-status`

```json
{
  "ollama": {
    "installed": true,
    "version": "0.17.6",
    "binary": "/opt/homebrew/bin/ollama",
    "server_running": true,
    "models": [
      { "name": "qwen3.5:9b", "size": "6.6 GB", "modified": "2026-03-28" }
    ],
    "configured_model": "qwen3.5:9b",
    "configured_agent": "claude",
    "ready": true
  },
  "airplane_mode": {
    "enabled": false,
    "forced": false,
    "connectivity": "online",
    "last_check": "2026-03-28T14:32:00Z"
  }
}
```

### Dashboard Card

On the integrations page:
- Ollama status (installed / running / ready)
- Current model + size
- Airplane mode toggle
- "Pull model" action (`ollama pull <model>`)
- "Launch local" action (`ollama launch <agent> --model <model>`)

## Slash Commands

### `/airplane [on|off|status]`

- `on` — force airplane mode, start local backend
- `off` — disable airplane mode, resume auto-detect
- `status` — show current mode, connectivity, backend health
- No args — toggle current state

### `/local [launch|status|pull|config]`

- `launch` — start `ollama launch <agent> --model <model>` with Augur MCP attached
- `status` — show Ollama health, installed models, current config
- `pull <model>` — run `ollama pull <model>` and update preference
- `config` — open local backend preferences for editing
- No args — same as `launch`

### Integration with Existing Commands

- `/onboard` gains a "Local Mode Setup" step — detect Ollama, suggest models, configure preferences
- `/dev-sync` gains Ollama status in its health report
- `/observe` shows airplane mode state in system health dashboard

### Notification Flow

```
[auto-detect] No connectivity detected
[airplane] Switching to local mode — ollama launch claude --model qwen3.5:9b
[airplane] Filtered 3 external-dependent MCP tools
[airplane] Ready. Local model active.
```

## Scope

### In Scope (v1)

- Ollama as the only local backend (extensible later)
- Preference-based config for backend, model, agent
- Airplane mode with auto-detect + manual override
- MCP tool filtering when offline
- Health checks and dashboard card
- `/airplane` and `/local` slash commands
- `/onboard` integration

### Not in Scope (v1)

- LM Studio, llama.cpp, vLLM backends (config structure supports them for future)
- Automatic model recommendation based on hardware
- Model download progress tracking in dashboard
- Prompt simplification for weaker models (local models get the same prompts)
- Ollama server auto-start (user manages Ollama lifecycle)
- Cloud model support via Ollama (`minimax:cloud`, etc.) — only local models

## Risks

**Local model quality**: A 9B model will struggle with complex multi-step skills and long prompts. Known limitation — not something Augur should fix in v1. Users who want better local performance pull a bigger model.
