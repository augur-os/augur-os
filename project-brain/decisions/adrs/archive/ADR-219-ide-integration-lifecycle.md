---
status: Implemented
date: '2026-03-04'
deciders:
- Gur Sannikov
- Claude
related: []
hub: null
tags:
- ide
- integration
- lifecycle
superseded_by: null
---

# ADR-219: IDE Integration Lifecycle

## Context

The Augur system manages IDE/CLI integrations through three disconnected subsystems:

1. **Dashboard** (`/settings/integrations`) — displays integration status cards with health checks, but has no mechanism to enable or disable integrations
2. **Config** (`config/agents/ide_integrations.yaml`) — stores `enabled: true/false` per IDE, but no system reads or enforces this flag
3. **sync_agents** (10 adapters in `plugins/ai/skills/ai_bridge/scripts/sync_agents/adapters/`) — generates config files for every adapter unconditionally, ignoring the enabled flag

This disconnect creates real problems:
- **Unwanted files**: IDEs the user doesn't use (Cursor, VSCode, Windsurf, Cline, Kimi) still receive generated config files (`.cursorrules`, `.cursor/`, `.windsurf/`, etc.) on every sync
- **No dashboard control**: The only way to "disable" an IDE is to manually edit YAML — the dashboard shows status but can't change it
- **No installed detection**: The dashboard doesn't detect which IDEs are actually installed on the local machine; it relies solely on MCP config presence
- **Wasted sync cycles**: The adaptive `auto-agent-sync` loop processes all 10 adapters regardless of relevance

The user's real workflow uses only Antigravity, Claude Code, Codex, and Claude Desktop. The remaining 6 IDEs produce unnecessary file churn and clutter.

## Decision

### 1. Config-Driven Lifecycle

`config/agents/ide_integrations.yaml` becomes the **single source of truth** for IDE lifecycle state. Schema enriched with:

```yaml
integrations:
  <ide_key>:
    enabled: bool          # User-controlled toggle (read-write via dashboard)
    installed: bool        # Auto-detected from filesystem (read-only)
    managed_files: list    # Files this adapter creates (for cleanup)
    last_synced: str|null  # Timestamp of last successful sync
    last_health: dict      # Health check results
    last_error: str|null
```

### 2. Adapter Base Class — Lifecycle Methods

Add three methods to `BaseAdapter` (`plugins/ai/skills/ai_bridge/scripts/sync_agents/adapters/base.py`):

- **`adapter_name: str`** — canonical key matching YAML (e.g. `"cursor"`, `"claude_code"`)
- **`get_managed_files() -> list[str]`** — returns file/directory paths this adapter creates
- **`cleanup() -> list[str]`** — deletes all managed files, returns what was removed (idempotent)
- **`detect_installed() -> bool`** — checks binary via `shutil.which()` and config dir via `Path.home()`

All 10 adapters implement these with their specific paths and detection logic.

### 3. Engine Gating

`sync_agents/engine.py` loads `ide_integrations.yaml` and gates the adapter loop:

```python
ide_config = _load_ide_integrations()
for adapter in adapters:
    if not _is_adapter_enabled(adapter.adapter_name, ide_config):
        logger.info(f"Skipping disabled adapter: {adapter.adapter_name}")
        continue
```

Applied in both `sync_all()` and `fix_mode()`.

### 4. MCP Tool: `ide-lifecycle`

New MCP tool in `src/mcp/augur_mcp/domain/ide.py` with three actions:

| Action | Behavior |
|--------|----------|
| `enable` | Set `enabled: true` in YAML. Message to run `/ops-sync` for file regeneration. |
| `disable` | Set `enabled: false` in YAML. Run `adapter.cleanup()` to delete generated files immediately. |
| `detect` | Scan all adapters' `detect_installed()`, update `installed` and `managed_files` in YAML. |

### 5. API Route

Extend `POST /api/ide/integrations` with:
- `{action: "enable", ide: "<key>"}` → calls MCP `ide-lifecycle` enable
- `{action: "disable", ide: "<key>"}` → calls MCP `ide-lifecycle` disable
- `{action: "detect"}` → calls MCP `ide-lifecycle` detect

### 6. Dashboard Toggle

`IntegrationsTab.tsx` gains:
- **Enable/disable toggle switch** on each integration card
- **Auto-detection on page load** — calls detect action, shows "Not installed" badge for missing IDEs
- **Four visual states**: Enabled+Synced (green), Enabled+Unsynced (yellow), Disabled (gray), Not Installed (dimmed)
- **Show all adapters** — not just installed ones

### 7. Immediate Cleanup on Disable

When an IDE is disabled, its generated files are deleted immediately (no archive, no deferred cleanup). This includes:
- Project-root files (`.cursorrules`, `CODEX.md`, etc.)
- Dot-directories (`.cursor/`, `.windsurf/`, `.gemini/`, etc.)
- Home-directory files (`~/.codex/`, `~/.kimi/`, `~/.opencode/`)

Re-enabling triggers a message to run `/ops-sync` which regenerates all files.

## Consequences

### Positive

