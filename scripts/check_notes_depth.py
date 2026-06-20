#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.paths import get_vault_dir  # noqa: E402

CONFIG_DIR_NAMES = {"config", "_config", "_templates"}
DEFAULT_ALLOWED_DEEP_DIRS = {
    Path("augur/platform-admin/setup/ollama"),
    Path("health/virtual-doctor/medications"),
    Path("health/virtual-doctor/symptoms"),
    Path("lifestyle/apple/reminders"),
    Path("lifestyle/apple/voice-memos"),
    Path("lifestyle/recipe-manager/recipes/perfected"),
    Path("lifestyle/recipe-manager/recipes/to-try"),
    Path("venture/content/linkedin/assets"),
    Path("venture/content/linkedin/context"),
    Path("venture/content/linkedin/posts"),
}


@dataclass(frozen=True, order=True)
class NotesDepthIssue:
    kind: str
    path: Path
    message: str


def _has_hidden_part(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


def _is_allowed_deep_dir(path: Path, allowed_deep_dirs: set[Path]) -> bool:
    return any(path == allowed or path.is_relative_to(allowed) for allowed in allowed_deep_dirs)


def check_notes_depth(
    notes_root: Path,
    *,
    allowed_deep_dirs: set[Path] | None = None,
    min_skinny_dir_depth: int = 3,
) -> list[NotesDepthIssue]:
    if not notes_root.exists():
        return [
            NotesDepthIssue(
                kind="missing_notes_root",
                path=Path("."),
                message="Notes root does not exist.",
            )
        ]
    if not notes_root.is_dir():
        return [
            NotesDepthIssue(
                kind="invalid_notes_root",
                path=Path("."),
                message="Notes root is not a directory.",
            )
        ]

    allowed = allowed_deep_dirs if allowed_deep_dirs is not None else DEFAULT_ALLOWED_DEEP_DIRS
    files = sorted(
        path
        for path in notes_root.rglob("*")
        if path.is_file() and not _has_hidden_part(path.relative_to(notes_root))
    )
    issues: set[NotesDepthIssue] = set()

    for file_path in files:
        rel_path = file_path.relative_to(notes_root)
        if "notes" in rel_path.parts:
            issues.add(
                NotesDepthIssue(
                    kind="repeated_notes_layer",
                    path=rel_path,
                    message="Path contains a nested 'notes' folder under the notes root.",
                )
            )
        if any(part in CONFIG_DIR_NAMES for part in rel_path.parts):
            issues.add(
                NotesDepthIssue(
                    kind="config_under_notes",
                    path=rel_path,
                    message="Config or template path lives under notes.",
                )
            )

    file_counts_by_dir: dict[Path, int] = {}
    for file_path in files:
        rel_path = file_path.relative_to(notes_root)
        for parent in rel_path.parents:
            if parent == Path("."):
                continue
            file_counts_by_dir[parent] = file_counts_by_dir.get(parent, 0) + 1

    for rel_dir, file_count in file_counts_by_dir.items():
        if len(rel_dir.parts) < min_skinny_dir_depth:
            continue
        if _is_allowed_deep_dir(rel_dir, allowed):
            continue
        if file_count == 1:
            issues.add(
                NotesDepthIssue(
                    kind="skinny_deep_dir",
                    path=rel_dir,
                    message=f"Directory has exactly one file descendant at depth {len(rel_dir.parts)}.",
                )
            )

    return sorted(issues)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check notes folder depth against the strict Obsidian contract.")
    parser.add_argument("--notes-root", type=Path, default=get_vault_dir() / "notes")
    args = parser.parse_args()

    issues = check_notes_depth(args.notes_root)
    if issues:
        print("Strict notes-depth issues:")
        for issue in issues:
            print(f"- {issue.kind}: {issue.path.as_posix()} - {issue.message}")
        return 1

    print("Notes folder depth matches strict contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
