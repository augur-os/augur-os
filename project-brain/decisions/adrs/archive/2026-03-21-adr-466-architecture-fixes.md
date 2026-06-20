# ADR-466 Architecture Review Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remediate 6 tech debt items identified in the Q1 2026 architecture review (ADR-466).

**Architecture:** Six independent fixes targeting path resolution duplication, type consolidation, config/state separation, ESLint enforcement, platform guards, and HMR leak cleanup. Tasks 1-2 are high priority (structural), 3-5 medium (correctness), 6 low (DX).

**Tech Stack:** Python (paths, daemon, MCP server), TypeScript/ESLint (dashboard), YAML (config)

---

## File Map

| Task | Create | Modify | Test |
|------|--------|--------|------|
| 1 | `src/config/path_primitives.py` | `src/config/paths.py`, `src/mcp/augur_mcp/config.py` | `tests/config/test_path_primitives.py` |
| 2 | — | `src/mcp/augur_mcp/interfaces/skill_registry.py`, `src/mcp/augur_mcp/adapters/filesystem_registry.py`, `src/mcp/augur_mcp/compat.py`, `src/plugins/skill_registry.py` | `tests/plugins/test_skill_registry.py` |
| 3 | — | `config/system/self_heal.yaml`, `.claude/skills/daemon/scripts/self_heal/scanner.py`, `.claude/skills/daemon/scripts/ai_self_healer.py` | `.claude/skills/daemon/augur/tests/test_ai_self_healer.py` |
| 4 | — | `apps/dashboard/eslint.config.cjs` | manual: `pnpm --filter dashboard lint` |
| 5 | — | `.claude/skills/daemon/scripts/unified_daemon.py` | `pytest .claude/skills/daemon/augur/tests/ -v` |
| 6 | — | `apps/dashboard/lib/mcp/connection.ts`, `apps/dashboard/scripts/mount-plugins.ts` | `pnpm --filter dashboard build` |

---

### Task 1: Unify Path Resolution

Extract shared path primitives from `src/config/paths.py` into a new module that both `paths.py` and `src/mcp/augur_mcp/config.py` can import. This eliminates 12 duplicated functions and the hardcoded `"Augur"` project name in the MCP config.

**Important**: `paths.py` has 8 `_*_dir()` functions, not 6. The 6 that have counterparts in `augur_mcp/config.py` move to primitives. The remaining 2 (`_rag_home_dir`, `_launch_agents_dir`) stay in `paths.py` and call primitives internally (e.g., `_rag_home_dir` delegates to `application_support_dir()`).

**Files:**
- Create: `src/config/path_primitives.py`
- Modify: `src/config/paths.py:28-165` (replace inline helpers with imports, keep `_rag_home_dir` and `_launch_agents_dir`)
- Modify: `src/mcp/augur_mcp/config.py:20-97` (replace inline helpers with imports)
- Test: `tests/config/test_path_primitives.py`

- [ ] **Step 1: Write failing tests for the shared primitives module**

```python
# tests/config/test_path_primitives.py
"""Tests for shared path primitives used by both monorepo and standalone resolvers."""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config.path_primitives import (
    expand_path,
    env_path,
    is_macos,
    xdg_data_home,
    xdg_state_home,
    xdg_cache_home,
    application_support_dir,
    state_home_dir,
    logs_home_dir,
    cache_home_dir,
    vault_home_dir,
    documents_home_dir,
)


def test_expand_path_resolves_home():
    result = expand_path("~/test")
    assert not str(result).startswith("~")
    assert result.is_absolute()


def test_env_path_returns_none_for_missing_var():
    result = env_path("AUGUR_NONEXISTENT_TEST_VAR_12345")
    assert result is None


def test_env_path_returns_path_for_set_var():
    with patch.dict(os.environ, {"AUGUR_TEST_PATH": "/tmp/test"}):
        result = env_path("AUGUR_TEST_PATH")
        assert result == Path("/tmp/test")


def test_application_support_dir_uses_project_name():
    result = application_support_dir("TestProject")
    if is_macos():
        assert "TestProject" in str(result)
    else:
        assert "testproject" in str(result).lower()


def test_vault_home_dir_uses_project_name():
    result = vault_home_dir("TestProject")
    assert "TestProject" in str(result)


def test_all_dir_functions_return_absolute_paths():
    name = "Augur"
    for fn in [application_support_dir, state_home_dir, logs_home_dir,
               cache_home_dir, vault_home_dir, documents_home_dir]:
        result = fn(name)
        assert result.is_absolute(), f"{fn.__name__} returned relative path"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/config/test_path_primitives.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.config.path_primitives'`

