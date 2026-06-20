#!/usr/bin/env python3
from pathlib import Path
import sys


def find_augur_root():
    # 1. Check if we are already inside an Augur directory
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "apps" / "dashboard").exists() and (parent / "plugins" / "augur-mcp").exists():
            return parent

    # 2. Check common locations
    common_roots = [
        Path.home() / "Projects" / "Augur",
        Path.home() / "Augur",
        Path.home() / "augur",
        Path.home() / "Projects" / "augur",
    ]

    for root in common_roots:
        if root.exists() and (root / "apps" / "dashboard").exists():
            return root

    return None


if __name__ == "__main__":
    root = find_augur_root()
    if root:
        sys.stdout.write(f"{root}\n")
