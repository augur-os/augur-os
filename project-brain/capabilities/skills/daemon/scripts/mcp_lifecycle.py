"""MCP server lifecycle management -- graceful shutdown and preflight checks.

Provides functions for stopping MCP servers and pre-startup cleanup.
Imported by mcp_health_monitor.py for CLI access.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from .bootstrap_paths import ensure_project_paths  # noqa: E402
except ImportError:
    from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

from src.config.paths import get_runtime_dir

try:
    from src.logging import get_entity_logger
except ImportError:
    import logging as _logging

    def get_entity_logger(name: str):
        logger = _logging.getLogger(name)
        if not logger.handlers:
            handler = _logging.StreamHandler()
            handler.setFormatter(_logging.Formatter('%(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(_logging.INFO)
        return logger

try:
    from .process_utils import is_pid_alive, is_process_responsive, kill_process
    from .orphan_scanner import scan_system_orphans
except ImportError:
    from process_utils import is_pid_alive, is_process_responsive, kill_process
    from orphan_scanner import scan_system_orphans

logger = get_entity_logger("mcp_lifecycle")


def graceful_stop(
    load_pids_fn,
    save_pids_fn,
    write_issue_fn=None,
) -> dict:
    """
    Gracefully stop all registered MCP servers.

    Args:
        load_pids_fn: Callable returning PID registry dict
        save_pids_fn: Callable to save PID registry dict
        write_issue_fn: Optional callback for issue logging

    Returns:
        Summary of shutdown actions
    """
    pids_data = load_pids_fn()
    servers = pids_data.get("servers", {})

    results = {
        "stopped": [],
        "failed": [],
        "not_running": [],
        "locks_released": [],
    }

    # Send SIGTERM to all registered servers
    for name, info in servers.items():
        pid = info.get("pid")
        if not pid:
            results["not_running"].append(name)
            continue

        if not is_pid_alive(pid):
            results["not_running"].append(name)
            continue

        logger.info(f"Sending SIGTERM to '{name}' (PID {pid})")
        if kill_process(pid, graceful=True):
            results["stopped"].append(name)
        else:
            results["failed"].append(name)

    # Clear PID registry
    save_pids_fn({"servers": {}})
    logger.info("Cleared MCP PID registry")

    # Release lock files
    runtime_dir = get_runtime_dir()
    lock_files = ["dashboard_rebuild.lock", "dashboard_reload.lock"]

    for lock_file in lock_files:
        lock_path = runtime_dir / lock_file
        if lock_path.exists():
            lock_path.unlink()
            results["locks_released"].append(lock_file)
            logger.info(f"Released lock: {lock_file}")

    return results


def preflight_check(
    load_pids_fn,
    save_pids_fn,
    remove_pid_fn,
    write_issue_fn=None,
) -> dict:
    """
    Preflight check to clean up orphaned PIDs and validate ports.

    Args:
        load_pids_fn: Callable returning PID registry dict
        save_pids_fn: Callable to save PID registry dict
        remove_pid_fn: Callable(name) to remove a PID from registry
        write_issue_fn: Optional callback for issue logging

    Returns:
        Summary of preflight actions
    """
    results = {
        "orphans_killed": [],
        "dead_pids_removed": [],
        "ports_validated": [],
        "port_conflicts": [],
    }

    pids_data = load_pids_fn()
    servers = pids_data.get("servers", {})

    # Scan for orphan/dead PIDs
    for name, info in servers.items():
        pid = info.get("pid")
        if not pid:
            continue

        # Check if process is alive
        if not is_pid_alive(pid):
            results["dead_pids_removed"].append(name)
            remove_pid_fn(name)
            logger.info(f"Preflight: Removed dead PID for '{name}'")
            continue

        # Check if process is stalled
        if not is_process_responsive(pid):
            logger.info(f"Preflight: Killing stalled process '{name}' (PID {pid})")
            if kill_process(pid):
                results["orphans_killed"].append(name)
                remove_pid_fn(name)

    # Validate registered ports
    for name, info in list(servers.items()):
        port = info.get("port")
        if port:
            try:
                import socket

                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(("localhost", port))
                sock.close()

                if result == 0:
                    # Port is in use
                    if not is_pid_alive(info.get("pid")):
                        results["port_conflicts"].append({"name": name, "port": port})
                        logger.warning(f"Preflight: Port {port} conflict for '{name}'")
                    else:
                        results["ports_validated"].append({"name": name, "port": port})
                else:
                    if is_pid_alive(info.get("pid")):
                        logger.warning(f"Preflight: '{name}' alive but port {port} not listening")
            except Exception as e:
                logger.debug(f"Preflight: Failed to validate port {port}: {e}")

    # System-level orphan scan (catches unregistered orphans)
    orphan_scan = scan_system_orphans(
        allowlist_pids={os.getpid()},
        write_issue_fn=write_issue_fn,
    )
    results["system_orphans"] = orphan_scan
    if orphan_scan["orphans_killed"]:
        logger.info(f"Preflight: System scan killed {orphan_scan['orphans_killed']} orphaned MCP process(es)")

    # Write clean registry
    save_pids_fn(pids_data)

    return results
