#!/usr/bin/env python3
"""
Migration script: Clean up legacy Augur LaunchAgent plists and install unified daemon.

Replaces the old per-service LaunchAgents (com.augur.logmonitor, com.augur.nightly,
com.augur.continuous) with a single unified daemon that shows as "Augur" in
macOS Background Activity.

Usage:
    python3 cleanup_legacy_plists.py          # Run migration
    python3 cleanup_legacy_plists.py --dry-run # Show what would be done
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from subprocess import CompletedProcess, run  # nosec B404


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve executable path to absolute when available."""
    if not command:
        raise ValueError("Command must not be empty")

    executable = command[0]
    if Path(executable).is_absolute():
        return command

    resolved = shutil.which(executable)
    if not resolved:
        return command

    return [resolved, *command[1:]]


def _run_command(command: list[str], **kwargs: object) -> CompletedProcess:
    """Run subprocess command with resolved executable."""
    return run(_resolve_command(command), **kwargs)  # nosec B603


from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

from src.config.paths import get_launch_agents_dir

LAUNCH_AGENTS = get_launch_agents_dir()

# Legacy plists to remove
LEGACY_PLISTS = [
    "com.augur.logmonitor.plist",
    "com.augur.nightly.plist",
    "com.augur.continuous.plist",
]


def run_migration(dry_run: bool = False) -> int:
    """Run the full migration from legacy plists to unified daemon."""
    if sys.platform != "darwin":
        _out("This script only runs on macOS")
        return 1

    _out("=" * 60)
    _out("Augur Daemon Migration")
    _out("  From: 3 separate LaunchAgents (python3 entries)")
    _out("  To:   1 unified daemon LaunchAgent")
    _out("=" * 60)

    # Step 1: Remove legacy plists
    _out("\n--- Step 1: Remove legacy LaunchAgent plists ---")
    for plist_name in LEGACY_PLISTS:
        plist_path = LAUNCH_AGENTS / plist_name
        if plist_path.exists():
            if dry_run:
                _out(f"  [DRY RUN] Would remove: {plist_name}")
            else:
                _run_command(["launchctl", "unload", str(plist_path)], capture_output=True)
                plist_path.unlink()
                _out(f"  Removed: {plist_name}")
        else:
            _out(f"  Already gone: {plist_name}")

    # Step 2: Install unified daemon via service_healer
    _out("\n--- Step 2: Install unified daemon ---")
    from skills.daemon.scripts.service_healer import install_services

    if dry_run:
        _out("  [DRY RUN] Would install com.augur.daemon.plist")
    else:
        results = install_services()
        for name, status in results.items():
            _out(f"  {name}: {status}")

    # Step 3: Reset Background Activity cache
    _out("\n--- Step 3: Reset macOS Background Activity cache ---")
    if dry_run:
        _out("  [DRY RUN] Would run sfltool resetbtm")
    else:
        try:
            result = _run_command(
                ["sfltool", "resetbtm"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                _out("  Background Activity cache reset")
                _out("  NOTE: You may need to re-approve Augur in System Settings")
            else:
                _out("  sfltool returned non-zero (may need admin privileges)")
        except FileNotFoundError:
            _out("  sfltool not available (requires macOS 13+)")
            _out("  Old entries may persist until next reboot")

    # Step 4: Verify
    _out("\n--- Step 4: Verify ---")
    daemon_plist = LAUNCH_AGENTS / "com.augur.daemon.plist"
    if dry_run:
        _out("  [DRY RUN] Would verify daemon is running")
    else:
        if daemon_plist.exists():
            result = _run_command(
                ["launchctl", "list", "com.augur.daemon"],
                capture_output=True,
            )
            if result.returncode == 0:
                _out("  Unified daemon is RUNNING")
            else:
                _out("  Unified daemon plist installed but not running yet")
                _out("  It will start automatically on next login, or run:")
                _out(f"  launchctl load -w {daemon_plist}")
        else:
            _out("  WARNING: com.augur.daemon.plist not found")

    # Summary
    remaining = [p for p in LEGACY_PLISTS if (LAUNCH_AGENTS / p).exists()]
    _out("\n" + "=" * 60)
    if remaining:
        _out(f"WARNING: {len(remaining)} legacy plists still present:")
        for p in remaining:
            _out(f"  - {p}")
    else:
        _out("Migration complete!")
        _out("  - All legacy plists removed")
        _out("  - Unified daemon installed")
        _out("  - Open System Settings > General > Login Items to verify")
        _out("    'Augur' should appear with its icon")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate Augur to unified daemon")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()
    return run_migration(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
