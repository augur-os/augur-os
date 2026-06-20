from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_config_dir, get_documents_dir, get_runtime_dir, get_vault_dir

from skills.ingest.scripts.inbox_unified_models import (
    InboxSourceLane,
    InboxVaultCandidate,
    InboxVaultTarget,
    UnifiedInboxRegistry,
    to_dict,
)


def inbox_config_root() -> Path:
    return get_runtime_dir() / "brain" / "inbox" / "config"


def _repo_defaults_path() -> Path:
    return get_config_dir() / "system" / "inbox.yaml"


def _read_yaml(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if data is not None else default


def _write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def _resolve_config_path(value: str) -> str:
    if value.startswith("documents/"):
        return str(get_documents_dir() / value.removeprefix("documents/"))
    return str(Path(value).expanduser().resolve(strict=False))


def _default_personal_vault() -> InboxVaultTarget:
    return InboxVaultTarget(
        id="personal",
        kind="private",
        name="Personal",
        vault_root=str(get_vault_dir()),
        docs_root=str(get_documents_dir()),
        default=True,
        writable=True,
    )


def _source_from_config(raw: dict[str, Any]) -> InboxSourceLane:
    lane_id = str(raw["id"])
    root_values = raw.get("filesystem_roots") or []
    configured_path = raw.get("path")
    configured_drop_root = raw.get("drop_root")
    if configured_drop_root:
        drop_root = _resolve_config_path(str(configured_drop_root))
    elif configured_path:
        drop_root = _resolve_config_path(str(configured_path))
    elif root_values:
        drop_root = _resolve_config_path(str(root_values[0]))
    else:
        drop_root = str(get_documents_dir() / "inbox" / lane_id)

    allowed = [str(item) for item in raw.get("allowed_targets") or ["personal"]]
    return InboxSourceLane(
        id=lane_id,
        type=str(raw.get("type") or "watched_folder"),
        name=str(raw.get("name") or lane_id.replace("-", " ").title()),
        domain=str(raw.get("domain") or "auto"),
        drop_root=drop_root,
        write_modes=[str(item) for item in raw.get("write_modes") or []],
        default_target_vault=str(raw.get("default_target_vault") or "personal"),
        allowed_targets=allowed,
        enabled=bool(raw.get("enabled", True)),
        health_state=str(raw.get("health_state") or "ready"),
        health_error=str(raw.get("health_error") or ""),
    )


def _source_with_target_health(
    source: InboxSourceLane,
    vault_ids: set[str],
) -> InboxSourceLane:
    referenced_ids = [source.default_target_vault, *source.allowed_targets]
    missing_ids = sorted({vault_id for vault_id in referenced_ids if vault_id not in vault_ids})
    if not missing_ids:
        return replace(source, health_state="ready", health_error="")
    return replace(
        source,
        health_state="needs_target",
        health_error=f"Missing inbox target vault id(s): {', '.join(missing_ids)}",
    )


def _merge_source_config(default_raw: dict[str, Any], override_raw: dict[str, Any]) -> dict[str, Any]:
    merged = dict(default_raw)
    merged.update(override_raw)
    return merged


def _default_sources_by_id() -> dict[str, dict[str, Any]]:
    defaults = _read_yaml(_repo_defaults_path(), {})
    return {
        str(raw["id"]): raw
        for raw in defaults.get("default_sources", [])
    }


def load_discovery_config() -> dict[str, Any]:
    defaults = _read_yaml(_repo_defaults_path(), {})
    raw = defaults.get("discovery") or {}
    marker_files = raw.get("marker_files") or [".augur/vault.yaml"]
    approved_parent_roots = raw.get("approved_parent_roots") or []
    return {
        "marker_files": [str(item) for item in marker_files],
        "approved_parent_roots": [str(item) for item in approved_parent_roots],
        "max_depth": int(raw.get("max_depth", 3)),
    }


def _runtime_source_payload(
    source: InboxSourceLane,
    default_raw: dict[str, Any] | None,
) -> dict[str, Any]:
    if default_raw is None:
        payload = to_dict(source)
        payload.pop("health_state", None)
        payload.pop("health_error", None)
        return payload

    default_source = _source_from_config(default_raw)
    payload: dict[str, Any] = {"id": source.id}
    for field_name in (
        "type",
        "name",
        "domain",
        "drop_root",
        "write_modes",
        "default_target_vault",
        "allowed_targets",
        "enabled",
    ):
        if getattr(source, field_name) != getattr(default_source, field_name):
            payload[field_name] = to_dict(getattr(source, field_name))
    return payload


def _canonical_runtime_source_payload(
    raw: dict[str, Any],
    default_sources_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    lane_id = str(raw["id"])
    default_raw = default_sources_by_id.get(lane_id)
    source_config = _merge_source_config(default_raw or {}, raw)
    source = _source_from_config(source_config)
    return _runtime_source_payload(source, default_raw)


def load_inbox_registry() -> UnifiedInboxRegistry:
    config_root = inbox_config_root()
    user_vaults = _read_yaml(config_root / "vaults.yaml", {}).get("vaults", [])
    user_sources = _read_yaml(config_root / "sources.yaml", {}).get("sources", [])
    candidates = _read_yaml(config_root / "discovered.yaml", {}).get("candidates", [])

    vaults = [_default_personal_vault()]
    for raw in user_vaults:
        target = InboxVaultTarget(**raw)
        if target.id == "personal":
            vaults[0] = target
        else:
            vaults.append(target)

    vault_ids = {vault.id for vault in vaults}
    sources_by_id: dict[str, InboxSourceLane] = {}
    default_sources_by_id = _default_sources_by_id()
    for raw in default_sources_by_id.values():
        source = _source_from_config(raw)
        sources_by_id[source.id] = _source_with_target_health(source, vault_ids)
    for raw in user_sources:
        lane_id = str(raw["id"])
        source_config = _merge_source_config(default_sources_by_id.get(lane_id, {}), raw)
        source = _source_from_config(source_config)
        sources_by_id[source.id] = _source_with_target_health(source, vault_ids)

    return UnifiedInboxRegistry(
        config_root=config_root,
        sources=list(sources_by_id.values()),
        vaults=vaults,
        candidates=[InboxVaultCandidate(**raw) for raw in candidates],
    )


def register_vault_target(target: InboxVaultTarget) -> InboxVaultTarget:
    registry = load_inbox_registry()
    saved_target = replace(target, writable=True)
    targets = [item for item in registry.vaults if item.id != saved_target.id]
    targets.append(saved_target)
    mutable_targets = [item for item in targets if item.id != "personal"]
    _write_yaml(registry.config_root / "vaults.yaml", {"vaults": to_dict(mutable_targets)})
    return saved_target


def register_source_lane(source: InboxSourceLane) -> InboxSourceLane:
    config_root = inbox_config_root()
    user_sources = _read_yaml(config_root / "sources.yaml", {}).get("sources", [])
    saved_source = _source_from_config(to_dict(source))
    default_sources_by_id = _default_sources_by_id()
    sources = [
        _canonical_runtime_source_payload(raw, default_sources_by_id)
        for raw in user_sources
        if str(raw.get("id")) != saved_source.id
    ]
    sources.append(
        _runtime_source_payload(
            saved_source,
            default_sources_by_id.get(saved_source.id),
        )
    )
    _write_yaml(config_root / "sources.yaml", {"sources": sources})
    return saved_source
