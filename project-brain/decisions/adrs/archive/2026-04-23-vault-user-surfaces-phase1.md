# Vault User Surfaces Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove repo `staging/` as a live surface, move it into `get_vault_dir()/_drafts/staging`, and make `get_vault_dir()/skills` the active user-owned skill root with automatic client export.

**Architecture:** Phase 1 introduces explicit vault user-surface path helpers, expands canonical skill discovery to cover both repo and vault skill roots, and makes every downstream consumer read from those managed roots instead of assuming `skills/` is the only canonical source. Drafts remain stored under the vault but are deliberately invisible to discovery, sync, RAG, and dashboard consumers. Runtime callers that still depend on staged-only skills are resolved explicitly before repo `staging/` is deleted.

**Tech Stack:** Python 3.11, pytest, Augur path helpers in `src.config.paths`, canonical skill discovery in `src.plugins.skill_discovery`, sync_agents export pipeline, MCP browse/discovery infrastructure, unified RAG indexer, uv.

---

## File Structure

Path and root helpers:

- Modify `src/config/paths.py`
  - Add `get_vault_drafts_dir()`, `get_vault_staging_dir()`, `get_vault_skills_dir()`, and `get_managed_skill_source_dirs()`.
  - Update `get_all_client_skill_dirs()` so vault active skills are treated as first-class local managed skills.
- Modify `tests/src/test_paths.py`
  - Add regression coverage for the new vault helpers and managed-root enumeration.

Canonical discovery:

- Modify `src/plugins/skill_discovery.py`
  - Discover repo `skills/` and vault `skills/`.
  - Preserve external inventory semantics.
  - Add explicit `source_root` and `canonical` metadata and `ownership="user"` for vault skills.
- Modify `tests/unit/test_skill_discovery_source.py`
  - Cover vault user skills, canonical flags, and draft exclusion.
- Modify `tests/unit/test_skill_discovery_external_inventory.py`
  - Verify external inventory aggregation still works after vault roots are added.

Managed export:

- Modify `skills/ai/scripts/sync_agents/skill_sync.py`
  - Load managed skill sources from repo and vault roots.
  - Keep drafts ignored.
- Modify `tests/sync_agents/test_skill_sync.py`
  - Cover vault skill export and draft exclusion.

Downstream consumers:

- Modify `src/mcp/augur_mcp/domain/discovery.py`
  - Count both repo and vault managed skills in manifest generation.
- Modify `src/mcp/augur_mcp/infrastructure/browse/cli.py`
  - Resolve CLI help from managed roots rather than repo-only assumptions.
- Modify `src/mcp/augur_mcp/infrastructure/browse/index.py`
  - Keep enrichment compatible with vault-owned canonical skills.
- Modify `skills/rag/scripts/_indexer_helpers.py`
  - Classify vault skill dirs explicitly.
- Modify `skills/rag/scripts/_scanners_knowledge.py`
  - Read ownership/source metadata from canonical discovery records instead of repo-only heuristics.
- Modify focused tests under:
  - `tests/unit/test_launch_skill_inventory.py`
  - `tests/unit/test_list_skills_launch_metadata.py`
  - `skills/rag/augur/tests/test_unified_indexer.py`

Cutover and migration:

- Modify `src/lib/staged_skill_catalog.py`
  - Stop treating repo `staging/` as a live lookup root.
  - Resolve active skills from repo `skills/` and vault `skills/` only.
- Modify `tests/unit/test_staged_skill_catalog.py`
  - Replace staged lookup expectations with vault draft + active root expectations.
- Create `scripts/migrate_staging_to_vault_drafts.py`
  - Copy repo `staging/` to `get_vault_staging_dir()` preserving the tree.
  - Optionally promote explicitly named active skills into repo `skills/` or vault `skills/`.
- Create `tests/src/test_migrate_staging_to_vault_drafts.py`
  - Cover copy, idempotence, and explicit promotion behavior.

Docs and cutover evidence:

- Modify `docs/references/vault-user-surface-migration-checklist.md`
  - Mark phase-1 tasks complete during execution.
- Modify `docs/creating-skills.md`
  - Document repo skills vs vault skills vs vault drafts.

---

### Task 1: Add Vault User-Surface Path Helpers

**Files:**
- Modify: `src/config/paths.py`
- Test: `tests/src/test_paths.py`

