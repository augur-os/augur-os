---
date: 2026-05-16
status: Draft
deciders:
  - gsannikov
related:
  - feedback-skill-test-convention (Augur memory)
  - ADR-601 (shared-vault structure for team skills + private-vault for personal skills)
  - ADR-270 (external vault locations)
---

# Prevent Staged-Skill Test Leakage into Central tests/ — Design

## Problem

The Augur monorepo is upstream-bound: parts of it (released MVP skills + repo-level infrastructure) get published into a public release tree (`build/codex/plugins/augur/`, future `build_public_release_tree.py --scope mvp`). The central `tests/` directory is part of that upstream artifact.

Today the central `tests/` directory contains tests for skills that are **NOT** part of the MVP release:

1. **At least 1 filename-revealing leak** (now-fixed): `tests/cli/test_bundle_server_file_manager.py` named the staged-r1 `file-manager` skill in its filename + hard-coded it as a subprocess argument. Renamed to `test_bundle_server_per_skill_smoke.py` 2026-05-16.

2. **31 skill-attributed tests** in central `tests/` whose skill (ingest, ai, daemon, knowledge, rag, platform-admin — all MVP) already has its own `shared-vault/skills/<skill>/augur/tests/` directory. These violate the existing `feedback-skill-test-convention` memory ("Augur skill tests live in shared-vault/skills/<skill>/augur/tests/"). Distribution is:
   - 12 ingest tests (wiki adapters, queries, prompts)
   - 9 ai tests (sync_agents, codex_dream_automation, purge, command_discovery)
   - 5 daemon tests (routines, scheduled_executions, vault_hygiene)
   - 3 knowledge tests (browse_skill_inventory, release_workspace, knowledge_imports)
   - 1 rag (unified_search_imports)
   - 1 platform-admin (capability_exposure_policy)

3. **2 already-fixed cases**: `tests/adaptive/` (empty vestigial dir, deleted) and `tests/daemon/{test_local_flag.py, test_self_heal_worktree_policy.py}` (moved to `shared-vault/skills/daemon/augur/tests/`).

4. **Legitimate boundary tests that NAME staged skills**: 4 tests in central `tests/` correctly reference vault-tier skill names because they're testing the boundary itself (`test_no_vault_skill_refs.py`, `test_shared_config_paths.py`, `test_configure_mcp_cli.py`, `test_dynamic_plugin_loader.py`). These MUST stay in central `tests/` to validate the segregation.

The problem is two-headed: (a) historical drift placed skill-specific tests outside their canonical home, (b) there is no mechanical guard preventing recurrence.

## Goal

After this design ships:

1. Every skill-specific test lives in its skill's `augur/tests/` directory (per `feedback-skill-test-convention`).
2. Central `tests/` contains only repo-level tests (src/, scripts/, apps/dashboard/) plus an allowlist of boundary tests that need to know vault-tier names.
3. A pre-commit / CI guard refuses commits that introduce new skill-specific tests under central `tests/` or that mention staged-skill names outside the allowlist.
4. The 31 historically-drifted tests get migrated to their skill homes (one-time work, tracked in the implementation plan's Impact Manifest).

## Non-goals

- Migrating the test bodies' content — the tests themselves are correct, only their location changes.
- Changing the upstream-release pipeline (`build_public_release_tree.py` still NotImplementedError for `mvp` scope; the guard described here is upstream of any release).
- Touching legitimate boundary tests in the allowlist.
- Renaming any production code.

## Approach

Three layers, decoupled:

```
┌─────────────────────────────────────────────────────────────────┐
│  Convention: tests live with their skill                        │
│  shared-vault/skills/<skill>/augur/tests/test_*.py              │
│  ~/Projects/Au-vault/skills/<skill>/augur/tests/test_*.py       │
└─────────────────────────────────────────────────────────────────┘
                            ▲
                            │ enforced by
                            │
┌─────────────────────────────────────────────────────────────────┐
│  Guard: scripts/check_skill_test_placement.py                   │
│  - reads tests/ and shared-vault/skills/                        │
│  - flags any tests/ file that imports a skill's scripts/ tree   │
│    or whose name matches a vault-tier skill                     │
│  - honors an allowlist file (boundary tests that legitimately   │
│    need to know vault-tier names)                               │
│  - runs as .githooks/pre-commit AND CI                          │
│  - exit 0 = clean, exit 1 = violation with file:line list       │
└─────────────────────────────────────────────────────────────────┘
                            ▲
                            │ migrates from
                            │
┌─────────────────────────────────────────────────────────────────┐
│  One-time migration (Phase 2 of the implementation plan)        │
│  Move the 31 historically-drifted skill-attributed tests into   │
│  their skill's augur/tests/ — with importlib path updates as    │
│  needed.                                                        │
└─────────────────────────────────────────────────────────────────┘
```

### Components

#### 1. `scripts/check_skill_test_placement.py` (new)

Pure-Python guard. Pseudocode:

```python
def main():
    repo = get_project_root()
    central = repo / "tests"
    vault_skills = list_shared_vault_skills()       # 20 skill names from manifest
    private_skills = list_private_vault_skills()    # books/plugin-pack/file-manager etc
    staged_skills = list_staged_skills_from_release_matrix()
    allowlist = parse_allowlist(repo / "config/system/test_placement_allowlist.yaml")

    violations = []
    for test_file in central.rglob("test_*.py"):
        # Rule 1: filename can't contain a vault/staged skill name (with hyphen or underscore)
        for skill in private_skills + staged_skills:
            if skill in test_file.stem or skill.replace("-", "_") in test_file.stem:
                if test_file not in allowlist:
                    violations.append((test_file, f"filename references {skill}"))

        # Rule 2: file body can't import from skills/<vault_skill>/scripts/
        text = test_file.read_text()
        for skill in vault_skills + private_skills:
            if re.search(rf"shared-vault/skills/{re.escape(skill)}/scripts/", text):
                if test_file not in allowlist:
                    violations.append((test_file, f"imports from skill/{skill}/scripts/"))

    if violations:
        print("Test placement violations (move to skill's augur/tests/, or add to allowlist):")
        for f, r in violations:
            print(f"  {f}: {r}")
        return 1
    return 0
```

#### 2. `config/system/test_placement_allowlist.yaml` (new)

```yaml
# Tests under central tests/ that legitimately need to know vault-tier
# skill names. Boundary/architecture tests that validate the segregation.
allowed_central_tests_with_skill_refs:
  - tests/architecture/test_no_vault_skill_refs.py    # tests that src/ has NO vault skill refs
  - tests/mcp/test_shared_config_paths.py              # config-path resolution uses skill names as examples
  - tests/scripts/test_configure_mcp_cli.py            # MCP server config names
  - tests/packages/augur-mcp/tools/test_dynamic_plugin_loader.py  # comment-only
  - tests/unit/test_staged_skill_catalog.py            # tests the staging mechanism itself
  - tests/src/test_migrate_staging_to_vault_drafts.py  # tests the migration script
  - tests/cli/test_bundle_server_per_skill_smoke.py    # parameterized over any present skill
```

#### 3. Hook wiring

- `.githooks/pre-commit` (new entry): `python scripts/check_skill_test_placement.py || exit 1`
- `.github/workflows/<existing CI>.yml`: add the script to the test-collection job
- Pre-existing memory `feedback-cross-agent-enforcement` says: prefer `.githooks/` + CI gates over Claude-only rules so the rule fires for any agent. This design satisfies that.

## Invariants

Preserved:

1. `shared-vault/skills/<skill>/augur/tests/` is the canonical home for skill tests (per `feedback-skill-test-convention`).
2. Private-vault skills' tests live in the private vault, NOT in this repo (per ADR-601).

New:

3. Central `tests/` accepts only: repo-level tests (src/, scripts/, apps/dashboard/) AND tests on the allowlist.
4. The guard refuses commits that introduce new violations.
5. The allowlist is YAML, version-controlled, and requires a code review to extend — it's the explicit exception list, not a silent override.

## Data flow

### Event 1: developer adds a new skill-specific test under central `tests/`

```
git commit -m "test: cover new ingest behavior"
  └─ .githooks/pre-commit
      └─ scripts/check_skill_test_placement.py
          ├─ scans tests/ for staged/vault skill name refs
          ├─ finds tests/test_new_ingest_thing.py imports
          │  from shared-vault/skills/ingest/scripts/wiki.py
          └─ exit 1, prints:
              "tests/test_new_ingest_thing.py: imports from skill/ingest/scripts/"
              "→ move to shared-vault/skills/ingest/augur/tests/"
              "  OR add to config/system/test_placement_allowlist.yaml if it's a
                  boundary test"
```

### Event 2: developer adds a boundary test that legitimately needs a skill name

```
git commit -m "test: validate vault skill names never leak into src/"
  └─ pre-commit guard fires
  └─ developer adds tests/architecture/test_new_boundary.py to allowlist
  └─ re-commit: passes
```

### Event 3: CI catches a missed pre-commit (force-push, different machine)

Same guard runs in CI. PR build fails with the same actionable message.

## Error handling

| Case | Detection | Response |
|---|---|---|
| Skill name appears in filename outside allowlist | regex on test_file.stem | exit 1, suggest move target or allowlist add |
| Skill scripts path appears in test body | regex on text | exit 1, same message |
| Allowlist references a non-existent file | `path.exists()` on each entry | exit 1, stale-allowlist error |
| New skill added to shared-vault/skills/ without updating discovery | the guard picks it up automatically (it lists vault skills at runtime) | no change needed |
| Allowlist becomes unreviewed sprawl | manual policy: PR review requires sign-off for any allowlist add | not enforced by code |

## Cross-OS behavior

Pure Python via `pathlib`. No shell-specific glob behavior. Works identically on macOS/Linux/Windows. The `.githooks/pre-commit` shebang invokes `uv run python` (already standard in the repo's other githooks).

## Testing strategy

### Layer 1 — Unit tests

`tests/scripts/test_check_skill_test_placement.py`:
- Fixture: tmp_path with a fake `tests/` + `shared-vault/skills/` tree.
- Cases: clean (exit 0), filename violation, body-import violation, allowlist exemption, allowlist with stale entry.

### Layer 2 — Integration

After the guard ships:
- Run `scripts/check_skill_test_placement.py` against the post-migration repo state — should exit 0 cleanly.
- Add a deliberate violation (touch a tests/ file with a skill name) — should exit 1 with the actionable message.
- Verify the pre-commit hook fires on the deliberate violation.

### Layer 3 — Real-data verification (CLAUDE.md rule #34)

On this developer's machine post-migration:
- Run the guard against current main: 0 violations expected.
- Confirm the 31 historically-drifted tests are at their new homes (each passes `uv run pytest <new-path>`).

## Migration (Phase 2 of the implementation plan)

Move 31 files in batches, per-skill, with path-depth updates:

| Skill | Tests to move | New parent depth (parents[N]) |
|---|---:|---|
| ingest | 12 | `parents[4]` (test at shared-vault/skills/ingest/augur/tests/) gives repo root |
| ai | 9 | same |
| daemon | 5 | same |
| knowledge | 3 | same |
| rag | 1 | same |
| platform-admin | 1 | same |

For each test:
1. `git mv tests/<...>/<file>.py shared-vault/skills/<skill>/augur/tests/<file>.py`
2. Update any `Path(__file__).resolve().parents[N]` constants to reflect new depth
3. Update any `from src.X` imports — these typically still work because the test adds `parents[N]` to sys.path
4. Run the test from its new location: `uv run pytest shared-vault/skills/<skill>/augur/tests/<file>.py`
5. If breakage: investigate (may need conftest.py shim in the new dir)

This phase is mechanical but per-file; ~3 hours total. Captured in the implementation plan as parallel-safe per-skill batches.

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Migrated test loses access to src/* imports due to parents[N] depth change | High | Each move includes a runtime verification; new conftest.py shim added at skill's augur/tests/ if needed (same pattern I used for tests/dashboard/python/conftest.py adding src/scripts/ to sys.path) |
| Allowlist grows unbounded over time | Medium | Code review policy; quarterly audit |
| Future skill rename leaves stale skill-name regex in the guard | Low | Guard reads skill names from `shared-vault/skills/` at runtime; rename is automatically picked up |
| pre-commit hook adds friction | Low | Guard runs in <100ms (text scan + dir listing); standard for an Augur githook |

## Future work (out of scope here)

- Same guard for `apps/dashboard/scripts/` (dashboard has its own ownership-boundary issues — see Cluster D website tests for an analogous external-repo leak).
- Reverse direction: detect cases where a skill's `augur/tests/` references something it shouldn't (e.g., another skill's internals).
