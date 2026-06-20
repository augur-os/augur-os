"""Git-synced project document catalog reader."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.index.document_attachments import normalize_attached_brain_ids


@dataclass(frozen=True)
class DocumentCatalogEntry:
    remote_id: str
    canonical_document_id: str
    source_id: str
    source_relative_path: str
    provider: str
    attached_brain_ids: tuple[str, ...]
    title: str
    summary: str
    summary_status: str
    summary_generated_from_revision: str
    remote_revision: str
    remote_modified_at: str
    path: Path


class DocumentCatalog(dict[str, DocumentCatalogEntry]):
    """Dict-compatible catalog with identity-domain indexes."""

    def __init__(self) -> None:
        super().__init__()
        self.by_remote_id: dict[str, DocumentCatalogEntry] = {}
        self.by_canonical_document_id: dict[str, DocumentCatalogEntry] = {}
        self.by_source_path: dict[str, DocumentCatalogEntry] = {}

    def add_entry(self, entry: DocumentCatalogEntry) -> None:
        source_path_key = _source_path_key(entry.source_id, entry.source_relative_path)
        if entry.remote_id:
            self.by_remote_id[entry.remote_id] = entry
            self[entry.remote_id] = entry
        if entry.canonical_document_id:
            self.by_canonical_document_id[entry.canonical_document_id] = entry
            self.setdefault(entry.canonical_document_id, entry)
        if source_path_key:
            self.by_source_path[source_path_key] = entry
            self.setdefault(source_path_key, entry)


def load_document_catalog(project_root: Path) -> dict[str, DocumentCatalogEntry]:
    catalog_root = Path(project_root) / "project-brain" / "knowledge" / "documents"
    if not catalog_root.is_dir():
        return {}

    entries = DocumentCatalog()
    for path in sorted(catalog_root.rglob("*.md")):
        try:
            metadata, body = parse_frontmatter(path)
        except Exception:
            continue

        remote_id = _string(metadata.get("remote_id"))
        canonical_document_id = _string(metadata.get("canonical_document_id"))
        source_id = _string(metadata.get("source_id"))
        source_relative_path = _string(metadata.get("source_relative_path"))
        if not any((remote_id, canonical_document_id, source_id and source_relative_path)):
            continue

        entry = DocumentCatalogEntry(
            remote_id=remote_id,
            canonical_document_id=canonical_document_id,
            source_id=source_id,
            source_relative_path=source_relative_path,
            provider=_string(metadata.get("provider")),
            attached_brain_ids=normalize_attached_brain_ids(metadata.get("attached_brain_ids")),
            title=_string(metadata.get("title")) or _title_from_path(path),
            summary=body.strip(),
            summary_status=_string(metadata.get("summary_status")),
            summary_generated_from_revision=_string(metadata.get("summary_generated_from_revision")),
            remote_revision=_string(metadata.get("remote_revision")),
            remote_modified_at=_string(metadata.get("remote_modified_at")),
            path=path,
        )
        entries.add_entry(entry)
    return entries


def lookup_catalog_entry(
    catalog: Mapping[str, DocumentCatalogEntry],
    *,
    remote_id: str,
    canonical_document_id: str,
    source_id: str,
    source_relative_path: str,
) -> DocumentCatalogEntry | None:
    for index_name, key in (
        ("by_remote_id", remote_id),
        ("by_canonical_document_id", canonical_document_id),
        ("by_source_path", _source_path_key(source_id, source_relative_path)),
    ):
        index = getattr(catalog, index_name, None)
        if key and isinstance(index, Mapping):
            entry = index.get(key)
            if entry is not None:
                return entry

    for key in (
        remote_id,
        canonical_document_id,
        _source_path_key(source_id, source_relative_path),
    ):
        if key and key in catalog:
            return catalog[key]
    return None


def _source_path_key(source_id: str, source_relative_path: str) -> str:
    if not source_id or not source_relative_path:
        return ""
    return f"source-path:{source_id}:{source_relative_path}"


def _string(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, datetime):
        text = value.isoformat()
        return f"{text.removesuffix('+00:00')}Z" if text.endswith("+00:00") else text
    if isinstance(value, date):
        return value.isoformat()
    return ""


def _title_from_path(path: Path) -> str:
    return path.stem.replace("-", " ").replace("_", " ").title()
