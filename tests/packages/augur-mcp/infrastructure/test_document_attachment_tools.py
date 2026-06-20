from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from src.lib.frontmatter_utils import parse_frontmatter
from src.mcp.augur_framework.tools.infrastructure.browse import register_browse_tools
from src.mcp.augur_framework.tools.infrastructure.browse.document_sources import (
    attach_project_document_source_impl,
    list_project_document_sources_impl,
    update_project_document_source_summary_impl,
    upsert_document_catalog_summary_impl,
)


@pytest.mark.asyncio
async def test_attach_project_document_source_impl_writes_sources_yaml(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse.document_sources.get_project_root",
        lambda: project_root,
    )
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse.document_sources.read_project_brain_id",
        lambda _root: "project-y",
    )

    result = json.loads(
        await attach_project_document_source_impl(
            source_id="project-y-drive",
            name="Project Y Drive",
            provider="google-drive",
            remote_id="folders/abc123",
            attached_brain_ids=["project-y"],
            catalog_summary="Shared project references.",
        )
    )

    assert result["success"] is True
    assert result["record"]["id"] == "project-y-drive"
    payload = yaml.safe_load((project_root / "config" / "documents" / "sources.yaml").read_text(encoding="utf-8"))
    assert payload["sources"][0]["catalog_summary"] == "Shared project references."


@pytest.mark.asyncio
async def test_list_project_document_sources_impl_returns_configured_records(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    config = project_root / "config" / "documents" / "sources.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "sources:\n"
        "  - id: project-y-drive\n"
        "    name: Project Y Drive\n"
        "    provider: google-drive\n"
        "    remote_id: folders/abc123\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse.document_sources.get_project_root",
        lambda: project_root,
    )

    result = json.loads(await list_project_document_sources_impl())

    assert result["success"] is True
    assert result["sources"][0]["id"] == "project-y-drive"


@pytest.mark.asyncio
async def test_update_project_document_source_summary_impl_writes_summary(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    config = project_root / "config" / "documents" / "sources.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "sources:\n"
        "  - id: project-y-drive\n"
        "    name: Project Y Drive\n"
        "    provider: google-drive\n"
        "    remote_id: folders/abc123\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse.document_sources.get_project_root",
        lambda: project_root,
    )

    result = json.loads(
        await update_project_document_source_summary_impl(
            source_id="project-y-drive",
            catalog_title="Project Y References",
            catalog_summary="Human-approved source summary.",
            summary_status="human",
            summary_generated_from_revision="drive-revision-42",
        )
    )

    assert result["success"] is True
    assert result["record"]["catalog_summary"] == "Human-approved source summary."


@pytest.mark.asyncio
async def test_upsert_document_catalog_summary_impl_writes_catalog_entry(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse.document_sources.get_project_root",
        lambda: project_root,
    )

    result = json.loads(
        await upsert_document_catalog_summary_impl(
            source_id="project-y-drive",
            title="Investor Deck",
            summary="Human-approved deck summary.",
            remote_id="google-drive:file:deck",
            source_relative_path="deck.md",
            provider="google-drive",
            attached_brain_ids=["project-y"],
        )
    )

    assert result["success"] is True
    path = Path(result["path"])
    metadata, body = parse_frontmatter(path)
    assert metadata["remote_id"] == "google-drive:file:deck"
    assert body == "Human-approved deck summary.\n"


@pytest.mark.asyncio
async def test_upsert_document_catalog_summary_impl_rejects_personal_filesystem_source(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse.document_sources.get_project_root",
        lambda: project_root,
    )

    result = json.loads(
        await upsert_document_catalog_summary_impl(
            source_id="downloads",
            title="Tax Form",
            summary="Personal tax form from Downloads.",
            remote_id="filesystem:/Users/example/Downloads/tax.pdf",
            provider="filesystem",
            attached_brain_ids=["personal"],
        )
    )

    assert result["success"] is False
    assert "shared provider" in result["error"]


def test_register_browse_tools_exposes_document_attachment_tools():
    class FakeMcp:
        def __init__(self) -> None:
            self.names: list[str] = []

        def tool(self, *, name: str, annotations):
            self.names.append(name)

            def decorator(func):
                return func

            return decorator

    fake = FakeMcp()

    register_browse_tools(fake)

    assert "attach-project-document-source" in fake.names
    assert "list-project-document-sources" in fake.names
    assert "update-project-document-source-summary" in fake.names
    assert "upsert-document-catalog-summary" in fake.names
