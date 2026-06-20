"""CLI gate: prove the public partition carries no private content.

Exit 0 when clean, 1 when any finding is present. Used locally and in CI
(.github/workflows/partition-integrity.yml) and, later, by the release guard.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.lib.partition_integrity import load_policy, scan_partition

_MARKER_ENV = "AUGUR_PRIVATE_MARKER_REGEX"


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan the public partition for private content.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="Repo root to scan.")
    parser.add_argument("--policy", type=Path, default=None, help="Override policy YAML path.")
    parser.add_argument("--json", action="store_true", help="Emit findings as JSON.")
    args = parser.parse_args()

    # Privacy gate: a missing marker regex means marker detection is a silent
    # no-op, so a "clean" result must not be falsely trusted. Warn loudly.
    if not (os.environ.get(_MARKER_ENV) or "").strip():
        print(
            f"WARNING: {_MARKER_ENV} is unset/empty — private-marker detection is "
            "DISABLED. Personal markers (names/emails/client ids) will NOT be "
            "caught; a 'clean' result is not proof of marker safety.",
            file=sys.stderr,
        )

    policy = load_policy(args.policy) if args.policy else None
    findings = scan_partition(root=args.root, policy=policy)

    if args.json:
        print(json.dumps([f.__dict__ for f in findings], indent=2))
    elif findings:
        print(f"Partition-integrity: {len(findings)} private finding(s):")
        for f in findings:
            loc = f"{f.path}:{f.line}" if f.line else f.path
            print(f"  [{f.kind}] {loc} — {f.detail}")
    else:
        print("Partition-integrity: clean (no private findings).")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
