# Managed Skill Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable skills to live in AI client folders (Claude Code, Codex) as platform-managed, with ejection to `skills/` on customization, update notifications for ejected skills, and a unified browse page showing all skills from all sources.

**Architecture:** Extend `discover_all_skills()` to scan 5 locations (project `skills/`, Claude local/global, Codex local/global). Add `source` field to `SkillRecord`. Add `source` frontmatter tag to generated stubs. Add source filter to browse page. Build eject/reset/status commands as MCP tools. Extend browse detail panel with source badge and eject CTA.

**Tech Stack:** Python (discovery, MCP tools, stub generation), TypeScript/React (dashboard browse page), YAML frontmatter

---

### Task 1: Add `source` Field to SkillRecord

**Files:**
- Modify: `src/plugins/skill_discovery.py:52-100` (SkillRecord dataclass)
- Test: `tests/unit/test_skill_discovery_source.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_skill_discovery_source.py`:

```python
"""Tests for source field in SkillRecord."""

import pytest
from dataclasses import asdict
from src.plugins.skill_discovery import SkillRecord


def _minimal_record(**overrides) -> SkillRecord:
    """Build a SkillRecord with minimal required fields."""
    from pathlib import Path
    defaults = dict(
        name="test-skill",
        description="A test skill",
        path=Path("/tmp/test-skill"),
        author="bundled",
        hub="dev",
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
        origin="augur",
        source="augur",
    )
    defaults.update(overrides)
    return SkillRecord(**defaults)


def test_source_field_exists():
    record = _minimal_record(source="augur")
    assert record.source == "augur"


def test_source_field_claude_local():
    record = _minimal_record(source="claude-local")
    assert record.source == "claude-local"


def test_source_field_claude_global():
    record = _minimal_record(source="claude-global")
    assert record.source == "claude-global"


def test_source_field_codex_local():
    record = _minimal_record(source="codex-local")
    assert record.source == "codex-local"


def test_source_field_codex_global():
    record = _minimal_record(source="codex-global")
    assert record.source == "codex-global"


def test_source_field_in_asdict():
    record = _minimal_record(source="claude-local")
    d = asdict(record)
    assert d["source"] == "claude-local"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_skill_discovery_source.py -v`
Expected: FAIL with `TypeError: SkillRecord.__init__() got an unexpected keyword argument 'source'`

- [ ] **Step 3: Add `source` field to SkillRecord**

In `src/plugins/skill_discovery.py`, add the `source` field to the `SkillRecord` dataclass after the `origin` field (line 76):

```python
    origin: str = ""          # "augur" for skills/, client name for caches
    source: str = "augur"     # provenance: augur, claude-local, claude-global, codex-local, codex-global
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_skill_discovery_source.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/plugins/skill_discovery.py tests/unit/test_skill_discovery_source.py
git commit -m "feat(discovery): add source field to SkillRecord for skill provenance tracking"
```

---

### Task 2: Extend Discovery to Scan Client Folders

**Files:**
- Modify: `src/plugins/skill_discovery.py:284-308` (`_discover_all_skills_impl`)
- Modify: `src/config/paths.py` (add helper for client skill dirs)
- Test: `tests/unit/test_skill_discovery_source.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_skill_discovery_source.py`:

```python
import tempfile
from pathlib import Path
from unittest.mock import patch
from src.plugins.skill_discovery import (
    _discover_all_skills_impl,
    invalidate_discovery_cache,
)


def _create_skill_md(skill_dir: Path, name: str, description: str = "test", extra_fm: str = ""):
    """Create a minimal SKILL.md in the given directory."""
    skill_dir.mkdir(parents=True, exist_ok=True)
    fm = f"---\nname: {name}\ndescription: {description}\n{extra_fm}---\n\nSkill body.\n"
    (skill_dir / "SKILL.md").write_text(fm)


def test_discover_claude_local_skills():
    """Skills in .claude/skills/ (project-level) are discovered with source=claude-local."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # Create a Claude local skill (not auto-generated)
        claude_skill = root / ".claude" / "skills" / "my-tool"
        _create_skill_md(claude_skill, "my-tool")

        # No skills in skills/ dir
        (root / "skills").mkdir()

        with patch("src.plugins.skill_discovery.get_skills_dir", return_value=root / "skills"), \
             patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]), \
             patch("src.plugins.skill_discovery._get_client_skill_dirs", return_value={
                 "claude-local": root / ".claude" / "skills",
                 "claude-global": Path("/nonexistent"),
                 "codex-local": Path("/nonexistent"),
                 "codex-global": Path("/nonexistent"),
             }):
            invalidate_discovery_cache()
            skills = _discover_all_skills_impl()

        my_tool = next((s for s in skills if s.name == "my-tool"), None)
        assert my_tool is not None
        assert my_tool.source == "claude-local"
        assert my_tool.tier == 2  # client skills are tier 2


def test_augur_skill_wins_over_client_skill():
    """When same skill exists in skills/ and .claude/skills/, skills/ wins."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # Augur skill
        augur_skill = root / "skills" / "shared"
        _create_skill_md(augur_skill, "shared", description="augur version")

        # Claude local skill with same name
        claude_skill = root / ".claude" / "skills" / "shared"
        _create_skill_md(claude_skill, "shared", description="claude version")

        with patch("src.plugins.skill_discovery.get_skills_dir", return_value=root / "skills"), \
             patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]), \
             patch("src.plugins.skill_discovery._get_client_skill_dirs", return_value={
                 "claude-local": root / ".claude" / "skills",
                 "claude-global": Path("/nonexistent"),
                 "codex-local": Path("/nonexistent"),
                 "codex-global": Path("/nonexistent"),
             }):
            invalidate_discovery_cache()
            skills = _discover_all_skills_impl()

        shared = next((s for s in skills if s.name == "shared"), None)
        assert shared is not None
        assert shared.source == "augur"
        assert shared.description == "augur version"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_skill_discovery_source.py::test_discover_claude_local_skills -v`
Expected: FAIL with `AttributeError: module 'src.plugins.skill_discovery' has no attribute '_get_client_skill_dirs'`

- [ ] **Step 3: Add `_get_client_skill_dirs()` helper to `src/config/paths.py`**

