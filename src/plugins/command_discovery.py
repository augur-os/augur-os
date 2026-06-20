"""Unified command discovery from SKILL.md frontmatter (ADR-252).

Slash commands are declared in ``x-augur-commands`` on each skill's
``SKILL.md``. Command docs live under ``skills/{skill}/commands/`` and are
resolved by convention for help surfaces and generated agent references.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from src.lib.frontmatter_utils import load_skill_frontmatter
from src.plugins.skill_discovery import discover_all_skills, invalidate_discovery_cache


@dataclass(frozen=True)
class CommandInfo:
    id: str
    description: str
    visibility: str
    loop: Optional[dict] = None
    alias: Optional[str] = None
    group: Optional[str] = None
    bundle: Optional[str] = None
    path: Optional[Path] = None


# Module-level cache for discover_commands() results.
# Cleared between sync runs via clear_cache(). Avoids redundant filesystem
# scans when multiple callers (templates, adapters) discover commands in
# the same process.
_cache: dict[tuple, list[CommandInfo]] = {}


def clear_cache() -> None:
    """Clear the discover_commands() cache between sync runs."""
    _cache.clear()
    invalidate_discovery_cache()


def _normalise_command_id(raw_id: Any) -> str:
    return str(raw_id or "").strip().lstrip("/")


def _resolve_command_source_path(skill_dir: Path, cmd_id: str, cmd_type: str, command: dict[str, Any]) -> Path:
    explicit_source = command.get("source_path")
    if isinstance(explicit_source, str) and explicit_source.strip():
        source_path = Path(explicit_source).expanduser()
        return source_path if source_path.is_absolute() else skill_dir / source_path

    if cmd_type == "skill":
        return skill_dir / "commands" / cmd_id / "SKILL.md"

    callable_path = command.get("callable")
    if isinstance(callable_path, str) and callable_path.strip():
        resolved_callable = skill_dir / callable_path
        if resolved_callable.exists():
            return resolved_callable

    return skill_dir / "commands" / f"{cmd_id}.md"


def _command_infos_from_skill(
    *,
    skill_dir: Path,
    description: str,
    commands: Iterable[Any],
    group: str | None,
    bundle: str | None,
    visibility_filter: Optional[set[str]],
) -> list[CommandInfo]:
    discovered: list[CommandInfo] = []
    for command in commands:
        if not isinstance(command, dict):
            continue

        cmd_id = _normalise_command_id(command.get("id"))
        if not cmd_id:
            continue

        visibility = str(command.get("visibility") or "core").strip() or "core"
        if visibility_filter and visibility not in visibility_filter:
            continue

        cmd_type = str(command.get("type") or "workflow")
        source_path = _resolve_command_source_path(skill_dir, cmd_id, cmd_type, command)
        loop = command.get("loop")
        if not isinstance(loop, dict):
            loop = None

        alias = command.get("alias")
        discovered.append(
            CommandInfo(
                id=cmd_id,
                description=str(command.get("description") or description or ""),
                visibility=visibility,
                loop=loop,
                alias=str(alias) if alias else None,
                group=str(command.get("group") or group or "") or None,
                bundle=str(command.get("bundle") or bundle or "") or None,
                path=source_path,
            )
        )
    return discovered


def _discover_commands_from_skill_parent(
    skills_dir: Path,
    visibility_filter: Optional[set[str]],
) -> list[CommandInfo]:
    commands: list[CommandInfo] = []
    if not skills_dir.exists():
        return commands

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue
        frontmatter = load_skill_frontmatter(skill_dir)
        declared_commands = frontmatter.get("x-augur-commands")
        if not isinstance(declared_commands, list):
            continue
        commands.extend(
            _command_infos_from_skill(
                skill_dir=skill_dir,
                description=str(frontmatter.get("description") or ""),
                commands=declared_commands,
                group=str(frontmatter.get("x-augur-group") or "") or None,
                bundle="project",
                visibility_filter=visibility_filter,
            )
        )
    return commands


def discover_commands(
    *,
    plugins_dir: Optional[Path] = None,
    visibility_filter: Optional[set[str]] = None,
) -> list[CommandInfo]:
    """Discover all slash commands from ``x-augur-commands`` frontmatter.

    Results are cached per (plugins_dir, visibility_filter) for the lifetime
    of the process. Call clear_cache() to invalidate.

    Args:
        plugins_dir: Override skill parent directory for testing.
        visibility_filter: Optional filter applied to command visibility.

    Returns:
        Sorted list of CommandInfo (by visibility, then id)
    """
    cache_key = (str(plugins_dir), tuple(sorted(visibility_filter)) if visibility_filter else ())
    if cache_key in _cache:
        return _cache[cache_key]

    if plugins_dir is not None:
        commands = _discover_commands_from_skill_parent(plugins_dir, visibility_filter)
    else:
        commands = []
        for skill in discover_all_skills():
            commands.extend(
                _command_infos_from_skill(
                    skill_dir=skill.path,
                    description=skill.description,
                    commands=skill.commands,
                    group=skill.group,
                    bundle=skill.layer,
                    visibility_filter=visibility_filter,
                )
            )

    result = sorted(commands, key=lambda c: (c.visibility, c.id))
    _cache[cache_key] = result
    return result
