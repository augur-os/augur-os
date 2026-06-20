# augur_mcp Namespace Dismantle — Track 3a Follow-up A

> **Worktree required:** Use branch `dismantle-augur-mcp` off main.

**Goal:** Delete `src/mcp/augur_mcp/` entirely. Move 120 .py files into `augur_core/`, `augur_framework/`, or `augur_shared/`. Migrate 338 external import sites.

**Architecture:** 5 PRs. Each phase is independently reversible. Re-export shims preserve compat through PR 4; PR 5 deletes them.

## Source-tree mapping

| Current path | Target path | Rationale |
|---|---|---|
| `augur_mcp/core/` | `augur_core/tools/core/` | Registry/discovery tools (already wired to augur-core) |
| `augur_mcp/domain/` | `augur_framework/tools/domain/` | Operational (cowork, ide, plugins) |
| `augur_mcp/infrastructure/` | `augur_framework/tools/infrastructure/` | Operational (files, jobs, paths, system, etc.) |
| `augur_mcp/tools/hubs/` | `augur_framework/tools/hubs/` | Hub tool wrappers |
| `augur_mcp/tools/internal/` | `augur_framework/tools/internal/` | Internal helpers |
| `augur_mcp/tools/integrations/` | `augur_framework/tools/integrations/` | External integrations |
| `augur_mcp/tools/settings/` | `augur_framework/tools/settings/` | Settings tools |
| `augur_mcp/wizard/` | `augur_framework/tools/wizard/` | Onboarding wizard |
| `augur_mcp/adapters/` | `augur_shared/adapters/` | Framework adapters used by both servers |
| `augur_mcp/utils/` | `augur_shared/utils/` | Shared utilities |
| `augur_mcp/interfaces/` | `augur_shared/interfaces/` | Shared abstractions |
| `augur_mcp/static_resources/` | `augur_shared/static_resources/` | Shared static data |
| `augur_mcp/tests/` | `tests/mcp/` | Test code (consolidate into top-level tests/) |
| `augur_mcp/__init__.py`, `compat.py`, `client_surface.py`, `bundle_server.py`, `plugin_tools.py`, `mcp_sdk.py` | (already in augur_shared via PR 1 shims) | Track 3a moved these via shims; PR 5 removes the shims |

## Critical rules

- **Never** `--no-verify`.
- **Track 2 invariant**: vault per-bundle servers must keep launching at every PR.
- **augur-core / augur-framework invariant**: both servers must keep registering their tools at every PR.
- **Re-export shims** at original locations through PR 4. PR 5 removes them.
- **Bulk substitution discipline**: use sed with explicit per-module patterns (avoid blanket `s/augur_mcp/...` since we have multiple targets).

## PR 1 — Move shared infrastructure to augur_shared/

Files: `adapters/`, `utils/`, `interfaces/`, `static_resources/`.

Steps:
1. `git mv src/mcp/augur_mcp/adapters src/mcp/augur_shared/adapters` (and similarly for utils, interfaces, static_resources)
2. Add re-export shims at original paths:
   ```python
   # src/mcp/augur_mcp/adapters/__init__.py
   """Re-export from augur_shared. Deprecated; removed in PR 5."""
   from src.mcp.augur_shared.adapters import *  # noqa
   ```
3. Update internal imports inside the moved files (any `from src.mcp.augur_mcp.X` → `from src.mcp.augur_shared.X` for siblings)
4. Run tests; commit

Verification: full test cascade pass; vault per-bundle servers still launch.

## PR 2 — Move core/ to augur_core/tools/core/ + update wiring

1. `git mv src/mcp/augur_mcp/core src/mcp/augur_core/tools/core`
2. Add re-export shim at `src/mcp/augur_mcp/core/__init__.py`
3. Update `src/mcp/augur_core/tools/__init__.py` to import from new location (was `from src.mcp.augur_mcp.core import register_core_tools`; now `from src.mcp.augur_core.tools.core import register_core_tools`)
4. Update internal imports inside `core/*.py` files
5. Run tests + augur-core stdio smoke test

## PR 3 — Move framework tool surfaces to augur_framework/tools/

Files: `domain/`, `infrastructure/`, `tools/hubs/`, `tools/internal/`, `tools/integrations/`, `tools/settings/`, `wizard/`.

1. `git mv` each subdirectory under `augur_framework/tools/`
2. Re-export shims at all original locations
3. Update `src/mcp/augur_framework/tools/__init__.py` to import from new locations
4. Update internal imports
5. Run tests + augur-framework stdio smoke test

## PR 4 — Migrate ~338 external consumer import sites

Bulk sed substitution on consumers. Pattern map:

```
src.mcp.augur_mcp.core.X      → src.mcp.augur_core.tools.core.X
src.mcp.augur_mcp.domain.X    → src.mcp.augur_framework.tools.domain.X
src.mcp.augur_mcp.infrastructure.X → src.mcp.augur_framework.tools.infrastructure.X
src.mcp.augur_mcp.tools.X     → src.mcp.augur_framework.tools.X (when not core)
src.mcp.augur_mcp.wizard.X    → src.mcp.augur_framework.tools.wizard.X
src.mcp.augur_mcp.adapters.X  → src.mcp.augur_shared.adapters.X
src.mcp.augur_mcp.utils.X     → src.mcp.augur_shared.utils.X
src.mcp.augur_mcp.interfaces.X → src.mcp.augur_shared.interfaces.X
src.mcp.augur_mcp.static_resources.X → src.mcp.augur_shared.static_resources.X
```

Apply via sed across `src/`, `apps/`, `tests/`, `scripts/`, `skills/*/augur/`. ~50 test files particularly affected.

Verification: full test cascade; dashboard build clean; 5 vault servers launch; augur-core + augur-framework stdio tests pass.

## PR 5 — Move tests + delete augur_mcp/

1. `git mv src/mcp/augur_mcp/tests tests/mcp` (consolidate into top-level)
2. Audit grep — any remaining `from src.mcp.augur_mcp` references? Should be zero.
3. `rm -rf src/mcp/augur_mcp/`
4. `ls src/mcp/` should show only `augur_core/`, `augur_framework/`, `augur_shared/`, plus `pyproject.toml`, `plugin_utils.py`, `README.md`
5. Run full test cascade + dashboard build
6. Verify 5 vault servers launch via `python -m augur_shared.bundle_server <bundle>`
7. Verify augur-core stdio + augur-framework stdio
8. Commit + push

## Done criteria

1. ✅ `src/mcp/augur_mcp/` directory does not exist
2. ✅ Zero `from src.mcp.augur_mcp` or `import augur_mcp` statements anywhere except docstrings/historical-doc references
3. ✅ All tests pass; allowlist remains `frozenset()`
4. ✅ Dashboard builds; pages load
5. ✅ 5 vault per-bundle servers launch
6. ✅ augur-core (29 tools) and augur-framework (~205 tools) stdio servers register correctly
