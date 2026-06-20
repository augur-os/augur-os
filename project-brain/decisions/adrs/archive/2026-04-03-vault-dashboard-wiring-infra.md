# Vault Dashboard Wiring — Infrastructure Plan (Plan A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the generic vault MCP tools and enhanced auto-page that all 31+ skills benefit from, plus two YAML quick-win pages.

**Architecture:** Two new Python MCP tools (`vault-file-read`, `vault-file-write`) in a new `vault_ops.py` core module. Enhanced `list_skill_vault_notes_impl` with directory grouping, type extraction, and higher limits. Upgraded `VaultNotesBlock.tsx` with collapsible directory sections, type-aware icons, and new config props. Two YAML page configs for linkedin-writer and lifestyle.

**Tech Stack:** Python (MCP tools), TypeScript/React (dashboard component), YAML (page configs)

**Spec:** `docs/superpowers/specs/2026-04-03-vault-dashboard-wiring-design.md`

**Plan B** (5 custom TSX pages for career, venture-augur, growth) will be written separately after this plan is complete.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/mcp/augur_mcp/core/vault_ops.py` | Create | vault-file-read + vault-file-write implementations |
| `src/mcp/augur_mcp/core/__init__.py` | Modify (lines 40-77, 338-356) | Register new tools, import vault_ops |
| `src/mcp/augur_mcp/core/skills.py` | Modify (lines 505-565) | Enhanced list_skill_vault_notes_impl |
| `apps/dashboard/components/blocks/types/VaultNotesBlock.tsx` | Modify (full file) | Directory grouping, type icons, new config props |
| `skills/linkedin-writer/augur/pages/overview.yaml` | Create | YAML page config |
| `skills/lifestyle/augur/pages/overview.yaml` | Create | YAML page config |
| `tests/packages/augur-mcp/core/test_vault_ops.py` | Create | Tests for vault-file-read/write |
| `tests/packages/augur-mcp/core/test_skill_vault_notes.py` | Create | Tests for enhanced vault notes |

---

### Task 1: Create vault-file-read MCP tool

**Files:**
- Create: `src/mcp/augur_mcp/core/vault_ops.py`
- Create: `tests/packages/augur-mcp/core/test_vault_ops.py`

- [ ] **Step 1: Write the test for vault-file-read**

```python
# tests/packages/augur-mcp/core/test_vault_ops.py
"""Tests for vault file read/write operations."""

import json
import pytest
from pathlib import Path


@pytest.fixture
def mock_vault(tmp_path, monkeypatch):
    """Create a mock vault directory with test files."""
    vault = tmp_path / "vault"
    vault.mkdir()
    # Create a skill directory with a markdown file
    skill_dir = vault / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "note.md").write_text(
        "---\ntitle: Test Note\ntype: note\n---\n\nThis is the body content.\n"
    )
    # Create a nested file
    sub = skill_dir / "ideas"
    sub.mkdir()
    (sub / "idea-one.md").write_text(
        "---\ntitle: Idea One\ntype: idea\n---\n\nGreat idea here.\n"
    )
    monkeypatch.setattr(
        "augur_mcp.core.vault_ops.get_skill_data_dir",
        lambda name: vault / name,
    )
    return vault


