#!/usr/bin/env python3
"""
Add data_dir to all plugin dashboard.yaml files.

ADR-013: Each skill must have data_dir configured for TypeScript strict mode.

Usage:
    python3 add_data_dir_to_dashboards.py [--dry-run]
"""

import sys
from pathlib import Path

import yaml


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).resolve().parents[3]


def get_plugin_bundles() -> list[str]:
    """Get list of plugin bundles to scan."""
    return [
        'crew',
        'orchestrator',
        'services',
        'apps',
    ]


def add_data_dir_to_dashboard(dashboard_path: Path, bundle: str, skill: str, dry_run: bool) -> bool:
    """
    Add data_dir to a dashboard.yaml file if not present.

    Returns True if modified, False otherwise.
    """
    try:
        with open(dashboard_path, 'r') as f:
            content = f.read()

        # Parse YAML
        data = yaml.safe_load(content) or {}

        # Check if data_dir already exists
        if 'data_dir' in data:
            _out(f"  [SKIP] Already has data_dir: {dashboard_path}")
            return False

        # Canonical data_dir uses the skill id.
        data_dir = skill

        if dry_run:
            _out(f"  [DRY-RUN] Would add data_dir: {data_dir} to {dashboard_path}")
            return True

        # Add data_dir after any existing top-level keys or at the beginning
        # We'll insert it after 'name' and 'description' if they exist
        lines = content.split('\n')
        new_lines = []
        inserted = False

        for i, line in enumerate(lines):
            new_lines.append(line)

            # Insert after description or name (whichever comes last at top level)
            if not inserted and not line.startswith(' ') and not line.startswith('#'):
                if line.startswith('description:') or (
                    line.startswith('name:') and i + 1 < len(lines) and not lines[i + 1].startswith('description:')
                ):
                    # Find the end of the multi-line value if it's a block scalar
                    j = i + 1
                    while j < len(lines) and (lines[j].startswith(' ') or lines[j].strip() == ''):
                        new_lines.append(lines[j])
                        j += 1

                    # Insert data_dir
                    new_lines.append(f"\ndata_dir: {data_dir}")
                    inserted = True

                    # Continue from where we left off
                    for k in range(j, len(lines)):
                        new_lines.append(lines[k])
                    break

        # If we couldn't find a good insertion point, add at the beginning
        if not inserted:
            new_content = f"data_dir: {data_dir}\n\n" + content
        else:
            new_content = '\n'.join(new_lines)

        # Write back
        with open(dashboard_path, 'w') as f:
            f.write(new_content)

        _out(f"  [ADDED] data_dir: {data_dir} to {dashboard_path}")
        return True

    except Exception as e:
        _out(f"  [ERROR] Failed to process {dashboard_path}: {e}")
        return False


def main():
    dry_run = '--dry-run' in sys.argv

    if dry_run:
        _out("=== DRY RUN MODE - No changes will be made ===\n")

    project_root = get_project_root()
    plugins_dir = project_root / 'plugins'

    if not plugins_dir.exists():
        _out(f"ERROR: Plugins directory not found: {plugins_dir}")
        sys.exit(1)

    _out(f"Scanning plugins in: {plugins_dir}\n")

    modified_count = 0
    skipped_count = 0
    missing_dashboard = []

    for bundle in get_plugin_bundles():
        bundle_dir = plugins_dir / bundle
        skills_dir = bundle_dir / 'skills'

        if not skills_dir.exists():
            continue

        _out(f"Bundle: {bundle}")

        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith('.'):
                continue

            skill = skill_dir.name
            dashboard_path = skill_dir / 'dashboard.yaml'

            if not dashboard_path.exists():
                missing_dashboard.append(f"{bundle}/{skill}")
                continue

            result = add_data_dir_to_dashboard(dashboard_path, bundle, skill, dry_run)
            if result:
                modified_count += 1
            else:
                skipped_count += 1

        _out()

    # Summary
    _out("=== Summary ===")
    _out(f"Modified: {modified_count}")
    _out(f"Skipped (already has data_dir): {skipped_count}")

    if missing_dashboard:
        _out(f"\nSkills without dashboard.yaml ({len(missing_dashboard)}):")
        for skill in missing_dashboard:
            _out(f"  - {skill}")

    if dry_run:
        _out("\nThis was a dry run. Run without --dry-run to make changes.")


if __name__ == '__main__':
    main()
