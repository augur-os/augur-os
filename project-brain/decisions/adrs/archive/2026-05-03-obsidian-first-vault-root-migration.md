# Obsidian-First Vault Root Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the vault root Obsidian-first by moving inactive staging to tracked `drafts/`, keeping Drafts and Archive Browse-only, and moving obvious root-level data/config into `notes/` and `config/` without activating inactive implementations.

**Architecture:** Code guards land before content moves. Augur path helpers, indexers, discovery, and Browse learn the new `drafts/` and inactive-scope contract first; then the Au-vault repo is moved with `git mv` and verified independently. Runtime state remains outside the vault via existing `get_runtime_dir()` paths.

**Tech Stack:** Python 3.11+ path helpers, pytest, Next.js dashboard TypeScript/Jest tests, git-tracked Au-vault content moves, Augur generated registry/sync checks.

---

## Scope Split

This plan implements the first safe migration slice:

- path contract change from `_drafts/staging` to `drafts/staging`;
- inactive Drafts/Archive Browse behavior;
- audits that prevent draft/archive material from becoming active runtime surface;
- obvious root data/config moves.

Deep item-by-item semantic review remains a separate follow-up for ambiguous roots that cannot be classified from path and content evidence alone. The 2026-05-05 follow-up resolved `apple/`, `growth/`, `content/`, `remote-access/remote-health.yaml`, and `updater/history.yaml`; the remaining ambiguous root is `memory/`.

## File Structure

Modify:

- `src/config/paths.py` - canonical vault root helpers for `drafts/`, `drafts/staging/`, `archive/`, `notes/`, and `config/`.
- `tests/src/test_paths.py` - path-helper regression tests.
- `tests/test_vault_runtime_pollution.py` - string guards for the new drafts path and runtime-state boundary.
- `apps/dashboard/lib/browse/viewModeMapping.ts` - path fallback for Browse Drafts and Archive.
- `tests/dashboard/browse/viewModeMapping.test.ts` - dashboard Browse path mapping tests.
- `src/lib/index/_scanners_structural.py` - vault journey categories and inactive metadata for drafts/archive.
- `skills/platform-admin/scripts/vault_migration_inventory.py` - final root classification for `drafts/`, `archive/`, `config/`, and temporary legacy roots.
- `skills/loop-repo/scripts/vault_hygiene_ops.py` - vault root hygiene allowlist and old `_drafts` warning after migration.
- `tests/unit/test_staged_skill_catalog.py` - staged catalog tests using `drafts/staging`.
- `tests/unit/test_mvp_staging_migration.py` - non-MVP migration tests using `drafts/staging`.
- `tests/src/test_migrate_staging_to_vault_drafts.py` - promotion/migration tests using `drafts/staging`.
- `tests/dashboard/browse/viewModeMapping.test.ts` - TS tests for `drafts/` path matching.
- `docs/creating-skills.md` - documentation path update.
- `docs/references/vault-user-surface-migration-checklist.md` - checklist path update.
- `skills/platform-admin/commands/stage-release.md` - command policy path update.
- `skills/platform-admin/commands/port-release.md` - command policy path update.
- `docs/superpowers/specs/2026-04-23-vault-user-surfaces-phase1-design.md` - mark superseded path details with a pointer to the 2026-05-02 design instead of rewriting history.

Vault content moves in `~/Projects/Au-vault`:

- `_drafts/` -> `drafts/`
- `career-ops/` -> `notes/career/` plus `career-ops/config/` -> `config/career-ops/`
- `books/` -> `notes/books/`
- `reading-list/reading-list.yaml` -> `notes/books/reading-list.yaml`
- `finance/` -> `notes/finance/`
- `health/` -> `notes/health/`
- `venture-augur/` -> `notes/venture/`
- `linkedin-writer/` -> `notes/venture/content/linkedin/`
- `advisor/` -> `notes/augur/advisor/`
- `attention/` -> `config/attention/`
- `dashboard/` -> `config/dashboard/`
- `google-workspace/` -> `config/google-workspace/`
- `file-manager/` -> `config/file-manager/`

Do not move these in this plan:

- `memory/`

---

### Task 1: Update Vault Path Helpers

**Files:**
- Modify: `tests/src/test_paths.py`
- Modify: `src/config/paths.py`
- Modify: `tests/test_vault_runtime_pollution.py`

- [ ] **Step 1: Write failing path-helper tests**

Add this test next to `test_vault_user_surface_helpers_share_vault_root` in `tests/src/test_paths.py`:

```python
def test_obsidian_first_vault_helpers_share_vault_root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: tmp_path / "vault")
    (tmp_path / "vault").mkdir()
    paths.invalidate_project_cache()

    assert paths.get_vault_drafts_dir() == tmp_path / "vault" / "drafts"
    assert paths.get_vault_staging_dir() == tmp_path / "vault" / "drafts" / "staging"
    assert paths.get_vault_archive_dir() == tmp_path / "vault" / "archive"
    assert paths.get_vault_notes_dir() == tmp_path / "vault" / "notes"
    assert paths.get_vault_config_dir() == tmp_path / "vault" / "config"
    assert paths.get_vault_skills_dir() == tmp_path / "vault" / "skills"
```

Update the existing `test_vault_user_surface_helpers_share_vault_root` assertions to expect `drafts` instead of `_drafts`:

```python
assert paths.get_vault_drafts_dir() == tmp_path / "vault" / "drafts"
assert paths.get_vault_staging_dir() == tmp_path / "vault" / "drafts" / "staging"
assert paths.get_vault_skills_dir() == tmp_path / "vault" / "skills"
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run:

```bash
.venv/bin/python -m pytest -q tests/src/test_paths.py::test_obsidian_first_vault_helpers_share_vault_root tests/src/test_paths.py::test_vault_user_surface_helpers_share_vault_root
```

Expected: FAIL because `get_vault_archive_dir`, `get_vault_notes_dir`, or `get_vault_config_dir` is missing, and existing drafts helpers still return `_drafts`.

- [ ] **Step 3: Implement the path helpers**

Replace the current vault draft helper block in `src/config/paths.py` with:

```python
def get_vault_drafts_dir() -> Path:
    return get_vault_dir() / "drafts"


def get_vault_staging_dir() -> Path:
    return get_vault_drafts_dir() / "staging"


def get_vault_archive_dir() -> Path:
    return get_vault_dir() / "archive"


def get_vault_notes_dir() -> Path:
    return get_vault_dir() / "notes"


def get_vault_config_dir() -> Path:
    return get_vault_dir() / "config"


def get_vault_skills_dir() -> Path:
    return get_vault_dir() / "skills"
```

- [ ] **Step 4: Update runtime pollution guard**

In `tests/test_vault_runtime_pollution.py`, update `test_private_skills_and_staging_payloads_resolve_from_vault_not_repo` to assert the new drafts path:

```python
assert 'return get_vault_dir() / "drafts"' in paths
assert 'return get_vault_drafts_dir() / "staging"' in paths
assert 'return get_vault_dir() / "_drafts"' not in paths
assert 'return get_vault_dir() / "skills"' in paths
```

- [ ] **Step 5: Verify tests pass**

Run:

```bash
.venv/bin/python -m pytest -q tests/src/test_paths.py tests/test_vault_runtime_pollution.py
```

Expected: PASS.

- [ ] **Step 6: Commit path helper change**

Run:

```bash
git add src/config/paths.py tests/src/test_paths.py tests/test_vault_runtime_pollution.py
git commit -m "fix(vault): move staging helpers to drafts root"
```

---

### Task 2: Update Staging Catalog And Release Tooling Tests

**Files:**
- Modify: `tests/unit/test_staged_skill_catalog.py`
- Modify: `tests/unit/test_mvp_staging_migration.py`
- Modify: `tests/src/test_migrate_staging_to_vault_drafts.py`
- Modify: `scripts/migrate_staging_to_vault_drafts.py`
- Modify: `scripts/manage_porting_payload.py`
- Modify: `scripts/port_release_into_main.py`
- Modify: `src/lib/staged_skill_catalog.py`
- Modify: `src/lib/mvp_staging_migration.py`

- [ ] **Step 1: Update tests to construct `drafts/staging`**

In the three test files, replace local test roots like:

```python
tmp_path / "vault" / "_drafts" / "staging"
```

with:

```python
tmp_path / "vault" / "drafts" / "staging"
```

In `tests/unit/test_staged_skill_catalog.py`, update the draft skill setup:

```python
vault_staging = tmp_path / "vault" / "drafts" / "staging"
```

and:

```python
draft_skill = tmp_path / "vault" / "drafts" / "staging" / "r3" / "skills" / "draft-only"
```

- [ ] **Step 2: Run catalog and migration tests**

Run:

```bash
.venv/bin/python -m pytest -q tests/unit/test_staged_skill_catalog.py tests/unit/test_mvp_staging_migration.py tests/src/test_migrate_staging_to_vault_drafts.py
```

Expected: PASS, because production code reads `get_vault_staging_dir()` and Task 1 already changed the helper.

- [ ] **Step 3: Update script wording**

In `scripts/migrate_staging_to_vault_drafts.py`, update names and help text only; keep callable function names for compatibility in this task:

```python
"""Move repo staging payloads into the vault drafts/staging tree."""
```

In CLI descriptions and printed text, use:

```text
drafts/staging
```

not:

```text
_drafts/staging
```

Apply the same text-only path wording update in `scripts/manage_porting_payload.py`, `scripts/port_release_into_main.py`, `src/lib/staged_skill_catalog.py`, and `src/lib/mvp_staging_migration.py` comments/docstrings when they mention `_drafts`.

- [ ] **Step 4: Re-run focused tests**

Run:

```bash
.venv/bin/python -m pytest -q tests/unit/test_staged_skill_catalog.py tests/unit/test_mvp_staging_migration.py tests/src/test_migrate_staging_to_vault_drafts.py tests/scripts/test_manage_porting_payload.py tests/scripts/test_port_release_into_main.py
```

Expected: PASS.

- [ ] **Step 5: Commit staging tooling update**

Run:

```bash
git add scripts/migrate_staging_to_vault_drafts.py scripts/manage_porting_payload.py scripts/port_release_into_main.py src/lib/staged_skill_catalog.py src/lib/mvp_staging_migration.py tests/unit/test_staged_skill_catalog.py tests/unit/test_mvp_staging_migration.py tests/src/test_migrate_staging_to_vault_drafts.py
git commit -m "fix(vault): point staging tooling at drafts root"
```

---

### Task 3: Make Drafts And Archive Browse-Only Inactive Scopes

**Files:**
- Modify: `tests/dashboard/browse/viewModeMapping.test.ts`
- Modify: `apps/dashboard/lib/browse/viewModeMapping.ts`
- Modify: `src/lib/index/_scanners_structural.py`
- Modify: `src/lib/index/unified_search.py`
- Create: `tests/lib/index/test_unified_search_inactive_scopes.py`

- [ ] **Step 1: Write failing Browse path tests**

Update `tests/dashboard/browse/viewModeMapping.test.ts`:

```ts
it("matches drafts from vault draft paths before journey metadata exists", () => {
  expect(itemMatchesViewMode({ path: "drafts/staging/draft.md" }, "drafts")).toBe(true);
  expect(itemMatchesViewMode({ path: "_drafts/staging/draft.md" }, "drafts")).toBe(false);
});

