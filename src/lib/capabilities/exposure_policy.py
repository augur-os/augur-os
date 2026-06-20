"""Capability exposure policy resolver.

Discovery records describe current state. The policy overlay describes intent.
The resolver merges both into records that Browse and generators can consume.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

import yaml

from src.config.paths import get_project_root

CapabilityType = Literal["skill", "mcp-server", "mcp-tool", "command", "workflow", "cli"]
OwnerKind = Literal["augur", "external", "adopted", "user"]
Management = Literal["generated", "managed-policy", "unmanaged"]
Scope = Literal["project", "user", "global", "mixed"]
ClassificationStatus = Literal["approved", "unclassified", "deprecated", "blocked"]

_VALID_TYPES = {"skill", "mcp-server", "mcp-tool", "command", "workflow", "cli"}
_VALID_OWNERS = {"augur", "external", "adopted", "user"}
_VALID_MANAGEMENT = {"generated", "managed-policy", "unmanaged"}
_VALID_SCOPES = {"project", "user", "global", "mixed"}
_VALID_STATUSES = {"approved", "unclassified", "deprecated", "blocked"}
_AI_CLIENT_TARGETS = {"claude", "codex", "gemini", "opencode", "cursor", "copilot"}
_POLICY_FIELDS = {
    "type",
    "owner_kind",
    "management",
    "scope",
    "primary_surface",
    "preferred_client",
    "export_to",
    "classification_status",
    "multi_client_approved",
}


@dataclass(frozen=True)
class CapabilityDiscovery:
    id: str
    type: CapabilityType
    owner_kind: OwnerKind = "augur"
    management: Management = "generated"
    scope: Scope = "project"
    source_paths: tuple[str, ...] = ()
    current_exposure: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityRecord:
    id: str
    type: CapabilityType
    owner_kind: OwnerKind
    management: Management
    scope: Scope
    primary_surface: str
    preferred_client: str
    export_to: tuple[str, ...]
    classification_status: ClassificationStatus
    source_paths: tuple[str, ...]
    current_exposure: tuple[str, ...]
    drift: tuple[str, ...]
    metadata: dict[str, str] = field(default_factory=dict)
    multi_client_approved: bool = False


def capability_policy_path(project_root: Path | None = None) -> Path:
    root = project_root or get_project_root()
    return root / "config" / "system" / "capability_exposure.yaml"


@functools.lru_cache(maxsize=8)
def _load_capability_policy_cached(path_str: str, _mtime: float, _size: int) -> dict[str, Any]:
    """Parse a capability policy file, memoized by path + (mtime, size).

    ``capability_exposure.yaml`` is ~200 KB / ~8.8k lines, and the runtime
    MCP tool filter resolves it once per tool registration (hundreds of times
    at server startup). Parsing it fresh every call cost ~45s of pure YAML
    scanning and blew past the MCP client's 30s startup timeout. The
    ``(mtime, size)`` key auto-invalidates whenever the file changes, so a
    config sync is still picked up without a manual reset.

    The returned dict is shared across callers and must be treated as
    read-only; all current callers only read ``.get("capabilities")``.
    """
    raw = yaml.safe_load(Path(path_str).read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return {"version": 1, "capabilities": {}}

    if not isinstance(raw.get("capabilities"), dict):
        raw["capabilities"] = {}
    raw.setdefault("version", 1)
    return raw


def load_capability_policy(path: Path | None = None) -> dict[str, Any]:
    policy_path = path or capability_policy_path()
    try:
        stat = policy_path.stat()
    except OSError:
        return {"version": 1, "capabilities": {}}

    return _load_capability_policy_cached(str(policy_path), stat.st_mtime, stat.st_size)


def reset_capability_policy_cache() -> None:
    """Clear the memoized capability policy parse (test/sync hook)."""
    _load_capability_policy_cached.cache_clear()


def _clean_list(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        values = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        values = [str(part).strip() for part in value]
    else:
        values = []
    return tuple(dict.fromkeys(item for item in values if item))


def _choice(value: Any, default: str, valid: set[str]) -> str:
    candidate = str(value or "").strip()
    return candidate if candidate in valid else default


def _record_drift(
    *,
    classification_status: str,
    export_to: tuple[str, ...],
    current_exposure: tuple[str, ...],
) -> tuple[str, ...]:
    current = set(current_exposure)
    intended = set(export_to)
    current_ai_clients = current & _AI_CLIENT_TARGETS
    intended_ai_clients = intended & _AI_CLIENT_TARGETS
    drift: list[str] = []

    if len(current_ai_clients) > 1 and current_ai_clients != intended_ai_clients:
        drift.append("duplicate")
    if classification_status == "unclassified" and current:
        drift.append("unclassified_export")
    if classification_status in {"approved", "deprecated", "blocked"}:
        if current - intended:
            drift.append("unexpected_client")
        if classification_status == "approved" and intended - current:
            drift.append("missing_expected_export")

    return tuple(drift)


def resolve_capability_records(
    discovered: list[CapabilityDiscovery],
    *,
    policy: dict[str, Any] | None = None,
    active_tiers: set[str] | None = None,
) -> list[CapabilityRecord]:
    loaded_policy = policy if policy is not None else load_capability_policy()
    policy_entries = loaded_policy.get("capabilities") or {}
    if not isinstance(policy_entries, dict):
        policy_entries = {}
    active = _normalize_active_tiers(active_tiers)

    records: list[CapabilityRecord] = []
    for item in discovered:
        overlay = policy_entries.get(item.id) or {}
        if not isinstance(overlay, dict):
            overlay = {}

        owner_kind = _choice(overlay.get("owner_kind"), item.owner_kind, _VALID_OWNERS)
        management = _choice(overlay.get("management"), item.management, _VALID_MANAGEMENT)
        scope = _choice(overlay.get("scope"), item.scope, _VALID_SCOPES)
        if not _scope_is_active(scope, active):
            continue
        classification_status = _choice(
            overlay.get("classification_status"),
            "unclassified",
            _VALID_STATUSES,
        )
        capability_type = _choice(overlay.get("type"), item.type, _VALID_TYPES)
        primary_surface = str(overlay.get("primary_surface") or item.metadata.get("primary_surface") or capability_type)
        preferred_client = str(overlay.get("preferred_client") or item.metadata.get("preferred_client") or "none")
        export_to = _clean_list(overlay.get("export_to"))
        current_exposure = _clean_list(item.current_exposure)
        source_paths = _clean_list(item.source_paths)
        multi_client_approved = bool(overlay.get("multi_client_approved", False))
        drift = _record_drift(
            classification_status=classification_status,
            export_to=export_to,
            current_exposure=current_exposure,
        )
        metadata = {str(key): str(value) for key, value in item.metadata.items() if value is not None}
        for key, value in overlay.items():
            if key not in _POLICY_FIELDS and value is not None:
                metadata[str(key)] = str(value)

        records.append(
            CapabilityRecord(
                id=item.id,
                type=cast(CapabilityType, capability_type),
                owner_kind=cast(OwnerKind, owner_kind),
                management=cast(Management, management),
                scope=cast(Scope, scope),
                primary_surface=primary_surface,
                preferred_client=preferred_client,
                export_to=export_to,
                classification_status=cast(ClassificationStatus, classification_status),
                source_paths=source_paths,
                current_exposure=current_exposure,
                drift=drift,
                metadata=metadata,
                multi_client_approved=multi_client_approved,
            )
        )

    return sorted(records, key=lambda record: record.id)


def _normalize_active_tiers(active_tiers: set[str] | None) -> set[str]:
    if active_tiers is None:
        return _default_active_tiers()
    return _expand_tier_aliases(active_tiers)


def _default_active_tiers() -> set[str]:
    try:
        from src.lib.brain_stack import resolve_active_stack

        return _expand_tier_aliases(
            brain.type.value for brain in resolve_active_stack(cwd=get_project_root()).ordered()
        )
    except Exception:
        return {"global", "user", "project"}


def _expand_tier_aliases(tiers: Any) -> set[str]:
    normalized: set[str] = set()
    for tier in tiers:
        value = str(tier).strip().lower()
        if not value:
            continue
        normalized.add(value)
        if value == "personal":
            normalized.add("user")
    return normalized


def _scope_is_active(scope: str, active_tiers: set[str]) -> bool:
    if scope == "mixed":
        return True
    return scope in active_tiers


def export_allowed(record: CapabilityRecord, target: str, *, existing: bool = False) -> bool:
    """Return whether a generated export may be written for target."""
    if record.classification_status == "blocked":
        return False
    if record.classification_status == "unclassified":
        return existing and target in record.current_exposure
    if record.classification_status == "deprecated":
        return existing and target in record.current_exposure
    return target in record.export_to