- [ ] **Step 3: Create the shared primitives module**

Extract the 12 duplicated functions from `src/config/paths.py:28-149` into a new module. Each directory function takes `project_name: str` as a parameter instead of reading it internally.

```python
# src/config/path_primitives.py
"""Shared path primitives for monorepo and standalone resolvers.

Both src/config/paths.py (monorepo) and src/mcp/augur_mcp/config.py (standalone)
delegate to these functions. Project name is always passed explicitly — the caller
decides whether to read it from project.yaml or use a default.
"""
from __future__ import annotations

import os
import platform
from pathlib import Path


def expand_path(p: str | Path) -> Path:
    """Expand ~ and resolve to absolute path."""
    return Path(p).expanduser().resolve()


def env_path(*names: str) -> Path | None:
    """Return first matching env var as a resolved Path, or None.

    Strips whitespace from env values to match existing behavior in
    both paths.py and augur_mcp/config.py.
    """
    for name in names:
        val = os.environ.get(name)
        if val and val.strip():
            return expand_path(val.strip())
    return None


def is_macos() -> bool:
    return platform.system() == "Darwin"


def xdg_data_home() -> Path:
    return expand_path(os.environ.get("XDG_DATA_HOME", "~/.local/share"))


def xdg_state_home() -> Path:
    return expand_path(os.environ.get("XDG_STATE_HOME", "~/.local/state"))


def xdg_cache_home() -> Path:
    return expand_path(os.environ.get("XDG_CACHE_HOME", "~/.cache"))


def application_support_dir(project_name: str) -> Path:
    if is_macos():
        return expand_path(f"~/Library/Application Support/{project_name}")
    return xdg_data_home() / project_name.lower()


def state_home_dir(project_name: str) -> Path:
    if is_macos():
        return application_support_dir(project_name) / "state"
    return xdg_state_home() / project_name.lower()


def logs_home_dir(project_name: str) -> Path:
    if is_macos():
        return expand_path(f"~/Library/Logs/{project_name}")
    return xdg_state_home() / project_name.lower() / "logs"


def cache_home_dir(project_name: str) -> Path:
    if is_macos():
        return expand_path(f"~/Library/Caches/{project_name}")
    return xdg_cache_home() / project_name.lower()


def vault_home_dir(project_name: str) -> Path:
    return expand_path(f"~/Vault/{project_name}")


def documents_home_dir(project_name: str) -> Path:
    return expand_path(f"~/Documents/{project_name}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/config/test_path_primitives.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Refactor `paths.py` to import from `path_primitives`**

In `src/config/paths.py`, replace the inline helpers (lines 28-149) with imports from `path_primitives`. Keep `get_project_name()` (lines 61-72) in `paths.py` since it reads `project.yaml` — that's the monorepo-specific logic. The private `_application_support_dir()`, `_state_home_dir()`, etc. become thin wrappers that call `path_primitives.application_support_dir(get_project_name())`.

Key changes in `src/config/paths.py`:
- Lines 28-29: Remove `_expand`, import `expand_path as _expand` from `path_primitives`
- Lines 32-37: Remove `_env_path`, import `env_path as _env_path`
- Lines 40-53: Remove `_is_macos`, `_xdg_*`, import from `path_primitives`
- Lines 102-149: Replace 6 `_*_dir()` functions with calls to `path_primitives.*_dir(get_project_name())`
- Lines 150-165: Keep `_rag_home_dir()` and `_launch_agents_dir()` in `paths.py`, update to delegate to `path_primitives.application_support_dir(get_project_name())` internally

- [ ] **Step 6: Run existing paths tests**

Run: `pytest tests/config/ -v`
Expected: PASS (all existing tests still pass)

- [ ] **Step 7: Refactor `augur_mcp/config.py` to import from `path_primitives`**

In `src/mcp/augur_mcp/config.py`, replace the inline helpers (lines 20-97) with imports from `path_primitives`. The `MCPConfig` class keeps its `from_env()` factory but delegates to `path_primitives.*_dir(project_name)` where `project_name` defaults to `"Augur"` when `KERNEL_AVAILABLE` is False, and reads `get_project_name()` from `paths.py` when `KERNEL_AVAILABLE` is True.

Key changes in `src/mcp/augur_mcp/config.py`:
- Lines 20-21: Remove `_expand`, import from `path_primitives`
- Lines 24-29: Remove `_env_path`, import from `path_primitives`
- Lines 32-45: Remove `_is_macos`, `_xdg_*`, import from `path_primitives`
- Lines 48-97: Remove all `_get_*_dir()` functions
- In `MCPConfig.from_env()` (line 191+): use `path_primitives.*_dir(project_name)` with project_name resolved from kernel or defaulted

- [ ] **Step 8: Run MCP server tests**

Run: `pytest tests/ -k "mcp" -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/config/path_primitives.py tests/config/test_path_primitives.py src/config/paths.py src/mcp/augur_mcp/config.py
git commit -m "refactor: extract shared path primitives, eliminate duplication between paths.py and augur_mcp/config.py (ADR-466 Fix 1)"
```

---

### Task 2: Consolidate SkillMetadata Types

Make `SkillRecord` from `skill_discovery.py` the single canonical type. Remove the MCP-layer `SkillMetadata` dataclass (in `interfaces/skill_registry.py`) and its conversion overhead. The legacy `SkillMetadata` in `skill_discovery.py` stays as a backward-compat wrapper for non-MCP callers — it is not removed.

**Standalone mode constraint**: `skill_discovery.py` unconditionally imports `src.config.paths`, so it cannot be imported in standalone mode (`KERNEL_AVAILABLE=False`). The fix: keep a minimal `SkillRecord`-compatible dataclass in `interfaces/skill_registry.py` for standalone mode, guarded by `KERNEL_AVAILABLE`. When kernel is available, import the real `SkillRecord`; when not, use the local minimal version with the same field names.

**Files:**
- Modify: `src/mcp/augur_mcp/interfaces/skill_registry.py:14-77` (replace MCP `SkillMetadata` with `SkillRecord`-compatible type)
- Modify: `src/mcp/augur_mcp/adapters/filesystem_registry.py:24-45` (remove `_to_mcp_metadata` conversion)
- Modify: `src/mcp/augur_mcp/compat.py:86-147` (simplify conversion layer)
- Modify: `src/plugins/skill_registry.py` (keep legacy `SkillMetadata` re-export, add `SkillRecord` re-export)
- Modify: `src/mcp/augur_mcp/dynamic_registry.py` (update `.id` → `.name`)
- Modify: `src/mcp/augur_mcp/core/skills.py` (update any `.id` field access)
- Test: `tests/plugins/test_skill_registry.py`

- [ ] **Step 1: Read all consumer files to understand field access patterns**

Read these files and grep for `.id`, `.display_name`, `.triggers`, `.capabilities`, `.has_modules`, `.has_scripts`, `.has_references` to understand which SkillMetadata fields are used where:

```bash
grep -n '\.id\b\|\.display_name\|\.triggers\|\.capabilities\|\.has_modules\|\.has_scripts\|\.has_references\|\.token_estimate\|\.layer\|\.disabled' \
  src/mcp/augur_mcp/dynamic_registry.py \
  src/mcp/augur_mcp/core/skills.py \
  src/mcp/augur_mcp/core/context.py
