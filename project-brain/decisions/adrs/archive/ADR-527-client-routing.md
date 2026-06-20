---
status: Implemented
date: 2026-04-02
deciders:
  - gsannikov
related:
  - ADR-020
  - ADR-130
  - ADR-200
  - ADR-460
hub: adaptive
tags:
  - routing
  - local-mode
  - airplane-mode
  - ollama
superseded_by: null
---

# ADR-527: Per-Action AI Client Routing

## Context

Augur dispatches all actions to whatever IDE agent is currently connected or the implicit default. There is no way to control which AI client handles a specific action or workflow. Users cannot:

- Route career actions through Codex while health actions use local Ollama
- Automatically switch everything to local mode when offline (airplane mode)
- Run autoloops with Ollama instead of cloud models

The existing infrastructure has the building blocks — 7 dispatch modes (ADR-130), airplane mode toggle, Ollama backend support, autoloop scan/fix engine (ADR-200) — but no unified routing layer connects them.

## Decision

Add a **ClientResolver** service that answers one question: "given this action in this context, which AI client should handle it?"

### Resolution Priority Chain

| Priority | Source | Condition |
|----------|--------|-----------|
| 1 | Airplane mode | `airplane_mode.enabled == true` -> Ollama |
| 2 | `--local` flag | Autoloop invoked with `--local` -> Ollama |
| 3 | Per-action override | `client_routing.overrides[action_id]` exists |
| 4 | Global default | `client_routing.default_client` is set |
| 5 | Implicit default | Whatever IDE agent is currently connected |

### Components

**1. ClientResolver module** (`src/mcp/augur_mcp/infrastructure/client_resolver.py`)
- `ResolvedClient` dataclass: `client_id`, `client_type` (ide/local/api), `model`, `source`
- `ClientResolver` class with `resolve()`, `set_override()`, `clear_override()`, `set_default()`, `list_overrides()`
- Reads preferences YAML, supports injected path for testing

**2. Three MCP tools** (registered in `infrastructure/__init__.py`)
- `resolve-client` — returns resolved client for an action
- `set-client-override` — write per-action override to preferences
- `list-available-clients` — returns clients from integrations registry

**3. Preferences schema** (`config/defaults/config/system/preferences.yaml`)
```yaml
client_routing:
  default_client: null
  overrides: {}
```

**4. Dashboard integration**
- `useActionRunner.ts`: calls `resolve-client` before dispatch (skipped for `fire` mode). Local clients get `recommended_agent` set on the action.
- `BrowseDetailActions.tsx`: `ClientSelector` dropdown per action. Fetches `list-available-clients` once in parent. Supports airplane mode indicator, click-outside-to-close.

**5. Autoloop `--local` flag**
- `OpsContext.client` field added to `src/lib/ops_protocol.py`
- `adaptive_loop_executor.py`: `--local` argparse flag sets `engine._local_client = "ollama"`
- Propagated through `engine_entry_runner.py` to `OpsContext` construction

**6. CLI interface** (`/local config`)
- `skills/local/commands/config.md`: set/clear overrides, list, set default
- Wired to the same MCP tools as the dashboard

### Files Changed

| File | Change |
|------|--------|
| `src/mcp/augur_mcp/infrastructure/client_resolver.py` | New — ClientResolver + ResolvedClient |
| `src/mcp/augur_mcp/infrastructure/local_backends.py` | 3 tool impls + input models |
| `src/mcp/augur_mcp/infrastructure/__init__.py` | Tool registration |
| `src/mcp/augur_mcp/client_surface.py` | Tool visibility |
| `config/defaults/config/system/preferences.yaml` | `client_routing` section |
| `src/lib/ops_protocol.py` | `client` field on OpsContext |
| `skills/daemon/scripts/adaptive_loop_executor.py` | `--local` flag |
| `skills/daemon/scripts/adaptive/engine.py` | `_local_client` propagation |
| `skills/daemon/scripts/adaptive/engine_entry_runner.py` | Pass client to OpsContext |
| `skills/local/commands/config.md` | New — `/local config` command |
| `skills/local/SKILL.md` | Config subcommand docs |
| `apps/dashboard/hooks/useActionRunner.ts` | `resolveClient` before dispatch |
| `apps/dashboard/components/shared/BrowseDetailActions.tsx` | ClientSelector dropdown |

