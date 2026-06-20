#!/usr/bin/env python3
"""Write a capability baseline snapshot to disk for drift diffing (ADR-734 C1)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.lib.capabilities.baseline import build_baseline, write_baseline  # noqa: E402
from src.lib.capabilities.discovery import discover_capabilities  # noqa: E402
from src.lib.capabilities.exposure_policy import resolve_capability_records  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write capability baseline JSON.")
    parser.add_argument("--out", required=True, help="Path to write baseline JSON to.")
    args = parser.parse_args(argv)

    records = resolve_capability_records(discover_capabilities())
    snapshot = build_baseline(records)
    write_baseline(Path(args.out), snapshot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
