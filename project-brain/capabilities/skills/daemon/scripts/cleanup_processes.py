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
# TODO_CLEANUP: This file is 800 lines — consider splitting into smaller modules

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


_NO_WINDOW_CREATIONFLAGS = 0x08000000 if sys.platform == "win32" else 0


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


from src.config.paths import get_launch_agents_dir, get_logs_dir, get_project_name, get_project_port, get_runtime_dir

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

try:
    import dashboard_lifecycle
except ImportError:
    dashboard_lifecycle = None

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
    if _NO_WINDOW_CREATIONFLAGS:
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | _NO_WINDOW_CREATIONFLAGS
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


def get_pids_on_port(port: int | None = None) -> Set[str]:
    """Find PIDs listening (server) on a specific port.

    Only returns server processes (LISTEN state), not client connections
    like browser tabs connected to the port.
    """
    if port is None:
        port = get_project_port()
    pids = set()

    if IS_WINDOWS:
        output = run_command(["netstat", "-ano"])
        for line in output.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.strip().split()
                if parts:
                    pids.add(parts[-1])
    else:
        # lsof -i:PORT -sTCP:LISTEN — only server/listening processes
        output = run_command(["lsof", "-t", f"-i:{port}", "-sTCP:LISTEN"])
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
        pid_int = int(pid)
    except (TypeError, ValueError):
        return False

    if IS_WINDOWS:
        output = run_command(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Get-Process -Id {pid_int} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id",
            ],
            timeout=2,
        )
        return any(line.strip() == str(pid_int) for line in output.splitlines())

    try:
        os.kill(pid_int, 0)
        return True
    except (ProcessLookupError, ValueError, OSError):
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
        if IS_WINDOWS:
            return is_pid_alive(pid)

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


def _get_process_group(pid: str) -> Optional[int]:
    """Get the process group ID (PGID) for a PID."""
    if IS_WINDOWS:
        return None
    output = run_command(["ps", "-o", "pgid=", "-p", pid])
    pgid = output.strip()
    if pgid.isdigit():
        return int(pgid)
    return None