Add after `get_client_config_dir()` (around line 553):

```python
def get_client_skill_dirs() -> dict[str, Path]:
    """Return skill directories for all supported AI clients, keyed by source tag.

    Returns:
        Dict mapping source tags to skill directory paths. Paths may not exist.
    """
    project_root = Path.cwd()
    home = Path.home()
    return {
        "claude-local": project_root / ".claude" / "skills",
        "claude-global": home / ".claude" / "skills",
        "codex-local": project_root / ".codex" / "prompts",
        "codex-global": home / ".codex" / "prompts",
    }
```

- [ ] **Step 4: Extend `_discover_all_skills_impl()` to scan client folders**

In `src/plugins/skill_discovery.py`, add import:

```python
from src.config.paths import (
    get_claude_plugin_skill_dirs,
    get_skills_dir,
    get_client_skill_dirs,
)
```

Add a module-level wrapper (so tests can mock it):

```python
def _get_client_skill_dirs() -> dict[str, Path]:
    """Wrapper for testability."""
    from src.config.paths import get_client_skill_dirs
    return get_client_skill_dirs()
```

Extend `_discover_all_skills_impl()` — add after the plugin-cache source (after line 306):

```python
    # Source 3: AI client skill directories (platform-managed skills)
    try:
        for source_tag, skill_parent in _get_client_skill_dirs().items():
            if not skill_parent.is_dir():
                continue
            is_flat = source_tag.startswith("codex")  # Codex uses flat .md files
            if is_flat:
                for skill_file in skill_parent.iterdir():
                    if not skill_file.is_file() or skill_file.suffix != ".md":
                        continue
                    _process_flat_skill_file(skill_file, source_tag, 2, disabled_ids, skills_dict)
            else:
                for skill_dir in skill_parent.iterdir():
                    if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                        continue
                    _process_skill_dir(skill_dir, source_tag, 2, disabled_ids, skills_dict)
    except Exception:
        pass  # Client skill discovery is optional
```

Update `_process_skill_dir()` to set `source` on the SkillRecord (around line 382):

```python
    skills_dict[canonical_id] = SkillRecord(
        ...
        source=origin if origin in ("claude-local", "claude-global", "codex-local", "codex-global") else "augur",
        ...
    )
```

- [ ] **Step 5: Add `_process_flat_skill_file()` for Codex flat `.md` files**

Add to `src/plugins/skill_discovery.py`:

```python
def _process_flat_skill_file(
    skill_file: Path,
    origin: str,
    tier: int,
    disabled_ids: set[str],
    skills_dict: dict[str, SkillRecord],
) -> None:
    """Process a flat .md skill file (Codex format) into a SkillRecord."""
    if _is_auto_generated(skill_file):
        return

    try:
        content = skill_file.read_text(encoding="utf-8")
    except Exception:
        return

    frontmatter = _extract_frontmatter(content)
    if not isinstance(frontmatter, dict):
        frontmatter = {}

    canonical_id = normalize_skill_id(
        str(frontmatter.get("name") or "").strip() or skill_file.stem
    )
    if not canonical_id:
        return

    description = str(frontmatter.get("description") or "").strip()
    triggers = _extract_triggers(frontmatter, description, content)
    capabilities = _extract_capabilities(content)

    disabled = canonical_id in disabled_ids
    if disabled and canonical_id not in CORE_SKILLS:
        return

    existing = skills_dict.get(canonical_id)
    if existing and hasattr(existing, "tier") and existing.tier < tier:
        return

    skills_dict[canonical_id] = SkillRecord(
        name=canonical_id,
        description=description,
        path=skill_file.parent,
        author=str(frontmatter.get("x-augur-created-by") or ""),
        hub=str(frontmatter.get("x-augur-hub") or ""),
        visibility=frontmatter.get("x-augur-visibility") or "",
        loop_config={},
        dependencies={},
        mcp_tools=[],
        dashboard_pages=[],
        commands=[],
        config={},
        file_intake={},
        agent=None,
        skill_type=str(frontmatter.get("x-augur-type") or ""),
        tags=(),
        tier=tier,
        origin=origin,
        source=origin,
        display_name=str(frontmatter.get("name") or skill_file.stem),
        triggers=tuple(triggers),
        capabilities=tuple(capabilities),
        token_estimate=len(content) // 4,
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_skill_discovery_source.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/plugins/skill_discovery.py src/config/paths.py tests/unit/test_skill_discovery_source.py
git commit -m "feat(discovery): scan Claude and Codex client folders for platform-managed skills"
```

---

### Task 3: Add `source` Tag to Generated Stubs

**Files:**
- Modify: `scripts/generate_client_stubs.py:69-88` (stub builders)
- Test: `tests/unit/test_generate_stubs_source.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_generate_stubs_source.py`:

```python
"""Tests for source tag in generated client stubs."""

import tempfile
from pathlib import Path
from src.lib.frontmatter_utils import parse_frontmatter


def _create_source_skill(skills_dir: Path, name: str):
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test skill\n---\n\nBody.\n"
    )


def test_subdir_stub_has_source_augur():
    """Claude subdir stub should include source: augur in frontmatter."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        skills_dir = root / "skills"
        _create_source_skill(skills_dir, "my-skill")

        # Create target directories
        (root / ".claude" / "skills").mkdir(parents=True)

        from scripts.generate_client_stubs import generate_and_validate
        generate_and_validate(root, skills_dir)

        stub = root / ".claude" / "skills" / "my-skill" / "SKILL.md"
        assert stub.exists()
        meta, _body = parse_frontmatter(stub)
        assert meta.get("source") == "augur"


def test_flat_stub_has_source_augur_comment():
    """Codex flat stub should include source: augur in the generated content."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        skills_dir = root / "skills"
        _create_source_skill(skills_dir, "my-skill")

        (root / ".codex" / "prompts").mkdir(parents=True)

        from scripts.generate_client_stubs import generate_and_validate
        generate_and_validate(root, skills_dir)

        stub = root / ".codex" / "prompts" / "my-skill.md"
        assert stub.exists()
        content = stub.read_text()
        assert "source: augur" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_generate_stubs_source.py -v`
Expected: FAIL — `assert meta.get("source") == "augur"` fails (source field not present in generated stubs)