class TestVaultFileRead:
    @pytest.mark.asyncio
    async def test_read_existing_file(self, mock_vault):
        from augur_mcp.core.vault_ops import vault_file_read_impl

        result = json.loads(await vault_file_read_impl("test-skill", "note.md"))
        assert result["success"] is True
        assert result["frontmatter"]["title"] == "Test Note"
        assert result["frontmatter"]["type"] == "note"
        assert "This is the body content." in result["body"]
        assert result["lines"] > 0

    @pytest.mark.asyncio
    async def test_read_nested_file(self, mock_vault):
        from augur_mcp.core.vault_ops import vault_file_read_impl

        result = json.loads(await vault_file_read_impl("test-skill", "ideas/idea-one.md"))
        assert result["success"] is True
        assert result["frontmatter"]["title"] == "Idea One"

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, mock_vault):
        from augur_mcp.core.vault_ops import vault_file_read_impl

        result = json.loads(await vault_file_read_impl("test-skill", "nope.md"))
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_read_path_traversal_blocked(self, mock_vault):
        from augur_mcp.core.vault_ops import vault_file_read_impl

        result = json.loads(await vault_file_read_impl("test-skill", "../../etc/passwd"))
        assert result["success"] is False
        assert "traversal" in result["error"].lower() or "outside" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_read_nonexistent_skill(self, mock_vault):
        from augur_mcp.core.vault_ops import vault_file_read_impl

        result = json.loads(await vault_file_read_impl("no-such-skill", "note.md"))
        assert result["success"] is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/Projects/Augur && python -m pytest tests/packages/augur-mcp/core/test_vault_ops.py::TestVaultFileRead -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'augur_mcp.core.vault_ops'`

- [ ] **Step 3: Implement vault-file-read**

```python
# src/mcp/augur_mcp/core/vault_ops.py
"""Vault file read/write operations.

Generic tools for reading and writing individual vault files.
Used by TSX pages that need full file content (not just previews).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from augur_mcp.config import get_skill_data_dir


async def vault_file_read_impl(skill: str, path: str) -> str:
    """Read full content of a vault file by relative path.

    Args:
        skill: Skill name (resolves to vault/{skill}/)
        path: Relative path within the skill's vault dir

    Returns:
        JSON string with {success, frontmatter, body, lines, modified}
    """
    vault_dir = get_skill_data_dir(skill)
    if not vault_dir.is_dir():
        return json.dumps({"success": False, "error": f"Skill vault dir not found: {skill}"})

    target = (vault_dir / path).resolve()

    # Security: prevent path traversal outside skill vault dir
    try:
        target.relative_to(vault_dir.resolve())
    except ValueError:
        return json.dumps({"success": False, "error": "Path outside skill vault directory"})

    if not target.is_file():
        return json.dumps({"success": False, "error": f"File not found: {path}"})

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return json.dumps({"success": False, "error": str(e)})

    # Parse frontmatter
    frontmatter: dict[str, Any] = {}
    body = content
    if content.startswith("---"):
        end = content.find("\n---", 4)
        if end != -1:
            yaml_block = content[4:end]
            body = content[end + 4:]
            if body.startswith("\n"):
                body = body[1:]
            try:
                import yaml
                meta = yaml.safe_load(yaml_block)
                if isinstance(meta, dict):
                    frontmatter = meta
            except Exception:
                pass

    stat = target.stat()
    return json.dumps({
        "success": True,
        "frontmatter": frontmatter,
        "body": body,
        "lines": content.count("\n") + 1,
        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "path": str(target.relative_to(vault_dir)),
    }, default=str)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Projects/Augur && python -m pytest tests/packages/augur-mcp/core/test_vault_ops.py::TestVaultFileRead -v
```

Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_mcp/core/vault_ops.py tests/packages/augur-mcp/core/test_vault_ops.py
git commit -m "feat(mcp): add vault-file-read tool for full vault file content"
```

---

### Task 2: Create vault-file-write MCP tool

**Files:**
- Modify: `src/mcp/augur_mcp/core/vault_ops.py`
- Modify: `tests/packages/augur-mcp/core/test_vault_ops.py`

- [ ] **Step 1: Write the test for vault-file-write**

Append to `tests/packages/augur-mcp/core/test_vault_ops.py`:

```python
class TestVaultFileWrite:
    @pytest.mark.asyncio
    async def test_write_new_file(self, mock_vault):
        from augur_mcp.core.vault_ops import vault_file_write_impl

        result = json.loads(await vault_file_write_impl(
            skill="test-skill",
            path="new-note.md",
            title="New Note",
            body="Some content here.",
            metadata={"type": "note"},
        ))
        assert result["success"] is True
        assert result["created"] is True

        # Verify file was written
        written = (mock_vault / "test-skill" / "new-note.md").read_text()
        assert "title: New Note" in written
        assert "type: note" in written
        assert "Some content here." in written

    @pytest.mark.asyncio
    async def test_write_creates_parent_dirs(self, mock_vault):
        from augur_mcp.core.vault_ops import vault_file_write_impl

        result = json.loads(await vault_file_write_impl(
            skill="test-skill",
            path="deep/nested/file.md",
            title="Nested",
            body="Deep content.",
        ))
        assert result["success"] is True
        assert (mock_vault / "test-skill" / "deep" / "nested" / "file.md").exists()

    @pytest.mark.asyncio
    async def test_write_path_traversal_blocked(self, mock_vault):
        from augur_mcp.core.vault_ops import vault_file_write_impl

        result = json.loads(await vault_file_write_impl(
            skill="test-skill",
            path="../../evil.md",
            title="Evil",
            body="Bad.",
        ))
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_write_overwrites_existing(self, mock_vault):
        from augur_mcp.core.vault_ops import vault_file_write_impl

        result = json.loads(await vault_file_write_impl(
            skill="test-skill",
            path="note.md",
            title="Updated Note",
            body="Updated content.",
        ))
        assert result["success"] is True
        assert result["created"] is False

        written = (mock_vault / "test-skill" / "note.md").read_text()
        assert "Updated Note" in written
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/Projects/Augur && python -m pytest tests/packages/augur-mcp/core/test_vault_ops.py::TestVaultFileWrite -v
```

Expected: FAIL with `ImportError: cannot import name 'vault_file_write_impl'`

- [ ] **Step 3: Implement vault-file-write**

Append to `src/mcp/augur_mcp/core/vault_ops.py`:

```python
async def vault_file_write_impl(
    skill: str,
    path: str,
    title: str,
    body: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Write a vault file with frontmatter.

    Args:
        skill: Skill name (resolves to vault/{skill}/)
        path: Relative path within the skill's vault dir
        title: Title for frontmatter
        body: Markdown body content
        metadata: Additional frontmatter fields (optional)

    Returns:
        JSON string with {success, path, created}
    """
    vault_dir = get_skill_data_dir(skill)
    target = (vault_dir / path).resolve()

    # Security: prevent path traversal
    try:
        target.relative_to(vault_dir.resolve())
    except ValueError:
        return json.dumps({"success": False, "error": "Path outside skill vault directory"})

    created = not target.exists()

    fm: dict[str, Any] = {"title": title}
    if metadata:
        fm.update(metadata)

    from src.lib.frontmatter_utils import write_frontmatter
    try:
        write_frontmatter(target, fm, body)
    except OSError as e:
        return json.dumps({"success": False, "error": str(e)})

    return json.dumps({
        "success": True,
        "path": str(target.relative_to(vault_dir)),
        "created": created,
    })
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Projects/Augur && python -m pytest tests/packages/augur-mcp/core/test_vault_ops.py -v
```

Expected: 9 PASS (5 read + 4 write)

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_mcp/core/vault_ops.py tests/packages/augur-mcp/core/test_vault_ops.py
git commit -m "feat(mcp): add vault-file-write tool for creating vault files"
```

