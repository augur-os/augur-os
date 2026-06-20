"""Cloud execution profiles and readiness classification for AI clients."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
from typing import Callable, Mapping, Sequence

import yaml

from src.config.paths import get_config_dir, get_project_root

SAFE_MODES = frozenset({"read", "review", "plan"})
MUTATION_MODES = frozenset({"fix", "commit", "pr"})
VALID_STATUSES = frozenset(
    {
        "ready",
        "missing-secret",
        "needs-github-app",
        "local-only",
        "disabled-by-policy",
        "unknown",
    }
)


@dataclass(frozen=True)
class LocalProfile:
    cli: str
    plugin_pack: str
    mcp_client_id: str
    config_paths: tuple[str, ...]


@dataclass(frozen=True)
class CloudProfile:
    vendor_surface: str
    execution_kind: str
    github_workflow: str | None
    default_modes: tuple[str, ...]
    mutation_modes: tuple[str, ...]
    triggers: dict[str, tuple[str, ...]]
    required_secrets: tuple[str, ...]
    required_apps: tuple[str, ...]
    enterprise_notes: tuple[str, ...]


@dataclass(frozen=True)
class ClientCloudProfile:
    client_id: str
    display_name: str
    local: LocalProfile
    cloud: CloudProfile
    enabled: bool = True


@dataclass(frozen=True)
class CloudClientStatus:
    client_id: str
    display_name: str
    status: str
    local_cli_present: bool
    workflow_present: bool | None
    cloud_review_ready: bool
    cloud_mutation_enabled: bool
    blockers: tuple[str, ...]
    mutation_blockers: tuple[str, ...]
    default_modes: tuple[str, ...]
    mutation_modes: tuple[str, ...]

    def __repr__(self) -> str:
        return (
            "CloudClientStatus("
            f"client_id={self.client_id!r}, "
            f"display_name={self.display_name!r}, "
            f"status={self.status!r}, "
            f"local_cli_available={self.local_cli_present!r}, "
            f"workflow_available={self.workflow_present!r}, "
            f"cloud_review_ready={self.cloud_review_ready!r}, "
            f"cloud_mutation_enabled={self.cloud_mutation_enabled!r}, "
            f"blockers={self.blockers!r}, "
            f"mutation_blockers={self.mutation_blockers!r}, "
            f"default_modes={self.default_modes!r}, "
            f"mutation_modes={self.mutation_modes!r})"
        )


def load_cloud_profiles(path: Path | None = None) -> dict[str, ClientCloudProfile]:
    """Load cloud execution profiles keyed by client id."""
    config_path = path or get_config_dir() / "agents" / "cloud_execution.yaml"
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, Mapping):
        raise ValueError("cloud execution config must be a mapping")
    _validate_global_modes(data)

    clients = _required_mapping(data, "clients", "config")
    profiles: dict[str, ClientCloudProfile] = {}
    for client_id, raw_profile in clients.items():
        profile = _profile_from_mapping(str(client_id), raw_profile)
        _validate_profile(profile)
        profiles[profile.client_id] = profile
    return profiles


def classify_cloud_status(
    profile: ClientCloudProfile,
    *,
    repo_root: Path | None = None,
    env: Mapping[str, str] | None = None,
    command_exists: Callable[[str], str | None] | None = None,
    app_enabled: Mapping[str, bool] | None = None,
    enabled_mutation_clients: set[str] | None = None,
) -> CloudClientStatus:
    """Classify one client's cloud readiness without mutating local state."""
    root = repo_root or get_project_root()
    env_map = env if env is not None else os.environ
    command_checker = command_exists or shutil.which
    enabled_apps = app_enabled or {}
    mutation_clients = enabled_mutation_clients or set()

    local_cli_present = command_checker(profile.local.cli) is not None
    workflow_present = _workflow_present(profile, root)
    blockers = _cloud_blockers(profile, env_map, enabled_apps, workflow_present)
    status = _status_from_blockers(blockers)
    cloud_review_ready = status == "ready"

    mutation_blockers = _mutation_blockers(
        profile=profile,
        cloud_review_ready=cloud_review_ready,
        enabled_mutation_clients=mutation_clients,
    )

    return CloudClientStatus(
        client_id=profile.client_id,
        display_name=profile.display_name,
        status=status,
        local_cli_present=local_cli_present,
        workflow_present=workflow_present,
        cloud_review_ready=cloud_review_ready,
        cloud_mutation_enabled=not mutation_blockers,
        blockers=tuple(blockers),
        mutation_blockers=tuple(mutation_blockers),
        default_modes=profile.cloud.default_modes,
        mutation_modes=profile.cloud.mutation_modes,
    )


def _profile_from_mapping(client_id: str, raw_profile: Mapping[str, object]) -> ClientCloudProfile:
    if not isinstance(raw_profile, Mapping):
        raise ValueError(f"{client_id} profile must be a mapping")

    local_raw = _required_mapping(raw_profile, "local", client_id)
    cloud_raw = _required_mapping(raw_profile, "cloud", client_id)
    triggers = _triggers_from_mapping(
        _optional_mapping(cloud_raw, "triggers", client_id),
        client_id,
    )

    return ClientCloudProfile(
        client_id=client_id,
        display_name=str(raw_profile.get("display_name") or client_id),
        enabled=_optional_bool(raw_profile, "enabled", client_id, default=True),
        local=LocalProfile(
            cli=_required_string(local_raw, "cli", f"{client_id}.local"),
            plugin_pack=_required_string(local_raw, "plugin_pack", f"{client_id}.local"),
            mcp_client_id=_required_string(local_raw, "mcp_client_id", f"{client_id}.local"),
            config_paths=_required_string_list(local_raw, "config_paths", f"{client_id}.local"),
        ),
        cloud=CloudProfile(
            vendor_surface=_required_string(cloud_raw, "vendor_surface", f"{client_id}.cloud"),
            execution_kind=_required_string(cloud_raw, "execution_kind", f"{client_id}.cloud"),
            github_workflow=_optional_workflow_string(
                cloud_raw.get("github_workflow"),
                f"{client_id}.cloud.github_workflow",
            ),
            default_modes=_required_string_list(cloud_raw, "default_modes", f"{client_id}.cloud"),
            mutation_modes=_required_string_list(cloud_raw, "mutation_modes", f"{client_id}.cloud"),
            triggers=triggers,
            required_secrets=_required_string_list(
                cloud_raw,
                "required_secrets",
                f"{client_id}.cloud",
            ),
            required_apps=_required_string_list(cloud_raw, "required_apps", f"{client_id}.cloud"),
            enterprise_notes=_required_string_list(
                cloud_raw,
                "enterprise_notes",
                f"{client_id}.cloud",
            ),
        ),
    )


