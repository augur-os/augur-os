#!/usr/bin/env python3
"""
Check Repo Health
Wrapper for repo audit.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import repo_audit  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Check repo health")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    result = repo_audit.run_audit()
    if args.json:
        sys.stdout.write(f"{json.dumps(result, indent=2)}\n")
    else:
        sys.stdout.write(f"{json.dumps(result, indent=2)}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
