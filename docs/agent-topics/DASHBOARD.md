<!--
⚠️  AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
Source: docs/agent-topics/DASHBOARD.md
Generator: project-brain/capabilities/skills/ai/scripts/sync_agents/__init__.py
-->
# Dashboard

> **When to load**: Load this doc when working on dashboard UI components, pages, layouts, or AI integration patterns.

See also [architecture-dashboard.md](../architecture-dashboard.md) for the contributor-facing dashboard architecture.

## Dashboard UI Guidelines

### Hub Page Rules
1. **Overview tab required** - First tab MUST be "Overview" pointing to `/[hub]`
2. **No duplicate headers** - layout.tsx renders title; page.tsx should NOT repeat it
3. **Tabs != Tool Cards** - Same item shouldn't appear in both
4. **Page file location** - Custom page TSX files go in `apps/dashboard/features/pages/{hub}/{page}/page.tsx`. NEVER in `project-brain/capabilities/skills/*/augur/dashboard/`. The catch-all registry only discovers pages from `features/pages/`. Placing pages elsewhere creates orphan tabs that crash the build.
5. **Verify after adding pages** - After creating a new page, run `pnpm run mount-plugins` from `apps/dashboard/` and confirm `0 orphans` in the tab registry output before committing.

### Browse Page Rules

Browse is a **discovery surface** — every tab is the same file-card mechanism over a
category of `BrowseItem`s, with `metadata` driving each card's badges, tags, and
actions.

1. **New signals ride existing cards** - An audit result, health score, or drift
   finding joins onto the relevant item's `BrowseItem.metadata` and surfaces as a card
   tag/badge (`getSkillStateTags`, `BrowseCard.collectBadges`) plus a detail-panel
   section. Do NOT add a bespoke `ViewMode` / browse tab for it.
2. **No `devOnly` panel tabs** - A view mode that bypasses the file-card grid (renders
   a custom component instead) splits the discovery mechanism and needs out-of-band
   toggles to even show. The single exception is a true interactive manager surface
   (install/configure/rebuild console, e.g. `extensions-bundles`).
3. **Findings with no owning item ride the nearest card** - e.g. ADR-741
   `stale_capability_entries` point at deleted skills, so they ride the `mcp-tools`
   capability card. Catalog aggregates belong on a hub dashboard card or in CLI/MCP.
4. **Join key discipline** - The browse index keys skills by slug; external reports
   often key by raw name. Index under both (see `lib/browse/skillCoverage.ts`).

See [architecture-dashboard.md](../architecture-dashboard.md) → "Discovery contract".

### Anti-Patterns (Forbidden)
- `min-h-screen` on page components
- Hardcoded backgrounds like `bg-slate-950`
- Duplicate headers between layout and page
- Bespoke `devOnly` browse view modes that bypass the shared file-card grid

### Before UI Changes
```bash
# Read design standards first
cat $(python3 -c "from src.config.paths import get_project_root; print(get_project_root())")/apps/dashboard/docs/references/design-standards.md
```

## Dashboard Commands

```bash
/dev-build                              # Rebuild dashboard and diagnose build errors
/dev-debug                              # Diagnose browser/runtime issues
/auto-lint                              # Lint and apply allowed fixes
pnpm --filter dashboard test            # Run dashboard tests
pnpm --filter dashboard test -- <file>  # Run a specific dashboard test
```

## Data Fetching (MCP-Direct Hooks)

All dashboard data fetching uses MCP hooks that call tools directly through `POST /api/mcp/tool`. There is no proxy route layer — components call MCP tools by name.

### Hooks

| Hook | Signature | Use Case |
|------|-----------|----------|
| `useMcpQuery` | `(key, tool, preset, opts?)` | Read data (replaces `useCachedFetch`) |
| `useMcpMutation` | `(tool, opts?)` | Write data with cache invalidation |
| `useMcpPoll` | `(key, tool, intervalMs, opts?)` | Interval-based polling (replaces `useCachedPoll`) |
| `mcpCall` | `(tool, args)` | Low-level imperative calls |

### Presets (PresetName)

