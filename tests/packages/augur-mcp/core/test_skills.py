"""Tests for canonical core skill MCP tools."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest


@pytest.mark.anyio
async def test_reindex_browse_category_allows_wiki(monkeypatch, tmp_path):
    from src.mcp.augur_core.tools.core.skills import reindex_browse_category_impl

    root = tmp_path
    script = root / "src" / "lib" / "index" / "unified_indexer.py"
    script.parent.mkdir(parents=True)
    script.write_text("# placeholder", encoding="utf-8")

    class _Proc:
        returncode = 0
        stdout = "Indexed 2 wiki entries\n"
        stderr = ""

    def fake_run(*_args, **_kwargs):
        return _Proc()

    monkeypatch.setattr("src.mcp.augur_shared.config.get_project_root", lambda: root)
    monkeypatch.setattr("subprocess.run", fake_run)

    result = json.loads(await reindex_browse_category_impl("wiki"))

    assert result["success"] is True
    assert result["category"] == "wiki"
    assert result["count"] == 2


@pytest.mark.anyio
async def test_reindex_browse_category_allows_mcp_servers(monkeypatch, tmp_path):
    from src.mcp.augur_core.tools.core.skills import reindex_browse_category_impl

    root = tmp_path
    script = root / "src" / "lib" / "index" / "unified_indexer.py"
    script.parent.mkdir(parents=True)
    script.write_text("# placeholder", encoding="utf-8")

    class _Proc:
        returncode = 0
        stdout = "Indexed 7 mcp-servers entries\n"
        stderr = ""

    def fake_run(*_args, **_kwargs):
        return _Proc()

    monkeypatch.setattr("src.mcp.augur_shared.config.get_project_root", lambda: root)
    monkeypatch.setattr("subprocess.run", fake_run)

    result = json.loads(await reindex_browse_category_impl("mcp-servers"))

    assert result["success"] is True
    assert result["category"] == "mcp-servers"
    assert result["count"] == 7


@pytest.mark.anyio
async def test_update_skill_doc_preserves_frontmatter(monkeypatch, tmp_path):
    from src.mcp.augur_core.tools.core.skills import update_skill_doc_impl

    skill_dir = tmp_path / "skills" / "adr"
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\n" "name: adr\n" "x-augur-hub: command\n" "---\n" "\n" "# Old Body\n",
        encoding="utf-8",
    )

    def resolve_skill_entry(skill_name: str):
        assert skill_name == "adr"
        return SimpleNamespace(path=skill_dir)

    result = json.loads(
        await update_skill_doc_impl(
            "adr",
            "# New Body\n\nUpdated from the dashboard.",
            resolve_skill_entry,
        )
    )

    assert result["success"] is True
    assert result["path"] == str(skill_md)
    written = skill_md.read_text(encoding="utf-8")
    assert "name: adr" in written
    assert "x-augur-hub: command" in written
    assert "# Old Body" not in written
    assert "# New Body" in written


@pytest.mark.anyio
async def test_get_skill_doc_marks_generated_exports_read_only(tmp_path):
    from src.mcp.augur_core.tools.core.skills import get_skill_doc_impl

    skill_dir = tmp_path / ".codex" / "skills" / "adr"
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\n"
        "name: adr\n"
        "---\n"
        "<!--\n"
        "AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY\n"
        "Source: skills/augur-core/commands/adr.md\n"
        "-->\n"
        "\n"
        "# ADR Command\n",
        encoding="utf-8",
    )

    def resolve_skill_entry(skill_name: str):
        assert skill_name == "adr"
        return SimpleNamespace(path=skill_dir)

    result = json.loads(await get_skill_doc_impl("adr", resolve_skill_entry))

    assert result["content"] == "# ADR Command"
    assert result["editable"] is False
    assert result["generated"] is True
    assert result["path"] == str(skill_md)


@pytest.mark.anyio
async def test_update_skill_doc_refuses_generated_exports(tmp_path):
    from src.mcp.augur_core.tools.core.skills import update_skill_doc_impl

    skill_dir = tmp_path / ".gemini" / "skills" / "adr"
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    original = (
        "---\n"
        "name: adr\n"
        "---\n"
        "<!--\n"
        "AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY\n"
        "Source: skills/augur-core/commands/adr.md\n"
        "-->\n"
        "\n"
        "# ADR Command\n"
    )
    skill_md.write_text(original, encoding="utf-8")

    def resolve_skill_entry(skill_name: str):
        assert skill_name == "adr"
        return SimpleNamespace(path=skill_dir)

    result = json.loads(await update_skill_doc_impl("adr", "# Edited", resolve_skill_entry))

    assert result["success"] is False
    assert result["generated"] is True
    assert "Generated skill documentation" in result["error"]
    assert skill_md.read_text(encoding="utf-8") == original
    assert not skill_md.with_suffix(".md.bak").exists()
