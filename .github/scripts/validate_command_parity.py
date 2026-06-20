#!/usr/bin/env python3
"""Validate command registry parity (ADR-251).

Hard-fail gate: exits 1 if any declared command lacks a source file
or if duplicate command IDs exist across plugins.
"""

import sys
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.lib.ai.discovery import validate_commands


def main() -> int:
    result = validate_commands(PROJECT_ROOT)

    errors = result.get("errors", [])
    warnings = result.get("warnings", [])

    for w in warnings:
        print(f"WARNING: {w}")

    if errors:
        print(f"\n{len(errors)} command parity error(s) found:")
        for e in errors:
            print(f"  ERROR: {e}")
        return 1

    print("Command parity check passed — all declarations have source files, no duplicates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
