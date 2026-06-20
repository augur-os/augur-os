# Architecture Review Phases 1-3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the 3 independent quick/medium phases from the architecture review design spec — vault elimination, remote execution wiring, plugin tool loading fix, and RAG pipeline unification.

**Architecture:** Four independent workstreams touching Python MCP server, TypeScript dashboard, sync_agents pipeline, and RAG indexing. No shared state between phases — safe to parallelize.

**Tech Stack:** Python 3.11+, TypeScript/Next.js 16, FastMCP, TanStack Query, Zustand

**Spec:** `docs/superpowers/specs/2026-03-20-arch-review-remaining-items-design.md`

**Scope note:** Phases 4-5 (discovery consolidation, agent tiers) are larger refactors that each need their own plan. This plan covers Phases 1-3 only.

---

## File Map

### Phase 1a: Vault Elimination (Item 4)
| Action | File |
|--------|------|
| Modify | `.claude/skills/ai_bridge/scripts/sync_agents/constants.py` |
| Modify | `.claude/skills/ai_bridge/scripts/sync_agents/engine.py` |
| Modify | `.claude/skills/ai_bridge/SKILL.md` |
| Modify | `CLAUDE.md` (auto-gen header) |
| Move | `get_vault_dir()/ai_bridge/agent-rules.md` → `docs/agent-topics/agent-rules.md` |