```

Note: `SkillRecord` uses `name` where MCP `SkillMetadata` uses `id`. All consumers accessing `.id` need to switch to `.name`. Also check `list_skill_ids()` convenience methods on the ABC — they use `.id` internally.

Also grep more broadly for all `.id` consumers:
```bash
grep -rn 'skill\.id\b\|\.id:' src/mcp/augur_mcp/ src/plugins/
```

- [ ] **Step 2: Update `SkillRegistry` ABC to use `SkillRecord`**

In `src/mcp/augur_mcp/interfaces/skill_registry.py`:
- Remove the MCP `SkillMetadata` dataclass (lines 14-77)
- Add a `KERNEL_AVAILABLE` guard:
  - If True: `from src.plugins.skill_discovery import SkillRecord`
  - If False: define a minimal frozen dataclass `SkillRecord` with the same core fields (`name`, `description`, `path`, `master`, `hub`, `display_name`, `triggers`, `capabilities`, `has_modules`, `has_scripts`, `has_references`, `skill_type`, `tags`, `sync_enabled`, `origin`, `disabled`, `layer`, `aliases`, `token_estimate`, `visibility`)
- Update `SkillRegistry` ABC methods to return `list[SkillRecord]` and `SkillRecord | None`
- Update `list_skill_ids()` to use `.name` instead of `.id`

- [ ] **Step 3: Remove `_to_mcp_metadata` conversion in `filesystem_registry.py`**

In `src/mcp/augur_mcp/adapters/filesystem_registry.py`:
- Remove `_to_mcp_metadata()` function (lines 24-45)
- `list_skills()` returns `SkillRecord` objects directly from `discover_all_skills()`
- `resolve_skill()` returns `SkillRecord` directly

- [ ] **Step 4: Simplify compat.py conversion layer**

In `src/mcp/augur_mcp/compat.py`:
- Remove `SkillMetadata` conversion functions (lines 86-147)
- The monorepo adapter delegates directly to `FilesystemSkillRegistry` which now returns `SkillRecord`
- Standalone adapter creates minimal `SkillRecord` instances instead of `SkillMetadata`

- [ ] **Step 5: Update field access in `dynamic_registry.py`**

In `src/mcp/augur_mcp/dynamic_registry.py`:
- Change `.id` references to `.name` (the `SkillRecord` field name)
- All other fields (`path`, `triggers`, `has_modules`, `has_scripts`, `has_references`, `display_name`, `description`) exist on both types — no changes needed for these

- [ ] **Step 5b: Update `.id` references in `core/skills.py`**

In `src/mcp/augur_mcp/core/skills.py`:
- Grep for `.id` field access on skill objects and change to `.name`
- This file implements `list_skills_impl`, `get_skill_impl`, `find_skill_impl` which return metadata to MCP clients

- [ ] **Step 6: Update `skill_registry.py` re-exports**

In `src/plugins/skill_registry.py`:
- Keep the legacy `SkillMetadata` re-export (it still exists in `skill_discovery.py` for backward compat callers)
- Add `SkillRecord` re-export as the preferred canonical type
- Keep `list_skills()` and `resolve_skill()` wrappers returning `SkillRecord`

- [ ] **Step 7: Update tests**

In `tests/plugins/test_skill_registry.py`:
- Replace `SkillMetadata` assertions with `SkillRecord` field names
- `.id` → `.name`
- Verify `visibility`, `loop_config`, `hub` fields are directly accessible (no wrapper needed)

- [ ] **Step 8: Run full test suite**

Run: `pytest tests/plugins/ tests/mcp/ -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/mcp/augur_mcp/interfaces/skill_registry.py src/mcp/augur_mcp/adapters/filesystem_registry.py src/mcp/augur_mcp/compat.py src/mcp/augur_mcp/dynamic_registry.py src/plugins/skill_registry.py tests/plugins/test_skill_registry.py
git commit -m "refactor: consolidate SkillMetadata → SkillRecord as single canonical type (ADR-466 Fix 2)"
```

---

### Task 3: Move Scan Targets to State Directory

Move `discovered_scan_targets` from `config/system/self_heal.yaml` (config) to the state directory (runtime). This restores ADR-087 compliance: config files are static, state accumulates at runtime.

**Important**: `scanner.py:571` reads `USER_CONFIG` from `ai_self_healer.py:100`, which defines it as `get_config_dir() / "system" / "self_heal.yaml"`. Both files must be updated — `ai_self_healer.py` owns the path constant, and its config merge function at line ~244 also reads `discovered_scan_targets` from `USER_CONFIG`.

**Files:**
- Modify: `config/system/self_heal.yaml:7-99` (remove `discovered_scan_targets` section)
- Modify: `.claude/skills/daemon/scripts/self_heal/scanner.py:384,442,565-603` (read/write from state dir)
- Modify: `.claude/skills/daemon/scripts/ai_self_healer.py:100,244-248` (update `USER_CONFIG` or add separate state path, update config merge to read targets from state)
- Test: `.claude/skills/daemon/augur/tests/test_ai_self_healer.py`

- [ ] **Step 1: Read the scanner.py functions that read/write scan targets**

Read these specific sections:
- `.claude/skills/daemon/scripts/self_heal/scanner.py:380-450` (`init_scan_targets`, `_get_tracked_files`)
- `.claude/skills/daemon/scripts/self_heal/scanner.py:560-610` (`persist_discovered_targets`)

Also read:
- `.claude/skills/daemon/scripts/ai_self_healer.py:95-105` (where `USER_CONFIG` is defined)
- `.claude/skills/daemon/scripts/ai_self_healer.py:240-255` (config merge that reads `discovered_scan_targets`)

Understand: Where does it resolve the config path? What's the YAML structure? How does `scanner.py` get `USER_CONFIG` from `ai_self_healer`?

- [ ] **Step 1b: Add state path constant to `ai_self_healer.py`**

In `.claude/skills/daemon/scripts/ai_self_healer.py`, add a new constant alongside `USER_CONFIG`:
```python
SCAN_TARGETS_STATE = get_state_dir() / "self_heal" / "scan_targets.yaml"
```

Update the config merge function (~line 244) to NOT read `discovered_scan_targets` from `USER_CONFIG`. Instead, have `scanner.py` read targets directly from the state file.

- [ ] **Step 2: Update `persist_discovered_targets()` to write to state dir**

In `.claude/skills/daemon/scripts/self_heal/scanner.py:565-603`:
- Change the write target from `config/system/self_heal.yaml` to `get_state_dir() / "self_heal" / "scan_targets.yaml"`
- Create the directory if it doesn't exist
- Write only the `discovered_scan_targets` list (not embedded in the larger config file)
- Keep the same YAML structure for the targets list

- [ ] **Step 3: Update `init_scan_targets()` to read from state dir**

In `.claude/skills/daemon/scripts/self_heal/scanner.py:384`:
- Read targets from `get_state_dir() / "self_heal" / "scan_targets.yaml"` instead of `config/system/self_heal.yaml`
- Still read static routing rules (severity mapping) from `config/system/self_heal.yaml`

- [ ] **Step 4: Update `_get_tracked_files()` to read from state dir**

In `.claude/skills/daemon/scripts/self_heal/scanner.py:442`:
- Same change — read discovered targets from state dir

- [ ] **Step 5: Remove `discovered_scan_targets` from config YAML**

In `config/system/self_heal.yaml`:
- Remove lines 7-99 (the entire `discovered_scan_targets` section)
- Add a comment: `# Runtime scan targets live in state/self_heal/scan_targets.yaml (ADR-466)`

