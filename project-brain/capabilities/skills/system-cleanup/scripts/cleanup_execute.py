#!/usr/bin/env python3
"""Execute disk cleanup for one category by moving items to the OS Trash.

Safety contract (see SKILL.md):
- Reversible by design: every removal goes through send2trash (OS Trash),
  never ``rm -rf`` / ``shutil.rmtree`` / ``unlink``. There is no hard-delete
  mode in this skill.
- Confirmation-gated: without ``--confirm`` this is a dry run that reports
  what would be trashed and refuses to touch anything.
- Item-scoped: only items the category scan itself enumerates are eligible.
  ``--items`` narrows execution to an explicit subset; paths outside the scan
  result are rejected, and the category ROOT is never removed.
- Protected paths (the Augur repo, vault/documents stores, ~/Documents, the
  home dir, anything outside home) are skipped and reported.
- The ``trash`` category is report-only — emptying the OS Trash is not
  reversible, so this tool refuses it even with ``--confirm``.

Usage:
    uv run python cleanup_execute.py --category browser-caches            # dry run
    uv run python cleanup_execute.py --category browser-caches --confirm  # trash
    uv run python cleanup_execute.py --category large-files \
        --items ~/Downloads/big.iso --confirm
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cleanup_common  # noqa: E402
from cleanup_common import (  # noqa: E402
    CATEGORY_PATHS,
    COMPUTED_CATEGORIES,
    REPORT_ONLY_CATEGORIES,
    format_bytes,
    is_protected,
    iso_now,
    protected_roots,
)
from cleanup_scan import scan_category  # noqa: E402


def _result(category: str, confirm: bool, **extra) -> dict:
    base = {
        "category": category,
        "confirmed": confirm,
        "executed": False,
        "success": False,
        "reversible": True,
        "trashed": 0,
        "failed": 0,
        "skippedProtected": 0,
        "unknownItems": 0,
        "spaceReclaimed": 0,
        "log": [],
        "timestamp": iso_now(),
    }
    base.update(extra)
    return base


def execute_cleanup(
    category: str,
    items: list[str] | None = None,
    confirm: bool = False,
    limit: int = 500,
    category_paths: dict[str, list[str]] | None = None,
    dev_scan_roots: list[str] | None = None,
    large_file_dirs: list[str] | None = None,
    protected: list[Path] | None = None,
    home: Path | None = None,
) -> dict:
    """Trash scanned items in a category. Dry run unless confirm=True."""
    if category in REPORT_ONLY_CATEGORIES:
        return _result(
            category, confirm,
            message=(
                f"Category '{category}' is report-only: emptying the OS Trash "
                "is not reversible. Use Finder's Empty Trash instead."
            ),
            log=[{"type": "error",
                  "message": f"Refused: '{category}' is report-only."}],
        )

    scan = scan_category(
        category,
        limit=limit,
        category_paths=category_paths,
        dev_scan_roots=dev_scan_roots,
        large_file_dirs=large_file_dirs,
    )
    if scan.get("error"):
        return _result(category, confirm, message=scan["error"],
                       log=[{"type": "error", "message": scan["error"]}])

    candidates = {str(Path(i["path"]).resolve()): i for i in scan.get("items", [])}

    log: list[dict] = []
    unknown = 0
    if items:
        selected: dict[str, dict] = {}
        for raw in items:
            key = str(Path(raw).expanduser().resolve())
            if key in candidates:
                selected[key] = candidates[key]
            else:
                unknown += 1
                log.append({
                    "type": "error",
                    "message": f"Rejected (not in the '{category}' scan): {raw}",
                })
        targets = selected
    else:
        targets = candidates

    roots = protected if protected is not None else protected_roots()

    trashed = 0
    failed = 0
    skipped_protected = 0
    space_reclaimed = 0

    for key, item in targets.items():
        size = item.get("size", 0)
        if is_protected(key, roots=roots, home=home):
            skipped_protected += 1
            log.append({
                "type": "warning",
                "message": f"Skipped (protected path): {key}",
            })
            continue
        if not confirm:
            log.append({
                "type": "info",
                "message": f"[dry-run] Would trash: {key} ({format_bytes(size)})",
            })
            trashed += 1
            space_reclaimed += size
            continue
        outcome = cleanup_common.send_to_trash(key)
        if outcome.get("trashed"):
            trashed += 1
            space_reclaimed += size
            log.append({
                "type": "success",
                "message": f"Trashed (recoverable from OS Trash): {key} "
                           f"({format_bytes(size)})",
            })
        else:
            failed += 1
            log.append({
                "type": "error",
                "message": f"Failed: {key} — {outcome.get('error')}",
            })

    if confirm:
        message = (
            f"Trashed {trashed} item(s), {format_bytes(space_reclaimed)} reclaimed "
            "(recoverable from the OS Trash)."
        )
    else:
        message = (
            f"Dry run only — {trashed} item(s), {format_bytes(space_reclaimed)} "
            "would be trashed. Pass --confirm to move them to the OS Trash."
        )

    return _result(
        category, confirm,
        executed=confirm,
        success=failed == 0 and unknown == 0,
        trashed=trashed,
        failed=failed,
        skippedProtected=skipped_protected,
        unknownItems=unknown,
        spaceReclaimed=space_reclaimed,
        log=log,
        message=message,
    )


def _print_human(result: dict) -> None:
    for entry in result["log"]:
        print(f"  [{entry['type']}] {entry['message']}")
    print(result.get("message", ""))


def main(argv: list[str] | None = None) -> int:
    executable = sorted(set(CATEGORY_PATHS) - REPORT_ONLY_CATEGORIES) + list(
        COMPUTED_CATEGORIES
    )
    parser = argparse.ArgumentParser(
        description="Move scanned disk-waste items to the OS Trash (reversible). "
                    "Dry run unless --confirm is passed.",
    )
    parser.add_argument("--category", required=True,
                        help=f"Category to clean. Executable: {', '.join(executable)}. "
                             "'trash' is report-only.")
    parser.add_argument("--items", nargs="*", default=None,
                        help="Explicit item paths (must come from the category scan)")
    parser.add_argument("--confirm", action="store_true",
                        help="Actually move items to the OS Trash "
                             "(without it: dry run, nothing is touched)")
    parser.add_argument("--limit", type=int, default=500,
                        help="Maximum scanned items eligible (default: 500)")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args(argv)

    result = execute_cleanup(
        args.category, items=args.items, confirm=args.confirm, limit=args.limit,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _print_human(result)
    if args.category in REPORT_ONLY_CATEGORIES or result.get("message", "").startswith(
        "Unknown category"
    ):
        return 2
    return 0 if result["success"] or not args.confirm else 1


if __name__ == "__main__":
    raise SystemExit(main())