---

### Task 3: Register vault tools in core MCP server

**Files:**
- Modify: `src/mcp/augur_mcp/core/__init__.py` (lines 49-77 imports, ~356 registration)

- [ ] **Step 1: Add imports**

In `src/mcp/augur_mcp/core/__init__.py`, add after line 64 (`from .skill_lifecycle import ...`):

```python
from .vault_ops import vault_file_read_impl, vault_file_write_impl
```

- [ ] **Step 2: Register vault-file-read tool**

After the `list_skill_vault_notes` registration block (after line 356), add:

```python
    @mcp.tool(
        name="vault-file-read",
        annotations=tool_annotations(
            {
                "title": "Read Vault File",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def vault_file_read(skill: str = "", path: str = "", skillId: str = "", skill_id: str = "") -> str:
        """Read full content of a specific vault file (frontmatter + body)."""
        name = skill or skillId or skill_id
        return await vault_file_read_impl(name, path)

    if mcp_tool_interceptor:
        vault_file_read = mcp_tool_interceptor(vault_file_read)
```

- [ ] **Step 3: Register vault-file-write tool**

Immediately after vault-file-read registration:

```python
    @mcp.tool(
        name="vault-file-write",
        annotations=tool_annotations(
            {
                "title": "Write Vault File",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def vault_file_write(
        skill: str = "",
        path: str = "",
        title: str = "",
        body: str = "",
        metadata: dict | None = None,
        skillId: str = "",
        skill_id: str = "",
    ) -> str:
        """Write a vault file with YAML frontmatter. Creates parent dirs."""
        name = skill or skillId or skill_id
        return await vault_file_write_impl(name, path, title, body, metadata)

    if mcp_tool_interceptor:
        vault_file_write = mcp_tool_interceptor(vault_file_write)
```

- [ ] **Step 4: Verify MCP server starts**

```bash
cd ~/Projects/Augur && python -c "from augur_mcp.core import register_tools; print('OK')"
```

