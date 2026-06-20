---
title: ADR-770 Shared Vault Reference Inventory
brain_scope: project
status: active
owner: team
date: 2026-05-21
adr: ADR-770
---

# ADR-770 Shared Vault Reference Inventory

## Commands

Initial scan before physical moves:

```bash
rg -n "shared-vault" --hidden -g '!node_modules' -g '!.git' -g '!apps/dashboard/.next' -g '!project-brain'
```

Post-move scan after `git mv`:

```bash
rg -n "shared-vault" --hidden -g '!node_modules' -g '!.git' -g '!apps/dashboard/.next' -g '!llms-full.txt'
```

Final active-code scan, excluding historical ADR/spec/migration text and this
report:

```bash
rg -n "shared-vault" . --hidden -g '!**/.git/**' -g '!**/.next/**' -g '!**/node_modules/**' -g '!**/.venv/**' -g '!docs/superpowers/**' -g '!docs/adrs/**' -g '!docs/migrations/**' -g '!project-brain/reports/**'
```

Canonical project-brain skill-path guard:

```bash
rg -n "project-brain/skills|project-brain', 'skills|project-brain\", \"skills" apps tests src scripts .github config project-brain --hidden -g '!**/.git/**' -g '!**/.next/**' -g '!**/node_modules/**' -g '!**/.venv/**' -g '!project-brain/reports/**'
```

## Counts

| Scan | Hit count | Notes |
| --- | ---: | --- |
| Before physical move | 2606 | Included canonical paths, generated docs, historical ADR/spec text, tests, and skill-local code. |
| After physical move | 2591 | The old root is empty except for `shared-vault/README.md`; remaining hits are code/doc/test references to classify or migrate. |
| Final active-code scan | 25 | All hits are compatibility wrappers/comments, stale-input filters, legacy registry cleanup fixtures, or the `shared-vault/README.md` pointer. |
| Final `project-brain/skills` guard | 0 | No code/test/config path still targets the rejected intermediate shape. |

## Classification

| Category | Examples | Migration action |
| --- | --- | --- |
| Canonical path references | `src/config/paths.py`, `src/plugins/skill_discovery.py`, MCP loaders, dashboard discovery | Replace with project-brain helpers or mapped-source helpers. |
| Import/PYTHONPATH references | `src/lib/brain_init.py`, MCP config templates, skill bootstrap scripts | Replace `${AUGUR_ROOT}/shared-vault` with `${AUGUR_ROOT}/project-brain/capabilities`. |
| Generated-source templates | sync-agents constants/adapters, dashboard registry generators | Update source templates, then regenerate outputs. |
| Tests and fixtures | `tests/src/test_paths.py`, dashboard path tests, migrated skill tests | Update active behavior tests; leave only explicit historical fixtures. |
| Historical docs and ADR/spec text | implemented ADRs, migration plans, architecture history | Keep when describing old behavior or ADR history. |
| Compatibility wrappers | `shared-vault/README.md`, deprecated `get_shared_vault_*` helpers | Keep temporarily with clear deprecation and expiry. |

## Remaining Active Hits

| Remaining area | Reason retained |
| --- | --- |
| `src/plugins/skill_discovery.py` | Accepts legacy `shared-vault` metadata only so stale records continue to classify as project-owned during migration. |
| `src/lib/index/_scanners_knowledge.py` | Normalizes legacy `source_root`/`source` values from `shared-vault` to `project-brain` at the scanner boundary. |
| `src/lib/brain_registry_bootstrap.py` and brain-registry tests | Prunes old registry entries whose data root was the retired `shared-vault` directory. |
| `src/mcp/augur_shared/adapters/filesystem_registry.py` | Repairs configured legacy `shared-vault/skills` roots to the canonical project-brain skill root. |
| `scripts/augur-codex-mcp*` | Filters stale incoming `PYTHONPATH` entries ending in `shared-vault`. |
| `src/lib/repo_hygiene.py`, `shared-vault/README.md` | Keeps the compatibility pointer root visible and allowed while durable data lives under `project-brain/`. |
| Compatibility tests | Preserve behavior for explicit old-path fixtures and environment override cases. |

## Closeout Rule

ADR-770 is not clean until every remaining `shared-vault` hit is either:

- historical ADR/spec/docs text,
- a compatibility-expiring wrapper,
- a test fixture for compatibility behavior, or
- removed in favor of `project-brain/` or mapped-source helpers.
