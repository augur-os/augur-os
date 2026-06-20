from __future__ import annotations

from pathlib import Path

import pytest

from src.lib.index.document_attachments import (
    DocumentAttachmentConfigError,
    DocumentAttachmentMetadata,
    attachment_metadata_for_local_personal_document,
    document_source_from_shared_config,
    document_sync_status,
    normalize_attached_brain_ids,
)


def test_normalize_attached_brain_ids_dedupes_and_rejects_empty_values():
    assert normalize_attached_brain_ids([" personal ", "project-y", "personal"]) == (
        "personal",
        "project-y",
    )
    assert normalize_attached_brain_ids("personal,project-y") == (
        "personal",
        "project-y",
    )
    assert normalize_attached_brain_ids([]) == ()
    assert normalize_attached_brain_ids([" ", None, "project-y"]) == ("project-y",)


def test_local_personal_document_metadata_marks_desktop_personal(tmp_path):
    source_path = tmp_path / "Desktop"
    document_path = source_path / "proposal.pdf"
    metadata = attachment_metadata_for_local_personal_document(
        source_id="desktop",
        document_path=document_path,
    )

    assert metadata.canonical_document_id == f"filesystem:{document_path.resolve(strict=False)}"
    assert metadata.source_id == "desktop"
    assert metadata.source_type == "local"
    assert metadata.provider == "filesystem"
    assert metadata.attached_brain_ids == ("personal",)
    assert metadata.index_status == "synced"


def test_local_personal_document_metadata_uses_document_path_identity(tmp_path):
    source_path = tmp_path / "Desktop"
    first = attachment_metadata_for_local_personal_document(
        source_id="desktop",
        document_path=source_path / "first.pdf",
    )
    second = attachment_metadata_for_local_personal_document(
        source_id="desktop",
        document_path=source_path / "second.pdf",
    )

    assert first.canonical_document_id == f"filesystem:{(source_path / 'first.pdf').resolve(strict=False)}"
    assert second.canonical_document_id == f"filesystem:{(source_path / 'second.pdf').resolve(strict=False)}"
    assert first.canonical_document_id != second.canonical_document_id


def test_project_shared_source_rejects_filesystem_provider(tmp_path):
    with pytest.raises(DocumentAttachmentConfigError) as exc:
        document_source_from_shared_config(
            {
                "id": "project-y-downloads",
                "provider": "filesystem",
                "path": str(tmp_path / "Downloads"),
                "attached_brain_ids": ["project-y"],
            },
            project_brain_id="project-y",
        )

    assert "Project document sources must use a shared provider" in str(exc.value)


def test_project_shared_source_rejects_local_path_field():
    with pytest.raises(DocumentAttachmentConfigError) as exc:
        document_source_from_shared_config(
            {
                "id": "project-y-drive",
                "provider": "google-drive",
                "remote_id": "folder:abc123",
                "path": "/Users/someone/private",
                "attached_brain_ids": ["project-y"],
            },
            project_brain_id="project-y",
            local_cache_path=Path("/tmp/project-y-drive-cache"),
        )

    assert "Project document sources must not store local paths" in str(exc.value)


@pytest.mark.parametrize(
    "source_id",
    ["project-y-drive", "downloads", "documents", "desktop"],
)
def test_project_shared_source_accepts_safe_source_ids(source_id):
    source = document_source_from_shared_config(
        {
            "id": source_id,
            "provider": "google-drive",
            "remote_id": "folder:abc123",
            "attached_brain_ids": ["project-y"],
        },
        project_brain_id="project-y",
        local_cache_path=Path("/tmp/project-y-drive-cache"),
    )

    assert source.id == source_id


@pytest.mark.parametrize(
    "source_id",
    ["../escape", "project/y", r"project\y", "project.y", "-starts-with-dash"],
)
def test_project_shared_source_rejects_unsafe_source_ids(source_id):
    with pytest.raises(DocumentAttachmentConfigError) as exc:
        document_source_from_shared_config(
            {
                "id": source_id,
                "provider": "google-drive",
                "remote_id": "folder:abc123",
                "attached_brain_ids": ["project-y"],
            },
            project_brain_id="project-y",
            local_cache_path=Path("/tmp/project-y-drive-cache"),
        )

    assert "Document source field 'id' must be a safe slug" in str(exc.value)