- [ ] **Step 3: Add `source: augur` to stub generation**

In `scripts/generate_client_stubs.py`, update `_write_subdir_stub()` (line 78-88):

```python
def _write_subdir_stub(target: Path, name: str, description: str, body: str) -> None:
    """Write a SKILL.md stub with YAML frontmatter via canonical write_frontmatter."""
    meta: dict[str, Any] = {
        "name": name,
        "description": description,
        "source": "augur",
        MARKER_FIELD: True,
    }
    stub_body = MARKER + "\n"
    if body:
        stub_body += "\n" + body
    write_frontmatter(target, meta, stub_body)
```

Update `_build_flat_stub()` (line 69-75) to include source in the generated content:

```python
def _build_flat_stub(name: str, description: str, body: str) -> str:
    parts = [MARKER, f"<!-- source: augur -->", "", f"# {name}"]
    if description:
        parts.extend(["", f"> {description}"])
    if body:
        parts.extend(["", body])
    return "\n".join(parts) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_generate_stubs_source.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_client_stubs.py tests/unit/test_generate_stubs_source.py
git commit -m "feat(stubs): add source: augur tag to generated client stubs"
```

---

### Task 4: Add `source` Field to RAG Skill Indexer

**Files:**
- Modify: `skills/rag/scripts/_scanners_knowledge.py:34-80` (`index_skills`)
- Test: `tests/unit/test_rag_skill_source.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_rag_skill_source.py`:

```python
"""Tests for source field in RAG skill index entries."""

import tempfile
from pathlib import Path
from src.lib.frontmatter_utils import parse_frontmatter


def test_indexed_skill_has_source_field():
    """RAG index entry for a skill should include the source field."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rag_dir = Path(tmp) / "rag"
        rag_dir.mkdir()

        # Create a skill
        skill_dir = root / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: test-skill\ndescription: A test\nx-augur-hub: dev\n---\n\nBody.\n"
        )

        from skills.rag.scripts._scanners_knowledge import index_skills
        count = index_skills(root, rag_dir)

        assert count == 1
        # Find the generated index entry
        entries = list((rag_dir / "skills").rglob("*.md"))
        assert len(entries) == 1
        meta, _body = parse_frontmatter(entries[0])
        assert "source" in meta
        assert meta["source"] == "augur"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_rag_skill_source.py -v`
Expected: FAIL — `assert "source" in meta` fails

- [ ] **Step 3: Add `source` field to `index_skills()`**

In `skills/rag/scripts/_scanners_knowledge.py`, update the `entry_meta` dict in `index_skills()` (around line 62):

```python
        # Determine source from path
        try:
            rel = str(skill_md.relative_to(root))
            if rel.startswith("skills/"):
                source = "augur"
            elif ".claude/skills" in rel:
                source = "claude-local"
            elif ".codex/prompts" in rel:
                source = "codex-local"
            else:
                source = "augur"
        except ValueError:
            source = "augur"

        entry_meta: dict[str, Any] = {
            "type": "skill",
            "hub": hub,
            "bundle": bundle_name,
            "name": skill_name,
            "source": source,
            "source_path": source_path,
            "description": meta.get("description", ""),
            "visibility": meta.get("visibility", ""),
            "tags": meta.get("tags") or [],
            "related": meta.get("related") or [],
            "checksum": _checksum(skill_md),
            "modified": _mtime_iso(skill_md),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_rag_skill_source.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/rag/scripts/_scanners_knowledge.py tests/unit/test_rag_skill_source.py
git commit -m "feat(rag): include source field in skill index entries"
```

---

### Task 5: Add Source Filter to `list-skills` MCP Tool

**Files:**
- Modify: `src/mcp/augur_mcp/core/models.py` (add `source` param to `ListSkillsInput`)
- Modify: `src/mcp/augur_mcp/core/skills.py:47-136` (`list_skills_impl`)
- Test: `tests/unit/test_list_skills_source_filter.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_list_skills_source_filter.py`:

```python
"""Tests for source filter in list-skills MCP tool."""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path


@pytest.fixture
def mock_skills():
    """Create mock skill records with different sources."""
    records = []
    for name, source, origin in [
        ("ask", "augur", "augur"),
        ("ui-tool", "claude-local", "claude-local"),
        ("shared", "claude-global", "claude-global"),
    ]:
        m = MagicMock()
        m.name = name
        m.display_name = name
        m.description = f"{name} description"
        m.triggers = ()
        m.capabilities = ()
        m.token_estimate = 100
        m.has_modules = False
        m.has_scripts = False
        m.has_references = False
        m.hub = "dev"
        m.layer = None
        m.master = None
        m.plugin = None
        m.source = source
        m.skill_type = "domain"
        m.tags = ()
        m.origin = origin
        m.author = "bundled"
        records.append(m)
    return records


@pytest.mark.asyncio
async def test_list_skills_no_filter(mock_skills):
    """Without source filter, all skills returned."""
    from src.mcp.augur_mcp.core.skills import list_skills_impl
    from src.mcp.augur_mcp.core.models import ListSkillsInput, ResponseFormat

    params = ListSkillsInput(format=ResponseFormat.JSON)
    cache = MagicMock()
    cache.get.return_value = None
    metrics = MagicMock()

    result = await list_skills_impl(params, cache, metrics, lambda **kw: mock_skills)
    data = json.loads(result)
    assert data["count"] == 3


@pytest.mark.asyncio
async def test_list_skills_filter_augur(mock_skills):
    """Filter source=augur returns only Augur skills."""
    from src.mcp.augur_mcp.core.skills import list_skills_impl
    from src.mcp.augur_mcp.core.models import ListSkillsInput, ResponseFormat

    params = ListSkillsInput(format=ResponseFormat.JSON, source="augur")
    cache = MagicMock()
    cache.get.return_value = None
    metrics = MagicMock()

    result = await list_skills_impl(params, cache, metrics, lambda **kw: mock_skills)
    data = json.loads(result)
    assert data["count"] == 1
    assert data["skills"][0]["name"] == "ask"


@pytest.mark.asyncio
async def test_list_skills_filter_claude_local(mock_skills):
    """Filter source=claude-local returns only Claude local skills."""
    from src.mcp.augur_mcp.core.skills import list_skills_impl
    from src.mcp.augur_mcp.core.models import ListSkillsInput, ResponseFormat

    params = ListSkillsInput(format=ResponseFormat.JSON, source="claude-local")
    cache = MagicMock()
    cache.get.return_value = None
    metrics = MagicMock()

    result = await list_skills_impl(params, cache, metrics, lambda **kw: mock_skills)
    data = json.loads(result)
    assert data["count"] == 1
    assert data["skills"][0]["name"] == "ui-tool"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_list_skills_source_filter.py -v`