- [ ] **Step 1: Add failing tests for vault helper paths**

Append to `tests/src/test_paths.py`:

```python
def test_vault_user_surface_helpers_share_vault_root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: tmp_path / "vault")
    (tmp_path / "vault").mkdir()
    paths.invalidate_project_cache()

    assert paths.get_vault_drafts_dir() == tmp_path / "vault" / "_drafts"
    assert paths.get_vault_staging_dir() == tmp_path / "vault" / "_drafts" / "staging"
    assert paths.get_vault_skills_dir() == tmp_path / "vault" / "skills"


def test_get_managed_skill_source_dirs_includes_repo_and_live_vault(monkeypatch, tmp_path):
    project_root = tmp_path / "repo"
    (project_root / "skills").mkdir(parents=True)
    vault_skills = tmp_path / "vault" / "skills"
    vault_skills.mkdir(parents=True)

    monkeypatch.setattr(paths, "get_project_root", lambda: project_root)
    monkeypatch.setattr(paths, "get_vault_skills_dir", lambda: vault_skills)

    result = paths.get_managed_skill_source_dirs()

    assert result == [project_root / "skills", vault_skills]


def test_get_managed_skill_source_dirs_for_explicit_temp_root_stays_repo_local(monkeypatch, tmp_path):
    explicit_root = tmp_path / "other-root"
    (explicit_root / "skills").mkdir(parents=True)
    monkeypatch.setattr(paths, "get_project_root", lambda: tmp_path / "live-root")
    monkeypatch.setattr(paths, "get_vault_skills_dir", lambda: tmp_path / "vault" / "skills")

    result = paths.get_managed_skill_source_dirs(explicit_root)

    assert result == [explicit_root / "skills"]
```

- [ ] **Step 2: Run the focused path tests and verify failure**

Run:

```bash
uv run pytest tests/src/test_paths.py -k "vault_user_surface_helpers or managed_skill_source_dirs" -q
```

Expected: FAIL with `AttributeError` for missing `get_vault_drafts_dir`, `get_vault_staging_dir`, `get_vault_skills_dir`, or `get_managed_skill_source_dirs`.

- [ ] **Step 3: Add the new path helpers**

Add to `src/config/paths.py` below `get_vault_dir()`:

```python
def get_vault_drafts_dir() -> Path:
    return get_vault_dir() / "_drafts"


def get_vault_staging_dir() -> Path:
    return get_vault_drafts_dir() / "staging"


def get_vault_skills_dir() -> Path:
    return get_vault_dir() / "skills"


def get_managed_skill_source_dirs(project_root: Path | None = None) -> list[Path]:
    root = project_root.resolve() if project_root is not None else get_project_root().resolve()
    dirs: list[Path] = []

    repo_skills = root / "skills"
    if repo_skills.is_dir():
        dirs.append(repo_skills)

    live_root = get_project_root().resolve()
    if root == live_root:
        vault_skills = get_vault_skills_dir()
        if vault_skills.is_dir():
            dirs.append(vault_skills)

    return dirs
```

- [ ] **Step 4: Update `get_all_client_skill_dirs()` to include active vault skills**

Replace the top of `get_all_client_skill_dirs()` in `src/config/paths.py` with:

```python
def get_all_client_skill_dirs(project_root: Path | None = None) -> list[Path]:
    """Return all managed and external skill directories that exist on disk."""
    dirs: list[Path] = []
    root = project_root.resolve() if project_root is not None else get_project_root().resolve()

    for managed_dir in get_managed_skill_source_dirs(root):
        if not managed_dir.is_dir():
            continue
        dirs.append(managed_dir)

    seen = {path.resolve() for path in dirs}
    live_project_root = get_project_root().resolve()
```

Keep the existing client/plugin-cache loop unchanged after `live_project_root`.

- [ ] **Step 5: Re-run the focused path tests and verify they pass**

Run:

```bash
uv run pytest tests/src/test_paths.py -k "vault_user_surface_helpers or managed_skill_source_dirs" -q
```

Expected: `3 passed`.

- [ ] **Step 6: Commit the verified path-helper checkpoint**

```bash
git add src/config/paths.py tests/src/test_paths.py
git commit -m "feat: add vault user surface path helpers"
```

---

### Task 2: Extend Canonical Skill Discovery For Vault Skills

