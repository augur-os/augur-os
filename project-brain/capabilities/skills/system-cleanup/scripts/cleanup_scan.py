#!/usr/bin/env python3
"""Read-only scan of macOS disk-waste categories. DELETES NOTHING.

Enumerates cleanup candidates per category (browser/app caches, logs, Trash
contents, installer leftovers, Xcode data, AI-tool caches, dev artifacts,
large files) with sizes, sorted largest-first.

Usage:
    uv run python cleanup_scan.py --category all --limit 25
    uv run python cleanup_scan.py --category dev-artifacts --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cleanup_common import (  # noqa: E402
    CATEGORY_PATHS,
    COMPUTED_CATEGORIES,
    DEV_ARTIFACT_NAMES,
    DEV_SCAN_ROOTS,
    LARGE_FILE_SCAN_DIRS,
    LARGE_FILE_THRESHOLD,
    dir_size_fast,
    format_bytes,
    iso_now,
    walk_limited,
)


def _item(path: Path, size: int, kind: str) -> dict:
    st_mtime = path.stat().st_mtime
    return {
        "path": str(path),
        "name": path.name,
        "size": size,
        "lastModified": datetime.fromtimestamp(st_mtime, tz=timezone.utc).isoformat(),
        "type": kind,
    }


def scan_dev_artifacts(limit: int = 100, scan_roots: list[str] | None = None) -> dict:
    """Scan for dev artifact directories (node_modules, .venv, ...)."""
    items: list[dict] = []
    total_size = 0

    for root_pattern in (scan_roots if scan_roots is not None else DEV_SCAN_ROOTS):
        root = Path(os.path.expanduser(root_pattern))
        if not root.is_dir():
            continue
        for entry in walk_limited(root, max_depth=3):
            if entry.name in DEV_ARTIFACT_NAMES and entry.is_dir():
                try:
                    size, _ = dir_size_fast(entry)
                    record = _item(entry, size, "directory")
                    record["name"] = f"{entry.parent.name}/{entry.name}"
                    items.append(record)
                    total_size += size
                except (PermissionError, OSError):
                    continue

    items.sort(key=lambda x: x["size"], reverse=True)
    return {
        "category": "dev-artifacts",
        "items": items[:limit],
        "totalSize": total_size,
        "timestamp": iso_now(),
    }


def scan_large_files(limit: int = 100, scan_dirs: list[str] | None = None) -> dict:
    """Scan common directories for files larger than 100 MB."""
    items: list[dict] = []
    total_size = 0

    for dir_pattern in (scan_dirs if scan_dirs is not None else LARGE_FILE_SCAN_DIRS):
        d = Path(os.path.expanduser(dir_pattern))
        if not d.is_dir():
            continue
        try:
            for entry in d.rglob("*"):
                try:
                    if entry.is_file():
                        size = entry.stat().st_size
                        if size >= LARGE_FILE_THRESHOLD:
                            items.append(_item(entry, size, "file"))
                            total_size += size
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            continue

    items.sort(key=lambda x: x["size"], reverse=True)
    return {
        "category": "large-files",
        "items": items[:limit],
        "totalSize": total_size,
        "timestamp": iso_now(),
    }


def scan_category(
    category: str,
    limit: int = 100,
    category_paths: dict[str, list[str]] | None = None,
    dev_scan_roots: list[str] | None = None,
    large_file_dirs: list[str] | None = None,
) -> dict:
    """Scan a category and return individual items. Read-only."""
    import glob as globmod

    paths_config = category_paths if category_paths is not None else CATEGORY_PATHS

    if category == "all":
        combined_items: list[dict] = []
        total_size = 0
        for cat_name in paths_config:
            result = scan_category(cat_name, limit=limit, category_paths=paths_config)
            combined_items.extend(result.get("items", []))
            total_size += result.get("totalSize", 0)
        for special, scanner, scope in (
            ("dev-artifacts", scan_dev_artifacts, dev_scan_roots),
            ("large-files", scan_large_files, large_file_dirs),
        ):
            result = scanner(limit, scope)
            combined_items.extend(result.get("items", []))
            total_size += result.get("totalSize", 0)
        combined_items.sort(key=lambda x: x["size"], reverse=True)
        return {
            "category": "all",
            "items": combined_items[:limit],
            "totalSize": total_size,
            "timestamp": iso_now(),
        }

    if category == "dev-artifacts":
        return scan_dev_artifacts(limit, dev_scan_roots)
    if category == "large-files":
        return scan_large_files(limit, large_file_dirs)

    paths = paths_config.get(category)
    if not paths:
        return {
            "category": category,
            "items": [],
            "totalSize": 0,
            "error": f"Unknown category: {category}",
            "timestamp": iso_now(),
        }

    items: list[dict] = []
    total_size = 0

    for pattern in paths:
        expanded = os.path.expanduser(pattern)
        targets: list[Path] = []

        if "*" in expanded or "?" in expanded:
            targets = [Path(m) for m in globmod.glob(expanded)]
        else:
            p = Path(expanded)
            if p.is_dir():
                # List direct children as scannable items
                try:
                    targets = sorted(p.iterdir(), key=lambda x: x.name)
                except (PermissionError, OSError):
                    continue
            elif p.is_file():
                targets = [p]

        for target in targets:
            try:
                if target.is_file():
                    size = target.stat().st_size
                    items.append(_item(target, size, "file"))
                    total_size += size
                elif target.is_dir():
                    size, _ = dir_size_fast(target)
                    items.append(_item(target, size, "directory"))
                    total_size += size
            except (PermissionError, OSError):
                continue

    items.sort(key=lambda x: x["size"], reverse=True)
    return {
        "category": category,
        "items": items[:limit],
        "totalSize": total_size,
        "timestamp": iso_now(),
    }


def _print_human(result: dict) -> None:
    error = result.get("error")
    if error:
        print(f"{result['category']}: ERROR — {error}")
        return
    print(f"category: {result['category']}")
    print(f"total:    {format_bytes(result['totalSize'])} "
          f"({len(result['items'])} items shown)")
    for item in result["items"]:
        marker = "/" if item["type"] == "directory" else ""
        print(f"  {format_bytes(item['size']):>10}  {item['path']}{marker}")


def main(argv: list[str] | None = None) -> int:
    known = sorted(CATEGORY_PATHS) + list(COMPUTED_CATEGORIES) + ["all"]
    parser = argparse.ArgumentParser(
        description="Read-only scan of macOS disk-waste categories (deletes nothing).",
    )
    parser.add_argument("--category", default="all", choices=known,
                        help="Category to scan (default: all)")
    parser.add_argument("--limit", type=int, default=100,
                        help="Maximum items to return (default: 100)")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args(argv)

    result = scan_category(args.category, limit=args.limit)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _print_human(result)
    return 2 if result.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
