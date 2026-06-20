#!/usr/bin/env python3
"""CI check: verify first-level dirs in managed locations match skill names.

Exit 0 if all dirs are valid, exit 1 if any violations found.

Spec: docs/superpowers/specs/2026-03-23-dir-alignment-design.md
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.lib.dir_alignment import get_managed_locations, validate_dir_name


def main() -> int:
    locations = get_managed_locations()
    if not locations:
        print("No managed locations configured in project.yaml")
        return 0

    violations: list[str] = []
    for loc in locations:
        if not loc.path.is_dir():
            continue
        for entry in sorted(loc.path.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            if not validate_dir_name(loc, entry.name):
                violations.append(f"  {loc.path.name}/{entry.name}")

    if violations:
        print(f"Directory alignment violations ({len(violations)}):")
        for v in violations:
            print(v)
        return 1

    print("All directories aligned with skill names")
    return 0


if __name__ == "__main__":
    sys.exit(main())
