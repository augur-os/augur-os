#!/usr/bin/env python3
"""Augur-specific nightly checks beyond standard CI."""


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


def iter_skill_dirs(root: Path):
    plugins_root = root / "plugins"
    if not plugins_root.exists():
        return

    for bundle_dir in sorted(plugins_root.iterdir()):
        if not bundle_dir.is_dir() or bundle_dir.name.startswith("."):
            continue
        skills_dir = bundle_dir / "skills"
        if not skills_dir.exists():
            continue
        for skill_dir in sorted(skills_dir.iterdir()):
            if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                yield bundle_dir.name, skill_dir


def check_skill_md_length(root: Path) -> list[str]:
    """All SKILL.md files should be <100 lines."""
    issues = []
    for skill_md in root.rglob("plugins/*/skills/*/SKILL.md"):
        if "node_modules" in str(skill_md):
            continue
        lines = len(skill_md.read_text().splitlines())
        if lines > 100:
            rel = skill_md.relative_to(root)
            issues.append(f"{rel}: {lines} lines (max 100)")
    return issues


def check_dashboard_registration(root: Path) -> list[str]:
    """All skills with dashboard files should have augur.yaml registration."""
    issues = []
    for bundle, skill_dir in iter_skill_dirs(root):
        canonical_dashboard = skill_dir / "augur" / "dashboard"
        legacy_dashboard = skill_dir / "dashboard"
        augur_yaml = skill_dir / "augur.yaml"

        has_dashboard = canonical_dashboard.exists() or legacy_dashboard.exists()
        if has_dashboard and not augur_yaml.exists():
            issues.append(
                f"plugins/{bundle}/skills/{skill_dir.name}: has dashboard content but no augur.yaml registration"
            )
    return issues


def check_forbidden_augur_data(root: Path) -> list[str]:
    """augur/data/ is a forbidden path — user-editable content lives in get_vault_dir() (ADR-270)."""
    issues = []
    for bundle, skill_dir in iter_skill_dirs(root):
        forbidden = skill_dir / "augur" / "data"
        if forbidden.exists():
            issues.append(
                f"plugins/{bundle}/skills/{skill_dir.name}/augur/data/ exists — "
                "this is a forbidden path, move content to the vault (get_vault_dir())"
            )
    return issues


def main():
    root = get_project_root()

    checks = [
        ("SKILL.md line count (<100)", check_skill_md_length),
        ("Dashboard registration (augur.yaml)", check_dashboard_registration),
        ("Forbidden augur/data/ directories", check_forbidden_augur_data),
    ]

    total_issues = 0
    for name, check_fn in checks:
        print(f"\n## {name}")
        issues = check_fn(root)
        if issues:
            for issue in issues:
                print(f"  - {issue}")
            total_issues += len(issues)
        else:
            print("  All checks pass")

    print(f"\nTotal issues: {total_issues}")
    return 1 if total_issues > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
