from __future__ import annotations

from pathlib import Path

import pytest

from src.lib.index.document_attachments import DocumentAttachmentConfigError
from src.lib.index.document_source_config import (
    configured_document_sources,
    read_project_brain_id,
)


def _write_sources_config(project_root: Path, body: str) -> Path:
    config_path = project_root / "config" / "documents" / "sources.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(body, encoding="utf-8")
    return config_path


def test_configured_document_sources_include_personal_defaults_without_config(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    documents_dir = tmp_path / "Au-docs"
    documents_dir.mkdir()

    sources = configured_document_sources(
        project_root=project_root,
        documents_dir=documents_dir,
        cache_root=tmp_path / "cache",
    )

    assert sources[0].id == "documents"
    assert sources[0].provider == "filesystem"
    assert sources[0].source_type == "local"
    assert sources[0].attached_brain_ids == ("personal",)


@pytest.mark.parametrize(
    "config_body",
    [
        pytest.param("", id="empty"),
        pytest.param("# shared document sources are not configured yet\n", id="comment"),
        pytest.param("version: 1\n", id="mapping-without-sources"),
    ],
)
def test_configured_document_sources_treats_empty_config_as_no_shared_sources(
    tmp_path,
    monkeypatch,
    config_body,
):
    project_root = tmp_path / "project"
    _write_sources_config(project_root, config_body)
    documents_dir = tmp_path / "Au-docs"
    documents_dir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)

    sources = configured_document_sources(
        project_root=project_root,
        documents_dir=documents_dir,
        cache_root=tmp_path / "cache",
    )

    assert [source.id for source in sources] == ["documents"]


def test_configured_document_sources_load_project_shared_source(tmp_path):
    project_root = tmp_path / "project"
    _write_sources_config(
        project_root,
        "sources:\n"
        "  - id: project-y-drive\n"
        "    name: Project Y Drive\n"
        "    provider: google-drive\n"
        "    remote_id: folder:abc123\n"
        "    attached_brain_ids:\n"
        "      - project-y\n"
        "    remote_revision: drive-revision-42\n",
    )
    documents_dir = tmp_path / "Au-docs"
    documents_dir.mkdir()

    sources = configured_document_sources(
        project_root=project_root,
        documents_dir=documents_dir,
        project_brain_id="project-y",
        cache_root=tmp_path / "cache",
    )

    shared = next(source for source in sources if source.id == "project-y-drive")
    assert shared.name == "Project Y Drive"
    assert shared.source_type == "shared"
    assert shared.provider == "google-drive"
    assert shared.source_remote_id == "folder:abc123"
    assert shared.attached_brain_ids == ("project-y",)
    assert shared.remote_revision == "drive-revision-42"
    assert shared.resolved_path == (tmp_path / "cache" / "project-y-drive").resolve(strict=False)


def test_configured_document_sources_load_project_shared_source_catalog_summary(tmp_path):
    project_root = tmp_path / "project"
    _write_sources_config(
        project_root,
        "sources:\n"
        "  - id: project-y-drive\n"
        "    name: Project Y Drive\n"
        "    provider: google-drive\n"
        "    remote_id: folder:abc123\n"
        "    attached_brain_ids:\n"
        "      - project-y\n"
        "    remote_revision: drive-revision-42\n"
        "    catalog_title: Project Y Reference Folder\n"
        "    catalog_summary: Shared project documents used by Browse cards.\n"
        "    summary_status: human\n"
        "    summary_generated_from_revision: drive-revision-41\n",
    )
    documents_dir = tmp_path / "Au-docs"
    documents_dir.mkdir()

    sources = configured_document_sources(
        project_root=project_root,
        documents_dir=documents_dir,
        project_brain_id="project-y",
        cache_root=tmp_path / "cache",
    )

    shared = next(source for source in sources if source.id == "project-y-drive")
    assert shared.catalog_title == "Project Y Reference Folder"
    assert shared.catalog_summary == "Shared project documents used by Browse cards."
    assert shared.summary_status == "human"
    assert shared.summary_generated_from_revision == "drive-revision-41"


@pytest.mark.parametrize("source_id", ["documents", "desktop", "downloads"])
def test_configured_document_sources_rejects_shared_ids_reserved_by_personal_defaults(
    tmp_path,
    monkeypatch,
    source_id,
):
    project_root = tmp_path / "project"
    _write_sources_config(
        project_root,
        "sources:\n" f"  - id: {source_id}\n" "    provider: google-drive\n" "    remote_id: folder:abc123\n",
    )
    documents_dir = tmp_path / "Au-docs"
    home = tmp_path / "home"
    for path in (documents_dir, home / "Desktop", home / "Downloads"):
        path.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)

    with pytest.raises(
        DocumentAttachmentConfigError,
        match=rf"(duplicate|reserved) source id.*{source_id}",
    ):
        configured_document_sources(
            project_root=project_root,
            documents_dir=documents_dir,
            project_brain_id="project-y",
            cache_root=tmp_path / "cache",
        )


