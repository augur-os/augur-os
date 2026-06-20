import json
import os
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_list_hub_vault_notes_aggregates_and_sorts_notes(tmp_path: Path):
    """Hub notes combine multiple skills and keep newest notes first."""
    from src.mcp.augur_core.tools.core.hub_vault_notes import list_hub_vault_notes_impl

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    older_note = knowledge_dir / "idea.md"
    older_note.write_text("---\ntitle: Idea\n---\nOlder insight")
    os.utime(older_note, (1_000_000, 1_000_000))

    search_dir = tmp_path / "search"
    nested_dir = search_dir / "notes"
    nested_dir.mkdir(parents=True)
    newer_note = nested_dir / "fresh.md"
    newer_note.write_text("---\ntitle: Fresh\n---\nNewest insight")
    os.utime(newer_note, (2_000_000, 2_000_000))

    result = json.loads(
        await list_hub_vault_notes_impl(
            hub_id="brain",
            skill_names=["knowledge", "search"],
            vault_dir=tmp_path,
            limit=10,
            per_skill_limit=2,
        )
    )

    assert result["success"] is True
    assert result["count"] == 2
    assert [note["name"] for note in result["notes"]] == ["notes/fresh.md", "idea.md"]
    assert [note["skill"] for note in result["notes"]] == ["search", "knowledge"]
    assert result["notes"][0]["preview"] == "Newest insight"


@pytest.mark.asyncio
async def test_list_hub_vault_notes_returns_empty_for_missing_skills(tmp_path: Path):
    """Missing skill vaults should return an empty notes payload."""
    from src.mcp.augur_core.tools.core.hub_vault_notes import list_hub_vault_notes_impl

    result = json.loads(
        await list_hub_vault_notes_impl(
            hub_id="brain",
            skill_names=["knowledge"],
            vault_dir=tmp_path,
            limit=10,
            per_skill_limit=2,
        )
    )

    assert result["success"] is True
    assert result["hub_id"] == "brain"
    assert result["notes"] == []
    assert result["count"] == 0


@pytest.mark.asyncio
async def test_list_hub_vault_notes_uses_obsidian_first_skill_root(tmp_path: Path):
    """Migrated skill data is read from its domain-first vault location."""
    from src.mcp.augur_core.tools.core.hub_vault_notes import list_hub_vault_notes_impl

    career_dir = tmp_path / "career"
    career_dir.mkdir(parents=True)
    (career_dir / "cv.md").write_text("---\ntitle: CV\n---\nCareer summary")

    result = json.loads(
        await list_hub_vault_notes_impl(
            hub_id="career",
            skill_names=["career-ops"],
            vault_dir=tmp_path,
            limit=10,
            per_skill_limit=2,
        )
    )

    assert result["success"] is True
    assert result["count"] == 1
    assert result["notes"][0]["name"] == "cv.md"
    assert result["notes"][0]["skill"] == "career-ops"
