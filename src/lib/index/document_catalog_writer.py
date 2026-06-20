"""Bounded writers for git-tracked project document catalog summaries."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from src.lib.frontmatter_utils import write_frontmatter
from src.lib.index.document_attachments import (
    SAFE_SOURCE_ID_RE,
    SHARED_PROJECT_PROVIDERS,
    DocumentAttachmentConfigError,
    normalize_attached_brain_ids,
)
from src.lib.index.document_source_config import PERSONAL_DEFAULT_SOURCE_IDS


def upsert_document_catalog_summary(
    *,
    project_root: Path,
    source_id: str,
    title: str,
    summary: str,
    remote_id: str = "",
    canonical_document_id: str = "",
    source_relative_path: str = "",
    provider: str = "",
    attached_brain_ids: Iterable[str] | str | None = None,
    summary_status: str = "human",
    summary_generated_from_revision: str = "",
    remote_revision: str = "",
    remote_modified_at: str = "",
) -> Path:
    source = _safe_slug(source_id, "source_id")
    clean_title = _required_text(title, "title")
    clean_summary = _required_text(summary, "summary")
    if not any(value.strip() for value in (remote_id, canonical_document_id, source_relative_path)):
        raise DocumentAttachmentConfigError("Catalog entries require at least one lookup identity")
    clean_provider = provider.strip().lower()
    _validate_shared_catalog_source(source, clean_provider)

    metadata: dict[str, object] = {
        "remote_id": remote_id.strip(),
        "canonical_document_id": canonical_document_id.strip(),
        "source_id": source,
        "source_relative_path": source_relative_path.strip(),
        "provider": clean_provider,
        "attached_brain_ids": list(normalize_attached_brain_ids(attached_brain_ids)),
        "title": clean_title,
        "summary_status": summary_status.strip() or "human",
        "summary_generated_from_revision": summary_generated_from_revision.strip(),
        "remote_revision": remote_revision.strip(),
        "remote_modified_at": remote_modified_at.strip(),
    }
    metadata = {key: value for key, value in metadata.items() if value not in ("", [])}
    path = (
        Path(project_root)
        / "project-brain"
        / "knowledge"
        / "documents"
        / source
        / f"{_entry_slug(clean_title, remote_id, canonical_document_id, source_relative_path)}.md"
    )
    write_frontmatter(path, metadata, clean_summary + "\n")
    content = path.read_text(encoding="utf-8")
    path.write_text(content.replace("\n---\n\n", "\n---\n", 1), encoding="utf-8")
    return path


def _validate_shared_catalog_source(source_id: str, provider: str) -> None:
    if source_id.lower() in PERSONAL_DEFAULT_SOURCE_IDS or provider not in SHARED_PROJECT_PROVIDERS:
        raise DocumentAttachmentConfigError(
            "Catalog summaries require a shared provider-backed project document source"
        )


def _required_text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DocumentAttachmentConfigError(f"Catalog field {field!r} is required")
    return value.strip()


def _safe_slug(value: str, field: str) -> str:
    clean = _required_text(value, field)
    if not SAFE_SOURCE_ID_RE.fullmatch(clean):
        raise DocumentAttachmentConfigError(f"Catalog field {field!r} must be a safe slug")
    return clean


def _entry_slug(
    title: str,
    remote_id: str,
    canonical_document_id: str,
    source_relative_path: str,
) -> str:
    basis = title or source_relative_path or canonical_document_id or remote_id
    slug = re.sub(r"[^A-Za-z0-9]+", "-", basis).strip("-").lower()
    return slug or "document"
