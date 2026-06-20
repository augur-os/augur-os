# Prevent Staged-Skill Test Leakage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the architectural leak where skill-specific tests live under central `tests/` (the upstream-bound directory) and prevent recurrence via a mechanical guard.

**Architecture:** A pure-Python guard (`scripts/check_skill_test_placement.py`) wired into `.githooks/pre-commit` + CI, paired with a YAML allowlist for legitimate boundary tests + a one-time migration of 31 historically-drifted files into their skill's `augur/tests/` directory.

**Tech Stack:** Python 3.12, pytest, existing `.githooks/` + CI infrastructure.

**Spec:** [`docs/superpowers/specs/2026-05-16-prevent-staged-skill-test-leakage-design.md`](../specs/2026-05-16-prevent-staged-skill-test-leakage-design.md).

---

## Task 1: Create the guard script with unit tests (TDD)

**Files:**
- Create: `scripts/check_skill_test_placement.py`
- Create: `tests/scripts/test_check_skill_test_placement.py`
- Create: `config/system/test_placement_allowlist.yaml`

- [ ] **Step 1: Write the failing tests**

Tests cover: clean state (exit 0), filename violation, body-import violation, allowlist exemption, stale allowlist entry. Use tmp_path fixtures with fake `tests/` and `shared-vault/skills/` trees.

- [ ] **Step 2: Run tests to confirm RED**

```bash
/auto-test-pytest tests/scripts/test_check_skill_test_placement.py
```

Expected: `ModuleNotFoundError` or `FileNotFoundError`.

- [ ] **Step 3: Implement the guard per the spec**

Pure-Python, no external deps beyond `pathlib`, `re`, `yaml`. Uses `src.config.paths.get_project_root()`. Lists vault skills from `shared-vault/skills/`. Parses allowlist YAML.

- [ ] **Step 4: Create the initial allowlist**

```yaml
allowed_central_tests_with_skill_refs:
  - tests/architecture/test_no_vault_skill_refs.py
  - tests/mcp/test_shared_config_paths.py
  - tests/scripts/test_configure_mcp_cli.py
  - tests/packages/augur-mcp/tools/test_dynamic_plugin_loader.py
  - tests/unit/test_staged_skill_catalog.py
  - tests/src/test_migrate_staging_to_vault_drafts.py
  - tests/cli/test_bundle_server_per_skill_smoke.py
```

- [ ] **Step 5: Tests pass; commit**

---

## Task 2: Wire the guard into pre-commit + CI

**Files:**
- Modify: `.githooks/pre-commit`
- Modify: `.github/workflows/ci.yml` (or equivalent — check existing structure first)

- [ ] **Step 1: Append the guard to pre-commit**

```bash
# In .githooks/pre-commit, add:
uv run python scripts/check_skill_test_placement.py || {
  echo "Staged-skill test placement violation. See scripts/check_skill_test_placement.py output above."
  exit 1
}
```

- [ ] **Step 2: Append to CI**

Add as a step in the existing test/lint job. Should run BEFORE pytest so violations surface fast.

- [ ] **Step 3: Verify with a deliberate violation**

```bash
touch tests/test_ingest_garbage.py
echo "from shared-vault.skills.ingest.scripts.wiki import foo" >> tests/test_ingest_garbage.py
git add tests/test_ingest_garbage.py
git commit -m "test: deliberate violation"
# Expected: pre-commit fails with actionable message
rm tests/test_ingest_garbage.py
git reset
```

- [ ] **Step 4: Commit the wiring**

---

## Task 3: Pre-migration verification

**Files:** none — measurement only.

- [ ] **Step 1: Run the guard against current main**

```bash
uv run python scripts/check_skill_test_placement.py
```

Expected: 31 violations matching the inventory in the spec (12 ingest + 9 ai + 5 daemon + 3 knowledge + 1 rag + 1 platform-admin). Capture the output as evidence of the pre-migration state.

---

## Tasks 4-9: Per-skill migration (six parallel-safe batches)

Each batch follows the same pattern. Listed here for **ingest** (largest, 12 files); other batches follow the same template.

### Task 4: Migrate 12 ingest tests

**Files:** 12 files moving from `tests/...` → `shared-vault/skills/ingest/augur/tests/`

