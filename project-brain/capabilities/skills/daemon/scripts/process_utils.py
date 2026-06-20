"""Process utility helpers for MCP health monitoring.

Provides low-level process inspection, killing, and command execution
used by both the health monitor and the orphan scanner.
"""
from __future__ import annotations

import os
import signal
import shutil
import sys
import time
from subprocess import DEVNULL, CompletedProcess, run  # nosec B404
from typing import Any, Optional


IS_WINDOWS = sys.platform == "win32"
SIGTERM_TIMEOUT_SECONDS = 5


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve command executable to absolute path when available."""
    if not command:
        return command
    resolved = shutil.which(command[0])
    if resolved:
        return [resolved, *command[1:]]
    return command


def run_command(command: list[str], **kwargs: Any) -> CompletedProcess[str]:
    """Run subprocess command with resolved executable path."""
    if IS_WINDOWS:
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | 0x08000000
    return run(_resolve_command(command), **kwargs)  # nosec B603


def is_pid_alive(pid: int) -> bool:
    """Check if a PID exists."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError):
        return False
    except PermissionError:
        return True  # Process exists but we can't signal it


def get_process_state(pid: int) -> Optional[str]:
    """Get process state on Unix systems."""
    if IS_WINDOWS:
        return None

    try:
        result = run_command(
            ["ps", "-o", "state=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def is_process_responsive(pid: int) -> bool:
    """
    Check if a process is responsive (not stalled).

    Checks:
    1. Process exists
    2. Not in zombie (Z) or uninterruptible sleep (D) state
    """
    if not is_pid_alive(pid):
        return False

    state = get_process_state(pid)
    if state:
        # D = uninterruptible sleep, Z = zombie, T = stopped
        if state.startswith(("D", "Z", "T")):
            return False

    return True


def kill_process(pid: int, graceful: bool = True) -> bool:
    """Kill a process, optionally trying graceful shutdown first."""
    if not is_pid_alive(pid):
        return True

    try:
        if IS_WINDOWS:
            run_command(
                ["taskkill", "/F", "/PID", str(pid)],
                check=False,
                stdout=DEVNULL,
                stderr=DEVNULL,
            )
        else:
            if graceful:
                os.kill(pid, signal.SIGTERM)
                # Wait for graceful termination
                for _ in range(SIGTERM_TIMEOUT_SECONDS * 10):
                    if not is_pid_alive(pid):
                        return True
                    time.sleep(0.1)

            os.kill(pid, signal.SIGKILL)

        time.sleep(0.5)
        return not is_pid_alive(pid)

    except ProcessLookupError:
        return True
    except Exception:
        return False
