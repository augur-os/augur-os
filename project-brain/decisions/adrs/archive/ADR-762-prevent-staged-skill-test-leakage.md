---
status: Implemented
date: 2026-05-16
deciders:
  - gsannikov
related:
  - ADR-601
  - ADR-270
hub: dev
tags:
  - tests
  - boundary-enforcement
  - upstream-leak
  - skill-architecture
superseded_by: null
spec_file: 2026-05-16-prevent-staged-skill-test-leakage-design.md
plan_file: 2026-05-16-prevent-staged-skill-test-leakage.md
---

# ADR-762: Prevent Staged-Skill Test Leakage into Central tests/

> **ADR-762 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Wire a pre-commit + CI guard (`scripts/check_skill_test_placement.py`) backed by a YAML allowlist that refuses any test under central `tests/` whose filename or imports reference a vault-tier or staged-tier skill — and migrate the 31 historically-drifted skill-attributed tests into their canonical `shared-vault/skills/<skill>/augur/tests/` home.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-16-prevent-staged-skill-test-leakage-design.md`](../superpowers/specs/2026-05-16-prevent-staged-skill-test-leakage-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-16-prevent-staged-skill-test-leakage.md`](../superpowers/plans/2026-05-16-prevent-staged-skill-test-leakage.md)

## Status notes

**Implemented** (2026-05-16). Ships in commits `3b2a8d2ae` + `e414e9dc7` + `ac6a20d63` + `76e8d77b7`:

- `scripts/check_skill_test_placement.py` — pure-Python guard with body-import + staged-skill-filename rules. 5/5 unit tests pass.
- `config/system/test_placement_allowlist.yaml` — 14 boundary-test entries (test_no_vault_skill_refs, capability discovery, the worktree_preflight integration test, etc.); zero known-debt entries (all cleared via migration).
- `.githooks/pre-commit` + `.github/workflows/ci-tests.yml` — guard wired into both surfaces per `feedback-cross-agent-enforcement`.
- 25 tests migrated into their skills' `augur/tests/`: 13 ingest, 6 ai, 4 daemon, 1 rag, 1 file-manager (the originally-reported leak, renamed + parameterized as `tests/cli/test_bundle_server_per_skill_smoke.py`).
- 2 skill-named subdirs cleaned up: `tests/adaptive/` (vestigial) deleted, `tests/daemon/` migrated.
- 2 skill-conftests added/extended: `shared-vault/skills/daemon/augur/tests/conftest.py` + new `shared-vault/skills/ingest/augur/tests/conftest.py`. Each pre-imports the pip mcp SDK before skill-local paths shadow it.

Guard verified `exit 0` against current main as of `76e8d77b7`. Pre-commit hook actively refused an attempted commit during the migration when the allowlist diverged from the moved files — proving the gate is live.

**Runtime verification refreshed** (2026-05-17). The earlier `parents[N]` follow-up note is stale: the current migrated-test set no longer reproduces that failure class.

- `uv run python scripts/check_skill_test_placement.py` exits 0 against current main.
- The focused migrated daemon set (`test_local_flag.py`, `test_self_heal_worktree_policy.py`, `test_scheduled_executions.py`, `test_vault_hygiene_adr416.py`, `test_routine_tools.py`, `test_routines_registry.py`) reports `32 passed, 4 skipped`.
- `/auto-test-pytest` module verification for `brain` reports `1513 passed`.
- `/auto-test-pytest` module verification for `command` surfaced one unrelated daemon adaptive-loop public-history assertion drift (`created_at`, `job_id`, `kind`, `name`, `state` keys now present). That is not a staged-skill-placement or `parents[N]` migration failure, so it does not block ADR-762 closure.

**Proposed** (2026-05-16). Discovered during the post-ADR-759 test-triage cleanup as a structural architectural bug: the upstream-bound central `tests/` directory contained at least 1 filename-revealing leak (now fixed: `tests/cli/test_bundle_server_file_manager.py` → `test_bundle_server_per_skill_smoke.py`) and 31 additional skill-attributed tests for MVP-released skills (ingest, ai, daemon, knowledge, rag, platform-admin) that violate the existing `feedback-skill-test-convention` memory ("Augur skill tests live in shared-vault/skills/<skill>/augur/tests/").

