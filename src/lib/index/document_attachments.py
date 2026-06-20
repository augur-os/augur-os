"""Document attachment and freshness metadata for Browse/RAG."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:
    from src.lib.index.document_sources import DocumentSource


SHARED_PROJECT_PROVIDERS = {
    "google-drive",
    "google-docs",
    "sharepoint",
    "onedrive",
    "github",
    "notion",
    "confluence",
    "shared-folder",
}
SAFE_SOURCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class DocumentAttachmentConfigError(ValueError):
    """Raised when document attachment configuration violates ownership rules."""


def normalize_attached_brain_ids(raw: Iterable[object] | None) -> tuple[str, ...]:
    values: Iterable[object]
    if isinstance(raw, str):
        values = raw.split(",")
    else:
        values = raw or ()
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        brain_id = value.strip()
        if not brain_id or brain_id in seen:
            continue
        seen.add(brain_id)
        result.append(brain_id)
    return tuple(result)


def document_sync_status(
    *,
    remote_revision: str | None,
    indexed_revision: str | None,
    summary_generated_from_revision: str | None,
    has_local_index: bool,
    has_access: bool,
    requires_remote_revision: bool = False,
) -> str:
    if not has_access:
        return "needs_access"
    if not has_local_index:
        return "not_indexed"
    if requires_remote_revision and not (remote_revision or "").strip():
        return "source_changed"
    if remote_revision and remote_revision != indexed_revision:
        return "source_changed"
    if remote_revision and summary_generated_from_revision and remote_revision != summary_generated_from_revision:
        return "summary_stale"
    return "synced"


@dataclass(frozen=True)
class DocumentAttachmentMetadata:
    canonical_document_id: str
    source_id: str
    source_type: str
    provider: str
    attached_brain_ids: tuple[str, ...]
    remote_id: str = ""
    remote_revision: str = ""
    remote_modified_at: str = ""
    indexed_revision: str = ""
    index_status: str = "synced"
    catalog_entry_path: str = ""
    catalog_title: str = ""
    catalog_summary: str = ""
    summary_status: str = ""
    summary_generated_from_revision: str = ""

    def to_frontmatter(self) -> dict[str, Any]:
        brain_id = self.attached_brain_ids[0] if len(self.attached_brain_ids) == 1 else ""
        return {
            "canonical_document_id": self.canonical_document_id,
            "remote_id": self.remote_id,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "provider": self.provider,
            "attached_brain_ids": list(self.attached_brain_ids),
            "brain_id": brain_id,
            "remote_revision": self.remote_revision,
            "remote_modified_at": self.remote_modified_at,
            "indexed_revision": self.indexed_revision,
            "index_status": self.index_status,
            "catalog_entry_path": self.catalog_entry_path,
            "catalog_title": self.catalog_title,
            "catalog_summary": self.catalog_summary,
            "summary_status": self.summary_status,
            "summary_generated_from_revision": self.summary_generated_from_revision,
        }


def attachment_metadata_for_local_personal_document(
    *,
    source_id: str,
    document_path: Path,
) -> DocumentAttachmentMetadata:
    resolved_document = Path(document_path).expanduser().resolve(strict=False)
    return DocumentAttachmentMetadata(
        canonical_document_id=f"filesystem:{resolved_document}",
        source_id=source_id,
        source_type="local",
        provider="filesystem",
        attached_brain_ids=("personal",),
        index_status="synced",
    )


def document_source_from_shared_config(
    raw: Mapping[str, Any],
    *,
    project_brain_id: str,
    local_cache_path: Path | None = None,
) -> DocumentSource:
    from src.lib.index.document_sources import DocumentSource

    source_id = _required_safe_slug(raw, "id")
    provider = _required_string(raw, "provider")
    if provider not in SHARED_PROJECT_PROVIDERS:
        raise DocumentAttachmentConfigError(
            "Project document sources must use a shared provider such as google-drive or sharepoint"
        )
    if "path" in raw:
        raise DocumentAttachmentConfigError("Project document sources must not store local paths")
    source_remote_id = _required_string(raw, "remote_id")
    attached = _attached_brain_ids_from_shared_config(
        raw.get("attached_brain_ids"),
        project_brain_id=project_brain_id,
    )
    if local_cache_path is None:
        raise DocumentAttachmentConfigError("local_cache_path is required for shared document sources")
    return DocumentSource(
        id=source_id,
        name=_optional_nonblank_string(raw, "name", default=source_id),
        path=local_cache_path,
        source_type="shared",
        provider=provider,
        attached_brain_ids=attached,
        source_remote_id=source_remote_id,
        remote_revision=str(raw.get("remote_revision") or ""),
        remote_modified_at=str(raw.get("remote_modified_at") or ""),
        catalog_title=_optional_nonblank_string(raw, "catalog_title", default=""),
        catalog_summary=_optional_nonblank_string(raw, "catalog_summary", default=""),
        summary_status=_optional_nonblank_string(raw, "summary_status", default=""),
        summary_generated_from_revision=_optional_nonblank_string(
            raw,
            "summary_generated_from_revision",
            default="",
        ),
    )


def _attached_brain_ids_from_shared_config(
    raw: object,
    *,
    project_brain_id: str,
) -> tuple[str, ...]:
    if raw is None:
        attached = ()
    elif isinstance(raw, str):
        if not raw.strip() or any(not item.strip() for item in raw.split(",")):
            raise DocumentAttachmentConfigError("attached_brain_ids must be a string or list of strings")
        attached = normalize_attached_brain_ids(raw)
    elif isinstance(raw, Mapping):
        raise DocumentAttachmentConfigError("attached_brain_ids must be a string or list of strings")
    elif isinstance(raw, (list, tuple)):
        if any(not isinstance(value, str) or not value.strip() for value in raw):
            raise DocumentAttachmentConfigError("attached_brain_ids must be a string or list of strings")
        attached = normalize_attached_brain_ids(raw)
    else:
        raise DocumentAttachmentConfigError("attached_brain_ids must be a string or list of strings")
    if not attached:
        return (project_brain_id,)
    if project_brain_id not in attached:
        return (project_brain_id, *attached)
    return attached


def _required_string(raw: Mapping[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DocumentAttachmentConfigError(f"Document source field {key!r} is required")
    return value.strip()


def _optional_nonblank_string(
    raw: Mapping[str, Any],
    key: str,
    *,
    default: str,
) -> str:
    if key not in raw:
        return default
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DocumentAttachmentConfigError(f"Document source field {key!r} must be a nonblank string")
    return value.strip()


def _required_safe_slug(raw: Mapping[str, Any], key: str) -> str:
    value = _required_string(raw, key)
    if not SAFE_SOURCE_ID_RE.fullmatch(value):
        raise DocumentAttachmentConfigError(f"Document source field {key!r} must be a safe slug")
    return value
