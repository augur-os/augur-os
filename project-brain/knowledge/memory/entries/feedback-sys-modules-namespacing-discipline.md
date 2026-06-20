---
title: feedback-sys-modules-namespacing-discipline
name: feedback-sys-modules-namespacing-discipline
description: When loading a module via importlib.spec_from_file_location, NEVER register
  it under a generic short name like "scoring" or "audit" in sys.modules — those collide
  globally across the test sweep and break unrelated tests with cryptic ImportError.
  Always namespace (e.g. `dashboard_scoring`)
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback_sys_modules_namespacing_discipline.md
source_hash: 05abfa97a9bba589
_mentions:
- '[[project-augur-mcp-shim-two-module-objects]]'
- '[[project-dashboard-importability-test-template]]'
_entity_tier: 3
---




`sys.modules` is a single dict shared across an entire pytest collection run. If `tests/dashboard/python/test_normalizer.py` does `sys.modules["scoring"] = dashboard_scoring_package` to load `apps/dashboard/scripts/skill-scripts/scoring/__init__.py`, then a LATER test that does `from scoring import TOKEN_BUDGET_HOT` (intending the shared-vault one at `shared-vault/skills/ai/scripts/ops/agent_digest/scoring.py`) hits the cached dashboard module and fails with `ImportError: cannot import name 'TOKEN_BUDGET_HOT' from 'scoring'`. The dashboard scoring module is utterly unrelated to the ai-skill scoring module; they just share a name.

**Why:** burned 30+ min on this on 2026-05-16 during the 290-failure triage. 3 tests in `shared-vault/skills/ai/augur/tests/` collected fine individually but errored under full-sweep collection. Stack trace pointed at `'~/Projects/Augur/apps/dashboard/scripts/skill-scripts/scoring/__init__.py'` instead of the expected ai-skill scoring path — clear sys.modules pollution from a sibling test that loaded the dashboard scoring first.

**How to apply:**
1. **Never use bare short names in `sys.modules`** when loading via `importlib.spec_from_file_location` in tests. Always namespace:
   ```python
   # WRONG — collides globally
   sys.modules["scoring"] = pkg
   # RIGHT — namespaced
   sys.modules["dashboard_scoring"] = pkg
   ```
2. Common offending names to watch for: `scoring`, `audit`, `analyzer`, `validator`, `helpers`, `config` — any single word that multiple parts of the codebase legitimately use as a module name.
3. Pair the registration with the spec's `submodule_search_locations=[str(parent)]` so relative imports within the loaded package use the namespaced name correctly (`dashboard_scoring.dimensions` not `scoring.dimensions`).
4. **Symptom that this rule was violated**: a test passes in isolation but fails under full sweep with `ImportError: cannot import name 'X' from 'Y'`, where Y is a module name shared by two unrelated parts of the codebase. The fix is upstream — find which earlier test polluted `sys.modules[Y]` and namespace its registration.
5. **Test isolation rule of thumb**: any test that touches `sys.path.insert` or `sys.modules[name] = ...` should ask "would my changes still be safe if 100 unrelated tests ran after me?" If the answer requires the cleanup to happen later, use `monkeypatch.syspath_prepend()` / `monkeypatch.setattr(sys, "modules", ...)` to auto-clean per pytest's fixture lifecycle.

Related: [[project-dashboard-importability-test-template]] (the rewriter that produces this namespacing pattern). [[project-augur-mcp-shim-two-module-objects]] (the OTHER class of sys.modules-identity bug — same module file, two distinct entries).
