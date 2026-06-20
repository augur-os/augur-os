from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from skills.ingest.scripts.demo_ready import run_demo_smoke


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the AI PC investor demo.")
    parser.add_argument(
        "--desktop",
        type=Path,
        default=Path.home() / "Desktop" / "Augur Demo Inbox",
    )
    parser.add_argument("--airplane", choices=["on", "off"], default="on")
    parser.add_argument("--require-cloud", action="store_true")
    args = parser.parse_args(argv)

    result = run_demo_smoke(
        desktop=args.desktop,
        airplane=args.airplane,
        require_cloud=bool(args.require_cloud),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