def test_project_shared_source_accepts_google_drive_metadata():
    source = document_source_from_shared_config(
        {
            "id": "project-y-drive",
            "provider": "google-drive",
            "remote_id": "folder:abc123",
            "attached_brain_ids": ["project-y"],
            "remote_revision": "drive-revision-42",
            "remote_modified_at": "2026-06-07T08:00:00Z",
        },
        project_brain_id="project-y",
        local_cache_path=Path("/tmp/project-y-drive-cache"),
    )

    assert source.id == "project-y-drive"
    assert source.provider == "google-drive"
    assert source.source_type == "shared"
    assert source.source_remote_id == "folder:abc123"
    assert not hasattr(source, "remote_id")
    assert source.attached_brain_ids == ("project-y",)
    assert source.remote_revision == "drive-revision-42"


def test_project_shared_source_trims_optional_name():
    source = document_source_from_shared_config(
        {
            "id": "project-y-drive",
            "name": " Project Y Drive ",
            "provider": "google-drive",
            "remote_id": "folder:abc123",
            "attached_brain_ids": ["project-y"],
        },
        project_brain_id="project-y",
        local_cache_path=Path("/tmp/project-y-drive-cache"),
    )

    assert source.name == "Project Y Drive"


@pytest.mark.parametrize("name", ["", "  ", None, 123])
def test_project_shared_source_rejects_malformed_optional_name(name):
    with pytest.raises(DocumentAttachmentConfigError) as exc:
        document_source_from_shared_config(
            {
                "id": "project-y-drive",
                "name": name,
                "provider": "google-drive",
                "remote_id": "folder:abc123",
                "attached_brain_ids": ["project-y"],
            },
            project_brain_id="project-y",
            local_cache_path=Path("/tmp/project-y-drive-cache"),
        )

    assert "Document source field 'name' must be a nonblank string" in str(exc.value)


@pytest.mark.parametrize(
    "attached_brain_ids",
    [
        pytest.param("personal,team-core", id="comma-string"),
        pytest.param(("personal", "team-core"), id="tuple"),
    ],
)
def test_project_shared_source_prepends_project_brain_when_missing(attached_brain_ids):
    source = document_source_from_shared_config(
        {
            "id": "project-y-drive",
            "provider": "google-drive",
            "remote_id": "folder:abc123",
            "attached_brain_ids": attached_brain_ids,
        },
        project_brain_id="project-y",
        local_cache_path=Path("/tmp/project-y-drive-cache"),
    )

    assert source.attached_brain_ids == ("project-y", "personal", "team-core")


@pytest.mark.parametrize(
    "config_override",
    [
        pytest.param({}, id="absent"),
        pytest.param({"attached_brain_ids": None}, id="none"),
        pytest.param({"attached_brain_ids": []}, id="empty-list"),
    ],
)
def test_project_shared_source_defaults_attached_brain_ids_to_project(config_override):
    source = document_source_from_shared_config(
        {
            "id": "project-y-drive",
            "provider": "google-drive",
            "remote_id": "folder:abc123",
            **config_override,
        },
        project_brain_id="project-y",
        local_cache_path=Path("/tmp/project-y-drive-cache"),
    )

    assert source.attached_brain_ids == ("project-y",)


@pytest.mark.parametrize(
    "attached_brain_ids",
    [
        {"brain": "project-y"},
        "",
        " , ",
        ["project-y", None],
        ["project-y", ""],
        ("project-y", 123),
    ],
)
def test_project_shared_source_rejects_malformed_attached_brain_ids(
    attached_brain_ids,
):
    with pytest.raises(DocumentAttachmentConfigError) as exc:
        document_source_from_shared_config(
            {
                "id": "project-y-drive",
                "provider": "google-drive",
                "remote_id": "folder:abc123",
                "attached_brain_ids": attached_brain_ids,
            },
            project_brain_id="project-y",
            local_cache_path=Path("/tmp/project-y-drive-cache"),
        )

    assert "attached_brain_ids must be a string or list of strings" in str(exc.value)


