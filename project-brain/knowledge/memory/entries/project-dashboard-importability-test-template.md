---
title: project-dashboard-importability-test-template
name: project-dashboard-importability-test-template
description: Auto-generated importability tests under tests/dashboard/python/test_*.py
  target modules at apps/dashboard/scripts/skill-scripts/<varies>/<name>.py; the generator's
  flat-layout template is broken post-merge. Use the `_load_module` helper pattern
  below
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project_dashboard_importability_test_template.md
source_hash: 59d78b42734982b3
---


Auto-generated importability tests at `tests/dashboard/python/test_<name>.py` were originally produced by a scaffolder that assumed a flat `tests/dashboard/../scripts/<name>.py` layout. After the mcp-app-factory + frontend + page-builder merge, the canonical location is **`apps/dashboard/scripts/skill-scripts/<subdir>/<name>.py`** where `<subdir>` is one of: `scoring`, `file_analyzers`, `mcp`, `source_adapters`, `stages`, `workflow`, `skill_generation`, `import_stages`, `questionnaires`, `mount`, `blocks`, OR the file lives at the top level of `skill-scripts/`. Many modules use relative imports (`from ._helpers import logger`) or bare sibling imports (`from workflow_runner import RunState`), so the test loader has to be package-aware AND sys.path-aware.

**Why:** triaged 92 of these tests on 2026-05-16 during the ADR-759 line of work. The original template did `importlib.import_module("<bare_name>")` against a `SCRIPTS_DIR = parents[2] / "scripts"` path that doesn't exist — 25+ tests collected fine but errored with `ModuleNotFoundError`. Wrote a batch rewriter (the `_load_module` helper below) that locates each module by name under `skill-scripts/`, loads it via `importlib.spec_from_file_location` with proper package context, and inserts the parent + `skill-scripts/` root onto sys.path. Net: 295/322 dashboard python tests passing post-rewrite.

**How to apply:**
1. **For new importability tests**, use this template (correct as of 2026-05-16):

```python
"""Importability test for apps/dashboard/scripts/skill-scripts/<subdir>/<name>.py (auto-generated)."""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = PROJECT_ROOT / "apps/dashboard/scripts/skill-scripts/<subdir>/<name>.py"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_module(module_path):
    """Load the target module, supporting relative imports if it lives in a package
    and bare imports of sibling modules under skill-scripts/."""
    skill_scripts_root = module_path
    while skill_scripts_root.name != "skill-scripts" and skill_scripts_root.parent != skill_scripts_root:
        skill_scripts_root = skill_scripts_root.parent
    if skill_scripts_root.name == "skill-scripts" and str(skill_scripts_root) not in sys.path:
        sys.path.insert(0, str(skill_scripts_root))
    if str(module_path.parent) not in sys.path:
        sys.path.insert(0, str(module_path.parent))

    parent = module_path.parent
    init = parent / "__init__.py"
    if init.exists():
        package_name = "dashboard_skill_scripts_" + parent.name.replace("-", "_")
        if package_name not in sys.modules:
            pkg_spec = importlib.util.spec_from_file_location(
                package_name, init, submodule_search_locations=[str(parent)]
            )
            pkg = importlib.util.module_from_spec(pkg_spec)
            sys.modules[package_name] = pkg
            pkg_spec.loader.exec_module(pkg)
        mod_full_name = package_name + "." + module_path.stem
        spec = importlib.util.spec_from_file_location(mod_full_name, module_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_full_name] = mod
        spec.loader.exec_module(mod)
        return mod
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_path.stem] = mod
    spec.loader.exec_module(mod)
    return mod


def test_<name>_importable():
    assert MODULE_PATH.exists(), f"{MODULE_PATH} not found"
    mod = _load_module(MODULE_PATH)
    assert mod is not None
```

2. **For batch rewrites** of broken importability tests, the rewriter at `/tmp/rewrite_importability_tests.py` (committed in commit `bbc3ea424`) auto-locates modules under skill-scripts/ and emits the v3 template. It's idempotent — re-running on already-v3 files is a no-op. If the scaffolder ever gets fixed, port that template into it.

3. **Namespaced package id** (`dashboard_skill_scripts_<parent>`) matters — using bare `scoring` as a sys.modules key collides with `shared-vault/skills/ai/scripts/ops/agent_digest/scoring.py` and breaks unrelated downstream tests. See [[project-augur-mcp-shim-two-module-objects]] for the related class of "wrong module object" bug.

4. **If a test still fails after applying this template**, the remaining failure is almost always a real production bug surfaced by the now-functional test (e.g. `workflow_runner` module missing, `from playwright.async_api import ...` against a Python package not in pyproject.toml, etc) — NOT a test-side issue.
