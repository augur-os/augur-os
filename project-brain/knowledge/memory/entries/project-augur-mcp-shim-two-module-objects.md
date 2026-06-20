---
title: project-augur-mcp-shim-two-module-objects
name: project-augur-mcp-shim-two-module-objects
description: Augur's legacy `augur_mcp` shim loads each canonical impl file as TWO
  sys.modules entries (long `src.mcp.augur_*` and short `augur_*` paths) — monkeypatching
  the short path NEVER lands on the long-path module the impl actually uses. Always
  patch `src.mcp.augur_framework...` long path
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project_augur_mcp_shim_two_module_objects.md
source_hash: cb31f1250a9b7869
---


`src/mcp/augur_mcp/__init__.py` is a legacy compatibility shim that aliases imports like `augur_mcp.infrastructure.X` to canonical modules like `augur_framework.tools.infrastructure.X`. Crucially, Python imports the SAME source file as TWO distinct sys.modules entries depending on the path:

- `src.mcp.augur_framework.tools.infrastructure.file_platform` (long path; what production impls use)
- `augur_framework.tools.infrastructure.file_platform` (short path; what `augur_mcp` aliases point at)

`id(short_module) != id(long_module)`. Replacing an attribute on one does NOT replace it on the other. `unittest.mock.patch("augur_mcp.infrastructure.file_platform._ALLOWED_ROOTS", ...)` resolves via the shim to the SHORT-path module — the canonical impl looks up `_ALLOWED_ROOTS` on the LONG-path module — the patch is a no-op for the impl.

**Why:** triaged 290 pre-existing test failures on 2026-05-16 (ADR-759 line of work). At least 84 failures across 6 files (test_file_tools, test_file_rw, test_file_binary, test_file_operations, test_file_platform, test_settings) ALL hit `assert result["status"] == "success"` failing with `'error'` because the security guard's `_ALLOWED_ROOTS` patch never landed and the canonical impl saw the real allowed-roots config (which rejects tmp paths). Also burned 30 min on `test_user_gets_design_standards` patching `augur_mcp.core.context._get_project_root` instead of `src.mcp.augur_core.tools.core.context._get_project_root` — verified the two are different module objects via id().

**How to apply:**
1. When a test patches `augur_mcp.<anything>`, the patch target is almost certainly wrong. **Always patch the canonical long path**: `src.mcp.augur_<core|framework|shared>...`.
2. Mechanical sed-equivalent fix when running into "MCP tool returned error instead of success" or "FileNotFoundError on expected output state file" patterns:
   - `augur_mcp.infrastructure.` → `src.mcp.augur_framework.tools.infrastructure.`
   - `augur_mcp.core.` → `src.mcp.augur_core.tools.core.`
   - `augur_mcp.adapters.`, `augur_mcp.context_injector.` etc → `src.mcp.augur_shared.*`
   - Check `src/mcp/augur_mcp/__init__.py:_ALIASES` for the full mapping table.
3. The `augur_mcp._ALIASES` dict is also incomplete in places; if a test fails with `AttributeError: module 'augur_mcp' has no attribute 'X'` and `X` exists under `src/mcp/augur_*/...`, add the alias to `_ALIASES` first (Cluster A pattern).
4. Diagnostic: `python -c "import sys; sys.path.insert(0, '~/Projects/Augur/src/mcp'); import augur_mcp; import augur_framework.tools.X as a; import src.mcp.augur_framework.tools.X as b; print('same?', a is b, id(a), id(b))"` — confirm the gotcha is in play for any given module.

**Update 2026-05-24:** Still live — `pytest tests/` run monolithically (whole tree, one process) shows **187 failures**; down from 290 on 2026-05-16, so partially chipped away. EVERY one is this class: tests pass in isolation (`tests/packages/augur-mcp/` alone = 601 passed) but fail when an earlier dir imports the alternate module path first. Confirmed deterministic (no pytest-randomly/xdist installed). Beyond the MCP impls, the same bug hits `src.cli_plugins` vs bare `cli_plugins` (test_cli_plugins patches `src.cli_plugins._get_skill_dirs`, `discover_subcommands` returns 7 real skills) and `src.mcp.augur_shared.bundle_server` vs `augur_shared.bundle_server` (test_bundle_server patches long path, impl logs `[augur_shared.bundle_server] bundle 'apple' not found`). Trigger is `src/` on sys.path enabling bare top-level imports as a SECOND object — that path entry also makes `src/logging/` shadow the stdlib `logging`. **Why the test loop is green:** `auto-test-pytest` (project-brain/.../routine-codebase/scripts/test_pytest_ops.py::_run_pytest) runs HUB-SCOPED test_dirs with `-x --tb=short -q`, never the whole tree in one process — so it sidesteps the cross-dir pollution and masks the broken monolithic-run invariant. Reproduces on any checkout (pure source+test code, no worktree paths) — NOT worktree-specific. A durable fix is a root-conftest guard aliasing `sys.modules["X"] = sys.modules["src.X"]` (single object identity) and/or sys.path hygiene so `src/` is never a top-level import root.

Related: [[feedback-chrome-mcp-multi-browser]] also covers a session-time silent-wrong-target failure mode; both share the lesson "always verify what you THINK you're talking to is what you ARE talking to before going deep on the wrong diagnosis tree." See also [[project-test-suite-topology]] (the loop runs three runners, none monolithic).