### Phase 1b: Wire Remote Execution (Item 5)
| Action | File |
|--------|------|
| Modify | `apps/dashboard/hooks/useActionRunner.ts` |
| Modify | `apps/dashboard/lib/stores/chatStore.ts` |
| Modify | `apps/dashboard/app/settings/page.tsx` or equivalent settings layout |
| Modify | `CLAUDE.md` (Rule #10 amendment) |

### Phase 2: Plugin Tool Loading Fix (Item 6)
| Action | File |
|--------|------|
| Modify | `src/mcp/augur_mcp/plugin_tools.py` |
| Modify | `src/mcp/augur_mcp/client_surface.py` |
| Modify | `src/mcp/augur_mcp/server.py` |
| Modify | `src/mcp/augur_mcp/domain/plugins.py` (add `get-plugin-load-status` tool) |
| Create | `apps/dashboard/lib/mcp/plugin-tool-sources.ts` |
| Modify | `apps/dashboard/lib/mcp/createAPIRoute.ts` |
| Create | `apps/dashboard/components/ui/PluginRequiredBanner.tsx` |
| Create | `apps/dashboard/components/ui/ToolErrorBanner.tsx` |
| Modify | 8 consumer page components (integrate banners) |

### Phase 3: RAG Pipeline Unification (Item 3)
| Action | File |
|--------|------|
| Modify | `.claude/skills/rag/scripts/unified_indexer.py` |
| Modify | `.claude/skills/ai_bridge/scripts/ops/rag_reindex.py` |
| Modify | `.claude/skills/knowledge/scripts/mcp/rag_search.py` |
| Delete | `.claude/skills/rag/scripts/rag_indexer.py` |

---

## Phase 1a: Vault Elimination

### Task 1: Copy agent-rules.md from vault to repo

**Files:**
- Copy: `get_vault_dir()/ai_bridge/agent-rules.md` → `docs/agent-topics/agent-rules.md`

Note: Vault deletion happens AFTER code changes (Task 4b) to avoid broken state if intermediate tasks fail.

- [ ] **Step 1: Check if agent-rules.md exists in vault**

```bash
ls -la get_vault_dir()/ai_bridge/agent-rules.md
```

- [ ] **Step 2: Check if docs/agent-topics/ already has agent-rules.md**

```bash
ls -la docs/agent-topics/agent-rules.md 2>/dev/null || echo "not present"
```

- [ ] **Step 3: Copy vault file to repo (preserve content)**

```bash
cp get_vault_dir()/ai_bridge/agent-rules.md docs/agent-topics/agent-rules.md
```

If `docs/agent-topics/agent-rules.md` already exists, diff the two and keep the more complete version.

- [ ] **Step 4: Commit**

```bash
git add docs/agent-topics/agent-rules.md
git commit -m "chore: copy agent-rules.md from vault to repo (single source)"
```

---

### Task 2: Update sync_agents constants to read from repo

**Files:**
- Modify: `.claude/skills/ai_bridge/scripts/sync_agents/constants.py:90-129`

- [ ] **Step 1: Read the file**

Read `constants.py` fully to understand `_discover_source_paths()` (lines 90-117) and the module-level constants (lines 122-129).

- [ ] **Step 2: Rewrite `_discover_source_paths()`**

Replace the vault-based path resolution with direct repo paths:

```python
def _discover_source_paths() -> dict[str, Path]:
    """Resolve source paths for agent rules and topics.

    Canonical source is docs/agent-topics/ in the repo.
    No vault dependency.
    """
    root = _get_project_root()
    topics_dir = root / "docs" / "agent-topics"

    return {
        "rules": topics_dir / "agent-rules.md",
        "workflows": topics_dir,  # workflow docs live alongside topics
        "skills": topics_dir,
        "topics": topics_dir,
    }
```

- [ ] **Step 3: Remove `_AI_BRIDGE_VAULT` usage**

Remove or comment out the `_AI_BRIDGE_VAULT = get_skill_vault_dir("ai_bridge")` line if it's only used by `_discover_source_paths()`. Check for other callers first.

- [ ] **Step 4: Verify imports still work**

```bash
cd ~/Projects/Augur && python -c "from sync_agents.constants import SOURCE_RULES; print(SOURCE_RULES)"
```

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/ai_bridge/scripts/sync_agents/constants.py
git commit -m "fix(sync-agents): read agent rules from repo, not vault"
```

---

### Task 3: Update sync_agents engine to remove vault dependency

**Files:**
- Modify: `.claude/skills/ai_bridge/scripts/sync_agents/engine.py:851-925`

- [ ] **Step 1: Read engine.py sync_all() function**

Read lines 851-930 to understand the vault read step and 1000-byte guard.

- [ ] **Step 2: Remove 1000-byte guard from sync_all()**

At lines 894-908, remove the `_MIN_SOURCE_BYTES` check and `_REQUIRED_SECTIONS` validation. The repo file is version-controlled — truncation is caught by git, not byte-count guards.

- [ ] **Step 3: Remove all `sync_topic_docs_shared()` calls**

This function is called at THREE locations: lines 362 (definition), 611 (in `fix_mode()`), and 925 (in `sync_all()`). Remove all three call sites and delete the function definition at line 362-384.

- [ ] **Step 4: Update fix_mode() guard**

At line 595, `fix_mode()` has a diverged copy of the 1000-byte guard. Remove it too.

- [ ] **Step 5: Remove `sync_vaults()` call for agent topics only**

At line 932, `sync_vaults()` handles both agent topics AND other vault adapters (ADR-436). Only remove the agent-topics portion. If `sync_vaults()` does multiple things, surgically remove the topic docs branch, not the entire call.

- [ ] **Step 5b: Clean up `_AI_BRIDGE_VAULT` references**

`_AI_BRIDGE_VAULT` is used in `constants.py` at line 108 and in `_display_path()` at line 79. After `_discover_source_paths()` no longer uses it:
- If `_display_path()` still needs vault paths for other display purposes, keep it
- If `_AI_BRIDGE_VAULT` has no remaining callers, remove the import and variable

- [ ] **Step 6: Verify sync_all still runs**

```bash
cd ~/Projects/Augur && python -m skills.ai.scripts.sync_agents sync all 2>&1 | head -20
```

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/ai_bridge/scripts/sync_agents/engine.py
git commit -m "fix(sync-agents): remove vault dependency from engine"
```

---

### Task 4: Update SKILL.md and CLAUDE.md headers

**Files:**
- Modify: `.claude/skills/ai_bridge/SKILL.md:148-153`
- Modify: `CLAUDE.md:1-5`

- [ ] **Step 1: Read ai_bridge SKILL.md frontmatter**

Read lines 144-155 to find `agent_sources` block.

- [ ] **Step 2: Update agent_sources paths**

Change `agent_sources` values to be relative to project root `docs/agent-topics/`:

```yaml
agent_sources:
  rules: docs/agent-topics/agent-rules.md
  topics: docs/agent-topics
```

Or remove the `agent_sources` block entirely if `constants.py` no longer reads it (check after Task 2).

- [ ] **Step 3: Update CLAUDE.md auto-gen header**

Replace lines 1-5:

```html
<!--
AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
Source: docs/agent-topics/agent-rules.md
Generator: .claude/skills/ai_bridge/scripts/sync_agents
-->
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/ai_bridge/SKILL.md CLAUDE.md
git commit -m "chore: update source paths in SKILL.md and CLAUDE.md header"
```

---

### Task 4b: Delete vault copies (after all code changes)

**Files:**
- Delete: `get_vault_dir()/ai_bridge/agent-rules.md`
- Delete: `get_vault_dir()/ai_bridge/agent-topics/`

This runs LAST in Phase 1a, after code changes are committed and verified.

- [ ] **Step 1: Verify sync_agents works with repo source**

```bash
python -m skills.ai.scripts.sync_agents sync all
```

Must succeed without vault dependency.

- [ ] **Step 2: Delete vault copies (interactive — confirm with user)**

Ask the user for confirmation before deleting:

```bash
echo "About to delete vault copies (repo is now canonical source):"
echo "  get_vault_dir()/ai_bridge/agent-rules.md"
echo "  get_vault_dir()/ai_bridge/agent-topics/"
echo "Proceed? (y/n)"
```

```bash
rm get_vault_dir()/ai_bridge/agent-rules.md
rm -rf get_vault_dir()/ai_bridge/agent-topics/
```

---

## Phase 1b: Wire Remote Execution

### Task 5: Add `api` dispatch case to useActionRunner

**Files:**
- Modify: `apps/dashboard/hooks/useActionRunner.ts:482-505`

- [ ] **Step 1: Read useActionRunner.ts**

Read the full file to understand existing dispatch cases, imports, and helper functions (`runFire`, `runOneshot`, `runChat`, `runIde`).

- [ ] **Step 2: Write `runApi()` function**

Add before the `useActionRunner` function (peer to `runFire`, `runOneshot`, etc.). Note: use `ActionDef` type (line 13), not `ActionConfig`:

```typescript
async function runApi(
  action: ActionDef,
  context: PageContext,
  onResult?: (result: string) => void
): Promise<void> {
  const { resolveContext } = await import("@/lib/chat/context-envelope");
  const envelope = await resolveContext(context, "standard");

  const settingsRes = await fetch("/api/settings/execution-mode");
  const settings = await settingsRes.json();

  if (!settings.provider || !settings.apiKey) {
    toast.error("No API provider configured. Go to Settings to set up API execution.");
    return;
  }

  const prompt = action.prompt || `Execute action: ${action.label}`;

  const res = await fetch("/api/llm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      provider: settings.provider,
      model: settings.model || "default",
      messages: [
        { role: "system", content: envelope.system || "" },
        { role: "user", content: prompt },
      ],
      max_tokens: 4096,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "API call failed" }));
    toast.error(err.error || "API execution failed");
    return;
  }

  const data = await res.json();
  const result = data.content?.[0]?.text || data.text || JSON.stringify(data);

  if (onResult) {
    onResult(result);
  } else {
    toast.success("Action completed via API");
  }
}
```

- [ ] **Step 3: Add `case "api"` to dispatch switch**

After the `modal` case (line 504), add:

```typescript
case "api":
  await runApi(action, pageContext);
  break;
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd apps/dashboard && npx tsc --noEmit hooks/useActionRunner.ts 2>&1 | head -20
```

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/hooks/useActionRunner.ts
git commit -m "feat(dashboard): add api dispatch mode to useActionRunner"
```

---

### Task 6: Mount ExecutionModeToggle in settings

**Files:**
- Modify: Settings page (find via `grep -r "ExecutionMode" apps/dashboard/app/settings/`)

- [ ] **Step 1: Find the settings page that should host the toggle**

```bash
# Find settings pages
ls apps/dashboard/app/settings/
# Check if there's already an execution or general settings page
grep -r "execution" apps/dashboard/app/settings/ --include="*.tsx" -l
```

- [ ] **Step 2: Read ExecutionModeToggle.tsx**

Read `apps/dashboard/components/ExecutionModeToggle.tsx` to understand its props interface.

- [ ] **Step 3: Import and mount the toggle**

In the appropriate settings page, add:

```tsx
import { ExecutionModeToggle } from "@/components/ExecutionModeToggle";
// ... inside the page component:
<ExecutionModeToggle
  mode={executionMode}
  onChange={setExecutionMode}
  hasApiProviders={hasApiProviders}
/>
```

The `executionMode` state should be read from and written to settings via `useCachedFetch`/`useCachedMutation` calling the `set-config`/`get-settings` MCP tools.

- [ ] **Step 4: Mount ProviderConfigModal**

Import and add `ProviderConfigModal` from `@/components/remote/ProviderConfigModal` to the same settings page, gated on `executionMode === "api"` or always visible with a "Configure API Providers" button.

- [ ] **Step 5: Verify page renders**

Check the settings page loads without errors in the browser.

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/app/settings/
git commit -m "feat(dashboard): mount ExecutionModeToggle and ProviderConfigModal in settings"
```

---

### Task 7: Amend CLAUDE.md Rule #10

**Files:**
- Modify: `CLAUDE.md:41`

- [ ] **Step 1: Read current Rule #10**

Read CLAUDE.md line 41 (Rule #10).

- [ ] **Step 2: Amend rule text**

Replace the current Rule #10 text with:

> "No direct LLM calls from dashboard — Dashboard NEVER calls LLM APIs directly **except through the registered LLM proxy route** (`/api/llm`) **when the user has explicitly configured API execution mode** (ADR-020). All other AI execution happens in IDE/CLI agents via `useActionRunner` with `dispatch: 'ide'`. No `import anthropic`, no embedded prompt execution."

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: amend Rule #10 to allow LLM proxy route per ADR-020"
```

---

### Task 7b: Connect chatStore remote mode to API dispatch

**Files:**
- Modify: `apps/dashboard/lib/stores/chatStore.ts`

- [ ] **Step 1: Read chatStore.ts**

Read the file. Find `ChatMode` type and `openChat()` function. The store already has `"remote"` as a valid `ChatMode`.

- [ ] **Step 2: Wire remote mode to API execution**

When `chatMode === "remote"`, the chat should route messages through `/api/llm` instead of the IDE bridge. In the store's message-sending logic, add a branch:

```typescript
if (chatMode === "remote") {
  const res = await fetch("/api/llm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, model, messages, max_tokens: 4096 }),
  });
  // Handle response...
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/lib/stores/chatStore.ts
git commit -m "feat(dashboard): connect chatStore remote mode to /api/llm"
```

---

### Task 7c: Implement auto-mode dispatch logic

**Files:**
- Modify: `apps/dashboard/hooks/useActionRunner.ts`

- [ ] **Step 1: Add auto-mode resolution**

Add a helper function that resolves `"auto"` dispatch to either `"ide"` or `"api"`:

```typescript
async function resolveAutoMode(): Promise<"ide" | "api" | "chat"> {
  try {
    const ideRes = await fetch("/api/ide/detect");
    const ideData = await ideRes.json();
    if (ideData.count > 0) return "ide";
  } catch { /* IDE detection failed */ }

  try {
    const settingsRes = await fetch("/api/settings/execution-mode");
    const settings = await settingsRes.json();
    if (settings.provider && settings.apiKey) return "api";
  } catch { /* Settings fetch failed */ }

  return "chat";  // fallback to chat dialog
}
```

- [ ] **Step 2: Add `case "auto"` to dispatch switch**

```typescript
case "auto": {
  const resolved = await resolveAutoMode();
  // Re-dispatch with resolved mode
  await runAction({ ...action, dispatch: resolved });
  break;
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/hooks/useActionRunner.ts
git commit -m "feat(dashboard): add auto-mode dispatch resolution (IDE → API → chat)"
```

---

## Phase 2: Plugin Tool Loading Fix

### Task 8: Add error tracking to plugin_tools.py

**Files:**
- Modify: `src/mcp/augur_mcp/plugin_tools.py:109-212`

- [ ] **Step 1: Read plugin_tools.py**

Read the full file, focusing on `register_plugin_tools()` (line 109) and the error handling at lines 208-212.

- [ ] **Step 2: Add `_failed_plugins` registry**

At module level (near top of file):

```python
_failed_plugins: dict[str, str] = {}  # skill_name -> error message

def get_failed_plugins() -> dict[str, str]:
    """Return plugins that failed to load."""
    return dict(_failed_plugins)
```

- [ ] **Step 3: Promote error logging from DEBUG to WARNING**

In the `except` block at lines 208-212, change:

```python
except Exception as e:
    _failed_plugins[skill_name] = str(e)
    logger.warning("Failed to load plugin tools from %s: %s", skill_name, e)
```

- [ ] **Step 4: Commit**

```bash
git add src/mcp/augur_mcp/plugin_tools.py
git commit -m "fix(mcp): track and warn on plugin tool load failures"
```

---

### Task 9: Add PLUGIN_TOOL_SOURCES and startup validation to server

**Files:**
- Modify: `src/mcp/augur_mcp/client_surface.py`
- Modify: `src/mcp/augur_mcp/server.py:544-545`

- [ ] **Step 1: Read client_surface.py**

Read the full file to find `CURATED_VISIBLE_TOOLS`.

- [ ] **Step 2: Add PLUGIN_TOOL_SOURCES mapping**

After `CURATED_VISIBLE_TOOLS`, add:

```python
PLUGIN_TOOL_SOURCES: dict[str, str] = {
    "get-attention-items": "attention",
    "get-attention-summary": "attention",
    "get-agent-telemetry": "advisor",
    "get-agent-weights": "advisor",
    "update-agent-weights": "advisor",
    "get-skill-health": "advisor",
    "verify-changes": "advisor",
    "get-daemon-status": "daemon",
    "insights-pending": "daemon",
    "plugin-events-list": "daemon",
    "plugin-events-acknowledge": "daemon",
    "scan-file-organizer": "organizer",
    "get-context-files": "file-manager",
    "manage-cli-agents": "ai_bridge",
    "manage-tools-catalog": "ai_bridge",
    "run-adaptive-growth": "devops",
    "generate-ide-instructions": "mcp-app-factory",
    "validate-agent-wizard": "mcp-app-factory",
    "unified-search": "knowledge",
    "knowledge-project-index-rebuild": "knowledge",
    "knowledge-summarize-url": "knowledge",
    "knowledge-summarize-file": "knowledge",
    "start-rag-indexing": "knowledge",
    "search-skill-knowledge": "rag",
    "check-system-permissions": "system-cleanup",
}
```

- [ ] **Step 3: Add startup validation to server.py**

After tool registration completes in `main()` (around line 545), add:

```python
# Validate curated tools are registered
from .client_surface import CURATED_VISIBLE_TOOLS, PLUGIN_TOOL_SOURCES
from .plugin_tools import get_failed_plugins

registered = set(mcp._tool_manager._tools.keys()) if hasattr(mcp, '_tool_manager') else set(mcp._tools.keys())
missing_curated = CURATED_VISIBLE_TOOLS - registered
for tool_name in sorted(missing_curated):
    source = PLUGIN_TOOL_SOURCES.get(tool_name, "unknown")
    logger.warning("Curated tool '%s' not registered (plugin: %s)", tool_name, source)

failed = get_failed_plugins()
if failed:
    logger.warning("Plugin load failures: %s", ", ".join(f"{k}: {v}" for k, v in failed.items()))
    total_tools = len(registered)
    logger.info("Loaded %d tools total. %d plugins failed.", total_tools, len(failed))
```

- [ ] **Step 4: Emit heal_event on plugin failures**

After the failed plugins check, if any failed:

```python
if failed:
    from .infrastructure.settings import emit_heal_event
    emit_heal_event("plugin_load_failure", {
        "failed_plugins": failed,
        "count": len(failed),
    })
```

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_mcp/client_surface.py src/mcp/augur_mcp/server.py
git commit -m "feat(mcp): add plugin tool source mapping, startup validation, heal events"
```

---

### Task 9b: Add `get-plugin-load-status` MCP tool

**Files:**
- Modify: `src/mcp/augur_mcp/domain/plugins.py`

- [ ] **Step 1: Read plugins.py**

Read `domain/plugins.py` to find where to add the new tool (near `plugin-health`).

- [ ] **Step 2: Add the tool**

```python
@mcp.tool(name="get-plugin-load-status", annotations={"readOnlyHint": True})
async def get_plugin_load_status_tool() -> str:
    """Return which plugin skills failed to load MCP tools and why."""
    from ..plugin_tools import get_failed_plugins
    failed = get_failed_plugins()
    return json.dumps({
        "failed_plugins": failed,
        "total_failed": len(failed),
        "status": "healthy" if not failed else "degraded",
    })
```

- [ ] **Step 3: Commit**

```bash
git add src/mcp/augur_mcp/domain/plugins.py
git commit -m "feat(mcp): add get-plugin-load-status tool for diagnostics"
```

---

### Task 10: Add fallback metadata to createAPIRoute

**Files:**
- Create: `apps/dashboard/lib/mcp/plugin-tool-sources.ts`
- Modify: `apps/dashboard/lib/mcp/createAPIRoute.ts:74-98,223-232`

- [ ] **Step 1: Create TypeScript PLUGIN_TOOL_SOURCES**

```typescript
// apps/dashboard/lib/mcp/plugin-tool-sources.ts
// Interim constant — will be replaced by skill-manifest.json read in Phase 4
export const PLUGIN_TOOL_SOURCES: Record<string, string> = {
  "get-attention-items": "attention",
  "get-attention-summary": "attention",
  "get-agent-telemetry": "advisor",
  "get-agent-weights": "advisor",
  "update-agent-weights": "advisor",
  "get-skill-health": "advisor",
  "verify-changes": "advisor",
  "get-daemon-status": "daemon",
  "insights-pending": "daemon",
  "plugin-events-list": "daemon",
  "plugin-events-acknowledge": "daemon",
  "scan-file-organizer": "organizer",
  "get-context-files": "file-manager",
  "manage-cli-agents": "ai_bridge",
  "manage-tools-catalog": "ai_bridge",
  "run-adaptive-growth": "devops",
  "generate-ide-instructions": "mcp-app-factory",
  "validate-agent-wizard": "mcp-app-factory",
  "unified-search": "knowledge",
  "knowledge-project-index-rebuild": "knowledge",
  "knowledge-summarize-url": "knowledge",
  "knowledge-summarize-file": "knowledge",
  "start-rag-indexing": "knowledge",
  "search-skill-knowledge": "rag",
  "check-system-permissions": "system-cleanup",
};
```

- [ ] **Step 2: Read createAPIRoute.ts**

Read lines 62-98 and 223-232 to understand all three fallback injection points.

- [ ] **Step 3: Add `_fallback` metadata to all three fallback paths**

Import the mapping:
```typescript
import { PLUGIN_TOOL_SOURCES } from "./plugin-tool-sources";
```

At each `gracefulFallback` return point, distinguish between tool errors and missing plugins. The `MCPBridge` can check tool existence:

```typescript
import { PLUGIN_TOOL_SOURCES } from "./plugin-tool-sources";

// In the error handler, determine reason:
const bridge = getMCPBridge();
const toolRegistered = bridge ? await bridge.toolExists(toolName).catch(() => false) : false;

return NextResponse.json({
  ...gracefulFallback.data,
  _fallback: true,
  _reason: toolRegistered ? "tool_error" : "plugin_not_installed",
  _plugin: PLUGIN_TOOL_SOURCES[toolName] || null,
  _error: toolRegistered ? errorMessage : undefined,
});
```

If `MCPBridge.toolExists()` doesn't exist yet, add a lightweight method that checks the tool list without making a full call. Alternatively, use the `PLUGIN_TOOL_SOURCES` mapping — if the tool is in the mapping, it's plugin-provided and the failure likely means the plugin isn't loaded.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/lib/mcp/plugin-tool-sources.ts apps/dashboard/lib/mcp/createAPIRoute.ts
git commit -m "feat(dashboard): inject _fallback metadata in gracefulFallback responses"
```

---

### Task 11: Create PluginRequiredBanner and ToolErrorBanner

**Files:**
- Create: `apps/dashboard/components/ui/PluginRequiredBanner.tsx`
- Create: `apps/dashboard/components/ui/ToolErrorBanner.tsx`

- [ ] **Step 1: Create PluginRequiredBanner**

```tsx
// apps/dashboard/components/ui/PluginRequiredBanner.tsx
import Link from "next/link";

interface PluginRequiredBannerProps {
  plugin: string | null;
}

export function PluginRequiredBanner({ plugin }: PluginRequiredBannerProps) {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30 p-4 text-sm text-amber-800 dark:text-amber-200">
      <p>
        This feature requires the <strong>{plugin || "unknown"}</strong> plugin.{" "}
        <Link href="/settings/skills" className="underline hover:no-underline">
          Install via Settings
        </Link>
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Create ToolErrorBanner**

```tsx
// apps/dashboard/components/ui/ToolErrorBanner.tsx
interface ToolErrorBannerProps {
  error: string;
  plugin?: string | null;
}

export function ToolErrorBanner({ error, plugin }: ToolErrorBannerProps) {
  if (process.env.NODE_ENV === "production") return null;

  return (
    <div className="rounded-lg border border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/30 p-4 text-sm text-red-800 dark:text-red-200">
      <p className="font-medium">Tool error{plugin ? ` (${plugin})` : ""}</p>
      <p className="mt-1 font-mono text-xs">{error}</p>
    </div>
  );
}
```

- [ ] **Step 3: Create shared fallback check utility**

```typescript
// Add to apps/dashboard/lib/mcp/plugin-tool-sources.ts
export function isFallbackResponse(data: unknown): data is { _fallback: true; _reason: string; _plugin: string | null; _error?: string } {
  return typeof data === "object" && data !== null && "_fallback" in data && (data as Record<string, unknown>)._fallback === true;
}
```

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/components/ui/PluginRequiredBanner.tsx apps/dashboard/components/ui/ToolErrorBanner.tsx apps/dashboard/lib/mcp/plugin-tool-sources.ts
git commit -m "feat(dashboard): add PluginRequiredBanner and ToolErrorBanner components"
```

---

### Task 11b: Integrate banners into 8 consumer pages

**Files:**
- Modify: 8 page components that use plugin-provided routes with `gracefulFallback`

- [ ] **Step 1: Identify the 8 consumer pages**

```bash
# Find pages that fetch from these routes:
grep -r "agents/telemetry\|agents/weights\|agents/wizard/validate\|file-organizer/scan\|insights/pending\|plugin-events\|rag/rebuild-master-index" apps/dashboard/app/ --include="*.tsx" -l
```

- [ ] **Step 2: For each consumer page, add fallback check**

Import the utilities and banners:

```tsx
import { isFallbackResponse } from "@/lib/mcp/plugin-tool-sources";
import { PluginRequiredBanner } from "@/components/ui/PluginRequiredBanner";
import { ToolErrorBanner } from "@/components/ui/ToolErrorBanner";
```

In the component's render, before the normal data display:

```tsx
if (isFallbackResponse(data)) {
  if (data._reason === "plugin_not_installed") {
    return <PluginRequiredBanner plugin={data._plugin} />;
  }
  return <ToolErrorBanner error={data._error || "Unknown error"} plugin={data._plugin} />;
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/app/
git commit -m "feat(dashboard): show plugin banners instead of empty data for 8 routes"
```

---

## Phase 3: RAG Pipeline Unification

### Task 12: Add chunking to unified_indexer.py

**Files:**
- Modify: `.claude/skills/rag/scripts/unified_indexer.py:180-191`
- Reference: `.claude/skills/rag/scripts/rag_indexer.py:89-123`

- [ ] **Step 1: Read rag_indexer.py chunk logic**

Read lines 89-123 of `rag_indexer.py` to understand `chunk_markdown()`.

- [ ] **Step 2: Read unified_indexer.py reindex_all()**

Read lines 94-191 to understand the current pipeline and where to insert chunking.

- [ ] **Step 3: Add `_chunk_skills()` function to unified_indexer.py**

After `reindex_all()`, add a chunking post-processor:

```python
def _chunk_skills(rag_dir: Path, root: Path) -> int:
    """Split large SKILL.md files into heading-based chunks."""
    chunks_dir = rag_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for skill_dir in (root / ".claude" / "skills").iterdir():
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        content = skill_md.read_text(errors="replace")
        if len(content) < 2000:
            continue

        # Read hub from frontmatter for directory organization
        hub = "uncategorized"
        if content.startswith("---"):
            try:
                _, fm, _ = content.split("---", 2)
                import yaml
                data = yaml.safe_load(fm)
                hub = (data or {}).get("x-augur-hub", "uncategorized")
            except Exception:
                pass

        out_dir = chunks_dir / hub / skill_dir.name
        out_dir.mkdir(parents=True, exist_ok=True)

        # Split on headings
        lines = content.split("\n")
        current_heading = "preamble"
        current_chunk: list[str] = []

        for line in lines:
            if line.startswith("#"):
                # Flush previous chunk
                if current_chunk:
                    text = "\n".join(current_chunk).strip()
                    if len(text) >= 50:
                        safe_name = current_heading.replace("/", "-").replace(" ", "-")[:60]
                        chunk_path = out_dir / f"{safe_name}.md"
                        chunk_path.write_text(
                            f"---\nsource: {skill_dir.name}\nheading: {current_heading}\n---\n\n{text}\n"
                        )
                        count += 1
                current_heading = line.lstrip("#").strip()
                current_chunk = [line]
            else:
                current_chunk.append(line)

        # Flush last chunk
        if current_chunk:
            text = "\n".join(current_chunk).strip()
            if len(text) >= 50:
                safe_name = current_heading.replace("/", "-").replace(" ", "-")[:60]
                chunk_path = out_dir / f"{safe_name}.md"
                chunk_path.write_text(
                    f"---\nsource: {skill_dir.name}\nheading: {current_heading}\n---\n\n{text}\n"
                )
                count += 1

    return count
```

- [ ] **Step 4: Call `_chunk_skills()` from `reindex_all()`**

After the scanner loop (around line 165), before manifest write:

```python
chunk_count = _chunk_skills(rag_dir, root)
stats["chunks"] = chunk_count
```

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/rag/scripts/unified_indexer.py
git commit -m "feat(rag): add heading-based chunking to unified indexer"
```

---

### Task 13: Populate manifest.entries

**Files:**
- Modify: `.claude/skills/rag/scripts/unified_indexer.py:180-191`

- [ ] **Step 1: Collect all pointer files into entries list**

After all scanners run and before manifest write, add:

```python
# Collect entries from all category pointer files
entries = []
for category_dir in sorted(rag_dir.iterdir()):
    if category_dir.name.startswith("_") or not category_dir.is_dir():
        continue
    if category_dir.name in ("chunks", "cache", "projects"):
        continue
    for entry_file in sorted(category_dir.rglob("*.md")):
        try:
            text = entry_file.read_text(errors="replace")
            fm_data = {}
            if text.startswith("---"):
                _, fm_raw, _ = text.split("---", 2)
                fm_data = yaml.safe_load(fm_raw) or {}
            entries.append({
                "name": fm_data.get("name", entry_file.stem),
                "category": category_dir.name,
                "hub": fm_data.get("hub", ""),
                "path": str(entry_file.relative_to(rag_dir)),
                "description": fm_data.get("description", ""),
            })
        except Exception:
            continue
```

- [ ] **Step 2: Add entries to manifest**

In the manifest dict (around line 183), add `entries`:

```python
manifest = {
    "version": "2.0",
    "indexed_at": datetime.now().isoformat(),
    "root": str(rag_dir),
    "stats": stats,
    "total": sum(stats.values()),
    "entries": entries,
}
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/rag/scripts/unified_indexer.py
git commit -m "feat(rag): populate manifest.entries for project index search"
```

---

### Task 14: Redirect nightly daemon to unified indexer

**Files:**
- Modify: `.claude/skills/ai_bridge/scripts/ops/rag_reindex.py:88-176`

- [ ] **Step 1: Read rag_reindex.py**

Read the full file to understand `scan()` and `fix()`.

- [ ] **Step 2: Update fix() to call unified_indexer.reindex_all()**

Replace the per-skill `rag_indexer.py` invocation with a single call to `unified_indexer.reindex_all()`:

```python
# In fix():
from rag.scripts.unified_indexer import reindex_all

stats = reindex_all(
    root=ctx.project_root,
    rag_dir=rag_dir,
    vault_dir=vault_dir,
)
```

- [ ] **Step 3: Remove git add/commit calls**

Delete the `subprocess.run(["git", "add", rag_path], ...)` call at line ~168 and the `_flush_rag_batch()` commit call at line ~176. RAG output is outside the repo.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/ai_bridge/scripts/ops/rag_reindex.py
git commit -m "fix(rag): redirect nightly daemon to unified indexer, remove git staging"
```

---

### Task 15: Fix knowledge-project-index-search

**Files:**
- Modify: `.claude/skills/knowledge/scripts/mcp/rag_search.py:56-119`

- [ ] **Step 1: Read rag_search.py project-index-search tool**

Read lines 56-119.

- [ ] **Step 2: Add word-overlap scoring**

Replace the simple substring match with word-overlap scoring:

```python
def _score_entry(entry: dict, query_words: set[str]) -> float:
    """Score an entry by word overlap with query."""
    text = f"{entry.get('name', '')} {entry.get('description', '')} {entry.get('hub', '')}".lower()
    entry_words = set(text.split())
    if not query_words:
        return 0.0
    overlap = query_words & entry_words
    return len(overlap) / len(query_words)
```

- [ ] **Step 3: Update search logic to use entries and scoring**

```python
entries = manifest.get("entries", [])
if not entries:
    return json.dumps({"results": [], "total": 0, "message": "No entries in manifest"})

query_words = set(query.lower().split())
scored = []
for entry in entries:
    if entry_type and entry.get("category") != entry_type:
        continue
    score = _score_entry(entry, query_words)
    if score > 0:
        scored.append({**entry, "score": round(score, 3)})

scored.sort(key=lambda x: x["score"], reverse=True)
results = scored[:20]
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/knowledge/scripts/mcp/rag_search.py
git commit -m "fix(rag): add word-overlap scoring to project index search"
```

---

### Task 16: Delete rag_indexer.py

**Files:**
- Delete: `.claude/skills/rag/scripts/rag_indexer.py`

- [ ] **Step 1: Verify no remaining imports of rag_indexer**

```bash
grep -r "rag_indexer" --include="*.py" --include="*.ts" . | grep -v "\.pyc" | grep -v "__pycache__"
```

If any remaining references exist, update them to use `unified_indexer` instead.

- [ ] **Step 2: Delete the file**

```bash
rm .claude/skills/rag/scripts/rag_indexer.py
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/rag/scripts/rag_indexer.py
git commit -m "chore(rag): retire rag_indexer.py — unified_indexer is canonical"
```

---

## Verification

After all phases complete:

**Phase 1a — Vault elimination:**
- [ ] `python -m skills.ai.scripts.sync_agents sync all` succeeds without vault
- [ ] CLAUDE.md header references `docs/agent-topics/agent-rules.md`
- [ ] `get_vault_dir()/ai_bridge/agent-rules.md` does not exist

**Phase 1b — Remote execution:**
- [ ] Dashboard build passes: `cd apps/dashboard && npm run build`
- [ ] Settings page shows ExecutionModeToggle
- [ ] Setting mode to "API" and clicking an action button dispatches via `/api/llm`
- [ ] Auto mode falls back correctly: IDE when available, API when configured, chat when neither

**Phase 2 — Plugin tool loading:**
- [ ] MCP server startup log shows plugin load summary with counts
- [ ] Missing plugin tools logged as WARNING with plugin name
- [ ] Dashboard routes with absent plugin show `PluginRequiredBanner` instead of empty data
- [ ] `get-plugin-load-status` MCP tool returns failure details

**Phase 3 — RAG unification:**
- [ ] `python .claude/skills/rag/scripts/unified_indexer.py` completes
- [ ] Manifest has entries: `python -c "import yaml; m=yaml.safe_load(open('$HOME/Library/Application Support/Augur/rag/_meta/manifest.yaml')); print(len(m.get('entries',[])))"`
- [ ] Chunks exist: `ls ~/Library/Application\ Support/Augur/rag/chunks/`
- [ ] `rag_indexer.py` is deleted, no imports remain
- [ ] No `git add` calls in `rag_reindex.py`