- [ ] **Step 1: List the files**

From the analysis output:
```
tests/lib/index/test_index_prompts_vault.py
tests/mcp/test_list_prompts_vault.py
tests/packages/augur-mcp/test_wiki_queries_tools.py
tests/packages/augur-mcp/test_wiki_tools.py
tests/unit/test_wiki_report_contract.py
tests/wiki/sources/test_adr_index_adapter.py
tests/wiki/sources/test_daily_logs_adapter.py
tests/wiki/sources/test_existing_pipeline_adapters.py
tests/wiki/sources/test_git_recent_commits_adapter.py
tests/wiki/sources/test_memory_md_adapter.py
tests/wiki/test_query_registry.py
tests/wiki/test_query_runner.py
```

- [ ] **Step 2: For each file: git mv + path-depth update**

```bash
for f in <files>; do
  base=$(basename $f)
  git mv $f shared-vault/skills/ingest/augur/tests/$base
  # Edit if file references Path(__file__).resolve().parents[N] — update N
  # to reflect new depth (parents[4] from augur/tests/ = repo root)
done
```

- [ ] **Step 3: Add conftest.py to ingest's augur/tests/ if needed**

If migrated tests need src/ on sys.path:

```python
import sys
from pathlib import Path
_repo_root = Path(__file__).resolve().parents[4]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
```

- [ ] **Step 4: Run all 12 migrated tests**

```bash
/auto-test-pytest shared-vault/skills/ingest/augur/tests/test_*.py
```

Expected: all pass (some may surface real import issues that need per-file fix).

- [ ] **Step 5: Run the guard — should now show 19 violations (was 31)**

- [ ] **Step 6: Commit the batch**

### Task 5: Migrate 9 ai tests

```
tests/dashboard/python/test_mcp.py            (NOTE: actually a dashboard test that uses ai, leave per Cluster A)
tests/dashboard/python/test_normalizer.py     (same — dashboard, leave)
tests/packages/augur-mcp/infrastructure/test_browse.py
tests/scripts/test_sync_output_policy.py
tests/sync_agents/test_codex_dream_automation.py
tests/sync_agents/test_purge.py
tests/test_auto_index_notes.py
tests/test_command_discovery.py
tests/unit/test_resolve_cli_config.py
```

(Note: the 2 dashboard tests under tests/dashboard/python/ test ai-skill content but are dashboard-page-related; review case-by-case whether they belong with the dashboard or with ai. The analysis flagged them but the dashboard context may dominate.)

### Tasks 6-9: Same template for daemon (5), knowledge (3), rag (1), platform-admin (1)

---

## Task 10: Post-migration verification + value validation

**Files:** none.

- [ ] **Step 1: Run the guard**

```bash
uv run python scripts/check_skill_test_placement.py
```

Expected: 0 violations.

- [ ] **Step 2: Run the full pytest sweep**

```bash
/auto-test-pytest
```

Compare pass/fail count to pre-migration baseline; should be ≥ same (the migration shouldn't break tests, only relocate them).

- [ ] **Step 3: Try to push a deliberate violation**

Confirms the .githooks/pre-commit guard actually fires for new violations.

- [ ] **Step 4: Real-data value (CLAUDE.md rule #34)**

Concrete evidence for the merge commit:
- 31 files moved from central `tests/` into their skills' `augur/tests/`.
- 0 staged-skill names remain in central `tests/` filenames or imports outside the 7-entry allowlist.
- pre-commit guard rejects deliberate violations.
- pytest sweep pass count unchanged or improved.

---

## Self-Review Notes

| Spec component | Task(s) |
|---|---|
| `scripts/check_skill_test_placement.py` | Task 1 |
| `config/system/test_placement_allowlist.yaml` | Task 1 |
| `.githooks/pre-commit` + CI | Task 2 |
| Pre-migration measurement | Task 3 |
| Per-skill migration batches | Tasks 4-9 (parallel-safe) |
| Post-migration validation | Task 10 |

Parallelism: Tasks 4-9 are independent per-skill and can be run as parallel subagents (each batch operates on disjoint files and modifies disjoint skill directories). Task 1 must come first (the guard is needed to measure). Tasks 2-3 sequential after Task 1. Tasks 4-9 parallel. Task 10 sequential after all migration.