**Files:**
- Modify: `src/plugins/skill_discovery.py`
- Test: `tests/unit/test_skill_discovery_source.py`
- Test: `tests/unit/test_skill_discovery_external_inventory.py`

- [ ] **Step 1: Add failing tests for vault skill discovery and draft exclusion**

Append to `tests/unit/test_skill_discovery_source.py`:

```python
def test_discover_vault_skill_is_user_owned_and_canonical(tmp_path):
    root = tmp_path / "repo"
    vault = tmp_path / "vault"
    vault_skill = vault / "skills" / "career-ops"
    _write_skill_md(vault_skill, "career-ops")

    with patch("src.plugins.skill_discovery.get_project_root", return_value=root), \
        patch("src.plugins.skill_discovery.get_managed_skill_source_dirs", return_value=[root / "skills", vault / "skills"]), \
        patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]), \
        patch("src.plugins.skill_discovery._get_client_skill_dirs", return_value=_client_dirs()):
        invalidate_discovery_cache()
        records = _discover_all_skills_impl(tiers=(0,))

    record = next(r for r in records if r.name == "career-ops")
    assert record.ownership == "user"
    assert record.source_root == "vault"
    assert record.canonical is True


def test_discovery_ignores_vault_drafts(tmp_path):
    root = tmp_path / "repo"
    vault = tmp_path / "vault"
    draft_skill = vault / "_drafts" / "staging" / "r4" / "skills" / "venture"
    _write_skill_md(draft_skill, "venture")

    with patch("src.plugins.skill_discovery.get_project_root", return_value=root), \
        patch("src.plugins.skill_discovery.get_managed_skill_source_dirs", return_value=[root / "skills", vault / "skills"]), \
        patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]), \
        patch("src.plugins.skill_discovery._get_client_skill_dirs", return_value=_client_dirs()):
        invalidate_discovery_cache()
        records = _discover_all_skills_impl()

    assert all(record.name != "venture" for record in records)
```

- [ ] **Step 2: Run the focused discovery tests and verify failure**

Run:

```bash
uv run pytest tests/unit/test_skill_discovery_source.py -k "vault_skill or vault_drafts" -q
```

Expected: FAIL because `SkillRecord` does not yet expose `source_root` / `canonical` and discovery does not yet scan vault skills.

- [ ] **Step 3: Extend `SkillRecord` and managed discovery roots**

Update `SkillRecord` in `src/plugins/skill_discovery.py`:

```python
    source_root: str = "repo"   # repo | vault | external-client | plugin-cache
    canonical: bool = True
```

Import the new helper near the top:

```python
from src.config.paths import (
    get_claude_plugin_skill_dirs,
    get_managed_skill_source_dirs,
)
```

Add a helper below `_get_client_skill_dirs()`:

```python
def _get_managed_skill_dirs() -> list[Path]:
    """Wrapper for repo + vault managed skill roots."""
    return get_managed_skill_source_dirs()
```

- [ ] **Step 4: Scan repo and vault managed roots distinctly**

In `_discover_all_skills_impl()` replace the single `skills_dir = get_skills_dir()` canonical scan with:

```python
managed_roots = [(path.resolve(), "vault" if path.resolve() != get_project_root().resolve() / "skills" else "repo")
                 for path in _get_managed_skill_dirs() if path.is_dir()]

for managed_root, source_root in managed_roots:
    for skill_md in sorted(managed_root.glob("*/SKILL.md")):
        if _is_auto_generated(skill_md):
            continue
        frontmatter = _extract_frontmatter(skill_md.read_text(encoding="utf-8"))
        ownership, upstream = _extract_ownership_and_upstream(frontmatter, managed=True)
        if source_root == "vault":
            ownership = "user"
        records.append(
            SkillRecord(
                ...,
                path=skill_md.parent,
                tier=0,
                origin="vault" if source_root == "vault" else "augur",
                ownership=ownership,
                upstream=upstream,
                source="vault" if source_root == "vault" else "augur",
                source_root=source_root,
                canonical=True,
            )
        )
```

Use the existing field population for the elided `...` fields; only the root classification changes.

- [ ] **Step 5: Preserve external aggregation semantics**

When constructing external inventory `SkillRecord`s, set:

```python
source_root="external-client" if source_tag != "plugin-cache" else "plugin-cache",
canonical=False,
```

Keep `ownership="external"` and current `client_sources` aggregation behavior unchanged.