- Users control which IDEs receive generated config via a dashboard toggle
- Disabling an IDE immediately cleans up its file footprint — no orphaned configs
- `sync_agents` and adaptive loops skip disabled adapters, reducing cycle time
- Auto-detection surfaces which IDEs are actually installed vs. just configured
- Single source of truth (`ide_integrations.yaml`) eliminates config drift between systems

### Negative

- Re-enabling requires a separate `/ops-sync` run (not instant regeneration) to keep the MCP tool fast
- Adding a new adapter now requires implementing 3 additional methods beyond existing sync methods
- The YAML file grows with `managed_files` lists per adapter

### Neutral

- Existing health check and MCP config flows are unchanged
- The `/ops-sync` command gains a `--detect` flag but remains backward compatible
- `auto-agent-sync` adaptive loop automatically respects enabled gating with no config changes

## Alternatives Considered

### Alternative A: Decentralized Plugin Config

Move enable/disable state from centralized `ide_integrations.yaml` into per-adapter config files inside the ai_bridge plugin, per ADR-163 decentralization principle.

**Rejected because**: All 10 IDE adapters are owned by a single plugin (ai_bridge). This isn't cross-plugin config creep — it's intra-plugin state. Splitting into 10 separate YAML files adds file management overhead with no architectural benefit.

### Alternative B: Dashboard-Only State (localStorage)

Store enable/disable in browser localStorage. Mirror to a `.sync-config.json` at project root for the sync command.

**Rejected because**: State split between browser and filesystem is fragile. Doesn't survive browser clear, breaks on multi-machine setups, and creates two sources of truth.

### Alternative C: Archive Before Delete

Move generated files to a backup location before deleting on disable, allowing recovery on re-enable.

**Rejected because**: Re-enabling just runs `/ops-sync` which regenerates everything from source. No data loss risk. Archiving adds complexity with no value.

## References

- Design doc: `docs/plans/2026-03-04-ide-integration-lifecycle-design.md`
- Implementation plan: `docs/plans/2026-03-04-ide-integration-lifecycle-plan.md`
- ADR-145: Cross-agent parity (sync_agents adapter model)
- ADR-186: sync_agents package refactoring (adapter structure)
- ADR-163: Plugin decentralization principle
- ADR-177: Pre-commit auto-fix mode (fix_mode gating)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `/adr write`. Edit if needed before running.

**Team name**: `adr-219-ide-lifecycle`

### Phase 1: Backend — Adapter Lifecycle
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Add `adapter_name`, `get_managed_files()`, `cleanup()`, `detect_installed()` to BaseAdapter with default implementations | `plugins/ai/skills/ai_bridge/scripts/sync_agents/adapters/base.py` |
| 1.2 | developer | medium | Implement lifecycle methods for all 10 adapters (claude_code, cursor, windsurf, cline, copilot, gemini, opencode, kimi, antigravity, codex) | `plugins/ai/skills/ai_bridge/scripts/sync_agents/adapters/*.py` |
| 1.3 | developer | medium | Add `_load_ide_integrations()`, `_is_adapter_enabled()` to engine.py; gate adapter loops in `sync_all()` and `fix_mode()` | `plugins/ai/skills/ai_bridge/scripts/sync_agents/engine.py` |
| 1.4 | developer | low | Write tests for adapter lifecycle methods and engine gating | `plugins/ai/skills/ai_bridge/scripts/sync_agents/tests/test_adapter_lifecycle.py`, `tests/test_engine_gating.py` |

### Phase 2: MCP Tool + API
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Add `IdeLifecycleInput` model and `ide-lifecycle` MCP tool with enable/disable/detect actions | `src/mcp/augur_mcp/domain/ide.py` |
| 2.2 | developer | low | Add POST handlers for enable/disable/detect to API route | `src/dashboard/app/api/ide/integrations/route.ts` |
| 2.3 | developer | low | Write MCP tool input model tests | `src/mcp/augur_mcp/tests/test_ide_lifecycle.py` |

### Phase 3: Dashboard UI
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Add toggle switch, auto-detection on load, four visual states, show all adapters | `src/dashboard/app/settings/ai/tabs/IntegrationsTab.tsx` |
| 3.2 | developer | low | Update ide_integrations.yaml with entries for all 10 adapters | `config/agents/ide_integrations.yaml` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run adapter lifecycle tests and engine gating tests |
| V.2 | validator | low | Run MCP tool tests |
| V.3 | validator | low | Verify dashboard builds (`npx next build`) |
| V.4 | validator | medium | Browser smoke test: toggle off Cursor, verify file cleanup, toggle on, verify re-sync message |
| V.5 | architect | low | Verify ADR intent matches implementation — all 3 systems connected |

### Completion Criteria
- [ ] All 10 adapters have `adapter_name`, `get_managed_files()`, `detect_installed()`
- [ ] `sync_all()` and `fix_mode()` skip disabled adapters
- [ ] MCP `ide-lifecycle` tool handles enable/disable/detect
- [ ] Dashboard toggle works end-to-end with immediate file cleanup
- [ ] All tests pass
- [ ] No orphaned files or broken references
- [ ] ADR status updated to Implemented