Expected: FAIL — `ListSkillsInput` does not accept `source` parameter

- [ ] **Step 3: Add `source` parameter to `ListSkillsInput`**

Find `ListSkillsInput` in `src/mcp/augur_mcp/core/models.py` and add:

```python
class ListSkillsInput(BaseModel):
    format: ResponseFormat = ResponseFormat.JSON
    source: str | None = None  # Filter by source: augur, claude-local, claude-global, codex-local, codex-global
```

- [ ] **Step 4: Add source filtering to `list_skills_impl()`**

In `src/mcp/augur_mcp/core/skills.py`, update the cache key and add filtering after dedup (around line 88):

```python
    # Update cache key to include source filter
    cache_key = f"list_skills:{params.format}:{params.source or 'all'}"
    cached = skill_cache.get(cache_key)
    if cached:
        return cached
```

After `sorted_unique` is built (around line 88), add source filtering:

```python
    sorted_unique = sorted(unique_skills.values(), key=lambda s: s.name)

    # Apply source filter if specified
    if params.source:
        sorted_unique = [
            s for s in sorted_unique
            if getattr(s, "source", "augur") == params.source
        ]
```

Update the `"source"` value in the per-skill dict to use the actual `source` field:

```python
                "source": getattr(skill, "source", "augur"),
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_list_skills_source_filter.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/mcp/augur_mcp/core/models.py src/mcp/augur_mcp/core/skills.py tests/unit/test_list_skills_source_filter.py
git commit -m "feat(mcp): add source filter to list-skills tool"
```

---

### Task 6: Build Skill Lifecycle MCP Tools (eject, reset, status)

**Files:**
- Create: `src/mcp/augur_mcp/core/skill_lifecycle.py`
- Modify: MCP tool registration (wherever tools are registered — check `src/mcp/augur_mcp/core/__init__.py` or similar)
- Test: `tests/unit/test_skill_lifecycle.py` (new)

- [ ] **Step 1: Write the failing test for `skill_eject`**

Create `tests/unit/test_skill_lifecycle.py`:

```python
"""Tests for skill lifecycle operations (eject, reset, status)."""

import tempfile
import shutil
from pathlib import Path
import pytest


def _setup_project(tmp: str):
    """Create a minimal project structure."""
    root = Path(tmp)
    (root / "skills").mkdir()
    (root / ".claude" / "skills").mkdir(parents=True)
    (root / ".codex" / "prompts").mkdir(parents=True)
    return root


def _create_client_skill(root: Path, name: str, client: str = "claude"):
    """Create a skill in the client folder."""
    if client == "claude":
        skill_dir = root / ".claude" / "skills" / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: A platform skill\n---\n\nSkill body.\n"
        )
    elif client == "codex":
        prompts_dir = root / ".codex" / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        (prompts_dir / f"{name}.md").write_text(
            f"---\nname: {name}\ndescription: A codex skill\n---\n\nSkill body.\n"
        )


def test_eject_copies_skill_to_skills_dir():
    """Ejecting a Claude skill copies it to skills/ and adds upstream tracking."""
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_project(tmp)
        _create_client_skill(root, "ui-tool", "claude")

        from src.mcp.augur_mcp.core.skill_lifecycle import eject_skill
        result = eject_skill("ui-tool", "claude-local", root)

        assert result["success"] is True
        ejected_dir = root / "skills" / "ui-tool"
        assert ejected_dir.exists()
        assert (ejected_dir / "SKILL.md").exists()

        # Check upstream tracking in frontmatter
        from src.lib.frontmatter_utils import parse_frontmatter
        meta, _body = parse_frontmatter(ejected_dir / "SKILL.md")
        assert meta.get("x-augur-upstream") == "claude-local"


def test_eject_codex_flat_file():
    """Ejecting a Codex flat .md skill scaffolds a proper SKILL.md."""
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_project(tmp)
        _create_client_skill(root, "codex-tool", "codex")

        from src.mcp.augur_mcp.core.skill_lifecycle import eject_skill
        result = eject_skill("codex-tool", "codex-local", root)

        assert result["success"] is True
        ejected_dir = root / "skills" / "codex-tool"
        assert (ejected_dir / "SKILL.md").exists()


def test_eject_fails_if_already_in_skills():
    """Ejecting a skill that already exists in skills/ should fail."""
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_project(tmp)
        _create_client_skill(root, "existing", "claude")
        # Also create in skills/
        existing = root / "skills" / "existing"
        existing.mkdir()
        (existing / "SKILL.md").write_text("---\nname: existing\ndescription: already here\n---\n")

        from src.mcp.augur_mcp.core.skill_lifecycle import eject_skill
        result = eject_skill("existing", "claude-local", root)
        assert result["success"] is False


def test_reset_deletes_from_skills():
    """Resetting an ejected skill removes it from skills/ and notifies user."""
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_project(tmp)
        # Create an ejected skill in skills/ with upstream tracking
        skill_dir = root / "skills" / "ui-tool"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: ui-tool\ndescription: test\nx-augur-upstream: claude-local\n---\n"
        )

        from src.mcp.augur_mcp.core.skill_lifecycle import reset_skill
        result = reset_skill("ui-tool", root)

        assert result["success"] is True
        assert not skill_dir.exists()
        assert "install" in result["message"].lower()


def test_reset_refuses_without_upstream():
    """Reset should refuse if the skill has no x-augur-upstream."""
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_project(tmp)
        skill_dir = root / "skills" / "native-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: native-skill\ndescription: born in augur\n---\n"
        )

        from src.mcp.augur_mcp.core.skill_lifecycle import reset_skill
        result = reset_skill("native-skill", root)

        assert result["success"] is False
        assert skill_dir.exists()


def test_skill_status_augur():
    """Status for an Augur skill shows source=augur."""
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_project(tmp)
        skill_dir = root / "skills" / "ask"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: ask\ndescription: inner voice\nx-augur-hub: brain\n---\n"
        )

        from src.mcp.augur_mcp.core.skill_lifecycle import skill_status
        result = skill_status("ask", root)

        assert result["name"] == "ask"
        assert result["source"] == "augur"
        assert result["location"] == str(skill_dir)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_skill_lifecycle.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.mcp.augur_mcp.core.skill_lifecycle'`

