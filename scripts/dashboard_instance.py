#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.lib.dashboard_instance import resolve_dashboard_instance  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve the Augur dashboard instance for a checkout."
    )
    parser.add_argument("--root", default=os.getcwd())
    parser.add_argument("--runtime-dir")
    parser.add_argument("--instance")
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()

    instance = resolve_dashboard_instance(
        Path(args.root),
        runtime_dir=Path(args.runtime_dir) if args.runtime_dir else None,
        explicit_instance=args.instance,
        interactive=args.interactive,
    )
    print(json.dumps(instance.to_json_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
