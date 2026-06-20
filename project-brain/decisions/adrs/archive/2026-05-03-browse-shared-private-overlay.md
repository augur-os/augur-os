# Browse Shared Private Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved index-time shared/private Browse overlay for notes, sources, wiki pages, and skills, including provenance filters and append-only promotion packets.

**Architecture:** The RAG index remains the backend contract: scanners write distinct pointer files for shared, private, and packet records, and `browse-index` passes that metadata through with an optional scope filter. The dashboard consumes provenance metadata directly, keeps duplicates visible through stable item IDs, and calls a narrow MCP promotion tool that delegates to `src.lib.vault_promotion.create_promotion_packet`.

**Tech Stack:** Python 3.11, pathlib, pytest, Augur MCP tools, Next.js 16, React 19, Jest, Testing Library, TypeScript.

---

## Approved Spec

Use the approved spec at `docs/superpowers/specs/2026-05-03-browse-shared-private-overlay-design.md` as the governing product contract.

The implementation must preserve these decisions:

- Overlay merge happens at index time.
- Default Browse remains merged.
- Shared/private duplicates remain separate visible items.
- Every overlay item exposes `vault_scope`, `vault_root`, `promotion_state`, `source_path`, and `source_root`.
- Scope filters support `Shared`, `Private`, and `Packet`.
- Private notes, sources, wiki pages, and skills get a `Promote` action.
- Promotion writes append-only packets under `shared-vault/inbox/promotions/` and never mutates canonical shared content.

## File Structure

- Create `src/lib/index/_overlay.py`: shared overlay metadata helpers for vault, wiki, and skills scanners.
- Modify `src/lib/index/_scanners_structural.py`: stamp vault entries with overlay metadata and collision-safe output paths.
- Modify `src/lib/index/_scanners_knowledge.py`: stamp wiki and skills entries with overlay metadata and collision-safe IDs.
- Modify `src/lib/index/_indexer_helpers.py`: classify repo, shared-vault, and private-vault skill roots distinctly.
- Modify `src/config/paths.py`: include shared-vault and configured private-vault skills in managed skill source directories.
- Modify `src/lib/index/unified_indexer.py`: pass shared root helpers into vault and wiki category reindexing.
- Create `src/mcp/augur_framework/tools/infrastructure/browse/promotion.py`: MCP implementation for append-only promotion packets.
- Modify `src/mcp/augur_framework/tools/infrastructure/browse/index.py`: preserve metadata, filter by scope, and match journey categories from metadata.
- Modify `src/mcp/augur_framework/tools/infrastructure/browse/__init__.py`: register the new `scope` parameter and `promote-browse-item` tool.
- Create `apps/dashboard/lib/browse/overlay.ts`: dashboard overlay helpers for scope labels, filtering, and promote actions.
- Modify `apps/dashboard/lib/browse/transforms.ts`: scope-aware IDs, metadata normalization, and promote actions for vault/wiki records.
- Modify `apps/dashboard/lib/browse/skill-card-ux.ts`: skill scope tags and skill promote action.
- Modify `apps/dashboard/components/shared/BrowseCard.tsx`: shared/private/packet badges for non-skill cards.
- Modify `apps/dashboard/app/(views)/browse/useBrowseState.ts`: scope filter state, MCP query arg, and client-side filtering.
- Modify `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx`: compact scope filter control and active filter chip.
- Modify `apps/dashboard/app/(views)/browse/page.tsx`: pass scope filter state into the toolbar.
- Add focused tests under `skills/rag/augur/tests/`, `tests/packages/augur-mcp/infrastructure/`, and `tests/dashboard/browse/`.

## Data Rules

Use these exact metadata values:

| Content | `vault_scope` | `vault_root` | `promotion_state` | `source_root` |
| --- | --- | --- | --- | --- |
| Repo-root canonical skill | `shared` | `project` | `integrated` | `repo` |
| Shared-vault content | `shared` | `shared-vault` | `integrated` | `shared-vault` |
| Private-vault content | `private` | `private-vault` | `private` | `private-vault` |
| Promotion packet files | `shared` | `shared-vault` | `packet` | `shared-vault` |

Use these ID formats:

- Vault entries: `vault:{scope}:{relative_path_without_suffix}`
- Wiki entries: `wiki:{scope}:{relative_path_without_suffix}`
- Skills: `skill:{source_root}:{skill_name}`

Use these output path formats:

- Vault notes/sources: `rag/vault/{journey_category}/{scope}/{relative_path_after_root}`
- Vault promotion packets: `rag/vault/inbox/promotions/{packet_relative_path}`
- Wiki: `rag/wiki/{scope}/{relative_path_from_wiki_root}`
- Skills: `rag/skills/{hub}/{source_root}/{skill_name}.md`

### Task 1: Vault And Wiki Overlay Indexing

**Files:**
- Create: `src/lib/index/_overlay.py`
- Modify: `src/lib/index/_scanners_structural.py`
- Modify: `src/lib/index/_scanners_knowledge.py`
- Modify: `src/lib/index/unified_indexer.py`
- Test: `skills/rag/augur/tests/test_unified_indexer.py`

- [ ] **Step 1: Write failing vault overlay tests**

Add this test near the existing vault scanner tests in `skills/rag/augur/tests/test_unified_indexer.py`:

```python
def test_index_vault_scans_shared_private_notes_and_promotion_packets(tmp_path):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index.unified_indexer import index_vault

    shared_vault = tmp_path / "project" / "shared-vault"
    private_vault = tmp_path / "private-vault"
    (shared_vault / "notes" / "career").mkdir(parents=True)
    (private_vault / "notes" / "career").mkdir(parents=True)
    (shared_vault / "inbox" / "promotions" / "packet-a").mkdir(parents=True)

    (shared_vault / "notes" / "career" / "strategy.md").write_text(
        "---\ntitle: Team Strategy\n---\nShared plan\n",
        encoding="utf-8",
    )
    (private_vault / "notes" / "career" / "strategy.md").write_text(
        "---\ntitle: Private Strategy\n---\nPrivate plan\n",
        encoding="utf-8",
    )
    (shared_vault / "inbox" / "promotions" / "packet-a" / "synthesis.md").write_text(
        "---\ntitle: Strategy Packet\nvault_scope: shared\npromotion_state: packet\n---\nPacket\n",
        encoding="utf-8",
    )

    rag_dir = tmp_path / "rag"
    count = index_vault(private_vault, rag_dir, shared_vault_dir=shared_vault)

    assert count == 3
    entries = [parse_frontmatter(path)[0] for path in sorted((rag_dir / "vault").rglob("*.md"))]
    assert {entry["id"] for entry in entries} == {
        "vault:shared:notes/career/strategy",
        "vault:private:notes/career/strategy",
        "vault:shared:inbox/promotions/packet-a/synthesis",
    }
    assert {entry["vault_scope"] for entry in entries} == {"shared", "private"}
    assert {entry["promotion_state"] for entry in entries} == {"integrated", "private", "packet"}
    assert (rag_dir / "vault" / "notes" / "shared" / "career" / "strategy.md").is_file()
    assert (rag_dir / "vault" / "notes" / "private" / "career" / "strategy.md").is_file()
    assert (rag_dir / "vault" / "inbox" / "promotions" / "packet-a" / "synthesis.md").is_file()
```

- [ ] **Step 2: Write failing wiki overlay tests**

Add this test near `test_index_wiki_creates_pointer_files`:

```python
def test_index_wiki_scans_shared_and_private_duplicates_with_distinct_ids(tmp_path):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index.unified_indexer import index_wiki

    shared_wiki = tmp_path / "project" / "shared-vault" / "wiki"
    private_wiki = tmp_path / "private-vault" / "wiki"
    (shared_wiki / "concepts").mkdir(parents=True)
    (private_wiki / "concepts").mkdir(parents=True)
    (shared_wiki / "concepts" / "agent-memory.md").write_text(
        "---\ntitle: Agent Memory\n---\nShared article\n",
        encoding="utf-8",
    )
    (private_wiki / "concepts" / "agent-memory.md").write_text(
        "---\ntitle: Agent Memory\n---\nPrivate article\n",
        encoding="utf-8",
    )

    rag_dir = tmp_path / "rag"
    count = index_wiki(private_wiki, rag_dir, shared_wiki_dir=shared_wiki)

    assert count == 2
    entries = [parse_frontmatter(path)[0] for path in sorted((rag_dir / "wiki").rglob("*.md"))]
    assert {entry["id"] for entry in entries} == {
        "wiki:shared:concepts/agent-memory",
        "wiki:private:concepts/agent-memory",
    }
    assert {entry["vault_scope"] for entry in entries} == {"shared", "private"}
    assert {entry["promotion_state"] for entry in entries} == {"integrated", "private"}
    assert (rag_dir / "wiki" / "shared" / "concepts" / "agent-memory.md").is_file()
    assert (rag_dir / "wiki" / "private" / "concepts" / "agent-memory.md").is_file()
```

- [ ] **Step 3: Run tests and confirm the expected failure**

Run:

```bash
uv run pytest skills/rag/augur/tests/test_unified_indexer.py::test_index_vault_scans_shared_private_notes_and_promotion_packets skills/rag/augur/tests/test_unified_indexer.py::test_index_wiki_scans_shared_and_private_duplicates_with_distinct_ids -q
```

Expected: both tests fail because `index_vault()` and `index_wiki()` do not accept `shared_vault_dir` or `shared_wiki_dir`.

- [ ] **Step 4: Add overlay metadata helpers**

Create `src/lib/index/_overlay.py`:

```python
"""Shared/private overlay metadata helpers for RAG index scanners."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

OverlayScope = Literal["shared", "private"]

_ROOT_LABELS: dict[OverlayScope, str] = {
    "shared": "shared-vault",
    "private": "private-vault",
}


def overlay_root_label(scope: OverlayScope, *, source_root: str | None = None) -> str:
    if source_root == "repo":
        return "project"
    return _ROOT_LABELS[scope]


def is_promotion_packet_relative(rel: Path) -> bool:
    return len(rel.parts) >= 3 and rel.parts[0] == "inbox" and rel.parts[1] == "promotions"


def promotion_state(scope: OverlayScope, rel: Path) -> str:
    if scope == "shared" and is_promotion_packet_relative(rel):
        return "packet"
    if scope == "shared":
        return "integrated"
    return "private"


def overlay_metadata(
    *,
    scope: OverlayScope,
    rel: Path,
    source_root: str | None = None,
) -> dict[str, str]:
    resolved_source_root = source_root or _ROOT_LABELS[scope]
    return {
        "vault_scope": scope,
        "vault_root": overlay_root_label(scope, source_root=resolved_source_root),
        "promotion_state": promotion_state(scope, rel),
        "source_root": resolved_source_root,
    }


def overlay_entry_id(category: str, scope: OverlayScope, rel: Path) -> str:
    normalized = rel.with_suffix("").as_posix()
    return f"{category}:{scope}:{normalized}"


def vault_overlay_output_path(category_dir: Path, scope: OverlayScope, rel: Path) -> Path:
    if is_promotion_packet_relative(rel):
        return category_dir / rel
    if rel.parts and rel.parts[0] in {"inbox", "notes", "sources", "_drafts", "archive", "_system"}:
        root = rel.parts[0]
        tail = Path(*rel.parts[1:]) if len(rel.parts) > 1 else Path(rel.name)
        return category_dir / root / scope / tail
    return category_dir / scope / rel


def wiki_overlay_output_path(category_dir: Path, scope: OverlayScope, rel: Path) -> Path:
    return category_dir / scope / rel
```

- [ ] **Step 5: Implement vault overlay indexing**

In `src/lib/index/_scanners_structural.py`, import the helper and change `index_vault` to accept `shared_vault_dir`:

```python
try:
    from ._overlay import (
        overlay_entry_id,
        overlay_metadata,
        vault_overlay_output_path,
    )
except ImportError:
    from _overlay import (
        overlay_entry_id,
        overlay_metadata,
        vault_overlay_output_path,
    )
```

Change the function signature:

```python
def index_vault(
    vault_dir: Path,
    rag_dir: Path,
    *,
    shared_vault_dir: Path | None = None,
) -> int:
```

Replace the single-root loop with this root loop:

```python
    roots: list[tuple[str, Path]] = []
    if shared_vault_dir is not None:
        roots.append(("shared", shared_vault_dir))
    roots.append(("private", vault_dir))

    for scope, current_vault_dir in roots:
        if not current_vault_dir.is_dir():
            continue

        for vault_file in sorted(current_vault_dir.rglob("*")):
            if not vault_file.is_file() or vault_file.suffix.lower() not in _VAULT_EXTENSIONS:
                continue
            try:
                rel = vault_file.relative_to(current_vault_dir)
            except ValueError:
                continue

            if scope == "shared":
                if not (
                    rel.parts[:1] in {("notes",), ("sources",)}
                    or (len(rel.parts) >= 2 and rel.parts[0] == "inbox" and rel.parts[1] == "promotions")
                ):
                    continue
            if scope == "private" and rel.parts[:1] == ("wiki",):
                continue

            parts = rel.parts
            if not parts:
                continue
```

Inside `entry_meta`, add:

```python
            entry_meta.update(
                overlay_metadata(scope=scope, rel=rel)
            )
            entry_meta["id"] = overlay_entry_id("vault", scope, rel)
```

Replace the output path line with:

```python
            output_path = vault_overlay_output_path(category_dir, scope, rel)
```

- [ ] **Step 6: Implement wiki overlay indexing**

In `src/lib/index/_scanners_knowledge.py`, import the helper:

```python
try:
    from ._overlay import overlay_entry_id, overlay_metadata, wiki_overlay_output_path
except ImportError:
    from _overlay import overlay_entry_id, overlay_metadata, wiki_overlay_output_path
```

Change the signature:

```python
def index_wiki(
    wiki_dir: Path,
    rag_dir: Path,
    *,
    shared_wiki_dir: Path | None = None,
) -> int:
```

Replace the single-root loop header with:

```python
    roots: list[tuple[str, Path]] = []
    if shared_wiki_dir is not None:
        roots.append(("shared", shared_wiki_dir))
    roots.append(("private", wiki_dir))

    for scope, current_wiki_dir in roots:
        if not current_wiki_dir.is_dir():
            continue

        for wiki_file in sorted(current_wiki_dir.rglob("*.md")):
            if wiki_file.name == "index.md":
                continue
            meta, body = parse_frontmatter(wiki_file)
```

Change relative path and output path creation to:

```python
            rel = wiki_file.relative_to(current_wiki_dir).with_suffix("")
            entry_name = "/".join(rel.parts)
            output_path = wiki_overlay_output_path(
                category_dir,
                scope,
                wiki_file.relative_to(current_wiki_dir),
            )
```