- [ ] **Step 3: Implement `skill_lifecycle.py`**

Create `src/mcp/augur_mcp/core/skill_lifecycle.py`:

```python
"""Skill lifecycle operations: eject, reset, status.

Manages transitions between platform-managed and Augur-managed skill states.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter
from src.plugins.skill_discovery import invalidate_discovery_cache


# Client folder patterns keyed by source tag
_CLIENT_SKILL_PATHS: dict[str, tuple[str, bool]] = {
    # source_tag: (relative_path_template, is_flat)
    "claude-local": (".claude/skills/{name}", False),
    "claude-global": ("~/.claude/skills/{name}", False),
    "codex-local": (".codex/prompts/{name}.md", True),
    "codex-global": ("~/.codex/prompts/{name}.md", True),
}


def _resolve_client_path(source: str, name: str, project_root: Path) -> Path:
    """Resolve the client-side path for a skill given its source tag."""
    template, is_flat = _CLIENT_SKILL_PATHS[source]
    path_str = template.replace("{name}", name)
    if path_str.startswith("~/"):
        return Path.home() / path_str[2:]
    return project_root / path_str


def eject_skill(name: str, source: str, project_root: Path) -> dict:
    """Eject a platform-managed skill to skills/ for customization.

    Args:
        name: Skill name (canonical ID)
        source: Current source tag (claude-local, claude-global, codex-local, codex-global)
        project_root: Project root directory

    Returns:
        Dict with success, message keys
    """
    skills_dir = project_root / "skills"
    target_dir = skills_dir / name

    if target_dir.exists():
        return {"success": False, "message": f"Skill '{name}' already exists in skills/. Cannot eject."}

    if source not in _CLIENT_SKILL_PATHS:
        return {"success": False, "message": f"Unknown source: {source}. Expected one of: {list(_CLIENT_SKILL_PATHS.keys())}"}

    client_path = _resolve_client_path(source, name, project_root)
    _template, is_flat = _CLIENT_SKILL_PATHS[source]

    if is_flat:
        # Codex: flat .md file -> scaffold skill directory
        if not client_path.exists():
            return {"success": False, "message": f"Client skill not found at {client_path}"}

        target_dir.mkdir(parents=True, exist_ok=True)
        meta, body = parse_frontmatter(client_path)
        meta["x-augur-upstream"] = source
        write_frontmatter(target_dir / "SKILL.md", meta, body)
    else:
        # Claude: directory with SKILL.md
        if not client_path.exists() or not (client_path / "SKILL.md").exists():
            return {"success": False, "message": f"Client skill not found at {client_path}"}

        shutil.copytree(client_path, target_dir)

        # Add upstream tracking to the ejected SKILL.md
        skill_md = target_dir / "SKILL.md"
        meta, body = parse_frontmatter(skill_md)
        meta["x-augur-upstream"] = source
        write_frontmatter(skill_md, meta, body)

    invalidate_discovery_cache()
    return {"success": True, "message": f"Skill '{name}' ejected to skills/{name}/. You can now customize it."}


def reset_skill(name: str, project_root: Path) -> dict:
    """Reset an ejected skill back to platform-managed.

    Deletes the skill from skills/ and removes the generated client stub.
    Notifies user to install the platform version.

    Args:
        name: Skill name
        project_root: Project root directory

    Returns:
        Dict with success, message keys
    """
    skill_dir = project_root / "skills" / name

    if not skill_dir.exists():
        return {"success": False, "message": f"Skill '{name}' not found in skills/."}

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return {"success": False, "message": f"No SKILL.md found in skills/{name}/."}

    meta, _body = parse_frontmatter(skill_md)
    upstream = meta.get("x-augur-upstream")

    if not upstream:
        return {"success": False, "message": f"Skill '{name}' has no upstream source (x-augur-upstream). Cannot reset — this skill was born in Augur."}

    # Delete the skill directory
    shutil.rmtree(skill_dir)

    # Remove generated stub from client folder if it exists
    for source_tag in ("claude-local", "codex-local"):
        try:
            stub_path = _resolve_client_path(source_tag, name, project_root)
            if source_tag.startswith("codex"):
                if stub_path.exists():
                    stub_path.unlink()
            else:
                stub_md = stub_path / "SKILL.md"
                if stub_md.exists():
                    stub_md.unlink()
                    try:
                        stub_path.rmdir()
                    except OSError:
                        pass
        except (KeyError, OSError):
            pass

    invalidate_discovery_cache()

    # Determine install hint
    if "claude" in upstream:
        install_hint = f"claude skill install {name}"
    elif "codex" in upstream:
        install_hint = f"codex install {name}"
    else:
        install_hint = f"Install '{name}' via your AI client"

    return {
        "success": True,
        "message": f"Skill '{name}' removed from Augur. Install the platform version: `{install_hint}`",
    }


def skill_status(name: str, project_root: Path) -> dict:
    """Get the lifecycle status of a skill.

    Args:
        name: Skill name
        project_root: Project root directory

    Returns:
        Dict with name, source, location, upstream, update_available keys
    """
    skills_dir = project_root / "skills"
    skill_dir = skills_dir / name

    # Check skills/ first (Augur-managed)
    if skill_dir.exists() and (skill_dir / "SKILL.md").exists():
        meta, _body = parse_frontmatter(skill_dir / "SKILL.md")
        upstream = meta.get("x-augur-upstream")
        return {
            "name": name,
            "source": "augur",
            "location": str(skill_dir),
            "upstream": upstream,
            "update_available": False,  # TODO: compare versions when registry is available
            "description": meta.get("description", ""),
        }

    # Check client folders
    for source_tag, (template, is_flat) in _CLIENT_SKILL_PATHS.items():
        client_path = _resolve_client_path(source_tag, name, project_root)
        if is_flat:
            if client_path.exists():
                meta, _body = parse_frontmatter(client_path)
                return {
                    "name": name,
                    "source": source_tag,
                    "location": str(client_path),
                    "upstream": None,
                    "update_available": False,
                    "description": meta.get("description", ""),
                }
        else:
            if client_path.exists() and (client_path / "SKILL.md").exists():
                meta, _body = parse_frontmatter(client_path / "SKILL.md")
                return {
                    "name": name,
                    "source": source_tag,
                    "location": str(client_path),
                    "upstream": None,
                    "update_available": False,
                    "description": meta.get("description", ""),
                }

    return {
        "name": name,
        "source": "unknown",
        "location": None,
        "upstream": None,
        "update_available": False,
        "description": "",
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_skill_lifecycle.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Register MCP tools**

Find the MCP tool registration file (check the pattern used for existing skill tools). Register three new tools: `skill-eject`, `skill-reset`, `skill-status`. Each wraps the corresponding function from `skill_lifecycle.py`. Follow the existing registration pattern used for `list-skills`, `get-skill`, `find-skill`.

- [ ] **Step 6: Commit**

```bash
git add src/mcp/augur_mcp/core/skill_lifecycle.py tests/unit/test_skill_lifecycle.py
git commit -m "feat(mcp): add skill-eject, skill-reset, skill-status lifecycle tools"
```

---

### Task 7: Add Source Filter to Browse Page

**Files:**
- Modify: `apps/dashboard/lib/browse/types.ts:110-124` (SkillDetail interface)
- Modify: `apps/dashboard/app/(views)/browse/useBrowseState.ts` (add sourceFilter state)
- Modify: `apps/dashboard/app/(views)/browse/page.tsx` (render source filter pills)

- [ ] **Step 1: Add `source` to SkillDetail type**

In `apps/dashboard/lib/browse/types.ts`, add to the `SkillDetail` interface (line 110):

```typescript
export interface SkillDetail {
  skillId: string;
  hub: string;
  title: string;
  icon: string;
  description: string;
  problemStatement?: string;
  blocks: import('@/lib/blocks/types').BlockManifest[];
  actions: SkillAction[];
  health?: { status: string; lastCheck?: string; errors24h?: number };
  skillDoc?: string;
  qualityTier?: string;
  qualityScore?: number | string;
  masterClient?: string;
  source?: string;           // augur, claude-local, claude-global, codex-local, codex-global
  upstream?: string;          // original source if ejected
  updateAvailable?: boolean;  // true if upstream has newer version
}
```

Also add `source` to `BrowseItem.metadata` known fields comment (line 59):

```typescript
  // Known metadata fields: source ("augur"|"claude-local"|"claude-global"|"codex-local"|"codex-global"), plugin (string|null), master (string)
