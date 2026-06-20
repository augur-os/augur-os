"""CLI helper for setup-completeness verification."""

from __future__ import annotations

import argparse
import json

from .aggregator import compute_setup_status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print setup completeness status")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    parser.add_argument("--skip-cache", action="store_true", help="Bypass cached probe status")
    args = parser.parse_args(argv)
    status = compute_setup_status(skip_cache=args.skip_cache)
    if args.json:
        print(json.dumps(status.to_dict(), indent=2, default=str))
    else:
        print(f"{status.completed}/{status.total} ({status.pct}%) {status.state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
