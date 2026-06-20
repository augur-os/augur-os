#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.lib.mvp_staging_migration import migrate_non_mvp_skills


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    report = migrate_non_mvp_skills(args.project_root.resolve())
    print(f"kept={len(report['kept'])} moved={len(report['moved'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