```

- [ ] **Step 2: Add sourceFilter state to useBrowseState**

In `apps/dashboard/app/(views)/browse/useBrowseState.ts`, add after `pluginFilter` state (around line 197):

```typescript
  /* ----- Source filter (skill provenance) ----- */
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);
```

Add `sourceFilter` to the `changeView` reset (around line 274):

```typescript
    setSourceFilter(null);
```

Add source filtering to the filtered items computation. Find where `hubFilter` and `typeFilter` are applied to the items list, and add:

```typescript
    // Source filter
    if (sourceFilter) {
      filtered = filtered.filter((item) => {
        const itemSource = item.metadata?.source ?? "augur";
        if (sourceFilter === "platform-local") {
          return itemSource === "claude-local" || itemSource === "codex-local";
        }
        if (sourceFilter === "platform-global") {
          return itemSource === "claude-global" || itemSource === "codex-global";
        }
        return itemSource === sourceFilter;
      });
    }
```

Export `sourceFilter` and `setSourceFilter` in the returned state object.

- [ ] **Step 3: Add source filter UI to browse page**

In `apps/dashboard/app/(views)/browse/page.tsx`, find the hub filter pills section. Add source filter pills after the hub filter (only visible when category is "skills"):

```tsx
{/* Source filter — skills category only */}
{state.effectiveViewMode === "skills" && (
  <div className="flex items-center gap-1.5 flex-wrap">
    <span className="text-xs text-[var(--text-muted)] mr-1">Source:</span>
    {[
      { value: null, label: "All" },
      { value: "augur", label: "Augur" },
      { value: "platform-local", label: "Local" },
      { value: "platform-global", label: "Global" },
    ].map((opt) => (
      <button
        key={opt.value ?? "all"}
        onClick={() => state.setSourceFilter(opt.value)}
        className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
          state.sourceFilter === opt.value
            ? "bg-[var(--accent-primary)] text-white"
            : "bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
        }`}
      >
        {opt.label}
      </button>
    ))}
  </div>
)}
```

- [ ] **Step 4: Verify build passes**

Run: `cd ~/Projects/Augur && pnpm --filter dashboard build`
Expected: Build succeeds with no TypeScript errors

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/browse/types.ts apps/dashboard/app/(views)/browse/useBrowseState.ts apps/dashboard/app/(views)/browse/page.tsx
git commit -m "feat(dashboard): add source filter to browse page for skill provenance"
```

---

### Task 8: Add Source Badge and Eject CTA to Detail Panel

**Files:**
- Modify: `apps/dashboard/components/shared/BrowseDetailPanel.tsx`
- Modify: `apps/dashboard/lib/browse/useSkillDetail.ts` (pass source data through)

- [ ] **Step 1: Update `useSkillDetail` to include source**

In `apps/dashboard/lib/browse/useSkillDetail.ts`, extend the `detail` memo (around line 47) to include source:

```typescript
  const detail = useMemo<SkillDetail | null>(() => {
    if (!skillId || !data?.skill) return null;
    return {
      skillId,
      hub: data.skill.hub,
      title: data.skill.title,
      icon: data.skill.icon,
      description: data.skill.description,
      problemStatement: data.skill.problemStatement,
      blocks,
      actions: data.actions ?? [],
      health: data.health,
      skillDoc: data.skillDoc?.skillDoc,
      source: data.skill.source,
      upstream: data.skill.upstream,
      updateAvailable: data.skill.updateAvailable,
    };
  }, [skillId, data, blocks]);
```

Update the `SkillMetaResponse` interface to include the new fields:

```typescript
interface SkillMetaResponse {
  skill?: {
    id: string;
    hub: string;
    title: string;
    icon: string;
    description: string;
    problemStatement?: string;
    source?: string;
    upstream?: string;
    updateAvailable?: boolean;
  };
  actions?: SkillAction[];
  health?: { status: string; lastCheck?: string; errors24h?: number };
  skillDoc?: { hasSkillMd: boolean; skillDoc?: string };
}
```

- [ ] **Step 2: Add source badge to BrowseDetailPanel**

In `apps/dashboard/components/shared/BrowseDetailPanel.tsx`, add source badge after the hub badge in the metadata badges section (around line 76):

```tsx
{/* Source badge */}
{detail.source && detail.source !== "augur" && (
  <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-[var(--accent-info)]/10 text-[var(--accent-info)]">
    {detail.source === "claude-local" ? "Claude (local)"
      : detail.source === "claude-global" ? "Claude (global)"
      : detail.source === "codex-local" ? "Codex (local)"
      : detail.source === "codex-global" ? "Codex (global)"
      : detail.source}
  </span>
)}
{detail.updateAvailable && (
  <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-[var(--accent-warning)]/15 text-[var(--accent-warning)]">
    Update available
  </span>
)}
```

- [ ] **Step 3: Add eject CTA for platform skills**

In `apps/dashboard/components/shared/BrowseDetailPanel.tsx`, add an eject button section before the actions section (around line 114):

```tsx
{/* Eject CTA — platform skills only */}
{detail.source && detail.source !== "augur" && (
  <section>
    <div className="rounded-xl border border-dashed border-[var(--accent-primary)]/30 bg-[var(--accent-primary)]/5 p-4">
      <h3 className="text-sm font-medium text-[var(--text-primary)] mb-1">
        Customize this skill
      </h3>
      <p className="text-xs text-[var(--text-muted)] mb-3">
        Eject to your project to modify instructions, add scripts, or connect to the dashboard.
      </p>
      <button
        onClick={() => {
          // Call skill-eject MCP tool via action runner
          fetch('/api/mcp/tool', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              tool: 'skill-eject',
              args: { name: detail.skillId, source: detail.source },
            }),
          }).then(() => window.location.reload());
        }}
        className="px-3 py-1.5 rounded-lg text-xs font-medium bg-[var(--accent-primary)] text-white hover:opacity-90 transition-opacity"
      >
        Eject to Augur
      </button>
    </div>
  </section>
)}
```

- [ ] **Step 4: Verify build passes**

Run: `cd ~/Projects/Augur && pnpm --filter dashboard build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/components/shared/BrowseDetailPanel.tsx apps/dashboard/lib/browse/useSkillDetail.ts
git commit -m "feat(dashboard): add source badge and eject CTA to skill detail panel"
```

---

### Task 9: Build Skill Eject/Reset Slash Commands

**Files:**
- Create: `skills/import/commands/skill-eject.md`
- Create: `skills/import/commands/skill-reset.md`
- Create: `skills/import/commands/skill-status.md`
- Create: `skills/import/commands/skill-refresh.md`

- [ ] **Step 1: Create `/skill eject` command**

Create `skills/import/commands/skill-eject.md`:

```markdown
---
name: skill-eject
description: Eject a platform-managed skill to skills/ for customization
---

# /skill eject <name>

Eject a platform-managed skill from its AI client folder to `skills/` for customization.

## Usage

```
/skill eject <skill-name>
```

## What it does

1. Locates the skill in the AI client folder (`.claude/skills/` or `.codex/prompts/`)
2. Copies the full skill content to `skills/<name>/`
3. Adds `x-augur-upstream` tracking to the ejected SKILL.md
4. Next sync generates a client stub with `source: augur`
5. You can now freely modify the skill

## Steps

1. Call `skill-status` MCP tool with the provided skill name to verify it exists and is platform-managed
2. If source is "augur", tell the user the skill is already in Augur
3. Call `skill-eject` MCP tool with the skill name and source
4. Report the result
5. Call `invalidate_discovery_cache` or suggest running `/skill refresh`
```

- [ ] **Step 2: Create `/skill reset` command**

Create `skills/import/commands/skill-reset.md`:

```markdown
---
name: skill-reset
description: Reset an ejected skill back to platform-managed
---

# /skill reset <name>

Remove a customized skill from `skills/` and notify the user to install the platform version.

## Usage

```
/skill reset <skill-name>
```

## What it does

1. Verifies the skill has `x-augur-upstream` set (was originally a platform skill)
2. Deletes `skills/<name>/`
3. Removes the generated client stub
4. Notifies the user to install the platform version via their AI client

## Steps

1. Call `skill-status` MCP tool with the skill name
2. If source is not "augur" or has no upstream, tell the user this skill cannot be reset
3. Warn the user: "This will delete skills/<name>/ and its customizations. Git history is the safety net. Proceed?"
4. On confirmation, call `skill-reset` MCP tool
5. Display the install instruction from the response
```

- [ ] **Step 3: Create `/skill status` command**

Create `skills/import/commands/skill-status.md`:

```markdown
---
name: skill-status
description: Show the lifecycle status of a skill
---

# /skill status <name>

Show where a skill lives, its source, and whether updates are available.

## Usage

```
/skill status <skill-name>
```

## Steps

1. Call `skill-status` MCP tool with the skill name
2. Display results as a table:
   - Name
   - Source (augur / claude-local / claude-global / codex-local / codex-global)
   - Location (file path)
   - Upstream (if ejected)
   - Update available (yes/no)
```

- [ ] **Step 4: Create `/skill refresh` command**

Create `skills/import/commands/skill-refresh.md`:

```markdown
---
name: skill-refresh
description: Force rescan of all skill locations
---

# /skill refresh

Force a rescan of all skill directories (skills/, client folders) and invalidate the discovery cache.

## Usage

```
/skill refresh
```

## Steps

1. Call the Python discovery cache invalidation
2. Report: "Discovery cache invalidated. Next query will rescan all locations."
```

- [ ] **Step 5: Commit**

```bash
git add skills/import/commands/
git commit -m "feat(commands): add /skill eject, reset, status, refresh slash commands"
```

---

### Task 10: Integration Test — Full Lifecycle

**Files:**
- Create: `tests/integration/test_skill_lifecycle_integration.py`

- [ ] **Step 1: Write the integration test**

Create `tests/integration/test_skill_lifecycle_integration.py`:

```python
"""Integration test for the full skill lifecycle: discover → eject → discover → reset."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from src.plugins.skill_discovery import (
    _discover_all_skills_impl,
    invalidate_discovery_cache,
)
from src.mcp.augur_mcp.core.skill_lifecycle import eject_skill, reset_skill, skill_status


def _create_skill_md(path: Path, name: str, extra_fm: str = ""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nname: {name}\ndescription: {name} skill\n{extra_fm}---\n\nBody.\n")


def test_full_lifecycle():
    """Test: platform skill → eject → augur skill → reset → removed."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "skills").mkdir()
        (root / ".claude" / "skills" / "ui-tool").mkdir(parents=True)
        _create_skill_md(root / ".claude" / "skills" / "ui-tool" / "SKILL.md", "ui-tool")

        # Phase 1: Discovery finds the Claude local skill
        with patch("src.plugins.skill_discovery.get_skills_dir", return_value=root / "skills"), \
             patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]), \
             patch("src.plugins.skill_discovery._get_client_skill_dirs", return_value={
                 "claude-local": root / ".claude" / "skills",
                 "claude-global": Path("/nonexistent"),
                 "codex-local": Path("/nonexistent"),
                 "codex-global": Path("/nonexistent"),
             }):
            invalidate_discovery_cache()
            skills = _discover_all_skills_impl()

        ui = next((s for s in skills if s.name == "ui-tool"), None)
        assert ui is not None
        assert ui.source == "claude-local"

        # Phase 2: Eject
        result = eject_skill("ui-tool", "claude-local", root)
        assert result["success"] is True
        assert (root / "skills" / "ui-tool" / "SKILL.md").exists()

        # Phase 3: Discovery now finds it as augur
        with patch("src.plugins.skill_discovery.get_skills_dir", return_value=root / "skills"), \
             patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]), \
             patch("src.plugins.skill_discovery._get_client_skill_dirs", return_value={
                 "claude-local": root / ".claude" / "skills",
                 "claude-global": Path("/nonexistent"),
                 "codex-local": Path("/nonexistent"),
                 "codex-global": Path("/nonexistent"),
             }):
            invalidate_discovery_cache()
            skills = _discover_all_skills_impl()

        ui = next((s for s in skills if s.name == "ui-tool"), None)
        assert ui is not None
        assert ui.source == "augur"

        # Phase 4: Status shows augur with upstream
        status = skill_status("ui-tool", root)
        assert status["source"] == "augur"
        assert status["upstream"] == "claude-local"

        # Phase 5: Reset
        result = reset_skill("ui-tool", root)
        assert result["success"] is True
        assert not (root / "skills" / "ui-tool").exists()
        assert "install" in result["message"].lower()