The leak is real but narrower than the worst-case interpretation: the build/codex/ upstream export pipeline correctly filters staged-skill **code** OUT, but the tests/ directory itself ships forward (via the future `build_public_release_tree.py --scope mvp` which is currently `NotImplementedError` — i.e. leak hasn't fired yet but the structural risk exists today).

Two already-fixed pre-conditions (2026-05-16, commits `3b2a8d2ae` + `e414e9dc7`):
- `tests/adaptive/` deleted (vestigial post-ADR-756 consolidation)
- `tests/daemon/` migrated into `shared-vault/skills/daemon/augur/tests/`
- `tests/cli/test_bundle_server_file_manager.py` renamed + parameterized

The 31-test migration + the guard are the durable durable fix. Plan is implementation-ready; per-skill batches are parallel-safe; estimated ~3 hours. Run `/adr implement ADR-762` to execute.

## Related

- ADR-601 (shared-vault for team skills; private-vault for personal)
- ADR-270 (external vault paths)
- `feedback-skill-test-convention` memory (canonical test-placement rule that this ADR enforces mechanically)
- `feedback-cross-agent-enforcement` memory (use `.githooks/` / CI gates, not Claude-only rules)
- `feedback-long-session-drift` memory (mechanical gates beat behavioral rules — exactly what this ADR delivers)

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed: []
  patterns_deprecated: []
  files_affected:
    # New guard infrastructure
    - scripts/check_skill_test_placement.py                                  # new
    - tests/scripts/test_check_skill_test_placement.py                       # new
    - config/system/test_placement_allowlist.yaml                            # new
    - .githooks/pre-commit                                                   # add guard invocation
    - .github/workflows/<existing CI yml>                                    # add guard step

    # Tests to migrate (12 ingest → shared-vault/skills/ingest/augur/tests/)
    - tests/lib/index/test_index_prompts_vault.py                            # → ingest
    - tests/mcp/test_list_prompts_vault.py                                   # → ingest
    - tests/packages/augur-mcp/test_wiki_queries_tools.py                    # → ingest
    - tests/packages/augur-mcp/test_wiki_tools.py                            # → ingest
    - tests/unit/test_wiki_report_contract.py                                # → ingest
    - tests/wiki/sources/test_adr_index_adapter.py                           # → ingest
    - tests/wiki/sources/test_daily_logs_adapter.py                          # → ingest
    - tests/wiki/sources/test_existing_pipeline_adapters.py                  # → ingest
    - tests/wiki/sources/test_git_recent_commits_adapter.py                  # → ingest
    - tests/wiki/sources/test_memory_md_adapter.py                           # → ingest
    - tests/wiki/test_query_registry.py                                      # → ingest
    - tests/wiki/test_query_runner.py                                        # → ingest

    # Tests to migrate (9 ai → shared-vault/skills/ai/augur/tests/)
    - tests/packages/augur-mcp/infrastructure/test_browse.py                 # → ai (review)
    - tests/scripts/test_sync_output_policy.py                               # → ai
    - tests/sync_agents/test_codex_dream_automation.py                       # → ai
    - tests/sync_agents/test_purge.py                                        # → ai
    - tests/test_auto_index_notes.py                                         # → ai
    - tests/test_command_discovery.py                                        # → ai
    - tests/unit/test_resolve_cli_config.py                                  # → ai
    # 2 dashboard-attributed ai tests (review case-by-case):
    - tests/dashboard/python/test_mcp.py                                     # review: dashboard or ai
    - tests/dashboard/python/test_normalizer.py                              # review: dashboard or ai

    # Tests to migrate (5 daemon → shared-vault/skills/daemon/augur/tests/)
    - tests/lib/runtime/test_runtime_imports.py                              # → daemon
    - tests/mcp/test_scheduled_executions.py                                 # → daemon
    - tests/nightly/test_vault_hygiene_adr416.py                             # → daemon
    - tests/unit/test_list_routines_mcp.py                                   # → daemon
    - tests/unit/test_routine_discovery.py                                   # → daemon

    # Tests to migrate (3 knowledge → shared-vault/skills/knowledge/augur/tests/)
    - tests/lib/knowledge/test_knowledge_imports.py                          # → knowledge
    - tests/unit/test_browse_skill_inventory.py                              # → knowledge
    - tests/unit/test_release_workspace.py                                   # → knowledge

    # Tests to migrate (1 rag, 1 platform-admin)
    - tests/lib/index/test_unified_search_imports.py                         # → rag
    - tests/lib/test_capability_exposure_policy.py                           # → platform-admin
```
