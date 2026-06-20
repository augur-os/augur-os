---
title: "ADR-534: Dispatch Target Categories"
status: Implemented
date: 2026-04-05
deciders: gsannikov
related: [ADR-020, ADR-130, ADR-160, ADR-460]
---

# ADR-534: Dispatch Target Categories

## Status

Implemented

## Context

The dashboard action dispatch system treated all targets identically — Claude, Codex, Cursor, Gemini, and local tools all rendered as the same purple-cyan gradient button with no visual distinction. Users couldn't tell which targets run in the cloud vs locally vs require manual paste. The dispatch mechanism was broken (calling a non-existent `/api/ide/prompt` route), and disabling a target had no effect on MCP config or synced agent files.

Additionally, tools like Cursor and Codex have both CLI and GUI variants that need independent control but share infrastructure (config dirs, MCP entries), creating a dangerous corner case where disabling one variant could break the other.

### Pain Points

- All "Send to X" buttons looked identical — no way to distinguish cloud CLI from local LLM from GUI IDE
- Send buttons silently failed (404 to non-existent API route)
- No way to disable a target and have it cascade to MCP/sync cleanup
- No shared-resource protection for multi-variant tools (codex CLI + codex app)

## Decision

### 1. Three target categories

Every dispatch target has exactly one category declared in `cli_agents.yaml`:

| Category | Meaning | Dispatch | Visual |
|----------|---------|----------|--------|
| `remote` | Cloud-backed CLI | Embedded PTY | Purple/cyan gradient, REMOTE badge |
| `local` | Local LLM CLI | Embedded PTY | Green/teal gradient, LOCAL badge |
| `ide` | GUI application | Copy to clipboard | Gray outline, IDE badge |

### 2. Group-based infrastructure sharing

Entries with the same `group` field share MCP/sync infrastructure. Enable/disable is per-group (controls MCP + agent sync cascade). Individual variant visibility in the dispatch dialog is per-entry via `variant_overrides`.

### 3. Config schema

`cli_agents.yaml` gains `category` and `group` fields per entry:

```yaml
agents:
  codex:
    cmd: ["codex", "--full-auto"]
    category: remote
    group: codex
  codex-app:
    cmd: ["codex"]
    category: ide
    group: codex  # shares infra with codex CLI
```

### 4. State resolution

`/api/cli/configs` merges three sources:

1. **Config catalog** — entries from `cli_agents.yaml`
2. **PATH availability** — binary found on system
3. **User preferences** — `dispatch_targets.enabled_groups` + `variant_overrides`

Returns only enabled + available entries with their category.

### 5. Disable cascade

When a group is disabled:
- `sync_agents` deletes synced skill files for that group's adapters
- MCP server entries are removed
- All variants disappear from dispatch dialog

When a variant is disabled (group stays enabled):
- Only affects dispatch dialog visibility
- No MCP/sync impact (shared resources stay live)

### 6. Settings UI

New "Dispatch" tab in Settings shows group cards with:
- Group toggle (controls MCP/sync cascade)
- Category badge (REMOTE/LOCAL/IDE)
- Variant checkboxes when group has multiple entries

## Consequences

### Positive

- Users can instantly identify target type by color/badge
- IDE targets always copy to clipboard — no more broken auto-send attempts
- Disabling a group properly cleans up synced files and MCP entries
- Shared-resource protection prevents breaking one variant by disabling another
- Single source of truth (`cli_agents.yaml`) for all dispatch targets

### Negative

- Adding a new CLI tool requires editing `cli_agents.yaml` (by design — explicit is better than magic)
- `sync_agents` gains a dependency on user preferences file

### Neutral

- `get-ide-status` MCP tool is no longer used for target detection (replaced by `/api/cli/configs`)
- The auto-send-to-single-IDE path was removed (always shows dialog for user control)

## Implementation

### Files changed

| File | Change |
|------|--------|
| `Au-vault/ai/cli_agents.yaml` | Added `category` and `group` fields to all 8 entries |
| `apps/dashboard/app/api/cli/cli-config.ts` | Added `CliCategory` type, replaced `CLI_ENTRIES` with `KNOWN_CLI_IDS` set |
| `apps/dashboard/app/api/cli/configs/route.ts` | Merge prefs, return `category`/`group`/`enabled` per entry |
| `apps/dashboard/features/components/ActionDialogView.tsx` | `TargetCategory` type, `CATEGORY_STYLES` map, category-aware button rendering |
| `apps/dashboard/features/components/chat/ChatViewPanels.tsx` | Single-source target detection from configs, category-aware dispatch |
| `apps/dashboard/features/components/chat/types.ts` | Added `category`/`group`/`enabled` to `FloatingChatConfig` |
| `apps/dashboard/features/hooks/useCliChat.ts` | Added fields to `CliConfig` interface |
| `src/mcp/augur_mcp/core/preferences.py` | Default `dispatch_targets` in `_load_preferences()` |
| `skills/ai/scripts/sync_agents/engine.py` | `_ADAPTER_TO_GROUP` map, `_load_enabled_groups()`, skip/cleanup disabled groups |
| `apps/dashboard/app/settings/tabs/DispatchTargetsTab.tsx` | New settings tab component |
| `apps/dashboard/app/settings/dispatch/page.tsx` | New route page |
| `apps/dashboard/lib/tabs/registry.ts` | Added Dispatch tab to settings |

### Bug fixes included

| Bug | Root cause | Fix |
|-----|-----------|-----|
| "Send to X" does nothing | `/api/ide/prompt` route didn't exist | Route through embedded CLI PTY |
| Empty system prompt on actions | `get-context` returns `{result: string}` not `ContextEnvelope` | Extract markdown into `projectIdentity` |
| Auto-send race condition | CLI not ready when prompt sent | Removed auto-send, always show dialog |
| Skill scores crash | `hub` field returned as dict object | Extract `.id` string in skill_scorer.py |

## Alternatives Considered

### A. Runtime detection of category

Detect whether a CLI is cloud-based by heuristic (checking binary name, API endpoints). Rejected: fragile, impossible to maintain, wrong for custom setups.

### B. Single toggle per tool (no group/variant split)

One toggle for "Codex" that controls both CLI and App. Rejected: users want to enable CLI dispatch but not the IDE copy variant, or vice versa. The group model preserves infrastructure safety while allowing dispatch flexibility.

### C. Hardcoded category lists in TypeScript

Keep categories in dashboard code instead of config. Rejected: adding a new tool would require a code change and rebuild instead of a config edit.

## References

- [ADR-020: Action dispatch modes](ADR-020-action-dispatch-modes.md)
- [ADR-130: Action dialog refactor](ADR-130-action-dialog-refactor.md)
- [ADR-160: Agent bubble execution](ADR-160-agent-bubble-execution.md)
- [ADR-460: Agent tier operationalization](ADR-460-agent-tier-operationalization.md)
- Design spec: `docs/superpowers/specs/2026-04-05-dispatch-target-categories-design.md`
- Implementation plan: `docs/superpowers/plans/2026-04-05-dispatch-target-categories.md`