```

- [ ] **Step 2: Run integration test**

Run: `cd ~/Projects/Augur && python -m pytest tests/integration/test_skill_lifecycle_integration.py -v`
Expected: All assertions PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_skill_lifecycle_integration.py
git commit -m "test: add integration test for full skill lifecycle (discover → eject → reset)"
```

---

### Task 11: Update `generate_client_stubs.py` to Skip Platform Skills

**Files:**
- Modify: `scripts/generate_client_stubs.py:205-260` (`cleanup_stale_stubs`)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_generate_stubs_source.py`:

```python
def test_cleanup_does_not_delete_platform_skills():
    """Cleanup should not delete client skills that don't have the AUGUR-GENERATED marker."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".claude" / "skills" / "platform-tool").mkdir(parents=True)

        # Platform skill — no AUGUR-GENERATED marker
        (root / ".claude" / "skills" / "platform-tool" / "SKILL.md").write_text(
            "---\nname: platform-tool\ndescription: a platform skill\n---\n\nBody.\n"
        )

        from scripts.generate_client_stubs import cleanup_stale_stubs
        deleted = cleanup_stale_stubs(root, existing_names=set())

        # Should NOT be deleted — it's not generated by Augur
        assert len(deleted) == 0
        assert (root / ".claude" / "skills" / "platform-tool" / "SKILL.md").exists()
```

- [ ] **Step 2: Run test to verify it passes (existing behavior should already be correct)**

Run: `cd ~/Projects/Augur && python -m pytest tests/unit/test_generate_stubs_source.py::test_cleanup_does_not_delete_platform_skills -v`
Expected: PASS — `cleanup_stale_stubs` already checks `is_generated()` before deleting

This test confirms the existing safety behavior. If it fails, fix `cleanup_stale_stubs` to respect the `is_generated()` check.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_generate_stubs_source.py
git commit -m "test: verify stub cleanup does not delete platform-managed skills"
```

---

### Task 12: Update SKILL.md for Import Skill

**Files:**
- Modify: `skills/import/SKILL.md` (add eject/reset commands documentation)

- [ ] **Step 1: Read current SKILL.md**

Read `skills/import/SKILL.md` to understand the current structure.

- [ ] **Step 2: Add lifecycle commands to the SKILL.md**

Add to the commands section of `skills/import/SKILL.md`:

```markdown
## Skill Lifecycle Commands

### /skill eject <name>
Eject a platform-managed skill to `skills/` for customization. Copies the full skill content and adds upstream tracking (`x-augur-upstream`).

### /skill reset <name>
Reset an ejected skill back to platform-managed. Deletes from `skills/`, removes the generated stub, and notifies you to install the platform version.

### /skill status <name>
Show lifecycle status: source, location, upstream tracking, update availability.

### /skill refresh
Force rescan of all skill directories and invalidate the discovery cache.
```

Also add `x-augur-commands` entries to the frontmatter:

```yaml
x-augur-commands:
  - skill-eject
  - skill-reset
  - skill-status
  - skill-refresh
```

- [ ] **Step 3: Commit**

```bash
git add skills/import/SKILL.md
git commit -m "docs: add skill lifecycle commands to import skill documentation"
```
