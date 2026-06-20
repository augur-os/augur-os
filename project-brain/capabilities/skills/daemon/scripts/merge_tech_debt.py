#!/usr/bin/env python3
"""
Merge Runtime Tech Debt into Codebase Markers.

Part of ADR-041: Daemon Production Monitoring & Self-Healing.

This script runs during the nightly workflow to:
1. Read state tech debt from state/tech_debt.md
2. Merge unique issues into the codebase marker scan
3. Clean up resolved issues from tech_debt.md

Usage:
    python3 merge_tech_debt.py              # Merge runtime markers
    python3 merge_tech_debt.py --cleanup    # Also cleanup resolved issues
    python3 merge_tech_debt.py --dry-run    # Show what would be merged
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Setup project root
from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

try:
    from src.logging import get_entity_logger
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        logging = importlib.import_module("logging")
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger


from src.config.paths import get_runtime_dir

logger = get_entity_logger("merge_tech_debt")


# ═══════════════════════════════════════════════════════════════════════════════
# FILE PATHS
# ═══════════════════════════════════════════════════════════════════════════════


def get_runtime_tech_debt_file() -> Path:
    """Get the runtime tech debt file path."""
    return get_runtime_dir() / "tech_debt.md"


def get_merged_markers_file() -> Path:
    """Get the merged markers output file path."""
    return get_runtime_dir() / "merged_markers.json"


# ═══════════════════════════════════════════════════════════════════════════════
# MARKER PARSING
# ═══════════════════════════════════════════════════════════════════════════════

# Pattern: # TODO_BUG(category/severity): message (seen Nx, last: timestamp)
MARKER_PATTERN = re.compile(
    r"^#\s*(TODO_\w+)\(([^/]+)/([^)]+)\):\s*(.+?)(?:\s*\(seen\s+(\d+)x,\s*last:\s*([^)]+)\))?\s*$"
)


def parse_markers(content: str) -> list[dict]:
    """Parse markers from tech debt file content."""
    markers = []

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("_") or line.startswith("<!--"):
            continue

        match = MARKER_PATTERN.match(line)
        if match:
            markers.append(
                {
                    "type": match.group(1),
                    "category": match.group(2),
                    "severity": match.group(3),
                    "message": match.group(4).strip(),
                    "count": int(match.group(5)) if match.group(5) else 1,
                    "last_seen": match.group(6) if match.group(6) else datetime.now().isoformat(),
                    "source": "runtime",
                }
            )

    return markers


def read_runtime_tech_debt() -> list[dict]:
    """Read markers from runtime tech debt file."""
    tech_debt_file = get_runtime_tech_debt_file()

    if not tech_debt_file.exists():
        logger.info("No runtime tech debt file found")
        return []

    content = tech_debt_file.read_text()
    markers = parse_markers(content)

    logger.info(f"Read {len(markers)} markers from {tech_debt_file}")
    return markers


# ═══════════════════════════════════════════════════════════════════════════════
# MERGE LOGIC
# ═══════════════════════════════════════════════════════════════════════════════


def load_existing_merged() -> list[dict]:
    """Load previously merged markers."""
    merged_file = get_merged_markers_file()

    if not merged_file.exists():
        return []

    try:
        payload = json.loads(merged_file.read_text())

        # Current schema is an object with top-level metadata + markers list.
        if isinstance(payload, dict):
            markers = payload.get("markers", [])
            if isinstance(markers, list):
                return markers
            logger.warning("Invalid merged markers schema: 'markers' is not a list")
            return []

        # Backward compatibility for legacy list-only payloads.
        if isinstance(payload, list):
            return payload

        logger.warning("Invalid merged markers payload: expected object or list")
        return []
    except Exception as e:
        logger.warning(f"Failed to read merged markers: {e}")
        return []


def merge_markers(runtime_markers: list[dict], existing_merged: list[dict]) -> list[dict]:
    """Merge runtime markers with existing merged markers.

    Deduplication is based on message hash.
    """
    # Create index of existing markers by message
    existing_by_message = {m["message"]: m for m in existing_merged}

    merged = []
    new_count = 0

    for marker in runtime_markers:
        msg = marker["message"]

        if msg in existing_by_message:
            # Update existing marker
            existing = existing_by_message[msg]
            existing["count"] = max(existing.get("count", 1), marker["count"])
            existing["last_seen"] = max(existing.get("last_seen", ""), marker["last_seen"])
            merged.append(existing)
        else:
            # New marker
            merged.append(marker)
            new_count += 1

    # Add any existing markers not in runtime (may have been resolved)
    for msg, marker in existing_by_message.items():
        if not any(m["message"] == msg for m in merged):
            marker["resolved"] = True
            merged.append(marker)

    logger.info(f"Merged {len(merged)} markers ({new_count} new)")
    return merged


def save_merged_markers(markers: list[dict]) -> None:
    """Save merged markers to JSON file."""
    merged_file = get_merged_markers_file()
    merged_file.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "merged_at": datetime.now().isoformat(),
        "total": len(markers),
        "active": len([m for m in markers if not m.get("resolved")]),
        "resolved": len([m for m in markers if m.get("resolved")]),
        "markers": markers,
    }

    merged_file.write_text(json.dumps(output, indent=2))
    logger.info(f"Saved merged markers to {merged_file}")


# ═══════════════════════════════════════════════════════════════════════════════
# CLEANUP
# ═══════════════════════════════════════════════════════════════════════════════


def cleanup_resolved_from_runtime() -> int:
    """Remove resolved markers from runtime tech debt file.

    A marker is considered resolved if it hasn't been seen in the last 24 hours.
    """
    tech_debt_file = get_runtime_tech_debt_file()

    if not tech_debt_file.exists():
        return 0

    content = tech_debt_file.read_text()
    lines = content.splitlines()
    cleaned_lines = []
    removed = 0

    for line in lines:
        # Keep headers and non-marker lines
        if not line.strip().startswith("# TODO_"):
            cleaned_lines.append(line)
            continue

        # Check if marker is stale (no recent occurrence)
        match = MARKER_PATTERN.match(line.strip())
        if match and match.group(6):
            try:
                last_seen = datetime.fromisoformat(match.group(6))
                age_hours = (datetime.now() - last_seen).total_seconds() / 3600

                if age_hours > 24:
                    # Skip this line (remove stale marker)
                    removed += 1
                    continue
            except ValueError:
                pass

        cleaned_lines.append(line)

    if removed > 0:
        tech_debt_file.write_text("\n".join(cleaned_lines))
        logger.info(f"Removed {removed} stale markers from {tech_debt_file}")

    return removed


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Merge runtime tech debt into codebase markers")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Also cleanup resolved issues from tech_debt.md",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be merged without writing",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    args = parser.parse_args()

    # Read runtime markers
    runtime_markers = read_runtime_tech_debt()

    if not runtime_markers:
        _out("No runtime markers to merge")
        return 0

    # Load existing merged markers
    existing_merged = load_existing_merged()

    # Merge
    merged = merge_markers(runtime_markers, existing_merged)

    if args.dry_run:
        _out("Would merge the following markers:")
        for m in merged:
            status = "[RESOLVED]" if m.get("resolved") else "[ACTIVE]"
            _out(f"  {status} {m['type']}({m['category']}/{m['severity']}): {m['message'][:60]}...")
        return 0

    # Save merged markers
    save_merged_markers(merged)

    # Cleanup if requested
    if args.cleanup:
        removed = cleanup_resolved_from_runtime()
        if args.json:
            _out(json.dumps({"merged": len(merged), "cleaned": removed}))
        else:
            _out(f"Merged {len(merged)} markers, cleaned {removed} stale entries")
    else:
        if args.json:
            _out(json.dumps({"merged": len(merged)}))
        else:
            _out(f"Merged {len(merged)} markers")

    return 0


if __name__ == "__main__":
    sys.exit(main())
