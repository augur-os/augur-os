# Page Migration Runbook: TSX to YAML Config-Driven Pages

**Date:** 2026-03-30
**Status:** Approved
**Related:** ADR-491 (Config-Driven Pages), ADR-274 (Auto-Page Capabilities)

## Problem

47 custom TSX pages in `skills/dashboard/pages/`. These work but are hand-coded, inconsistent, and hard to maintain. Goal: migrate as many as possible to YAML config-driven pages (rendered by `ConfigPage` + block system) while keeping pages working at every step.

Previous batch attempt failed because it converted 30+ pages at once with fabricated MCP tool names and no browser verification.

## Approach: Tool-First, One Page at a Time

No batches. No skips. Every page is migrated individually with full verification. If something is broken, fix it before moving on.

### Phase 1: Tool Verification Diagnostic

A Python script that scans TSX pages for MCP tool references and verifies each tool works.

**Script:** `scripts/verify-page-tools.py`

**Process:**
1. Scan all 47 TSX pages for MCP tool names (`useMcpQuery`, `useMcpMutation`, `tool: 'name'`)
2. Call each tool via the MCP server JSON-RPC endpoint
3. Record: exists (bool), returns_data (bool), shape (object/array/scalar), field names
4. Output: `docs/generated/tool-verification.json`

**Output format:**
```json
{
  "get-daemon-status": {
    "exists": true,
    "returns_data": true,
    "shape": "object",
    "fields": ["status", "pid", "uptime_seconds", "services"],
    "pages": ["command/observe", "command/daemon"]
  }
}
```

This is a diagnostic, not a gate. Missing/broken tools get fixed, not skipped.

### Phase 2: Per-Page Migration (Repeatable Process)

For EACH page, in order from simplest to most complex:

**Step 1: Diagnose.** Read the TSX. Extract every MCP tool. Run through verification.

**Step 2: Fix tools.** For each tool that fails:
- Doesn't exist → implement in Python MCP server
- Returns no data → fix the data source/handler
- Returns wrong shape → fix the response format

**Step 3: Write YAML.** Create config at `skills/{skill}/augur/pages/{name}.yaml` using ONLY verified tools. Choose block type:
- Multiple independent data sources → `metrics-dashboard`
- List of items → `card-grid` or `data-table`
- Single data source with stats → `stat-grid`
- Mutations → `quickAdd` or `row_actions` on the data block
- Documentation → `markdown`

**Step 4: Build.** `pnpm run build:scripts && node scripts/dist/mount-plugins.mjs && npx next build`. Must pass.

**Step 5: Browser verify.** Navigate to the page in Chrome. Confirm:
- Page renders (no blank, no error boundary)
- Data loads (no "No data", no "500 Internal Server Error")
- Layout correct (cards/tables/badges show real content)
- Interactions work (search, filter, actions if applicable)

**Step 6: Delete TSX.** Only after browser confirmation. Remove page.tsx and orphaned components/hooks/types.

**Step 7: Commit.** `feat(pages): migrate {hub}/{page} to YAML config`

**If Step 5 fails:** Revert YAML, keep TSX, debug issue. Never move to next page with a broken one.

### Phase 3: Block Enhancement (When Needed)

When a tier of pages needs capabilities blocks don't have:

1. Identify the missing capability (e.g., charts, tabbed sections, inline editing)
2. Enhance the block system FIRST with tests
3. Verify the enhancement works with test data
4. THEN use it in the page migration

### Page Ordering: Easiest First

**Tier 1 — Read-only, 1-2 tools, no custom components (~15 pages):**
Simple stat displays and action lists. Block types: `stat-grid`, `action-bar`, `card-grid`, `markdown`.

Examples: career/growth, command/updater/plugins, life/health, studio/workbench/audit

**Tier 2 — Read-only, 3+ tools or custom rendering (~12 pages):**
Multiple data sources, custom formatting. Block type: `metrics-dashboard`.

Examples: command/observe, brain/scraper, life/wealth, career/project-dev

**Tier 3 — Mutations (~10 pages):**
Forms, toggles, inline editing. Block features: `quickAdd`, `row_actions`.

Examples: life/eisenhower, brain/reading-list/articles, life/home-automation

**Tier 4 — Complex (~10 pages):**
Tabs, charts, custom hooks, multi-component. May need block enhancements or stay as custom TSX.

Examples: brain/knowledge/memory, career/venture-augur, command/daemon

**Between tiers:** Assess what block enhancements are needed for the next tier. Build them before starting.

## Success Criteria

- Every migrated page renders with real data (verified in browser)
- No 500 errors, no "No data" placeholders on migrated pages
- Build passes after every single migration
- Custom TSX pages that remain are genuinely complex (can't be expressed with current blocks)
- Each page committed individually

## Anti-Patterns (What NOT to Do)

- Batch-convert multiple pages without verifying each one
- Create YAML with tool names without verifying they exist and return data
- Delete TSX before confirming YAML renders correctly in browser
- Skip pages — fix blockers instead
- Make up MCP tool names based on what the tool "should" be called