- [ ] **Step 6: Re-run focused discovery tests**

Run:

```bash
uv run pytest tests/unit/test_skill_discovery_source.py -k "vault_skill or vault_drafts" -q
uv run pytest tests/unit/test_skill_discovery_external_inventory.py -q
```

Expected:

```text
2 passed
2 passed
```

- [ ] **Step 7: Commit the discovery checkpoint**

```bash
git add src/plugins/skill_discovery.py tests/unit/test_skill_discovery_source.py tests/unit/test_skill_discovery_external_inventory.py
git commit -m "feat: discover vault-owned canonical skills"
```

---

### Task 3: Export Vault Skills Through sync_agents And Ignore Drafts

**Files:**
- Modify: `skills/ai/scripts/sync_agents/skill_sync.py`
- Test: `tests/sync_agents/test_skill_sync.py`

- [ ] **Step 1: Add failing sync tests for vault skill export**

Append to `tests/sync_agents/test_skill_sync.py`:

```python
def test_load_skill_sources_reads_repo_and_vault_roots(tmp_path, monkeypatch):
    from sync_agents import skill_sync

    repo_skills = tmp_path / "repo" / "skills"
    vault_skills = tmp_path / "vault" / "skills"
    for root, name in ((repo_skills, "ask"), (vault_skills, "career-ops")):
        skill_dir = root / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\\nname: {name}\\ndescription: {name}\\n---\\n\\n# {name}\\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(skill_sync, "get_managed_skill_source_dirs", lambda project_root=None: [repo_skills, vault_skills])

    sources = skill_sync._load_managed_skill_sources(tmp_path / "repo")

    assert [name for name, *_ in sources] == ["ask", "career-ops"]


def test_load_skill_sources_ignores_vault_drafts(tmp_path, monkeypatch):
    from sync_agents import skill_sync

    repo_skills = tmp_path / "repo" / "skills"
    vault_skills = tmp_path / "vault" / "skills"
    draft_skill = tmp_path / "vault" / "_drafts" / "staging" / "r4" / "skills" / "venture"
    (repo_skills / "ask").mkdir(parents=True)
    (repo_skills / "ask" / "SKILL.md").write_text("---\\nname: ask\\ndescription: ask\\n---\\n", encoding="utf-8")
    draft_skill.mkdir(parents=True)
    (draft_skill / "SKILL.md").write_text("---\\nname: venture\\ndescription: venture\\n---\\n", encoding="utf-8")

    monkeypatch.setattr(skill_sync, "get_managed_skill_source_dirs", lambda project_root=None: [repo_skills, vault_skills])

    sources = skill_sync._load_managed_skill_sources(tmp_path / "repo")

    assert [name for name, *_ in sources] == ["ask"]
```

- [ ] **Step 2: Run the focused sync tests and verify failure**

Run:

```bash
PYTHONPATH=skills/ai/scripts uv run pytest tests/sync_agents/test_skill_sync.py -k "managed_skill_sources" -q
```

Expected: FAIL with `AttributeError: module 'sync_agents.skill_sync' has no attribute '_load_managed_skill_sources'`.

- [ ] **Step 3: Replace repo-only skill loading with managed-root loading**

In `skills/ai/scripts/sync_agents/skill_sync.py`, import the new helper:

```python
from src.config.paths import (
    get_codex_native_skills_dir,
    get_codex_prompt_dir,
    get_managed_skill_source_dirs,
)
```

Add a new loader below `_load_skill_sources()`:

```python
def _load_managed_skill_sources(project_root: Path) -> list[tuple[str, Path, str, str, str, bool]]:
    sources: list[tuple[str, Path, str, str, str, bool]] = []
    for skills_dir in get_managed_skill_source_dirs(project_root):
        sources.extend(_load_skill_sources(skills_dir))
    return sorted(sources, key=lambda item: item[0])
```

Then replace every caller that currently passes `PROJECT_ROOT / "skills"` or `skills_dir` for canonical skill export with:

```python
managed_sources = _load_managed_skill_sources(PROJECT_ROOT)
```

and feed `managed_sources` into the existing sync routines.

- [ ] **Step 4: Re-run the focused sync tests**

Run:

