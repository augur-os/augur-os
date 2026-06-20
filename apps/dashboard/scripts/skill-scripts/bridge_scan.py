#!/usr/bin/env python3
"""Bridge scan CLI: scan a source and return manifest + integration plan (ADR-086).

Called by the /api/bridge/scan TypeScript route via subprocess.

Usage:
    python3 bridge_scan.py --path ~/Documents/Finance --hub finance --source-type folder

Output: JSON with scan manifest and integration plan.
"""

from __future__ import annotations

import argparse
import json
import sys

from source_adapters import FolderAdapter
from file_analyzers import get_analyzer_map
from integration_planner import IntegrationPlanner


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan an external data source and return manifest + integration plan.")
    parser.add_argument("--path", required=True, help="Path to the data source")
    parser.add_argument("--hub", required=True, help="Hub identifier")
    parser.add_argument("--source-type", default="folder", help="Source type (default: folder)")
    parser.add_argument("--level", type=int, default=2, help="Integration level: 1 (import) or 2 (connect)")

    args = parser.parse_args()

    if args.source_type != "folder":
        json.dump(
            {"error": f"Unsupported source type: {args.source_type}"},
            sys.stdout,
            indent=2,
        )
        sys.exit(1)

    try:
        # Create adapter with all analyzers
        analyzers = get_analyzer_map()
        adapter = FolderAdapter(args.path, analyzers=analyzers)

        # Scan the source
        manifest = adapter.scan()

        # Plan integrations
        planner = IntegrationPlanner(args.hub, level=args.level)
        plan = planner.plan(manifest)

        # Build response
        result = {
            "hub": args.hub,
            "source_type": args.source_type,
            "source_path": manifest.source_path,
            "scanned_at": manifest.scanned_at.isoformat(),
            "file_count": manifest.file_count,
            "directory_count": manifest.directory_count,
            "total_size": manifest.total_size,
            "files": [
                {
                    "name": f.name,
                    "path": f.path,
                    "size": f.size,
                    "file_type": f.file_type,
                    "is_directory": f.is_directory,
                    "structure": manifest.file_structures.get(f.path),
                }
                for f in manifest.files
                if "/" not in f.path  # top-level only for the UI
            ],
            "integrations": [i.to_dict() for i in plan.integrations],
            "ignored": [i.to_dict() for i in plan.ignored],
        }

        json.dump(result, sys.stdout, indent=2, default=str)
        print()

    except NotADirectoryError as e:
        json.dump({"error": str(e)}, sys.stdout, indent=2)
        sys.exit(1)
    except Exception as e:
        json.dump({"error": f"Scan failed: {e}"}, sys.stdout, indent=2)
        sys.exit(1)


if __name__ == "__main__":
    main()
