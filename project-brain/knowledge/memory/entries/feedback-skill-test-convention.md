---
title: feedback-skill-test-convention
name: feedback-skill-test-convention
description: Augur skill tests live in shared-vault/skills/<skill>/augur/tests/ and
  import scripts via importlib.util.spec_from_file_location — NEVER via dotted module
  path
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback_skill_test_convention.md
source_hash: e29cf19f39db1293
---


When writing tests for a shared-vault skill, tests live in `shared-vault/skills/<skill>/augur/tests/` (with the `augur/` nesting), not in `<skill>/tests/`. Tests import the skill's scripts using `importlib.util.spec_from_file_location("...", _MODULE_PATH)` and reference identifiers as `mod.foo()`, not via dotted module paths like `from shared_vault.skills.<skill>.scripts.foo import bar`.

**Why:** The directory names contain hyphens (`shared-vault/`, `loop-hygiene/`, etc.) which are invalid as Python module name components. `from shared_vault.skills.loop_hygiene.scripts.X import Y` cannot resolve — Python won't map `shared_vault` → `shared-vault`. The repo's `tests/conftest.py` provides `import_plugin_module(bundle, skill, module_path)` as a helper for this case, but the established pattern in `loop-wiring/`, `loop-memory/`, etc. is the inline `importlib.util.spec_from_file_location` form.

**How to apply:**
- New skill test files: place at `shared-vault/skills/<skill>/augur/tests/test_*.py`, never at `<skill>/tests/`
- Import the script under test like this (copy from `loop-wiring/augur/tests/test_dead_wiring_ops.py`):
  ```python
  import importlib.util
  from pathlib import Path

  _MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "module_name.py"
  _SPEC = importlib.util.spec_from_file_location("module_name_under_test", _MODULE_PATH)
  assert _SPEC and _SPEC.loader
  mod = importlib.util.module_from_spec(_SPEC)
  _SPEC.loader.exec_module(mod)
  ```
  Then call `mod.some_function(...)`, reference `mod.CONSTANT`, etc.
- When writing PLANS/SPECS that show test code: never write `from shared_vault.skills.X.scripts.Y import Z` — write the importlib form instead. Hyphenated dirs make the dotted form unresolvable.
- Plan reviewers should flag the dotted form as a plan bug.

**Dataclass + importlib gotcha:** if the loaded module defines `@dataclass(frozen=True)` with `field(default_factory=...)`, Python's dataclass machinery looks up the owning module via `sys.modules[cls.__module__]` during field resolution and crashes with `AttributeError: 'NoneType' object has no attribute '__dict__'` because inline importlib does NOT auto-register the loaded module in `sys.modules`. Fix: add `sys.modules["<spec-name>"] = mod` BEFORE `_SPEC.loader.exec_module(mod)`. Use the same unique sentinel name passed to `spec_from_file_location`. The `loop-wiring` precedent doesn't hit this because its loaded modules have no dataclasses; modules that DO use dataclasses (loop-hygiene `lifecycle_config.py` etc.) need the sys.modules registration.

**Known codebase exception:** `shared-vault/skills/ai/scripts/sync_agents/tests/*.py` files use the **dotted-module** form (`from sync_agents.foo import bar` after `sys.path.insert`), NOT the importlib idiom. This is legacy debt observed during ADR-746 (May 2026) — the directory is import-resolvable because `sync_agents/` itself has no hyphens. The importlib idiom is still the correct choice for **new** test files (it's more portable across worktrees and shared-vault layouts), but pre-existing `sync_agents/tests/*.py` files are exempt from harmonization until a follow-up cleanup. When adding a new test file in this subtree, follow the importlib idiom; do not match the legacy style.
