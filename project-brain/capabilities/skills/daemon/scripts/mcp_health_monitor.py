#!/usr/bin/env python3
"""
MCP Server Health Monitor.

Monitors MCP server processes for health issues:
- Detects stalled PIDs (process exists but unresponsive)
- Cleans up zombie processes
- Logs issues as TODO_BUG markers for nightly review

Mode-aware behavior (ADR-063):
- Both modes: Auto-kill stalled processes
- Dev mode: Additionally logs stack trace to mcp_issues.md for debugging

Usage:
    python3 mcp_health_monitor.py                  # Run once
    python3 mcp_health_monitor.py --loop           # Continuous monitoring (for daemon)
    python3 mcp_health_monitor.py --check          # Check only, no action
    python3 mcp_health_monitor.py --graceful-stop  # Stop all MCP servers gracefully
    python3 mcp_health_monitor.py --preflight      # Pre-startup orphan cleanup
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


try:
    from bootstrap_paths import ensure_project_paths
except ImportError:
    _SCRIPTS_DIR = Path(__file__).resolve().parent
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    from bootstrap_paths import ensure_project_paths

PROJECT_ROOT = ensure_project_paths(__file__)

try:
    from src.logging import get_entity_logger
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        logging = importlib.import_module("logging")
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger


from src.config.paths import get_logs_dir, get_runtime_dir

# Local imports
try:
    from .daemon_mode import get_daemon_mode, is_production_mode
except ImportError:
    try:
        from daemon_mode import get_daemon_mode, is_production_mode
    except ImportError:

        def get_daemon_mode():
            return os.environ.get("AUGUR_MODE", "production")

        def is_production_mode():
            return get_daemon_mode() == "production"


try:
    from .notification_service import notify
except ImportError:
    try:
        from notification_service import notify
    except ImportError:

        def notify(message: str, channel: str = "system"):
            _out(f"[NOTIFY] {message}")


# Import extracted modules
try:
    from .process_utils import (
        is_pid_alive,
        is_process_responsive,
        get_process_state,
        kill_process,
        run_command as _run_command,
        IS_WINDOWS,
    )
    from .orphan_scanner import (
        detect_client_orphans as _detect_client_orphans_raw,
        scan_system_orphans,
    )
    from .mcp_lifecycle import (
        graceful_stop as _graceful_stop_impl,
        preflight_check as _preflight_check_impl,
    )
except ImportError:
    from process_utils import (
        is_pid_alive,
        is_process_responsive,
        get_process_state,
        kill_process,
        run_command as _run_command,
        IS_WINDOWS,
    )
    from orphan_scanner import (
        detect_client_orphans as _detect_client_orphans_raw,
        scan_system_orphans,
    )
    from mcp_lifecycle import (
        graceful_stop as _graceful_stop_impl,
        preflight_check as _preflight_check_impl,
    )

logger = get_entity_logger("mcp_health_monitor")

# Configuration
CHECK_INTERVAL_SECONDS = 60

# How often (in monitor loop iterations) to run system orphan scan.
# With 60s interval, every 5th iteration = every 5 minutes.
ORPHAN_SCAN_INTERVAL = 5


# ---- DATA STRUCTURES ----


@dataclass
class MCPProcessStatus:
    """Status of an MCP process."""

    name: str
    pid: Optional[int] = None
    is_alive: bool = False
    is_responsive: bool = False
    command: str = ""
    checked_at: str = ""
    action_taken: str = "none"
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


# ---- PID REGISTRY ----


def get_mcp_pids_file() -> Path:
    """Get the MCP PIDs registry file path."""
    return get_runtime_dir() / "mcp_pids.json"


def load_mcp_pids() -> dict:
    """Load MCP PIDs from registry."""
    pids_file = get_mcp_pids_file()
    if not pids_file.exists():
        return {"servers": {}}

    try:
        return json.loads(pids_file.read_text())
    except Exception as e:
        logger.warning(f"Failed to load MCP PIDs: {e}")
        return {"servers": {}}


def save_mcp_pids(data: dict) -> None:
    """Save MCP PIDs to registry."""
    pids_file = get_mcp_pids_file()
    pids_file.parent.mkdir(parents=True, exist_ok=True)

    data["updated_at"] = datetime.now().isoformat()
    pids_file.write_text(json.dumps(data, indent=2))


def remove_pid_from_registry(name: str) -> None:
    """Remove a stale PID from the registry."""
    data = load_mcp_pids()
    if name in data.get("servers", {}):
        del data["servers"][name]
        save_mcp_pids(data)
        logger.info(f"Removed {name} from MCP PID registry")


def register_mcp_server(name: str, pid: int, client: str, transport: str, port: Optional[int] = None) -> None:
    """
    Register an MCP server in the PID registry with full metadata.

    Args:
        name: Server name
        pid: Process ID
        client: IDE client name (e.g., "claude-code", "cursor", "windsurf")
        transport: Transport type ("stdio" or "sse")
        port: Optional port number for SSE servers
    """
    data = load_mcp_pids()
    data["servers"][name] = {
        "pid": pid,
        "command": "",  # Will be populated by caller if needed
        "client": client,
        "transport": transport,
        "started_at": datetime.now().isoformat(),
        "port": port,
    }
    save_mcp_pids(data)
    logger.info(f"Registered MCP server '{name}' (PID {pid}, client: {client})")


def detect_client_orphans() -> list[tuple[str, dict]]:
    """Detect MCP servers whose parent client process is no longer running."""
    return _detect_client_orphans_raw(load_mcp_pids)


# ---- TECH DEBT MARKERS ----


def write_mcp_issue(name: str, pid: int, issue_type: str) -> None:
    """Write an MCP issue as a TODO_BUG marker for nightly review."""
    issues_file = get_runtime_dir() / "mcp_issues.md"
    issues_file.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Format as marker for runtime tech debt (note: uses HTML comment to avoid scanner false positive)
    marker = f"<!-- TODO_BUG(integration/medium): MCP '{name}' (PID {pid}) {issue_type}, auto-fixed {timestamp} -->\n"

    # Append to file (create if not exists)
    with open(issues_file, "a") as f:
        f.write(marker)

    logger.debug(f"Logged MCP issue: {name} - {issue_type}")


def write_health_log(statuses: list[MCPProcessStatus]) -> None:
    """Write health check results to log file."""
    log_file = get_logs_dir() / "mcp_health.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "mode": get_daemon_mode(),
        "servers": [s.to_dict() for s in statuses],
    }

    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ---- MONITORING LOGIC ----


def check_mcp_health(check_only: bool = False) -> list[MCPProcessStatus]:
    """
    Check health of all registered MCP processes.

    Args:
        check_only: If True, don't take any action

    Returns:
        List of process statuses
    """
    statuses = []
    pids_data = load_mcp_pids()
    servers = pids_data.get("servers", {})

    # Check for client orphans (ADR-063 Decision 3)
    if not check_only:
        orphans = detect_client_orphans()
        for orphan_name, orphan_info in orphans:
            orphan_pid = orphan_info.get("pid")
            if orphan_pid and is_pid_alive(orphan_pid):
                logger.info(f"Killing orphaned MCP '{orphan_name}' (PID {orphan_pid})")
                kill_process(orphan_pid)
            remove_pid_from_registry(orphan_name)

    if not servers:
        logger.debug("No MCP servers in registry")
        return statuses

    for name, info in servers.items():
        pid = info.get("pid")
        status = MCPProcessStatus(
            name=name,
            pid=pid,
            checked_at=datetime.now().isoformat(),
            command=info.get("command", ""),
        )

        if not pid:
            status.error = "No PID registered"
            statuses.append(status)
            continue

        # Check if alive
        status.is_alive = is_pid_alive(pid)

        if not status.is_alive:
            status.error = "Process not found"
            if not check_only:
                remove_pid_from_registry(name)
                status.action_taken = "removed_from_registry"
            statuses.append(status)
            continue

        # Check if responsive
        status.is_responsive = is_process_responsive(pid)

        if not status.is_responsive:
            status.error = "Process stalled"
            logger.warning(f"MCP '{name}' (PID {pid}) is stalled")

            if check_only:
                statuses.append(status)
                continue

            # Auto-kill stalled processes in all modes (ADR-063 Decision 2)
            if kill_process(pid):
                status.action_taken = "killed"
                remove_pid_from_registry(name)
                write_mcp_issue(name, pid, "stalled")
                logger.info(f"Killed stalled MCP '{name}' (PID {pid})")

                # In dev mode, also log stack trace for debugging
                if not is_production_mode():
                    state = get_process_state(pid) or "unknown"
                    issues_file = get_runtime_dir() / "mcp_issues.md"
                    with open(issues_file, "a") as f:
                        f.write(f"\n## Stack Trace: {name} (PID {pid})\n")
                        f.write(f"**Timestamp**: {datetime.now().isoformat()}\n")
                        f.write(f"**State**: {state}\n")
                        f.write(f"**Command**: {info.get('command', 'unknown')}\n")
                        f.write("**Action**: Auto-killed (dev mode)\n\n")
            else:
                status.action_taken = "kill_failed"
                logger.error(f"Failed to kill stalled MCP '{name}'")

        statuses.append(status)

    # Write health log
    write_health_log(statuses)

    return statuses


def get_summary(statuses: list[MCPProcessStatus]) -> dict:
    """Get summary statistics from health check results."""
    return {
        "total": len(statuses),
        "alive": sum(1 for s in statuses if s.is_alive),
        "responsive": sum(1 for s in statuses if s.is_responsive),
        "stalled": sum(1 for s in statuses if s.is_alive and not s.is_responsive),
        "dead": sum(1 for s in statuses if not s.is_alive),
        "actions_taken": sum(1 for s in statuses if s.action_taken != "none"),
        "mode": get_daemon_mode(),
        "timestamp": datetime.now().isoformat(),
    }


def monitor_loop(interval: int = CHECK_INTERVAL_SECONDS) -> None:
    """Continuous monitoring loop."""
    logger.info(f"Starting MCP health monitor (interval: {interval}s, mode: {get_daemon_mode()})")

    iteration = 0
    while True:
        try:
            statuses = check_mcp_health()
            summary = get_summary(statuses)

            if summary["stalled"] > 0 or summary["dead"] > 0:
                logger.warning(
                    f"MCP Health: {summary['alive']}/{summary['total']} alive, "
                    f"{summary['stalled']} stalled, {summary['dead']} dead"
                )

            # System-level orphan scan every ORPHAN_SCAN_INTERVAL iterations
            if iteration % ORPHAN_SCAN_INTERVAL == 0:
                orphan_scan = scan_system_orphans(
                    allowlist_pids={os.getpid()},
                    write_issue_fn=write_mcp_issue,
                )
                if orphan_scan["orphans_killed"]:
                    logger.info(f"System orphan scan: killed {orphan_scan['orphans_killed']} " f"orphaned process(es)")

        except Exception as e:
            logger.error(f"Monitor loop error: {e}")

        iteration += 1
        time.sleep(interval)


# ---- SHUTDOWN & PREFLIGHT (ADR-063) ----


def graceful_stop() -> dict:
    """Gracefully stop all registered MCP servers."""
    return _graceful_stop_impl(load_mcp_pids, save_mcp_pids, write_mcp_issue)


def preflight_check() -> dict:
    """Preflight check to clean up orphaned PIDs and validate ports."""
    return _preflight_check_impl(load_mcp_pids, save_mcp_pids, remove_pid_from_registry, write_mcp_issue)


# ---- CLI ----


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="MCP Server Health Monitor")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuous monitoring loop",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check only, no action on stalled processes",
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
    parser.add_argument(
        "--graceful-stop",
        action="store_true",
        help="Gracefully stop all MCP servers and clean up",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Run preflight check (clean orphans, validate ports)",
    )
    parser.add_argument(
        "--scan-orphans",
        action="store_true",
        help="Scan system for orphaned MCP processes (ppid=1)",
    )
    args = parser.parse_args()

    def _print_or_json(title: str, results: dict) -> None:
        if args.json:
            _out(json.dumps(results, indent=2))
        else:
            _out(title)
            _out("=" * 50)
            for key, val in results.items():
                if isinstance(val, list):
                    _out(f"{key}: {len(val)}")
                    for item in val:
                        _out(f"  - {item}" if isinstance(item, str) else f"  - {item}")
                elif isinstance(val, dict):
                    _out(f"{key}: {val}")
                else:
                    _out(f"{key}: {val}")

    if args.graceful_stop:
        _print_or_json("Graceful Stop Results", graceful_stop())
        return 0

    if args.preflight:
        _print_or_json("Preflight Check Results", preflight_check())
        return 0

    if args.scan_orphans:
        results = scan_system_orphans(
            dry_run=args.check, allowlist_pids={os.getpid()}, write_issue_fn=write_mcp_issue,
        )
        _print_or_json(f"System Orphan Scan ({'DRY RUN' if args.check else 'ACTIVE'})", results)
        return 0

    if args.loop:
        monitor_loop(args.interval)
        return 0

    statuses = check_mcp_health(check_only=args.check)
    summary = get_summary(statuses)

    if args.json:
        output = {
            "summary": summary,
            "servers": [s.to_dict() for s in statuses],
        }
        _out(json.dumps(output, indent=2))
    else:
        _out("MCP Health Status")
        _out("=" * 50)
        _out(f"Mode: {summary['mode']}")
        _out(f"Total servers: {summary['total']}")
        _out(f"Alive: {summary['alive']}")
        _out(f"Responsive: {summary['responsive']}")
        _out(f"Stalled: {summary['stalled']}")
        _out(f"Dead: {summary['dead']}")
        _out(f"Actions taken: {summary['actions_taken']}")

        if statuses:
            _out("\nServer Details:")
            for status in statuses:
                icon = "OK" if status.is_responsive else ("STALLED" if status.is_alive else "DEAD")
                action = f" [{status.action_taken}]" if status.action_taken != "none" else ""
                _out(f"  {status.name}: {icon} (PID {status.pid}){action}")

    return 0 if summary["stalled"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
