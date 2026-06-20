#!/usr/bin/env python3
"""Data migration safety — backup, validate, detect orphans."""


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

import shutil
from pathlib import Path
from datetime import datetime
import yaml
from src.config.paths import get_project_root, get_runtime_dir

try:
    from src.logging import get_entity_logger
except ImportError:
    import logging

    def get_entity_logger(name: str):
        return logging.getLogger(name)


logger = get_entity_logger("platform-admin")


def backup_file(file_path: Path) -> Path:
    """Create a timestamped backup before editing."""
    backup_dir = get_runtime_dir() / "backups" / "data-migrations"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    rel_path = file_path.relative_to(get_project_root())
    backup_name = f"{rel_path.stem}_{timestamp}{rel_path.suffix}"
    backup_path = backup_dir / backup_name

    shutil.copy2(file_path, backup_path)
    logger.info(f"Backed up: {rel_path} -> {backup_path.relative_to(get_project_root())}")
    return backup_path


def validate_yaml(file_path: Path) -> list[str]:
    """Validate YAML file after editing."""
    issues = []
    try:
        with open(file_path) as f:
            data = yaml.safe_load(f)
        if data is None:
            issues.append("File is empty YAML")
    except yaml.YAMLError as e:
        issues.append(f"YAML parse error: {e}")
    return issues


def detect_orphaned_data(root: Path) -> list[str]:
    """Detect colocated data directories that don't match any skill code (ADR-083)."""
    issues = []
    plugins_root = root / "plugins"

    if not plugins_root.exists():
        return ["plugins/ directory not found"]

    for bundle_dir in sorted(plugins_root.iterdir()):
        if not bundle_dir.is_dir() or bundle_dir.name.startswith("."):
            continue

        skills_dir = bundle_dir / "skills"
        if not skills_dir.exists():
            continue

        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue

            data_dir = skill_dir / "data"
            if data_dir.exists():
                # Check if skill has any code (SKILL.md, scripts/, mcp/, etc.)
                has_code = any(
                    (skill_dir / f).exists() for f in ["SKILL.md", "scripts", "mcp", "dashboard", "dashboard.yaml"]
                )
                if not has_code:
                    file_count = sum(1 for _ in data_dir.rglob("*") if _.is_file())
                    issues.append(
                        f"Orphaned data: plugins/{bundle_dir.name}/skills/{skill_dir.name}/data/ ({file_count} files) — no matching skill code"
                    )

    return issues


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Data migration safety tools")
    sub = parser.add_subparsers(dest="command")

    backup_cmd = sub.add_parser("backup", help="Backup a file before editing")
    backup_cmd.add_argument("file", help="File to backup")

    validate_cmd = sub.add_parser("validate", help="Validate YAML after editing")
    validate_cmd.add_argument("file", help="YAML file to validate")

    sub.add_parser("orphans", help="Detect orphaned data directories")

    args = parser.parse_args()
    root = get_project_root()

    if args.command == "backup":
        backup_file(Path(args.file).resolve())
    elif args.command == "validate":
        issues = validate_yaml(Path(args.file).resolve())
        if issues:
            for i in issues:
                print(f"  ERROR: {i}")
            sys.exit(1)
        else:
            print("  YAML valid")
    elif args.command == "orphans":
        issues = detect_orphaned_data(root)
        if issues:
            print("Orphaned data directories:")
            for i in issues:
                print(f"  - {i}")
            sys.exit(1)
        else:
            print("No orphaned data directories found")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
