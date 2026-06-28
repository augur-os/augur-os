"""Agent Skills-compatible Augur skill metadata normalization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from src.lib.frontmatter_utils import load_skill_frontmatter

STANDARD_PRIMARY_SURFACES = frozenset({"cli", "mcp", "mcp via dashboard", "skill"})
STANDARD_TOOL_SURFACES = frozenset({"cli", "mcp", "mcp via dashboard"})
LEGACY_AUGUR_FIELDS = frozenset(
    {
        "x-augur-type",
        "x-augur-release",
        "x-augur-tags",
        "x-augur-commands",
        "x-augur-cli-integrations",
        "x-augur-mcp-tools",
        "x-augur-routine",
        "x-augur-routines",
        "x-augur-config",
        "x-augur-dashboard-pages",
        "x-augur-dependencies",
    }
)


@dataclass(frozen=True)
class NormalizedCommand:
    id: str
    visibility: str = ""
    type: str = "workflow"
    callable: str = ""


@dataclass(frozen=True)
class NormalizedTool:
    name: str
    surface: str = "mcp"


@dataclass(frozen=True)
class NormalizedRoutine:
    id: str
    execution: str = ""
    policy: str = ""
    callable: str = ""
    hub: str = ""


@dataclass(frozen=True)
class NormalizedSkill:
    name: str
    description: str
    source_path: str
    ownership: str
    hub: str = ""
    skill_type: str = ""
    release: str = ""
    tags: tuple[str, ...] = ()
    commands: tuple[NormalizedCommand, ...] = ()
    tools: tuple[NormalizedTool, ...] = ()
    routines: tuple[NormalizedRoutine, ...] = ()
    dashboard_pages: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


def normalize_skill_file(
    skill_md: Path,
    *,
    shared_root: Path | None,
    private_root: Path | None,
) -> NormalizedSkill:
    frontmatter = load_skill_frontmatter(skill_md)
    ownership = infer_skill_ownership(
        skill_md,
        shared_root=shared_root,
        private_root=private_root,
    )
    return normalize_skill_frontmatter(
        frontmatter,
        source_path=str(skill_md),
        ownership=ownership,
    )


def infer_skill_ownership(
    skill_md: Path,
    *,
    shared_root: Path | None,
    private_root: Path | None,
) -> str:
    resolved = skill_md.resolve()
    if private_root is not None and _is_relative_to(resolved, private_root.resolve()):
        return "user"
    if shared_root is not None and _is_relative_to(resolved, shared_root.resolve()):
        return "augur"
    return "augur"


def normalize_skill_frontmatter(
    frontmatter: dict[str, Any],
    *,
    source_path: str,
    ownership: str,
) -> NormalizedSkill:
    block = frontmatter.get("x-augur")
    x_augur = block if isinstance(block, dict) else {}
    legacy_keys = sorted(key for key in frontmatter if key in LEGACY_AUGUR_FIELDS)
    warnings: list[str] = []
    if legacy_keys:
        warnings.append("legacy x-augur-* fields used")
    if x_augur and legacy_keys:
        warnings.append("legacy fields shadowed by x-augur block")

    tools = _normalize_tools(
        x_augur.get("tools") if "tools" in x_augur else frontmatter.get("x-augur-mcp-tools"),
        warnings,
    )
    commands = _normalize_commands(
        x_augur.get("commands") if "commands" in x_augur else _legacy_commands(frontmatter),
    )
    routines = _normalize_routines(
        (
            x_augur.get("routines")
            if "routines" in x_augur
            else (_loop_routines(frontmatter) or _legacy_routines(frontmatter))
        ),
    )
    dashboard_pages = _normalize_dashboard_pages(
        x_augur.get("dashboard") if "dashboard" in x_augur else _legacy_dashboard_pages(frontmatter)
    )
    dependencies = _normalize_dependencies(
        x_augur.get("dependencies") if "dependencies" in x_augur else frontmatter.get("x-augur-dependencies")
    )
    metadata = _normalize_metadata(frontmatter)

    return NormalizedSkill(
        name=str(frontmatter.get("name") or Path(source_path).parent.name),
        description=str(frontmatter.get("description") or ""),
        source_path=source_path,
        ownership=ownership,
        # Hubs were retired in ADR-802; field stays for backward compat but is
        # no longer populated from frontmatter.
        hub="",
        skill_type=_scalar_text(x_augur["type"] if "type" in x_augur else frontmatter.get("x-augur-type") or ""),
        release=_scalar_text(x_augur["release"] if "release" in x_augur else frontmatter.get("x-augur-release") or ""),
        tags=tuple(
            str(tag) for tag in _as_list(x_augur["tags"] if "tags" in x_augur else frontmatter.get("x-augur-tags"))
        ),
        commands=commands,
        tools=tools,
        routines=routines,
        dashboard_pages=dashboard_pages,
        dependencies=dependencies,
        warnings=tuple(dict.fromkeys(warnings)),
        metadata=metadata,
    )


def _normalize_tools(value: Any, warnings: list[str]) -> tuple[NormalizedTool, ...]:
    tools: list[NormalizedTool] = []
    for item in _as_list(value):
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("id") or "").strip()
            surface = str(item.get("surface") or "mcp").strip()
        else:
            name = str(item or "").strip()
            surface = "mcp"
        if not name:
            continue
        if surface not in STANDARD_TOOL_SURFACES:
            warnings.append(f"invalid tool surface: {name} -> {surface}")
        tools.append(NormalizedTool(name=name, surface=surface))
    return tuple(tools)


def _normalize_commands(value: Any) -> tuple[NormalizedCommand, ...]:
    commands: list[NormalizedCommand] = []
    seen: set[str] = set()
    for item in _as_list(value):
        if isinstance(item, dict):
            command_id = str(item.get("id") or item.get("name") or "").strip()
            command_key = command_id.lstrip("/")
            if not command_key or command_key in seen:
                continue
            seen.add(command_key)
            commands.append(
                NormalizedCommand(
                    id=command_id,
                    visibility=str(item.get("visibility") or ""),
                    type=str(item.get("type") or "workflow"),
                    callable=str(item.get("callable") or ""),
                )
            )
        else:
            command_id = str(item or "").strip()
            command_key = command_id.lstrip("/")
            if not command_key or command_key in seen:
                continue
            seen.add(command_key)
            commands.append(NormalizedCommand(id=command_id))
    return tuple(commands)


def _normalize_routines(value: Any) -> tuple[NormalizedRoutine, ...]:
    routines: list[NormalizedRoutine] = []
    for item in _as_list(value):
        if not isinstance(item, dict):
            continue
        routine_id = str(item.get("id") or "").strip()
        if not routine_id:
            continue
        routines.append(
            NormalizedRoutine(
                id=routine_id,
                execution=str(item.get("execution") or ""),
                policy=str(item.get("policy") or ""),
                callable=str(item.get("callable") or ""),
                hub=str(item.get("hub") or ""),
            )
        )
    return tuple(routines)


def _legacy_commands(frontmatter: dict[str, Any]) -> Any:
    commands = []
    commands.extend(_as_list(frontmatter.get("x-augur-commands")))
    config = frontmatter.get("x-augur-config")
    if isinstance(config, dict):
        commands.extend(_as_list(config.get("commands")))
        contributions = config.get("contributions")
        if isinstance(contributions, dict):
            commands.extend(_as_list(contributions.get("commands")))
    return commands


def _loop_routines(frontmatter: dict[str, Any]) -> list[dict[str, Any]]:
    """Map canonical ``x-augur-loop(s)`` blocks to NormalizedRoutine-shaped dicts.

    ``execution`` is synthesized from loop kind (``.md`` discover -> inline-session,
    else tiered) to match ``registry._routine_from_loop``; ``policy`` comes from
    ``memory.trust``, ``callable`` from ``automation.discover``.
    """
    blocks: list[dict[str, Any]] = []
    single = frontmatter.get("x-augur-loop")
    if isinstance(single, dict):
        blocks.append(single)
    plural = frontmatter.get("x-augur-loops")
    if isinstance(plural, list):
        blocks.extend(block for block in plural if isinstance(block, dict))
    routines: list[dict[str, Any]] = []
    for block in blocks:
        automation = block.get("automation") if isinstance(block.get("automation"), dict) else {}
        memory = block.get("memory") if isinstance(block.get("memory"), dict) else {}
        discover = str(automation.get("discover") or "")
        routines.append(
            {
                "id": block.get("id"),
                "execution": "inline-session" if discover.endswith(".md") else "tiered",
                "policy": memory.get("trust") or "",
                "callable": discover,
                "hub": "",
            }
        )
    return routines


def _legacy_routines(frontmatter: dict[str, Any]) -> Any:
    if frontmatter.get("x-augur-routines") is not None:
        return frontmatter.get("x-augur-routines")
    if frontmatter.get("x-augur-routine") is not None:
        return [frontmatter.get("x-augur-routine")]
    return []


def _normalize_dashboard_pages(value: Any) -> tuple[str, ...]:
    if isinstance(value, dict):
        value = value.get("pages")
    pages: list[str] = []
    for item in _as_list(value):
        if isinstance(item, dict):
            page = str(item.get("route") or item.get("path") or item.get("url") or item.get("id") or "").strip()
        else:
            page = str(item).strip()
        if page:
            pages.append(page)
    return tuple(pages)


def _legacy_dashboard_pages(frontmatter: dict[str, Any]) -> Any:
    pages = []
    pages.extend(_as_list(frontmatter.get("x-augur-dashboard-pages")))
    config = frontmatter.get("x-augur-config")
    if isinstance(config, dict):
        contributions = config.get("contributions")
        if isinstance(contributions, dict):
            pages.extend(_as_list(contributions.get("pages")))
    return pages


def _normalize_dependencies(value: Any) -> tuple[str, ...]:
    if isinstance(value, dict):
        values = []
        for key in ("required", "optional"):
            values.extend(_as_list(value.get(key)))
        return tuple(str(item).strip() for item in values if str(item).strip())
    return tuple(str(item).strip() for item in _as_list(value) if str(item).strip())


def _normalize_metadata(frontmatter: dict[str, Any]) -> Mapping[str, str]:
    cli_names = _legacy_cli_integration_names(frontmatter.get("x-augur-cli-integrations"))
    if not cli_names:
        return {}
    return {"cli_integrations": ",".join(cli_names)}


def _legacy_cli_integration_names(value: Any) -> tuple[str, ...]:
    names: list[str] = []
    for item in _as_list(value):
        if isinstance(item, dict):
            raw_name = item.get("name") or item.get("id")
        else:
            raw_name = item
        name = str(raw_name or "").strip()
        if name:
            names.append(name)
    return tuple(dict.fromkeys(names))


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _scalar_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
