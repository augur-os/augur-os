# Main-Rooted Global MCP Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent generated user-global MCP configs from being stamped with linked-worktree paths.

**Architecture:** Add root-selection helpers to the MCP projection paths. The requested repo root remains the active checkout, but each generated target receives an effective root: main checkout for user-global config, active checkout for repo-local `{repo_root}` config.

**Tech Stack:** Python, pytest, Augur MCP config generator, git worktree detection.

---

### Task 1: Document The Decision

**Files:**
- Create: `docs/adrs/ADR-774-main-rooted-global-mcp-config.md`
- Create: `docs/superpowers/specs/2026-05-22-main-rooted-global-mcp-config-design.md`
- Create: `docs/superpowers/plans/2026-05-22-main-rooted-global-mcp-config.md`

- [x] **Step 1: Write the design and plan**

The design states that user-global configs use the main checkout root, while repo-local `{repo_root}` configs use the active checkout.

- [x] **Step 2: Write ADR-774**

Create a thin ADR that points to this spec and plan, marks status `Accepted`, and lists `scripts/configure_mcp.py` plus `tests/scripts/test_configure_mcp_cli.py` in the impact manifest.

### Task 2: Add Failing Coverage

**Files:**
- Modify: `tests/scripts/test_configure_mcp_cli.py`

- [x] **Step 1: Add a test for global config from a linked worktree**

Patch the worktree detector to report a linked worktree, patch the main checkout resolver to return the real project root, run `configure_mcp.py --repo-root <tmp-worktree> --client cursor --auto --no-external`, and assert the generated config contains the main root but not the tmp worktree root.

- [x] **Step 2: Run the focused test**

Use the repo's auto-test-pytest operation with `pytest_args` narrowed to the new test. Expected result before implementation: failure because generated Cursor config references the tmp worktree root.

### Task 3: Implement Root Selection

**Files:**
- Modify: `scripts/configure_mcp.py`

- [x] **Step 1: Add git worktree helpers**

Add helpers to resolve the main checkout from `git worktree list --porcelain` and detect whether the requested root is a linked worktree.

- [x] **Step 2: Add config-scope helpers**

Add a helper that treats IDE config paths containing `{repo_root}` as repo-local and all other generated client configs as user-global.

- [x] **Step 3: Use an effective root per IDE**

In the IDE loop, build Augur server entries with the main checkout root for user-global configs when the requested root is a linked worktree. Keep repo-local configs on the requested root.

### Task 4: Verify

**Files:**
- No new files.

- [x] **Step 1: Rerun the focused auto-test-pytest slice**

Expected result after implementation: the new test passes.

- [x] **Step 2: Run real main config validation**

Run `configure_mcp.py --repo-root ~/Projects/Augur --check --verbose` and confirm all client configs are up to date.

- [x] **Step 3: Run self-heal validation scan**

Run `auto-heal-validate` scan against `~/Projects/Augur` and confirm it reports healthy config and service install state.

- [x] **Step 4: Run ADR post-write sync**

Run the ADR upsert/index/sync commands so `adrs-index.json`, `docs/generated/adr-index.md`, and generated agent instructions reflect ADR-774.

### Task 5: Close Secondary Global Writers

**Files:**
- Create: `src/config/worktrees.py`
- Modify: `project-brain/capabilities/skills/ai/scripts/sync_agents/templates.py`
- Modify: `project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/opencode.py`
- Modify: `project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/antigravity.py`
- Modify: `project-brain/capabilities/skills/plugin-pack/scripts/formatters/mcp_config.py`
- Modify: `project-brain/capabilities/skills/plugin-pack/scripts/formatters/cowork.py`
- Modify: `project-brain/capabilities/skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`
- Modify: `project-brain/capabilities/skills/plugin-pack/augur/tests/test_cowork_formatter.py`

- [x] **Step 1: Add sync-agent global root resolver**

Add a helper that resolves the main checkout for user-global MCP projections while leaving repo-local generated files on the active worktree.

- [x] **Step 2: Fix OpenCode and Antigravity global MCP sync**

OpenCode and Antigravity global configs use the stable main root when sync runs from a linked worktree. Antigravity preserves non-Augur servers already present in the global config.

- [x] **Step 3: Fix Cowork connector registration**

Claude Desktop Cowork connector registration uses the main checkout root instead of `src.config.paths.get_project_root()` directly when invoked from a worktree.

- [x] **Step 4: Add and run stale-writer regression tests**

Add tests covering OpenCode, Antigravity, and Cowork global projections from simulated linked worktrees, then run the affected test files.