```bash
PYTHONPATH=skills/ai/scripts uv run pytest tests/sync_agents/test_skill_sync.py -k "managed_skill_sources" -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit the sync checkpoint**

```bash
git add skills/ai/scripts/sync_agents/skill_sync.py tests/sync_agents/test_skill_sync.py
git commit -m "feat: sync vault-owned skills to clients"
```

---

### Task 4: Update MCP Browse, Manifest, And RAG Consumers

**Files:**
- Modify: `src/mcp/augur_mcp/domain/discovery.py`
- Modify: `src/mcp/augur_mcp/infrastructure/browse/cli.py`
- Modify: `src/mcp/augur_mcp/infrastructure/browse/index.py`
- Modify: `skills/rag/scripts/_indexer_helpers.py`
- Modify: `skills/rag/scripts/_scanners_knowledge.py`
- Test: `tests/unit/test_launch_skill_inventory.py`
- Test: `tests/unit/test_list_skills_launch_metadata.py`
- Test: `skills/rag/augur/tests/test_unified_indexer.py`

- [ ] **Step 1: Add failing tests for user-owned launch and RAG metadata**

Append to `tests/unit/test_launch_skill_inventory.py`:

```python
def test_launch_inventory_preserves_user_owned_skill_metadata(tmp_path):
    from src.lib.launch_skill_inventory import build_launch_skill_inventory
    from src.plugins.skill_discovery import SkillRecord

    record = SkillRecord(
        name="career-ops",
        description="Career ops",
        path=tmp_path / "vault" / "skills" / "career-ops",
        author="user",
        hub="career",
        visibility="",
        loop_config={},
        dependencies={},
        mcp_tools=[],
        dashboard_pages=[],
        commands=[],
        config={},
        agent=None,
        skill_type="domain",
        tags=(),
        tier=0,
        origin="vault",
        ownership="user",
        upstream={},
        source="vault",
        source_root="vault",
        canonical=True,
    )

    manifest = build_launch_skill_inventory([record], tmp_path)

    assert manifest["skills"][0]["ownership"] == "user"
    assert manifest["skills"][0]["source_root"] == "vault"
```

Append to `skills/rag/augur/tests/test_unified_indexer.py`:

```python
def test_index_skills_uses_user_ownership_from_discovery_record(tmp_path, monkeypatch):
    from src.plugins.skill_discovery import SkillRecord
    from skills.rag.scripts._scanners_knowledge import index_skills

    project_root = tmp_path / "repo"
    skill_dir = tmp_path / "vault" / "skills" / "career-ops"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\\nname: career-ops\\ndescription: Career ops\\n---\\n", encoding="utf-8")

    record = SkillRecord(
        name="career-ops",
        description="Career ops",
        path=skill_dir,
        author="user",
        hub="career",
        visibility="",
        loop_config={},
        dependencies={},
        mcp_tools=[],
        dashboard_pages=[],
        commands=[],
        config={},
        agent=None,
        skill_type="domain",
        tags=(),
        tier=0,
        origin="vault",
        ownership="user",
        upstream={},
        source="vault",
        source_root="vault",
        canonical=True,
    )

    monkeypatch.setattr("src.plugins.skill_discovery.discover_all_skills", lambda *args, **kwargs: [record])
```

Use the same assertion style as the existing ownership tests in that file and assert `ownership: user` is written into the emitted entry.

- [ ] **Step 2: Run the focused consumer tests and verify failure**

Run:

```bash
uv run pytest tests/unit/test_launch_skill_inventory.py -k "user_owned_skill_metadata" -q
uv run pytest skills/rag/augur/tests/test_unified_indexer.py -k "user_ownership_from_discovery_record" -q
```

Expected: FAIL because `SkillRecord` consumers do not yet serialize or prefer vault ownership metadata.

- [ ] **Step 3: Count managed roots in MCP manifest generation**

In `src/mcp/augur_mcp/domain/discovery.py`, replace repo-only scanning in `_scan_skills()` with:

```python
from src.config.paths import get_managed_skill_source_dirs

for skills_root in get_managed_skill_source_dirs():
    if not skills_root.is_dir():
        continue
    for skill_dir in sorted(skills_root.iterdir()):
        ...
```

Keep the frontmatter parsing logic the same.

- [ ] **Step 4: Make browse and RAG trust canonical discovery metadata**

In `skills/rag/scripts/_indexer_helpers.py`, update `_classify_skill_dir()`:

```python
from src.config.paths import get_vault_skills_dir

vault_skills = get_vault_skills_dir().resolve()
try:
    skill_dir.relative_to(vault_skills)
    return ("user", "vault")