Inside `entry_meta`, add:

```python
                "id": overlay_entry_id("wiki", scope, wiki_file.relative_to(current_wiki_dir)),
```

Then add:

```python
            entry_meta.update(
                overlay_metadata(scope=scope, rel=wiki_file.relative_to(current_wiki_dir))
            )
```

- [ ] **Step 7: Wire reindexing to path helpers**

In `src/lib/index/unified_indexer.py`, extend imports:

```python
from src.config.paths import (
    get_compiled_wiki_dir,
    get_project_root,
    get_rag_dir,
    get_rag_category_dir,
    get_shared_vault_dir,
    get_shared_wiki_dir,
    get_skills_dir,
)
```

In `reindex_category`, change wiki and vault calls:

```python
        if category == "wiki":
            if wiki_dir is None:
                wiki_dir = get_compiled_wiki_dir()
            return index_wiki(wiki_dir, rag_dir, shared_wiki_dir=get_shared_wiki_dir(root))
```

```python
        if category == "vault":
            if vault_dir is None:
                raise ValueError("vault_dir is required for vault reindex")
            return index_vault(vault_dir, rag_dir, shared_vault_dir=get_shared_vault_dir(root))
```

For the CLI category branch, preserve explicit `--wiki-dir` and `--vault-dir` while still passing shared roots through `reindex_category`.

- [ ] **Step 8: Run tests and commit**

Run:

```bash
uv run pytest skills/rag/augur/tests/test_unified_indexer.py::test_index_vault skills/rag/augur/tests/test_unified_indexer.py::test_index_vault_scans_shared_private_notes_and_promotion_packets skills/rag/augur/tests/test_unified_indexer.py::test_index_wiki_creates_pointer_files skills/rag/augur/tests/test_unified_indexer.py::test_index_wiki_scans_shared_and_private_duplicates_with_distinct_ids -q
```

Expected: all four tests pass.

Commit:

```bash
git add src/lib/index/_overlay.py src/lib/index/_scanners_structural.py src/lib/index/_scanners_knowledge.py src/lib/index/unified_indexer.py skills/rag/augur/tests/test_unified_indexer.py
git commit -m "feat(index): add shared private vault overlay"
```

### Task 2: Skill Overlay Provenance

**Files:**
- Modify: `src/config/paths.py`
- Modify: `src/lib/index/_indexer_helpers.py`
- Modify: `src/lib/index/_scanners_knowledge.py`
- Test: `skills/rag/augur/tests/test_unified_indexer.py`

- [ ] **Step 1: Write failing skill provenance test**

Add this test near the existing `index_skills` tests:

```python
def test_index_skills_keeps_repo_shared_and_private_duplicate_skills_distinct(tmp_path, monkeypatch):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index import _indexer_helpers
    from src.lib.index.unified_indexer import index_skills

    root = tmp_path / "project"
    repo_skill = root / "skills" / "assistant"
    shared_skill = root / "shared-vault" / "skills" / "assistant"
    private_skill = tmp_path / "private-vault" / "skills" / "assistant"
    for skill_dir, description in (
        (repo_skill, "Repo skill"),
        (shared_skill, "Shared skill"),
        (private_skill, "Private skill"),
    ):
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: assistant\ndescription: {description}\nx-augur-hub: brain\n---\n# Assistant\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        _indexer_helpers,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [root / "skills", root / "shared-vault" / "skills", private_skill.parent],
        raising=False,
    )
    monkeypatch.setattr(
        _indexer_helpers,
        "get_shared_vault_skills_dir",
        lambda project_root=None: root / "shared-vault" / "skills",
        raising=False,
    )
    monkeypatch.setattr(
        _indexer_helpers,
        "get_configured_vault_skills_dir",
        lambda project_root=None: private_skill.parent,
        raising=False,
    )
    monkeypatch.setattr("src.plugins.skill_discovery.discover_all_skills", lambda: [])

    rag_dir = tmp_path / "rag"
    count = index_skills(root, rag_dir)

    assert count == 3
    entries = [parse_frontmatter(path)[0] for path in sorted((rag_dir / "skills").rglob("*.md"))]
    assert {entry["id"] for entry in entries} == {
        "skill:repo:assistant",
        "skill:shared-vault:assistant",
        "skill:private-vault:assistant",
    }
    assert {entry["vault_scope"] for entry in entries} == {"shared", "private"}
    assert {entry["source_root"] for entry in entries} == {"repo", "shared-vault", "private-vault"}
    assert (rag_dir / "skills" / "brain" / "repo" / "assistant.md").is_file()
    assert (rag_dir / "skills" / "brain" / "shared-vault" / "assistant.md").is_file()
    assert (rag_dir / "skills" / "brain" / "private-vault" / "assistant.md").is_file()
```

- [ ] **Step 2: Run test and confirm the expected failure**

Run:

```bash
uv run pytest skills/rag/augur/tests/test_unified_indexer.py::test_index_skills_keeps_repo_shared_and_private_duplicate_skills_distinct -q
```

Expected: fails because the skills scanner writes duplicate `assistant.md` paths and does not stamp overlay metadata.

- [ ] **Step 3: Include shared and private skill roots**

In `src/config/paths.py`, update `get_managed_skill_source_dirs` so it appends unique existing roots in this order:

```python
    candidates = [
        root / "skills",
        get_shared_vault_skills_dir(root),
        get_configured_vault_skills_dir(root),
    ]

    live_root = get_project_root().resolve()
    if root == live_root:
        candidates.append(get_vault_skills_dir())

    seen: set[Path] = set()
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        dirs.append(candidate)
        seen.add(resolved)
```

- [ ] **Step 4: Add skill overlay classification helpers**

In `src/lib/index/_indexer_helpers.py`, import shared/private path helpers:

```python
from src.config.paths import (
    get_claude_plugin_skill_dirs,
    get_client_skill_dirs,
    get_configured_vault_skills_dir,
    get_managed_skill_source_dirs,
    get_project_root,
    get_shared_vault_skills_dir,
)
```

Add this helper below `_classify_skill_dir`:

```python
def _skill_overlay_metadata(skill_dir: Path, root: Path) -> dict[str, str]:
    root = Path(root).resolve()
    resolved = Path(skill_dir).resolve()
    repo_skills = (root / "skills").resolve()
    shared_skills = get_shared_vault_skills_dir(root).resolve()
    private_skills = get_configured_vault_skills_dir(root).resolve()

    for parent, metadata in (
        (repo_skills, {
            "vault_scope": "shared",
            "vault_root": "project",
            "promotion_state": "integrated",
            "source_root": "repo",
        }),
        (shared_skills, {
            "vault_scope": "shared",
            "vault_root": "shared-vault",
            "promotion_state": "integrated",
            "source_root": "shared-vault",
        }),
        (private_skills, {
            "vault_scope": "private",
            "vault_root": "private-vault",
            "promotion_state": "private",
            "source_root": "private-vault",
        }),
    ):
        try:
            resolved.relative_to(parent)
        except ValueError:
            continue
        return dict(metadata)

    return {}
```

Export `_skill_overlay_metadata` through the local import block used by `_scanners_knowledge.py`.

- [ ] **Step 5: Stamp skills and write collision-safe paths**

In `src/lib/index/_scanners_knowledge.py`, import `_skill_overlay_metadata` from `_indexer_helpers`.