- [ ] **Step 6: Seed the state file with existing targets**

Create the initial state file by copying the current discovered targets:

```bash
mkdir -p ~/Library/Application\ Support/Augur/state/self_heal/
# The first daemon run will auto-discover targets, but seed existing ones for continuity
```

- [ ] **Step 7: Update tests**

In `.claude/skills/daemon/augur/tests/test_ai_self_healer.py:415`:
- Update test data to reflect the new file location
- Mock `get_state_dir()` instead of config path

- [ ] **Step 8: Run daemon tests**

Run: `pytest .claude/skills/daemon/augur/tests/ -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add config/system/self_heal.yaml .claude/skills/daemon/scripts/self_heal/scanner.py .claude/skills/daemon/scripts/ai_self_healer.py .claude/skills/daemon/augur/tests/test_ai_self_healer.py
git commit -m "fix: move discovered_scan_targets from config to state dir, restore ADR-087 compliance (ADR-466 Fix 3)"
```

---

### Task 4: Add ESLint Rule for spawn/exec in API Routes

Extend ESLint to block `child_process` and `node-pty` imports in API route files, matching the existing `fs` restriction from ADR-453.

**Files:**
- Modify: `apps/dashboard/eslint.config.cjs` (add restricted import rule)
- Test: `pnpm --filter dashboard lint`

