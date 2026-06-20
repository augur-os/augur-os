#!/usr/bin/env python3
"""
Dashboard Server Monitor — thin wrapper.

The implementation lives in the ``monitor`` package (monitor/__init__.py).
This file re-exports every public symbol so that existing callers
(``import dashboard_monitor``, ``from dashboard_monitor import X``)
continue to work unchanged.

Usage:
    python3 dashboard_monitor.py              # Run once
    python3 dashboard_monitor.py --loop       # Continuous monitoring (for daemon)
    python3 dashboard_monitor.py --check      # Check only, no action
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure the scripts directory is on sys.path so that the ``monitor`` package
# (a sibling directory) and other daemon-local imports resolve correctly.
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# Re-export the entire public API from the monitor package.
from monitor import *  # noqa: F401,F403
from monitor import (
    CHECK_INTERVAL_SECONDS,
    _out,
    check_and_recover,
    get_dashboard_status,
    monitor_loop,
)


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Dashboard Server Monitor")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuous monitoring loop",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check status only, no recovery action",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=CHECK_INTERVAL_SECONDS,
        help=f"Check interval in seconds (default: {CHECK_INTERVAL_SECONDS})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    args = parser.parse_args()

    if args.loop:
        monitor_loop(args.interval)
        return 0

    if args.check:
        status = get_dashboard_status()
    else:
        status = check_and_recover()

    if args.json:
        _out(json.dumps(status, indent=2))
    else:
        _out("Dashboard Status")
        _out("=" * 40)
        _out(f"Running: {status['running']}")
        _out(f"Healthy: {status.get('healthy', 'N/A')}")
        _out(f"HTTP Status: {status.get('http_status', 'N/A')}")
        _out(f"PIDs: {status.get('pids', [])}")
        _out(f"Rebuild in progress: {status.get('rebuild_in_progress', False)}")
        _out(f"Mode: {status.get('mode', 'unknown')}")
        _out(f"Action: {status.get('action', 'none')}")

    return 0 if status.get("running") and status.get("healthy", True) else 1


if __name__ == "__main__":
    sys.exit(main())
