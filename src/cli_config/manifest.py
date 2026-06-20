"""Manifest loader and validator for config/system/mcp_servers.yaml."""

from __future__ import annotations

import platform
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml

from src.logging import get_entity_logger

logger = get_entity_logger("cli_config.manifest")

_KNOWN_CLIENTS = frozenset({"claude", "codex", "gemini", "copilot"})
_MCP_CONFIG_CLIENTS = (
    "claude",
    "codex",
    "gemini",
    "cursor",
    "windsurf",
    "copilot",
    "opencode",
    "antigravity",
    "cline",
    "perplexity",
    "generic",
    "cowork",
)
_KNOWN_PLATFORMS = frozenset({"darwin", "linux", "windows"})
_CLIENT_ALIASES = {
    "claude-code": "claude",
    "claude_code": "claude",
}
_MCP_CONFIG_TARGET = "mcp-config"
_PLATFORM_ALIASES = {
    "mac": "darwin",
    "macos": "darwin",
    "osx": "darwin",
    "win": "windows",
    "win32": "windows",
}


@dataclass(frozen=True)
class ServerEntry:
    """One MCP server in the manifest (project-tier or vault-tier)."""

    id: str
    description: str
    command: str
    args: list[str]
    cwd_required: bool = False
    env: dict[str, str] = field(default_factory=dict)
    bundle: str | None = None  # Set for vault_tier entries.
    bundle_path: str | None = None  # Set for vault_tier entries.
    per_client_args: dict[str, list[str]] = field(default_factory=dict)
    platforms: list[str] = field(default_factory=list)
    startup_timeout_sec: int | None = None
    # Direct construction has no tier context; YAML loading applies tier-aware defaults.
    scope: str = "global"

    def supports_platform(self, platform_name: str | None = None) -> bool:
        """Return true when this server should be registered on the platform."""
        if not self.platforms:
            return True
        return _normalize_platform(platform_name) in self.platforms


@dataclass(frozen=True)
class Manifest:
    """Parsed config/system/mcp_servers.yaml."""

    project_tier: list[ServerEntry]
    vault_tier: list[ServerEntry]
    monolith_exclusions: list[str]
    policy_path: Path | None = None

    def all_augur_servers(self, platform_name: str | None = None) -> list[ServerEntry]:
        """Both project- and vault-tier servers supported by the platform."""
        return [entry for entry in [*self.project_tier, *self.vault_tier] if entry.supports_platform(platform_name)]

    def all_augur_servers_for_client(
        self,
        client: str,
        platform_name: str | None = None,
        existing_server_ids: set[str] | None = None,
        include_project_scoped: bool = False,
    ) -> list[ServerEntry]:
        """Return server entries allowed for a generated client config."""
        entries = [
            entry
            for entry in self.all_augur_servers(platform_name)
            if include_project_scoped or entry.scope != "project"
        ]
        target = _normalize_client(client)
        has_policy_file = self.policy_path is not None and self.policy_path.exists()
        if not has_policy_file:
            existing_ids = {entry.id for entry in entries}
        elif existing_server_ids is None:
            existing_ids = set()
        else:
            existing_ids = {str(server_id) for server_id in existing_server_ids}
        try:
            policy = load_capability_policy(self.policy_path) if self.policy_path is not None else None
            records = {
                record.id: record
                for record in resolve_capability_records(
                    _discover_mcp_server_capabilities_from_entries(entries),
                    policy=policy,
                )
            }
        except Exception:
            logger.warning(
                "MCP server capability policy resolution failed for %s; " "preserving existing generated exports only",
                target,
                exc_info=True,
            )
            if has_policy_file:
                return [entry for entry in entries if entry.id in existing_ids]
            return entries

        allowed: list[ServerEntry] = []
        for entry in entries:
            record = records.get(f"mcp-server:{entry.id}")
            if record is None:
                allowed.append(entry)
                continue

            normalized_record = _normalize_record_clients(record)
            existing = entry.id in existing_ids
            if existing and target not in normalized_record.current_exposure:
                normalized_record.current_exposure = tuple(dict.fromkeys((*normalized_record.current_exposure, target)))
            if any(
                export_allowed(normalized_record, policy_target, existing=existing)
                for policy_target in _mcp_server_policy_targets(target)
            ):
                allowed.append(entry)
        return allowed