- [ ] **Step 1: Read the current ESLint config**

Read: `apps/dashboard/eslint.config.cjs`
Read: `apps/dashboard/.eslintrc.json`

Understand: How are `fs` imports currently restricted? Is it via `no-restricted-imports` or a custom rule?

- [ ] **Step 2: Grep for existing `fs` restriction pattern**

```bash
grep -n "restricted\|no-restricted\|fs-exempt\|@fs-exempt" apps/dashboard/eslint.config.cjs apps/dashboard/.eslintrc.json
```

Understand the enforcement pattern to replicate for spawn/exec.

- [ ] **Step 3: Add spawn/exec restriction to ESLint config**

Add `no-restricted-imports` rule for API route files (`**/api/**/*.ts`):

```javascript
// In the overrides array, for files matching "**/api/**/*.ts"
{
  files: ["**/api/**/*.ts", "**/api/**/*.tsx"],
  rules: {
    "no-restricted-imports": ["error", {
      paths: [
        { name: "child_process", message: "API routes must not spawn subprocesses. Use MCP tools instead. Add // @spawn-exempt: <reason> if this is a legitimate exception (ADR-466)." },
        { name: "node:child_process", message: "API routes must not spawn subprocesses. Use MCP tools instead. Add // @spawn-exempt: <reason> if this is a legitimate exception (ADR-466)." },
        { name: "node-pty", message: "API routes must not use PTY. Use MCP tools instead. Add // @spawn-exempt: <reason> if this is a legitimate exception (ADR-466)." },
      ]
    }]
  }
}
```

