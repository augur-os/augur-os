from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.index.document_attachments import DocumentAttachmentConfigError
from src.lib.index.document_catalog_writer import upsert_document_catalog_summary
from src.lib.index.document_source_config_writer import (
    attach_project_document_source,
    list_project_document_source_records,
    update_project_document_source_summary,
)


def _sources_yaml(project_root: Path) -> Path:
    return project_root / "config" / "documents" / "sources.yaml"


def test_attach_project_document_source_creates_git_tracked_config(tmp_path):
    project_root = tmp_path / "project"

    record = attach_project_document_source(
        project_root=project_root,
        project_brain_id="project-y",
        source_id="project-y-drive",
        name="Project Y Drive",
        provider="google-drive",
        remote_id="folders/abc123",
        attached_brain_ids=["project-y"],
        catalog_summary="Design references and delivery material for Project Y.",
        summary_status="human",
    )

    payload = yaml.safe_load(_sources_yaml(project_root).read_text(encoding="utf-8"))
    assert record["id"] == "project-y-drive"
    assert payload == {
        "sources": [
            {
                "id": "project-y-drive",
                "name": "Project Y Drive",
                "provider": "google-drive",
                "remote_id": "folders/abc123",
                "attached_brain_ids": ["project-y"],
                "catalog_summary": "Design references and delivery material for Project Y.",
                "summary_status": "human",
            }
        ]
    }


def test_attach_project_document_source_rejects_local_paths(tmp_path):
    with pytest.raises(DocumentAttachmentConfigError, match="must not store local paths"):
        attach_project_document_source(
            project_root=tmp_path / "project",
            project_brain_id="project-y",
            source_id="local-project",
            name="Local Project",
            provider="google-drive",
            remote_id="folders/abc123",
            path="/Users/example/Downloads",
        )


def test_attach_project_document_source_rejects_filesystem_provider(tmp_path):
    with pytest.raises(DocumentAttachmentConfigError, match="must use a shared provider"):
        attach_project_document_source(
            project_root=tmp_path / "project",
            project_brain_id="project-y",
            source_id="local-project",
            name="Local Project",
            provider="filesystem",
            remote_id="folders/abc123",
        )


def test_attach_project_document_source_replaces_only_when_requested(tmp_path):
    project_root = tmp_path / "project"
    attach_project_document_source(
        project_root=project_root,
        project_brain_id="project-y",
        source_id="project-y-drive",
        name="Project Y Drive",
        provider="google-drive",
        remote_id="folders/abc123",
    )

    with pytest.raises(DocumentAttachmentConfigError, match="already exists"):
        attach_project_document_source(
            project_root=project_root,
            project_brain_id="project-y",
            source_id="project-y-drive",
            name="Project Y Drive Updated",
            provider="google-drive",
            remote_id="folders/def456",
        )

    attach_project_document_source(
        project_root=project_root,
        project_brain_id="project-y",
        source_id="project-y-drive",
        name="Project Y Drive Updated",
        provider="google-drive",
        remote_id="folders/def456",
        replace=True,
    )

    records = list_project_document_source_records(project_root)
    assert len(records) == 1
    assert records[0]["name"] == "Project Y Drive Updated"
    assert records[0]["remote_id"] == "folders/def456"


def test_update_project_document_source_summary_changes_only_summary_fields(tmp_path):
    project_root = tmp_path / "project"
    attach_project_document_source(
        project_root=project_root,
        project_brain_id="project-y",
        source_id="project-y-drive",
        name="Project Y Drive",
        provider="google-drive",
        remote_id="folders/abc123",
        remote_revision="drive-revision-42",
    )

    record = update_project_document_source_summary(
        project_root=project_root,
        source_id="project-y-drive",
        catalog_title="Project Y References",
        catalog_summary="Two to four lines of human-approved project context.",
        summary_status="human",
        summary_generated_from_revision="drive-revision-42",
    )

    assert record["remote_id"] == "folders/abc123"
    assert record["catalog_title"] == "Project Y References"
    assert record["catalog_summary"] == "Two to four lines of human-approved project context."
    assert record["summary_status"] == "human"


def test_upsert_document_catalog_summary_writes_frontmatter_and_body(tmp_path):
    project_root = tmp_path / "project"

    path = upsert_document_catalog_summary(
        project_root=project_root,
        source_id="project-y-drive",
        title="Investor Deck",
        summary="Explains the Project Y market, architecture, and delivery plan.",
        remote_id="google-drive:file:deck",
        source_relative_path="deck.md",
        provider="google-drive",
        attached_brain_ids=["project-y"],
        summary_status="human",
        summary_generated_from_revision="drive-revision-42",
        remote_revision="drive-revision-42",
    )

    metadata, body = parse_frontmatter(path)
    assert path == (project_root / "project-brain" / "knowledge" / "documents" / "project-y-drive" / "investor-deck.md")
    assert metadata["remote_id"] == "google-drive:file:deck"
    assert metadata["source_id"] == "project-y-drive"
    assert metadata["attached_brain_ids"] == ["project-y"]
    assert metadata["summary_status"] == "human"
    assert body == "Explains the Project Y market, architecture, and delivery plan.\n"


def test_upsert_document_catalog_summary_rejects_personal_filesystem_sources(tmp_path):
    with pytest.raises(DocumentAttachmentConfigError, match="shared provider"):
        upsert_document_catalog_summary(
            project_root=tmp_path / "project",
            source_id="downloads",
            title="Tax Form",
            summary="Personal tax form from Downloads.",
            remote_id="filesystem:/Users/example/Downloads/tax.pdf",
            provider="filesystem",
            attached_brain_ids=["personal"],
        )


def test_upsert_document_catalog_summary_requires_lookup_identity(tmp_path):
    with pytest.raises(DocumentAttachmentConfigError, match="at least one lookup identity"):
        upsert_document_catalog_summary(
            project_root=tmp_path / "project",
            source_id="project-y-drive",
            title="No Identity",
            summary="This entry cannot be matched to a document.",
        )
