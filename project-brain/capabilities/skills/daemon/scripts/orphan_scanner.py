"""Orphan detection for MCP processes.

Scans the system for orphaned MCP processes (ppid=1) and provides
client-based orphan detection via PID registry inspection.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

try:
    from .process_utils import (
        IS_WINDOWS,
        is_pid_alive,
        kill_process,
        run_command,
    )
except ImportError:
    from process_utils import (
        IS_WINDOWS,
        is_pid_alive,
        kill_process,
        run_command,
    )

# Setup project root
try:
    from .bootstrap_paths import ensure_project_paths  # noqa: E402
except ImportError:
    from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

try:
    from src.logging import get_entity_logger
except ImportError:
    import importlib
    import logging as _logging

    def get_entity_logger(name: str):
        logger = _logging.getLogger(name)
        if not logger.handlers:
            handler = _logging.StreamHandler()
            handler.setFormatter(_logging.Formatter('%(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(_logging.INFO)
        return logger


logger = get_entity_logger("mcp_orphan_scanner")

# Known MCP process patterns (command-line substrings) for system-level orphan scanning
MCP_PROCESS_PATTERNS = [
    "augur_core",
    "augur_framework",
    "augur_shared.bundle_server",
    "context7-mcp",
    "playwright-mcp",
    "claude-in-chrome-mcp",
]

# Minimum age (seconds) before a process is eligible for orphan killing.
# Prevents killing processes that are still starting up.
ORPHAN_MIN_AGE_SECONDS = 120


def _parse_etime(etime_str: str) -> int:
    """
    Parse `ps -o etime=` output into seconds.

    Formats: "MM:SS", "HH:MM:SS", "D-HH:MM:SS"
    """
    etime_str = etime_str.strip()
    if not etime_str:
        return 0

    days = 0
    if "-" in etime_str:
        day_part, etime_str = etime_str.split("-", 1)
        days = int(day_part)

    parts = etime_str.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
    elif len(parts) == 2:
        hours = 0
        minutes, seconds = int(parts[0]), int(parts[1])
    else:
        return 0

    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def detect_client_orphans(
    load_mcp_pids_fn: Any,
) -> list[tuple[str, dict]]:
    """
    Detect MCP servers whose parent client process is no longer running.

    Args:
        load_mcp_pids_fn: Callable returning the PID registry dict.

    Returns:
        List of (server_name, server_info) tuples for orphaned servers
    """
    orphans = []
    pids_data = load_mcp_pids_fn()
    servers = pids_data.get("servers", {})

    # Map client names to process names to look for
    client_process_map = {
        "claude-code": "claude",
        "cursor": "Cursor",
        "windsurf": "windsurf",
        "opencode": "opencode",
        "antigravity": "antigravity",
        "copilot": "copilot",
        "gemini": "gemini",
        "codex": "codex",
    }

    for name, info in servers.items():
        client = info.get("client", "unknown")
        if client == "unknown":
            continue

        process_name = client_process_map.get(client.lower())
        if not process_name:
            continue

        # Check if client process is running
        try:
            if IS_WINDOWS:
                result = run_command(
                    ["tasklist", "/FI", f"IMAGENAME eq {process_name}.exe"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                client_alive = process_name in result.stdout
            else:
                result = run_command(
                    ["pgrep", "-i", process_name],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                client_alive = result.returncode == 0

            if not client_alive:
                logger.warning(f"MCP '{name}' orphaned (client '{client}' not running)")
                orphans.append((name, info))

        except Exception as e:
            logger.debug(f"Failed to check client process for '{name}': {e}")

    return orphans


def scan_system_orphans(
    dry_run: bool = False,
    allowlist_pids: Optional[set[int]] = None,
    write_issue_fn: Any = None,
) -> dict:
    """
    Scan the system for orphaned MCP processes regardless of PID registry state.

    Finds processes matching known MCP patterns whose parent PID is 1 (reparented
    to launchd/init after parent died) and are older than ORPHAN_MIN_AGE_SECONDS.

    Args:
        dry_run: If True, report but don't kill orphans
        allowlist_pids: PIDs to never kill (e.g. current session's own PID)
        write_issue_fn: Optional callback(name, pid, issue_type) for logging issues

    Returns:
        Dict with scan results: scanned, orphans_found, orphans_killed, details
    """
    if IS_WINDOWS:
        return {"scanned": 0, "orphans_found": 0, "orphans_killed": 0, "details": [], "skipped": "windows"}

    allowlist = allowlist_pids or set()
    results: dict[str, Any] = {
        "scanned": 0,
        "orphans_found": 0,
        "orphans_killed": 0,
        "details": [],
    }

    for pattern in MCP_PROCESS_PATTERNS:
        # Find PIDs matching this pattern
        try:
            pgrep_result = run_command(
                ["pgrep", "-f", pattern],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if pgrep_result.returncode != 0:
                continue

            pids = [int(p.strip()) for p in pgrep_result.stdout.strip().splitlines() if p.strip()]
        except Exception as e:
            logger.debug(f"pgrep failed for pattern '{pattern}': {e}")
            continue

        for pid in pids:
            results["scanned"] += 1

            # Skip allowlisted PIDs (current session)
            if pid in allowlist:
                continue

            # Skip our own process
            if pid == os.getpid():
                continue

            # Get parent PID
            try:
                ppid_result = run_command(
                    ["ps", "-o", "ppid=", "-p", str(pid)],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if ppid_result.returncode != 0:
                    continue
                ppid = int(ppid_result.stdout.strip())
            except (ValueError, Exception):
                continue

            # Orphan criteria: ppid == 1 means reparented to launchd/init
            if ppid != 1:
                continue

            # Age check: skip processes younger than threshold
            try:
                etime_result = run_command(
                    ["ps", "-o", "etime=", "-p", str(pid)],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if etime_result.returncode != 0:
                    continue
                age_seconds = _parse_etime(etime_result.stdout)
                if age_seconds < ORPHAN_MIN_AGE_SECONDS:
                    continue
            except Exception:
                continue

            results["orphans_found"] += 1

            detail = {
                "pid": pid,
                "pattern": pattern,
                "ppid": ppid,
                "age_seconds": age_seconds,
                "action": "dry_run" if dry_run else "killed",
            }

            if not dry_run:
                logger.info(f"Killing orphaned MCP process: PID {pid} (pattern={pattern}, age={age_seconds}s)")
                if kill_process(pid):
                    results["orphans_killed"] += 1
                    if write_issue_fn:
                        write_issue_fn(pattern, pid, f"orphaned (ppid=1, age={age_seconds}s)")
                    detail["action"] = "killed"
                else:
                    detail["action"] = "kill_failed"
                    logger.warning(f"Failed to kill orphaned MCP PID {pid}")
            else:
                logger.info(f"[DRY RUN] Orphaned MCP process: PID {pid} (pattern={pattern}, age={age_seconds}s)")

            results["details"].append(detail)

    return results