- [ ] **Step 4: Check for existing legitimate spawn usage in API routes**

```bash
grep -rn "child_process\|node-pty\|spawn\|execSync\|execFile" apps/dashboard/app/api/ --include="*.ts" --include="*.tsx"
```

Add `// @spawn-exempt: <reason>` comments to any legitimate uses (e.g., terminal/PTY routes).

- [ ] **Step 5: Run lint to verify**

Run: `pnpm --filter dashboard lint`
Expected: PASS (no new violations, or only flagged routes that need exemption)

- [ ] **Step 6: Commit**

```bash
# Only commit the flat config file — .eslintrc.json is legacy and should not be modified
git add apps/dashboard/eslint.config.cjs
git commit -m "feat: add ESLint rule blocking spawn/exec in API routes (ADR-466 Fix 4)"
```

---

### Task 5: Platform Guard for Apple Daemon Services

Gate `note_watcher` and `note_ingest` services behind `sys.platform == 'darwin'` so the daemon doesn't crash-loop on non-macOS systems.

**Files:**
- Modify: `.claude/skills/daemon/scripts/unified_daemon.py:184-199`
- Test: `pytest .claude/skills/daemon/augur/tests/ -v`

- [ ] **Step 1: Read the service list construction**

Read: `.claude/skills/daemon/scripts/unified_daemon.py:160-210`

Understand: How is `SERVICES` defined? Is it a list literal or dynamically built?

- [ ] **Step 2: Add platform guard**

In `.claude/skills/daemon/scripts/unified_daemon.py`, wrap the two Apple services:

```python
import sys

# ... in the SERVICES list construction ...

# Apple-specific services (macOS only)
if sys.platform == "darwin":
    SERVICES.extend([
        {
            "name": "note_watcher",
            # ... existing config from lines 184-191 ...
        },
        {
            "name": "note_ingest",
            # ... existing config from lines 192-199 ...
        },
    ])
```

If `SERVICES` is a list literal, convert the two Apple entries to a conditional append.

- [ ] **Step 3: Run daemon tests**

Run: `pytest .claude/skills/daemon/augur/tests/ -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/daemon/scripts/unified_daemon.py
git commit -m "fix: gate Apple daemon services behind sys.platform == 'darwin' (ADR-466 Fix 5)"
```

