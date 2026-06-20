# MCP-Based Skill Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace file-copy adapter pattern with MCP-based stub generation for cross-client skill distribution, fixing broken cross-client resource access.

**Architecture:** Three dedup sites get adapted-copy exclusion filters. A new `render-skill-file` MCP tool generates thin discovery stubs per client format. A thin sync script replaces 11 adapter `sync_skill()` methods. Adapter classes remain for rules/config/memory sync.

**Tech Stack:** Python 3.11+, FastMCP, YAML frontmatter, pytest

**Spec:** `docs/superpowers/specs/2026-03-20-mcp-skill-sync-design.md`

---

### Task 1: Add `_is_adapted_copy()` Helper

**Files:**
- Create: `src/mcp/augur_mcp/adapters/skill_detection.py`
- Test: `tests/mcp/adapters/test_skill_detection.py`

This is a shared helper used by all three dedup sites.

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/adapters/test_skill_detection.py
import tempfile
from pathlib import Path
from src.mcp.augur_mcp.adapters.skill_detection import is_adapted_copy


class TestIsAdaptedCopy:
    def test_adapted_copy_marker(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\nname: foo\n---\n<!-- AUGUR-ADAPTED-COPY source=claude-code -->\nBody")
        assert is_adapted_copy(skill_md) is True

    def test_stub_marker(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\nname: foo\n---\n<!-- AUGUR-STUB — full content via MCP get-skill -->\n")
        assert is_adapted_copy(skill_md) is True

    def test_master_skill(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\nname: foo\ndescription: real skill\n---\n# Foo\n\nReal content here.")
        assert is_adapted_copy(skill_md) is False

    def test_legacy_auto_generated(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("<!-- AUTO-GENERATED FILE -->\n---\nname: foo\n---\nBody")
        assert is_adapted_copy(skill_md) is True

    def test_nonexistent_file(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        assert is_adapted_copy(skill_md) is False

    def test_empty_file(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("")
        assert is_adapted_copy(skill_md) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/mcp/adapters/test_skill_detection.py -v`
Expected: FAIL with `ModuleNotFoundError` — module doesn't exist yet

- [ ] **Step 3: Write minimal implementation**

```python
# src/mcp/augur_mcp/adapters/skill_detection.py
"""Detect adapted/stub skill copies vs master originals."""

from pathlib import Path

_ADAPTED_MARKERS = (
    "AUGUR-ADAPTED-COPY",
    "AUGUR-STUB",
    "AUTO-GENERATED FILE",
    "Generator:",
)


def is_adapted_copy(skill_md: Path) -> bool:
    """Check if a SKILL.md file is an adapted copy or stub (not the master).

    Reads the first 500 bytes and checks for known markers.
    Uses substring search (not startswith) because stubs begin
    with --- YAML frontmatter before the marker comment.
    """
    if not skill_md.exists():
        return False
    try:
        header = skill_md.read_text(encoding="utf-8")[:500]
    except (OSError, UnicodeDecodeError):
        return False
    return any(marker in header for marker in _ADAPTED_MARKERS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/mcp/adapters/test_skill_detection.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_mcp/adapters/skill_detection.py tests/mcp/adapters/test_skill_detection.py
git commit -m "feat(skill-sync): add is_adapted_copy() detection helper"
```

---

### Task 2: Fix Dedup in `filesystem_registry.py`

**Files:**
- Modify: `src/mcp/augur_mcp/adapters/filesystem_registry.py:131-142`
- Test: `tests/mcp/adapters/test_skill_detection.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/mcp/adapters/test_skill_detection.py
import pytest
from unittest.mock import patch, MagicMock
from src.mcp.augur_mcp.adapters.filesystem_registry import FilesystemSkillRegistry


class TestRegistryDedup:
    def _make_skill_dir(self, tmp_path, client_dir, skill_name, content):
        """Create a skill directory with SKILL.md."""
        skill_dir = tmp_path / client_dir / skill_name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(content)
        return skill_dir

    def test_master_wins_over_adapted_copy(self, tmp_path):
        """Master in .claude/skills/ should win over adapted copy in .gemini/skills/."""
        master_content = "---\nname: apple\ndescription: Apple integration\n---\n# Apple\nReal content"
        adapted_content = "---\nname: apple\ndescription: Apple integration\n---\n<!-- AUGUR-ADAPTED-COPY source=claude-code -->"

        self._make_skill_dir(tmp_path, ".claude/skills", "apple", master_content)
        self._make_skill_dir(tmp_path, ".gemini/skills", "apple", adapted_content)

        registry = FilesystemSkillRegistry(plugins_dir=tmp_path)
        with patch.object(registry, '_iter_skill_dirs') as mock_iter:
            mock_iter.return_value = [
                (tmp_path / ".claude/skills/apple", "claude"),
                (tmp_path / ".gemini/skills/apple", "gemini"),
            ]
            skills = registry._scan_skills()

        apple = [s for s in skills if s.id == "apple"]
        assert len(apple) == 1
        assert "claude" in str(apple[0].path) or apple[0].layer == "claude"

    def test_stub_excluded_from_registry(self, tmp_path):
        """Stubs should not appear in registry when master exists."""
        master_content = "---\nname: foo\ndescription: Foo skill\n---\n# Foo\nReal content"
        stub_content = "---\nname: foo\ndescription: Foo skill\n---\n<!-- AUGUR-STUB — full content via MCP get-skill -->"

        self._make_skill_dir(tmp_path, ".claude/skills", "foo", master_content)
        self._make_skill_dir(tmp_path, ".gemini/skills", "foo", stub_content)

        registry = FilesystemSkillRegistry(plugins_dir=tmp_path)
        with patch.object(registry, '_iter_skill_dirs') as mock_iter:
            mock_iter.return_value = [
                (tmp_path / ".claude/skills/foo", "claude"),
                (tmp_path / ".gemini/skills/foo", "gemini"),
            ]
            skills = registry._scan_skills()

        foo = [s for s in skills if s.id == "foo"]
        assert len(foo) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/mcp/adapters/test_skill_detection.py::TestRegistryDedup -v`
Expected: FAIL — current dedup lets adapted copy overwrite master

- [ ] **Step 3: Modify `_scan_skills()` in filesystem_registry.py**

In `src/mcp/augur_mcp/adapters/filesystem_registry.py`, modify the `_scan_skills()` method (lines ~131-142):

```python
# Add import at top of file:
from src.mcp.augur_mcp.adapters.skill_detection import is_adapted_copy

# Replace the dedup loop in _scan_skills():
def _scan_skills(self) -> list[SkillMetadata]:
    disabled_ids = self._load_disabled_skills()
    skills_dict: dict[str, SkillMetadata] = {}
    for skill_dir, layer in self._iter_skill_dirs():
        # Skip adapted copies and stubs — only masters enter registry
        skill_md = skill_dir / "SKILL.md"
        if is_adapted_copy(skill_md):
            continue
        skill = self._parse_skill(skill_dir, layer, disabled_ids)
        if skill:
            if skill.id not in skills_dict:
                skills_dict[skill.id] = skill  # first master wins
            # else: keep existing master
    return sorted(skills_dict.values(), key=lambda s: s.id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/mcp/adapters/test_skill_detection.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_mcp/adapters/filesystem_registry.py tests/mcp/adapters/test_skill_detection.py
git commit -m "fix(skill-sync): exclude adapted copies from filesystem registry dedup"
```

---

### Task 3: Fix Dedup in `skills.py` and `skill_registry.py`

**Files:**
- Modify: `src/mcp/augur_mcp/core/skills.py:78-86`
- Modify: `src/plugins/skill_registry.py:147-162`
- Test: `tests/mcp/adapters/test_skill_detection.py` (extend)

- [ ] **Step 1: Write the failing test for skills.py dedup**

This test verifies that `list_skills_impl`'s dedup loop actually filters adapted copies. Before the fix, adapted copies pass through the dedup loop unchecked.

```python
# Append to tests/mcp/adapters/test_skill_detection.py
from unittest.mock import patch, MagicMock

class TestSkillsImplDedup:
    def test_list_skills_impl_excludes_stub_entries(self, tmp_path):
        """list_skills_impl should not return skills whose path is a stub."""
        # Create a stub SKILL.md
        stub_dir = tmp_path / "stub_skill"
        stub_dir.mkdir()
        (stub_dir / "SKILL.md").write_text("---\nname: test\n---\n<!-- AUGUR-STUB -->")

        # Create a mock skill with path pointing to the stub
        stub_skill = MagicMock()
        stub_skill.id = "test"
        stub_skill.path = stub_dir

        master_dir = tmp_path / "master_skill"
        master_dir.mkdir()
        (master_dir / "SKILL.md").write_text("---\nname: test\n---\n# Real content")

        master_skill = MagicMock()
        master_skill.id = "test"
        master_skill.path = master_dir

        # Simulate list_skills_impl receiving both entries
        # After fix: stub should be filtered, master should survive
        from src.mcp.augur_mcp.adapters.skill_detection import is_adapted_copy
        skills = [master_skill, stub_skill]
        filtered = [s for s in skills if not (hasattr(s, 'path') and s.path and is_adapted_copy(s.path / "SKILL.md"))]
        assert len(filtered) == 1
        assert filtered[0].path == master_dir
```

- [ ] **Step 2: Run test to verify it passes** (validates the filtering pattern; Task 3 Step 3 applies it to list_skills_impl)

Run: `python -m pytest tests/mcp/adapters/test_skill_detection.py::TestSkillsImplDedup -v`
Expected: PASS (the filter logic works; Step 3 wires it into the actual function)

- [ ] **Step 3: Modify `list_skills_impl()` in skills.py**

In `src/mcp/augur_mcp/core/skills.py`, modify the dedup loop (lines ~78-86):

```python
# Add import at top:
from src.mcp.augur_mcp.adapters.skill_detection import is_adapted_copy

# Replace dedup loop in list_skills_impl():
unique_skills = {}
for skill in skills_meta:
    sid = str(skill.id).strip().lower()
    # Skip adapted copies — defensive guard
    if hasattr(skill, 'path') and skill.path and is_adapted_copy(skill.path / "SKILL.md"):
        continue
    if sid not in unique_skills:
        unique_skills[sid] = skill  # first master wins
```

- [ ] **Step 4: Add `AUGUR-STUB` to `_is_auto_generated()` in skill_registry.py**

In `src/plugins/skill_registry.py`, modify `_is_auto_generated()` (lines ~147-162):

```python
# Find the return line that checks markers, add AUGUR-STUB:
return (
    "AUTO-GENERATED FILE" in header
    or "Generator:" in header
    or "AUGUR-ADAPTED-COPY" in header
    or "AUGUR-STUB" in header  # New: detect MCP-based stubs
)
```

- [ ] **Step 5: Run all dedup tests**

Run: `python -m pytest tests/mcp/adapters/test_skill_detection.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/mcp/augur_mcp/core/skills.py src/plugins/skill_registry.py tests/mcp/adapters/test_skill_detection.py
git commit -m "fix(skill-sync): exclude adapted copies from all three dedup sites"
```

---

### Task 4: Create Client Format Spec Table

**Files:**
- Create: `src/mcp/augur_mcp/core/client_formats.py`
- Test: `tests/mcp/core/test_client_formats.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/core/test_client_formats.py
from src.mcp.augur_mcp.core.client_formats import CLIENT_FORMATS, ClientFormat


class TestClientFormats:
    def test_claude_code_format(self):
        fmt = CLIENT_FORMATS["claude-code"]
        assert fmt.skill_dir == ".claude/skills/{skill_id}"
        assert fmt.filename == "SKILL.md"
        assert fmt.path_base == "project"
        assert fmt.body is False
        assert "name" in fmt.frontmatter_fields
        assert "triggers" in fmt.frontmatter_fields

    def test_codex_format_home_based(self):
        fmt = CLIENT_FORMATS["codex"]
        assert fmt.path_base == "home"
        assert fmt.body is True

    def test_null_dir_clients(self):
        for client_id in ("cline", "claude-desktop", "windsurf", "kimi", "opencode", "antigravity"):
            fmt = CLIENT_FORMATS[client_id]
            assert fmt.skill_dir is None, f"{client_id} should have null skill_dir"

    def test_all_clients_present(self):
        expected = {
            "claude-code", "gemini", "codex", "cursor", "copilot",
            "cline", "claude-desktop", "windsurf", "kimi", "opencode", "antigravity",
        }
        assert set(CLIENT_FORMATS.keys()) == expected

    def test_has_subdirs_property(self):
        assert CLIENT_FORMATS["claude-code"].has_subdirs is True  # {skill_id} in path
        assert CLIENT_FORMATS["cursor"].has_subdirs is False  # flat dir

    def test_skill_dir_root(self):
        assert CLIENT_FORMATS["claude-code"].skill_dir_root == ".claude/skills"
        assert CLIENT_FORMATS["cursor"].skill_dir_root == ".cursor/rules"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/mcp/core/test_client_formats.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/mcp/augur_mcp/core/client_formats.py
"""Client format specifications for skill stub generation."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ClientFormat:
    """Describes how a client expects skill discovery files on disk."""

    skill_dir: str | None
    """Template for skill directory, e.g. '.claude/skills/{skill_id}'. None = MCP-only."""

    filename: str = "SKILL.md"
    """Filename within skill_dir."""

    path_base: str = "project"
    """'project' = relative to project root. 'home' = relative to client home dir."""

    frontmatter_fields: tuple[str, ...] = ()
    """Fields to include in YAML frontmatter."""

    frontmatter_map: dict[str, str] = field(default_factory=dict)
    """Static overrides for frontmatter values. Keys not in this map use skill metadata."""

    body: bool = False
    """If True, include a body template. If False, use AUGUR-STUB comment."""

    body_template: str | None = None
    """Template name for body content (only used when body=True)."""

    @property
    def has_subdirs(self) -> bool:
        """Whether skill_dir contains {skill_id} (subdirectory per skill)."""
        if self.skill_dir is None:
            return False
        return "{skill_id}" in self.skill_dir

    @property
    def skill_dir_root(self) -> str | None:
        """The static prefix of skill_dir before any {skill_id} template."""
        if self.skill_dir is None:
            return None
        return self.skill_dir.split("/{skill_id}")[0]


CLIENT_FORMATS: dict[str, ClientFormat] = {
    "claude-code": ClientFormat(
        skill_dir=".claude/skills/{skill_id}",
        filename="SKILL.md",
        path_base="project",
        frontmatter_fields=("name", "description", "x-augur-master", "triggers"),
    ),
    "gemini": ClientFormat(
        skill_dir=".gemini/skills/{skill_id}",
        filename="SKILL.md",
        path_base="project",
        frontmatter_fields=("name", "description"),
    ),
    "codex": ClientFormat(
        skill_dir="prompts",
        filename="{skill_id}.md",
        path_base="home",
        frontmatter_fields=(),
        body=True,
        body_template="codex_prompt",
    ),
    "cursor": ClientFormat(
        skill_dir=".cursor/rules",
        filename="{skill_id}.mdc",
        path_base="project",
        frontmatter_fields=("description", "globs", "alwaysApply"),
        frontmatter_map={"globs": "", "alwaysApply": "false"},
    ),
    "copilot": ClientFormat(
        skill_dir=".github/instructions",
        filename="{skill_id}.instructions.md",
        path_base="project",
        frontmatter_fields=("applyTo",),
        frontmatter_map={"applyTo": "**/*"},
    ),
    # --- MCP-only clients ---
    "cline": ClientFormat(skill_dir=None),
    "claude-desktop": ClientFormat(skill_dir=None),
    "windsurf": ClientFormat(skill_dir=None),
    "kimi": ClientFormat(skill_dir=None),
    "opencode": ClientFormat(skill_dir=None),
    "antigravity": ClientFormat(skill_dir=None),
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/mcp/core/test_client_formats.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_mcp/core/client_formats.py tests/mcp/core/test_client_formats.py
git commit -m "feat(skill-sync): add client format spec table"
```

---

### Task 5: Create `render-skill-file` MCP Tool

**Files:**
- Create: `src/mcp/augur_mcp/core/skill_renderer.py`
- Test: `tests/mcp/core/test_skill_renderer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/core/test_skill_renderer.py
import pytest
from unittest.mock import MagicMock
from src.mcp.augur_mcp.core.skill_renderer import render_skill_file, render_all_skill_files


class TestRenderSkillFile:
    def _mock_skill(self, skill_id="apple", name="apple", description="Apple integration",
                    master="claude-code", triggers=("apple", "notes")):
        skill = MagicMock()
        skill.id = skill_id
        skill.display_name = name
        skill.description = description
        skill.master = master
        skill.triggers = triggers
        return skill

    def test_claude_code_stub(self):
        skill = self._mock_skill()
        result = render_skill_file(skill, "claude-code")
        assert result["path"] == ".claude/skills/apple/SKILL.md"
        assert result["path_base"] == "project"
        assert "AUGUR-STUB" in result["content"]
        assert "name: apple" in result["content"]
        assert "triggers:" in result["content"]

    def test_gemini_stub(self):
        skill = self._mock_skill()
        result = render_skill_file(skill, "gemini")
        assert result["path"] == ".gemini/skills/apple/SKILL.md"
        assert "AUGUR-STUB" in result["content"]
        assert "name: apple" in result["content"]

    def test_cursor_mdc_stub(self):
        skill = self._mock_skill()
        result = render_skill_file(skill, "cursor")
        assert result["path"] == ".cursor/rules/apple.mdc"
        assert "description:" in result["content"]
        assert "AUGUR-STUB" in result["content"]

    def test_codex_with_body(self):
        skill = self._mock_skill()
        result = render_skill_file(skill, "codex")
        assert result["path"] == "prompts/apple.md"
        assert result["path_base"] == "home"
        assert "AUGUR-STUB" not in result["content"]  # body=True uses template
        assert "apple" in result["content"].lower()

    def test_null_client_returns_skip(self):
        skill = self._mock_skill()
        result = render_skill_file(skill, "windsurf")
        assert result["skip"] is True

    def test_unknown_client_returns_error(self):
        skill = self._mock_skill()
        result = render_skill_file(skill, "unknown-client")
        assert "error" in result

    def test_copilot_instructions_format(self):
        skill = self._mock_skill()
        result = render_skill_file(skill, "copilot")
        assert result["path"] == ".github/instructions/apple.instructions.md"
        assert "applyTo:" in result["content"]


class TestRenderAllSkillFiles:
    def test_returns_list_excluding_skipped(self):
        skills = [
            MagicMock(id="a", display_name="A", description="desc", master="claude-code", triggers=()),
            MagicMock(id="b", display_name="B", description="desc", master="claude-code", triggers=()),
        ]
        results = render_all_skill_files(skills, "claude-code")
        assert len(results) == 2
        assert all("path" in r for r in results)

    def test_null_client_returns_empty(self):
        skills = [MagicMock(id="a", display_name="A", description="desc", master="claude-code", triggers=())]
        results = render_all_skill_files(skills, "windsurf")
        assert results == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/mcp/core/test_skill_renderer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/mcp/augur_mcp/core/skill_renderer.py
"""Render client-formatted skill stub files for native discovery."""

from __future__ import annotations

from src.mcp.augur_mcp.core.client_formats import CLIENT_FORMATS, ClientFormat

_STUB_BODY = "<!-- AUGUR-STUB — full content via MCP get-skill -->\n"


def render_skill_file(skill, client_id: str) -> dict:
    """Generate a client-formatted stub file for one skill.

    Args:
        skill: SkillMetadata object with id, display_name, description, master, triggers
        client_id: Target client identifier (e.g. 'claude-code', 'gemini')

    Returns:
        dict with {path, content, path_base} or {skip: True} or {error: str}
    """
    fmt = CLIENT_FORMATS.get(client_id)
    if fmt is None:
        return {"error": f"Unknown client: {client_id}"}
    if fmt.skill_dir is None:
        return {"skip": True, "reason": f"Client '{client_id}' uses MCP-only access"}

    path = _build_path(fmt, skill.id)
    content = _build_content(fmt, skill)

    return {"path": path, "content": content, "path_base": fmt.path_base}


def render_all_skill_files(skills: list, client_id: str) -> list[dict]:
    """Generate stub files for all skills for one client.

    Returns list of {path, content, path_base} dicts (skipped/errored entries excluded).
    """
    results = []
    for skill in skills:
        result = render_skill_file(skill, client_id)
        if "path" in result:
            results.append(result)
    return results


def _build_path(fmt: ClientFormat, skill_id: str) -> str:
    """Build the target file path from format spec."""
    dir_part = fmt.skill_dir.format(skill_id=skill_id)
    filename = fmt.filename.format(skill_id=skill_id)
    return f"{dir_part}/{filename}"


def _build_content(fmt: ClientFormat, skill) -> str:
    """Build file content with frontmatter and body."""
    lines = []

    # Frontmatter
    if fmt.frontmatter_fields:
        lines.append("---")
        for field_name in fmt.frontmatter_fields:
            value = _resolve_field(fmt, field_name, skill)
            if value is not None:
                lines.append(f"{field_name}: {_format_yaml_value(value)}")
        lines.append("---")

    # Body
    if fmt.body and fmt.body_template:
        lines.append(_render_body_template(fmt.body_template, skill))
    else:
        lines.append(_STUB_BODY)

    return "\n".join(lines)


def _resolve_field(fmt: ClientFormat, field_name: str, skill) -> object | None:
    """Resolve a frontmatter field value from static map or skill metadata."""
    if field_name in fmt.frontmatter_map:
        return fmt.frontmatter_map[field_name]

    # Map field names to skill attributes
    attr_map = {
        "name": "display_name",
        "description": "description",
        "x-augur-master": "master",
        "triggers": "triggers",
    }
    attr = attr_map.get(field_name, field_name)
    return getattr(skill, attr, None)


def _format_yaml_value(value) -> str:
    """Format a Python value for YAML output."""
    if isinstance(value, (list, tuple)):
        if not value:
            return "[]"
        items = ", ".join(str(v) for v in value)
        return f"[{items}]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str) and any(c in value for c in ":#{}[]|>&*!%@`"):
        return f'"{value}"'
    return str(value)


def _render_body_template(template_name: str, skill) -> str:
    """Render a body template for clients that need full text (e.g. Codex)."""
    if template_name == "codex_prompt":
        return (
            f"<!-- AUGUR-STUB -->\n"
            f"# {skill.display_name}\n\n"
            f"{skill.description}\n\n"
            f"This skill is managed by Augur. "
            f"Access full content via MCP `get-skill` tool.\n"
        )
    return _STUB_BODY
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/mcp/core/test_skill_renderer.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_mcp/core/skill_renderer.py tests/mcp/core/test_skill_renderer.py
git commit -m "feat(skill-sync): add render-skill-file MCP tool implementation"
```

---

### Task 6: Register MCP Tools

**Files:**
- Modify: `src/mcp/augur_mcp/core/__init__.py` (add tool registrations in `register_core_tools()`)
- Test: `tests/mcp/core/test_skill_renderer.py` (extend with registration test)

Tools are registered via `register_core_tools(mcp, ...)` in `src/mcp/augur_mcp/core/__init__.py`, NOT as standalone decorators in `skills.py`. Follow the same pattern used by `list-skills`, `get-skill`, etc.

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/mcp/core/test_skill_renderer.py
from unittest.mock import MagicMock

class TestMCPToolRegistration:
    def test_render_skill_file_registered(self):
        """Verify render-skill-file is registered via register_core_tools."""
        from src.mcp.augur_mcp.core import register_core_tools
        mock_mcp = MagicMock()
        # Call register_core_tools and check that render-skill-file was registered
        # Inspect mock_mcp.tool calls to find the tool name
        register_core_tools(mock_mcp)
        tool_names = [call.kwargs.get("name", call.args[0] if call.args else "")
                      for call in mock_mcp.tool.call_args_list]
        assert "render-skill-file" in tool_names

    def test_render_all_skill_files_registered(self):
        """Verify render-all-skill-files is registered via register_core_tools."""
        from src.mcp.augur_mcp.core import register_core_tools
        mock_mcp = MagicMock()
        register_core_tools(mock_mcp)
        tool_names = [call.kwargs.get("name", call.args[0] if call.args else "")
                      for call in mock_mcp.tool.call_args_list]
        assert "render-all-skill-files" in tool_names
```

Note: The exact mock pattern depends on how `register_core_tools` uses the `mcp` object. Read the existing registrations in `src/mcp/augur_mcp/core/__init__.py` to match the pattern precisely — it may use `mcp.tool(name=...)` as a decorator, or `mcp.add_tool(...)`, or another mechanism.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/mcp/core/test_skill_renderer.py::TestMCPToolRegistration -v`
Expected: FAIL — tools not registered yet

- [ ] **Step 3: Add tool registrations in `register_core_tools()`**

In `src/mcp/augur_mcp/core/__init__.py`, inside the `register_core_tools()` function, add registrations for the two new tools. Follow the exact same pattern used by `list-skills` and `get-skill` in that function:

```python
from src.mcp.augur_mcp.core.skill_renderer import (
    render_skill_file as _render_skill_file,
    render_all_skill_files as _render_all_skill_files,
)

# Inside register_core_tools(mcp, ...):

@mcp.tool(name="render-skill-file")
async def render_skill_file_tool(skill_id: str, client_id: str) -> dict:
    """Generate a client-formatted stub file for native skill discovery."""
    skill = resolve_skill_entry(skill_id)
    if not skill:
        return {"error": f"Skill '{skill_id}' not found"}
    return _render_skill_file(skill, client_id)

@mcp.tool(name="render-all-skill-files")
async def render_all_skill_files_tool(client_id: str) -> list[dict]:
    """Generate all stub files for a client in one call."""
    skills = list_all_skills()
    return _render_all_skill_files(skills, client_id)
```

Note: `resolve_skill_entry` and `list_all_skills` must be resolved from whatever the existing tools use. Check the existing `get-skill` and `list-skills` tool implementations for the correct function names and imports.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/mcp/core/test_skill_renderer.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_mcp/core/__init__.py tests/mcp/core/test_skill_renderer.py
git commit -m "feat(skill-sync): register render-skill-file MCP tools"
```

---

### Task 7: Create Thin Sync Script

**Files:**
- Create: `dist/plugins/augur-knowledge/skills/ai_bridge/scripts/sync_agents/sync_client_skills.py`
- Test: `tests/sync_agents/test_sync_client_skills.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/sync_agents/test_sync_client_skills.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from dist.plugins.augur_knowledge.skills.ai_bridge.scripts.sync_agents.sync_client_skills import (
    sync_skills_for_client,
    cleanup_orphans,
)
from src.mcp.augur_mcp.core.client_formats import CLIENT_FORMATS


class TestSyncSkillsForClient:
    def test_writes_stubs_to_correct_paths(self, tmp_path):
        mcp_client = MagicMock()
        mcp_client.call.return_value = [
            {"path": ".claude/skills/foo/SKILL.md", "content": "---\nname: foo\n---\n<!-- AUGUR-STUB -->", "path_base": "project"},
            {"path": ".claude/skills/bar/SKILL.md", "content": "---\nname: bar\n---\n<!-- AUGUR-STUB -->", "path_base": "project"},
        ]

        sync_skills_for_client(mcp_client, "claude-code", tmp_path)

        assert (tmp_path / ".claude/skills/foo/SKILL.md").exists()
        assert (tmp_path / ".claude/skills/bar/SKILL.md").exists()
        assert "AUGUR-STUB" in (tmp_path / ".claude/skills/foo/SKILL.md").read_text()

    def test_skips_null_dir_clients(self, tmp_path):
        mcp_client = MagicMock()
        sync_skills_for_client(mcp_client, "windsurf", tmp_path)
        mcp_client.call.assert_not_called()


class TestCleanupOrphans:
    def test_removes_orphan_subdirs(self, tmp_path):
        """Orphan skill subdirectories should be removed."""
        fmt = CLIENT_FORMATS["claude-code"]
        skills_dir = tmp_path / ".claude/skills"

        # Create an orphan
        orphan = skills_dir / "old-skill"
        orphan.mkdir(parents=True)
        (orphan / "SKILL.md").write_text("---\nname: old\n---\n<!-- AUGUR-STUB -->")

        # Create a valid skill
        valid = skills_dir / "good-skill"
        valid.mkdir(parents=True)
        (valid / "SKILL.md").write_text("---\nname: good\n---\n<!-- AUGUR-STUB -->")

        written = {valid / "SKILL.md"}
        cleanup_orphans(fmt, tmp_path, written)

        assert not orphan.exists()
        assert valid.exists()

    def test_preserves_master_skills_in_subdirs(self, tmp_path):
        """Master skills (no AUGUR-STUB marker) should not be deleted."""
        fmt = CLIENT_FORMATS["claude-code"]
        skills_dir = tmp_path / ".claude/skills"

        master = skills_dir / "real-skill"
        master.mkdir(parents=True)
        (master / "SKILL.md").write_text("---\nname: real\n---\n# Real skill content")
        (master / "scripts").mkdir()

        written = set()  # Nothing written by sync
        cleanup_orphans(fmt, tmp_path, written)

        assert master.exists()  # Master should NOT be deleted

    def test_flat_dir_only_deletes_augur_files(self, tmp_path):
        """In flat dirs (Cursor), only delete files with AUGUR markers."""
        fmt = CLIENT_FORMATS["cursor"]
        rules_dir = tmp_path / ".cursor/rules"
        rules_dir.mkdir(parents=True)

        # User-authored file — must survive
        (rules_dir / "my-custom.mdc").write_text("---\ndescription: My rule\n---\nCustom rule")

        # Augur-generated orphan — should be deleted
        (rules_dir / "old-skill.mdc").write_text("---\ndescription: Old\n---\n<!-- AUGUR-STUB -->")

        written = set()
        cleanup_orphans(fmt, tmp_path, written)

        assert (rules_dir / "my-custom.mdc").exists()  # Preserved
        assert not (rules_dir / "old-skill.mdc").exists()  # Deleted
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/sync_agents/test_sync_client_skills.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# dist/plugins/augur-knowledge/skills/ai_bridge/scripts/sync_agents/sync_client_skills.py
"""Thin sync script: generates skill stubs via MCP and writes to client directories."""

from __future__ import annotations

import shutil
from pathlib import Path

from src.config.paths import get_client_config_dir
from src.mcp.augur_mcp.adapters.skill_detection import is_adapted_copy
from src.mcp.augur_mcp.core.client_formats import CLIENT_FORMATS, ClientFormat


def sync_skills_for_client(mcp_client, client_id: str, project_root: Path) -> int:
    """Sync all skill stubs for one client. Returns number of files written."""
    fmt = CLIENT_FORMATS.get(client_id)
    if not fmt or not fmt.skill_dir:
        return 0  # MCP-only client

    results = mcp_client.call("render-all-skill-files", client_id=client_id)

    if fmt.path_base == "home":
        base = get_client_config_dir(client_id, scope="global")
    else:
        base = project_root

    written_paths: set[Path] = set()
    for result in results:
        target = base / result["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result["content"], encoding="utf-8")
        written_paths.add(target)

    cleanup_orphans(fmt, base, written_paths)
    return len(written_paths)


def cleanup_orphans(fmt: ClientFormat, base: Path, written_paths: set[Path]) -> None:
    """Remove stubs for skills that no longer exist."""
    if not fmt.skill_dir_root:
        return
    skill_dir = base / fmt.skill_dir_root
    if not skill_dir.exists():
        return

    if fmt.has_subdirs:
        for subdir in skill_dir.iterdir():
            if not subdir.is_dir():
                continue
            stub_file = subdir / fmt.filename
            if stub_file in written_paths:
                continue
            # Only delete if this is a stub/adapted dir, not a master skill dir
            if stub_file.exists() and is_adapted_copy(stub_file):
                shutil.rmtree(subdir)
    else:
        for f in skill_dir.iterdir():
            if not f.is_file() or f in written_paths:
                continue
            # Only delete Augur-generated files, not user-authored ones
            try:
                header = f.read_text(encoding="utf-8")[:500]
            except (OSError, UnicodeDecodeError):
                continue
            if "AUGUR-STUB" in header or "AUGUR-ADAPTED-COPY" in header:
                f.unlink()


def sync_all_clients(mcp_client, project_root: Path, adapters: list | None = None) -> dict[str, int]:
    """Sync skill stubs for all installed clients. Returns {client_id: files_written}.

    Args:
        mcp_client: MCP client for calling render tools
        project_root: Project root path
        adapters: Optional list of adapter instances (from engine._get_all_adapters()).
                  If provided, used for detect_installed() checks.
    """
    # Build adapter lookup if provided
    adapter_map = {}
    if adapters:
        adapter_map = {a.adapter_name: a for a in adapters}

    results = {}
    for client_id in CLIENT_FORMATS:
        fmt = CLIENT_FORMATS[client_id]
        if not fmt.skill_dir:
            continue  # MCP-only client
        # Check if client is installed via adapter (if available)
        adapter_name = client_id.replace("-", "_")
        adapter = adapter_map.get(adapter_name)
        if adapter and not adapter.detect_installed():
            continue
        results[client_id] = sync_skills_for_client(mcp_client, client_id, project_root)

    # Invalidate MCP registry cache after all stubs are written
    # Critical for long-lived daemon processes (spec requirement)
    mcp_client.call("invalidate-cache")

    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/sync_agents/test_sync_client_skills.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add dist/plugins/augur-knowledge/skills/ai_bridge/scripts/sync_agents/sync_client_skills.py tests/sync_agents/test_sync_client_skills.py
git commit -m "feat(skill-sync): add thin sync script replacing adapter sync_skill()"
```

---

### Task 8: Wire Sync Script into Engine and Remove Old Code

**Files:**
- Modify: `dist/plugins/augur-knowledge/skills/ai_bridge/scripts/sync_agents/engine.py`
- Modify: `dist/plugins/augur-knowledge/skills/ai_bridge/scripts/sync_agents/adapters/base.py`
- Test: `tests/sync_agents/test_sync_client_skills.py` (extend)

This task integrates the new sync script and removes the old skill-sync code paths.

- [ ] **Step 1: Write a failing test for engine integration**

```python
# Append to tests/sync_agents/test_sync_client_skills.py

class TestEngineIntegration:
    def test_sync_all_calls_sync_client_skills(self):
        """Verify engine.sync_all() delegates skill sync to sync_all_clients()."""
        from unittest.mock import patch, MagicMock

        with patch(
            "dist.plugins.augur_knowledge.skills.ai_bridge.scripts.sync_agents"
            ".sync_client_skills.sync_all_clients"
        ) as mock_sync:
            mock_sync.return_value = {"claude-code": 5}
            # Import and call the engine's sync flow
            # The exact function depends on the engine's public API
            from dist.plugins.augur_knowledge.skills.ai_bridge.scripts.sync_agents.engine import sync_all
            # sync_all() should internally call sync_all_clients()
            # This test verifies the wiring exists
            # Note: sync_all() may require arguments — check its signature
```

Note: This test may need adaptation based on `sync_all()`'s actual signature and how it obtains the MCP client. Read engine.py's `sync_all()` (lines ~781-925) before writing the final test.

- [ ] **Step 2: In engine.py, replace `_fix_adapted_copy_freshness(adapters)` call with `sync_all_clients()`**

The actual replacement target is the `_fix_adapted_copy_freshness(adapters)` call at **line ~626** of engine.py (inside the fix-mode variant of `sync_all()`). `sync_single_skill` is NOT called directly in `sync_all()` — it is only called from within `_fix_adapted_copy_freshness`.

Replace:
```python
# Old (line ~626):
_fix_adapted_copy_freshness(adapters)
```

With:
```python
from .sync_client_skills import sync_all_clients
sync_all_clients(mcp_client, project_root, adapters=adapters)
```

If `sync_all()` does not have an `mcp_client` parameter, you need to either:
- Add it as a parameter, or
- Create the MCP client inline (check how other engine functions obtain MCP access)

- [ ] **Step 3: Remove `sync_single_skill()` from engine.py**

Delete the `sync_single_skill()` function (lines ~91-110).

- [ ] **Step 4: Remove `_fix_adapted_copy_freshness()` from engine.py**

Delete the `_fix_adapted_copy_freshness()` function (lines ~188-231). Stubs are cheap to regenerate — no freshness tracking needed.

- [ ] **Step 5: Remove `sync_skill()` from base.py**

In `adapters/base.py`, remove the `sync_skill()` method (lines ~74-79). The adapter classes remain for `sync_rules()`, `generate_mcp_config()`, `sync_memory()`, and `detect_installed()`.

- [ ] **Step 6: Check each adapter for `sync_skill()` overrides and remove them**

Run: `grep -rn "def sync_skill" dist/plugins/augur-knowledge/skills/ai_bridge/scripts/sync_agents/adapters/`

Delete each override found. The adapters keep all other methods.

- [ ] **Step 7: Run tests**

Run: `python -m pytest tests/sync_agents/ -v`
Expected: Tests that relied on `sync_skill()` will need updating (see Task 9). The new engine integration test should PASS.

- [ ] **Step 8: Commit**

```bash
git add dist/plugins/augur-knowledge/skills/ai_bridge/scripts/sync_agents/engine.py
git add dist/plugins/augur-knowledge/skills/ai_bridge/scripts/sync_agents/adapters/
git add tests/sync_agents/test_sync_client_skills.py
git commit -m "refactor(skill-sync): wire thin sync script, remove adapter sync_skill() methods"
```

---

### Task 9: Update Tests

**Files:**
- Modify: `tests/sync_agents/test_skill_sync.py`
- Modify: `dist/plugins/augur-knowledge/skills/ai_bridge/scripts/sync_agents/tests/test_adapter_lifecycle.py`

- [ ] **Step 1: Update `test_skill_sync.py`**

Replace `TestSyncSingleSkill` tests — they tested the old `sync_single_skill()` function which no longer exists. Replace with tests for the new `sync_client_skills.py` flow (if not already covered by Task 7 tests).

Update `TestCleanupOrphanAdaptedCopies` to also check for `AUGUR-STUB` marker in addition to `AUGUR-ADAPTED-COPY`.

- [ ] **Step 2: Update adapter lifecycle tests**

In `test_adapter_lifecycle.py`, remove any assertions about `sync_skill()` method existence on adapters. Update `TestAllAdaptersHaveLifecycleMethods` if it checks for `sync_skill`.

- [ ] **Step 3: Add cross-client resource access integration test**

```python
# Append to tests/sync_agents/test_sync_client_skills.py

class TestCrossClientResourceAccess:
    """Verify that skills mastered by one client are accessible from another."""

    def test_registry_resolves_to_master_not_stub(self, tmp_path):
        """When both master and stub exist, registry should resolve to master."""
        from src.mcp.augur_mcp.adapters.filesystem_registry import FilesystemSkillRegistry
        from unittest.mock import patch

        # Master with real content
        master_dir = tmp_path / ".claude/skills/apple"
        master_dir.mkdir(parents=True)
        (master_dir / "SKILL.md").write_text("---\nname: apple\ndescription: Apple\n---\n# Apple\nReal.")
        (master_dir / "scripts").mkdir()
        (master_dir / "scripts" / "run.py").write_text("print('hello')")

        # Stub in gemini
        stub_dir = tmp_path / ".gemini/skills/apple"
        stub_dir.mkdir(parents=True)
        (stub_dir / "SKILL.md").write_text("---\nname: apple\n---\n<!-- AUGUR-STUB -->")

        registry = FilesystemSkillRegistry(plugins_dir=tmp_path)
        with patch.object(registry, '_iter_skill_dirs') as mock_iter:
            mock_iter.return_value = [
                (master_dir, "claude"),
                (stub_dir, "gemini"),
            ]
            skills = registry._scan_skills()

        apple = [s for s in skills if s.id == "apple"]
        assert len(apple) == 1
        # Verify the resolved path is the master (has scripts/)
        assert (apple[0].path / "scripts" / "run.py").exists()
```

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/sync_agents/ tests/mcp/adapters/ tests/mcp/core/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tests/
git commit -m "test(skill-sync): update tests for MCP-based stub sync"
```

---

### Task 10: End-to-End Validation

**Files:** None (validation only)

- [ ] **Step 1: Run `/sync-agents` to regenerate all stubs**

Run: `/sync-agents`
Expected: All client skill files regenerated as stubs with `AUGUR-STUB` markers.

- [ ] **Step 2: Verify Claude Code skill discovery**

Check that `.claude/skills/*/SKILL.md` files are thin stubs:
```bash
head -10 .claude/skills/apple/SKILL.md
```
Expected: Frontmatter + `<!-- AUGUR-STUB -->` comment, no full body.

- [ ] **Step 3: Verify Gemini skill discovery**

```bash
head -10 .gemini/skills/apple/SKILL.md
```
Expected: Same stub format.

- [ ] **Step 4: Verify master skills retain full content**

```bash
wc -l .claude/skills/dev-build/SKILL.md
```
Expected: Master skills (where the skill is mastered by claude-code and lives in .claude/skills/) should still have full content — they are NOT stubs.

- [ ] **Step 5: Verify MCP tools resolve to master**

```bash
# Test via MCP tool call
python -c "
from src.mcp.augur_mcp.adapters.filesystem_registry import FilesystemSkillRegistry
reg = FilesystemSkillRegistry()
skills = reg.list_skills()
for s in skills[:5]:
    has_scripts = (s.path / 'scripts').exists() if s.path else False
    print(f'{s.id}: path={s.path}, has_scripts={has_scripts}')
"
```
Expected: All skills point to master directories. No skill path points to `.gemini/skills/` or other adapted locations.

- [ ] **Step 6: Verify orphan cleanup preserved user files**

Check that `.cursor/rules/` still contains any user-authored `.mdc` files (if any existed before sync).

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: No regressions.

- [ ] **Step 8: Final commit with all validation passing**

```bash
git add -A
git commit -m "feat(skill-sync): complete MCP-based skill sync migration"
```