## Consequences

### Positive

- Users can route specific actions to preferred clients without changing global settings
- Airplane mode automatically forces all actions to Ollama — zero manual intervention
- Autoloops can run offline with `--local` flag
- Single resolution point (ClientResolver) makes routing logic testable and debuggable
- `source` field on ResolvedClient provides observability into routing decisions

### Negative

- Each non-fire action dispatch adds one MCP round-trip (`resolve-client`)
- Preferences YAML is read from disk per resolution (no caching yet)
- `chat` and `oneshot` dispatch modes don't fully utilize client routing — `recommended_agent` is set but execution still uses connected IDE

### Neutral

- No changes to action YAML schema — existing actions work unchanged
- Skill authors cannot set client defaults in action definitions (can be added later)
- Human judgment in autoloops is unchanged — `--local` only affects AI client selection

## Alternatives Considered

### Alternative 1: Preferences-Only Routing (No ClientResolver)

Add `client_overrides` map to preferences and resolve in each dispatch point (useActionRunner, autoloop executor, MCP dispatch) independently.

Rejected: Resolution logic scattered across multiple files. Adding new routing rules (e.g., per-hub defaults) requires changes in every dispatch point.

### Alternative 2: Action YAML Schema Extension

Extend `ActionDef` with `client`/`provider`/`model` fields that skill authors set as defaults, with user overrides on top.

Rejected: Mixes concerns (skill author intent vs user preference). Requires migration of all action YAML files. Per-action user override already achieves the goal without schema changes.

## Implementation Order

### Phase 1: Core (Tasks 1-2)
1. ClientResolver module with tests
2. MCP tools + preferences schema

### Phase 2: Autoloop (Task 3)
3. OpsContext.client field + `--local` flag

### Phase 3: CLI + Dashboard (Tasks 4-6)
4. `/local config` command definition
5. useActionRunner integration
6. BrowseDetailActions ClientSelector

### Phase 4: Validation (Tasks 7-8)
7. Integration tests
8. Build verification + browser check

## References

- [Design spec](../../docs/superpowers/specs/2026-04-02-client-routing-design.md)
- [Implementation plan](../../docs/superpowers/plans/2026-04-02-client-routing.md)
- ADR-020: Auto dispatch mode resolution
- ADR-130: Action button discovery (v2)
- ADR-200: Auto-command scan/fix engine
- ADR-460: Agent tier system

## Implementation Prompt

> Implementation complete on branch `feat/client-routing`. 10 commits, 21 tests passing.

**Team name**: `adr-527-client-routing`

### Phase 1: Core
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | ClientResolver + ResolvedClient + 7 unit tests | `client_resolver.py`, `test_client_resolver.py` |
| 1.2 | developer | medium | MCP tools + preferences schema + 7 tool tests | `local_backends.py`, `__init__.py`, `client_surface.py`, `preferences.yaml` |

### Phase 2: Autoloop
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | low | OpsContext.client field + --local flag | `ops_protocol.py`, `adaptive_loop_executor.py`, `engine.py`, `engine_entry_runner.py` |
| 2.2 | developer | low | /local config command definition | `skills/local/commands/config.md`, `skills/local/SKILL.md` |

### Phase 3: Dashboard
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | resolveClient in useActionRunner | `useActionRunner.ts` |
| 3.2 | developer | medium | ClientSelector dropdown | `BrowseDetailActions.tsx` |

### Phase 4: Validation
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | low | Integration tests (5 e2e tests) | `test_client_routing_e2e.py` |
| 4.2 | validator | medium | Full test suite + dashboard build + browser check | — |

### Completion Criteria
- [x] All phases executed
- [x] All 21 tests pass
- [x] Dashboard builds (no type errors from our changes)
- [x] Two simplification passes completed
- [x] ADR status updated to Implemented
