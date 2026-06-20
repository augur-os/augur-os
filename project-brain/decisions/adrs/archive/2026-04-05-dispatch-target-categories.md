# Dispatch Target Categories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add category/group fields to CLI agent configs, wire enabled state through user preferences, render category-aware dispatch buttons, and cascade disable to MCP/sync.

**Architecture:** cli_agents.yaml gains `category` and `group` fields. `/api/cli/configs` merges config + PATH availability + user prefs to return only enabled targets. ActionDialogView renders buttons grouped by category with distinct colors/badges. ChatViewPanels dispatches remote/local via PTY, ide via clipboard.

**Tech Stack:** TypeScript (Next.js App Router), Python (MCP tools, sync_agents), YAML config, Tailwind CSS

---

### Task 1: Add category and group fields to cli_agents.yaml

**Files:**
- Modify: `~/Projects/Au-vault/ai/cli_agents.yaml`

- [ ] **Step 1: Add category and group to each entry**

```yaml
# CLI Agent launch configurations
# Used by the dashboard /api/cli route to spawn interactive AI agent PTY sessions.
#
# category: remote | local | ide
#   remote — cloud-backed CLI, runs in embedded terminal
#   local  — local LLM CLI, runs in embedded terminal
#   ide    — GUI application, dispatch copies to clipboard
#
# group: entries sharing a group share MCP/sync infrastructure.
#   Enable/disable is per-group. Variant visibility is per-entry.

agents:
  claude:
    cmd: ["claude", "--dangerously-skip-permissions"]
    cwd: "."
    category: remote
    group: claude
    env:
      HOMOSAPIEN_WELCOMED: "1"

  codex:
    cmd: ["codex", "--full-auto"]
    cwd: "."
    category: remote
    group: codex
    env:
      HOMOSAPIEN_WELCOMED: "1"

  gemini:
    cmd: ["gemini", "--yolo"]
    cwd: "."
    category: remote
    group: gemini
    env:
      HOMOSAPIEN_WELCOMED: "1"

  opencode:
    cmd: ["opencode"]
    cwd: "."
    category: local
    group: opencode
    env:
      HOMOSAPIEN_WELCOMED: "1"

  cursor-cli:
    cmd: ["cursor-agent", "--force", "--approve-mcps"]
    cwd: "."
    category: remote
    group: cursor
    env:
      HOMOSAPIEN_WELCOMED: "1"

  kimi:
    cmd: ["kimi", "--yolo"]
    cwd: "."
    category: remote
    group: kimi
    env:
      HOMOSAPIEN_WELCOMED: "1"

  copilot-cli:
    cmd: ["copilot"]
    cwd: "."
    category: remote
    group: copilot
    env:
      HOMOSAPIEN_WELCOMED: "1"

  claude-kimi:
    cmd: ["claude", "--dangerously-skip-permissions", "--model", "ollama/kimi-k2.5:cloud"]
    cwd: "."
    category: local
    group: claude-kimi
    env:
      HOMOSAPIEN_WELCOMED: "1"
      ANTHROPIC_AUTH_TOKEN: "ollama"
      ANTHROPIC_BASE_URL: "http://localhost:11434"
```

- [ ] **Step 2: Commit**

```bash
git add ~/Projects/Au-vault/ai/cli_agents.yaml
git commit -m "feat(config): add category and group fields to cli_agents.yaml"
```

---

### Task 2: Update /api/cli/configs to return category, group, and enabled state

**Files:**
- Modify: `apps/dashboard/app/api/cli/configs/route.ts`
- Modify: `apps/dashboard/app/api/cli/cli-config.ts` (add type, update CLI_ENTRIES)

- [ ] **Step 1: Add CliCategory type and update CLI_ENTRIES in cli-config.ts**

Add after line 15 in `cli-config.ts`:

```typescript
export type CliCategory = "remote" | "local" | "ide";
```

Update `CLI_ENTRIES` (line 78) to remove the hardcoded map — it's no longer needed since labels come from config. Replace with:

```typescript
/** Known CLI IDs for validation. Labels now come from cli_agents.yaml. */
export const KNOWN_CLI_IDS = new Set([
  "claude", "codex", "cursor-cli", "kimi", "gemini",
  "opencode", "claude-kimi", "copilot-cli",
]);
```

Update `isValidCli` (line 101) to use the new set:

```typescript
export function isValidCli(cliId: string): boolean {
  if (cliId.startsWith("agent-bubble-")) return true;
  return KNOWN_CLI_IDS.has(cliId);
}
```

- [ ] **Step 2: Update configs/route.ts to merge prefs and return category/group**

Replace the full `GET` handler in `configs/route.ts`:

```typescript
import { NextResponse } from "next/server";
import {
  getCliAgentsConfig,
  resolveCommand,
  type CliCategory,
} from "../cli-config";
import { callMCPTool, getMCPBridge } from "@/lib/mcp/MCPBridge";

export async function GET() {
  try {
    const agents = getCliAgentsConfig();

    // Load user preferences for enabled groups/variants
    let enabledGroups: string[] | null = null;
    let variantOverrides: Record<string, boolean> = {};
    try {
      const bridge = getMCPBridge();
      const prefResult = await callMCPTool("get-preferences", { key: "dispatch_targets" });
      const raw = bridge.constructor.extractText
        ? (bridge.constructor as any).extractText(prefResult)
        : JSON.stringify(prefResult);
      const prefs = JSON.parse(typeof raw === "string" ? raw : JSON.stringify(raw));
      const dt = prefs?.dispatch_targets ?? prefs;
      if (dt?.enabled_groups) enabledGroups = dt.enabled_groups;
      if (dt?.variant_overrides) variantOverrides = dt.variant_overrides;
    } catch {
      // Prefs unavailable — treat all as enabled (first-run default)
    }

    const configs = Object.entries(agents).map(([id, config]: [string, any]) => {
      const cmd = config.cmd?.[0];
      let available = false;
      if (cmd) {
        try {
          resolveCommand(cmd);
          available = true;
        } catch {
          available = false;
        }
      }

      const category: CliCategory = config.category || "remote";
      const group: string = config.group || id;

      // Enabled = group is in enabled list (or all enabled if no prefs yet)
      // AND variant is not explicitly disabled
      const groupEnabled = enabledGroups === null || enabledGroups.includes(group);
      const variantEnabled = variantOverrides[id] !== false;
      const enabled = groupEnabled && variantEnabled;

      return {
        cli_id: id,
        label: config.label || id,
        cmd: config.cmd,
        category,
        group,
        available,
        enabled,
      };
    });

    return NextResponse.json({
      configs,
      default_cli: "claude",
    });
  } catch (err: any) {
    return NextResponse.json(
      { error: err.message || "Failed to load CLI configs" },
      { status: 500 },
    );
  }
}
```

- [ ] **Step 3: Verify the API returns category/group/enabled**

```bash
curl -s http://localhost:3000/api/cli/configs | python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
for c in d['configs']:
    print(f\"{c['cli_id']:15} cat={c.get('category','?'):8} grp={c.get('group','?'):12} avail={c.get('available')} enabled={c.get('enabled')}\")
"
```

Expected: each entry shows category, group, available, and enabled fields.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/app/api/cli/cli-config.ts apps/dashboard/app/api/cli/configs/route.ts
git commit -m "feat(api): return category, group, enabled state from /api/cli/configs"
```

---

### Task 3: Update ActionDialogView with category-based styling

**Files:**
- Modify: `apps/dashboard/features/components/ActionDialogView.tsx`

- [ ] **Step 1: Update ActionTarget type to include category**

Replace the `ActionTarget` interface:

```typescript
export type TargetCategory = "remote" | "local" | "ide";

export interface ActionTarget {
  id: string;
  label: string;
  type: "ide" | "cli";
  category: TargetCategory;
}
```

- [ ] **Step 2: Add category style constants**

Add after the imports:

```typescript
const CATEGORY_STYLES: Record<TargetCategory, {
  gradient: string;
  badge: string;
  badgeText: string;
  label: string;
}> = {
  remote: {
    gradient: "bg-gradient-to-r from-purple-600 to-cyan-600 hover:from-purple-500 hover:to-cyan-500",
    badge: "bg-purple-500/20 text-purple-300 border-purple-500/30",
    badgeText: "REMOTE",
    label: "Send to",
  },
  local: {
    gradient: "bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500",
    badge: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
    badgeText: "LOCAL",
    label: "Send to",
  },
  ide: {
    gradient: "bg-[var(--bg-secondary)] hover:bg-[var(--bg-hover)] border border-[var(--border-color)]",
    badge: "bg-[var(--bg-hover)] text-[var(--text-muted)] border-[var(--border-color)]",
    badgeText: "IDE",
    label: "Copy for",
  },
};
```

- [ ] **Step 3: Update the target button rendering**

In the `targets.map()` section (around line 252), replace the button with category-aware rendering:

```typescript
{targets.length > 0 ? (
  <div className="space-y-1.5">
    {targets.map((target) => {
      const style = CATEGORY_STYLES[target.category];
      const isIde = target.category === "ide";
      return (
        <button
          key={target.id}
          onClick={() => isIde ? handleCopy() : handleSendToTarget(target.id)}
          disabled={isSending}
          className={`w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all disabled:opacity-80 disabled:cursor-not-allowed ${
            isIde
              ? `${style.gradient} text-[var(--text-primary)]`
              : `${style.gradient} text-white`
          }`}
        >
          {sendingTargetId === target.id ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : isIde ? (
            <Copy className="w-4 h-4" />
          ) : (
            <Terminal className="w-4 h-4" />
          )}
          <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded border ${style.badge}">
            {style.badgeText}
          </span>
          {style.label} {target.label}
        </button>
      );
    })}
  </div>
) : (
  <button
    onClick={handleCopy}
    disabled={isSending}
    className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-white bg-gradient-to-r from-purple-600 to-cyan-600 hover:from-purple-500 hover:to-cyan-500 transition-all disabled:opacity-80"
  >
    <Copy className="w-4 h-4" />
    Copy to Clipboard
  </button>
)}
```

- [ ] **Step 4: Remove the separate Copy button when targets exist (IDE buttons already copy)**

Remove the secondary "Copy to Clipboard" button that appears when targets exist — IDE category buttons already handle copying. Keep the "Dismiss" button.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/features/components/ActionDialogView.tsx
git commit -m "feat(ui): category-based dispatch buttons with remote/local/ide styling"
```

