#!/usr/bin/env python3
"""Prune a repo checkout down to the enabled skills for a release target."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from src.lib.release_workspace import prune_release_workspace


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--release-target",
        choices=("mvp", "r1", "r2", "r3", "r4"),
        required=True,
    )
    args = parser.parse_args()

    report = prune_release_workspace(args.project_root, args.release_target)
    print(f"Enabled skills: {len(report['enabled'])}")
    print(f"Removed skills: {len(report['removed'])}")


if __name__ == "__main__":
    main()
