---
title: project-test-suite-topology
name: project-test-suite-topology
description: Augur's full test surface spans THREE runners — pytest tests/, pytest
  shared-vault skill tests, and dashboard jest — "all tests pass" must cover all three
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project_test_suite_topology.md
source_hash: a19dd70625b15c23
---


Augur's automated test surface has three distinct runners; a "make all tests pass" / CI-green claim must cover all three or it is incomplete:

1. **Main pytest suite** — `pyproject.toml` `testpaths = ["tests", "plugins"]` (~2630 tests). Run: `uv run python -m pytest tests`. `plugins/` currently has 0 test files.
2. **Skill pytest suite** — `shared-vault/skills/*/augur/tests/` (~4243 tests, 717 files), NOT in `testpaths`. The `/auto-test-pytest` routine (`shared-vault/skills/routine-codebase/scripts/test_pytest_ops.py`) discovers these via `get_managed_skill_source_dirs`. Run shell-agnostically with `find shared-vault/skills -type d -path "*/augur/tests" -print0 | sort -z | xargs -0 uv run python -m pytest`. NOTE: zsh does NOT word-split unquoted `$vars`/`$(...)`, and `mapfile` is bash-only — use `xargs -0` or you'll pass one giant bogus path arg.
3. **Dashboard jest suite** — `apps/dashboard` (~290 suites / 2216 tests), runner `jest` (config `apps/dashboard/jest.config.js`). Run: `cd apps/dashboard && CI=true npx jest --ci`. The repo's `/auto-test-*` routine catalog has NO jest loop, so jest drift is easy to miss. There is also a Playwright visual suite (`test:visual`) that needs a live dashboard+browser — not a unit suite.

Order-dependent failures are common: run a suspected-polluted test ALONE first to tell real bug from cross-test `sys.modules`/`sys.path` pollution. See [[feedback-sys-modules-namespacing-discipline]].
