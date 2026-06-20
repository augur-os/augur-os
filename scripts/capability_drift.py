#!/usr/bin/env python3
"""Run the capability drift report (ADR-734 C2)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.paths import get_project_root  # noqa: E402
from src.lib.capabilities.discovery import discover_capabilities  # noqa: E402
from src.lib.capabilities.drift import run_all_drift_checks  # noqa: E402
from src.lib.capabilities.exposure_policy import (  # noqa: E402
    load_capability_policy,
    resolve_capability_records,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run capability drift checks.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Return non-zero if any warning is present (default: fail on FAIL only).",
    )
    args = parser.parse_args(argv)

    project_root = get_project_root()
    records = resolve_capability_records(discover_capabilities())
    policy = load_capability_policy()
    budgets = policy.get("budgets", {"gemini": 50, "opencode": 50})
    # Derive multi_client_approved from resolved records — per-capability
    # `multi_client_approved: true` overlays in policy land on each record.
    approved = {
        record.id.split(":", 1)[1]
        for record in records
        if record.multi_client_approved and ":" in record.id
    }

    report = run_all_drift_checks(
        records,
        project_root=project_root,
        agents_md_path=project_root / "AGENTS.md",
        budgets=budgets,
        multi_client_approved=approved,
    )

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for finding in report["findings"]:
            print(
                f"[{finding['severity'].upper()}] {finding['dimension']}: "
                f"{finding['capability_id']} — {finding['message']}"
            )
        print(f"\n{report['fail_count']} failures, {report['warn_count']} warnings.")

    if report["fail_count"]:
        return 1
    if args.fail_on_warn and report["warn_count"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
