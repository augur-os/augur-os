"""External-integration + inventory merge/filter helpers for Browse."""

from .index_common import _AI_ARTIFACT_PROBLEM_IDS
from .index_resolve import _entry_has_existing_source_path, _resolve_local_source_path


def _external_integration_entries() -> list[dict]:
    try:
        from src.lib.external_services import external_service_browse_entries

        return external_service_browse_entries()
    except Exception:
        return []


def _merge_external_integration_entries(
    entries: list[dict],
    external_entries: list[dict],
) -> list[dict]:
    if not external_entries:
        return entries
    merged = list(entries)
    existing_ids = {str(entry.get("id") or "") for entry in merged}
    for entry in external_entries:
        entry_id = str(entry.get("id") or "")
        if entry_id and entry_id in existing_ids:
            continue
        if entry_id:
            existing_ids.add(entry_id)
        merged.append(entry)
    return merged


def _source_path_dedupe_key(entry: dict) -> str:
    source_path = entry.get("source_path")
    resolved = _resolve_local_source_path(source_path)
    if resolved is None:
        return str(source_path or "")
    try:
        return str(resolved.expanduser().resolve(strict=False))
    except OSError:
        return str(resolved.expanduser())


def _filter_missing_inventory_entries(inventory_entries: list[dict]) -> tuple[list[dict], int]:
    if not inventory_entries:
        return inventory_entries, 0
    filtered: list[dict] = []
    missing_count = 0
    for entry in inventory_entries:
        if _entry_has_existing_source_path(entry):
            filtered.append(entry)
        else:
            missing_count += 1
    return filtered, missing_count


def _merge_inventory_entries(entries: list[dict], inventory_entries: list[dict]) -> tuple[list[dict], int]:
    if not inventory_entries:
        return entries, 0
    entries_by_path = {_source_path_dedupe_key(entry): entry for entry in entries if entry.get("source_path")}
    merged = list(entries)
    added_count = 0
    for entry in inventory_entries:
        source_path_key = _source_path_dedupe_key(entry)
        if source_path_key and source_path_key in entries_by_path:
            _merge_inventory_metadata(entries_by_path[source_path_key], entry)
            continue
        merged.append(entry)
        added_count += 1
        if source_path_key:
            entries_by_path[source_path_key] = entry
    return merged, added_count


def _merge_inventory_metadata(existing: dict, inventory_entry: dict) -> None:
    inventory_metadata = inventory_entry.get("metadata")
    if not isinstance(inventory_metadata, dict):
        inventory_metadata = {}

    existing_metadata = existing.get("metadata")
    if not isinstance(existing_metadata, dict):
        existing_metadata = {}
        existing["metadata"] = existing_metadata

    stale_problem_tags = {
        item.strip() for item in str(existing_metadata.get("problem_tags") or "").split(",") if item.strip()
    }
    for key in list(existing_metadata):
        if key.startswith("problem_"):
            existing_metadata.pop(key, None)

    for key, value in inventory_metadata.items():
        if key.startswith("problem_") or key == "inventory_source":
            existing_metadata[key] = value

    if inventory_entry.get("inventory_source"):
        existing_metadata["inventory_source"] = inventory_entry["inventory_source"]
        existing["inventory_source"] = inventory_entry["inventory_source"]

    fresh_problem_tags = [
        item.strip() for item in str(inventory_metadata.get("problem_tags") or "").split(",") if item.strip()
    ]

    existing_tags = existing.get("tags")
    if not isinstance(existing_tags, list):
        existing_tags = []
    stale_inventory_problem_tags = stale_problem_tags.intersection(_AI_ARTIFACT_PROBLEM_IDS)
    existing_tags = [
        tag
        for tag in existing_tags
        if str(tag) not in stale_inventory_problem_tags and str(tag) not in _AI_ARTIFACT_PROBLEM_IDS
    ]
    existing["tags"] = existing_tags
    for tag in fresh_problem_tags:
        if tag not in existing_tags:
            existing_tags.append(tag)
