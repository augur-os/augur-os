"""
capabilities._discovery_helpers — Shared helpers for capability discovery.

Small utility functions used by multiple discovery collectors:
capability_id, exposure/scope/owner helpers, policy helpers, merge logic.

Internal use by the capabilities package; do not import directly from outside.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .exposure_policy import (
    CapabilityDiscovery,
    OwnerKind,
    Scope,
    Management,
)

import re

_AI_CLIENT_EXPOSURE_TARGETS = frozenset({"claude", "codex", "gemini", "opencode", "cursor", "copilot"})


def capability_id(capability_type: str, raw_name: str) -> str:
    """Return a stable capability id for a type and display/source name."""
    normalized = re.sub(r"[^a-z0-9]+", "-", str(raw_name).strip().lower()).strip("-")
    return f"{capability_type}:{normalized}"


def _client_from_source(source: str) -> str:
    cleaned = source.strip().lower()
    if not cleaned:
        return ""
    for client in ("claude", "codex", "gemini", "opencode", "cursor", "copilot"):
        if cleaned == client or cleaned.startswith(f"{client}-"):
            return client
    return ""


def _exposure_from_sources(sources: Iterable[Any]) -> tuple[str, ...]:
    clients = (_client_from_source(str(source)) for source in sources)
    return tuple(dict.fromkeys(client for client in clients if client in _AI_CLIENT_EXPOSURE_TARGETS))


def _scope_from_sources(sources: Iterable[Any]) -> Scope:
    tags = [str(source).strip().lower() for source in sources if str(source).strip()]
    has_global = any("global" in tag for tag in tags)
    has_project = any("local" in tag or "project" in tag for tag in tags)
    if has_global and has_project:
        return "mixed"
    if has_global:
        return "global"
    return "project"


def _owner_kind(ownership: Any) -> OwnerKind:
    value = str(ownership or "augur").strip().lower()
    if value == "external":
        return "external"
    if value == "user":
        return "user"
    if value == "adopted":
        return "adopted"
    return "augur"


def _management(source_root: Any) -> Management:
    value = str(source_root or "").strip().lower()
    if value in {"external-client", "plugin-cache"}:
        return "unmanaged"
    return "generated"


def _policy_list(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        raw_values = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        raw_values = [str(part).strip() for part in value]
    else:
        raw_values = []
    return tuple(dict.fromkeys(item for item in raw_values if item))


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _declared_cli_names(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        items: Iterable[Any] = value.split(",")
    elif isinstance(value, list):
        items = value
    else:
        return ()
    names: list[str] = []
    for item in items:
        if isinstance(item, dict):
            raw_name = item.get("name") or item.get("id")
        else:
            raw_name = item
        name = str(raw_name or "").strip()
        if name:
            names.append(name)
    return names


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _path_for_source(py_file: Path, root: Path | None) -> str:
    if root is not None:
        try:
            return str(py_file.relative_to(root))
        except ValueError:
            pass
    return str(py_file)


def _unique_items(*groups: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item for group in groups for item in group if item))


def _metadata_values(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _merge_metadata(
    existing: dict[str, str],
    incoming: dict[str, str],
) -> dict[str, str]:
    metadata = dict(existing)
    for key, value in incoming.items():
        if not value:
            continue
        if key == "primary_surface":
            metadata.setdefault(key, value)
            continue
        if key == "skill":
            metadata[key] = ",".join(
                _unique_items(
                    _metadata_values(metadata.get(key, "")),
                    _metadata_values(value),
                )
            )
            continue
        if key not in metadata:
            metadata[key] = value
        elif metadata[key] != value:
            metadata[key] = ",".join(
                _unique_items(
                    _metadata_values(metadata[key]),
                    _metadata_values(value),
                )
            )
    return metadata


def _merge_capability_records(
    records: Iterable[CapabilityDiscovery],
) -> list[CapabilityDiscovery]:
    merged: dict[str, CapabilityDiscovery] = {}
    for record in records:
        existing = merged.get(record.id)
        if existing is None:
            merged[record.id] = record
            continue
        merged[record.id] = CapabilityDiscovery(
            id=existing.id,
            type=existing.type,
            owner_kind=existing.owner_kind,
            management=existing.management,
            scope=existing.scope,
            source_paths=_unique_items(existing.source_paths, record.source_paths),
            current_exposure=_unique_items(
                existing.current_exposure,
                record.current_exposure,
            ),
            metadata=_merge_metadata(existing.metadata, record.metadata),
        )
    return sorted(merged.values(), key=lambda item: item.id)
