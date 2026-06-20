# Client Routing: Per-Action AI Client Configuration

**Date:** 2026-04-02
**Status:** Draft
**Scope:** ClientResolver service, per-action overrides, airplane mode integration, autoloop --local flag

## Problem

Augur has no way to control which AI client handles a specific action or workflow. All actions use whatever IDE agent is connected or the implicit default. Users cannot:

- Route career actions through Codex while health actions use local Ollama
- Automatically switch everything to local mode when offline (airplane)
- Run autoloops with Ollama instead of cloud models

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Default action config | Empty (inherits global) | No migration, existing behavior preserved |
| Override storage | Preferences YAML | User data, not skill data |
| Client list source | Integrations tab registry | Dynamic, no hardcoded list |
| Airplane mode | Absolute override to Ollama | Simplest mental model |
| Autoloop --local | Ollama for scan/fix, human judgment unchanged | Keep trust gating as-is |
| CLI entry point | `/local config` subcommand | Natural home for routing config |

## Architecture

### ClientResolver

Single Python module that answers: "given this action in this context, which AI client handles it?"

**File:** `src/mcp/augur_mcp/infrastructure/client_resolver.py`

**Resolution priority chain (highest wins):**

| Priority | Source | Condition |
|----------|--------|-----------|
| 1 | Airplane mode | `airplane_mode.enabled == true` -> Ollama |
| 2 | `--local` flag | Autoloop invoked with `--local` -> Ollama |
| 3 | Per-action override | `client_routing.overrides[action_id]` exists |
| 4 | Global default | `client_routing.default_client` is set |
| 5 | Implicit default | Whatever IDE agent is currently connected |

**Output dataclass:**

```python
@dataclass
class ResolvedClient:
    client_id: str          # e.g. "antigravity", "claude-code", "ollama"
    client_type: str        # "ide" | "local" | "api"
    model: str | None       # e.g. "qwen3.5:9b" for Ollama, None for IDE agents
    source: str             # "airplane" | "local_flag" | "override" | "global" | "implicit"
```

The `source` field provides observability -- logs and UI can show why a client was chosen.

### Preferences YAML Schema

New `client_routing` section added to preferences:

```yaml
client_routing:
  default_client: null           # null = use implicit (connected IDE agent)
  overrides:                     # action_id -> client_id
    career-job-search: codex
    health-track-vitals: ollama
    # finance actions -> no entry, uses default
```

Existing sections unchanged:
- `airplane_mode` -- stays as-is, ClientResolver reads `airplane_mode.enabled`
- `local_backends` -- stays as-is, Ollama config lives here

### MCP Tools

Three new tools registered in `local_backends.py`:

| Tool | Purpose | Args |
|------|---------|------|
| `resolve-client` | Returns which client handles a given action | `{ action_id }` |
| `set-client-override` | Write per-action override to preferences | `{ action_id, client_id }` or `{ action_id, clear: true }` |
| `list-available-clients` | Returns registered clients from integrations registry | `{}` |

### Resolution Examples

```
User config:
  default_client: claude-code
  overrides:
    career-job-search: codex
    health-track-vitals: ollama

Scenario: Normal mode
  career-job-search     -> Codex       (override)
  health-track-vitals   -> Ollama      (override)
  finance-review        -> Claude Code (global default)

Scenario: Airplane mode ON
  career-job-search     -> Ollama      (airplane overrides all)
  health-track-vitals   -> Ollama      (airplane overrides all)
  finance-review        -> Ollama      (airplane overrides all)
```

## Per-Action Override UI (Browse Page)

Action detail view gets a **Client** control:

- **Default state:** Shows "Default (Claude Code)" or current global -- greyed out to indicate inherited
- **On click:** Dropdown populated from Integrations tab via `list-available-clients`
- **After selection:** Shows chosen client name with "x" to clear back to default
- **Airplane indicator:** When airplane mode is on, shows "Ollama (airplane)" with disabled dropdown

**Data flow:**
1. User picks client from dropdown
2. Dashboard calls `set-client-override` MCP tool
3. Tool writes to `client_routing.overrides` in preferences YAML
4. Next dispatch, `resolve-client` picks up the override

No bulk editing for now -- one action at a time.

## CLI Interface

`/local config` subcommand:

```bash
# Set override for a specific action
/local config career-job-search codex
/local config health-track-vitals ollama

# Clear an override (back to default)
/local config career-job-search --clear

# See all overrides
/local config --list

# Set global default
/local config --default codex
```

Writes to the same `client_routing` section in preferences YAML.

## Autoloop --local Mode

**Invocation:**

```bash
/auto-code-review --local
```

Or in daemon config for scheduled runs: `loop_args: ["--local"]`

**Changes:**

1. `adaptive_loop_executor.py` parses `--local` flag
2. Sets `ctx.client = "ollama"` on execution context
3. Scan/fix functions that use AI check `ctx.client` for backend selection
4. Trust gating and human judgment gates unchanged

**Context object extension:**

```python
@dataclass
class AutoCommandContext:
    # ... existing fields ...
    client: str | None = None  # None = use global default, "ollama" = local
```

Scan/fix functions that make no AI calls need no changes.

## Airplane Mode Integration

When airplane mode activates (manual or auto-detect):

1. `ClientResolver` returns Ollama for all actions regardless of overrides
2. Existing tool filtering (web-search, web-fetch) unchanged -- additive behavior
3. Running autoloops inherit airplane state on next cycle
4. Dashboard action detail shows "Ollama (airplane)" with disabled dropdown

When airplane deactivates, overrides and global default resume.

## File Changes

| File | Change |
|------|--------|
| `src/mcp/augur_mcp/infrastructure/client_resolver.py` | **New** -- ClientResolver class, resolution chain, ResolvedClient |
| `src/mcp/augur_mcp/infrastructure/actions.py` | Call ClientResolver at dispatch time |
| `src/mcp/augur_mcp/infrastructure/local_backends.py` | Register 3 new MCP tools |
| `config/defaults/config/system/preferences.yaml` | Add `client_routing` section |
| `skills/daemon/scripts/adaptive_loop_executor.py` | Parse `--local` flag, set `ctx.client` |
| `skills/daemon/scripts/adaptive/engine_auto_cycle.py` | Pass `ctx.client` through to scan/fix |
| `skills/local/SKILL.md` | Add `config` subcommand docs |
| `skills/local/commands/config.md` | **New** -- `/local config` command definition |
| `apps/dashboard/hooks/useActionRunner.ts` | Call `resolve-client` before dispatch |
| `apps/dashboard/components/shared/BrowseDetailActions.tsx` | Add client dropdown, airplane indicator |

## Non-Goals

- No schema changes to action YAML files
- No skill-author-level client defaults (can add later)
- No cloud AI judge for autoloops (human judgment stays)
- No bulk override editing UI
- No per-action model selection (only client selection)