def _discover_mcp_server_capabilities_from_entries(
    entries: list[ServerEntry],
) -> list[Any]:
    """Discover MCP server capability records from this manifest instance."""
    from src.lib.capabilities.exposure_policy import CapabilityDiscovery

    records: list[Any] = []
    for entry in entries:
        bundle = str(entry.bundle or "")
        bundle_path = str(entry.bundle_path or "")
        source_paths = ["config/system/mcp_servers.yaml"]
        if bundle_path:
            source_paths.append(bundle_path)

        records.append(
            CapabilityDiscovery(
                id=f"mcp-server:{entry.id}",
                type="mcp-server",
                owner_kind="augur",
                management="generated",
                scope=entry.scope,
                source_paths=tuple(source_paths),
                current_exposure=("mcp-config",),
                metadata={
                    "tier": "vault" if bundle or bundle_path else "project",
                    "bundle": bundle,
                    "bundle_path": bundle_path,
                    "primary_surface": "mcp",
                },
            )
        )
    return records


def load_capability_policy(path: Path | None = None) -> dict[str, Any]:
    """Load capability policy without importing policy code eagerly."""
    from src.lib.capabilities.exposure_policy import load_capability_policy as load

    return load(path)


def resolve_capability_records(
    discovered: list[Any],
    *,
    policy: dict[str, Any] | None = None,
) -> list[Any]:
    """Resolve capability records without importing policy eagerly."""
    from src.lib.capabilities.exposure_policy import resolve_capability_records as resolve

    if policy is None:
        return resolve(discovered)
    return resolve(discovered, policy=policy)


def export_allowed(record: Any, target: str, *, existing: bool = False) -> bool:
    """Return whether a capability record may export to a target."""
    from src.lib.capabilities.exposure_policy import export_allowed as allowed

    return allowed(record, target, existing=existing)


def _normalize_client(client: str) -> str:
    cleaned = str(client or "").strip().lower()
    return _CLIENT_ALIASES.get(cleaned, cleaned)


def _mcp_server_policy_targets(client: str) -> tuple[str, ...]:
    """Return accepted policy targets for generated MCP server configs."""
    target = _normalize_client(client)
    if target == _MCP_CONFIG_TARGET:
        return (_MCP_CONFIG_TARGET,)
    return (target, _MCP_CONFIG_TARGET)


def _normalize_clients(values: Any) -> tuple[str, ...]:
    if isinstance(values, str):
        raw_values = [values]
    elif isinstance(values, (list, tuple, set)):
        raw_values = list(values)
    else:
        raw_values = []
    return tuple(dict.fromkeys(_normalize_client(str(value)) for value in raw_values))


def _normalize_record_clients(record: Any) -> SimpleNamespace:
    current_exposure = _normalize_clients(getattr(record, "current_exposure", ()))
    export_to = _normalize_clients(getattr(record, "export_to", ()))
    if "mcp-config" in export_to:
        export_to = tuple(dict.fromkeys((*export_to, *_MCP_CONFIG_CLIENTS)))
    if "mcp-config" in current_exposure:
        current_exposure = tuple(dict.fromkeys((*current_exposure, *_MCP_CONFIG_CLIENTS)))
    return SimpleNamespace(
        classification_status=getattr(record, "classification_status", "unclassified"),
        export_to=export_to,
        current_exposure=current_exposure,
    )


def load_manifest(path: Path | None = None) -> Manifest:
    """Load and validate config/system/mcp_servers.yaml.

    Args:
        path: Override path (used by tests). Defaults to the canonical
            project-relative location.

    Raises:
        FileNotFoundError: if the manifest doesn't exist.
        ValueError: if any entry is malformed.
    """
    if path is None:
        from src.config.paths import get_project_root

        path = get_project_root() / "config" / "system" / "mcp_servers.yaml"

    if not path.exists():
        raise FileNotFoundError(f"Manifest not found at {path}")

    raw = yaml.safe_load(path.read_text()) or {}
    return _build_manifest(raw, policy_path=path.parent / "capability_exposure.yaml")


def _build_manifest(
    raw: dict[str, Any],
    *,
    policy_path: Path | None = None,
) -> Manifest:
    project_tier = [_build_entry(e, tier="project") for e in raw.get("project_tier", []) or []]
    vault_tier = [_build_entry(e, tier="vault") for e in raw.get("vault_tier", []) or []]
    monolith_exclusions = list(raw.get("monolith_exclusions", []) or [])

    _validate_unique_ids(project_tier + vault_tier)
    _validate_vault_entries(vault_tier)
    _validate_exclusions_against_vault(monolith_exclusions, vault_tier)

    return Manifest(
        project_tier=project_tier,
        vault_tier=vault_tier,
        monolith_exclusions=monolith_exclusions,
        policy_path=policy_path,
    )


