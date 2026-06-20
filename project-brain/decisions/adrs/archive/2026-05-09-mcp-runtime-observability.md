# MCP Runtime Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show configured, running, and stale Augur MCP runtime state in Browse so capability cleanup does not require terminal process audits.

**Architecture:** Reuse the existing Browse `mcp-servers` category. The MCP backend enriches configured server rows from `config/system/mcp_servers.yaml` with live process metadata and appends synthetic rows for running Augur MCP processes that are not configured. The dashboard table renders MCP-specific columns when the active view is `mcp-servers`.

**Tech Stack:** Python MCP backend, existing Browse MCP hook, TypeScript Browse transforms/table components, pytest, Vitest/Playwright.

---

### Task 1: Runtime Inventory Backend

**Files:**
- Create: `src/lib/mcp_runtime_inventory.py`
- Modify: `src/mcp/augur_framework/tools/infrastructure/browse/index.py`
- Test: `tests/lib/test_mcp_runtime_inventory.py`

- [x] **Step 1: Write failing tests**

Test process parsing for `augur_core`, `augur_framework`, and `augur_shared.bundle_server` commands. Test that configured server rows are enriched with `runtime_status`, `runtime_pids`, and `running_clients`, and that unconfigured running bundle servers become `stale-runtime` rows.

- [x] **Step 2: Verify tests fail**

Run: `.venv/bin/python -m pytest tests/lib/test_mcp_runtime_inventory.py -q`

Expected: import or assertion failure because the inventory module does not exist yet.

- [x] **Step 3: Implement minimal runtime inventory**

Parse `ps -axo pid=,ppid=,command=` output, normalize Augur server IDs, group running processes by server ID, enrich configured Browse rows, and append stale rows.

- [x] **Step 4: Verify tests pass**

Run: `.venv/bin/python -m pytest tests/lib/test_mcp_runtime_inventory.py -q`

Expected: all tests pass.

### Task 2: Browse MCP Server Rendering

**Files:**
- Modify: `apps/dashboard/lib/browse/transforms.ts`
- Modify: `apps/dashboard/components/shared/BrowseTableView.tsx`
- Modify: `apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx`
- Test: `tests/dashboard/lib/browse/transforms.test.ts`

- [x] **Step 1: Write failing transform test**

Add a test proving `transformIndexEntry(..., "mcp-servers")` preserves `runtimeStatus`, `runtimePids`, `runningClients`, and `staleRuntime` metadata.

- [x] **Step 2: Verify test fails**

Run: `pnpm --dir apps/dashboard vitest run ../../tests/dashboard/lib/browse/transforms.test.ts`

Expected: metadata assertion fails before transform support is added.

- [x] **Step 3: Render MCP-specific table columns**

Pass the active view mode into `BrowseTableView`. When it is `mcp-servers`, render `Server`, `Runtime`, `Clients`, `Tier`, and `Actions` columns.

- [x] **Step 4: Verify dashboard test passes**

Run: `pnpm --dir apps/dashboard vitest run ../../tests/dashboard/lib/browse/transforms.test.ts`

Expected: transform tests pass.

### Task 3: Verification

**Files:**
- No additional source edits unless verification exposes defects.

- [x] **Step 1: Run targeted Python and dashboard tests**

Run:
- `.venv/bin/python -m pytest tests/lib/test_mcp_runtime_inventory.py tests/lib/test_capability_browse_enrichment.py -q`
- `pnpm --dir apps/dashboard vitest run ../../tests/dashboard/lib/browse/transforms.test.ts`

- [x] **Step 2: Verify live Browse in browser**

Open `/browse?category=mcp-servers` against the active dashboard and confirm the MCP table loads with runtime state and no console/page errors.

- [x] **Step 3: Verify runtime cleanup remains clean**

Run the retired-process audit for `augur_framework --client-id codex` and old per-bundle `apple`, `file-manager`, `lifestyle` helpers. Expected: no matching live processes.