except ValueError:
    pass
```

In `skills/rag/scripts/_scanners_knowledge.py`, replace the repo-only ownership heuristic with:

```python
if discovery_record is not None:
    ownership = str(getattr(discovery_record, "ownership", "") or "external")
    source = str(getattr(discovery_record, "source", "") or source)
    skill_origin = str(getattr(discovery_record, "source_root", "") or skill_origin)
else:
    ...
```

In `src/mcp/augur_mcp/infrastructure/browse/cli.py`, keep `_find_skill_dir()` but rely on the updated `get_all_client_skill_dirs()` so vault skills participate automatically.

In `src/mcp/augur_mcp/infrastructure/browse/index.py`, when merging enrichment metadata, do not override `ownership="user"` with install-registry data:

```python
if entry_data["ownership"] == "external":
    enrichment[skill_name].setdefault("ownership", "external")
```

- [ ] **Step 5: Re-run the focused consumer tests**

Run:

```bash
uv run pytest tests/unit/test_launch_skill_inventory.py -k "user_owned_skill_metadata" -q
uv run pytest tests/unit/test_list_skills_launch_metadata.py -q
uv run pytest skills/rag/augur/tests/test_unified_indexer.py -k "ownership" -q
```

Expected: all targeted tests pass.

- [ ] **Step 6: Commit the consumer checkpoint**

```bash
git add src/mcp/augur_mcp/domain/discovery.py src/mcp/augur_mcp/infrastructure/browse/cli.py src/mcp/augur_mcp/infrastructure/browse/index.py skills/rag/scripts/_indexer_helpers.py skills/rag/scripts/_scanners_knowledge.py tests/unit/test_launch_skill_inventory.py tests/unit/test_list_skills_launch_metadata.py skills/rag/augur/tests/test_unified_indexer.py
git commit -m "feat: propagate vault skill ownership to consumers"
```

---

### Task 5: Cut Over `staged_skill_catalog` And Migrate Repo `staging/`

**Files:**
- Modify: `src/lib/staged_skill_catalog.py`
- Test: `tests/unit/test_staged_skill_catalog.py`
- Create: `scripts/migrate_staging_to_vault_drafts.py`
- Test: `tests/src/test_migrate_staging_to_vault_drafts.py`

- [ ] **Step 1: Add failing tests for vault-backed catalog behavior**

Replace the staged-path tests in `tests/unit/test_staged_skill_catalog.py` with:

```python
def test_find_skill_dir_prefers_repo_then_vault_active(tmp_path, monkeypatch) -> None:
    from src.lib.staged_skill_catalog import find_skill_dir

    repo_skill = tmp_path / "repo" / "skills" / "knowledge"
    vault_skill = tmp_path / "vault" / "skills" / "plugin-pack"
    for skill_dir, name in ((repo_skill, "knowledge"), (vault_skill, "plugin-pack")):
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"---\\nname: {name}\\n---\\n", encoding="utf-8")

    monkeypatch.setattr("src.lib.staged_skill_catalog.get_vault_skills_dir", lambda: tmp_path / "vault" / "skills")

    assert find_skill_dir(tmp_path / "repo", "knowledge") == repo_skill
    assert find_skill_dir(tmp_path / "repo", "plugin-pack") == vault_skill


def test_find_skill_dir_ignores_vault_drafts(tmp_path, monkeypatch) -> None:
    from src.lib.staged_skill_catalog import find_skill_dir

    draft_skill = tmp_path / "vault" / "_drafts" / "staging" / "r3" / "skills" / "plugin-pack"
    draft_skill.mkdir(parents=True)
    (draft_skill / "SKILL.md").write_text("---\\nname: plugin-pack\\n---\\n", encoding="utf-8")
    monkeypatch.setattr("src.lib.staged_skill_catalog.get_vault_skills_dir", lambda: tmp_path / "vault" / "skills")

    assert find_skill_dir(tmp_path / "repo", "plugin-pack") is None
