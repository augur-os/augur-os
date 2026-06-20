#!/usr/bin/env python3
"""Snapshot skill data directories before major operations."""


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

import json
import shutil
from pathlib import Path
from datetime import datetime
from src.config.paths import get_project_root, get_runtime_dir, get_skill_data_dir

try:
    from src.logging import get_entity_logger
except ImportError:
    import logging

    def get_entity_logger(name: str):
        return logging.getLogger(name)


logger = get_entity_logger("platform-admin")


def _discover_skill_data_dirs(root: Path) -> list[Path]:
    """Discover vault-backed skill data directories."""
    plugin_root = root / "plugins"
    if not plugin_root.exists():
        return []

    data_dirs: list[Path] = []
    for skill_dir in plugin_root.glob("*/skills/*"):
        if not skill_dir.is_dir():
            continue
        try:
            data_dirs.append(get_skill_data_dir(skill_dir.name))
        except Exception:
            legacy = skill_dir / "data"
            if legacy.exists():
                data_dirs.append(legacy)
    return sorted(data_dirs)


def create_snapshot(label: str = "") -> Path:
    """Create a timestamped snapshot of skill data directories."""
    root = get_project_root()
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    snapshot_name = f"pre-{label}-{timestamp}" if label else f"snapshot-{timestamp}"
    backup_dir = get_runtime_dir() / "backups" / snapshot_name

    logger.info(f"Creating snapshot: {backup_dir.relative_to(root)}")
    backup_dir.mkdir(parents=True, exist_ok=True)

    data_dirs = _discover_skill_data_dirs(root)
    if not data_dirs:
        raise FileNotFoundError("No skill data directories found under plugins/*/skills/*/(augur/data|data)")

    copied_files = 0
    rel_paths: list[str] = []
    for source_dir in data_dirs:
        rel = source_dir.relative_to(root)
        destination = backup_dir / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_dir, destination, dirs_exist_ok=True)
        rel_paths.append(str(rel))
        copied_files += sum(1 for item in destination.rglob("*") if item.is_file())

    manifest = {
        "schema_version": 1,
        "mode": "skill_data",
        "created_at": timestamp,
        "data_dirs": rel_paths,
        "file_count": copied_files,
    }
    (backup_dir / "manifest.json").write_text(f"{json.dumps(manifest, indent=2)}\n", encoding="utf-8")
    logger.info(f"Snapshot complete: {copied_files} files across {len(rel_paths)} data directories")
    return backup_dir


def list_snapshots() -> list[Path]:
    """List available snapshots."""
    backup_dir = get_runtime_dir() / "backups"
    if not backup_dir.exists():
        return []
    return sorted([d for d in backup_dir.iterdir() if d.is_dir()])


def restore_snapshot(snapshot_path: Path) -> None:
    """Restore skill data directories from a snapshot."""
    root = get_project_root()

    if not snapshot_path.exists():
        logger.error(f"Snapshot not found: {snapshot_path}")
        sys.exit(1)

    logger.info(f"Restoring from: {snapshot_path.name}")
    manifest_path = snapshot_path / "manifest.json"

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("mode") == "skill_data":
            data_dirs = manifest.get("data_dirs", [])
            logger.warning("Restoring snapshot will overwrite current skill data directories")

            restored = 0
            for rel in data_dirs:
                source_dir = snapshot_path / rel
                target_dir = root / rel
                if not source_dir.exists():
                    logger.warning(f"Skipping missing snapshot directory: {rel}")
                    continue
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                target_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source_dir, target_dir)
                restored += 1

            logger.info(f"Restore complete: {restored} data directories restored.")
            return

    # Legacy fallback: restore from repository-level data snapshot format.
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    logger.warning("Using legacy restore mode for repository-level data snapshot")
    for item in snapshot_path.iterdir():
        if item.name in {"runtime", "manifest.json"}:
            continue
        target = data_dir / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)

    logger.info("Legacy restore complete.")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Data backup/restore tool")
    sub = parser.add_subparsers(dest="command")

    create_cmd = sub.add_parser("create", help="Create a snapshot")
    create_cmd.add_argument("--label", default="", help="Label for the snapshot")

    sub.add_parser("list", help="List available snapshots")

    restore_cmd = sub.add_parser("restore", help="Restore from a snapshot")
    restore_cmd.add_argument("name", help="Snapshot directory name")

    args = parser.parse_args()

    if args.command == "create":
        create_snapshot(args.label)
    elif args.command == "list":
        snapshots = list_snapshots()
        if snapshots:
            print("Available snapshots:")
            for s in snapshots:
                print(f"  {s.name}")
        else:
            print("No snapshots found.")
    elif args.command == "restore":
        snapshot_path = get_runtime_dir() / "backups" / args.name
        restore_snapshot(snapshot_path)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