def _build_entry(raw: dict[str, Any], tier: str) -> ServerEntry:
    required = {"id", "command", "args"}
    missing = required - set(raw.keys())
    if missing:
        raise ValueError(f"{tier}_tier entry missing required fields: {sorted(missing)}; raw={raw!r}")
    if not isinstance(raw["args"], list):
        raise ValueError(f"args must be a list; got {type(raw['args']).__name__}; raw={raw!r}")
    per_client_args = _parse_per_client_args(raw.get("per_client_args"), raw)
    platforms = _parse_platforms(raw.get("platforms"), raw)
    startup_timeout_sec = _parse_startup_timeout(raw.get("startup_timeout_sec"), raw)
    scope = _parse_scope(raw.get("scope"), tier, raw)
    return ServerEntry(
        id=str(raw["id"]),
        description=str(raw.get("description", "")),
        command=str(raw["command"]),
        args=[str(a) for a in raw["args"]],
        cwd_required=bool(raw.get("cwd_required", False)),
        env={str(k): str(v) for k, v in (raw.get("env") or {}).items()},
        bundle=raw.get("bundle"),
        bundle_path=raw.get("bundle_path"),
        per_client_args=per_client_args,
        platforms=platforms,
        startup_timeout_sec=startup_timeout_sec,
        scope=scope,
    )


def _normalize_platform(platform_name: str | None = None) -> str:
    name = platform_name or platform.system()
    key = str(name).strip().lower()
    return _PLATFORM_ALIASES.get(key, key)


def _parse_platforms(value: Any, raw: dict[str, Any]) -> list[str]:
    """Validate and parse optional platform allow-list."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"platforms must be a list; got {type(value).__name__}; raw={raw!r}")
    platforms = [_normalize_platform(str(item)) for item in value]
    unknown = sorted(set(platforms) - _KNOWN_PLATFORMS)
    if unknown:
        raise ValueError(
            f"platforms contains unknown value(s) {unknown}; "
            f"expected one of {sorted(_KNOWN_PLATFORMS)}; raw={raw!r}"
        )
    return platforms


def _parse_startup_timeout(value: Any, raw: dict[str, Any]) -> int | None:
    """Validate optional Codex MCP startup timeout seconds."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("startup_timeout_sec must be a positive integer; " f"got {value!r}; raw={raw!r}")
    return value


def _parse_scope(value: Any, tier: str, raw: dict[str, Any]) -> str:
    """Validate optional MCP server scope."""
    default = "project" if tier == "project" else "global"
    if value is None:
        return default
    scope = str(value).strip().lower()
    if scope not in {"global", "user", "project"}:
        raise ValueError(f"scope must be one of ['global', 'project', 'user']; got {value!r}; raw={raw!r}")
    return scope


def _parse_per_client_args(value: Any, raw: dict[str, Any]) -> dict[str, list[str]]:
    """Validate and parse the optional per_client_args field.

    Defaults to an empty dict when absent. When present, must be a dict
    mapping a known client name (one of "claude", "codex", "gemini",
    "copilot") to a list of strings.
    """
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"per_client_args must be a dict; got {type(value).__name__}; raw={raw!r}")
    out: dict[str, list[str]] = {}
    for client, args in value.items():
        client_name = str(client)
        if client_name not in _KNOWN_CLIENTS:
            raise ValueError(
                f"per_client_args contains unknown client {client_name!r}; "
                f"expected one of {sorted(_KNOWN_CLIENTS)}; raw={raw!r}"
            )
        if not isinstance(args, list):
            raise ValueError(
                f"per_client_args[{client_name!r}] must be a list; " f"got {type(args).__name__}; raw={raw!r}"
            )
        out[client_name] = [str(a) for a in args]
    return out


def _validate_unique_ids(entries: list[ServerEntry]) -> None:
    seen: set[str] = set()
    for e in entries:
        if e.id in seen:
            raise ValueError(f"Duplicate server id in manifest: {e.id!r}")
        seen.add(e.id)


def _validate_vault_entries(vault_tier: list[ServerEntry]) -> None:
    for e in vault_tier:
        if not e.id.startswith("augur-"):
            raise ValueError(f"vault_tier entry id must start with 'augur-'; got {e.id!r}")
        if not e.bundle:
            raise ValueError(f"vault_tier entry {e.id!r} missing 'bundle' field")
        if not e.bundle_path:
            raise ValueError(f"vault_tier entry {e.id!r} missing 'bundle_path' field")


def _validate_exclusions_against_vault(exclusions: list[str], vault_tier: list[ServerEntry]) -> None:
    """Every monolith exclusion must correspond to a vault_tier entry."""
    vault_bundles = {e.bundle for e in vault_tier if e.bundle}
    extra = set(exclusions) - vault_bundles
    if extra:
        raise ValueError(f"monolith_exclusions contains bundle(s) without vault_tier entry: {sorted(extra)}")