Expected: `OK` (no import errors)

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_mcp/core/__init__.py
git commit -m "feat(mcp): register vault-file-read and vault-file-write tools"
```

---

### Task 4: Enhance list_skill_vault_notes_impl

**Files:**
- Modify: `src/mcp/augur_mcp/core/skills.py` (lines 505-565)
- Create: `tests/packages/augur-mcp/core/test_skill_vault_notes.py`

- [ ] **Step 1: Write tests for enhanced behavior**

```python
# tests/packages/augur-mcp/core/test_skill_vault_notes.py
"""Tests for enhanced list_skill_vault_notes_impl."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock


@pytest.fixture
def mock_skill_vault(tmp_path, monkeypatch):
    """Create vault with structured subdirectories."""
    vault = tmp_path / "vault" / "test-skill"
    vault.mkdir(parents=True)

    # Root files
    (vault / "readme.md").write_text("---\ntitle: README\ntype: doc\n---\n\nSkill readme.\n")

    # ideas/ subdir with small files
    ideas = vault / "ideas"
    ideas.mkdir()
    (ideas / "idea-a.md").write_text("---\ntitle: Idea A\ntype: idea\n---\n\nFirst idea.\n")
    (ideas / "idea-b.md").write_text("---\ntitle: Idea B\ntype: idea\n---\n\nSecond idea.\n")

    # notes/ subdir
    notes = vault / "notes"
    notes.mkdir()
    (notes / "long-note.md").write_text("---\ntitle: Long Note\ntype: note\n---\n\n" + "Line.\n" * 150)

    # Nested 3 levels
    deep = vault / "archive" / "2025"
    deep.mkdir(parents=True)
    (deep / "old.md").write_text("---\ntitle: Old\n---\n\nArchived.\n")

    skill_entry = MagicMock()
    skill_entry.name = "test-skill"

    monkeypatch.setattr(
        "augur_mcp.core.skills.get_skill_data_dir",
        lambda name: tmp_path / "vault" / name,
    )

    def resolve(name):
        if name == "test-skill":
            return skill_entry
        return None

    return vault, resolve


class TestEnhancedVaultNotes:
    @pytest.mark.asyncio
    async def test_returns_groups(self, mock_skill_vault):
        from augur_mcp.core.skills import list_skill_vault_notes_impl
        vault, resolve = mock_skill_vault

        result = json.loads(await list_skill_vault_notes_impl("test-skill", resolve))
        assert "groups" in result
        assert "stats" in result
        assert result["stats"]["total_files"] == 5
        assert result["stats"]["total_dirs"] >= 3

    @pytest.mark.asyncio
    async def test_groups_have_directory_names(self, mock_skill_vault):
        from augur_mcp.core.skills import list_skill_vault_notes_impl
        vault, resolve = mock_skill_vault

        result = json.loads(await list_skill_vault_notes_impl("test-skill", resolve))
        dir_names = [g["directory"] for g in result["groups"]]
        assert "ideas" in dir_names
        assert "notes" in dir_names

    @pytest.mark.asyncio
    async def test_files_have_type_and_lines(self, mock_skill_vault):
        from augur_mcp.core.skills import list_skill_vault_notes_impl
        vault, resolve = mock_skill_vault

        result = json.loads(await list_skill_vault_notes_impl("test-skill", resolve))
        # Find the ideas group
        ideas_group = next(g for g in result["groups"] if g["directory"] == "ideas")
        file_entry = ideas_group["files"][0]
        assert "type" in file_entry
        assert "lines" in file_entry
        assert file_entry["type"] == "idea"

    @pytest.mark.asyncio
    async def test_3_levels_deep(self, mock_skill_vault):
        from augur_mcp.core.skills import list_skill_vault_notes_impl
        vault, resolve = mock_skill_vault

        result = json.loads(await list_skill_vault_notes_impl("test-skill", resolve))
        # archive/2025/old.md should be found at 3 levels
        all_files = [f["name"] for g in result["groups"] for f in g["files"]]
        assert any("old.md" in f for f in all_files)

    @pytest.mark.asyncio
    async def test_preview_500_chars(self, mock_skill_vault):
        from augur_mcp.core.skills import list_skill_vault_notes_impl
        vault, resolve = mock_skill_vault

        result = json.loads(await list_skill_vault_notes_impl("test-skill", resolve))
        notes_group = next(g for g in result["groups"] if g["directory"] == "notes")
        long_file = notes_group["files"][0]
        assert len(long_file["preview"]) <= 500

    @pytest.mark.asyncio
    async def test_backwards_compatible_notes_array(self, mock_skill_vault):
        from augur_mcp.core.skills import list_skill_vault_notes_impl
        vault, resolve = mock_skill_vault

        result = json.loads(await list_skill_vault_notes_impl("test-skill", resolve))
        # Old consumers read result["notes"]
        assert "notes" in result
        assert isinstance(result["notes"], list)
        assert len(result["notes"]) == 5
        # Each note has the old shape
        note = result["notes"][0]
        assert "name" in note
        assert "modified" in note
        assert "preview" in note
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/Augur && python -m pytest tests/packages/augur-mcp/core/test_skill_vault_notes.py -v
```

Expected: FAIL (no `groups` key in response)

- [ ] **Step 3: Implement enhanced list_skill_vault_notes_impl**

Replace `src/mcp/augur_mcp/core/skills.py` lines 505-565 with:

```python
async def list_skill_vault_notes_impl(
    skill_name: str,
    resolve_skill_entry: Callable,
) -> str:
    """List vault notes for a skill with directory grouping.

    Returns both the legacy flat ``notes`` array (backwards compatible)
    and new ``groups`` / ``stats`` fields for the enhanced VaultNotesBlock.
    """
    from collections import defaultdict
    from datetime import datetime, timezone

    from augur_mcp.config import get_skill_data_dir

    skill_entry = resolve_skill_entry(skill_name)
    if not skill_entry:
        return json.dumps({"notes": [], "groups": [], "stats": {"total_files": 0, "total_dirs": 0}})

    vault_dir = get_skill_data_dir(skill_entry.name)
    if not vault_dir.is_dir():
        return json.dumps({"notes": [], "groups": [], "stats": {"total_files": 0, "total_dirs": 0}})

    # Collect .md files up to 3 levels deep
    all_md: list[Path] = []
    for pattern in ("*.md", "*/*.md", "*/*/*.md", "*/*/*/*.md"):
        all_md.extend(vault_dir.glob(pattern))

    # Deduplicate and sort by modification time (newest first)
    seen: set[Path] = set()
    md_files: list[Path] = []
    for p in sorted(all_md, key=lambda p: p.stat().st_mtime, reverse=True):
        if p not in seen:
            seen.add(p)
            md_files.append(p)

    # Build flat notes list (backwards compatible) — limit 50
    notes: list[dict] = []
    # Build grouped structure
    groups_map: defaultdict[str, list[dict]] = defaultdict(list)

    for md_file in md_files[:50]:
        stat = md_file.stat()
        content = md_file.read_text(encoding="utf-8", errors="replace")
        line_count = content.count("\n") + 1

        # Parse frontmatter for type field
        file_type = ""
        body = content
        if content.startswith("---"):
            end = content.find("\n---", 4)
            if end != -1:
                yaml_block = content[4:end]
                body = content[end + 4:].lstrip("\n")
                try:
                    import yaml
                    meta = yaml.safe_load(yaml_block)
                    if isinstance(meta, dict):
                        file_type = str(meta.get("type", ""))
                except Exception:
                    pass

        preview = body[:500].strip() if body else ""
        rel_path = md_file.relative_to(vault_dir)
        rel_name = str(rel_path)

        # Determine directory group
        if len(rel_path.parts) == 1:
            group_dir = "."
        else:
            group_dir = str(rel_path.parent)

        file_entry = {
            "name": rel_name,
            "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "preview": preview,
            "type": file_type,
            "lines": line_count,
        }

        notes.append({
            "name": rel_name,
            "modified": file_entry["modified"],
            "preview": preview,
        })

        groups_map[group_dir].append(file_entry)

    # Convert groups map to sorted list
    groups = []
    for dir_name in sorted(groups_map.keys(), key=lambda d: (d != ".", d)):
        files = groups_map[dir_name]
        groups.append({
            "directory": dir_name,
            "count": len(files),
            "files": files,
        })

    unique_dirs = {str(p.relative_to(vault_dir).parent) for p in md_files[:50] if len(p.relative_to(vault_dir).parts) > 1}

    return json.dumps({
        "notes": notes,
        "groups": groups,
        "stats": {
            "total_files": len(md_files[:50]),
            "total_dirs": len(unique_dirs) + 1,  # +1 for root
        },
    })
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Projects/Augur && python -m pytest tests/packages/augur-mcp/core/test_skill_vault_notes.py -v
```

Expected: 6 PASS

- [ ] **Step 5: Run existing tests to check backwards compatibility**

```bash
cd ~/Projects/Augur && python -m pytest tests/ -k "vault" -v --timeout=30
```

Expected: All existing vault tests still pass (the `notes` array shape is preserved)

- [ ] **Step 6: Commit**

```bash
git add src/mcp/augur_mcp/core/skills.py tests/packages/augur-mcp/core/test_skill_vault_notes.py
git commit -m "feat(mcp): enhance list-skill-vault-notes with grouping, types, 50-file limit"
```

---

### Task 5: Enhance VaultNotesBlock component

**Files:**
- Modify: `apps/dashboard/components/blocks/types/VaultNotesBlock.tsx` (full rewrite)

- [ ] **Step 1: Rewrite VaultNotesBlock with directory grouping**

Replace the full content of `apps/dashboard/components/blocks/types/VaultNotesBlock.tsx`:

```typescript
"use client";

import { useState, useMemo, useCallback } from "react";
import {
  FileText, ChevronDown, ChevronRight, Loader2,
  FolderOpen, Folder, StickyNote, Lightbulb, Newspaper,
  Settings, BookOpen, Hash,
} from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { BlockShell } from "../BlockShell";
import { Input } from "@/components/ui/Input";
import { formatTimeAgo } from "@/lib/timestamps";
import { stripMdExtension, truncate } from "@/lib/utils/format";

interface VaultNotesConfig {
  title?: string;
  limit?: number;
  directory_filter?: string;
  collapsed?: boolean;
  sort?: "modified_desc" | "directory";
}

interface VaultNote {
  name: string;
  modified?: string;
  preview?: string;
  content?: string;
  type?: string;
  lines?: number;
}

interface VaultGroup {
  directory: string;
  count: number;
  files: VaultNote[];
}

interface VaultStats {
  total_files: number;
  total_dirs: number;
}

const TYPE_ICONS: Record<string, typeof FileText> = {
  note: StickyNote,
  idea: Lightbulb,
  post: Newspaper,
  config: Settings,
  doc: BookOpen,
  interview: Hash,
};

function getTypeIcon(type?: string) {
  if (!type) return FileText;
  return TYPE_ICONS[type] || FileText;
}

export default function VaultNotesBlock(props: BlockProps<VaultNotesConfig>) {
  const { config, dataSource, onExpand } = props;
  const {
    title = "Vault Notes",
    limit = 50,
    directory_filter,
    collapsed: startCollapsed = false,
    sort = "modified_desc",
  } = config;

  const selfFetched = useBlockData<Record<string, unknown>>(dataSource, config, "vault-notes");
  const rawData = (props.data as Record<string, unknown> | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;

  // Extract groups and stats from enhanced response, fall back to flat notes
  const { groups, stats, notes } = useMemo(() => {
    if (!rawData) return { groups: [] as VaultGroup[], stats: null, notes: [] as VaultNote[] };

    const raw = rawData as Record<string, unknown>;

    // Enhanced response has groups[]
    if (Array.isArray(raw.groups) && raw.groups.length > 0) {
      let grps = raw.groups as VaultGroup[];

      // Apply directory filter
      if (directory_filter) {
        const allowed = new Set(directory_filter.split(",").map((d) => d.trim()));
        grps = grps.filter((g) => allowed.has(g.directory) || allowed.has(g.directory.split("/")[0]));
      }

      return {
        groups: grps,
        stats: (raw.stats as VaultStats) || null,
        notes: (raw.notes as VaultNote[]) || [],
      };
    }

    // Legacy flat response — wrap in single group
    const flatNotes = Array.isArray(raw) ? (raw as VaultNote[]) : (raw.notes as VaultNote[]) || [];
    return {
      groups: flatNotes.length > 0 ? [{ directory: ".", count: flatNotes.length, files: flatNotes }] : [],
      stats: null,
      notes: flatNotes,
    };
  }, [rawData, directory_filter]);

  const [expandedNotes, setExpandedNotes] = useState<Set<string>>(new Set());
  const [collapsedDirs, setCollapsedDirs] = useState<Set<string>>(
    () => new Set(startCollapsed ? groups.map((g) => g.directory) : []),
  );
  const [searchText, setSearchText] = useState("");

  const filteredGroups = useMemo(() => {
    if (!searchText) return groups;
    const lower = searchText.toLowerCase();
    return groups
      .map((g) => ({
        ...g,
        files: g.files.filter(
          (f) =>
            f.name.toLowerCase().includes(lower) ||
            (f.preview ?? "").toLowerCase().includes(lower) ||
            (f.type ?? "").toLowerCase().includes(lower),
        ),
      }))
      .filter((g) => g.files.length > 0);
  }, [groups, searchText]);

  const totalFiles = stats?.total_files ?? notes.length;

  const toggleNote = useCallback((name: string) => {
    setExpandedNotes((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  }, []);

  const toggleDir = useCallback((dir: string) => {
    setCollapsedDirs((prev) => {
      const next = new Set(prev);
      next.has(dir) ? next.delete(dir) : next.add(dir);
      return next;
    });
  }, []);

  return (
    <BlockShell title={title} icon={FileText} color="purple" onExpand={onExpand} staleError={error}>
      <div className="p-3">
        {loading &&
          Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="h-12 mb-2 rounded-lg bg-[var(--bg-hover)] animate-pulse" />
          ))}

        {!loading && totalFiles === 0 && !error && (
          <p className="text-xs text-[var(--text-muted)] italic text-center py-4">No notes</p>
        )}

        {!loading && totalFiles > 3 && (
          <div className="mb-2">
            <Input
              type="text"
              placeholder="Search notes..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-1.5 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-primary)]"
            />
          </div>
        )}

        {!loading && filteredGroups.length > 0 && (
          <div className="flex flex-col gap-2">
            {filteredGroups.map((group) => {
              const isDirCollapsed = collapsedDirs.has(group.directory);
              const showDirHeader = group.directory !== "." || filteredGroups.length > 1;

              return (
                <div key={group.directory}>
                  {showDirHeader && (
                    <button
                      onClick={() => toggleDir(group.directory)}
                      className="flex w-full items-center gap-1.5 px-1 py-1 text-left hover:bg-[var(--bg-hover)]/40 rounded transition-colors"
                    >
                      {isDirCollapsed ? (
                        <Folder className="h-3.5 w-3.5 text-[var(--text-muted)]" />
                      ) : (
                        <FolderOpen className="h-3.5 w-3.5 text-[var(--accent-primary)]" />
                      )}
                      <span className="text-xs font-medium text-[var(--text-primary)]">
                        {group.directory === "." ? "Root" : group.directory}
                      </span>
                      <span className="text-[10px] text-[var(--text-muted)] ml-auto">
                        {group.count}
                      </span>
                    </button>
                  )}

                  {!isDirCollapsed && (
                    <div className="flex flex-col gap-1 mt-0.5">
                      {group.files.slice(0, limit).map((note) => {
                        const isExpanded = expandedNotes.has(note.name);
                        const Icon = getTypeIcon(note.type);

                        return (
                          <div key={note.name} className="rounded-lg bg-[var(--bg-hover)]/30 overflow-hidden">
                            <button
                              onClick={() => toggleNote(note.name)}
                              className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left hover:bg-[var(--bg-hover)]/60 transition-colors"
                              aria-expanded={isExpanded}
                            >
                              <div className="flex items-center gap-2 min-w-0">
                                {isExpanded ? (
                                  <ChevronDown className="h-3 w-3 text-[var(--text-muted)] flex-shrink-0" />
                                ) : (
                                  <ChevronRight className="h-3 w-3 text-[var(--text-muted)] flex-shrink-0" />
                                )}
                                <Icon className="h-3 w-3 text-[var(--text-muted)] flex-shrink-0" />
                                <span className="text-xs font-medium text-[var(--text-primary)] truncate">
                                  {stripMdExtension(note.name.split("/").pop() || note.name)}
                                </span>
                              </div>
                              <div className="flex items-center gap-2 flex-shrink-0">
                                {note.lines && (
                                  <span className="text-[10px] text-[var(--text-muted)]">
                                    {note.lines}L
                                  </span>
                                )}
                                {note.modified && (
                                  <span className="text-[10px] text-[var(--text-muted)]">
                                    {formatTimeAgo(note.modified)}
                                  </span>
                                )}
                              </div>
                            </button>

                            {!isExpanded && note.preview && (
                              <p className="px-3 pb-2 text-[10px] text-[var(--text-muted)] leading-relaxed">
                                {truncate(note.preview)}
                              </p>
                            )}

                            {isExpanded && (
                              <div className="border-t border-[var(--border-color)]/30 px-3 py-2">
                                {note.content ? (
                                  <div className="text-xs text-[var(--text-secondary)] leading-relaxed whitespace-pre-wrap">
                                    {note.content}
                                  </div>
                                ) : note.preview ? (
                                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed whitespace-pre-wrap">
                                    {note.preview}
                                  </p>
                                ) : (
                                  <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                                    <Loader2 className="h-3 w-3 animate-spin" />
                                    Loading...
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}

            {searchText && filteredGroups.length === 0 && (
              <p className="py-3 text-center text-xs text-[var(--text-muted)]">No notes match your search</p>
            )}
          </div>
        )}
      </div>
    </BlockShell>
  );
}
```

- [ ] **Step 2: Verify build passes**

```bash
cd ~/Projects/Augur && pnpm --filter dashboard build 2>&1 | tail -5
```

Expected: Build succeeds with no TypeScript errors

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/components/blocks/types/VaultNotesBlock.tsx
git commit -m "feat(ui): enhance VaultNotesBlock with directory grouping and type icons"
```

---

### Task 6: Create linkedin-writer YAML page

**Files:**
- Create: `skills/linkedin-writer/augur/pages/overview.yaml`

- [ ] **Step 1: Verify directory exists**

```bash
ls ~/Projects/Augur/skills/linkedin-writer/augur/pages/ 2>/dev/null || mkdir -p ~/Projects/Augur/skills/linkedin-writer/augur/pages/
```

- [ ] **Step 2: Create YAML page config**

```yaml
# skills/linkedin-writer/augur/pages/overview.yaml
title: LinkedIn Writer
icon: Linkedin
hub: career
route: linkedin-writer
order: 30
blocks:
  - type: vault-notes
    title: Posts
    mcp_tool: list-skill-vault-notes
    skill_id: linkedin-writer
    config:
      directory_filter: posts
      sort: modified_desc
      limit: 30

  - type: vault-notes
    title: Context & Assets
    mcp_tool: list-skill-vault-notes
    skill_id: linkedin-writer
    config:
      directory_filter: context,assets
      collapsed: true

  - type: action-bar
    mcp_tool: list-skill-actions
    skill_id: linkedin-writer
```

- [ ] **Step 3: Commit**

```bash
git add skills/linkedin-writer/augur/pages/overview.yaml
git commit -m "feat(linkedin-writer): add YAML dashboard page with post-focused layout"
```

---

### Task 7: Create lifestyle YAML page

**Files:**
- Create: `skills/lifestyle/augur/pages/overview.yaml`

- [ ] **Step 1: Verify directory exists**

```bash
ls ~/Projects/Augur/skills/lifestyle/augur/pages/ 2>/dev/null || mkdir -p ~/Projects/Augur/skills/lifestyle/augur/pages/
```

- [ ] **Step 2: Create YAML page config**

```yaml
# skills/lifestyle/augur/pages/overview.yaml
title: Lifestyle
icon: Heart
hub: life
route: lifestyle
order: 20
blocks:
  - type: vault-notes
    title: Ideas
    mcp_tool: list-skill-vault-notes
    skill_id: lifestyle
    config:
      directory_filter: ideas
      sort: modified_desc

  - type: vault-notes
    title: Recipes
    mcp_tool: list-skill-vault-notes
    skill_id: lifestyle
    config:
      directory_filter: recipe-manager

  - type: vault-notes
    title: Knowledge & Notes
    mcp_tool: list-skill-vault-notes
    skill_id: lifestyle
    config:
      directory_filter: knowledge,notes
      collapsed: true

  - type: action-bar
    mcp_tool: list-skill-actions
    skill_id: lifestyle
```

- [ ] **Step 3: Commit**

```bash
git add skills/lifestyle/augur/pages/overview.yaml
git commit -m "feat(lifestyle): add YAML dashboard page with idea/recipe/notes layout"
```

---

## Execution Notes

**Task dependencies:** Tasks 1-2 are independent. Task 3 depends on 1+2. Task 4 is independent. Task 5 depends on 4 (uses new response shape). Tasks 6-7 depend on 5 (use `directory_filter` config prop).

**Recommended order:** 1 → 2 → 3 → 4 → 5 → 6 → 7

**After Plan A is complete:** Write and execute Plan B for the 5 custom TSX pages (career pipeline, career profile, venture-augur content, growth dashboard, growth knowledge).

**Verification checklist:**
- [ ] `vault-file-read` returns full content with frontmatter for any vault file
- [ ] `vault-file-write` creates files with proper frontmatter via `write_frontmatter()`
- [ ] `list-skill-vault-notes` returns both `notes[]` (backwards compat) and `groups[]` (enhanced)
- [ ] VaultNotesBlock renders directory sections with collapsible folders and type icons
- [ ] LinkedIn-writer page shows posts prominently, context/assets collapsed
- [ ] Lifestyle page shows ideas, recipes, knowledge in separate sections
- [ ] All existing vault-related tests still pass