After `_source_metadata_from_skill(...)`, add:

```python
        skill_overlay = _skill_overlay_metadata(skill_dir, root)
        if skill_overlay:
            source_root = skill_overlay["source_root"]
            if source_root == "private-vault":
                source = "private-vault"
                ownership = "user"
                skill_client = "vault"
                skill_origin = "canonical"
            elif source_root == "shared-vault":
                source = "shared-vault"
                ownership = "augur"
                skill_client = "augur"
                skill_origin = "canonical"
            elif source_root == "repo":
                source = "augur"
                ownership = "augur"
                skill_client = "augur"
                skill_origin = "canonical"
```

Inside `entry_meta`, add:

```python
            "id": f"skill:{source_root}:{skill_name}",
```

Then merge overlay fields:

```python
        if skill_overlay:
            entry_meta.update(skill_overlay)
```

Replace the output path:

```python
        output_source_root = str(entry_meta.get("source_root") or "external")
        output_path = category_dir / hub / output_source_root / f"{skill_name}.md"
```

- [ ] **Step 6: Run tests and commit**

Run:

```bash
uv run pytest skills/rag/augur/tests/test_unified_indexer.py::test_index_skills_writes_client_metadata skills/rag/augur/tests/test_unified_indexer.py::test_index_skills_preserves_discovery_record_ownership_for_vault_skill skills/rag/augur/tests/test_unified_indexer.py::test_index_skills_fallback_vault_user_ownership_for_managed_root skills/rag/augur/tests/test_unified_indexer.py::test_index_skills_keeps_repo_shared_and_private_duplicate_skills_distinct -q
```

Expected: all four tests pass.

Commit:

```bash
git add src/config/paths.py src/lib/index/_indexer_helpers.py src/lib/index/_scanners_knowledge.py skills/rag/augur/tests/test_unified_indexer.py
git commit -m "feat(index): add skill overlay provenance"
```

### Task 3: Browse MCP Scope Filter And Promotion Tool

**Files:**
- Create: `src/mcp/augur_framework/tools/infrastructure/browse/promotion.py`
- Modify: `src/mcp/augur_framework/tools/infrastructure/browse/index.py`
- Modify: `src/mcp/augur_framework/tools/infrastructure/browse/__init__.py`
- Test: `tests/packages/augur-mcp/infrastructure/test_browse.py`

- [ ] **Step 1: Write failing Browse scope tests**

Add these imports in `tests/packages/augur-mcp/infrastructure/test_browse.py`:

```python
from src.lib.frontmatter_utils import write_frontmatter
from src.mcp.augur_framework.tools.infrastructure.browse import browse_index_impl
```

Add this test class:

```python
class TestBrowseIndexOverlayScope:
    def test_scope_filter_keeps_shared_private_and_packet_distinct(self, tmp_path, monkeypatch):
        rag_dir = tmp_path / "rag"
        vault_dir = rag_dir / "vault"
        write_frontmatter(
            vault_dir / "notes" / "shared" / "plan.md",
            {
                "id": "vault:shared:notes/plan",
                "type": "vault",
                "name": "plan",
                "description": "Shared plan",
                "journey_category": "notes",
                "vault_scope": "shared",
                "promotion_state": "integrated",
                "source_path": str(tmp_path / "shared-vault" / "notes" / "plan.md"),
            },
            "",
        )
        write_frontmatter(
            vault_dir / "notes" / "private" / "plan.md",
            {
                "id": "vault:private:notes/plan",
                "type": "vault",
                "name": "plan",
                "description": "Private plan",
                "journey_category": "notes",
                "vault_scope": "private",
                "promotion_state": "private",
                "source_path": str(tmp_path / "private-vault" / "notes" / "plan.md"),
            },
            "",
        )
        write_frontmatter(
            vault_dir / "inbox" / "promotions" / "packet-a" / "synthesis.md",
            {
                "id": "vault:shared:inbox/promotions/packet-a/synthesis",
                "type": "vault",
                "name": "synthesis",
                "description": "Packet",
                "journey_category": "inbox",
                "vault_scope": "shared",
                "promotion_state": "packet",
                "source_path": str(tmp_path / "shared-vault" / "inbox" / "promotions" / "packet-a" / "synthesis.md"),
            },
            "",
        )

        monkeypatch.setattr("src.config.paths.get_rag_category_dir", lambda category: rag_dir / category)

        private_result = json.loads(browse_index_impl("vault", journey_category="notes", scope="private"))
        assert private_result["count"] == 1
        assert private_result["items"][0]["id"] == "vault:private:notes/plan"
        assert private_result["items"][0]["metadata"]["vault_scope"] == "private"

        shared_result = json.loads(browse_index_impl("vault", scope="shared"))
        assert [item["id"] for item in shared_result["items"]] == ["vault:shared:notes/plan"]

        packet_result = json.loads(browse_index_impl("vault", scope="packet"))
        assert [item["id"] for item in packet_result["items"]] == [
            "vault:shared:inbox/promotions/packet-a/synthesis",
        ]
```

- [ ] **Step 2: Write failing promotion tool test**

Add this test class:

```python
class TestPromoteBrowseItemImpl:
    def test_promote_private_note_creates_append_only_packet(self, tmp_path, monkeypatch):
        from src.mcp.augur_framework.tools.infrastructure.browse.promotion import promote_browse_item_impl

        private_vault = tmp_path / "private-vault"
        shared_vault = tmp_path / "project" / "shared-vault"
        source = private_vault / "notes" / "career" / "plan.md"
        source.parent.mkdir(parents=True)
        source.write_text("---\ntitle: Private Plan\n---\nBody\n", encoding="utf-8")

        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.browse.promotion.get_vault_dir",
            lambda: private_vault,
        )
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.browse.promotion.get_shared_vault_dir",
            lambda: shared_vault,
        )

        result = json.loads(
            promote_browse_item_impl(
                category="notes",
                title="Private Plan",
                source_path=str(source),
                description="Private note for team review",
            )
        )

        assert result["success"] is True
        packet_path = Path(result["packet_path"])
        assert packet_path.is_dir()
        assert packet_path.parent == shared_vault / "inbox" / "promotions"
        assert (packet_path / "manifest.yaml").is_file()
        assert (packet_path / "synthesis.md").is_file()
        assert source.read_text(encoding="utf-8").endswith("Body\n")
```

- [ ] **Step 3: Run tests and confirm expected failures**

Run:

```bash
uv run pytest tests/packages/augur-mcp/infrastructure/test_browse.py::TestBrowseIndexOverlayScope tests/packages/augur-mcp/infrastructure/test_browse.py::TestPromoteBrowseItemImpl -q
```

Expected: import or argument failures for `scope` and `promote_browse_item_impl`.

- [ ] **Step 4: Add scope filtering**

In `src/mcp/augur_framework/tools/infrastructure/browse/index.py`, add this helper:

```python
def _entry_matches_scope(entry: dict, scope: str | None) -> bool:
    if not scope:
        return True
    normalized = scope.strip().lower()
    if normalized == "packet":
        return str(entry.get("promotion_state") or "").strip().lower() == "packet"
    if normalized in {"shared", "private"}:
        if str(entry.get("promotion_state") or "").strip().lower() == "packet":
            return False
        return str(entry.get("vault_scope") or "").strip().lower() == normalized
    return True
```

Update `_entry_matches_vault_journey` to check metadata first:

```python
    journey = str(entry.get("journey_category") or "").strip()
    if journey:
        return journey == root
```

Update `browse_index_impl` signature:

```python
def browse_index_impl(
    category: str,
    hub: str | None = None,
    limit: int = 0,
    search: str | None = None,
    journey_category: str | None = None,
    scope: str | None = None,
) -> str:
```

Apply scope filtering after journey filtering and before search:

```python
    if scope:
        entries = [entry for entry in entries if _entry_matches_scope(entry, scope)]
        total_count = len(entries)
        if not search_lower:
            entries = entries[:effective_limit]
```

Leave `vault_scope`, `vault_root`, `promotion_state`, and `source_root` in metadata by making no exclusion changes; the current metadata pass-through keeps these keys.

- [ ] **Step 5: Add promotion implementation**

Create `src/mcp/augur_framework/tools/infrastructure/browse/promotion.py`:

```python
"""Promotion packet creation for Browse overlay items."""

from __future__ import annotations

import getpass
import json
from pathlib import Path
from typing import Iterable

from src.config.paths import get_shared_vault_dir, get_vault_dir
from src.lib.vault_promotion import PromotionPacketRequest, create_promotion_packet

_PROMOTABLE_CATEGORIES = {"notes", "sources", "wiki", "skills"}


def _as_list(values: Iterable[str] | None) -> list[str]:
    if not values:
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def promote_browse_item_impl(
    category: str,
    title: str,
    source_path: str,
    description: str = "",
    roles: list[str] | None = None,
    domains: list[str] | None = None,
) -> str:
    normalized_category = category.strip().lower()
    if normalized_category not in _PROMOTABLE_CATEGORIES:
        return json.dumps({
            "success": False,
            "error": f"category is not promotable: {category}",
        })

    source = Path(source_path).expanduser()
    if not source_path.strip() or not source.is_file():
        return json.dumps({
            "success": False,
            "error": "source_path must point to an existing file",
        })

    private_vault = get_vault_dir()
    if not _is_under(source, private_vault):
        return json.dumps({
            "success": False,
            "error": "only private vault sources can be promoted",
        })

    topic = title.strip() or source.stem
    source_reference = f"Source: {source}"
    synthesis = "\n\n".join(part for part in (description.strip(), source_reference) if part)
    packet = create_promotion_packet(
        get_shared_vault_dir(),
        PromotionPacketRequest(
            topic=topic,
            contributor=getpass.getuser() or "local-user",
            synthesis=synthesis,
            source_paths=[source],
            roles=_as_list(roles),
            domains=_as_list(domains),
            sensitivity="internal",
        ),
    )
    return json.dumps({
        "success": True,
        "message": f"Promotion packet created for {topic}",
        "packet_path": str(packet.path),
        "manifest_path": str(packet.manifest_path),
        "synthesis_path": str(packet.synthesis_path),
    })
```

- [ ] **Step 6: Register MCP changes**

In `src/mcp/augur_framework/tools/infrastructure/browse/__init__.py`, import:

```python
from .promotion import promote_browse_item_impl
```

Update `browse_index` signature and call:

```python
    async def browse_index(
        category: str,
        hub: str | None = None,
        limit: int = 0,
        search: str | None = None,
        journey_category: str | None = None,
        scope: str | None = None,
    ) -> str:
```

```python
        return browse_index_impl(category, hub, limit, search, journey_category, scope)
```

Register the promotion tool near other Browse write tools:

```python
    @mcp.tool(
        name="promote-browse-item",
        annotations=tool_annotations(
            {
                "title": "Promote Browse Item",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    async def promote_browse_item(
        category: str,
        title: str,
        source_path: str,
        description: str = "",
        roles: list[str] | None = None,
        domains: list[str] | None = None,
    ) -> str:
        """Create an append-only shared-vault promotion packet for a private Browse item."""
        return promote_browse_item_impl(category, title, source_path, description, roles, domains)
```

- [ ] **Step 7: Run tests and commit**

Run:

```bash
uv run pytest tests/packages/augur-mcp/infrastructure/test_browse.py::TestBrowseIndexOverlayScope tests/packages/augur-mcp/infrastructure/test_browse.py::TestPromoteBrowseItemImpl -q
```

Expected: both test classes pass.

Commit:

```bash
git add src/mcp/augur_framework/tools/infrastructure/browse/index.py src/mcp/augur_framework/tools/infrastructure/browse/promotion.py src/mcp/augur_framework/tools/infrastructure/browse/__init__.py tests/packages/augur-mcp/infrastructure/test_browse.py
git commit -m "feat(browse): expose overlay scope and promotion"
```

### Task 4: Dashboard Overlay Transform Contract

**Files:**
- Create: `apps/dashboard/lib/browse/overlay.ts`
- Modify: `apps/dashboard/lib/browse/transforms.ts`
- Test: `tests/dashboard/browse/browseOverlayTransforms.test.ts`

- [ ] **Step 1: Write failing transform tests**

Create `tests/dashboard/browse/browseOverlayTransforms.test.ts`:

```typescript
import { transformIndexEntry } from "@/lib/browse/transforms";

describe("Browse overlay transforms", () => {
  it("keeps shared and private wiki duplicates distinct", () => {
    const shared = transformIndexEntry({
      id: "wiki:shared:concepts/agent-memory",
      name: "concepts/agent-memory",
      title: "Agent Memory",
      description: "Shared article",
      hub: "brain",
      type: "wiki",
      source_path: "/project/shared-vault/wiki/concepts/agent-memory.md",
      metadata: {
        vault_scope: "shared",
        promotion_state: "integrated",
        source_root: "shared-vault",
      },
    }, "wiki");
    const privateItem = transformIndexEntry({
      id: "wiki:private:concepts/agent-memory",
      name: "concepts/agent-memory",
      title: "Agent Memory",
      description: "Private article",
      hub: "brain",
      type: "wiki",
      source_path: "/private/wiki/concepts/agent-memory.md",
      metadata: {
        vault_scope: "private",
        promotion_state: "private",
        source_root: "private-vault",
      },
    }, "wiki");

    expect(shared.id).toBe("wiki:shared:concepts/agent-memory");
    expect(privateItem.id).toBe("wiki:private:concepts/agent-memory");
    expect(privateItem.actions).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          label: "Promote",
          target: "promote-browse-item",
          args: expect.objectContaining({
            category: "wiki",
            source_path: "/private/wiki/concepts/agent-memory.md",
          }),
        }),
      ]),
    );
  });

  it("adds promote only for private notes and not shared notes", () => {
    const privateNote = transformIndexEntry({
      id: "vault:private:notes/career/plan",
      name: "plan",
      description: "Private plan",
      type: "vault",
      source_path: "/private/notes/career/plan.md",
      metadata: {
        journey_category: "notes",
        vault_scope: "private",
        promotion_state: "private",
      },
    }, "vault");
    const sharedNote = transformIndexEntry({
      id: "vault:shared:notes/career/plan",
      name: "plan",
      description: "Shared plan",
      type: "vault",
      source_path: "/project/shared-vault/notes/career/plan.md",
      metadata: {
        journey_category: "notes",
        vault_scope: "shared",
        promotion_state: "integrated",
      },
    }, "vault");

    expect(privateNote.actions?.some((action) => action.label === "Promote")).toBe(true);
    expect(sharedNote.actions?.some((action) => action.label === "Promote")).toBe(false);
  });
});
```

- [ ] **Step 2: Run test and confirm expected failure**