it("matches archive from vault archive paths before journey metadata exists", () => {
  expect(itemMatchesViewMode({ path: "archive/career/old.md" }, "archive")).toBe(true);
});
```

- [ ] **Step 2: Run the dashboard test and confirm failure**

Run:

```bash
pnpm --filter dashboard test -- tests/dashboard/browse/viewModeMapping.test.ts --runInBand
```

Expected: FAIL because `drafts` still maps to `_drafts`.

- [ ] **Step 3: Update Browse path mapping**

In `apps/dashboard/lib/browse/viewModeMapping.ts`, change the vault journey root map to:

```ts
const VAULT_JOURNEY_PATH_ROOTS: Partial<Record<ViewMode, string>> = {
  inbox: "inbox",
  notes: "notes",
  sources: "sources",
  drafts: "drafts",
  archive: "archive",
};
```

Remove `"system-metadata"` from `VAULT_JOURNEY_MODES` so a physical `_system` root is no longer treated as a vault journey path.

- [ ] **Step 4: Add inactive metadata to vault index entries**

In `src/lib/index/_scanners_structural.py`, update `_vault_journey_category`:

```python
def _vault_journey_category(vault_file: Path, vault_dir: Path) -> str:
    """Return the operation-mode Browse journey bucket for a vault file."""
    try:
        rel = vault_file.relative_to(vault_dir)
    except ValueError:
        return "other"
    if not rel.parts:
        return "other"
    root = rel.parts[0]
    if root in {"inbox", "notes", "sources", "wiki", "archive", "skills", "drafts"}:
        return root
    return "other"
```

Then add this after `entry_meta` is created in `index_vault`:

```python
        if entry_meta["journey_category"] in {"drafts", "archive"}:
            entry_meta["inactive_scope"] = "true"
            entry_meta["active_search_scope"] = "false"
        else:
            entry_meta["active_search_scope"] = "true"
```

- [ ] **Step 5: Add active search exclusion tests**

Create `tests/lib/index/test_unified_search_inactive_scopes.py`:

```python
from pathlib import Path

from src.lib.index import unified_search