---

### Task 4: Update ChatViewPanels target detection to pass category

**Files:**
- Modify: `apps/dashboard/features/components/chat/ChatViewPanels.tsx`

- [ ] **Step 1: Update target detection to use category from CLI configs**

In the `useEffect` that builds targets (around line 86), update the CLI target building:

```typescript
// Add CLI configs with category
if (cliConfigData?.configs) {
  const ideLabels = new Set(targets.map((t) => t.label.toLowerCase()));
  for (const cfg of cliConfigData.configs) {
    if (!cfg.available || !cfg.enabled) continue;
    if (ideLabels.has(cfg.label.toLowerCase())) continue;

    targets.push({
      id: `cli:${cfg.cli_id}`,
      label: cfg.label || cfg.cli_id,
      type: cfg.category === "ide" ? "ide" : "cli",
      category: cfg.category || "remote",
    });
  }
}
```

- [ ] **Step 2: Update the useMcpQuery for CLI configs to include new fields**

Ensure the `select` transform for the CLI configs query returns `category`, `group`, `enabled` fields. Find the existing query and update its type.

- [ ] **Step 3: Remove the IDE detection from get-ide-status MCP tool**

Since all targets now come from `/api/cli/configs`, remove the `useMcpQuery("ide-detect", "get-ide-status", ...)` and the IDE target building block. CLI configs is now the single source of truth.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/features/components/chat/ChatViewPanels.tsx
git commit -m "feat(dispatch): use cli configs as single source for targets with category"
```

---

### Task 5: Category-aware dispatch in handleSendToTarget

**Files:**
- Modify: `apps/dashboard/features/components/chat/ChatViewPanels.tsx`

- [ ] **Step 1: Update handleSendToTarget to branch on category**

The current handler should check the target's category:

```typescript
const handleSendToTarget = useCallback(
  async (targetId: string, fullPrompt: string) => {
    const [_type, id] = targetId.split(":");

    // Find the target to get its category
    const target = ideTargets.find((t) => t.id === targetId);
    const category = target?.category || "remote";

    // IDE targets: copy to clipboard, never auto-send
    if (category === "ide") {
      navigator.clipboard.writeText(fullPrompt);
      setChatView("terminal");
      setEmbeddedAction(null);
      return;
    }

    // Remote/Local CLI targets: send via embedded PTY
    const cliId = id as CliId;
    const adaptedPrompt = adaptPrompt(fullPrompt, {
      target: resolveDispatchTarget(targetId),
    });

    if (isRunning && cliProcess && cliProcess.status === "running") {
      sendMessage(adaptedPrompt);
      setChatView("terminal");
      setEmbeddedAction(null);
      return;
    }

    // Start CLI and send after init
    try {
      await startCli(cliId);
    } catch {
      // CLI might already be starting
    }
    await new Promise((r) => setTimeout(r, 4000));
    await fetch("/api/cli", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "send", cliId, input: adaptedPrompt }),
    });

    setChatView("terminal");
    setEmbeddedAction(null);
  },
  [isRunning, cliProcess, startCli, sendMessage, setChatView, setEmbeddedAction, ideTargets],
);
```

- [ ] **Step 2: Commit**

```bash
git add apps/dashboard/features/components/chat/ChatViewPanels.tsx
git commit -m "feat(dispatch): category-aware send — PTY for remote/local, clipboard for ide"
```

---

### Task 6: Add dispatch_targets to user preferences

**Files:**
- Modify: `src/mcp/augur_mcp/core/preferences.py`

- [ ] **Step 1: Add default dispatch_targets to preferences initialization**

In `_load_preferences()`, ensure `dispatch_targets` has a sensible default when missing:

```python
def _load_preferences() -> dict:
    prefs = _read_yaml()
    # Ensure dispatch_targets has defaults
    if "dispatch_targets" not in prefs:
        prefs["dispatch_targets"] = {
            "enabled_groups": None,  # None = all enabled (first-run)
            "variant_overrides": {},
        }
    return prefs
