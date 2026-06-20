#!/usr/bin/env python3
"""Migrate dashboard actions into file-based prompt and command entries.

Legacy skill metadata can contain ``x-augur-config.contributions.actions``.
The browse UI now discovers prompts and commands from Agent Skills directories:

  skills/<skill>/prompts/<id>.md
  skills/<skill>/commands/<id>.md

This script creates those files for migrated actions and removes only the
migrated action entries from SKILL.md. Modal or unknown actions stay in place.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter  # noqa: E402


PROMPT_DISPATCHES = {"oneshot", "ide", "chat", "auto"}
COMMAND_DISPATCHES = {"fire"}
MODAL_DISPATCHES = {"modal"}
VALID_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


@dataclass
class MigrationSummary:
    scanned: int = 0
    changed_skills: int = 0
    created_prompts: int = 0
    created_commands: int = 0
    existing_targets: list[str] = field(default_factory=list)
    kept_actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ActionContainer:
    actions: list[Any]
    owner: dict[str, Any]
    key: str


def _repo_root_from_arg(project_root: str | None) -> Path:
    return Path(project_root).resolve() if project_root else REPO_ROOT


def _frontmatter_action_containers(metadata: dict[str, Any]) -> list[ActionContainer]:
    containers: list[ActionContainer] = []

    top_level = metadata.get("actions")
    if isinstance(top_level, list):
        containers.append(ActionContainer(top_level, metadata, "actions"))

    config = metadata.get("x-augur-config")
    if isinstance(config, dict):
        contributions = config.get("contributions")
        if isinstance(contributions, dict):
            actions = contributions.get("actions")
            if isinstance(actions, list):
                containers.append(ActionContainer(actions, contributions, "actions"))

    return containers


def _action_id(action: dict[str, Any]) -> str:
    value = action.get("id")
    return value.strip() if isinstance(value, str) else ""


def _text(action: dict[str, Any], key: str) -> str:
    value = action.get(key)
    return value.strip() if isinstance(value, str) else ""


def _item_frontmatter(action: dict[str, Any]) -> dict[str, Any]:
    item: dict[str, Any] = {"id": _action_id(action)}
    for key in ("label", "description", "icon", "tags"):
        value = action.get(key)
        if value not in (None, "", []):
            item[key] = value
    return item


def _prompt_body(action: dict[str, Any]) -> str:
    for key in ("prompt", "context", "description", "label"):
        value = _text(action, key)
        if value:
            return f"{value}\n"
    return "Run this prompt.\n"


def _command_body(action: dict[str, Any]) -> str:
    label = _text(action, "label") or _action_id(action)
    description = _text(action, "description")
    lines = [f"# {label}", ""]
    if description:
        lines.extend([description, ""])

    command = _text(action, "command")
    if command:
        lines.extend([f"Run `{command}` from the CLI session.", ""])

    mcp_tool = _text(action, "mcp_tool")
    if mcp_tool:
        lines.extend([f"MCP tool: `{mcp_tool}`", ""])

    mcp_tools = action.get("mcp_tools")
    if isinstance(mcp_tools, list):
        tools = [tool for tool in mcp_tools if isinstance(tool, str) and tool]
        if tools:
            lines.extend(["MCP tools:", *[f"- `{tool}`" for tool in tools], ""])

    endpoint = _text(action, "endpoint")
    if endpoint:
        lines.extend([f"Dashboard endpoint: `{endpoint}`", ""])

    context = _text(action, "context")
    if context:
        lines.extend([context, ""])

    return "\n".join(lines).rstrip() + "\n"


def _write_or_report(
    target: Path,
    metadata: dict[str, Any],
    body: str,
    *,
    dry_run: bool,
    summary: MigrationSummary,
    kind: str,
    repo_root: Path,
) -> None:
    relative = target.relative_to(repo_root).as_posix()
    if target.exists():
        summary.existing_targets.append(relative)
        return

    if dry_run:
        if kind == "prompt":
            summary.created_prompts += 1
        else:
            summary.created_commands += 1
        print(f"    would create {relative}")
        return

    write_frontmatter(target, metadata, body)
    if kind == "prompt":
        summary.created_prompts += 1
    else:
        summary.created_commands += 1
    print(f"    created {relative}")


def _migrate_action(
    skill_dir: Path,
    action: dict[str, Any],
    *,
    dry_run: bool,
    summary: MigrationSummary,
    repo_root: Path,
) -> bool:
    action_id = _action_id(action)
    if not action_id or not VALID_ID.match(action_id):
        summary.warnings.append(f"{skill_dir.name}: invalid action id {action_id!r}; kept")
        return False

    dispatch = _text(action, "dispatch")
    if not dispatch and (_text(action, "type") == "modal" or _text(action, "modal")):
        summary.kept_actions.append(f"{skill_dir.name}:{action_id}")
        return False

    metadata = _item_frontmatter(action)

    if dispatch in PROMPT_DISPATCHES:
        target = skill_dir / "prompts" / f"{action_id}.md"
        _write_or_report(
            target,
            metadata,
            _prompt_body(action),
            dry_run=dry_run,
            summary=summary,
            kind="prompt",
            repo_root=repo_root,
        )
        return True

    if dispatch in COMMAND_DISPATCHES:
        target = skill_dir / "commands" / f"{action_id}.md"
        command_metadata = {**metadata, "x-augur-export-command": True}
        _write_or_report(
            target,
            command_metadata,
            _command_body(action),
            dry_run=dry_run,
            summary=summary,
            kind="command",
            repo_root=repo_root,
        )
        return True

    summary.kept_actions.append(f"{skill_dir.name}:{action_id}")
    if dispatch and dispatch not in MODAL_DISPATCHES:
        summary.warnings.append(
            f"{skill_dir.name}: unknown dispatch {dispatch!r} for {action_id!r}; kept"
        )
    return False


def migrate_skill(skill_md: Path, *, dry_run: bool, summary: MigrationSummary, repo_root: Path) -> bool:
    metadata, body = parse_frontmatter(skill_md, include_sidecar_config=False)
    if not metadata:
        return False

    containers = _frontmatter_action_containers(metadata)
    if not containers:
        return False

    changed = False
    for container in containers:
        kept: list[Any] = []
        for action in container.actions:
            if not isinstance(action, dict):
                kept.append(action)
                continue
            migrated = _migrate_action(
                skill_md.parent,
                action,
                dry_run=dry_run,
                summary=summary,
                repo_root=repo_root,
            )
            if migrated:
                changed = True
            else:
                kept.append(action)

        if kept:
            container.owner[container.key] = kept
        elif changed:
            container.owner.pop(container.key, None)

    if not changed:
        return False

    relative = skill_md.relative_to(repo_root).as_posix()
    if dry_run:
        print(f"  would update {relative}")
    else:
        write_frontmatter(skill_md, metadata, body)
        print(f"  updated {relative}")

    summary.changed_skills += 1
    return True


def migrate_repository(project_root: Path, *, dry_run: bool) -> MigrationSummary:
    skills_dir = project_root / "project-brain" / "capabilities" / "skills"
    summary = MigrationSummary()
    skill_mds = sorted(skills_dir.glob("*/SKILL.md"))
    summary.scanned = len(skill_mds)

    print(f"Scanning {summary.scanned} SKILL.md files")
    for skill_md in skill_mds:
        migrate_skill(skill_md, dry_run=dry_run, summary=summary, repo_root=project_root)

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="preview without writing")
    parser.add_argument("--project-root", help="repository root, defaults to this checkout")
    args = parser.parse_args()

    project_root = _repo_root_from_arg(args.project_root)
    summary = migrate_repository(project_root, dry_run=args.dry_run)

    verb = "Would update" if args.dry_run else "Updated"
    create_verb = "would create" if args.dry_run else "created"
    print(
        f"\n{verb} {summary.changed_skills}/{summary.scanned} skills; "
        f"{create_verb} {summary.created_prompts} prompts and "
        f"{summary.created_commands} commands."
    )
    if summary.existing_targets:
        print(f"Preserved {len(summary.existing_targets)} existing prompt/command files:")
        for item in summary.existing_targets:
            print(f"  {item}")
    if summary.kept_actions:
        print(f"Kept {len(summary.kept_actions)} modal/unknown actions:")
        for item in summary.kept_actions:
            print(f"  {item}")
    if summary.warnings:
        print("Warnings:", file=sys.stderr)
        for warning in summary.warnings:
            print(f"  {warning}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