def test_project_shared_source_requires_explicit_local_cache_path():
    with pytest.raises(DocumentAttachmentConfigError) as exc:
        document_source_from_shared_config(
            {
                "id": "project-y-drive",
                "provider": "google-drive",
                "remote_id": "folder:abc123",
                "attached_brain_ids": [],
            },
            project_brain_id="project-y",
        )

    assert "local_cache_path is required" in str(exc.value)


def test_document_sync_status_names_revision_states():
    assert (
        document_sync_status(
            remote_revision="drive-revision-42",
            indexed_revision="drive-revision-42",
            summary_generated_from_revision="drive-revision-42",
            has_local_index=True,
            has_access=True,
        )
        == "synced"
    )
    assert (
        document_sync_status(
            remote_revision="drive-revision-43",
            indexed_revision="drive-revision-42",
            summary_generated_from_revision="drive-revision-43",
            has_local_index=True,
            has_access=True,
        )
        == "source_changed"
    )
    assert (
        document_sync_status(
            remote_revision="drive-revision-42",
            indexed_revision=None,
            summary_generated_from_revision="drive-revision-42",
            has_local_index=True,
            has_access=True,
        )
        == "source_changed"
    )
    assert (
        document_sync_status(
            remote_revision="drive-revision-43",
            indexed_revision="drive-revision-43",
            summary_generated_from_revision="drive-revision-42",
            has_local_index=True,
            has_access=True,
        )
        == "summary_stale"
    )
    assert (
        document_sync_status(
            remote_revision="drive-revision-43",
            indexed_revision=None,
            summary_generated_from_revision="drive-revision-43",
            has_local_index=False,
            has_access=True,
        )
        == "not_indexed"
    )
    assert (
        document_sync_status(
            remote_revision=None,
            indexed_revision=None,
            summary_generated_from_revision=None,
            has_local_index=False,
            has_access=False,
        )
        == "needs_access"
    )


def test_document_sync_status_preserves_local_synced_without_remote_revision():
    assert (
        document_sync_status(
            remote_revision=None,
            indexed_revision=None,
            summary_generated_from_revision=None,
            has_local_index=True,
            has_access=True,
        )
        == "synced"
    )


@pytest.mark.parametrize("remote_revision", [None, ""])
def test_document_sync_status_marks_required_remote_revision_unproven_as_changed(
    remote_revision,
):
    assert (
        document_sync_status(
            remote_revision=remote_revision,
            indexed_revision="drive-revision-42",
            summary_generated_from_revision="drive-revision-42",
            has_local_index=True,
            has_access=True,
            requires_remote_revision=True,
        )
        == "source_changed"
    )


def test_attachment_metadata_serializes_for_index_frontmatter(tmp_path):
    metadata = DocumentAttachmentMetadata(
        canonical_document_id="google-drive:file:def456",
        source_id="project-y-drive",
        source_type="shared",
        provider="google-drive",
        attached_brain_ids=("project-y", "personal"),
        remote_id="google-drive:file:def456",
        remote_revision="drive-revision-42",
        remote_modified_at="2026-06-07T08:00:00Z",
        indexed_revision="drive-revision-42",
        index_status="synced",
        catalog_entry_path="project-brain/knowledge/documents/project-y-drive/architecture.md",
        catalog_title="Architecture Overview",
        catalog_summary="Short project catalog summary.",
        summary_generated_from_revision="drive-revision-42",
    )

    frontmatter = metadata.to_frontmatter()

    assert metadata.remote_id == "google-drive:file:def456"
    assert frontmatter["canonical_document_id"] == "google-drive:file:def456"
    assert frontmatter["remote_id"] == "google-drive:file:def456"
    assert frontmatter["attached_brain_ids"] == ["project-y", "personal"]
    assert frontmatter["brain_id"] == ""
    assert frontmatter["catalog_summary"] == "Short project catalog summary."


def test_attachment_metadata_serializes_single_brain_for_frontmatter():
    metadata = DocumentAttachmentMetadata(
        canonical_document_id="filesystem:/Users/example/Downloads/report.pdf",
        source_id="downloads",
        source_type="local",
        provider="filesystem",
        attached_brain_ids=("personal",),
    )

    frontmatter = metadata.to_frontmatter()

    assert frontmatter["brain_id"] == "personal"
