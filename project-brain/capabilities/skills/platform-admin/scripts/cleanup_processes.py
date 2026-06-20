#!/usr/bin/env python3
"""
Cross-Platform Process Cleanup Utility.

A unified script for cleaning up stale processes:
1. Dashboard processes on port 3000
2. Zombie MCP server processes
3. Stalled PIDs that exist but are unresponsive

Supports mode-aware behavior:
- Production: Auto-kill stalled processes
- Dev: Notify only, preserve for debugging

Usage:
    python3 cleanup_processes.py              # Interactive cleanup
    python3 cleanup_processes.py --check      # Check only, no kill
    python3 cleanup_processes.py --port 3000  # Cleanup specific port
    python3 cleanup_processes.py --mcp        # Cleanup MCP processes only
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from subprocess import DEVNULL, CompletedProcess, TimeoutExpired, run  # nosec B404
from typing import Any, Optional, Set


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Setup project root
from bootstrap_paths import ensure_project_paths  # noqa: E402

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
    from daemon_mode import get_daemon_mode, is_production_mode
except ImportError:

    def get_daemon_mode():
        return os.environ.get("AUGUR_MODE", "production")

    def is_production_mode():
        return get_daemon_mode() == "production"


try:
    from notification_service import notify
except ImportError:

    def notify(message: str, channel: str = "system"):
        _out(f"[NOTIFY] {message}")


logger = get_entity_logger("cleanup_processes")

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve executable path when available."""
    if not command:
        return command
    resolved = shutil.which(command[0])
    if resolved:
        return [resolved, *command[1:]]
    return command


def _run_command(command: list[str], **kwargs: Any) -> CompletedProcess[str]:
    """Run subprocess command with resolved executable path."""
    return run(_resolve_command(command), **kwargs)  # nosec B603


@dataclass
class ProcessInfo:
    """Information about a process."""

    pid: str
    name: str
    command: str = ""
    port: Optional[int] = None
    is_responsive: bool = True
    checked_at: str = ""

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "name": self.name,
            "command": self.command,
            "port": self.port,
            "is_responsive": self.is_responsive,
            "checked_at": self.checked_at,
        }


def run_command(cmd: list[str], timeout: int = 10) -> str:
    """Run a command and return stdout as string."""
    try:
        result = _run_command(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        return result.stdout.strip()
    except TimeoutExpired:
        logger.warning(f"Command timed out: {' '.join(cmd)}")
        return ""
    except Exception as e:
        logger.debug(f"Error running command {' '.join(cmd)}: {e}")
        return ""


def get_pids_on_port(port: int = 3000) -> Set[str]:
    """Find PIDs listening on a specific port."""
    pids = set()

    if IS_WINDOWS:
        output = run_command(["netstat", "-ano"])
        for line in output.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.strip().split()
                if parts:
                    pids.add(parts[-1])
    else:
        # lsof -t -i:PORT
        output = run_command(["lsof", "-t", f"-i:{port}"])
        for line in output.splitlines():
            if line.strip().isdigit():
                pids.add(line.strip())

    return pids


def get_mcp_pids() -> Set[str]:
    """Find PIDs of processes matching 'mcp'."""
    pids = set()

    if IS_WINDOWS:
        ps_cmd = (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*mcp*' } | "
            "Select-Object -ExpandProperty ProcessId"
        )
        output = run_command(["powershell", "-NoProfile", "-Command", ps_cmd])
        for line in output.splitlines():
            if line.strip().isdigit():
                pids.add(line.strip())
    else:
        # pgrep -f "mcp"
        output = run_command(["pgrep", "-f", "mcp"])
        for line in output.splitlines():
            pid = line.strip()
            if pid.isdigit() and pid != str(os.getpid()):
                pids.add(pid)

    return pids


def is_pid_alive(pid: str) -> bool:
    """Check if a PID exists and is running."""
    try:
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, ValueError):
        return False
    except PermissionError:
        # Process exists but we don't have permission
        return True


def is_pid_responsive(pid: str, timeout: float = 2.0) -> bool:
    """
    Check if a process is responsive (not stalled).

    For now, we check if the process responds to signal 0.
    Future: could add more sophisticated checks like /health endpoints.
    """
    try:
        # Basic liveness check
        os.kill(int(pid), 0)

        # For MCP processes, we could check if they respond to stdin/stdout
        # For dashboard, we could check HTTP health endpoint
        # For now, just check process state on Unix

        if not IS_WINDOWS:
            # Check process state via /proc or ps
            output = run_command(["ps", "-o", "state=", "-p", pid], timeout=2)
            if output:
                state = output.strip()
                # D = uninterruptible sleep (usually I/O), Z = zombie
                if state.startswith(("D", "Z")):
                    return False

        return True
    except Exception:
        return False


def get_process_info(pid: str) -> ProcessInfo:
    """Get detailed information about a process."""
    info = ProcessInfo(
        pid=pid,
        name="unknown",
        checked_at=datetime.now().isoformat(),
    )

    if IS_WINDOWS:
        ps_cmd = f"Get-Process -Id {pid} | Select-Object -Property Name,CommandLine | ConvertTo-Json"
        output = run_command(["powershell", "-NoProfile", "-Command", ps_cmd])
        if output:
            try:
                data = json.loads(output)
                info.name = data.get("Name", "unknown")
                info.command = data.get("CommandLine", "")
            except json.JSONDecodeError:
                pass
    else:
        # Get process name
        output = run_command(["ps", "-o", "comm=", "-p", pid])
        if output:
            info.name = output.strip()

        # Get full command
        output = run_command(["ps", "-o", "args=", "-p", pid])
        if output:
            info.command = output.strip()

    info.is_responsive = is_pid_responsive(pid)
    return info


