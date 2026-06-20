"""Document-source and capability metadata helpers for Browse entries."""

from src.config.paths import (
    get_cache_dir,
    get_documents_dir,
    get_project_root,
)


def _copy_document_metadata_aliases(metadata: dict[str, str]) -> None:
    aliases = {
        "attached_brain_ids": "attachedBrainIds",
        "index_status": "indexStatus",
        "catalog_summary": "catalogSummary",
        "summary_status": "summaryStatus",
        "remote_revision": "remoteRevision",
        "indexed_revision": "indexedRevision",
        "remote_modified_at": "remoteModifiedAt",
        "summary_generated_from_revision": "summaryGeneratedFromRevision",
    }
    for source_key, alias_key in aliases.items():
        value = metadata.get(source_key)
        if value and not metadata.get(alias_key):
            metadata[alias_key] = value


def _document_source_entries_for_browse(existing_entries: list[dict]) -> list[dict]:
    try:
        from src.lib.index.document_attachments import DocumentAttachmentConfigError
        from src.lib.index.document_source_config import configured_document_sources
    except Exception:
        return []

    project_root = get_project_root()
    documents_dir = get_documents_dir()
    try:
        sources = configured_document_sources(
            project_root=project_root,
            documents_dir=documents_dir,
            cache_root=get_cache_dir() / "document-sources",
        )
    except DocumentAttachmentConfigError as exc:
        return [_document_source_config_error_entry(str(exc))]
    except Exception as exc:
        return [_document_source_config_error_entry(f"Unable to load document source config: {exc}")]

    indexed_source_ids: set[str] = set()
    for entry in existing_entries:
        if not isinstance(entry, dict):
            continue
        source_id = entry.get("source_id")
        metadata = entry.get("metadata")
        if not source_id and isinstance(metadata, dict):
            source_id = metadata.get("source_id")
        if source_id:
            indexed_source_ids.add(str(source_id))
    entries: list[dict] = []
    for source in sources:
        if getattr(source, "source_type", "") != "shared":
            continue
        if source.id in indexed_source_ids:
            continue
        cache_path = source.resolved_path
        status = "not_indexed" if cache_path.exists() else "needs_access"
        summary = getattr(source, "catalog_summary", "") or "Shared project document source configured for this brain."
        entries.append(
            {
                "id": f"document-source:{source.id}",
                "title": source.name,
                "name": source.name,
                "description": summary,
                "type": "document-source",
                "hub": source.id,
                "source_path": "config/documents/sources.yaml",
                "metadata": {
                    "source_id": source.id,
                    "source_type": "shared",
                    "provider": source.provider,
                    "attached_brain_ids": ",".join(source.attached_brain_ids),
                    "index_status": status,
                    "catalog_summary": summary,
                    "catalog_title": getattr(source, "catalog_title", ""),
                    "remote_id": getattr(source, "source_remote_id", ""),
                    "remote_revision": getattr(source, "remote_revision", ""),
                    "remote_modified_at": getattr(source, "remote_modified_at", ""),
                },
            }
        )
    return entries


def _document_source_config_error_entry(message: str) -> dict:
    clean_message = message.strip() or "Unable to load document source config."
    return {
        "id": "document-source-config:error",
        "title": "Document source config error",
        "name": "Document source config error",
        "description": clean_message,
        "type": "document-source-error",
        "hub": "document-source-config",
        "source_path": "config/documents/sources.yaml",
        "metadata": {
            "source_type": "shared",
            "index_status": "config_error",
            "error": clean_message,
        },
    }


def _capability_metadata_for_browse_entry(category: str, entry: dict) -> dict[str, str]:
    from src.lib.capabilities.browse_enrichment import (
        capability_metadata_for_browse_entry,
    )

    return capability_metadata_for_browse_entry(category, entry)


def _capability_collision_key(key: str) -> str:
    return f"capability{key[:1].upper()}{key[1:]}"


_CAPABILITY_AUTHORITATIVE_KEYS = {
    "ownerKind",
}


def _merge_capability_metadata(
    metadata: dict[str, str],
    capability_metadata: dict[str, str],
) -> None:
    for key, value in capability_metadata.items():
        if not value:
            continue
        if key in _CAPABILITY_AUTHORITATIVE_KEYS:
            metadata[key] = value
            continue
        if key not in metadata:
            metadata[key] = value
            continue
        if metadata[key] == value:
            continue
        metadata.setdefault(_capability_collision_key(key), value)


def _apply_capability_metadata(category: str, entry: dict, metadata: dict[str, str]) -> None:
    try:
        capability_metadata = _capability_metadata_for_browse_entry(category, entry)
    except Exception:
        metadata["capabilityStatus"] = "inventory_error"
        return

    if capability_metadata:
        _merge_capability_metadata(metadata, capability_metadata)
