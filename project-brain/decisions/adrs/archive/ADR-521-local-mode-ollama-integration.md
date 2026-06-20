---
status: Implemented
date: 2026-03-28
deciders:
  - Gur Sannikov
related:
  - ADR-503
  - ADR-489
hub: command
tags:
  - ollama
  - local-mode
  - airplane-mode
  - offline
superseded_by: null
---

# ADR-521: Local Mode — Ollama Integration and Airplane Mode

## Context

Augur supports 9+ cloud-based CLI agents (Claude Code, Codex, Gemini, etc.) but has no local/offline execution path. Users lose all agent capabilities when:

- They are offline (flights, travel, no internet)
- They want to reduce cloud API costs
- They prefer local model execution for privacy

Ollama (v0.17.6+) provides a local LLM server with an `ollama launch` command that starts existing CLI agents (Claude Code, Codex, OpenCode, Cline, Droid, OpenClaw, Pi) against local models. This means Ollama is an **infrastructure backend**, not a new client — the agent is still Claude Code or Codex, just pointed at a local model server instead of cloud APIs.

The existing multi-client architecture (`generate_client_stubs.py`, `ide_integrations.yaml`, `client_surface.py`) does not need a new client type. Skill sync, MCP wiring, and agent formats are unchanged since the CLI is the same.

## Decision

### 1. Ollama as Tracked Infrastructure Backend

Ollama is tracked in `config/agents/ide_integrations.yaml` with health checks (binary present, server running, models available) but NOT as a client — as a backend service. The existing `OllamaAdapter` in `skills/ai/augur/adapters/ollama.py` is extended with a `get_launch_command()` method.

**Files**: `config/agents/ide_integrations.yaml`, `skills/ai/augur/adapters/ollama.py`

### 2. Two New MCP Tools

- **`get-local-backend-status`** — Detects Ollama installation, server status, available models, configured model/agent, readiness, and airplane mode state. Returns JSON with `ollama`, `airplane_mode`, and `launch_command` sections.
- **`toggle-airplane-mode`** — Supports `on`/`off`/`toggle`/`status` actions. Persists state to `airplane_mode` key in `config/system/preferences.yaml`.

Both registered in `CURATED_VISIBLE_TOOLS` for all-client visibility.

**Files**: `src/mcp/augur_mcp/infrastructure/local_backends.py`, `src/mcp/augur_mcp/infrastructure/connectivity.py`, `src/mcp/augur_mcp/infrastructure/__init__.py`, `src/mcp/augur_mcp/client_surface.py`

### 3. Preference-Based Configuration

Stored in Augur preferences (machine-specific, not in git):

```yaml
local_backends:
  default: ollama
  ollama:
    binary: /opt/homebrew/bin/ollama    # auto-detected
    model: qwen3.5:9b                   # default model
    agent: claude                        # claude|codex|opencode|cline|droid|openclaw|pi
    context_length: 32768
    extra_args: []                       # passed after -- to agent CLI

airplane_mode:
  enabled: false
  forced: false
  auto_detect: true
  fallback_tools:
    - web-search
    - web-fetch
    - knowledge-summarize-url
```

**Files**: `config/defaults/config/system/preferences.yaml`

### 4. Airplane Mode

Three triggers:
1. **Manual** — `/airplane on` or `/airplane off`
2. **Auto-detect** — DNS resolution against `api.anthropic.com` (connectivity watchdog)
3. **Dashboard toggle** — preference UI switch

Manual force (`/airplane on`) takes priority over auto-detect and stays on until `/airplane off`. When active, external-dependent MCP tools are filtered from the tool surface.

**Files**: `src/mcp/augur_mcp/infrastructure/connectivity.py`

### 5. Two New Slash Commands

- **`/airplane [on|off|status]`** — Toggle airplane mode. No args = toggle.
- **`/local [launch|status|pull|config|models]`** — Manage Ollama backend. No args = launch.

**Files**: `skills/airplane/SKILL.md`, `skills/local/SKILL.md`

### 6. Onboarding Integration

`/onboard` gains an optional "Local Mode Setup" step that detects Ollama, suggests models, and configures preferences.

