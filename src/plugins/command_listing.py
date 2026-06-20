"""Shared slash-command listing payload.

Single source of truth for the grouped slash-command listing consumed by both
the ``list-commands`` MCP tool (ai skill) and ``aug discover --commands``
(augur-core discover subcommand). Keeping one builder avoids the two surfaces
drifting apart. Depends only on shared ``src.plugins`` discovery — no skill
imports — so either caller can use it without cross-skill coupling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Display order + labels for visible (non-auto) slash command groups, keyed by
# the command's ``visibility`` tier.
SLASH_GROUP_ORDER = [
    ("app", "App Commands"),
    ("core", "Core Commands"),
    ("dev", "Dev Commands"),
    ("test", "Test Commands"),
    ("ops", "Ops Commands"),
]


def _is_truthy_frontmatter(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _is_native_slash_export(cmd: Any) -> bool:
    """Return True when a command doc is exported to native client slash surfaces."""
    path_value = getattr(cmd, "path", None)
    if not path_value:
        return False

    path = Path(path_value)
    if not path.is_file() or path.suffix != ".md":
        return False

    from src.lib.frontmatter_utils import parse_frontmatter

    frontmatter, _ = parse_frontmatter(path, include_sidecar_config=False)
    return _is_truthy_frontmatter(frontmatter.get("x-augur-export-command"))


def build_command_entry(cmd: Any) -> dict[str, Any]:
    """Render one discovered command into a JSON-safe entry."""
    entry: dict[str, Any] = {
        "id": cmd.id,
        "description": cmd.description,
        "visibility": cmd.visibility,
        "alias": cmd.alias,
        "group": cmd.group,
        "bundle": cmd.bundle,
    }
    if cmd.loop:
        entry["loop"] = {
            "name": cmd.loop.get("name", ""),
            "tier": cmd.loop.get("tier", ""),
            "trigger": cmd.loop.get("trigger", ""),
        }
    return entry


def render_commands_payload() -> dict[str, Any]:
    """Return grouped slash commands, auto loop commands, and non-command skills."""
    from src.plugins.command_discovery import discover_commands
    from src.plugins.skill_discovery import list_skills

    cmds = discover_commands()

    slash_groups: dict[str, list[dict[str, Any]]] = {}

    for cmd in cmds:
        if _is_native_slash_export(cmd):
            entry = build_command_entry(cmd)
            slash_groups.setdefault(cmd.visibility, []).append(entry)

    slash_sections = []
    for key, label in SLASH_GROUP_ORDER:
        items = slash_groups.get(key, [])
        if items:
            slash_sections.append(
                {
                    "key": key,
                    "label": label,
                    "commands": sorted(items, key=lambda c: c["id"]),
                }
            )

    command_ids = {cmd.id for cmd in cmds}
    all_skills = list_skills()
    skills_list = []
    for skill in all_skills:
        if skill.id not in command_ids and skill.visibility is None:
            skills_list.append(
                {
                    "id": skill.id,
                    "description": skill.description,
                    "bundle": skill.layer,
                }
            )

    total_slash_commands = sum(len(section["commands"]) for section in slash_sections)

    return {
        "total_commands": total_slash_commands,
        "total_slash_commands": total_slash_commands,
        "total_skills": len(all_skills),
        "total_visible_skills": len(all_skills),
        "non_command_skills": len(skills_list),
        "slash_commands": slash_sections,
        "skills": sorted(skills_list, key=lambda s: s["id"]),
    }
