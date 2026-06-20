"""Expose capability inventory policy metadata to Browse rows."""

from __future__ import annotations

import time
from typing import Any

from src.config.paths import get_project_root

from .discovery import capability_id, discover_capabilities
from .drafts import find_draft_leftovers
from .exposure_policy import CapabilityRecord, resolve_capability_records

_CATEGORY_TO_CAPABILITY_TYPE = {
    "skills": "skill",
    "mcp-servers": "mcp-server",
    "mcp-tools": "mcp-tool",
    "commands": "command",
    "scripts": "cli",
}
_CAPABILITY_ID_PREFIXES = {
    "skill",
    "mcp-server",
    "mcp-tool",
    "command",
    "workflow",
    "cli",
}
_CACHE_TTL_SECONDS = 5.0
_records_cache: dict[str, CapabilityRecord] | None = None
_records_cache_ts = 0.0
_draft_names_cache: frozenset[str] | None = None
_draft_names_cache_ts = 0.0


def _resolved_records_by_id() -> dict[str, CapabilityRecord]:
    """Return briefly cached resolved capability records keyed by id."""
    global _records_cache, _records_cache_ts

    now = time.monotonic()
    if _records_cache is not None and now - _records_cache_ts < _CACHE_TTL_SECONDS:
        return _records_cache

    records = resolve_capability_records(discover_capabilities())
    _records_cache = {record.id: record for record in records}
    _records_cache_ts = now
    return _records_cache


def _draft_leftover_names() -> frozenset[str]:
    """Return briefly cached set of draft-leftover stems (with .draft stripped)."""
    global _draft_names_cache, _draft_names_cache_ts

    now = time.monotonic()
    if _draft_names_cache is not None and now - _draft_names_cache_ts < _CACHE_TTL_SECONDS:
        return _draft_names_cache

    _draft_names_cache = frozenset(path.stem.replace(".draft", "") for path in find_draft_leftovers(get_project_root()))
    _draft_names_cache_ts = now
    return _draft_names_cache


def _entry_names(entry: dict[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in ("name", "title", "id"):
        value = str(entry.get(key) or "").strip()
        if value:
            values.append(value)
    return tuple(dict.fromkeys(values))


def _skill_id_from_source_path(source_path: Any) -> str:
    normalized = str(source_path or "").strip().replace("\\", "/")
    if not normalized:
        return ""
    parts = [part for part in normalized.split("/") if part]
    for index, part in enumerate(parts):
        if part == "skills" and index + 1 < len(parts):
            return capability_id("skill", parts[index + 1])
    return ""


def _candidate_ids(category: str, entry: dict[str, Any]) -> tuple[str, ...]:
    explicit_candidates: list[str] = []
    metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
    for value in (
        entry.get("capability_id"),
        entry.get("capabilityId"),
        metadata.get("capability_id"),
        metadata.get("capabilityId"),
    ):
        candidate = str(value or "").strip()
        if candidate and candidate.split(":", 1)[0] in _CAPABILITY_ID_PREFIXES:
            explicit_candidates.append(candidate)
    if category == "integrations":
        for raw_name in _entry_names(entry):
            if raw_name.split(":", 1)[0] in _CAPABILITY_ID_PREFIXES:
                explicit_candidates.append(raw_name)
    if explicit_candidates:
        return tuple(dict.fromkeys(explicit_candidates))

    if category == "integrations":
        candidates: list[str] = []
        for value in (metadata.get("skill"), entry.get("skill")):
            skill_name = str(value or "").strip()
            if skill_name:
                candidates.append(capability_id("skill", skill_name))
        source_skill_id = _skill_id_from_source_path(entry.get("source_path") or metadata.get("source_path"))
        if source_skill_id:
            candidates.append(source_skill_id)
        cli_tools = str(metadata.get("cli_tools") or "").strip()
        for tool_name in (part.strip() for part in cli_tools.split(",")):
            if tool_name:
                candidates.append(capability_id("cli", tool_name))
        return tuple(dict.fromkeys(candidates))

    capability_type = _CATEGORY_TO_CAPABILITY_TYPE.get(category)
    if not capability_type:
        return ()

    candidates: list[str] = []
    for raw_name in _entry_names(entry):
        if raw_name.startswith(f"{capability_type}:"):
            raw_name = raw_name.split(":", 1)[1]
        name = raw_name.lstrip("/") if capability_type == "command" else raw_name
        candidates.append(capability_id(capability_type, name))
    return tuple(dict.fromkeys(candidates))


def _join(values: tuple[str, ...]) -> str:
    return ",".join(values)


def _metadata_for_record(record: CapabilityRecord) -> dict[str, str]:
    return {
        "capabilityId": record.id,
        "ownerKind": record.owner_kind,
        "management": record.management,
        "scope": record.scope,
        "sourcePaths": _join(record.source_paths),
        "primarySurface": record.primary_surface,
        "preferredClient": record.preferred_client,
        "exportTo": _join(record.export_to),
        "classificationStatus": record.classification_status,
        "currentExposure": _join(record.current_exposure),
        "drift": _join(record.drift),
    }


def _is_draft_entry(entry: dict[str, Any]) -> bool:
    """Return True when the entry name matches a known draft leftover."""
    draft_names = _draft_leftover_names()
    if not draft_names:
        return False
    for name in _entry_names(entry):
        if name in draft_names:
            return True
        # Source paths can also reveal a draft (e.g. ".../foo.draft.md")
    source_path = entry.get("source_path") or ""
    if isinstance(source_path, str) and source_path.endswith(".draft.md"):
        return True
    return False


def capability_metadata_for_browse_entry(
    category: str,
    entry: dict[str, Any],
) -> dict[str, str]:
    """Return resolved capability metadata for a Browse category entry."""
    is_draft = _is_draft_entry(entry)
    candidate_ids = _candidate_ids(category, entry)
    if not candidate_ids:
        return {"isDraft": "true"} if is_draft else {}

    records_by_id = _resolved_records_by_id()
    for candidate_id in candidate_ids:
        record = records_by_id.get(candidate_id)
        if record is not None:
            metadata = _metadata_for_record(record)
            if is_draft:
                metadata["isDraft"] = "true"
            return metadata
    return {"isDraft": "true"} if is_draft else {}
