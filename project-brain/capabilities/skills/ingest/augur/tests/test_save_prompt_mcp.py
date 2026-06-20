"""Behavioral tests for the save-prompt atomic op."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.lib.ingest import note_index_refresh
from skills.ingest.scripts.mcp import url_tools
from skills.ingest.scripts.mcp.url_tools import save_prompt_impl
from src.lib.frontmatter_utils import parse_frontmatter


def _write_project_registry(tmp_path: Path) -> tuple[Path, Path, Path]:
    from src.lib.brain_manifest import (
        BrainManifest,
        ensure_brain_skeleton,
        write_brain_manifest,
    )
    from src.lib.brain_registry_io import save_registry
    from src.lib.brain_registry_models import (
        Brain,
        BrainRegistry,
        BrainType,
        GitArrangement,
        GitConfig,
    )

    personal = tmp_path / "personal"
    project = tmp_path / "repo"
    brain_root = project / "project-brain"
    ensure_brain_skeleton(brain_root)
    write_brain_manifest(
        brain_root,
        BrainManifest(
            schema_version=1,
            id="project-repo",
            type=BrainType.PROJECT,
            root=str(brain_root),
            attached_project=str(project),
        ),
    )
    registry_path = tmp_path / "brains.yaml"
    save_registry(
        BrainRegistry(
            version=1,
            brains={
                "personal": Brain(
                    id="personal",
                    type=BrainType.PERSONAL,
                    data_root=personal,
                    git=GitConfig(arrangement=GitArrangement.UNTRACKED),
                )
            },
        ),
        registry_path,
    )
    return registry_path, project, brain_root


@pytest.mark.asyncio
async def test_save_prompt_writes_card_and_returns_path(tmp_path):
    raw = await save_prompt_impl(
        label="Define a Goal",
        description="Define then act on a goal",
        body="State your {{goal}} clearly.",
        source_url="https://example.com/goal-prompt",
        vault_dir=tmp_path,
    )
    result = json.loads(raw)
    assert result["success"] is True
    assert result["deduplicated"] is False
    path = Path(result["path"])
    assert path.parent == tmp_path / "knowledge" / "notes"
    card = parse_frontmatter(path)[0]
    assert card["id"] == "define-a-goal"
    assert card["placeholders"] == ["goal"]
    assert card["source"] == "vault"
    assert card["x-augur-note-type"] == "prompt"
    assert card["x-augur-prompt-triggerable"] is True
    assert card.get("source_url") == "https://example.com/goal-prompt"


@pytest.mark.asyncio
async def test_save_prompt_routes_to_project_brain_from_cwd(monkeypatch, tmp_path):
    registry_path, project, brain_root = _write_project_registry(tmp_path)
    monkeypatch.setattr(
        url_tools,
        "refresh_notes_browse_index",
        lambda *, vault_dir: note_index_refresh.NoteBrowseIndexRefresh(
            success=True,
            count=1,
        ),
    )

    result = json.loads(
        await url_tools.save_prompt_impl(
            label="Project Prompt",
            description="Project scoped",
            body="Keep {{decision}} near project context.",
            cwd=project / "src",
            registry_path=registry_path,
        )
    )

    assert result["success"] is True
    assert result["brain"] == {
        "id": "project-repo",
        "type": "project",
        "reason": "active-project",
        "mode": "direct",
    }
    assert Path(result["path"]).parent == brain_root / "knowledge" / "notes"


@pytest.mark.asyncio
async def test_save_prompt_refreshes_browse_index_for_new_card(monkeypatch, tmp_path):
    calls: list[Path] = []

    def fake_refresh(*, paths=None, categories=None, vault_dir=None, documents_dir=None):
        calls.append(vault_dir)
        return {
            "vault": note_index_refresh.NoteBrowseIndexRefresh(success=True, count=5),
            "prompts": note_index_refresh.NoteBrowseIndexRefresh(success=True, count=3),
        }

    monkeypatch.setattr(url_tools, "refresh_browse_after_write", fake_refresh)

    result = json.loads(await url_tools.save_prompt_impl(
        label="Define a Goal",
        description="Define then act on a goal",
        body="State your {{goal}} clearly.",
        source_url="https://example.com/goal-prompt",
        vault_dir=tmp_path,
    ))

    assert result["success"] is True
    assert result["deduplicated"] is False
    assert result["browse_index"] == {
        "vault": {"success": True, "count": 5},
        "prompts": {"success": True, "count": 3},
    }
    assert calls == [tmp_path]


@pytest.mark.asyncio
async def test_save_prompt_deduped_card_does_not_claim_new_browse_refresh(
    monkeypatch, tmp_path
):
    calls: list[Path] = []

    def fake_refresh(*, paths=None, categories=None, vault_dir=None, documents_dir=None):
        calls.append(vault_dir)
        return {
            "vault": note_index_refresh.NoteBrowseIndexRefresh(success=True, count=5),
            "prompts": note_index_refresh.NoteBrowseIndexRefresh(success=True, count=3),
        }

    monkeypatch.setattr(url_tools, "refresh_browse_after_write", fake_refresh)

    first = json.loads(await url_tools.save_prompt_impl(
        label="Reusable",
        description="d",
        body="reuse {{x}}",
        vault_dir=tmp_path,
    ))
    second = json.loads(await url_tools.save_prompt_impl(
        label="Reusable Again",
        description="d2",
        body="reuse {{x}}",
        vault_dir=tmp_path,
    ))

    assert first["deduplicated"] is False
    assert first["browse_index"] == {
        "vault": {"success": True, "count": 5},
        "prompts": {"success": True, "count": 3},
    }
    assert second["deduplicated"] is True
    assert "browse_index" not in second
    assert calls == [tmp_path]


@pytest.mark.asyncio
async def test_save_prompt_dedupes_by_content_hash(tmp_path):
    first = json.loads(await save_prompt_impl(
        label="Reusable", description="d", body="reuse {{x}}", vault_dir=tmp_path,
    ))
    second = json.loads(await save_prompt_impl(
        label="Reusable Again", description="d2", body="reuse {{x}}", vault_dir=tmp_path,
    ))
    assert second["deduplicated"] is True
    assert second["path"] == first["path"]
    # Dedupe response reflects the *stored* card's label, not the new caller's.
    assert second["label"] == "Reusable"


@pytest.mark.asyncio
async def test_save_prompt_requires_label_and_body(tmp_path):
    no_label = json.loads(await save_prompt_impl(
        label="", description="d", body="x", vault_dir=tmp_path))
    no_body = json.loads(await save_prompt_impl(
        label="L", description="d", body="", vault_dir=tmp_path))
    assert no_label["success"] is False and "label" in no_label["error"]
    assert no_body["success"] is False and "body" in no_body["error"]