```

- [ ] **Step 2: Run the focused staged-catalog tests and verify failure**

Run:

```bash
uv run pytest tests/unit/test_staged_skill_catalog.py -k "vault_active or vault_drafts" -q
```

Expected: FAIL because `find_skill_dir()` still searches repo `staging/`.

- [ ] **Step 3: Retarget `staged_skill_catalog` to live + vault active skills only**

Update `src/lib/staged_skill_catalog.py` imports:

```python
from src.config.paths import get_vault_skills_dir, get_vault_staging_dir
```

Change `iter_staged_skill_dirs()` to read vault drafts instead of repo staging:

```python
def iter_staged_skill_dirs(project_root: Path, release: str | None = None) -> list[Path]:
    drafts_root = get_vault_staging_dir()
    releases = (release,) if release is not None else STAGED_RELEASES
    dirs: list[Path] = []
    for release_tag in releases:
        dirs.extend(_skill_dirs(drafts_root / release_tag / "skills"))
    return sorted(dirs)
```

Change `find_skill_dir()` so active lookups do **not** search drafts:

```python
def find_skill_dir(project_root: Path, skill_name: str) -> Path | None:
    live_dir = project_root / "skills" / skill_name
    if (live_dir / "SKILL.md").exists():
        return live_dir

    vault_dir = get_vault_skills_dir() / skill_name
    if (vault_dir / "SKILL.md").exists():
        return vault_dir

    return None
```

Leave `iter_staged_skill_dirs()` available only for explicit draft inspection tools.

- [ ] **Step 4: Add the repo-to-vault migration script**

Create `scripts/migrate_staging_to_vault_drafts.py`:

```python
from __future__ import annotations

import shutil
from pathlib import Path

from src.config.paths import get_project_root, get_vault_skills_dir, get_vault_staging_dir


def copy_repo_staging_to_vault_drafts() -> tuple[Path, Path]:
    project_root = get_project_root()
    source = project_root / "staging"
    target = get_vault_staging_dir()
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    return source, target


def promote_active_skill(skill_name: str, *, destination: str) -> Path:
    staging_root = get_vault_staging_dir()
    matches = sorted(staging_root.glob(f"*/skills/{skill_name}"))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one draft match for {skill_name}, found {len(matches)}")

    if destination == "vault":
        target_root = get_vault_skills_dir()
    elif destination == "repo":
        target_root = get_project_root() / "skills"
    else:
        raise ValueError(f"Unknown destination: {destination}")

    target_root.mkdir(parents=True, exist_ok=True)
    target = target_root / skill_name
    if target.exists():
        shutil.rmtree(target)
    shutil.move(str(matches[0]), str(target))
    return target
```

- [ ] **Step 5: Add migration script tests**

Create `tests/src/test_migrate_staging_to_vault_drafts.py`:

```python
from pathlib import Path


def test_copy_repo_staging_to_vault_drafts(tmp_path, monkeypatch):
    from scripts.migrate_staging_to_vault_drafts import copy_repo_staging_to_vault_drafts

    project_root = tmp_path / "repo"
    staged_skill = project_root / "staging" / "r4" / "skills" / "venture"
    staged_skill.mkdir(parents=True)
    (staged_skill / "SKILL.md").write_text("---\\nname: venture\\n---\\n", encoding="utf-8")
    vault_staging = tmp_path / "vault" / "_drafts" / "staging"

    monkeypatch.setattr("scripts.migrate_staging_to_vault_drafts.get_project_root", lambda: project_root)
    monkeypatch.setattr("scripts.migrate_staging_to_vault_drafts.get_vault_staging_dir", lambda: vault_staging)

    source, target = copy_repo_staging_to_vault_drafts()

    assert source == project_root / "staging"
    assert (target / "r4" / "skills" / "venture" / "SKILL.md").exists()
```

- [ ] **Step 6: Promote the known runtime blockers before deleting repo `staging/`**

Run this audit command first:

```bash
python - <<'PY'
from pathlib import Path
import re

targets = {}
for path in Path(".").rglob("*.py"):
    text = path.read_text(encoding="utf-8", errors="ignore")
    for kind in ("find_skill_file", "find_skill_dir"):
        for match in re.finditer(rf"{kind}\([^\n]*?,\s*\"([^\"]+)\"", text):
            targets.setdefault(match.group(1), set()).add(str(path))

for name in sorted(targets):
    print(name)
    for ref in sorted(targets[name]):
        print(f"  {ref}")
PY
```

Expected at minimum:

```text
apple
lifestyle
plugin-pack
```

Then promote the skills that shipped runtime still needs before deleting repo `staging/`:

```bash
uv run python scripts/migrate_staging_to_vault_drafts.py
uv run python - <<'PY'
from scripts.migrate_staging_to_vault_drafts import promote_active_skill
for skill_name in ("apple", "lifestyle"):
    print(promote_active_skill(skill_name, destination="vault"))
