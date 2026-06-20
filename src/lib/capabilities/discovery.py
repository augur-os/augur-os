"""Convert Augur discovery sources into capability inventory records."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from src.cli_config.manifest import load_manifest
from src.config.paths import (
    get_configured_vault_skills_dir,
    get_managed_skill_source_dirs,
    get_project_brain_skills_dir,
    get_project_root,
    get_vault_skills_dir,
)
from src.lib.external_services import (
    external_service_capability_id,
    external_service_registry_path,
    load_external_service_registry,
)
from src.lib.frontmatter_utils import load_skill_frontmatter, parse_frontmatter
from src.lib.skill_standard import normalize_skill_file
from src.plugins.command_discovery import discover_commands
from src.plugins.skill_discovery import discover_all_skills

from .exposure_policy import (
    CapabilityDiscovery,
    CapabilityType,
    OwnerKind,
    capability_policy_path,
    load_capability_policy,
)

# Import helpers from sibling modules (behavior-preserving split)
from ._discovery_helpers import (  # noqa: F401
    _declared_cli_names,
    _exposure_from_sources,
    _is_relative_to,
    _is_truthy,
    _management,
    _merge_capability_records,
    _merge_metadata,
    _metadata_values,
    _owner_kind,
    _path_for_source,
    _policy_list,
    _scope_from_sources,
    _unique_items,
    capability_id,
)
from ._discovery_mcp import (  # noqa: F401
    _declared_mcp_tool_exposure,
    _extract_mcp_tool_decorator_name,
    _script_mcp_tool_names,
)


def _same_path(left: Path, right: Path) -> bool:
    return left.resolve() == right.resolve()


def _private_root_for_skill_dir(
    project_root: Path,
    skills_dir: Path,
    configured_private_root: Path,
) -> Path:
    """Return the live private root for a skill directory.

    Lives in discovery.py (not _discovery_helpers) so that tests can monkeypatch
    discovery.get_vault_skills_dir and discovery.get_project_root to affect this.
    """
    live_project_root = get_project_root()
    if _same_path(project_root, live_project_root):
        live_private_root = get_vault_skills_dir()
        if _same_path(skills_dir, live_private_root):
            return live_private_root
    return configured_private_root


def discover_declared_skill_capabilities(
    root: Path | None = None,
    *,
    policy: dict[str, Any] | None = None,
    skill_source_dirs: tuple[Path, ...] | list[Path] | None = None,
) -> list[CapabilityDiscovery]:
    """Discover MCP tool and CLI declarations from managed skill roots.

    Lives in discovery.py so that tests can monkeypatch
    discovery.get_managed_skill_source_dirs, discovery.get_project_root,
    and discovery.get_vault_skills_dir.
    """
    project_root = root or get_project_root()
    if policy is None:
        policy = load_capability_policy(capability_policy_path(project_root))

    source_dirs = (
        list(skill_source_dirs) if skill_source_dirs is not None else get_managed_skill_source_dirs(project_root)
    )
    project_brain_root = get_project_brain_skills_dir(project_root)
    private_root = get_configured_vault_skills_dir(project_root)

    records: list[CapabilityDiscovery] = []
    for skills_dir in source_dirs:
        fallback_private_root = _private_root_for_skill_dir(
            project_root,
            skills_dir,
            private_root,
        )
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            skill_private_root = fallback_private_root
            if (
                skill_source_dirs is not None
                and not _is_relative_to(skill_md, project_brain_root)
                and not _is_relative_to(skill_md, private_root)
                and not _is_relative_to(skill_md, fallback_private_root)
            ):
                skill_private_root = skills_dir
            normalized = normalize_skill_file(
                skill_md,
                shared_root=project_brain_root,
                private_root=skill_private_root,
            )
            source_path = _path_for_source(skill_md, root)

            for tool in normalized.tools:
                records.append(
                    CapabilityDiscovery(
                        id=capability_id("mcp-tool", tool.name),
                        type="mcp-tool",
                        owner_kind=cast(OwnerKind, normalized.ownership),
                        management="generated",
                        scope="project",
                        source_paths=(source_path,),
                        current_exposure=_declared_mcp_tool_exposure(
                            tool.name,
                            policy,
                        ),
                        metadata={
                            "skill": normalized.name,
                            "primary_surface": tool.surface,
                        },
                    )
                )

            for cli_name in _declared_cli_names(normalized.metadata.get("cli_integrations")):
                records.append(
                    CapabilityDiscovery(
                        id=capability_id("cli", cli_name),
                        type="cli",
                        owner_kind=cast(OwnerKind, normalized.ownership),
                        management="generated",
                        scope="project",
                        source_paths=(source_path,),
                        current_exposure=("browse",),
                        metadata={
                            "skill": normalized.name,
                            "primary_surface": "cli",
                        },
                    )
                )

    return records


def discover_script_mcp_tool_capabilities(
    root: Path | None = None,
    *,
    policy: dict[str, Any] | None = None,
) -> list[CapabilityDiscovery]:
    """Discover MCP tools implemented in active managed skill scripts.

    Lives in discovery.py so that tests can monkeypatch
    discovery.get_managed_skill_source_dirs.
    """
    if policy is None:
        policy = load_capability_policy(capability_policy_path(root) if root is not None else None)

    project_root = root or get_project_root()
    project_brain_root = get_project_brain_skills_dir(project_root)
    configured_private_root = get_configured_vault_skills_dir(project_root)

    records: list[CapabilityDiscovery] = []
    for skills_dir in get_managed_skill_source_dirs(root):
        fallback_private_root = _private_root_for_skill_dir(
            project_root,
            skills_dir,
            configured_private_root,
        )
        skill_private_root = fallback_private_root
        if (
            not _same_path(skills_dir, project_brain_root)
            and not _is_relative_to(skills_dir, project_brain_root)
            and not _same_path(skills_dir, fallback_private_root)
            and not _is_relative_to(skills_dir, fallback_private_root)
        ):
            skill_private_root = skills_dir
        for mcp_dir in sorted(skills_dir.glob("*/scripts/mcp")):
            if not mcp_dir.is_dir():
                continue
            skill_dir = mcp_dir.parents[1]
            skill_md = skill_dir / "SKILL.md"
            if skill_md.is_file():
                normalized = normalize_skill_file(
                    skill_md,
                    shared_root=project_brain_root,
                    private_root=skill_private_root,
                )
                skill_name = normalized.name
                owner_kind = cast(OwnerKind, normalized.ownership)
            else:
                skill_name = skill_dir.name
                owner_kind = "augur"
            for py_file in sorted(mcp_dir.rglob("*.py")):
                if py_file.name.startswith("test_"):
                    continue
                source_path = _path_for_source(py_file, root)
                for tool_name in _script_mcp_tool_names(py_file):
                    records.append(
                        CapabilityDiscovery(
                            id=capability_id("mcp-tool", tool_name),
                            type="mcp-tool",
                            owner_kind=owner_kind,
                            management="generated",
                            scope="project",
                            source_paths=(source_path,),
                            current_exposure=_declared_mcp_tool_exposure(
                                tool_name,
                                policy,
                            ),
                            metadata={
                                "skill": skill_name,
                                "primary_surface": "mcp",
                            },
                        )
                    )
    return sorted(records, key=lambda record: record.id)


def discover_skill_capabilities() -> list[CapabilityDiscovery]:
    """Discover skill capability records from canonical skill discovery."""
    records: list[CapabilityDiscovery] = []
    for skill in discover_all_skills():
        path = Path(getattr(skill, "path", ""))
        client_sources = tuple(getattr(skill, "client_sources", ()) or ())
        metadata = {
            "source_root": str(getattr(skill, "source_root", "") or ""),
            "source": str(getattr(skill, "source", "") or ""),
            "primary_surface": "skill",
        }
        mcp_tools = getattr(skill, "mcp_tools", None)
        if mcp_tools:
            metadata["mcp_tools"] = ",".join(str(tool) for tool in mcp_tools)

        records.append(
            CapabilityDiscovery(
                id=capability_id("skill", getattr(skill, "name", path.name)),
                type="skill",
                owner_kind=_owner_kind(getattr(skill, "ownership", "augur")),
                management=_management(getattr(skill, "source_root", "")),
                scope=_scope_from_sources(client_sources),
                source_paths=(str(path / "SKILL.md"),),
                current_exposure=_exposure_from_sources(client_sources),
                metadata=metadata,
            )
        )
    return records


def _mcp_server_current_exposure(server_id: str, policy: dict[str, Any]) -> tuple[str, ...]:
    entries = policy.get("capabilities") if isinstance(policy, dict) else {}
    if not isinstance(entries, dict):
        return ("mcp-config",)

    entry = entries.get(capability_id("mcp-server", server_id))
    if not isinstance(entry, dict):
        return ("mcp-config",)

    if str(entry.get("classification_status") or "").strip() == "blocked":
        return ()

    export_to = set(_policy_list(entry.get("export_to")))
    return tuple(
        target
        for target in (
            "mcp-config",
            "claude",
            "codex",
            "gemini",
            "opencode",
            "cursor",
            "copilot",
        )
        if target in export_to
    )


def discover_mcp_server_capabilities() -> list[CapabilityDiscovery]:
    """Discover MCP server records from the generated MCP manifest."""
    try:
        manifest = load_manifest()
    except (FileNotFoundError, ValueError):
        return []
    policy = load_capability_policy(getattr(manifest, "policy_path", None))

    records: list[CapabilityDiscovery] = []
    for entry in manifest.all_augur_servers():
        bundle = str(getattr(entry, "bundle", "") or "")
        bundle_path = str(getattr(entry, "bundle_path", "") or "")
        source_paths = ["config/system/mcp_servers.yaml"]
        if bundle_path:
            source_paths.append(bundle_path)

        records.append(
            CapabilityDiscovery(
                id=capability_id("mcp-server", entry.id),
                type="mcp-server",
                owner_kind="augur",
                management="generated",
                scope=getattr(entry, "scope", "global"),
                source_paths=tuple(source_paths),
                current_exposure=_mcp_server_current_exposure(entry.id, policy),
                metadata={
                    "tier": "vault" if bundle or bundle_path else "project",
                    "bundle": bundle,
                    "bundle_path": bundle_path,
                    "primary_surface": "mcp",
                },
            )
        )
    return records


def _discover_command_doc_capabilities(root: Path | None) -> list[CapabilityDiscovery]:
    """Discover command records from managed skill command docs."""
    records: list[CapabilityDiscovery] = []
    for skills_dir in get_managed_skill_source_dirs(root):
        if not skills_dir.is_dir():
            continue
        for skill_dir in sorted(path for path in skills_dir.iterdir() if path.is_dir()):
            skill_md = skill_dir / "SKILL.md"
            commands_dir = skill_dir / "commands"
            if not skill_md.is_file() or not commands_dir.is_dir():
                continue

            skill_meta = load_skill_frontmatter(
                skill_md,
                include_sidecar_config=False,
            )
            skill_name = str(skill_meta.get("name") or skill_dir.name)
            hub = skill_dir.name  # x-augur-hub removed by ADR-802
            for command_file in sorted(commands_dir.glob("*.md")):
                if not command_file.is_file():
                    continue
                meta, _body = parse_frontmatter(command_file)
                if meta.get("skill") and not _is_truthy(meta.get("x-augur-export-command")):
                    continue

                command_name = str(meta.get("id") or command_file.stem).strip()
                if not command_name:
                    continue
                records.append(
                    CapabilityDiscovery(
                        id=capability_id("command", command_name),
                        type="command",
                        owner_kind="augur",
                        management="generated",
                        scope="project",
                        source_paths=(_path_for_source(command_file, root),),
                        current_exposure=_command_current_exposure(root, command_name),
                        metadata={
                            "visibility": str(meta.get("visibility") or ""),
                            "bundle": "project",
                            "hub": hub,
                            "skill": skill_name,
                            "primary_surface": "command",
                        },
                    )
                )
    return records


def _command_current_exposure(root: Path | None, command_name: str) -> tuple[str, ...]:
    exposure = ["cli", "agents-md", "browse"]
    project_root = root or get_project_root()
    if (project_root / ".claude" / "commands" / f"{command_name}.md").is_file():
        exposure.append("claude")
    if (project_root / ".codex" / "skills" / command_name / "SKILL.md").is_file():
        exposure.append("codex")
    if (project_root / ".gemini" / "skills" / command_name / "SKILL.md").is_file():
        exposure.append("gemini")
    return tuple(exposure)


def discover_command_capabilities(root: Path | None = None) -> list[CapabilityDiscovery]:
    """Discover command and workflow records from command discovery and docs."""
    records: list[CapabilityDiscovery] = []
    for command in discover_commands():
        command_name = str(getattr(command, "id", "") or "")
        command_record_id = capability_id("command", command_name)
        path = getattr(command, "path", None)
        source_paths = (str(path),) if path else ()
        loop = getattr(command, "loop", None)

        records.append(
            CapabilityDiscovery(
                id=command_record_id,
                type="command",
                owner_kind="augur",
                management="generated",
                scope="project",
                source_paths=source_paths,
                current_exposure=_command_current_exposure(root, command_name),
                metadata={
                    "visibility": str(getattr(command, "visibility", "") or ""),
                    "bundle": str(getattr(command, "bundle", "") or ""),
                    "primary_surface": "command",
                },
            )
        )
        if loop:
            records.append(
                CapabilityDiscovery(
                    id=capability_id("workflow", command_name),
                    type="workflow",
                    owner_kind="augur",
                    management="generated",
                    scope="project",
                    source_paths=source_paths,
                    current_exposure=("cli", "agents-md", "browse"),
                    metadata={
                        "command": command_record_id,
                        "loop": str(loop),
                        "primary_surface": "workflow",
                    },
                )
            )
    records.extend(_discover_command_doc_capabilities(root))
    return _merge_capability_records(records)


def _external_service_capability_type(service_type: str) -> str:
    normalized = str(service_type or "mcp").strip().lower()
    if normalized == "cli":
        return "cli"
    if normalized == "mcp":
        return "mcp-server"
    return ""


def _external_service_exposure(service_type: str, enabled: Any) -> tuple[str, ...]:
    normalized = str(service_type or "mcp").strip().lower()
    if normalized == "cli" and bool(enabled):
        return ("browse", "shell")
    if normalized == "mcp" and bool(enabled):
        return ("browse", "mcp-config")
    return ("browse",)


def discover_external_service_capabilities(
    root: Path | None = None,
) -> list[CapabilityDiscovery]:
    """Discover external registry services as read-only capability records."""
    registry = load_external_service_registry(root)
    if not registry:
        return []

    registry_path = str(external_service_registry_path(root))
    records: list[CapabilityDiscovery] = []
    for service_id, service in sorted(registry.items()):
        service_type = str(service.get("type") or "mcp").strip().lower()
        capability_type = _external_service_capability_type(service_type)
        if not capability_type:
            continue

        metadata = {
            "external_service_id": service_id,
            "primary_surface": service_type,
            "service_type": service_type,
            "enabled": "true" if bool(service.get("enabled", False)) else "false",
        }
        used_by = service.get("used_by")
        if isinstance(used_by, list) and used_by:
            metadata["used_by"] = ",".join(str(item) for item in used_by if str(item))
        for key in ("setup_url", "check_command", "command"):
            value = service.get(key)
            if value:
                metadata[key] = str(value)

        records.append(
            CapabilityDiscovery(
                id=external_service_capability_id(service_id, service_type),
                type=cast(CapabilityType, capability_type),
                owner_kind="external",
                management="unmanaged",
                scope="global",
                source_paths=(registry_path,),
                current_exposure=_external_service_exposure(
                    service_type,
                    service.get("enabled", False),
                ),
                metadata=metadata,
            )
        )
    return sorted(records, key=lambda record: record.id)


def _external_skill_config_path(root: Path | None = None) -> Path:
    project_root = root or get_project_root()
    return project_root / "config" / "external_skills.yaml"


def _external_skill_targets_exposure(targets: Any) -> tuple[str, ...]:
    if not isinstance(targets, dict):
        return ()
    mapping = {
        "claude_code": "claude",
        "claude-code": "claude",
        "claude": "claude",
        "codex": "codex",
        "gemini": "gemini",
        "opencode": "opencode",
        "cursor": "cursor",
        "copilot": "copilot",
    }
    exposure: list[str] = []
    for raw_target, raw_mode in targets.items():
        if not raw_mode:
            continue
        client = mapping.get(str(raw_target).strip())
        if client:
            exposure.append(client)
    return tuple(dict.fromkeys(exposure))


def discover_external_skill_bundle_capabilities(
    root: Path | None = None,
) -> list[CapabilityDiscovery]:
    """Discover vendored external skill bundles even when only one client owns them."""
    config_path = _external_skill_config_path(root)
    if not config_path.exists():
        return []

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    if not isinstance(data, dict):
        return []

    project_root = root or get_project_root()
    records: list[CapabilityDiscovery] = []
    for bundle in data.get("external_skill_bundles") or []:
        if not isinstance(bundle, dict):
            continue
        bundle_id = str(bundle.get("id") or "").strip()
        source_rel = str(bundle.get("source") or "").strip()
        if not bundle_id or not source_rel:
            continue
        source = (project_root / source_rel).resolve()
        exposure = _external_skill_targets_exposure(bundle.get("targets"))
        upstream = str(bundle.get("upstream") or "").strip()
        pinned_sha = str(bundle.get("pinned_sha") or "").strip()

        for raw_skill_name in bundle.get("skills") or []:
            skill_name = str(raw_skill_name or "").strip()
            if not skill_name:
                continue
            skill_md = source / "skills" / skill_name / "SKILL.md"
            source_paths = (str(skill_md),) if skill_md.exists() else (str(source),)
            metadata = {
                "source_root": "external-bundle",
                "source": bundle_id,
                "external_bundle": bundle_id,
                "primary_surface": "skill",
            }
            if upstream:
                metadata["upstream"] = upstream
            if pinned_sha:
                metadata["pinned_sha"] = pinned_sha

            records.append(
                CapabilityDiscovery(
                    id=capability_id("skill", skill_name),
                    type="skill",
                    owner_kind="external",
                    management="unmanaged",
                    scope="project",
                    source_paths=source_paths,
                    current_exposure=exposure,
                    metadata=metadata,
                )
            )

    return sorted(records, key=lambda record: record.id)


def discover_capabilities() -> list[CapabilityDiscovery]:
    """Aggregate all capability discovery collectors."""
    records = [
        *discover_skill_capabilities(),
        *discover_mcp_server_capabilities(),
        *discover_external_service_capabilities(),
        *discover_external_skill_bundle_capabilities(),
        *discover_command_capabilities(),
        *discover_declared_skill_capabilities(),
        *discover_script_mcp_tool_capabilities(),
    ]
    return _merge_capability_records(records)
