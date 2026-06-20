import json
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_list_hub_recent_files_returns_sorted_files(tmp_path: Path):
    """Files are returned sorted by modification time, newest first."""
    from src.mcp.augur_core.tools.core.hub_recent import list_hub_recent_files_impl

    # Create mock vault with two skills
    career_dir = tmp_path / "career"
    career_dir.mkdir()
    coach_dir = tmp_path / "coach"
    coach_dir.mkdir()

    # Create files with different mtimes
    old_file = career_dir / "old-note.md"
    old_file.write_text("---\ntitle: Old\n---\nOld content here")
    import os

    os.utime(old_file, (1000000, 1000000))

    new_file = coach_dir / "new-note.md"
    new_file.write_text("---\ntitle: New\n---\nNew content here")
    os.utime(new_file, (2000000, 2000000))

    mid_file = career_dir / "mid-doc.md"
    mid_file.write_text("Mid content no frontmatter")
    os.utime(mid_file, (1500000, 1500000))

    result = json.loads(
        await list_hub_recent_files_impl(
            hub_id="career",
            skill_names=["career", "coach"],
            vault_dir=tmp_path,
            limit=10,
            per_skill_limit=2,
        )
    )

    assert result["success"] is True
    assert result["count"] == 3
    names = [f["name"] for f in result["files"]]
    assert names == ["new-note.md", "mid-doc.md", "old-note.md"]
    assert result["files"][0]["skill"] == "coach"
    assert result["files"][1]["skill"] == "career"


@pytest.mark.asyncio
async def test_per_skill_limit_caps_items(tmp_path: Path):
    """No more than per_skill_limit files from any single skill."""
    from src.mcp.augur_core.tools.core.hub_recent import list_hub_recent_files_impl

    import os

    skill_dir = tmp_path / "career"
    skill_dir.mkdir()
    for i in range(5):
        f = skill_dir / f"note-{i}.md"
        f.write_text(f"Content {i}")
        os.utime(f, (1000000 + i * 1000, 1000000 + i * 1000))

    result = json.loads(
        await list_hub_recent_files_impl(
            hub_id="career",
            skill_names=["career"],
            vault_dir=tmp_path,
            limit=10,
            per_skill_limit=2,
        )
    )

    assert result["count"] == 2
    # Should be the 2 newest
    assert result["files"][0]["name"] == "note-4.md"
    assert result["files"][1]["name"] == "note-3.md"


@pytest.mark.asyncio
async def test_empty_vault_returns_empty(tmp_path: Path):
    """Hub with no vault files returns empty list."""
    from src.mcp.augur_core.tools.core.hub_recent import list_hub_recent_files_impl

    result = json.loads(
        await list_hub_recent_files_impl(
            hub_id="career",
            skill_names=["nonexistent"],
            vault_dir=tmp_path,
            limit=10,
            per_skill_limit=2,
        )
    )

    assert result["success"] is True
    assert result["count"] == 0
    assert result["files"] == []


@pytest.mark.asyncio
async def test_file_type_classification(tmp_path: Path):
    """Markdown files are 'note', other files are 'doc'."""
    from src.mcp.augur_core.tools.core.hub_recent import list_hub_recent_files_impl

    skill_dir = tmp_path / "career"
    skill_dir.mkdir()
    (skill_dir / "my-note.md").write_text("# Note")
    (skill_dir / "report.pdf").write_text("fake pdf")
    (skill_dir / "data.csv").write_text("a,b,c")

    result = json.loads(
        await list_hub_recent_files_impl(
            hub_id="career",
            skill_names=["career"],
            vault_dir=tmp_path,
            limit=10,
            per_skill_limit=5,
        )
    )

    types_by_name = {f["name"]: f["type"] for f in result["files"]}
    assert types_by_name["my-note.md"] == "note"
    assert types_by_name["report.pdf"] == "doc"
    assert types_by_name["data.csv"] == "doc"


@pytest.mark.asyncio
async def test_preview_strips_frontmatter(tmp_path: Path):
    """Preview text should not include YAML frontmatter."""
    from src.mcp.augur_core.tools.core.hub_recent import list_hub_recent_files_impl

    skill_dir = tmp_path / "career"
    skill_dir.mkdir()
    (skill_dir / "note.md").write_text("---\ntitle: Test\n---\nActual body content here")

    result = json.loads(
        await list_hub_recent_files_impl(
            hub_id="career",
            skill_names=["career"],
            vault_dir=tmp_path,
            limit=10,
            per_skill_limit=2,
        )
    )

    assert result["files"][0]["preview"] == "Actual body content here"


@pytest.mark.asyncio
async def test_recent_files_uses_obsidian_first_skill_root(tmp_path: Path):
    """Migrated skill data is read from its domain-first vault location."""
    from src.mcp.augur_core.tools.core.hub_recent import list_hub_recent_files_impl

    skill_dir = tmp_path / "career" / "data"
    skill_dir.mkdir(parents=True)
    (skill_dir / "applications.md").write_text("---\ntitle: Applications\n---\nPipeline")

    result = json.loads(
        await list_hub_recent_files_impl(
            hub_id="career",
            skill_names=["career-ops"],
            vault_dir=tmp_path,
            limit=10,
            per_skill_limit=2,
        )
    )

    assert result["count"] == 1
    assert result["files"][0]["path"] == "career/data/applications.md"
    assert result["files"][0]["skill"] == "career-ops"