---

### Task 6: Fix HMR Interval Leaks

Add `globalThis` singleton guards for intervals in `MCPBridge` and bound/cleanup patterns for collections in `mount-plugins.ts`.

**Important**: Line ~470 is a per-request timeout inside `sendRequest()`, tracked in `this.pendingRequests`. It is NOT a singleton — applying a `globalThis` guard there would break concurrent MCP requests. Only lines ~381 and ~414 (reconnection/recovery timers) need the singleton pattern.

**Files:**
- Modify: `apps/dashboard/lib/mcp/connection.ts:381,414` (singleton guards for reconnect/recovery timers)
- Modify: `apps/dashboard/lib/mcp/connection.ts:470` (verify cleanup on success/failure — different fix pattern)
- Modify: `apps/dashboard/scripts/mount-plugins.ts:107,112,541,808`
- Test: `pnpm --filter dashboard build`

- [ ] **Step 1: Read the MCPBridge reconnect/recovery code**

Read: `apps/dashboard/lib/mcp/connection.ts:370-490`

Understand: Which `setTimeout`/`setInterval` calls are singletons (reconnect/recovery) vs per-request (sendRequest timeout)?

- [ ] **Step 2: Add `globalThis` guards for reconnect/recovery timers ONLY**

Apply the singleton pattern to lines ~381 and ~414 (reconnection and recovery timers):

```typescript
// Before (leaks on HMR)
const timer = setTimeout(() => { ... }, delay);

// After (idempotent)
const TIMER_KEY = '__mcp_reconnect_timer__';
if ((globalThis as any)[TIMER_KEY]) {
  clearTimeout((globalThis as any)[TIMER_KEY]);
}
(globalThis as any)[TIMER_KEY] = setTimeout(() => { ... }, delay);
```

For line ~470 (per-request timeout in `sendRequest`): Do NOT apply the singleton pattern. Instead, verify that `clearTimeout(timeout)` is called in both the success and failure paths (it should be at lines ~472-474 and ~481-484). If the cleanup is already correct, remove the `TODO_BUG` marker with a comment explaining why. If cleanup is missing, add it.

- [ ] **Step 3: Read mount-plugins.ts watcher code**

Read: `apps/dashboard/scripts/mount-plugins.ts:100-120,535-550,800-815`

Understand: Which `Set`/`Map` collections are unbounded? Which `setTimeout` lacks cleanup?

- [ ] **Step 4: Add bounds to module-level collections**

For `SHELL_HUBS`, `devHubFilter`, `SHELL_PAGES` Sets:
- These are populated from known finite sources (hub configs, env vars), so they're bounded by design
- Remove the `TODO_BUG` markers since the bound is implicit (hub count is finite)
- Add a comment documenting the bound: `// Bounded by hub count (currently 6)`

For the `debounceTimer` at line ~808:
- Add cleanup in the watcher teardown / `process.on('SIGTERM')` handler

- [ ] **Step 5: Run build to verify**

Run: `pnpm --filter dashboard build`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/lib/mcp/connection.ts apps/dashboard/scripts/mount-plugins.ts
git commit -m "fix: add globalThis guards for HMR interval leaks, document collection bounds (ADR-466 Fix 6)"
```

---

## Execution Order

Tasks 1-5 are independent and can run in parallel. Task 6 is also independent but lowest priority.

**Recommended parallel grouping:**

| Agent | Tasks | Priority |
|-------|-------|----------|
| Agent A | Task 1 (paths) + Task 2 (SkillMetadata) | High — structural |
| Agent B | Task 3 (scan targets) + Task 5 (platform guard) | Medium — daemon fixes |
| Agent C | Task 4 (ESLint) + Task 6 (HMR leaks) | Medium/Low — dashboard fixes |

## Final Verification

After all tasks complete:

```bash
# Python tests
pytest tests/ -v --timeout=60

# Dashboard build
pnpm --filter dashboard build

# Lint
pnpm --filter dashboard lint

# Type check
pnpm --filter dashboard tsc --noEmit
```