def test_active_search_excludes_vault_drafts_archive_and_legacy_drafts(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    files = {
        "notes/active.md": "needle active note\n",
        "drafts/staging/draft.md": "needle draft\n",
        "archive/career/old.md": "needle archived\n",
        "_drafts/staging/legacy.md": "needle legacy draft\n",
    }
    for rel_path, content in files.items():
        path = vault / rel_path
        path.parent.mkdir(parents=True)
        path.write_text(content, encoding="utf-8")

    hits = unified_search._collect_rg_hits(
        "needle",
        unified_search._ACTIVE_SEARCH_EXCLUDE_GLOBS,
        [vault],
        max_hits=20,
    )
    hit_files = {Path(hit["file"]).relative_to(vault).as_posix() for hit in hits}

    assert "notes/active.md" in hit_files
    assert "drafts/staging/draft.md" not in hit_files
    assert "archive/career/old.md" not in hit_files
    assert "_drafts/staging/legacy.md" not in hit_files
```

- [ ] **Step 6: Update active search globs**

In `src/lib/index/unified_search.py`, add this below `_EXCLUDE_GLOBS`:

```python
_ACTIVE_SEARCH_EXCLUDE_GLOBS: list[str] = [
    *_EXCLUDE_GLOBS,
    "-g", "!drafts/**",
    "-g", "!archive/**",
    "-g", "!_drafts/**",
]
```

Then replace `_EXCLUDE_GLOBS` with `_ACTIVE_SEARCH_EXCLUDE_GLOBS` in the two active content searches inside `_raw_iterative_search`:

```python
priority_hits = _collect_rg_hits(rg_pattern, _ACTIVE_SEARCH_EXCLUDE_GLOBS, priority_dirs)
```

and:

```python
["-g", "!symbols.yaml", "-g", "!*_index.md", *_ACTIVE_SEARCH_EXCLUDE_GLOBS],
```

Leave Browse vault indexing in `index_vault` intact; only active search excludes inactive scopes.

- [ ] **Step 7: Add structural scanner tests**

Create or extend tests in the existing scanner test module that covers `_vault_journey_category`. If no direct test module exists, add this to `tests/unit/test_unified_indexer_vault_journey.py`:

```python
from pathlib import Path

from src.lib.index._scanners_structural import _vault_journey_category


def test_vault_journey_category_uses_drafts_root(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    draft_file = vault / "drafts" / "staging" / "r4" / "skills" / "career-ops" / "SKILL.md"
    legacy_file = vault / "_drafts" / "staging" / "r4" / "skills" / "career-ops" / "SKILL.md"
    archive_file = vault / "archive" / "career" / "old.md"

    assert _vault_journey_category(draft_file, vault) == "drafts"
    assert _vault_journey_category(legacy_file, vault) == "other"
    assert _vault_journey_category(archive_file, vault) == "archive"
```

- [ ] **Step 8: Verify dashboard and Python tests**

Run:

```bash
pnpm --filter dashboard test -- tests/dashboard/browse/viewModeMapping.test.ts --runInBand
.venv/bin/python -m pytest -q tests/unit/test_unified_indexer_vault_journey.py
.venv/bin/python -m pytest -q tests/lib/index/test_unified_search_inactive_scopes.py
```

Expected: PASS.

- [ ] **Step 9: Commit Browse inactive scope update**

Run:

```bash
git add apps/dashboard/lib/browse/viewModeMapping.ts tests/dashboard/browse/viewModeMapping.test.ts src/lib/index/_scanners_structural.py src/lib/index/unified_search.py tests/unit/test_unified_indexer_vault_journey.py tests/lib/index/test_unified_search_inactive_scopes.py
git commit -m "fix(browse): treat drafts and archive as inactive vault scopes"
```

---

### Task 4: Add Discovery And Export Guard Tests

**Files:**
- Modify: `tests/unit/test_skill_discovery_source.py`
- Modify: `tests/sync_agents/test_skill_sync.py`
- Modify: `tests/packages/augur-mcp/tools/test_dynamic_plugin_loader.py`

- [ ] **Step 1: Add skill discovery guard test**

Add this test to `tests/unit/test_skill_discovery_source.py`:

```python
def test_discovery_ignores_vault_drafts_and_archive(monkeypatch, tmp_path):
    from src.plugins import skill_discovery

    repo = tmp_path / "repo"
    vault = tmp_path / "vault"
    repo_skills = repo / "skills"
    vault_skills = vault / "skills"
    draft_skill = vault / "drafts" / "staging" / "r4" / "skills" / "draft-only"
    archived_skill = vault / "archive" / "skills" / "archived-only"

    for skill_dir in (repo_skills / "knowledge", vault_skills / "career-ops", draft_skill, archived_skill):
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"---\nname: {skill_dir.name}\nx-augur-hub: brain\n---\n", encoding="utf-8")

    monkeypatch.setattr(skill_discovery, "get_project_root", lambda: repo)
    monkeypatch.setattr(skill_discovery, "get_managed_skill_source_dirs", lambda project_root=None: [repo_skills, vault_skills])
    skill_discovery.invalidate_discovery_cache()

    names = {record.name for record in skill_discovery.discover_all_skills(tiers=(0,))}

    assert "knowledge" in names
    assert "career-ops" in names
    assert "draft-only" not in names
    assert "archived-only" not in names
```

- [ ] **Step 2: Run discovery guard**

Run:

```bash
.venv/bin/python -m pytest -q tests/unit/test_skill_discovery_source.py::test_discovery_ignores_vault_drafts_and_archive
```

Expected: PASS, because managed skill source dirs should only include repo `skills/` and vault `skills/`.

- [ ] **Step 3: Add sync/export guard**

In `tests/sync_agents/test_skill_sync.py`, replace the existing `_drafts` path in `test_managed_skill_sources_only_reads_returned_roots_and_excludes_draft_elsewhere_in_vault` with:

```python
draft_skill = tmp_path / "vault" / "drafts" / "staging" / "r4" / "skills" / "draft-only"
```

Replace the draft skill frontmatter and assertions in that test with:

```python
(draft_skill / "SKILL.md").write_text(
    "---\nname: draft-only\ndescription: draft-only\n---\n\n# Draft Only\n",
    encoding="utf-8",
)

sources = skill_sync._load_managed_skill_sources(tmp_path / "repo")
exported_names = [name for name, *_ in sources]

assert exported_names == ["ask", "career-ops"]
assert "draft-only" not in exported_names
```

This keeps the existing patch of `get_managed_skill_source_dirs` to `[repo_skills, vault_skills]`.

Also add this generated-export guard below `test_managed_skill_sources_drive_canonical_skill_exports`:

```python
def test_sync_skill_stubs_excludes_vault_drafts(tmp_path, monkeypatch):
    from sync_agents import skill_sync

    repo_root = tmp_path / "repo"
    repo_skills = repo_root / "skills"
    vault_skills = tmp_path / "vault" / "skills"
    draft_skill = tmp_path / "vault" / "drafts" / "staging" / "r4" / "skills" / "draft-only"

    for root, name in ((repo_skills, "ask"), (vault_skills, "career-ops"), (draft_skill.parent, "draft-only")):
        skill_dir = root / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {name}\n---\n\n# {name}\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(skill_sync, "PROJECT_ROOT", repo_root)
    monkeypatch.setattr(
        skill_sync,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [repo_skills, vault_skills],
    )

    captured: dict[str, object] = {}

    def fake_sync_skill_exports(adapters, sources, **kwargs):
        captured["sources"] = sources
        return len(sources)

    monkeypatch.setattr(skill_sync, "_sync_skill_exports", fake_sync_skill_exports)

    written = skill_sync._sync_skill_stubs([SimpleNamespace(adapter_name="claude-code")], cleanup_disabled=False)
    sources = captured["sources"]
    assert isinstance(sources, list)
    exported_names = [name for name, *_ in sources]

    assert written == 2
    assert exported_names == ["ask", "career-ops"]
    assert "draft-only" not in exported_names
```

- [ ] **Step 4: Add dynamic plugin loader guard**

In `tests/packages/augur-mcp/tools/test_dynamic_plugin_loader.py`, add this test below `test_loader_discovers_vault_local_skill_when_repo_skill_absent`:

```python
def test_loader_excludes_vault_draft_skill_roots(tmp_path, monkeypatch):
    repo_skills = tmp_path / "repo" / "skills"
    repo_skills.mkdir(parents=True)
    vault_skills = tmp_path / "vault" / "skills"
    active_skill = vault_skills / "career-ops"
    draft_skill = tmp_path / "vault" / "drafts" / "staging" / "r4" / "skills" / "draft-only"
    _write_skill(
        active_skill,
        hub="career",
        mcp_init_body=(
            "def register_tools(mcp, interceptor, metrics):\n"
            "    mcp.loaded_active_skill = 'career-ops'\n"
        ),
    )
    _write_skill(
        draft_skill,
        hub="career",
        mcp_init_body=(
            "def register_tools(mcp, interceptor, metrics):\n"
            "    mcp.loaded_draft_skill = 'draft-only'\n"
        ),
    )

    from src.mcp.augur_shared import plugin_tools

    monkeypatch.setattr(
        plugin_tools,
        "get_managed_skill_source_dirs",
        lambda: [repo_skills, vault_skills],
    )
    monkeypatch.setattr(plugin_tools, "is_skill_enabled", lambda _: True)

    plugin_tools.reset_plugin_registry()
    mcp = MagicMock()

    loaded = plugin_tools.register_plugin_tools(mcp, lambda f: f, MagicMock())

    assert loaded == 1
    assert mcp.loaded_active_skill == "career-ops"
    assert not hasattr(mcp, "loaded_draft_skill")
```

- [ ] **Step 5: Run export and loader tests**

Run:

```bash
.venv/bin/python -m pytest -q tests/unit/test_skill_discovery_source.py tests/sync_agents/test_skill_sync.py tests/packages/augur-mcp/tools/test_dynamic_plugin_loader.py
```

Expected: PASS.

- [ ] **Step 6: Commit guard tests**

Run:

```bash
git add tests/unit/test_skill_discovery_source.py tests/sync_agents/test_skill_sync.py tests/packages/augur-mcp/tools/test_dynamic_plugin_loader.py
git commit -m "test(vault): prove drafts and archive stay inactive"
```

---

### Task 5: Update Vault Migration And Hygiene Audits

**Files:**
- Modify: `skills/platform-admin/scripts/vault_migration_inventory.py`
- Modify: `skills/loop-repo/scripts/vault_hygiene_ops.py`
- Modify: `skills/platform-admin/augur/tests/test_vault_migration_inventory.py`
- Modify: `skills/loop-repo/augur/tests/test_vault_hygiene_ops.py`

- [ ] **Step 1: Write migration inventory tests**

In `skills/platform-admin/augur/tests/test_vault_migration_inventory.py`, add:

```python
def test_obsidian_first_roots_are_classified_as_in_place(tmp_path: Path):
    inventory = _module()

    vault = tmp_path / "vault"
    paths = [
        vault / "drafts" / "staging" / "r4" / "skills" / "career-ops" / "SKILL.md",
        vault / "archive" / "career" / "old.md",
        vault / "config" / "dashboard" / "active.yaml",
        vault / "notes" / "career" / "cv.md",
    ]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\ntitle: Sample\n---\n", encoding="utf-8")

    classifications = {
        inventory.classify_vault_path(path, vault).relative_path:
        inventory.classify_vault_path(path, vault).classification
        for path in paths
    }

    assert classifications["drafts/staging/r4/skills/career-ops/SKILL.md"] == "inactive_draft_root"
    assert classifications["archive/career/old.md"] == "inactive_archive_root"
    assert classifications["config/dashboard/active.yaml"] == "durable_config_root"
    assert classifications["notes/career/cv.md"] == "active_notes_root"
```

- [ ] **Step 2: Run migration inventory test and confirm failure**

Run:

```bash
.venv/bin/python -m pytest -q skills/platform-admin/augur/tests/test_vault_migration_inventory.py::test_obsidian_first_roots_are_classified_as_in_place
```

Expected: FAIL because current classifications still use `_drafts`, `_system`, and managed skill-name roots.

- [ ] **Step 3: Update migration inventory classifications**

In `skills/platform-admin/scripts/vault_migration_inventory.py`, set:

```python
PROTECTED_ROOTS = {"skills", "wiki", "sources", "drafts"}
USER_ROOTS = {"inbox", "notes", "archive"}
CONFIG_ROOTS = {"config"}
OBSIDIAN_ROOTS = {".obsidian", ".trash"}
```

In `classify_vault_path`, add explicit classifications before the managed-root check:

```python
    if root == "drafts":
        return VaultMigrationItem(rel_text, "inactive_draft_root", "keep_in_place", rel_text)
    if root == "archive":
        return VaultMigrationItem(rel_text, "inactive_archive_root", "keep_in_place", rel_text)
    if root == "notes":
        return VaultMigrationItem(rel_text, "active_notes_root", "keep_in_place", rel_text)
    if root == "config":
        return VaultMigrationItem(rel_text, "durable_config_root", "keep_in_place", rel_text)
```

Keep the managed-root branch for temporary legacy roots while Task 7 moves obvious roots and Task 8 adds the root contract checker:

```python
    if _is_valid_managed_root(root, vault_dir):
        return VaultMigrationItem(rel_text, "temporary_legacy_data_root", "review_for_notes_config_or_archive", rel_text)
```

- [ ] **Step 4: Write vault hygiene root allowlist test**

In `skills/loop-repo/augur/tests/test_vault_hygiene_ops.py`, add:

```python
def test_obsidian_first_root_allowlist_accepts_drafts_archive_config(tmp_path: Path, monkeypatch):
    vault = tmp_path / "vault"
    for root in ("drafts", "archive", "config", "notes", "sources", "wiki", "skills", "inbox"):
        (vault / root).mkdir(parents=True)
    (vault / ".git").mkdir()
    monkeypatch.setattr(mod, "_get_vault", lambda project_root=None: vault)
    monkeypatch.setattr(mod, "check_git_health", lambda vault: [])

    result = mod.scan(_ctx(tmp_path, difficulty=1))

    assert all(issue["file"] != "_drafts" for issue in result.issues)
    assert all(issue["file"] != "drafts" for issue in result.issues)
    assert all(issue["file"] != "archive" for issue in result.issues)
    assert all(issue["file"] != "config" for issue in result.issues)
```

- [ ] **Step 5: Update vault hygiene allowlist**

In `skills/loop-repo/scripts/vault_hygiene_ops.py`, replace:

```python
ALLOWED_TOP_DIRS = {"config", "memory", "dev", ".git", "_drafts", "skills", "sources", "wiki"}
```

with:

```python
ALLOWED_TOP_DIRS = {"inbox", "notes", "sources", "wiki", "skills", "drafts", "archive", "config", ".git"}
LEGACY_TOP_DIRS = {"_drafts", "_system"}
```

In `_is_valid_top_dir`, add:

```python
    if name in LEGACY_TOP_DIRS:
        return False
```

Keep the `validate_dir_name` fallback until Task 8 removes legacy data roots.

- [ ] **Step 6: Verify audit tests**

Run:

```bash
.venv/bin/python -m pytest -q skills/platform-admin/augur/tests/test_vault_migration_inventory.py skills/loop-repo/augur/tests/test_vault_hygiene_ops.py
```

Expected: PASS.

- [ ] **Step 7: Commit audit update**

Run:

```bash
git add skills/platform-admin/scripts/vault_migration_inventory.py skills/loop-repo/scripts/vault_hygiene_ops.py skills/platform-admin/augur/tests/test_vault_migration_inventory.py skills/loop-repo/augur/tests/test_vault_hygiene_ops.py
git commit -m "fix(vault): classify obsidian root contract"
```

---

### Task 6: Update Documentation And Command Policy Paths

**Files:**
- Modify: `docs/creating-skills.md`
- Modify: `docs/references/vault-user-surface-migration-checklist.md`
- Modify: `skills/platform-admin/commands/stage-release.md`
- Modify: `skills/platform-admin/commands/port-release.md`
- Modify: `docs/superpowers/specs/2026-04-23-vault-user-surfaces-phase1-design.md`

- [ ] **Step 1: Replace old staging path text**

Replace prose references to:

```text
get_vault_dir()/_drafts/staging/
_drafts/staging/
```

with:

```text
get_vault_dir()/drafts/staging/
drafts/staging/
```

In `docs/superpowers/specs/2026-04-23-vault-user-surfaces-phase1-design.md`, add this note under `## Summary`:

```markdown
> Superseded path note: the 2026-05-02 Obsidian-first vault root design replaces `_drafts/staging/` with tracked `drafts/staging/`. The ownership model remains: inactive drafts are not discovered or exported; active private skill implementations live under `skills/`.
```

- [ ] **Step 2: Run reference search**

Run:

```bash
rg -n "_drafts/staging|get_vault_dir\\(\\)/_drafts|vault/_drafts" docs skills scripts src tests apps
```

Expected: Remaining matches are historical references in old design docs with the superseded note, or tests intentionally checking legacy paths are not active.

- [ ] **Step 3: Commit docs update**

Run:

```bash
git add docs/creating-skills.md docs/references/vault-user-surface-migration-checklist.md skills/platform-admin/commands/stage-release.md skills/platform-admin/commands/port-release.md docs/superpowers/specs/2026-04-23-vault-user-surfaces-phase1-design.md
git commit -m "docs(vault): update staging path to drafts"
```

---

### Task 7: Move Vault Drafts And Obvious Data Roots

**Files:**
- Modify in `~/Projects/Au-vault`: tracked vault content only.

- [ ] **Step 1: Confirm code side is clean enough for vault move**

Run:

```bash
git status --short --branch
git -C ~/Projects/Au-vault status --short --branch
```

Expected: Augur may contain unrelated user edits, but no unstaged changes from Tasks 1-6. Au-vault must not contain uncommitted changes except known user files that are excluded from this migration.

- [ ] **Step 2: Rename `_drafts` to `drafts`**

Run:

```bash
VAULT=~/Projects/Au-vault
if [ -d "$VAULT/_drafts" ] && [ ! -e "$VAULT/drafts" ]; then
  git -C "$VAULT" mv _drafts drafts
fi
```

Expected: `git -C "$VAULT" status --short` shows `R` entries from `_drafts/...` to `drafts/...`.

- [ ] **Step 3: Create target root folders**

Run:

```bash
VAULT=~/Projects/Au-vault
mkdir -p "$VAULT/notes" "$VAULT/config" "$VAULT/archive" "$VAULT/inbox"
```

Expected: top-level parent directories exist. Do not pre-create `notes/career`, `notes/books`, `notes/finance`, `notes/health`, or `notes/venture`; `git mv old-root notes/new-root` must create those final directory names as renames instead of nesting old roots one level deeper.

- [ ] **Step 4: Move obvious human note/data roots**

Run:

```bash
VAULT=~/Projects/Au-vault
git -C "$VAULT" mv career-ops/config config/career-ops
git -C "$VAULT" mv career-ops notes/career
git -C "$VAULT" mv books notes/books
git -C "$VAULT" mv finance notes/finance
git -C "$VAULT" mv health notes/health
git -C "$VAULT" mv venture-augur notes/venture
mkdir -p "$VAULT/notes/venture/content"
git -C "$VAULT" mv linkedin-writer notes/venture/content/linkedin
mkdir -p "$VAULT/notes/augur"
git -C "$VAULT" mv advisor notes/augur/advisor
```

Expected: the moved roots no longer exist at vault root, and files are still tracked as renames.

- [ ] **Step 5: Move obvious config roots**

Run:

```bash
VAULT=~/Projects/Au-vault
git -C "$VAULT" mv attention config/attention
git -C "$VAULT" mv dashboard config/dashboard
git -C "$VAULT" mv google-workspace config/google-workspace
git -C "$VAULT" mv file-manager config/file-manager
```

Expected: these roots no longer exist at vault root.

- [ ] **Step 6: Move reading list into books notes**

Run:

```bash
VAULT=~/Projects/Au-vault
git -C "$VAULT" mv reading-list/reading-list.yaml notes/books/reading-list.yaml
rmdir "$VAULT/reading-list"
```

Expected: `reading-list/` is gone.

- [ ] **Step 7: Update vault reserved roots**

Overwrite `~/Projects/Au-vault/.augur-reserved` with:

```text
# Structural directories - not skill-aligned
inbox
notes
sources
wiki
skills
drafts
archive
config

# Temporary migration roots requiring item review
apple
content
growth
memory
updater
remote-access
```

Use an editor or `apply_patch` from the Augur session. Do not remove temporary roots until their contents are classified.

- [ ] **Step 8: Check vault diff**

Run:

```bash
git -C ~/Projects/Au-vault diff --cached --check
git -C ~/Projects/Au-vault status --short | sed -n '1,160p'
```

Expected: no whitespace errors; status shows renames and `.augur-reserved` modification only.

- [ ] **Step 9: Commit vault move**

Run:

```bash
git -C ~/Projects/Au-vault add -A
git -C ~/Projects/Au-vault diff --cached --check
git -C ~/Projects/Au-vault commit -m "chore(vault): move obvious data into obsidian roots"
```

Expected: commit succeeds with mostly rename entries.

---

### Task 8: Add Root Inventory Verification

**Files:**
- Create: `scripts/check_obsidian_vault_roots.py`
- Create: `tests/scripts/test_check_obsidian_vault_roots.py`

- [ ] **Step 1: Write failing root-check tests**

Create `tests/scripts/test_check_obsidian_vault_roots.py`:

```python
from pathlib import Path

from scripts.check_obsidian_vault_roots import check_disallowed_skill_markdown, check_vault_roots


def test_check_vault_roots_accepts_final_and_temporary_roots(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    for root in ("inbox", "notes", "sources", "wiki", "skills", "drafts", "archive", "config", "apple"):
        (vault / root).mkdir(parents=True)

    result = check_vault_roots(vault, temporary_roots={"apple"})

    assert result == []


def test_check_vault_roots_reports_unapproved_root(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "career-ops").mkdir(parents=True)

    result = check_vault_roots(vault, temporary_roots=set())

    assert result == ["career-ops"]


def test_check_disallowed_skill_markdown_reports_inactive_or_note_roots(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    allowed_active = vault / "skills" / "career-ops" / "SKILL.md"
    allowed_draft = vault / "drafts" / "staging" / "r4" / "skills" / "draft-only" / "SKILL.md"
    disallowed_note = vault / "notes" / "career" / "SKILL.md"
    disallowed_archive = vault / "archive" / "career" / "old-skill" / "SKILL.md"
    disallowed_config = vault / "config" / "career-ops" / "SKILL.md"

    for path in (allowed_active, allowed_draft, disallowed_note, disallowed_archive, disallowed_config):
        path.parent.mkdir(parents=True)
        path.write_text("---\nname: sample\n---\n", encoding="utf-8")

    result = check_disallowed_skill_markdown(vault)

    assert result == [
        "archive/career/old-skill/SKILL.md",
        "config/career-ops/SKILL.md",
        "notes/career/SKILL.md",
    ]
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```bash
.venv/bin/python -m pytest -q tests/scripts/test_check_obsidian_vault_roots.py
```

Expected: FAIL because `scripts/check_obsidian_vault_roots.py` does not exist.

- [ ] **Step 3: Implement root checker**

Create `scripts/check_obsidian_vault_roots.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.paths import get_vault_dir  # noqa: E402

FINAL_ROOTS = {"inbox", "notes", "sources", "wiki", "skills", "drafts", "archive", "config"}
DEFAULT_TEMPORARY_ROOTS = {"apple", "content", "growth", "memory", "updater", "remote-access"}
SKILL_MD_ALLOWED_ROOTS = {"skills", "drafts"}


def check_vault_roots(vault_dir: Path, *, temporary_roots: set[str] | None = None) -> list[str]:
    allowed = set(FINAL_ROOTS)
    allowed.update(temporary_roots if temporary_roots is not None else DEFAULT_TEMPORARY_ROOTS)
    unexpected: list[str] = []
    for entry in sorted(vault_dir.iterdir(), key=lambda item: item.name):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if entry.name not in allowed:
            unexpected.append(entry.name)
    return unexpected


def check_disallowed_skill_markdown(vault_dir: Path) -> list[str]:
    disallowed: list[str] = []
    for skill_md in sorted(vault_dir.rglob("SKILL.md")):
        rel = skill_md.relative_to(vault_dir)
        root = rel.parts[0] if rel.parts else ""
        if root not in SKILL_MD_ALLOWED_ROOTS:
            disallowed.append(rel.as_posix())
    return disallowed


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Au-vault root folders against the Obsidian-first contract.")
    parser.add_argument("--vault", type=Path, default=get_vault_dir())
    parser.add_argument("--strict", action="store_true", help="Disallow temporary migration roots.")
    args = parser.parse_args()

    temporary = set() if args.strict else DEFAULT_TEMPORARY_ROOTS
    unexpected = check_vault_roots(args.vault, temporary_roots=temporary)
    disallowed_skill_md = check_disallowed_skill_markdown(args.vault)
    if unexpected or disallowed_skill_md:
        if unexpected:
            print("Unexpected vault roots:")
            for root in unexpected:
                print(f"- {root}")
        if disallowed_skill_md:
            print("Disallowed SKILL.md locations:")
            for rel_path in disallowed_skill_md:
                print(f"- {rel_path}")
        return 1
    print("Vault roots match Obsidian-first contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Verify root checker**

Run:

```bash
.venv/bin/python -m pytest -q tests/scripts/test_check_obsidian_vault_roots.py
python3 scripts/check_obsidian_vault_roots.py
```

Expected: tests pass; live check passes while temporary roots remain listed in `DEFAULT_TEMPORARY_ROOTS`.

- [ ] **Step 5: Commit root checker**

Run:

```bash
git add scripts/check_obsidian_vault_roots.py tests/scripts/test_check_obsidian_vault_roots.py
git commit -m "test(vault): add obsidian root contract check"
```

---

### Task 9: Full Verification And Generated Surface Checks

**Files:**
- No intended source edits unless a generated check reports stale output.

- [ ] **Step 1: Run Python test slice**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/src/test_paths.py \
  tests/test_vault_runtime_pollution.py \
  tests/unit/test_staged_skill_catalog.py \
  tests/unit/test_mvp_staging_migration.py \
  tests/src/test_migrate_staging_to_vault_drafts.py \
  tests/scripts/test_manage_porting_payload.py \
  tests/scripts/test_port_release_into_main.py \
  tests/unit/test_skill_discovery_source.py \
  tests/sync_agents/test_skill_sync.py \
  tests/packages/augur-mcp/tools/test_dynamic_plugin_loader.py \
  tests/lib/index/test_unified_search_inactive_scopes.py \
  tests/scripts/test_check_obsidian_vault_roots.py \
  skills/platform-admin/augur/tests/test_vault_migration_inventory.py \
  skills/loop-repo/augur/tests/test_vault_hygiene_ops.py
```

Expected: PASS.

- [ ] **Step 2: Run dashboard Browse test**

Run:

```bash
pnpm --filter dashboard test -- tests/dashboard/browse/viewModeMapping.test.ts --runInBand
```

Expected: PASS.

- [ ] **Step 3: Check generated surfaces**

Run:

```bash
python3 -m skills.ai.scripts.sync_agents check
python3 apps/dashboard/scripts/generate_registry.py --check --quiet
python3 apps/dashboard/scripts/generate_registry.py --check --quiet
```

Expected: sync agents up to date; registry up to date. The duplicate registry check catches accidental generation drift after the first check warms runtime state.

- [ ] **Step 4: Run live vault root and hygiene checks**

Run:

```bash
python3 scripts/check_obsidian_vault_roots.py
python3 - <<'PY'
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
from src.lib.ops_protocol import OpsContext

module_path = Path('skills/loop-repo/scripts/vault_hygiene_ops.py')
spec = spec_from_file_location('vault_hygiene_ops', module_path)
module = module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
result = module.scan(OpsContext(project_root=Path.cwd(), difficulty=1))
print(result.health, result.severity, result.summary)
for issue in result.issues:
    print(issue.get('severity'), issue.get('kind'), issue.get('file'), '-', issue.get('message'))
raise SystemExit(0 if result.health == 'verified' else 1)
PY
```

Expected: root contract check passes; vault hygiene reports `verified`.

- [ ] **Step 5: Check repo diffs**

Run:

```bash
git diff --check
git -C ~/Projects/Au-vault diff --check
git status --short --branch
git -C ~/Projects/Au-vault status --short --branch
```

Expected: no whitespace errors. Augur and Au-vault may each be ahead by local commits; unrelated pre-existing dirty files in Augur remain uncommitted and are reported separately.

- [ ] **Step 6: Push only after verification passes**

Run:

```bash
git push
git -C ~/Projects/Au-vault push
```

Expected: both repos push cleanly.

- [ ] **Step 7: Final remote alignment**

Run:

```bash
git fetch origin main --quiet
git rev-list --left-right --count main...origin/main
git -C ~/Projects/Au-vault fetch origin main --quiet
git -C ~/Projects/Au-vault rev-list --left-right --count main...origin/main
python3 skills/platform-admin/scripts/dev_merge_purge.py status
python3 skills/platform-admin/scripts/merge_lock.py status
```

Expected:

```text
0	0
0	0
{
  "candidates": []
}
UNLOCKED
```

---

## Implementation Notes

- Do not remove `skills/`; it is runtime-sensitive and remains the active private skill source container.
- Do not move ambiguous roots in the first content pass.
- Do not treat `drafts/` as a git-ignored folder. It is tracked but inactive.
- Do not put runtime indexes, caches, sessions, or generated histories into `config/`.
- Do not use `git reset --hard`, `git checkout --`, or destructive cleanup on unrelated dirty files.
- Stage and commit Augur code changes separately from Au-vault content moves.
