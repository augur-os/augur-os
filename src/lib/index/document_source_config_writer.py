"""Bounded writers for git-tracked project document source config."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_cache_dir
from src.lib.index.document_attachments import (
    DocumentAttachmentConfigError,
    document_source_from_shared_config,
    normalize_attached_brain_ids,
)
from src.lib.index.document_source_config import (
    KNOWN_SHARED_SOURCE_FIELDS,
    SOURCE_CONFIG_RELATIVE_PATH,
)


def list_project_document_source_records(project_root: Path) -> list[dict[str, Any]]:
    config_path = Path(project_root) / SOURCE_CONFIG_RELATIVE_PATH
    payload = _read_payload(config_path)
    raw_sources = payload.get("sources", [])
    if raw_sources is None:
        return []
    if not isinstance(raw_sources, list):
        raise DocumentAttachmentConfigError("config/documents/sources.yaml field 'sources' must be a list")
    records: list[dict[str, Any]] = []
    for raw in raw_sources:
        if not isinstance(raw, Mapping):
            raise DocumentAttachmentConfigError("Each document source entry must be a mapping")
        records.append(dict(raw))
    return records


def attach_project_document_source(
    *,
    project_root: Path,
    project_brain_id: str,
    source_id: str,
    name: str,
    provider: str,
    remote_id: str,
    attached_brain_ids: Iterable[str] | str | None = None,
    catalog_title: str = "",
    catalog_summary: str = "",
    summary_status: str = "",
    summary_generated_from_revision: str = "",
    remote_revision: str = "",
    remote_modified_at: str = "",
    replace: bool = False,
    path: str | None = None,
) -> dict[str, Any]:
    record = _clean_record(
        {
            "id": source_id,
            "name": name,
            "provider": provider,
            "remote_id": remote_id,
            "attached_brain_ids": list(normalize_attached_brain_ids(attached_brain_ids)) or [project_brain_id],
            "catalog_title": catalog_title,
            "catalog_summary": catalog_summary,
            "summary_status": summary_status,
            "summary_generated_from_revision": summary_generated_from_revision,
            "remote_revision": remote_revision,
            "remote_modified_at": remote_modified_at,
            "path": path,
        }
    )
    document_source_from_shared_config(
        record,
        project_brain_id=project_brain_id,
        local_cache_path=get_cache_dir() / "document-sources" / source_id,
    )

    config_path = Path(project_root) / SOURCE_CONFIG_RELATIVE_PATH
    payload = _read_payload(config_path)
    sources = list_project_document_source_records(project_root)
    existing_index = next(
        (index for index, item in enumerate(sources) if item.get("id") == source_id),
        None,
    )
    if existing_index is not None and not replace:
        raise DocumentAttachmentConfigError(f"Document source {source_id!r} already exists")
    if existing_index is None:
        sources.append(record)
    else:
        sources[existing_index] = record
    payload["sources"] = sources
    _write_payload(config_path, payload)
    return record


def update_project_document_source_summary(
    *,
    project_root: Path,
    source_id: str,
    catalog_summary: str,
    summary_status: str,
    catalog_title: str = "",
    summary_generated_from_revision: str = "",
) -> dict[str, Any]:
    config_path = Path(project_root) / SOURCE_CONFIG_RELATIVE_PATH
    payload = _read_payload(config_path)
    sources = list_project_document_source_records(project_root)
    for record in sources:
        if record.get("id") != source_id:
            continue
        _set_or_remove(record, "catalog_title", catalog_title)
        _set_or_remove(record, "catalog_summary", catalog_summary)
        _set_or_remove(record, "summary_status", summary_status)
        _set_or_remove(
            record,
            "summary_generated_from_revision",
            summary_generated_from_revision,
        )
        payload["sources"] = sources
        _write_payload(config_path, payload)
        return record
    raise DocumentAttachmentConfigError(f"Document source {source_id!r} is not configured")


def _read_payload(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise DocumentAttachmentConfigError(f"Unable to read document source config from {config_path}") from exc
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise DocumentAttachmentConfigError("config/documents/sources.yaml must be a mapping")
    return dict(loaded)


def _write_payload(config_path: Path, payload: Mapping[str, Any]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(dict(payload), sort_keys=False, allow_unicode=True)
    config_path.write_text(text, encoding="utf-8")


def _clean_record(raw: Mapping[str, Any]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in KNOWN_SHARED_SOURCE_FIELDS:
            raise DocumentAttachmentConfigError(f"Unsupported document source field(s): {key}")
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        if isinstance(value, list) and not value:
            continue
        record[key] = value
    return record


def _set_or_remove(record: dict[str, Any], key: str, value: str) -> None:
    clean = value.strip() if isinstance(value, str) else ""
    if clean:
        record[key] = clean
    else:
        record.pop(key, None)
