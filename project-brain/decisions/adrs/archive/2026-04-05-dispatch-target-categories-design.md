# Dispatch Target Categories Design

**Date:** 2026-04-05
**Status:** Draft
**Scope:** Action dispatch UI, CLI/IDE target management, MCP/sync lifecycle

## Problem

All dispatch targets (Claude, Codex, Cursor, Gemini, etc.) render as identical gradient buttons with no visual distinction. The dispatch mechanism was broken (calling a non-existent `/api/ide/prompt` route). Users can't tell which targets run in the cloud vs locally vs require manual paste. Disabling a target has no effect on MCP config or synced agent files.

## Design

### 1. Target Categories

Every dispatch target has exactly one category:

| Category | Meaning | Dispatch behavior | Visual |
|----------|---------|-------------------|--------|
| `remote` | Cloud-backed CLI (Claude, Gemini, Codex CLI) | Start/reuse embedded CLI → send prompt via PTY | Purple/cyan gradient, `REMOTE` badge |
| `local` | Local LLM CLI (Ollama, OpenCode) | Start/reuse embedded CLI → send prompt via PTY | Green/teal gradient, `LOCAL` badge |
| `ide` | GUI application (Cursor, VS Code, Codex App) | Copy to clipboard → show "Paste in IDE" guidance | Gray outline, `IDE` badge |

### 2. Config Schema

`cli_agents.yaml` gains two fields: `category` and `group`.

```yaml
agents:
  - cli_id: claude
    label: Claude
    category: remote
    group: claude
    cmd: [claude, --dangerously-skip-permissions]

  - cli_id: codex
    label: Codex CLI
    category: remote
    group: codex
    cmd: [codex, --full-auto]

  - cli_id: codex-app
    label: Codex App
    category: ide
    group: codex
    cmd: [codex]

  - cli_id: cursor-cli
    label: Cursor CLI
    category: remote
    group: cursor
    cmd: [cursor-cli]

  - cli_id: cursor
    label: Cursor
    category: ide
    group: cursor
    cmd: [cursor]

  - cli_id: opencode
    label: OpenCode
    category: local
    group: opencode
    cmd: [opencode]

  - cli_id: gemini
    label: Gemini
    category: remote
    group: gemini
    cmd: [gemini, --yolo]
```

### 3. State Model

Each target has three states derived from two sources:

```
Config (cli_agents.yaml)     User Prefs (vault)
         │                           │
         ▼                           ▼
    ┌─────────┐              ┌──────────────┐
    │ catalog  │              │ enabled_groups│
    │ + PATH   │──── merge ──▶│ + variant    │──▶ final state
    │ check    │              │   overrides  │
    └─────────┘              └──────────────┘
```

**Target state resolution:**

| Config exists | Binary in PATH | Group enabled | Variant enabled | Result |
|:---:|:---:|:---:|:---:|---|
| Yes | Yes | Yes | Yes | **Enabled** — shown in dispatch dialog |
| Yes | Yes | Yes | No | **Hidden** — group active (MCP/sync live) but variant not in dispatch |
| Yes | Yes | No | — | **Disabled** — MCP removed, skills deleted, not in dispatch |
| Yes | No | — | — | **Not installed** — shown in Browse as "not installed" |
| No | — | — | — | Not in system |

### 4. User Preferences (vault)

Stored in user preferences via the existing `update-preference` MCP tool:

```yaml
dispatch_targets:
  enabled_groups:
    - claude
    - codex
    - gemini
  variant_overrides:
    codex-app: false    # Codex group enabled, but hide IDE variant from dispatch
    cursor: false       # Cursor group enabled, but hide IDE variant
```

### 5. Disable Cascade

When a **group** is disabled:

1. **Sync agents** — `sync_agents.py` deletes synced skill files for all clients in that group
2. **MCP config** — remove MCP server entries for all clients in that group
3. **Dashboard** — all variants in the group disappear from dispatch dialog

When a **variant** is disabled (but group stays enabled):
- Only affects dispatch dialog visibility
- No MCP/sync impact (shared resources stay live)

### 6. Shared-Resource Constraint

Entries with the same `group` share infrastructure (config dirs, skills folders, MCP entries). The group toggle controls the infrastructure. Individual variant toggles only control dispatch visibility.

This prevents the dangerous case: disabling `codex-app` (IDE) can't break `codex` (CLI) because they share `~/.codex/`.

### 7. API Changes

`/api/cli/configs` response adds `category` and `group`:

```typescript
{
  configs: [
    {
      cli_id: string;
      label: string;
      category: "remote" | "local" | "ide";
      group: string;
      cmd: string[];
      available: boolean;
      enabled: boolean;        // resolved from user prefs
    }
  ],
  default_cli: string;
}
```

Frontend filters to `available && enabled` before rendering.

### 8. ActionDialogView Changes

**Target grouping in UI:**
1. Remote CLIs first (purple/cyan gradient, `REMOTE` badge, Terminal icon)
2. Local CLIs second (green/teal gradient, `LOCAL` badge, Terminal icon)
3. GUI IDEs last (gray outline, `IDE` badge, Monitor icon)
4. "Copy to Clipboard" always at bottom as fallback

**Click behavior by category:**
- `remote` / `local`: `handleSendToTarget` → start embedded CLI if needed → send via PTY
- `ide`: copy to clipboard → switch to "copied" confirmation view with paste instructions

### 9. ChatViewPanels Changes

`handleSendToTarget` checks `category` from the target:
- `remote` | `local` → existing embedded CLI PTY path (start → wait → send via `/api/cli`)
- `ide` → copy to clipboard, no PTY interaction

### 10. Browse > Integrations Page

Each group shows as a card:
- Group name + icon
- Installed/not-installed state
- Enable/disable toggle (controls MCP + sync cascade)
- When enabled: variant checkboxes for dispatch visibility
  - `[x] Codex CLI (remote)`
  - `[ ] Codex App (IDE)`

### 11. Files to Modify

| File | Change |
|------|--------|
| `config/agents/cli_agents.yaml` | Add `category` and `group` fields to all entries |
| `apps/dashboard/app/api/cli/configs/route.ts` | Read `category`, `group`; merge user prefs for `enabled` |
| `apps/dashboard/features/components/ActionDialogView.tsx` | Category-based styling, badge, grouped rendering |
| `apps/dashboard/features/components/chat/ChatViewPanels.tsx` | Category-aware dispatch (PTY vs clipboard) |
| `src/scripts/sync_agents.py` | Respect enabled_groups when syncing/deleting |
| `src/mcp/augur_mcp/` | MCP config enable/disable on group toggle |
| Browse integrations page | Group cards with variant checkboxes |
| User preferences schema | `dispatch_targets.enabled_groups` + `variant_overrides` |