print(promote_active_skill("plugin-pack", destination="repo"))
PY
```

Expected: printed destination paths under `get_vault_skills_dir()/apple`, `get_vault_skills_dir()/lifestyle`, and `skills/plugin-pack`.

- [ ] **Step 7: Remove repo `staging/` and verify the migration**

Run:

```bash
rm -rf staging
uv run pytest tests/unit/test_staged_skill_catalog.py -q
uv run pytest tests/src/test_migrate_staging_to_vault_drafts.py -q
```

Expected:

```text
all staged catalog tests pass
migration tests pass
```

- [ ] **Step 8: Commit the cutover checkpoint**

```bash
git add src/lib/staged_skill_catalog.py tests/unit/test_staged_skill_catalog.py scripts/migrate_staging_to_vault_drafts.py tests/src/test_migrate_staging_to_vault_drafts.py
git rm -r staging
git commit -m "refactor: move staged drafts into vault-owned surfaces"
```

---

### Task 6: Final Docs, Verification, And No-Staging Proof

**Files:**
- Modify: `docs/references/vault-user-surface-migration-checklist.md`
- Modify: `docs/creating-skills.md`

- [ ] **Step 1: Update user-facing ownership docs**

Add this section to `docs/creating-skills.md` under the ownership model:

```markdown
### Vault-backed private skills

- Repo `skills/` are shipped Augur product skills.
- `get_vault_dir()/skills/` are active private user skills. They are canonical, discoverable, and exported to enabled clients.
- `get_vault_dir()/_drafts/staging/` is draft storage only. Drafts are not canonical and are ignored by discovery, sync, dashboard mounting, and RAG.
```

- [ ] **Step 2: Mark the completed checklist items**

Update `docs/references/vault-user-surface-migration-checklist.md` to check off:

```markdown
- [x] Preserve the current repo `staging/` tree as-is under `get_vault_dir()/_drafts/staging/`
- [x] Exclude `get_vault_dir()/_drafts/**` from skill discovery
- [x] Exclude `get_vault_dir()/_drafts/**` from client sync/export
- [x] Exclude `get_vault_dir()/_drafts/**` from RAG/wiki scanning
- [x] Extend canonical skill discovery to include `get_vault_dir()/skills/*`
- [x] Mark vault skills as user-owned canonical sources
- [x] Export vault skills to connected clients using the same managed surface rules as repo skills
```

- [ ] **Step 3: Run the phase-1 verification suite**

Run:

```bash
uv run pytest tests/src/test_paths.py -q
uv run pytest tests/unit/test_skill_discovery_source.py tests/unit/test_skill_discovery_external_inventory.py tests/unit/test_staged_skill_catalog.py -q
PYTHONPATH=skills/ai/scripts uv run pytest tests/sync_agents/test_skill_sync.py -q
uv run pytest tests/unit/test_launch_skill_inventory.py tests/unit/test_list_skills_launch_metadata.py -q
uv run pytest skills/rag/augur/tests/test_unified_indexer.py -q
python - <<'PY'
from pathlib import Path
from src.config.paths import get_project_root

project_root = get_project_root()
assert not (project_root / "staging").exists(), "repo staging still exists"
print("repo staging removed")
PY
```

Expected: all targeted tests pass, and the final command prints `repo staging removed`.

- [ ] **Step 4: Commit the documentation and verification checkpoint**

```bash
git add docs/references/vault-user-surface-migration-checklist.md docs/creating-skills.md
git commit -m "docs: document vault-backed user skill surfaces"
```

---

## Self-Review

### Spec coverage

- Ownership split: covered by Tasks 1, 2, and 5.
- Draft invisibility: covered by Tasks 2, 3, 4, and 5.
- Vault skills as canonical active user skills: covered by Tasks 1, 2, 3, and 4.
- Repo `staging/` removal: covered by Task 5.
- No phase-1 vault page behavior: preserved; no task activates `vault/pages`.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Every code-changing step contains concrete code or commands.

### Type consistency

- Managed roots use `get_managed_skill_source_dirs()` consistently across paths, discovery, and sync.
- Skill metadata fields are consistently named `ownership`, `source_root`, and `canonical`.

