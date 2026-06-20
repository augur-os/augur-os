"""Read and resolve RAG index entries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.lib.frontmatter_utils import extract_relationships, parse_frontmatter


def _relationship_targets(relationships: dict[str, list[str]]) -> list[str]:
    targets: list[str] = []
    seen: set[str] = set()
    for field_targets in relationships.values():
        for target in field_targets:
            if target not in seen:
                seen.add(target)
                targets.append(target)
    return targets


def read_index_entry(path: Path) -> dict[str, Any]:
    """Read a single index entry, returning metadata with discovered relations."""
    meta, body = parse_frontmatter(path)
    meta["_index_path"] = str(path)
    if body.strip():
        meta["_body"] = body.strip()

    # Normalize null hub to "system"
    if meta.get("hub") is None:
        meta["hub"] = "system"

    relationships = extract_relationships(meta)
    meta["relationships"] = relationships
    meta["relationship_targets"] = _relationship_targets(relationships)

    return meta


def list_category_entries(
    category_dir: Path,
    hub: str | None = None,
    limit: int = 0,
) -> list[dict[str, Any]]:
    """List all index entries in a category directory, optionally filtered by hub.

    When hub is specified and a matching subdirectory exists, scans only that
    subdirectory instead of walking the entire category tree.

    Args:
        category_dir: Path to the category directory.
        hub: Optional hub filter.
        limit: Max entries to return (0 = unlimited).
    """
    if not category_dir.exists():
        return []

    # Optimization: when hub filter matches a subdirectory, scan only that
    scan_dir = category_dir
    check_hub = False
    if hub:
        hub_dir = category_dir / hub
        if hub_dir.is_dir():
            scan_dir = hub_dir
        else:
            check_hub = True

    entries = []
    for md_file in sorted(scan_dir.rglob("*.md")):
        if not md_file.is_file():
            continue
        entry = read_index_entry(md_file)
        if check_hub and entry.get("hub") != hub:
            continue
        entries.append(entry)
        if limit and len(entries) >= limit:
            break
    return entries


def count_category_entries(category_dir: Path, hub: str | None = None) -> int:
    """Count entries in a category without reading them all."""
    if not category_dir.exists():
        return 0
    count = 0
    if hub:
        hub_dir = category_dir / hub
        if hub_dir.is_dir():
            count = sum(1 for _ in hub_dir.rglob("*.md"))
    else:
        count = sum(1 for _ in category_dir.rglob("*.md"))
    return count
