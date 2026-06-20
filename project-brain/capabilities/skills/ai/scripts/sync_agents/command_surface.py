"""Inventory Augur slash command surfaces across local clients."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

NO_DUPLICATES_REPORT = "No duplicate Augur command surfaces found."

_SOURCE_CLASS_ORDER = {
    "claude-code-project": 0,
    "cowork-build": 1,
    "cowork-upload": 2,
}


@dataclass(frozen=True)
class CommandSurfaceEntry:
    command: str
    source_class: str
    path: Path


@dataclass(frozen=True)
class CommandDuplicate:
    command: str
    suggested_owner: str
    sources: list[CommandSurfaceEntry]


def _source_class_sort_key(source_class: str) -> tuple[int, str]:
    return (_SOURCE_CLASS_ORDER.get(source_class, len(_SOURCE_CLASS_ORDER)), source_class)


def _entry_sort_key(entry: CommandSurfaceEntry) -> tuple[tuple[int, str], str, str]:
    return (_source_class_sort_key(entry.source_class), entry.command, str(entry.path))


def _command_files(commands_dir: Path) -> list[Path]:
    if not commands_dir.is_dir():
        return []
    return sorted(path for path in commands_dir.glob("*.md") if path.is_file())


def _entries_from_dir(commands_dir: Path, source_class: str) -> list[CommandSurfaceEntry]:
    return [
        CommandSurfaceEntry(command=path.stem, source_class=source_class, path=path)
        for path in _command_files(commands_dir)
    ]


def inventory_augur_command_surfaces(
    project_root: Path,
    *,
    cowork_plugin_dirs: Iterable[Path] | None = None,
) -> list[CommandSurfaceEntry]:
    """Collect known Augur command surfaces from Claude Code and Cowork paths."""
    root = Path(project_root)
    entries: list[CommandSurfaceEntry] = []
    entries.extend(_entries_from_dir(root / ".claude" / "commands", "claude-code-project"))
    entries.extend(
        _entries_from_dir(
            root / "build" / "cowork" / "plugins" / "augur" / "commands",
            "cowork-build",
        )
    )

    for cowork_dir in cowork_plugin_dirs or ():
        cowork_root = Path(cowork_dir)
        entries.extend(
            _entries_from_dir(
                cowork_root
                / "marketplaces"
                / "local-desktop-app-uploads"
                / "augur"
                / "commands",
                "cowork-upload",
            )
        )

    return sorted(entries, key=_entry_sort_key)


def find_duplicate_commands(entries: Iterable[CommandSurfaceEntry]) -> list[CommandDuplicate]:
    by_command: dict[str, list[CommandSurfaceEntry]] = defaultdict(list)
    for entry in entries:
        by_command[entry.command].append(entry)

    duplicates: list[CommandDuplicate] = []
    for command in sorted(by_command):
        sources = sorted(by_command[command], key=_entry_sort_key)
        source_classes = sorted({source.source_class for source in sources})
        if len(sources) < 2:
            continue
        suggested_owner = (
            "claude-code-project"
            if "claude-code-project" in source_classes
            else source_classes[0]
        )
        duplicates.append(
            CommandDuplicate(
                command=command,
                suggested_owner=suggested_owner,
                sources=sources,
            )
        )

    return duplicates


def format_duplicate_report(duplicates: Iterable[CommandDuplicate]) -> str:
    duplicate_list = list(duplicates)
    if not duplicate_list:
        return NO_DUPLICATES_REPORT

    sections: list[str] = []
    for duplicate in duplicate_list:
        lines = [
            f"DUPLICATE /{duplicate.command}",
            f"owner: {duplicate.suggested_owner}",
        ]
        lines.extend(f"- {source.source_class}: {source.path}" for source in duplicate.sources)
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


__all__ = [
    "CommandDuplicate",
    "CommandSurfaceEntry",
    "NO_DUPLICATES_REPORT",
    "find_duplicate_commands",
    "format_duplicate_report",
    "inventory_augur_command_surfaces",
]