Presets configure cache timing, stale-while-revalidate, and retry behavior:

| Preset | staleTime | gcTime | Use Case |
|--------|-----------|--------|----------|
| `device` | 30s | 5min | Hardware/system state |
| `realtime` | 5s | 1min | Live metrics, status |
| `live` | 10s | 2min | Frequently changing data |
| `user-data` | 2min | 10min | User content, notes |
| `config` | 5min | 30min | Settings, preferences |
| `static` | 30min | 60min | Rarely changing reference data |

### Examples

```tsx
// Read data with preset
const { data, isLoading } = useMcpQuery('health', 'get-system-health', 'device');

// Mutation with cache invalidation
const { mutate } = useMcpMutation('update-preference', {
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['preferences'] }),
});

// Polling every 5 seconds
const { data: status } = useMcpPoll('daemon', 'get-daemon-status', 5000);
```

### Deleted Hooks (Do Not Use)

`useCachedFetch`, `useCachedPoll`, `useCachedMutation`, `useAction`, and `useCachedSearch` have been removed. Use the MCP hooks above instead.

## Plugin File Mounting (IMPORTANT)

Dashboard UI components are mounted from skills at build time:
- **Source**: `project-brain/capabilities/skills/{skill}/augur/dashboard/`
- **Target**: `apps/dashboard/app/{hub}/`

**CRITICAL**: Files in `apps/dashboard/app/{hub}/` are **temporary copies**!
- They are overwritten by dashboard mount/build generation
- They contain a warning header: `AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY`
- They are marked read-only (mode 0o444)

```bash
# WRONG - editing the temporary copy
Edit apps/dashboard/app/control/tabs/LogsTab.tsx

# CORRECT - editing the source skill file
Edit project-brain/capabilities/skills/platform-admin/augur/dashboard/tabs/LogsTab.tsx
```

**How to find the source file**:
1. Look at the warning header in the mounted file - it contains the source path
2. Or map the path: `apps/dashboard/app/{hub}/...` -> `project-brain/capabilities/skills/{skill}/augur/dashboard/...`
3. Check `project-brain/capabilities/skills/*/SKILL.md` frontmatter for hub ID to skill mapping

## AI Integration Pattern (Central Action Buttons)

**CRITICAL**: All user-facing AI interactions in skills MUST go through the central action button infrastructure. Never create custom AI integration code.

### How It Works (ADR-162 Dispatch Model)

| Dispatch Mode | Description |
|---|---|
| `dispatch: fire` | Pure bash/script execution, no LLM needed |
| `dispatch: oneshot` | Single native AI-client prompt with focused context |
| `dispatch: ide` | Multi-step agent work, exploration, code changes |
| `dispatch: modal` | User confirmation or interactive input required |

**Canonical type**: `DispatchMode` from `apps/dashboard/lib/actions/types.ts`

### Adding AI Features to Skills

Define action defaults in `project-brain/capabilities/skills/{skill}/assets/actions/*.yaml`:
```yaml
id: my-ai-action
label: "Do Something Smart"
description: "AI analyzes X and suggests Y"
icon: Sparkles
dispatch: ide      # Multi-step agent work
```

**Anti-pattern**: Never use the legacy `flow:` field — it was replaced by `dispatch:` in ADR-162.

### Why This Pattern?

1. **Unified UX** - All AI actions behave consistently across skills
2. **IDE Context** - AI has full codebase access via IDE bridge
3. **No API Keys in Code** - Uses native AI-client configuration; dashboard code never owns model credentials
4. **Auditable** - All AI actions logged centrally
5. **User Control** - User sees and approves AI actions

### Dispatch vs MCP Hooks — Decision Table

| Context | Correct Pattern |
|---------|----------------|
| Component data loading | `useMcpQuery` or `useMcpPoll` |
| Component mutation (button click) | `useMcpMutation` |
| Action panel button — run script | `dispatch: 'fire'` |
| Action panel button — AI task | `dispatch: 'oneshot'` |
| Action panel button — IDE agent work | `dispatch: 'ide'` |
| Action panel button — UI form | `dispatch: 'modal'` |