Run:

```bash
pnpm --filter dashboard test -- tests/dashboard/browse/browseOverlayTransforms.test.ts
```

Expected: fails because the overlay helper and promote action do not exist.

- [ ] **Step 3: Add dashboard overlay helpers**

Create `apps/dashboard/lib/browse/overlay.ts`:

```typescript
import type { BrowseCardAction, BrowseItem, ViewMode } from "@/lib/browse/types";

export type OverlayScopeFilter = "shared" | "private" | "packet";

export const OVERLAY_VIEW_MODES: readonly ViewMode[] = ["notes", "sources", "wiki", "skills"];

export function isOverlayViewMode(mode: ViewMode): boolean {
  return OVERLAY_VIEW_MODES.includes(mode);
}

export function overlayScope(metadata: Record<string, string> | undefined): OverlayScopeFilter | null {
  const state = metadata?.promotion_state?.trim().toLowerCase();
  if (state === "packet") return "packet";
  const scope = metadata?.vault_scope?.trim().toLowerCase();
  if (scope === "shared" || scope === "private") return scope;
  return null;
}

export function overlayScopeLabel(scope: OverlayScopeFilter): string {
  if (scope === "shared") return "Shared";
  if (scope === "private") return "Private";
  return "Packet";
}

export function matchesOverlayScope(item: BrowseItem, scope: OverlayScopeFilter | null): boolean {
  if (!scope) return true;
  return overlayScope(item.metadata) === scope;
}

export function promotableBrowseCategory(category: string, metadata: Record<string, string>): string | null {
  if (category === "wiki" || category === "skills") return category;
  if (category === "vault") {
    const journey = metadata.journey_category;
    if (journey === "notes" || journey === "sources") return journey;
  }
  return null;
}

export function buildPromoteBrowseAction(args: {
  id: string;
  title: string;
  description: string;
  category: string;
  sourcePath: string;
  metadata: Record<string, string>;
}): BrowseCardAction | null {
  if (overlayScope(args.metadata) !== "private") return null;
  if (!args.sourcePath) return null;
  const category = promotableBrowseCategory(args.category, args.metadata);
  if (!category) return null;
  return {
    id: `promote-${args.id}`,
    label: "Promote",
    icon: "UploadCloud",
    type: "mcp-tool",
    target: "promote-browse-item",
    args: {
      category,
      title: args.title,
      source_path: args.sourcePath,
      description: args.description,
      roles: args.metadata.roles ? args.metadata.roles.split(",").map((role) => role.trim()).filter(Boolean) : [],
      domains: args.metadata.domains ? args.metadata.domains.split(",").map((domain) => domain.trim()).filter(Boolean) : [],
    },
  };
}
```

- [ ] **Step 4: Wire transforms**

In `apps/dashboard/lib/browse/transforms.ts`, import:

```typescript
import { buildPromoteBrowseAction } from "@/lib/browse/overlay";
```

In `browseIndexItemId`, prefer entry IDs and scope-aware source paths:

```typescript
function browseIndexItemId(entry: Record<string, any>, category: string, fallback: string): string {
  const explicit = firstString(entry.id);
  if (explicit) return explicit;
  if (SOURCE_BACKED_ID_CATEGORIES.has(category) || category === "wiki") {
    const sourcePath = typeof entry.source_path === "string" ? entry.source_path.trim() : "";
    if (sourcePath) return sourcePath;
  }
  return fallback || entry.source_path || entry.title || entry.name || category;
}
```

After `enrichedMeta` is created, preserve overlay keys from either top-level or nested metadata:

```typescript
  copyMeta(enrichedMeta, "vault_scope", firstString(entry.vault_scope, enrichedMeta.vault_scope));
  copyMeta(enrichedMeta, "vault_root", firstString(entry.vault_root, enrichedMeta.vault_root));
  copyMeta(enrichedMeta, "promotion_state", firstString(entry.promotion_state, enrichedMeta.promotion_state));
  copyMeta(enrichedMeta, "source_root", firstString(entry.source_root, enrichedMeta.source_root));
```

Before returning the `BrowseItem`, append promote actions:

```typescript
  const promoteAction = buildPromoteBrowseAction({
    id: itemId,
    title: entry.title || entry.description || entry.name || "",
    description,
    category,
    sourcePath: entry.source_path || "",
    metadata: enrichedMeta,
  });
  if (promoteAction) {
    actions = [...(actions ?? []), promoteAction];
  }
```

- [ ] **Step 5: Run tests and commit**

Run:

```bash
pnpm --filter dashboard test -- tests/dashboard/browse/browseOverlayTransforms.test.ts
```

Expected: tests pass.

Commit:

```bash
git add apps/dashboard/lib/browse/overlay.ts apps/dashboard/lib/browse/transforms.ts tests/dashboard/browse/browseOverlayTransforms.test.ts
git commit -m "feat(dashboard): transform overlay browse metadata"
```

### Task 5: Browse Scope Filter State And Toolbar

**Files:**
- Modify: `apps/dashboard/app/(views)/browse/useBrowseState.ts`
- Modify: `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx`
- Modify: `apps/dashboard/app/(views)/browse/page.tsx`
- Test: `tests/dashboard/browse/useBrowseState.test.tsx`
- Test: `tests/dashboard/browse/BrowseToolbarScope.test.tsx`

- [ ] **Step 1: Write failing state test**

Add this test to `tests/dashboard/browse/useBrowseState.test.tsx`:

```typescript
it("filters overlay items by private scope without collapsing duplicates", async () => {
  localStorage.setItem("augur:browse:view", "notes");
  mockUseMcpQuery.mockReturnValue({
    data: {
      items: [
        {
          id: "vault:shared:notes/career/plan",
          title: "Plan",
          description: "Shared",
          hub: "brain",
          type: "vault",
          source_path: "/project/shared-vault/notes/career/plan.md",
          metadata: { journey_category: "notes", vault_scope: "shared", promotion_state: "integrated" },
        },
        {
          id: "vault:private:notes/career/plan",
          title: "Plan",
          description: "Private",
          hub: "brain",
          type: "vault",
          source_path: "/private/notes/career/plan.md",
          metadata: { journey_category: "notes", vault_scope: "private", promotion_state: "private" },
        },
      ],
    },
    loading: false,
    error: null,
    refetch: jest.fn(),
  });

  const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
  const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

  await waitFor(() => {
    expect(result.current.filtered.map((item) => item.id)).toEqual([
      "vault:shared:notes/career/plan",
      "vault:private:notes/career/plan",
    ]);
  });

  act(() => {
    result.current.setScopeFilter("private");
  });

  await waitFor(() => {
    expect(result.current.filtered.map((item) => item.id)).toEqual([
      "vault:private:notes/career/plan",
    ]);
    expect(result.current.scopeItems.map((item) => item.id)).toEqual(["all", "shared", "private", "packet"]);
  });
});
```

- [ ] **Step 2: Write failing toolbar test**

Create `tests/dashboard/browse/BrowseToolbarScope.test.tsx`:

```typescript
/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowseToolbar } from "@/app/(views)/browse/BrowseToolbar";
import type { BrowseCategory } from "@/lib/browse/types";

const activeCategory: BrowseCategory = {
  id: "notes",
  label: "Notes",
  singularLabel: "Note",
  icon: "BookOpen",
  devOnly: false,
  group: "content",
};

function renderToolbar(onScopeFilterChange = jest.fn()) {
  render(
    <BrowseToolbar
      activeCategory={activeCategory}
      effectiveViewMode="notes"
      search=""
      onSearchChange={jest.fn()}
      semanticMode={false}
      onToggleSemantic={jest.fn()}
      onSemanticSearch={jest.fn()}
      semanticLoading={false}
      semanticResults={[]}
      semanticSearched={false}
      semanticError={null}
      tagFilter={null}
      onTagFilterChange={jest.fn()}
      tagItems={[]}
      hubFilter={null}
      onHubFilterChange={jest.fn()}
      hubItems={[]}
      sourceFilter={null}
      onSourceFilterChange={jest.fn()}
      scopeFilter={null}
      onScopeFilterChange={onScopeFilterChange}
      scopeItems={[
        { id: "all", label: "Scope: All" },
        { id: "shared", label: "Shared" },
        { id: "private", label: "Private" },
        { id: "packet", label: "Packet" },
      ]}
      masterFilter={null}
      onMasterFilterChange={jest.fn()}
      masterClients={[]}
      pluginFilter={null}
      onPluginFilterChange={jest.fn()}
      pluginNames={[]}
      typeFilter={null}
      onTypeFilterChange={jest.fn()}
      typeItems={[]}
      skillTagFilter={null}
      onSkillTagFilterChange={jest.fn()}
      skillTagItems={[]}
      sortBy="name-asc"
      onSortChange={jest.fn()}
    />,
  );
}

describe("BrowseToolbar scope filter", () => {
  it("renders scope filter and emits private selection", async () => {
    const onScopeFilterChange = jest.fn();
    renderToolbar(onScopeFilterChange);
    await userEvent.click(screen.getByRole("button", { name: /show filters/i }));
    await userEvent.selectOptions(screen.getByLabelText("Filter by Scope"), "private");
    expect(onScopeFilterChange).toHaveBeenCalledWith("private");
  });
});
```

- [ ] **Step 3: Run tests and confirm expected failures**

Run:

```bash
pnpm --filter dashboard test -- tests/dashboard/browse/useBrowseState.test.tsx tests/dashboard/browse/BrowseToolbarScope.test.tsx
```

Expected: TypeScript or assertion failures because scope state and props do not exist.

- [ ] **Step 4: Add state and filtering**

In `apps/dashboard/app/(views)/browse/useBrowseState.ts`, import:

```typescript
import {
  isOverlayViewMode,
  matchesOverlayScope,
  type OverlayScopeFilter,
} from "@/lib/browse/overlay";
```

Extend `BrowseState`:

```typescript
  scopeFilter: OverlayScopeFilter | null;
  setScopeFilter: (scope: OverlayScopeFilter | null) => void;
  scopeItems: { id: string; label: string }[];
```

Add state near `sourceFilter`:

```typescript
  const [scopeFilter, setScopeFilter] = useState<OverlayScopeFilter | null>(null);
```

Reset it in `changeView`:

```typescript
    setScopeFilter(null);
```

Include it in the MCP key and args:

```typescript
    ["browse-index", indexCategory, journeyCategoryKey, debouncedSearch, scopeFilter ?? "all"],
```

```typescript
        ...(scopeFilter ? { scope: scopeFilter } : {}),
```

Change the dedupe set key so duplicate titles stay visible:

```typescript
      const dedupeKey = [
        item.id,
        item.metadata?.vault_scope ?? "",
        item.metadata?.source_root ?? "",
        item.path ?? "",
      ].join("|");
      if (seen.has(dedupeKey)) return false;
      seen.add(dedupeKey);
```

Add scope items:

```typescript
  const scopeItems = useMemo(() => {
    if (!isOverlayViewMode(effectiveViewMode)) return [];
    return [
      { id: "all", label: "Scope: All" },
      { id: "shared", label: "Shared" },
      { id: "private", label: "Private" },
      { id: "packet", label: "Packet" },
    ];
  }, [effectiveViewMode]);
```

Apply filter before search:

```typescript
    if (scopeFilter && isOverlayViewMode(effectiveViewMode)) {
      result = result.filter((item) => matchesOverlayScope(item, scopeFilter));
    }
```

Add `scopeFilter` to the pagination reset dependencies and return object.

- [ ] **Step 5: Add toolbar props and UI**

In `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx`, import the type:

```typescript
import type { OverlayScopeFilter } from "@/lib/browse/overlay";
```

Extend props:

```typescript
  scopeFilter: OverlayScopeFilter | null;
  onScopeFilterChange: (scope: OverlayScopeFilter | null) => void;
  scopeItems: { id: string; label: string }[];
```

Destructure the new props and include `scopeFilter` in `activeFilterCount`, `clearAllFilters`, and `activeFilterChips`:

```typescript
    scopeFilter ? {
      id: "scope",
      label: `Scope: ${optionLabel(scopeItems, scopeFilter)}`,
      onClear: () => onScopeFilterChange(null),
    } : null,
```

Add the filter control before ownership:

```typescript
    ...(scopeItems.length > 0 ? [{
      id: "scope",
      node: (
        <FilterSelect
          label="Scope"
          value={scopeFilter}
          onChange={(value) => onScopeFilterChange(value as OverlayScopeFilter | null)}
          options={scopeItems}
        />
      ),
    }] : []),
```

In `apps/dashboard/app/(views)/browse/page.tsx`, add these props to the existing `<BrowseToolbar />` call:

```tsx
scopeFilter={state.scopeFilter}
onScopeFilterChange={state.setScopeFilter}
scopeItems={state.scopeItems}
```

- [ ] **Step 6: Run tests and commit**

Run:

```bash
pnpm --filter dashboard test -- tests/dashboard/browse/useBrowseState.test.tsx tests/dashboard/browse/BrowseToolbarScope.test.tsx
```

Expected: tests pass.

Commit:

```bash
git add apps/dashboard/app/\(views\)/browse/useBrowseState.ts apps/dashboard/app/\(views\)/browse/BrowseToolbar.tsx apps/dashboard/app/\(views\)/browse/page.tsx tests/dashboard/browse/useBrowseState.test.tsx tests/dashboard/browse/BrowseToolbarScope.test.tsx
git commit -m "feat(browse): add overlay scope filter"
```

### Task 6: Overlay Badges And Skill Card Promotion

**Files:**
- Modify: `apps/dashboard/components/shared/BrowseCard.tsx`
- Modify: `apps/dashboard/lib/browse/skill-card-ux.ts`
- Test: `tests/dashboard/browse/BrowseCardAction.test.tsx`
- Test: `tests/dashboard/browse/BrowseContentGridSkills.test.tsx`

- [ ] **Step 1: Write failing non-skill badge test**

Add this test in `tests/dashboard/browse/BrowseCardAction.test.tsx`:

```typescript
it("renders private overlay badge for private vault items", () => {
  render(
    <BrowseCard
      item={{
        ...baseItem,
        metadata: {
          vault_scope: "private",
          promotion_state: "private",
        },
      }}
    />,
  );
  expect(screen.getByText("Private")).toBeInTheDocument();
});
```

- [ ] **Step 2: Write failing skill badge and action test**

Add this test in `tests/dashboard/browse/BrowseContentGridSkills.test.tsx` near the skill-card tests:

```typescript
it("shows private scope and promote action for private skills", () => {
  const privateSkill: BrowseItem = {
    id: "skill:private-vault:assistant",
    title: "Assistant",
    description: "Private assistant skill",
    hub: "brain",
    path: "/private-vault/skills/assistant/SKILL.md",
    metadata: {
      ownership: "user",
      vault_scope: "private",
      promotion_state: "private",
      source_root: "private-vault",
    },
    primaryAction: { label: "Open docs", type: "navigate", target: "/browse/skill:private-vault:assistant" },
  };

  render(<SkillBrowseCard item={privateSkill} />);
  expect(screen.getByText("Private")).toBeInTheDocument();
  fireEvent.click(screen.getByTestId("skill-card-overflow"));
  expect(screen.getByRole("menuitem", { name: "Promote" })).toBeInTheDocument();
});
```

If `SkillBrowseCard` is not imported in that test file, import it from `@/components/shared/SkillBrowseCard`.

- [ ] **Step 3: Run tests and confirm expected failures**

Run:

```bash
pnpm --filter dashboard test -- tests/dashboard/browse/BrowseCardAction.test.tsx tests/dashboard/browse/BrowseContentGridSkills.test.tsx
```

Expected: tests fail because badges and skill promotion are not rendered.

- [ ] **Step 4: Add non-skill badges**

In `apps/dashboard/components/shared/BrowseCard.tsx`, add this block near the top of `collectBadges` after `const m = item.metadata;`:

```typescript
  if (m?.promotion_state === "packet") {
    badges.push({ key: "overlay-packet", node: (
      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-[var(--accent-warning)]/15 text-[var(--accent-warning)] border border-[var(--accent-warning)]/25">Packet</span>
    )});
  } else if (m?.vault_scope === "private") {
    badges.push({ key: "overlay-private", node: (
      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-[var(--accent-info)]/15 text-[var(--accent-info)] border border-[var(--accent-info)]/25">Private</span>
    )});
  } else if (m?.vault_scope === "shared") {
    badges.push({ key: "overlay-shared", node: (
      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-[var(--accent-success)]/15 text-[var(--accent-success)] border border-[var(--accent-success)]/25">Shared</span>
    )});
  }
```

- [ ] **Step 5: Add skill tags and promote action**

In `apps/dashboard/lib/browse/skill-card-ux.ts`, import:

```typescript
import { buildPromoteBrowseAction, overlayScope, overlayScopeLabel } from "@/lib/browse/overlay";
```

In `getSkillIdentityTags`, add after ownership:

```typescript
  const scope = overlayScope(metadata);
  if (scope) {
    tags.push({
      key: `overlay-${scope}`,
      label: overlayScopeLabel(scope),
      tone: scope === "packet" ? "warning" : scope === "private" ? "info" : "success",
      kind: "ownership",
      title: "Scope",
    });
  }
```

In `getSkillSecondaryActions`, add before reveal source:

```typescript
  const promoteAction = buildPromoteBrowseAction({
    id: item.id,
    title: item.title,
    description: item.description,
    category: "skills",
    sourcePath: item.path ?? "",
    metadata,
  });
  if (promoteAction) {
    actions.push(promoteAction);
  }
```

- [ ] **Step 6: Run tests and commit**

Run:

```bash
pnpm --filter dashboard test -- tests/dashboard/browse/BrowseCardAction.test.tsx tests/dashboard/browse/BrowseContentGridSkills.test.tsx
```

Expected: tests pass.

Commit:

```bash
git add apps/dashboard/components/shared/BrowseCard.tsx apps/dashboard/lib/browse/skill-card-ux.ts tests/dashboard/browse/BrowseCardAction.test.tsx tests/dashboard/browse/BrowseContentGridSkills.test.tsx
git commit -m "feat(browse): show overlay badges and skill promote"
```

### Task 7: Integration Verification And Browser Review

**Files:**
- Verify: Python indexer and MCP tests
- Verify: dashboard Jest and typecheck
- Verify: Browse page in a real browser

- [ ] **Step 1: Run focused Python verification**

Run:

```bash
uv run pytest skills/rag/augur/tests/test_unified_indexer.py::test_index_vault_scans_shared_private_notes_and_promotion_packets skills/rag/augur/tests/test_unified_indexer.py::test_index_wiki_scans_shared_and_private_duplicates_with_distinct_ids skills/rag/augur/tests/test_unified_indexer.py::test_index_skills_keeps_repo_shared_and_private_duplicate_skills_distinct tests/packages/augur-mcp/infrastructure/test_browse.py::TestBrowseIndexOverlayScope tests/packages/augur-mcp/infrastructure/test_browse.py::TestPromoteBrowseItemImpl -q
```

Expected: all selected Python tests pass.

- [ ] **Step 2: Run focused dashboard verification**

Run:

```bash
pnpm --filter dashboard test -- tests/dashboard/browse/browseOverlayTransforms.test.ts tests/dashboard/browse/useBrowseState.test.tsx tests/dashboard/browse/BrowseToolbarScope.test.tsx tests/dashboard/browse/BrowseCardAction.test.tsx tests/dashboard/browse/BrowseContentGridSkills.test.tsx
```

Expected: all selected Jest tests pass.

- [ ] **Step 3: Run dashboard typecheck**

Run:

```bash
pnpm --filter dashboard typecheck
```

Expected: exits 0 with no TypeScript errors.

- [ ] **Step 4: Rebuild through the dashboard command surface**

Invoke:

```text
/dev-build
```

Expected: the command rebuilds dashboard generated surfaces, handles stale Next.js artifacts through its own safety workflow, and reports a usable local Browse URL.

- [ ] **Step 5: Verify Browse in a real browser**

Use the in-app browser or another screenshot-capable browser tool to open the Browse page from the `/dev-build` output, then verify:

- The page reaches an interactive state with no client chunk error.
- `Notes`, `Sources`, `Wiki`, and `Skills` can be selected.
- The filters panel includes `Scope: All`, `Shared`, `Private`, and `Packet` for those modes.
- Shared/private duplicates remain visible in the default merged view.
- Private items show `Private` and a `Promote` action.
- Shared canonical items show `Shared` and no `Promote` action.
- Packet items show `Packet`.

If browser verification is unavailable, record that explicitly in the handoff and do not call the UI verified.

- [ ] **Step 6: Run final status**

Run:

```bash
git status --short
```

Expected: clean worktree after commits, or only intentional verification artifacts that are either committed or explicitly removed.

If browser review exposes a UI defect, make that fix as a new explicit task with its own failing test, implementation step, verification command, and commit. Do not hide an unplanned UI fix inside this verification task.

## Self-Review

Spec coverage:

- Index-time overlay is covered by Tasks 1 and 2.
- Notes, sources, wiki, and skills are covered by Tasks 1 and 2.
- Duplicate visibility is covered by collision-safe IDs and Task 5 dedupe key.
- Provenance metadata is covered by Tasks 1 and 2.
- Scope filters are covered by Tasks 3 and 5.
- Promotion packets are covered by Task 3 and dashboard promote wiring in Tasks 4 and 6.
- No canonical shared writes are performed; promotion delegates to the append-only packet writer.

Type consistency:

- Python uses `vault_scope`, `vault_root`, `promotion_state`, and `source_root`.
- Dashboard preserves the same snake_case metadata keys.
- Dashboard filter type is `OverlayScopeFilter = "shared" | "private" | "packet"`.
- MCP tool target is exactly `promote-browse-item`.

Placeholder scan:

- The plan contains exact files, tests, commands, expected outcomes, metadata values, and action payloads.
