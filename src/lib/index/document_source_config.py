"""Load configured document sources for personal and project document indexing."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_cache_dir
from src.lib.index.document_attachments import (
    SAFE_SOURCE_ID_RE,
    SHARED_PROJECT_PROVIDERS,
    DocumentAttachmentConfigError,
    document_source_from_shared_config,
)
from src.lib.index.document_sources import DocumentSource, default_document_sources

SOURCE_CONFIG_RELATIVE_PATH = Path("config") / "documents" / "sources.yaml"
PERSONAL_DEFAULT_SOURCE_IDS = frozenset({"documents", "desktop", "downloads"})
KNOWN_SHARED_SOURCE_FIELDS = frozenset(
    {
        "id",
        "name",
        "provider",
        "remote_id",
        "attached_brain_ids",
        "remote_revision",
        "remote_modified_at",
        "catalog_title",
        "catalog_summary",
        "summary_status",
        "summary_generated_from_revision",
        "path",
    }
)


def read_project_brain_id(project_root: Path) -> str:
    manifest_path = Path(project_root) / "project-brain" / "BRAIN.yaml"
    try:
        from src.lib.brain_manifest import BRAIN_MANIFEST_NAME, read_brain_manifest

        manifest = read_brain_manifest(Path(project_root) / "project-brain" / BRAIN_MANIFEST_NAME)
    except Exception as exc:
        raise DocumentAttachmentConfigError(f"Unable to read project brain id from {manifest_path}") from exc
    return manifest.id


def configured_document_sources(
    *,
    project_root: Path,
    documents_dir: Path,
    project_brain_id: str | None = None,
    cache_root: Path | None = None,
) -> list[DocumentSource]:
    sources = list(default_document_sources(documents_dir=documents_dir))
    config_path = Path(project_root) / SOURCE_CONFIG_RELATIVE_PATH
    if not config_path.is_file():
        return sources

    raw = _read_sources_yaml(config_path)
    if "sources" not in raw:
        return sources
    raw_sources = raw["sources"]
    if not isinstance(raw_sources, list):
        raise DocumentAttachmentConfigError("config/documents/sources.yaml field 'sources' must be a list")
    if not raw_sources:
        return sources

    reserved_source_ids = PERSONAL_DEFAULT_SOURCE_IDS | {source.id for source in sources}
    shared_source_ids: set[str] = set()
    shared_sources: list[tuple[str, Mapping[str, Any]]] = []
    for raw_source in raw_sources:
        if not isinstance(raw_source, Mapping):
            raise DocumentAttachmentConfigError("Each document source entry must be a mapping")
        _reject_unsupported_fields(raw_source)
        source_id = _safe_source_id(raw_source)
        if source_id in reserved_source_ids:
            raise DocumentAttachmentConfigError(f"Document source uses reserved source id {source_id!r}")
        if source_id in shared_source_ids:
            raise DocumentAttachmentConfigError(f"duplicate source id {source_id!r} in config/documents/sources.yaml")
        _validate_shared_source_fields(raw_source)
        shared_source_ids.add(source_id)
        shared_sources.append((source_id, raw_source))

    brain_id = project_brain_id or read_project_brain_id(project_root)
    local_cache_root = Path(cache_root) if cache_root is not None else get_cache_dir() / "document-sources"
    for source_id, raw_source in shared_sources:
        sources.append(
            document_source_from_shared_config(
                raw_source,
                project_brain_id=brain_id,
                local_cache_path=local_cache_root / source_id,
            )
        )
    return sources


def _read_sources_yaml(config_path: Path) -> Mapping[str, Any]:
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise DocumentAttachmentConfigError(f"Unable to read document source config from {config_path}") from exc
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise DocumentAttachmentConfigError("config/documents/sources.yaml must be a mapping with a 'sources' list")
    return raw


def _reject_unsupported_fields(raw_source: Mapping[str, Any]) -> None:
    unsupported = sorted(str(key) for key in raw_source if key not in KNOWN_SHARED_SOURCE_FIELDS)
    if unsupported:
        raise DocumentAttachmentConfigError("Unsupported document source field(s): " + ", ".join(unsupported))


def _safe_source_id(raw_source: Mapping[str, Any]) -> str:
    value = raw_source.get("id")
    if not isinstance(value, str) or not value.strip():
        raise DocumentAttachmentConfigError("Document source field 'id' is required")
    source_id = value.strip()
    if not SAFE_SOURCE_ID_RE.fullmatch(source_id):
        raise DocumentAttachmentConfigError("Document source field 'id' must be a safe slug")
    return source_id


def _validate_shared_source_fields(raw_source: Mapping[str, Any]) -> None:
    provider = _required_nonblank_string(raw_source, "provider")
    if provider not in SHARED_PROJECT_PROVIDERS:
        raise DocumentAttachmentConfigError(
            "Project document sources must use a shared provider such as google-drive or sharepoint"
        )
    if "path" in raw_source:
        raise DocumentAttachmentConfigError("Project document sources must not store local paths")
    _required_nonblank_string(raw_source, "remote_id")


def _required_nonblank_string(raw_source: Mapping[str, Any], key: str) -> str:
    value = raw_source.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DocumentAttachmentConfigError(f"Document source field {key!r} is required")
    return value.strip()