**Key rule**: Component-level data fetching uses MCP hooks. Action panel buttons use `dispatch`. Component-level buttons MUST NOT use `runAction()`.

```tsx
// WRONG — dispatch: 'ide' for a data refresh button
const refreshStats = () => {
  runAction({ dispatch: 'ide', prompt: 'Run collect_stats.py...' });
};

// CORRECT — MCP hook for component data
const { data, refetch } = useMcpQuery('stats', 'get-stats', 'realtime');
const refreshStats = () => refetch();
```

### Anti-Patterns (Forbidden)

```python
# WRONG - Custom AI integration
import anthropic
client = anthropic.Client()
response = client.messages.create(...)

# WRONG - Embedded prompts executed directly
def suggest_meal():
    prompt = "Given pantry items..."
    return call_claude(prompt)

# CORRECT - Define action button in dashboard.yaml
# AI runs in IDE when user clicks button
# See: apps/dashboard/hooks/useActionRunner.ts
```

## Creating/Modifying Dashboard UI Workflow

1. Run `get-design-standards` MCP tool first
2. Read the relevant page's current implementation
3. Check high-scoring pages as benchmarks (Page Score >90)
4. Implement changes
5. Run `/dev-build` to verify
6. Run targeted dashboard tests for affected components

## Browser verification for dashboard fixes

For dashboard fixes, curl responses, `next build`, and API success are not enough. Verify the actual page in a browser on the checkout that owns the dashboard port.

Required flow:

1. If Python MCP code changed, restart the MCP server through the documented lifecycle gate.
2. If the user names a port or URL, test that exact target first. Do not substitute a temporary server until you have reported whether the requested target is up.
3. Identify which checkout owns the dashboard port before opening it.
4. Open the affected page in Chrome on that checkout's server.
5. Wait long enough for MCP-backed data to load.
6. Confirm real domain data appears, not only headings, skeletons, or empty states.
7. Confirm no blocking overlay, modal, fatal toast, or error boundary prevents normal use. `System Move Detected` counts as blocking until healed or explicitly accepted by the user.
8. If browser automation is unavailable, ask the user to verify before claiming the page is fixed.

### Valuable Data Closeout

When the task asks whether dashboard pages present value, or when closing a dashboard ADR/release, the browser check must answer the data-quality question directly:

1. Record each checked URL and the useful records observed there, including counts, titles, timestamps, and primary action labels.
2. Treat stale local-model errors, missing-provider errors, zero-size outputs, disabled primary actions, or "not available" panels as failures unless the spec explicitly defines that empty state as success.
3. Compare adjacent surfaces that claim the same fact:
   - Setup profile status must match `/brain/profile`.
   - Setup wiki-query status must match `/brain/wiki`.
   - Browse memory/wiki counts must match the Brain memory/wiki surfaces or explain the scope difference.
   - Insights summaries must be backed by visible inbox, ask, wiki, or source records.
4. If a page shows useful data behind a blocking overlay, report both facts and do not mark it as clean.
5. If the page depends on private-vault skills or tabs, run generation/build with `AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS=1`; orphan tabs caused by excluding local skills are an environment failure, not proof the page works.

## Wiring audit for broken or empty pages

When a dashboard page is broken or empty, audit wiring before UI polish:

1. Grep `useMcpQuery`, `useMcpMutation`, and `useMcpPoll` tool names.
2. Compare them with actual `@mcp.tool(name=...)` registrations.
3. Confirm the component destructures the response shape the tool returns.
4. Confirm dashboard code does not bypass MCP with direct `fs`, `spawn`, `exec`, or Python script calls.
5. Check all custom pages in the affected hub, not only the first reported page.

## YAML page migration safety

Before replacing TSX with YAML config, inspect the TSX source. A page must stay TSX when it uses `useMcpMutation`, modal/toast workflows, more than two `useState` calls, or multiple local component imports that the YAML renderer cannot express.

Before adding YAML passive data blocks, verify the MCP tool is a read-only empty-args data source. Mutation tools, search tools, argument-required tools, and metadata-only status tools are not passive data sources.
