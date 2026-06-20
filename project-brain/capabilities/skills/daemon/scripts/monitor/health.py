"""Health check logic for the dashboard monitor.

Includes HTTP health probes, dashboard status aggregation, fatal build error
detection, and runtime incident detection.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from ._base import (
    DASHBOARD_PORT,
    DASHBOARD_STDERR_LOG,
    DEFAULT_DASHBOARD_STDERR_LOG,
    FATAL_BUILD_PATTERNS,
    FATAL_STDERR_MAX_AGE_SECONDS,
    FATAL_STDERR_TAIL_LINES,
    LOCK_CONFLICT_THRESHOLD,
    RUNTIME_INCIDENT_WINDOW_SECONDS,
    RUNTIME_TIMEOUT_THRESHOLD,
    _augmented_env,
    _resolve_command,
    get_daemon_mode,
    get_dashboard_dir,
    get_pids_on_port,
    get_runtime_dir,
    logger,
)
from .locks import get_build_lock_info, is_rebuild_in_progress

from subprocess import run  # nosec B404

# Module-level mutable state for runtime incident tracking
_runtime_incident_log_path: str | None = None
_runtime_incident_offset: int = 0


def reset_runtime_incident_cursor() -> None:
    """Move runtime incident scanning to the current end of the stderr log."""
    global _runtime_incident_log_path, _runtime_incident_offset

    stderr_log = DASHBOARD_STDERR_LOG
    if not stderr_log.exists():
        _runtime_incident_log_path = None
        _runtime_incident_offset = 0
        return

    try:
        _runtime_incident_log_path = str(stderr_log)
        _runtime_incident_offset = stderr_log.stat().st_size
    except OSError:
        _runtime_incident_log_path = None
        _runtime_incident_offset = 0


def is_dashboard_running() -> bool:
    """Check if the dashboard server is running on port 3000."""
    pids = get_pids_on_port(DASHBOARD_PORT)
    return len(pids) > 0


def check_dashboard_http_health(timeout: int = 5) -> int | None:
    """Perform an HTTP GET on the dashboard root and return the status code.

    Returns the HTTP status code (e.g. 200, 500) or None if the connection
    failed entirely (server not reachable).
    """
    try:
        with urlopen(  # nosec B310 -- localhost only
            f"http://localhost:{DASHBOARD_PORT}/",
            timeout=timeout,
        ) as resp:
            return resp.status
    except URLError as e:
        if hasattr(e, "code"):
            return e.code
        return None
    except Exception:
        return None


def get_dashboard_status() -> dict:
    """Get detailed dashboard status."""
    pids = get_pids_on_port(DASHBOARD_PORT)
    running = len(pids) > 0

    http_status = check_dashboard_http_health() if running else None
    healthy = http_status is not None and 200 <= http_status < 500

    # Only check build state when dashboard is NOT healthy.
    rebuild_in_progress = False if healthy else is_rebuild_in_progress()

    return {
        "running": running,
        "healthy": healthy,
        "http_status": http_status,
        "pids": list(pids),
        "rebuild_in_progress": rebuild_in_progress,
        "build_lock": get_build_lock_info(),
        "checked_at": datetime.now().isoformat(),
        "mode": get_daemon_mode(),
    }


def write_status(status: dict) -> None:
    """Write dashboard status to file."""
    stats_dir = get_runtime_dir() / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)

    status_file = stats_dir / "dashboard_status.json"
    import json
    status_file.write_text(json.dumps(status, indent=2))


def detect_fatal_build_errors() -> tuple[str, list[list[str]] | None, str] | None:
    """Read tail of dashboard.stderr.log for fatal patterns no restart can fix.

    Only inspects stderr modified within FATAL_STDERR_MAX_AGE_SECONDS to avoid
    acting on stale errors from a previous crash that has already been resolved.

    Returns (description, auto_fix_commands_or_None, manual_hint) or None.
    """
    stderr_log = DASHBOARD_STDERR_LOG
    if not stderr_log.exists():
        return None

    try:
        age = time.time() - stderr_log.stat().st_mtime
        if age > FATAL_STDERR_MAX_AGE_SECONDS:
            return None

        text = stderr_log.read_text(errors="replace")
        lines = text.splitlines()[-FATAL_STDERR_TAIL_LINES:]
        tail = "\n".join(lines)

        for pattern, description, auto_fix, manual_hint in FATAL_BUILD_PATTERNS:
            if pattern.search(tail):
                return description, auto_fix, manual_hint
    except Exception as e:
        logger.debug(f"Fatal error detection failed: {e}")

    return None


def detect_runtime_incident() -> dict[str, Any] | None:
    """Detect recent runtime degradation that leaves the process alive but unusable."""
    global _runtime_incident_log_path, _runtime_incident_offset

    stderr_log = DASHBOARD_STDERR_LOG
    if not stderr_log.exists():
        return None

    try:
        stat = stderr_log.stat()
        age = time.time() - stat.st_mtime
        if age > RUNTIME_INCIDENT_WINDOW_SECONDS:
            return None

        current_path = str(stderr_log)
        if _runtime_incident_log_path != current_path:
            _runtime_incident_log_path = current_path
            _runtime_incident_offset = (
                0
                if current_path != str(DEFAULT_DASHBOARD_STDERR_LOG)
                else stat.st_size
            )

        if stat.st_size < _runtime_incident_offset:
            _runtime_incident_offset = 0

        with stderr_log.open("r", errors="replace") as fh:
            fh.seek(_runtime_incident_offset)
            new_text = fh.read()
            _runtime_incident_offset = fh.tell()

        if not new_text:
            return None

        lines = new_text.splitlines()[-160:]
    except Exception as e:
        logger.debug(f"Runtime incident detection failed: {e}")
        return None

    timeout_count = sum("timed out after 60000ms" in line for line in lines)
    lock_conflicts = sum("Unable to acquire lock at" in line for line in lines)
    port_conflicts = sum(
        "Port 3000 is in use by an unknown process" in line for line in lines
    )

    reasons: list[str] = []
    if timeout_count >= RUNTIME_TIMEOUT_THRESHOLD:
        reasons.append(f"{timeout_count} API timeout(s)")
    if lock_conflicts >= LOCK_CONFLICT_THRESHOLD:
        reasons.append(f"{lock_conflicts} Next lock conflict(s)")
    if port_conflicts >= 1:
        reasons.append(f"{port_conflicts} port fallback(s)")

    degraded = timeout_count >= RUNTIME_TIMEOUT_THRESHOLD or (
        lock_conflicts >= LOCK_CONFLICT_THRESHOLD and port_conflicts >= 1
    )
    if not degraded:
        return None

    return {
        "type": "runtime_degraded",
        "timeout_count": timeout_count,
        "lock_conflicts": lock_conflicts,
        "port_conflicts": port_conflicts,
        "summary": ", ".join(reasons),
        "signature": f"{int(stat.st_mtime_ns)}:{_runtime_incident_offset}:{timeout_count}:{lock_conflicts}:{port_conflicts}",
    }


def attempt_auto_fix(description: str, fix_commands: list[list[str]]) -> bool:
    """Run auto-fix commands for a detected fatal build error.

    Returns True if all commands succeeded, False otherwise.
    """
    dashboard_dir = get_dashboard_dir()
    logger.info(f"Attempting auto-fix for: {description}")

    for cmd in fix_commands:
        logger.info(f"  Running: {' '.join(cmd)}")
        try:
            result = run(  # nosec B603
                _resolve_command(cmd),
                cwd=str(dashboard_dir),
                capture_output=True,
                text=True,
                timeout=120,
                env=_augmented_env(),
            )
            if result.returncode != 0:
                logger.error(
                    f"  Auto-fix command failed (rc={result.returncode}): "
                    f"{result.stderr[:300]}"
                )
                return False
            logger.info("  Command succeeded")
        except Exception as e:
            logger.error(f"  Auto-fix command error: {e}")
            return False

    logger.info(f"Auto-fix completed for: {description}")
    return True
