#!/usr/bin/env python3
"""Audit shared and private skills for standardization issues."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.paths import (  # noqa: E402
    get_configured_vault_skills_dir,
    get_project_brain_skills_dir,
)
from src.lib.skill_standard_scan import scan_skill_roots  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit skill standardization.")
    parser.add_argument(
        "--shared-root",
        type=Path,
        default=get_project_brain_skills_dir(PROJECT_ROOT),
        help="Shared Augur-owned skills root.",
    )
    parser.add_argument(
        "--private-root",
        type=Path,
        default=get_configured_vault_skills_dir(PROJECT_ROOT),
        help="Private user-owned skills root.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Return non-zero if any warning is present (default: fail on FAIL only).",
    )
    args = parser.parse_args(argv)

    report = scan_skill_roots(
        shared_root=args.shared_root,
        private_root=args.private_root,
    )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        for issue in report.issues:
            print(
                f"[{issue.severity.value.upper()}] {issue.code}: "
                f"{issue.skill} - {issue.message} ({issue.path}) "
                f"Fix: {issue.suggested_fix}"
            )
        print(
            f"\n{report.skills_scanned} skills scanned, "
            f"{report.fail_count} failures, {report.warn_count} warnings."
        )

    if report.fail_count:
        return 1
    if args.fail_on_warn and report.warn_count:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
