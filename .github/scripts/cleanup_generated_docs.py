#!/usr/bin/env python3
"""
Rotate stale files in docs/generated/.

Deletes dated report files older than --max-age-days (default 14).
Intended to run as part of the nightly CI or repo-sync workflow.
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GENERATED_DIR = PROJECT_ROOT / "docs" / "generated"

# Subdirectories that contain dated files (YYYY-MM-DD in filename)
DATED_SUBDIRS = ["hardening"]

DATE_FORMAT = "%Y-%m-%d"


def find_dated_files(directory: Path) -> list[tuple[Path, datetime]]:
    """Find files with dates in their filenames and parse the date."""
    import re

    date_re = re.compile(r"(\d{4}-\d{2}-\d{2})")
    results = []

    if not directory.is_dir():
        return results

    for f in directory.iterdir():
        if not f.is_file() or f.name.startswith("."):
            continue
        m = date_re.search(f.name)
        if m:
            try:
                file_date = datetime.strptime(m.group(1), DATE_FORMAT)
                results.append((f, file_date))
            except ValueError:
                continue
    return results


def rotate(max_age_days: int, dry_run: bool = False) -> list[Path]:
    """Delete dated files older than max_age_days. Returns list of deleted paths."""
    cutoff = datetime.now() - timedelta(days=max_age_days)
    deleted = []

    for subdir_name in DATED_SUBDIRS:
        subdir = GENERATED_DIR / subdir_name
        for filepath, file_date in find_dated_files(subdir):
            if file_date < cutoff:
                if dry_run:
                    print(f"  [DRY RUN] Would delete: {filepath.relative_to(PROJECT_ROOT)}")
                else:
                    filepath.unlink()
                    print(f"  Deleted: {filepath.relative_to(PROJECT_ROOT)}")
                deleted.append(filepath)

    return deleted


def main():
    parser = argparse.ArgumentParser(description="Rotate stale generated docs")
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=14,
        help="Delete dated files older than this many days (default: 14)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without deleting",
    )
    args = parser.parse_args()

    deleted = rotate(args.max_age_days, dry_run=args.dry_run)

    if deleted:
        action = "Would delete" if args.dry_run else "Deleted"
        print(f"\n{action} {len(deleted)} stale file(s).")
    else:
        print("No stale generated files to clean.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