def kill_pid(pid: str, graceful: bool = True, timeout: int = 5) -> bool:
    """
    Kill a process by PID.

    Args:
        pid: Process ID to kill
        graceful: If True, try SIGTERM first, then SIGKILL
        timeout: Seconds to wait for graceful termination

    Returns:
        True if process was killed or doesn't exist
    """
    if not pid or not is_pid_alive(pid):
        return True

    logger.info(f"Killing PID {pid}...")

    try:
        if IS_WINDOWS:
            _run_command(
                ["taskkill", "/F", "/PID", pid],
                check=False,
                stdout=DEVNULL,
                stderr=DEVNULL,
            )
        else:
            if graceful:
                # Try SIGTERM first
                os.kill(int(pid), signal.SIGTERM)

                # Wait for process to terminate
                for _ in range(timeout * 10):
                    if not is_pid_alive(pid):
                        logger.info(f"PID {pid} terminated gracefully")
                        return True
                    time.sleep(0.1)

                # If still alive, use SIGKILL
                logger.warning(f"PID {pid} did not respond to SIGTERM, sending SIGKILL")

            os.kill(int(pid), signal.SIGKILL)

        # Verify it's dead
        time.sleep(0.5)
        return not is_pid_alive(pid)

    except ProcessLookupError:
        return True  # Already dead
    except Exception as e:
        logger.error(f"Failed to kill PID {pid}: {e}")
        return False


def cleanup_port(port: int = 3000, check_only: bool = False) -> dict:
    """
    Cleanup processes on a specific port.

    Returns:
        Dict with results
    """
    results = {
        "port": port,
        "found": [],
        "killed": [],
        "failed": [],
        "mode": get_daemon_mode(),
    }

    pids = get_pids_on_port(port)

    if not pids:
        logger.info(f"No processes found on port {port}")
        return results

    logger.info(f"Found {len(pids)} process(es) on port {port}")

    for pid in pids:
        info = get_process_info(pid)
        info.port = port
        results["found"].append(info.to_dict())

        if check_only:
            continue

        if is_production_mode():
            if kill_pid(pid):
                results["killed"].append(pid)
                logger.info(f"Killed PID {pid} ({info.name})")
            else:
                results["failed"].append(pid)
                logger.error(f"Failed to kill PID {pid}")
        else:
            # Dev mode: notify only
            notify(f"Process {info.name} (PID {pid}) found on port {port}")
            logger.info(f"[DEV MODE] Would kill PID {pid} ({info.name})")

    return results


def cleanup_mcp(check_only: bool = False) -> dict:
    """
    Cleanup zombie MCP processes.

    Returns:
        Dict with results
    """
    results = {
        "type": "mcp",
        "found": [],
        "killed": [],
        "failed": [],
        "stalled": [],
        "mode": get_daemon_mode(),
    }

    pids = get_mcp_pids()

    if not pids:
        logger.info("No MCP processes found")
        return results

    logger.info(f"Found {len(pids)} MCP process(es)")

    for pid in pids:
        info = get_process_info(pid)
        results["found"].append(info.to_dict())

        # Check if stalled
        if not info.is_responsive:
            results["stalled"].append(pid)
            logger.warning(f"MCP process {pid} is stalled")

        if check_only:
            continue

        # Only kill stalled processes automatically
        if not info.is_responsive:
            if is_production_mode():
                if kill_pid(pid):
                    results["killed"].append(pid)
                    logger.info(f"Killed stalled MCP PID {pid}")
                else:
                    results["failed"].append(pid)
            else:
                notify(f"Stalled MCP process detected: PID {pid}")
                logger.info(f"[DEV MODE] Would kill stalled MCP PID {pid}")

    return results


def cleanup_all(check_only: bool = False) -> dict:
    """
    Cleanup all known process types.

    Returns:
        Combined results
    """
    return {
        "port_3000": cleanup_port(3000, check_only),
        "mcp": cleanup_mcp(check_only),
        "timestamp": datetime.now().isoformat(),
    }


def write_cleanup_log(results: dict) -> None:
    """Write cleanup results to log file."""
    log_dir = get_logs_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "cleanup_processes.log"

    entry = {
        "timestamp": datetime.now().isoformat(),
        "results": results,
    }

    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Cross-platform process cleanup utility")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check only, don't kill processes",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Cleanup specific port (default: 3000)",
    )
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="Cleanup MCP processes only",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress output",
    )
    args = parser.parse_args()

    if args.quiet:
        logger.setLevel("ERROR")

    mode = get_daemon_mode()
    if not args.json:
        _out(f"Daemon Mode: {mode}")
        _out("=" * 50)

    if args.port:
        results = cleanup_port(args.port, args.check)
    elif args.mcp:
        results = cleanup_mcp(args.check)
    else:
        results = cleanup_all(args.check)

    # Log results
    write_cleanup_log(results)

    if args.json:
        _out(json.dumps(results, indent=2))
    else:
        if args.port or args.mcp:
            found = len(results.get("found", []))
            killed = len(results.get("killed", []))
            _out(f"\nFound: {found}, Killed: {killed}")
        else:
            port_found = len(results.get("port_3000", {}).get("found", []))
            mcp_found = len(results.get("mcp", {}).get("found", []))
            _out(f"\nPort 3000: {port_found} found")
            _out(f"MCP: {mcp_found} found")

        _out("\nCleanup complete.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