**Files**: `skills/onboard/SKILL.md`

## Consequences

### Positive

- Users can run agents offline with zero cloud API costs
- Airplane mode auto-detects connectivity loss and switches seamlessly
- No changes to skill sync, MCP wiring, or agent formats — Ollama uses existing client protocols
- Configuration is extensible to future local backends (LM Studio, vLLM)
- Existing OllamaAdapter and integration dashboard gain agent launch capability

### Negative

- Local model quality is significantly lower than cloud (9B vs Claude Opus) — complex multi-step skills may fail
- Users must manage Ollama lifecycle (install, pull models, start server)
- Connectivity watchdog adds a background DNS check

### Neutral

- MCP server itself is already fully local — no changes needed
- Skill sync format unchanged — same client, different model backend
- Dashboard card UI deferred to follow-up work

## Alternatives Considered

### Alternative 1: New Client Type

Register "local" as a full client in `generate_client_stubs.py` with its own stub format, skill sync, and MCP wiring.

**Rejected**: Over-engineers the problem. The CLI is still Claude Code or Codex — Ollama just changes the model backend. Adding a new client type would duplicate skill sync for no benefit.

### Alternative 2: MCP-Only Mode (Custom Agent Loop)

Build a custom REPL that calls Ollama APIs directly, bypassing CLI agents entirely.

**Rejected**: Massive scope — reinvents what Claude Code already does. Would require building tool calling, conversation management, and prompt engineering from scratch.

### Alternative 3: Thin Launcher Without Integration Dashboard

Just provide a shell script that sets env vars and starts `claude --model X`.

**Rejected**: Doesn't track Ollama health, doesn't integrate with onboarding, no preference management, no airplane mode auto-detect. Users would have to remember commands and manage state manually.

## References

- Design spec: `docs/superpowers/specs/2026-03-28-local-mode-ollama-design.md`
- Implementation plan: `docs/superpowers/plans/2026-03-28-local-mode-ollama.md`
- Ollama Anthropic API compatibility: https://ollama.com/blog/claude
- Ollama launch command: https://ollama.com/blog/launch
- Ollama Codex integration: https://ollama.com/blog/codex
- Related: ADR-503 (Distribution Plugin Architecture), ADR-489 (One-Click Onboarding)

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - name: get-local-backend-status
      type: mcp-tool
      action: added
    - name: toggle-airplane-mode
      type: mcp-tool
      action: added
  patterns_deprecated: []
  files_affected:
    - src/mcp/augur_mcp/infrastructure/local_backends.py
    - src/mcp/augur_mcp/infrastructure/connectivity.py
    - src/mcp/augur_mcp/infrastructure/__init__.py
    - src/mcp/augur_mcp/client_surface.py
    - config/agents/ide_integrations.yaml
    - config/defaults/config/system/preferences.yaml
    - skills/airplane/SKILL.md
    - skills/local/SKILL.md
    - skills/onboard/SKILL.md
    - skills/ai/augur/adapters/ollama.py
```

## Implementation Prompt

> Already implemented. See commits on main branch (2026-03-28).

**Team name**: `adr-521-local-mode`

### Phase 1: MCP Infrastructure
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create get-local-backend-status MCP tool | `local_backends.py`, `__init__.py`, `client_surface.py` |
| 1.2 | developer | low | Create connectivity watchdog | `connectivity.py` |
| 1.3 | developer | medium | Create toggle-airplane-mode MCP tool | `local_backends.py`, `__init__.py` |

### Phase 2: Slash Commands
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | low | Create /airplane skill | `skills/airplane/SKILL.md` |
| 2.2 | developer | low | Create /local skill | `skills/local/SKILL.md` |

### Phase 3: Integration
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | low | Update integration config + adapter | `ide_integrations.yaml`, `ollama.py` |
| 3.2 | developer | low | Seed default preferences | `preferences.yaml` |
| 3.3 | developer | low | Update /onboard with local mode | `skills/onboard/SKILL.md` |

### Completion Criteria
- [x] All phases executed
- [x] All tests pass (27 new + 13 preference = 40 total)
- [x] ADR status updated to Implemented