def _validate_global_modes(data: Mapping[str, object]) -> None:
    safe_modes = set(_required_string_list(data, "default_safe_modes", "config"))
    mutation_modes = set(_required_string_list(data, "mutation_modes", "config"))
    overlap = safe_modes & mutation_modes
    if overlap:
        raise ValueError(f"default safe modes include mutation modes: {sorted(overlap)}")


def _validate_profile(profile: ClientCloudProfile) -> None:
    default_modes = set(profile.cloud.default_modes)
    mutation_modes = set(profile.cloud.mutation_modes)
    unsafe_defaults = default_modes & mutation_modes
    unknown_modes = (default_modes | mutation_modes) - (SAFE_MODES | MUTATION_MODES)

    if unsafe_defaults:
        raise ValueError(f"{profile.client_id} default modes include mutation modes: {sorted(unsafe_defaults)}")
    if unknown_modes:
        raise ValueError(f"{profile.client_id} has unknown modes: {sorted(unknown_modes)}")


def _workflow_present(profile: ClientCloudProfile, repo_root: Path) -> bool | None:
    if profile.cloud.github_workflow is None:
        return None
    return (repo_root / profile.cloud.github_workflow).exists()


def _cloud_blockers(
    profile: ClientCloudProfile,
    env: Mapping[str, str],
    enabled_apps: Mapping[str, bool],
    workflow_present: bool | None,
) -> list[str]:
    blockers: list[str] = []
    if not profile.enabled:
        blockers.append("disabled by Augur policy")
    if workflow_present is False:
        blockers.append(f"missing workflow: {profile.cloud.github_workflow}")
    for secret_name in profile.cloud.required_secrets:
        if not env.get(secret_name):
            blockers.append(f"missing secret: {secret_name}")
    for app_name in profile.cloud.required_apps:
        if enabled_apps.get(app_name) is not True:
            blockers.append(f"needs app or connector: {app_name}")
    return blockers


def _mutation_blockers(
    *,
    profile: ClientCloudProfile,
    cloud_review_ready: bool,
    enabled_mutation_clients: set[str],
) -> list[str]:
    blockers: list[str] = []
    if profile.client_id not in enabled_mutation_clients:
        blockers.append("mutation mode requires explicit opt-in")
    if not cloud_review_ready:
        blockers.append("cloud review mode is not ready")
    return blockers


def _status_from_blockers(blockers: Sequence[str]) -> str:
    if not blockers:
        return "ready"

    joined = "\n".join(blockers)
    if "disabled by Augur policy" in joined:
        return "disabled-by-policy"
    if "missing secret:" in joined:
        return "missing-secret"
    if "needs app or connector:" in joined:
        return "needs-github-app"
    if "missing workflow:" in joined:
        return "local-only"
    return "unknown"


def _required_mapping(
    raw: Mapping[str, object],
    field_name: str,
    owner: str,
) -> Mapping[str, object]:
    value = raw.get(field_name)
    if not isinstance(value, Mapping):
        raise ValueError(f"{owner}.{field_name} must be a mapping")
    return value


def _optional_mapping(
    raw: Mapping[str, object],
    field_name: str,
    owner: str,
) -> Mapping[str, object]:
    value = raw.get(field_name)
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{owner}.{field_name} must be a mapping")
    return value


def _required_string(raw: Mapping[str, object], field_name: str, owner: str) -> str:
    value = raw.get(field_name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{owner}.{field_name} is required")
    return value


def _optional_bool(
    raw: Mapping[str, object],
    field_name: str,
    owner: str,
    *,
    default: bool,
) -> bool:
    if field_name not in raw:
        return default
    value = raw[field_name]
    if not isinstance(value, bool):
        raise ValueError(f"{owner}.{field_name} must be a boolean")
    return value


def _required_string_list(
    raw: Mapping[str, object],
    field_name: str,
    owner: str,
) -> tuple[str, ...]:
    if field_name not in raw:
        raise ValueError(f"{owner}.{field_name} is required")
    return _string_list(raw[field_name], f"{owner}.{field_name}")


def _string_list(value: object, field_path: str) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        raise ValueError(f"{field_path} must be a list of strings")
    if any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field_path} must be a list of strings")
    return tuple(value)


def _optional_workflow_string(value: object, field_path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_path} must be null or a non-empty string")
    return value


def _triggers_from_mapping(
    raw_triggers: Mapping[str, object],
    client_id: str,
) -> dict[str, tuple[str, ...]]:
    triggers: dict[str, tuple[str, ...]] = {}
    for mode, values in raw_triggers.items():
        if not isinstance(mode, str):
            raise ValueError(f"{client_id}.cloud.triggers keys must be strings")
        triggers[mode] = _string_list(values, f"{client_id}.cloud.triggers.{mode}")
    return triggers
