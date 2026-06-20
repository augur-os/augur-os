"""Dashboard-safe MCP wrappers for project document attachment writes."""

from __future__ import annotations

import json
from collections.abc import Iterable

from src.config.paths import get_project_root
from src.lib.index.document_attachments import DocumentAttachmentConfigError
from src.lib.index.document_catalog_writer import upsert_document_catalog_summary
from src.lib.index.document_source_config import read_project_brain_id
from src.lib.index.document_source_config_writer import (
    attach_project_document_source,
    list_project_document_source_records,
    update_project_document_source_summary,
)


async def attach_project_document_source_impl(
    source_id: str,
    name: str,
    provider: str,
    remote_id: str,
    attached_brain_ids: list[str] | str | None = None,
    catalog_title: str = "",
    catalog_summary: str = "",
    summary_status: str = "human",
    summary_generated_from_revision: str = "",
    remote_revision: str = "",
    remote_modified_at: str = "",
    replace: bool = False,
) -> str:
    try:
        project_root = get_project_root()
        record = attach_project_document_source(
            project_root=project_root,
            project_brain_id=read_project_brain_id(project_root),
            source_id=source_id,
            name=name,
            provider=provider,
            remote_id=remote_id,
            attached_brain_ids=attached_brain_ids,
            catalog_title=catalog_title,
            catalog_summary=catalog_summary,
            summary_status=summary_status,
            summary_generated_from_revision=summary_generated_from_revision,
            remote_revision=remote_revision,
            remote_modified_at=remote_modified_at,
            replace=replace,
        )
        return json.dumps({"success": True, "record": record}, indent=2)
    except DocumentAttachmentConfigError as exc:
        return json.dumps({"success": False, "error": str(exc)}, indent=2)


async def list_project_document_sources_impl() -> str:
    try:
        sources = list_project_document_source_records(get_project_root())
        return json.dumps({"success": True, "sources": sources}, indent=2)
    except DocumentAttachmentConfigError as exc:
        return json.dumps({"success": False, "error": str(exc)}, indent=2)


async def update_project_document_source_summary_impl(
    source_id: str,
    catalog_summary: str,
    catalog_title: str = "",
    summary_status: str = "human",
    summary_generated_from_revision: str = "",
) -> str:
    try:
        record = update_project_document_source_summary(
            project_root=get_project_root(),
            source_id=source_id,
            catalog_title=catalog_title,
            catalog_summary=catalog_summary,
            summary_status=summary_status,
            summary_generated_from_revision=summary_generated_from_revision,
        )
        return json.dumps({"success": True, "record": record}, indent=2)
    except DocumentAttachmentConfigError as exc:
        return json.dumps({"success": False, "error": str(exc)}, indent=2)


async def upsert_document_catalog_summary_impl(
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
) -> str:
    try:
        path = upsert_document_catalog_summary(
            project_root=get_project_root(),
            source_id=source_id,
            title=title,
            summary=summary,
            remote_id=remote_id,
            canonical_document_id=canonical_document_id,
            source_relative_path=source_relative_path,
            provider=provider,
            attached_brain_ids=attached_brain_ids,
            summary_status=summary_status,
            summary_generated_from_revision=summary_generated_from_revision,
            remote_revision=remote_revision,
            remote_modified_at=remote_modified_at,
        )
        return json.dumps({"success": True, "path": str(path)}, indent=2)
    except DocumentAttachmentConfigError as exc:
        return json.dumps({"success": False, "error": str(exc)}, indent=2)
