#!/usr/bin/env python3
"""Audit and repair shared Augur global identity drift."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config.global_identity_drift import repair_editable_identity, scan_global_identity_drift
from src.config.runtime_identity import resolve_runtime_identity


def _repair_mcp_identity(args: argparse.Namespace, authority_root: Path) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "configure_mcp.py"),
        "--repo-root",
        str(authority_root),
        "--python",
        args.python,
        "--apply",
        "--no-external",
    ]
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _fresh_recheck(args: argparse.Namespace, current_root: Path) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--root",
        str(current_root),
        "--python",
        args.python,
    ]
    for site_package in args.site_packages or []:
        command.extend(["--site-packages", str(site_package)])
    if args.json:
        command.append("--json")
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Augur global identity drift.")
    parser.add_argument("--root", type=Path, default=None, help="Project root to inspect.")
    parser.add_argument("--python", default=sys.executable, help="Python executable to inspect.")
    parser.add_argument("--site-packages", action="append", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument("--repair", action="store_true", help="Repair editable identity before reporting.")
    args = parser.parse_args()

    identity = resolve_runtime_identity(args.root)
    site_dirs = args.site_packages if args.site_packages else None
    issues = scan_global_identity_drift(
        project_root=identity.current_root,
        python_executable=args.python,
        site_package_dirs=site_dirs,
    )

    if args.repair and issues:
        repair = repair_editable_identity(
            authority_root=identity.authority_root,
            python_executable=args.python,
        )
        mcp_repair = _repair_mcp_identity(args, identity.authority_root)
        if repair.returncode == 0 and mcp_repair.returncode == 0:
            recheck = _fresh_recheck(args, identity.current_root)
            if recheck.stdout:
                print(recheck.stdout, end="")
            if recheck.stderr:
                print(recheck.stderr, end="", file=sys.stderr)
            return recheck.returncode
        issues = scan_global_identity_drift(
            project_root=identity.current_root,
            python_executable=args.python,
            site_package_dirs=site_dirs,
        )
        if repair.returncode != 0 and not args.json:
            print(repair.stderr, file=sys.stderr)
        if mcp_repair.returncode != 0 and not args.json:
            print(mcp_repair.stderr, file=sys.stderr)

    payload = {
        "ok": not issues,
        "authorityRoot": str(identity.authority_root),
        "currentRoot": str(identity.current_root),
        "issues": [issue.as_dict() for issue in issues],
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    elif not issues:
        print(f"OK: shared Augur identity resolves to {identity.authority_root}")
    else:
        print(f"FAIL: {len(issues)} shared Augur identity issue(s)")
        for issue in issues:
            print(f"- {issue.surface} {issue.name}: {issue.path} expected {issue.expected}")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