def _windows_process_record(pid: str) -> dict[str, Any] | None:
    """Read minimal Windows process metadata for parent-chain cleanup."""
    if not pid or not str(pid).isdigit():
        return None
    ps_cmd = (
        f"Get-CimInstance Win32_Process -Filter \"ProcessId = {int(pid)}\" | "
        "Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    )
    output = run_command(["powershell", "-NoProfile", "-Command", ps_cmd], timeout=2)
    if not output:
        return None
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return None
    if isinstance(data, list):
        data = data[0] if data else None
    return data if isinstance(data, dict) else None


def _is_dashboard_process_record(record: dict[str, Any] | None) -> bool:
    """Return True for processes that are part of dashboard build/dev trees."""
    if not record:
        return False
    haystack = f"{record.get('Name', '')} {record.get('CommandLine', '')}".lower()
    if not haystack.strip():
        return False
    return any(
        marker in haystack
        for marker in (
            "build-lock",
            "next dev",
            "next-server",
            "pnpm",
            "apps\\dashboard",
            "apps/dashboard",
        )
    )


def _windows_dashboard_tree_root_pid(pid: str) -> str:
    """Find the highest dashboard-related ancestor for a Windows listener PID."""
    current = str(pid)
    best = current
    seen: set[str] = set()
    while current not in seen:
        seen.add(current)
        current_record = _windows_process_record(current)
        parent = current_record.get("ParentProcessId") if current_record else None
        parent_pid = str(parent or "").strip()
        if not parent_pid.isdigit() or parent_pid == "0":
            break
        parent_record = _windows_process_record(parent_pid)
        if not _is_dashboard_process_record(parent_record):
            break
        best = parent_pid
        current = parent_pid
    return best


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


def kill_process_group(pid: str, graceful: bool = True, timeout: int = 5) -> bool:
    """
    Kill the entire process group that a PID belongs to.

    This is essential for processes like next dev where the listener
    (next-server) is a child — killing only the child lets the parent
    respawn it. Killing the group takes down the entire tree.

    Args:
        pid: Any PID in the process group.
        graceful: If True, try SIGTERM first, then SIGKILL.
        timeout: Seconds to wait for graceful termination.

    Returns:
        True if the group was killed.
    """
    if IS_WINDOWS:
        return kill_process_tree(_windows_dashboard_tree_root_pid(pid))

    pgid = _get_process_group(pid)
    if pgid is None or pgid <= 1:
        # No group or init group — fall back to single-process kill
        return kill_pid(pid, graceful, timeout)

    logger.info(f"Killing process group {pgid} (from PID {pid})...")

    try:
        if graceful:
            os.killpg(pgid, signal.SIGTERM)
            for _ in range(timeout * 10):
                if not is_pid_alive(pid):
                    logger.info(f"Process group {pgid} terminated gracefully")
                    return True
                time.sleep(0.1)
            logger.warning(f"Process group {pgid} did not respond to SIGTERM, sending SIGKILL")

        os.killpg(pgid, signal.SIGKILL)
        time.sleep(0.5)
        return not is_pid_alive(pid)

    except ProcessLookupError:
        return True
    except PermissionError:
        logger.warning(f"Permission denied killing group {pgid}, falling back to single PID")
        return kill_pid(pid, graceful, timeout)
    except Exception as e:
        logger.error(f"Failed to kill process group {pgid}: {e}")
        return kill_pid(pid, graceful, timeout)


def kill_process_tree(pid: str) -> bool:
    """Kill a Windows process and its descendants."""
    if not pid or not is_pid_alive(pid):
        return True
    if not IS_WINDOWS:
        return kill_process_group(pid)

    logger.info(f"Killing process tree for PID {pid}...")
    try:
        _run_command(
            ["taskkill", "/F", "/T", "/PID", pid],
            check=False,
            stdout=DEVNULL,
            stderr=DEVNULL,
        )
        time.sleep(0.5)
        return not is_pid_alive(pid)
    except Exception as e:
        logger.error(f"Failed to kill process tree for PID {pid}: {e}")
        return False


LAUNCHD_DASHBOARD_LABEL = f"com.{get_project_name().lower()}.dashboard"
LAUNCHD_DASHBOARD_PLIST = get_launch_agents_dir() / f"{LAUNCHD_DASHBOARD_LABEL}.plist"


def _stop_launchd_service(label: str = LAUNCHD_DASHBOARD_LABEL) -> bool:
    """Unload a launchd service to fully stop it and prevent auto-restart.

    Uses `launchctl unload` which stops the process AND removes the job
    from launchd. This is necessary because `launchctl stop` with
    KeepAlive=true will immediately respawn the process.

    Returns True if the service was loaded and successfully unloaded.
    """
    if IS_WINDOWS or IS_LINUX:
        return False

    plist = LAUNCHD_DASHBOARD_PLIST
    if not plist.exists():
        logger.debug(f"launchd plist not found: {plist}")
        return False

    # Check if service is loaded
    result = _run_command(
        ["launchctl", "list", label],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.debug(f"launchd service '{label}' not loaded")
        return False

    logger.info(f"Unloading launchd service '{label}' to prevent auto-restart...")
    result = _run_command(
        ["launchctl", "unload", str(plist)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        logger.info(f"Unloaded launchd service '{label}'")
        return True
    else:
        logger.warning(f"Failed to unload launchd service '{label}': {result.stderr.strip()}")
        return False


def _start_launchd_service(label: str = LAUNCHD_DASHBOARD_LABEL) -> bool:
    """Load a launchd service plist to start it.

    Uses `launchctl load` which registers the job and starts it
    (because RunAtLoad=true in the plist).
    """
    if IS_WINDOWS or IS_LINUX:
        return False

    plist = LAUNCHD_DASHBOARD_PLIST
    if not plist.exists():
        logger.debug(f"launchd plist not found: {plist}")
        return False

    result = _run_command(
        ["launchctl", "load", str(plist)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        logger.info(f"Loaded launchd service '{label}'")
        return True
    else:
        logger.warning(f"Failed to load launchd service '{label}': {result.stderr.strip()}")
        return False



def _cleanup_next_lock(dashboard_dir: Optional[Path] = None) -> bool:
    """Remove stale .next/dev/lock file left by a killed next dev process."""
    if dashboard_dir is None:
        dashboard_dir = PROJECT_ROOT / "apps" / "dashboard"
    lock_file = dashboard_dir / ".next" / "dev" / "lock"
    if lock_file.exists():
        try:
            lock_file.unlink()
            logger.info(f"Removed stale lock file: {lock_file}")
            return True
        except OSError as e:
            logger.warning(f"Could not remove lock file {lock_file}: {e}")
            return False
    return False


def _dashboard_build_lock_meta_paths() -> list[Path]:
    """Return main dashboard build lock metadata paths, newest first."""
    locks_dir = get_runtime_dir() / "locks"
    return [
        locks_dir / "dashboard" / "main" / "dashboard_build.lock.meta",
        locks_dir / "dashboard" / "main" / "dashboard_build.flock.meta",
        locks_dir / "dashboard_build.lock.meta",
        locks_dir / "dashboard_build.flock.meta",
    ]


def _get_build_lock_holder_pid() -> Optional[str]:
    """Return the PID recorded in main dashboard build lock metadata, if alive."""
    for lock_meta in _dashboard_build_lock_meta_paths():
        if not lock_meta.exists():
            continue
        try:
            data = json.loads(lock_meta.read_text())
        except Exception:
            continue

        pid = str(data.get("pid", "")).strip()
        if pid.isdigit() and is_pid_alive(pid):
            return pid
    return None


def cleanup_port(port: int | None = None, check_only: bool = False, force: bool = False) -> dict:
    """
    Cleanup processes on a specific port.

    Args:
        port: Port number to clean up (default from project.yaml).
        check_only: If True, only report — don't kill.
        force: If True, kill processes regardless of daemon mode.
               Use this during explicit reload operations.

    Returns:
        Dict with results
    """
    if port is None:
        port = get_project_port()

    # Request permission from lifecycle gate
    if dashboard_lifecycle and not force:
        gate = dashboard_lifecycle.request_action(
            "cleanup_processes", "stop",
            f"cleanup_port(port={port}, force={force})",
            instance_id="main",
        )
        if gate["decision"] == "denied":
            logger.warning(f"Lifecycle gate denied cleanup: {gate['reason']}")
            return {
                "port": port,
                "found": [],
                "killed": [],
                "failed": [],
                "mode": get_daemon_mode(),
                "force": force,
                "gate_denied": True,
                "gate_reason": gate["reason"],
            }
    elif dashboard_lifecycle and force:
        dashboard_lifecycle.request_action(
            "cleanup_processes", "stop",
            f"cleanup_port(port={port}, force=True)",
            force=True,
            instance_id="main",
        )

    results = {
        "port": port,
        "found": [],
        "killed": [],
        "failed": [],
        "mode": get_daemon_mode(),
        "force": force,
    }

    # Prevent auto-restart during cleanup:
    # 1. Lifecycle gate (called above) coordinates with dashboard_monitor
    # 2. Unload launchd service so macOS doesn't respawn (KeepAlive=true)
    launchd_stopped = False
    pids = get_pids_on_port(port)
    if force and port == get_project_port() and not check_only:
        if dashboard_lifecycle:
            dashboard_lifecycle.log_event(
                "cleanup_processes", "stop",
                f"force cleanup starting on port {port}",
                instance_id="main",
            )
        if IS_MACOS:
            launchd_stopped = _stop_launchd_service()
            if launchd_stopped:
                # Give launchd a moment to stop the process — may already be dead
                time.sleep(1)
                # Re-check what's still alive after launchd stop
                pids = get_pids_on_port(port)

        build_holder_pid = _get_build_lock_holder_pid()
        if build_holder_pid and build_holder_pid not in pids:
            logger.info(
                f"Force cleanup: killing active dashboard build holder PID {build_holder_pid}",
            )
            if kill_process_group(build_holder_pid):
                results["killed"].append(build_holder_pid)
            else:
                results["failed"].append(build_holder_pid)

    results["launchd_stopped"] = launchd_stopped

    if not pids:
        logger.info(f"No processes found on port {port}")
        # Still clean up stale lock files even if no PIDs found on port
        if port == get_project_port() and not check_only:
            _cleanup_next_lock()
        return results

    logger.info(f"Found {len(pids)} process(es) on port {port}")

    for pid in pids:
        info = get_process_info(pid)
        info.port = port
        results["found"].append(info.to_dict())

        if check_only:
            continue

        if force or is_production_mode():
            # With --force, kill the entire process group to prevent respawn.
            # E.g. next-server is a child of next dev — killing only next-server
            # lets next dev respawn it immediately.
            kill_fn = kill_process_group if force else kill_pid
            if kill_fn(pid):
                results["killed"].append(pid)
                logger.info(f"Killed PID {pid} ({info.name})")
            else:
                results["failed"].append(pid)
                logger.error(f"Failed to kill PID {pid}")
        else:
            # Dev mode without --force: notify only
            notify(f"Process {info.name} (PID {pid}) found on port {port}")
            logger.info(f"[DEV MODE] Would kill PID {pid} — use --force to kill")

    # Clean up stale .next/dev/lock after killing dashboard processes.
    # Sleep briefly to let dying processes release file handles, then remove.
    if port == get_project_port() and results["killed"]:
        time.sleep(0.5)
        _cleanup_next_lock()

    return results


def cleanup_mcp(check_only: bool = False, force: bool = False) -> dict:
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

        # Only kill stalled processes automatically (or all with --force)
        if not info.is_responsive or force:
            if force or is_production_mode():
                if kill_pid(pid):
                    results["killed"].append(pid)
                    logger.info(f"Killed MCP PID {pid}")
                else:
                    results["failed"].append(pid)
            else:
                notify(f"Stalled MCP process detected: PID {pid}")
                logger.info(f"[DEV MODE] Would kill stalled MCP PID {pid} — use --force to kill")

    return results


def cleanup_all(check_only: bool = False, force: bool = False) -> dict:
    """
    Cleanup all known process types.

    Returns:
        Combined results
    """
    dashboard_port = get_project_port()
    return {
        f"port_{dashboard_port}": cleanup_port(dashboard_port, check_only, force=force),
        "mcp": cleanup_mcp(check_only, force=force),
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
        help=f"Cleanup specific port (default: {get_project_port()})",
    )
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="Cleanup MCP processes only",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force kill processes regardless of daemon mode (use during reload)",
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
        results = cleanup_port(args.port, args.check, force=args.force)
    elif args.mcp:
        results = cleanup_mcp(args.check, force=args.force)
    else:
        results = cleanup_all(args.check, force=args.force)

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
            dashboard_port = get_project_port()
            port_found = len(results.get(f"port_{dashboard_port}", {}).get("found", []))
            mcp_found = len(results.get("mcp", {}).get("found", []))
            _out(f"\nPort {dashboard_port}: {port_found} found")
            _out(f"MCP: {mcp_found} found")

        _out("\nCleanup complete.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
