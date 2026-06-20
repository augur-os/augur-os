#!/usr/bin/env python3
"""Augur-aware refactoring — update all references when renaming a skill."""


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import sys

sys.path.insert(0, '.')

from pathlib import Path
from src.config.paths import get_project_root

try:
    from src.logging import get_entity_logger
except ImportError:
    import logging

    def get_entity_logger(name: str):
        return logging.getLogger(name)


logger = get_entity_logger("platform-admin")


def find_skill_references(root: Path, old_name: str) -> list[tuple[Path, int, str]]:
    """Find all references to a skill name in the codebase."""
    matches = []
    patterns = [
        f"skills/{old_name}",
        f"skill:{old_name}",
        f"skill_{old_name}",
        f"crew/{old_name}",
        f"services/{old_name}",
        f"apps/{old_name}",
        f"orchestrator/{old_name}",
        f"plugins/{old_name}",
    ]

    extensions = {".py", ".ts", ".tsx", ".yaml", ".yml", ".md", ".json"}
    skip_dirs = {"node_modules", ".git", "__pycache__", ".next", "runtime"}

    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix not in extensions:
            continue
        if any(skip in str(file_path) for skip in skip_dirs):
            continue

        try:
            content = file_path.read_text(errors="ignore")
            for line_num, line in enumerate(content.splitlines(), 1):
                for pattern in patterns:
                    if pattern in line:
                        matches.append((file_path, line_num, line.strip()))
                        break
        except (PermissionError, OSError):
            continue

    return matches


def rename_skill(root: Path, old_name: str, new_name: str, dry_run: bool = True) -> int:
    """Rename a skill across the entire codebase."""
    matches = find_skill_references(root, old_name)

    if not matches:
        logger.info(f"No references to '{old_name}' found.")
        return 0

    logger.info(f"Found {len(matches)} references to '{old_name}':")
    for path, line_num, line in matches:
        rel = path.relative_to(root)
        logger.debug(f"  {rel}:{line_num}: {line[:80]}")

    if dry_run:
        logger.info(f"Dry run — would update {len(matches)} references. Use --apply to execute.")
        return len(matches)

    # Apply replacements
    updated_files = set()
    for path, _, _ in matches:
        if path in updated_files:
            continue
        content = path.read_text()
        new_content = content.replace(f"skills/{old_name}", f"skills/{new_name}")
        new_content = new_content.replace(f"skill:{old_name}", f"skill:{new_name}")
        new_content = new_content.replace(f"skill_{old_name}", f"skill_{new_name}")
        new_content = new_content.replace(f"crew/{old_name}", f"crew/{new_name}")
        new_content = new_content.replace(f"services/{old_name}", f"services/{new_name}")
        new_content = new_content.replace(f"apps/{old_name}", f"apps/{new_name}")
        new_content = new_content.replace(f"plugins/{old_name}", f"plugins/{new_name}")
        if new_content != content:
            path.write_text(new_content)
            updated_files.add(path)

    logger.info(f"Updated {len(updated_files)} files.")
    return len(updated_files)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Augur skill refactoring tool")
    parser.add_argument("old_name", help="Current skill name")
    parser.add_argument("new_name", help="New skill name")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry run)")

    args = parser.parse_args()
    root = get_project_root()
    rename_skill(root, args.old_name, args.new_name, dry_run=not args.apply)


if __name__ == "__main__":
    main()
