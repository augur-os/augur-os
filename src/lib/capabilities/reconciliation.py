"""Serializable capability reconciliation reports."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any

from .exposure_policy import CapabilityRecord

_CANONICAL_MCP_TOOL_SURFACES = ["cli", "mcp", "mcp via dashboard"]


def build_capability_report(records: list[CapabilityRecord]) -> dict[str, Any]:
    """Build a deterministic JSON-serializable report from resolved records."""
    sorted_records = sorted(records, key=lambda record: record.id)
    return {
        "counts": _counts(sorted_records),
        "duplicate_clusters": [
            {
                "id": record.id,
                "type": record.type,
                "owner_kind": record.owner_kind,
                "current_exposure": list(record.current_exposure),
            }
            for record in sorted_records
            if "duplicate" in record.drift
        ],
        "records": [_serialize_record(record) for record in sorted_records],
    }


def _counts(records: list[CapabilityRecord]) -> dict[str, Any]:
    return {
        "total": len(records),
        "by_type": _sorted_counter(record.type for record in records),
        "by_owner": _sorted_counter(record.owner_kind for record in records),
        "by_management": _sorted_counter(record.management for record in records),
        "by_status": _sorted_counter(record.classification_status for record in records),
        "by_drift": _sorted_counter(drift for record in records for drift in record.drift),
        "gemini_exposed": sum(1 for record in records if "gemini" in record.current_exposure),
        "opencode_exposed": sum(1 for record in records if "opencode" in record.current_exposure),
    }


def _sorted_counter(values: Iterable[Any]) -> dict[str, int]:
    counts = Counter(str(value) for value in values)
    return {key: counts[key] for key in sorted(counts)}


def _serialize_record(record: CapabilityRecord) -> dict[str, Any]:
    serialized: dict[str, Any] = {
        "id": record.id,
        "type": record.type,
        "owner_kind": record.owner_kind,
        "management": record.management,
        "scope": record.scope,
        "primary_surface": record.primary_surface,
        "preferred_client": record.preferred_client,
        "export_to": list(record.export_to),
        "classification_status": record.classification_status,
        "source_paths": list(record.source_paths),
        "current_exposure": list(record.current_exposure),
        "drift": list(record.drift),
        "metadata": dict(sorted(record.metadata.items())),
    }
    recommended_action = _recommended_action(record)
    if recommended_action is not None:
        serialized["recommended_action"] = recommended_action
    return serialized


def _recommended_action(record: CapabilityRecord) -> dict[str, Any] | None:
    if record.primary_surface not in _CANONICAL_MCP_TOOL_SURFACES and record.type == "mcp-tool":
        return {
            "id": "fix_primary_surface",
            "label": "Use canonical primary surface",
            "params": {"allowed": _CANONICAL_MCP_TOOL_SURFACES},
        }
    if (
        record.owner_kind == "user"
        and record.type == "mcp-tool"
        and record.classification_status == "unclassified"
        and "mcp" in record.current_exposure
    ):
        return {
            "id": "review_private_skill_policy",
            "label": "Review private skill policy",
            "params": {
                "suggested_primary_surface": "cli",
                "requires_approval": True,
            },
        }
    if (
        record.type == "skill"
        and record.owner_kind == "external"
        and "duplicate" in record.drift
        and ("geo" in record.id.lower() or "location" in record.id.lower())
    ):
        return {
            "id": "keep_only_in_client",
            "label": "Keep only in Claude",
            "params": {"target_client": "claude"},
        }
    if record.owner_kind == "augur" and record.management == "generated" and record.type == "mcp-tool":
        return {
            "id": "move_to_cli_only",
            "label": "Move to CLI only",
            "params": {},
        }
    if record.classification_status == "unclassified" and record.current_exposure:
        return {
            "id": "review_policy",
            "label": "Review exposure policy",
            "params": {},
        }
    return None