```

- [ ] **Step 2: Commit**

```bash
git add src/mcp/augur_mcp/core/preferences.py
git commit -m "feat(prefs): add dispatch_targets defaults for group/variant management"
```

---

### Task 7: Disable cascade — sync_agents respects enabled groups

**Files:**
- Modify: `skills/ai/scripts/sync_agents/constants.py`
- Modify: `skills/ai/scripts/sync_agents/adapters/__init__.py` or individual adapters

- [ ] **Step 1: Add enabled_groups check to sync_agents main flow**

In the sync_agents entry point, before running adapters, load preferences and filter out disabled groups:

```python
def _load_enabled_groups() -> set[str] | None:
    """Load enabled dispatch groups from user preferences. None = all enabled."""
    try:
        prefs_path = Path(get_vault_dir()) / ".augur" / "config" / "preferences.yaml"
        if not prefs_path.exists():
            return None
        import yaml
        with open(prefs_path) as f:
            prefs = yaml.safe_load(f) or {}
        dt = prefs.get("dispatch_targets", {})
        groups = dt.get("enabled_groups")
        return set(groups) if groups is not None else None
    except Exception:
        return None
```

- [ ] **Step 2: Map adapters to groups and skip disabled ones**

Add a mapping from adapter class to group name:

```python
ADAPTER_GROUPS = {
    "ClaudeCodeAdapter": "claude",
    "CodexAdapter": "codex",
    "CursorAdapter": "cursor",
    "GeminiAdapter": "gemini",
    "KimiAdapter": "kimi",
    "OpenCodeAdapter": "opencode",
    "CopilotAdapter": "copilot",
    "WindsurfAdapter": "windsurf",
    "ClineAdapter": "cline",
}
```

In the adapter loop, skip disabled groups and clean up their output directories:

```python
enabled_groups = _load_enabled_groups()
for adapter_cls in ADAPTERS:
    group = ADAPTER_GROUPS.get(adapter_cls.__name__)
    if enabled_groups is not None and group and group not in enabled_groups:
        # Group disabled — clean up synced files
        adapter = adapter_cls()
        if hasattr(adapter, 'output_dir') and adapter.output_dir.exists():
            clean_directory(adapter.output_dir)
        continue
    # Normal sync
    adapter_cls().sync()
```

- [ ] **Step 3: Commit**

```bash
git add skills/ai/scripts/sync_agents/
git commit -m "feat(sync): skip disabled groups and clean up their synced files"
```

---

### Task 8: Integration with Browse page for group/variant toggles

**Files:**
- This task creates the UI for managing enabled groups and variant overrides on the Browse > Integrations page. The exact page file depends on the existing Browse infrastructure.

- [ ] **Step 1: Identify the integrations page location**

Check `apps/dashboard/features/pages/browse/` or `apps/dashboard/app/browse/` for existing integration management UI.

- [ ] **Step 2: Add a "Dispatch Targets" section to the integrations page**

The section should:
1. Load CLI configs from `/api/cli/configs` (includes available, enabled, category, group)
2. Group entries by `group`
3. For each group: show a toggle switch (enabled/disabled)
4. When enabled: show variant checkboxes for entries within the group
5. On toggle: call `update-preference` MCP tool to update `dispatch_targets.enabled_groups` and `dispatch_targets.variant_overrides`

- [ ] **Step 3: Wire the toggle to update-preference MCP tool**

```typescript
async function toggleGroup(group: string, enabled: boolean) {
  const prefs = await mcpCall("get-preferences", { key: "dispatch_targets" });
  const dt = prefs?.dispatch_targets || { enabled_groups: null, variant_overrides: {} };

  let groups = dt.enabled_groups;
  if (groups === null) {
    // First toggle — initialize with all currently enabled groups
    groups = allGroups.filter(g => g !== group || enabled);
  } else if (enabled) {
    groups = [...new Set([...groups, group])];
  } else {
    groups = groups.filter((g: string) => g !== group);
  }

  await mcpCall("update-preference", {
    key: "dispatch_targets",
    value: { ...dt, enabled_groups: groups },
  });
}
```

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/features/pages/browse/
git commit -m "feat(browse): add dispatch target group/variant management UI"
```

---

## Execution Order

Tasks 1-5 form the core flow and should be done sequentially.
Tasks 6-7 add the preference persistence and sync cascade.
Task 8 adds the management UI and can be done last.
