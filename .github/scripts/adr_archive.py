#!/usr/bin/env python3
"""Archive and extract Implemented ADRs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.lib.adr_utils import (  # noqa: E402
    archive_eligible_adrs,
    extract_archived_adr,
    get_adr_dir,
    rebuild_archive_index,
)


def _parse_adr_number(value: str) -> int:
    cleaned = value.upper().removeprefix("ADR-")
    try:
        return int(cleaned)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid ADR number: {value}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive or extract Implemented ADRs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    archive_parser = subparsers.add_parser("archive-implemented", help="Move Implemented ADRs into zip bundles")
    archive_parser.add_argument("--dry-run", action="store_true", help="Report what would be archived")
    archive_parser.add_argument("--range-size", type=int, default=100, help="ADR numbers per zip bundle")
    archive_parser.add_argument(
        "--adr",
        action="append",
        type=_parse_adr_number,
        default=None,
        help="Archive only the given ADR number; may be passed more than once",
    )

    extract_parser = subparsers.add_parser("extract", help="Extract one archived ADR to runtime or a chosen directory")
    extract_parser.add_argument("adr", type=_parse_adr_number, help="ADR number, e.g. ADR-163 or 163")
    extract_parser.add_argument("--out", type=Path, default=None, help="Directory to extract into")

    subparsers.add_parser(
        "rebuild-index",
        help="Regenerate the archived rows in adrs-index.json by re-walking each archive zip (ADR-642)",
    )

    args = parser.parse_args()
    decisions_dir = get_adr_dir()

    if args.command == "archive-implemented":
        result = archive_eligible_adrs(
            decisions_dir,
            range_size=args.range_size,
            dry_run=args.dry_run,
            adr_numbers=args.adr,
        )
        action = "Would archive" if args.dry_run else "Archived"
        numbers = ", ".join(f"ADR-{number:03d}" for number in result.archived_numbers) or "none"
        print(f"{action}: {numbers}")
        print(f"Index: {result.index_path}")
        for archive_path in result.archive_paths:
            print(f"Bundle: {archive_path}")
        return 0

    if args.command == "extract":
        extracted = extract_archived_adr(decisions_dir, args.adr, destination_dir=args.out)
        print(extracted)
        return 0

    if args.command == "rebuild-index":
        index_path = rebuild_archive_index(decisions_dir)
        print(f"Rebuilt: {index_path}")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