@pytest.mark.parametrize("source_id", ["desktop", "downloads"])
def test_configured_document_sources_rejects_canonical_personal_ids_when_folders_missing(
    tmp_path,
    monkeypatch,
    source_id,
):
    project_root = tmp_path / "project"
    _write_sources_config(
        project_root,
        "sources:\n" f"  - id: {source_id}\n" "    provider: google-drive\n" "    remote_id: folder:abc123\n",
    )
    documents_dir = tmp_path / "Au-docs"
    documents_dir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)

    with pytest.raises(
        DocumentAttachmentConfigError,
        match=rf"reserved source id.*{source_id}",
    ):
        configured_document_sources(
            project_root=project_root,
            documents_dir=documents_dir,
            project_brain_id="project-y",
            cache_root=tmp_path / "cache",
        )


def test_configured_document_sources_rejects_duplicate_shared_ids(tmp_path):
    project_root = tmp_path / "project"
    _write_sources_config(
        project_root,
        "sources:\n"
        "  - id: project-y-drive\n"
        "    provider: google-drive\n"
        "    remote_id: folder:abc123\n"
        "  - id: project-y-drive\n"
        "    provider: sharepoint\n"
        "    remote_id: folder:def456\n",
    )
    documents_dir = tmp_path / "Au-docs"
    documents_dir.mkdir()

    with pytest.raises(
        DocumentAttachmentConfigError,
        match=r"duplicate source id.*project-y-drive",
    ):
        configured_document_sources(
            project_root=project_root,
            documents_dir=documents_dir,
            project_brain_id="project-y",
            cache_root=tmp_path / "cache",
        )


@pytest.mark.parametrize("field_name", ["include", "exclude"])
def test_configured_document_sources_rejects_unsupported_policy_fields(
    tmp_path,
    field_name,
):
    project_root = tmp_path / "project"
    _write_sources_config(
        project_root,
        "sources:\n"
        "  - id: project-y-drive\n"
        "    provider: google-drive\n"
        "    remote_id: folder:abc123\n"
        f"    {field_name}:\n"
        "      - '**/*.pdf'\n",
    )
    documents_dir = tmp_path / "Au-docs"
    documents_dir.mkdir()

    with pytest.raises(
        DocumentAttachmentConfigError,
        match=rf"Unsupported document source field.*{field_name}",
    ):
        configured_document_sources(
            project_root=project_root,
            documents_dir=documents_dir,
            project_brain_id="project-y",
            cache_root=tmp_path / "cache",
        )


@pytest.mark.parametrize(
    "config_body",
    [
        pytest.param(
            "sources:\n"
            "  - id: local-downloads\n"
            "    provider: filesystem\n"
            "    remote_id: folder:abc123\n"
            "    attached_brain_ids:\n"
            "      - project-y\n",
            id="filesystem-provider",
        ),
        pytest.param(
            "sources:\n"
            "  - id: project-y-drive\n"
            "    provider: google-drive\n"
            "    remote_id: folder:abc123\n"
            "    path: /Users/example/Downloads\n"
            "    attached_brain_ids:\n"
            "      - project-y\n",
            id="raw-path",
        ),
    ],
)
def test_configured_document_sources_reject_project_local_sources(
    tmp_path,
    config_body,
):
    project_root = tmp_path / "project"
    _write_sources_config(project_root, config_body)
    documents_dir = tmp_path / "Au-docs"
    documents_dir.mkdir()

    with pytest.raises(DocumentAttachmentConfigError):
        configured_document_sources(
            project_root=project_root,
            documents_dir=documents_dir,
            project_brain_id="project-y",
            cache_root=tmp_path / "cache",
        )


@pytest.mark.parametrize(
    ("config_body", "expected_message"),
    [
        pytest.param(
            "sources:\n" "  - id: local-downloads\n" "    provider: filesystem\n" "    remote_id: folder:abc123\n",
            "shared provider",
            id="filesystem-provider",
        ),
        pytest.param(
            "sources:\n"
            "  - id: project-y-drive\n"
            "    provider: google-drive\n"
            "    remote_id: folder:abc123\n"
            "    path: /Users/example/Downloads\n",
            "must not store local paths",
            id="raw-path",
        ),
        pytest.param(
            "sources:\n" "  - id: project-y-drive\n" "    provider: google-drive\n",
            "remote_id.*required",
            id="missing-remote-id",
        ),
    ],
)
def test_configured_document_sources_reports_bad_source_fields_before_missing_brain_manifest(
    tmp_path,
    config_body,
    expected_message,
):
    project_root = tmp_path / "project"
    _write_sources_config(project_root, config_body)
    documents_dir = tmp_path / "Au-docs"
    documents_dir.mkdir()

    with pytest.raises(DocumentAttachmentConfigError, match=expected_message):
        configured_document_sources(
            project_root=project_root,
            documents_dir=documents_dir,
            cache_root=tmp_path / "cache",
        )


@pytest.mark.parametrize(
    "config_body",
    [
        pytest.param("sources: project-y-drive\n", id="string"),
        pytest.param("sources:\n  id: project-y-drive\n", id="mapping"),
    ],
)
def test_configured_document_sources_reject_invalid_sources_shape(
    tmp_path,
    config_body,
):
    project_root = tmp_path / "project"
    _write_sources_config(project_root, config_body)
    documents_dir = tmp_path / "Au-docs"
    documents_dir.mkdir()

    with pytest.raises(DocumentAttachmentConfigError, match="sources.*list"):
        configured_document_sources(
            project_root=project_root,
            documents_dir=documents_dir,
            project_brain_id="project-y",
            cache_root=tmp_path / "cache",
        )


def test_configured_document_sources_reject_non_mapping_source_entries(tmp_path):
    project_root = tmp_path / "project"
    _write_sources_config(
        project_root,
        "sources:\n" "  - project-y-drive\n",
    )
    documents_dir = tmp_path / "Au-docs"
    documents_dir.mkdir()

    with pytest.raises(DocumentAttachmentConfigError, match="mapping"):
        configured_document_sources(
            project_root=project_root,
            documents_dir=documents_dir,
            project_brain_id="project-y",
            cache_root=tmp_path / "cache",
        )


def test_configured_document_sources_reject_invalid_yaml(tmp_path):
    project_root = tmp_path / "project"
    _write_sources_config(project_root, "sources:\n  - id: [broken\n")
    documents_dir = tmp_path / "Au-docs"
    documents_dir.mkdir()

    with pytest.raises(DocumentAttachmentConfigError, match="Unable to read"):
        configured_document_sources(
            project_root=project_root,
            documents_dir=documents_dir,
            project_brain_id="project-y",
            cache_root=tmp_path / "cache",
        )


def test_configured_document_sources_uses_default_cache_root(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    _write_sources_config(
        project_root,
        "sources:\n" "  - id: project-y-drive\n" "    provider: google-drive\n" "    remote_id: folder:abc123\n",
    )
    documents_dir = tmp_path / "Au-docs"
    documents_dir.mkdir()
    cache_dir = tmp_path / "augur-cache"

    monkeypatch.setattr(
        "src.lib.index.document_source_config.get_cache_dir",
        lambda: cache_dir,
    )

    sources = configured_document_sources(
        project_root=project_root,
        documents_dir=documents_dir,
        project_brain_id="project-y",
    )

    shared = next(source for source in sources if source.id == "project-y-drive")
    assert shared.resolved_path == (cache_dir / "document-sources" / "project-y-drive").resolve(strict=False)


def test_configured_document_sources_rejects_unsafe_id_before_cache_path_use(tmp_path):
    project_root = tmp_path / "project"
    _write_sources_config(
        project_root,
        "sources:\n" "  - id: ../escape\n" "    provider: google-drive\n" "    remote_id: folder:abc123\n",
    )
    documents_dir = tmp_path / "Au-docs"
    documents_dir.mkdir()

    with pytest.raises(DocumentAttachmentConfigError, match="safe slug"):
        configured_document_sources(
            project_root=project_root,
            documents_dir=documents_dir,
            project_brain_id="project-y",
            cache_root=tmp_path / "cache",
        )


def test_read_project_brain_id_reads_manifest(tmp_path):
    project_root = tmp_path / "project"
    manifest = project_root / "project-brain" / "BRAIN.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        "schema_version: 1\n" "id: project-y\n" "type: project\n" "root: .\n",
        encoding="utf-8",
    )

    assert read_project_brain_id(project_root) == "project-y"


def test_read_project_brain_id_raises_attachment_error_on_failure(tmp_path):
    project_root = tmp_path / "project"

    with pytest.raises(DocumentAttachmentConfigError, match="Unable to read"):
        read_project_brain_id(project_root)
