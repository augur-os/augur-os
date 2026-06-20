#!/usr/bin/env python3
"""
Unified Augur Daemon.

Single process that manages all background services as child subprocesses:
- log_monitor.py (persistent, 24/7)
- continuous_executor.py (persistent, 24/7)

Production Monitoring (ADR-041):
- dashboard_monitor.py (persistent, checks every 30s)
- mcp_health_monitor.py (persistent, checks every 60s)

Adaptive Loop Engine (ADR-176/180):
- adaptive_loop_executor.py (persistent, manages nightly/continuous/post-exec loops)
  Absorbed: nightly_maintainer, runtime_marker_scanner, ai_self_healer

Designed to run from within the Augur Daemon.app bundle so macOS
Background Activity shows "Augur" with proper icon instead of "python3".

Usage:
    python unified_daemon.py            # Start daemon (default, used by launchd)
    python unified_daemon.py start      # Same as above
    python unified_daemon.py stop       # Stop running daemon via PID file
    python unified_daemon.py status     # Show daemon and child service status
    python unified_daemon.py restart    # Stop + start
"""
# TODO_CLEANUP: This file is 811 lines — consider splitting into smaller modules

from __future__ import annotations

import argparse
import json
import os
os.environ["AUGUR_DAEMON"] = "1"
import signal
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from subprocess import DEVNULL, CompletedProcess, Popen, TimeoutExpired, run  # nosec B404
from typing import Any

def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Lazy import for notification service (avoid circular imports at startup)
_notification_service = None


try:
    from bootstrap_paths import ensure_project_paths, project_python_env
except ImportError:
    SCRIPTS_BOOTSTRAP_DIR = Path(__file__).resolve().parent
    if str(SCRIPTS_BOOTSTRAP_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_BOOTSTRAP_DIR))
    from bootstrap_paths import ensure_project_paths, project_python_env


PROJECT_ROOT = ensure_project_paths(__file__)

from src.config.paths import get_logs_dir, get_python_executable, get_runtime_dir, get_skill_root  # noqa: E402


def _bind_headless_streams() -> None:
    """Point stdout/stderr at the daemon logs when launched under pythonw.exe.

    pythonw.exe has no console, so sys.stdout/sys.stderr are None. This MUST run
    before any logger is created: logging.StreamHandler captures the stream at
    construction, so a None stream would make every log call raise. POSIX and
    console (python.exe) launches keep their real streams.
    """
    if sys.platform != "win32":
        return
    if sys.stdout is not None and sys.stderr is not None:
        return
    logs_dir = get_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
    if sys.stdout is None:
        sys.stdout = open(logs_dir / "daemon.stdout.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = open(logs_dir / "daemon.stderr.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115


_bind_headless_streams()

from src.logging import get_entity_logger  # noqa: E402
from skills.daemon.scripts import daemon_diagnostics  # noqa: E402

logger = get_entity_logger("unified_daemon")

# Per-service stderr log directory
_STDERR_LOGS_DIR = get_logs_dir() / "daemon" / "stderr"

# ═══════════════════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
RUNTIME_DIR = get_runtime_dir()
CRITICAL_DIR = RUNTIME_DIR / "self_heal" / "critical"
PID_FILE = RUNTIME_DIR / "daemon.pid"
STATUS_FILE = RUNTIME_DIR / "stats" / "daemon_status.json"
PYTHON = get_python_executable()

# Consecutive failures before giving up on a service
MAX_CONSECUTIVE_FAILURES = 3

_EXTRA_PATHS = [
    "/usr/bin",
    "/usr/sbin",
    "/opt/homebrew/bin",
    "/usr/local/bin",
    str(Path.home() / ".local" / "bin"),
    str(Path.home() / ".nvm" / "current" / "bin"),
    str(Path.home() / ".volta" / "bin"),
    "/usr/local/nodejs/bin",
]


def _resolve_skill_script(skill_name: str, *parts: str) -> Path | None:
    """Resolve an optional managed skill script from repo or vault roots."""
    try:
        script = get_skill_root(skill_name).joinpath(*parts)
    except ValueError:
        logger.info("Optional skill %s is not installed; skipping related daemon service", skill_name)
        return None
    if not script.is_file():
        logger.warning("Optional skill script missing for %s: %s", skill_name, script)
        return None
    return script


def _service_stderr_log_hint(service_name: str) -> str:
    """Return the runtime log location operators should inspect for a service."""
    return str(_STDERR_LOGS_DIR / f"{service_name}.stderr.log")


def _augmented_env() -> dict[str, str]:
    """Get environment with extra binary paths included."""
    env = project_python_env(PROJECT_ROOT)
    current_path = env.get("PATH", "")
    extra_paths = [p for p in _EXTRA_PATHS if Path(p).exists()]
    if extra_paths:
        env["PATH"] = os.pathsep.join(extra_paths + [current_path])
    return env


# ═══════════════════════════════════════════════════════════════════════════════
# CHILD SERVICE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

CHILD_SERVICES: dict[str, dict[str, Any]] = {
    "log_monitor": {
        "script": SCRIPTS_DIR / "log_monitor.py",
        "mode": "persistent",
        "restart_delay_seconds": 5,
        "max_restarts_per_hour": 10,
    },
    "continuous_executor": {
        "script": SCRIPTS_DIR / "continuous_executor.py",
        "mode": "persistent",
        "restart_delay_seconds": 10,
        "max_restarts_per_hour": 5,
    },
    # ─────────────────────────────────────────────────────────────────────────
    # ADR-041: Production Monitoring & Self-Healing
    # ─────────────────────────────────────────────────────────────────────────
    "dashboard_monitor": {
        "script": SCRIPTS_DIR / "dashboard_monitor.py",
        "args": ["--loop"],
        "mode": "persistent",
        "restart_delay_seconds": 10,
        "max_restarts_per_hour": 5,
        "description": "Monitors dashboard server, auto-restarts in production mode",
    },
    "mcp_health_monitor": {
        "script": SCRIPTS_DIR / "mcp_health_monitor.py",
        "args": ["--loop"],
        "mode": "persistent",
        "restart_delay_seconds": 15,
        "max_restarts_per_hour": 3,
        "description": "Monitors MCP servers for stalled PIDs",
    },
    # nightly_maintainer, runtime_marker_scanner, ai_self_healer absorbed into
    # adaptive_loop_engine (ADR-180: Adaptive Loops Consolidation)
    "insight_scanner": {
        "script": SCRIPTS_DIR / "insight_scanner.py",
        "args": ["--loop"],
        "mode": "persistent",
        "restart_delay_seconds": 60,
        "max_restarts_per_hour": 5,
        "description": "Proactive page insight generation via LLM analysis (ADR-078)",
    },
    # ─────────────────────────────────────────────────────────────────────────
    # ADR-176: Adaptive Loop Engine
    # ─────────────────────────────────────────────────────────────────────────
    "adaptive_loop_engine": {
        "script": SCRIPTS_DIR / "adaptive_loop_executor.py",
        "args": ["--loop"],
        "mode": "persistent",
        "restart_delay_seconds": 30,
        "max_restarts_per_hour": 3,
        "description": "Adaptive loop engine for autonomous self-improvement",
    },
    # ─────────────────────────────────────────────────────────────────────────
    # ADR-122: Filesystem-Driven Plugin Lifecycle
    # ─────────────────────────────────────────────────────────────────────────
    "plugin_watcher": {
        "script": SCRIPTS_DIR / "plugin_watcher.py",
        "args": ["--loop"],
        "mode": "persistent",
        "restart_delay_seconds": 15,
        "max_restarts_per_hour": 5,
        "description": "Polls top-level skills/ every 10s, emits skill_added/skill_removed events (ADR-122)",
    },
    # ─────────────────────────────────────────────────────────────────────────
    # ADR-130: Action Button Dispatch Modes — Schedule Executor
    # ─────────────────────────────────────────────────────────────────────────
    "schedule_executor": {
        "script": SCRIPTS_DIR / "schedule_executor.py",
        "args": ["--loop"],
        "mode": "persistent",
        "restart_delay_seconds": 30,
        "max_restarts_per_hour": 5,
        "description": "Executes due scheduled actions every 60s, walks skill schedule directories from vault data/assets (ADR-130)",
    },
    # ─────────────────────────────────────────────────────────────────────────
    # Notification Processor — process pending scheduled notifications
    # ─────────────────────────────────────────────────────────────────────────
    "notification_processor": {
        "script": SCRIPTS_DIR / "notification_service.py",
        "args": ["--loop"],
        "mode": "persistent",
        "restart_delay_seconds": 60,
        "max_restarts_per_hour": 3,
        "description": "Processes due scheduled notifications every 60s from state/daemon/notifications/pending.yaml",
    },
    # ─────────────────────────────────────────────────────────────────────────
    # RAG Incremental Sync — spec 2026-06-10
    # ─────────────────────────────────────────────────────────────────────────
    "rag_watcher": {
        "script": SCRIPTS_DIR / "rag_watcher.py",
        "args": ["--loop"],
        "mode": "persistent",
        "restart_delay_seconds": 15,
        "max_restarts_per_hour": 5,
        "heartbeat_file": str(get_runtime_dir() / "rag_watcher_state.json"),
        "heartbeat_timeout_seconds": 45,
        "description": "Watches brain roots via FSEvents, incrementally syncs the RAG index, owns the daily reconcile (spec 2026-06-10)",
    },
}

# ─────────────────────────────────────────────────────────────────────────
# ADR-158: Note Editing Integration — Apple-only services (macOS only)
# ─────────────────────────────────────────────────────────────────────────
if sys.platform == "darwin":
    note_watcher_script = _resolve_skill_script("apple", "scripts", "note_watcher.py")
    if note_watcher_script is not None:
        CHILD_SERVICES["note_watcher"] = {
            "script": note_watcher_script,
            "args": ["--loop"],
            "mode": "persistent",
            "restart_delay_seconds": 10,
            "max_restarts_per_hour": 5,
            "description": "Watches notes directories for changes, rebuilds cache, triggers sync (ADR-158)",
        }
    note_ingest_script = _resolve_skill_script("apple", "scripts", "note_ingest.py")
    if note_ingest_script is not None:
        CHILD_SERVICES["note_ingest"] = {
            "script": note_ingest_script,
            "args": ["--loop"],
            "mode": "persistent",
            "restart_delay_seconds": 60,
            "max_restarts_per_hour": 3,
            "description": "Polls Apple Notes inbox and ingests to local markdown (ADR-158)",
        }

# Shutdown flag
_shutdown = False


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve executable path when available."""
    if not command:
        return command
    resolved = shutil.which(command[0], path=_augmented_env().get("PATH"))
    if resolved:
        return [resolved, *command[1:]]
    return command


# Windows: the daemon itself runs under pythonw.exe (no console). A console-
# subsystem child (python.exe, npm, git, powershell) spawned from a parent
# without a console would otherwise allocate its OWN visible window. CREATE_NO_WINDOW
# gives the child a hidden console that its descendants inherit, so the whole
# daemon process tree stays windowless.
_NO_WINDOW_CREATIONFLAGS = (
    getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0)
    if sys.platform == "win32"
    else 0
)


def _apply_no_window(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Inject CREATE_NO_WINDOW on Windows without clobbering caller flags."""
    if _NO_WINDOW_CREATIONFLAGS:
        existing = int(kwargs.get("creationflags", 0) or 0)
        kwargs["creationflags"] = existing | _NO_WINDOW_CREATIONFLAGS
    return kwargs


def _popen_command(command: list[str], **kwargs: Any) -> Popen[Any]:
    """Start subprocess using resolved executable path."""
    return Popen(_resolve_command(command), **_apply_no_window(kwargs))  # nosec B603


def _run_command(command: list[str], **kwargs: Any) -> CompletedProcess[Any]:
    """Run a subprocess using resolved executable path."""
    return run(_resolve_command(command), **_apply_no_window(kwargs))  # nosec B603


def _graceful_stop_mcp_servers() -> None:
    """Call MCP health monitor's graceful stop to clean up server processes."""
    health_monitor = SCRIPTS_DIR / "mcp_health_monitor.py"
    if not health_monitor.exists():
        logger.warning("MCP health monitor not found, skipping graceful stop")
        return
    try:
        _run_command(
            [str(PYTHON), str(health_monitor), "--graceful-stop"],
            timeout=10,
            cwd=str(PROJECT_ROOT),
            stdout=DEVNULL,
            stderr=DEVNULL,
        )
        logger.info("MCP servers stopped gracefully")
    except Exception as e:
        logger.warning(f"Graceful MCP stop failed: {e}")


def _signal_handler(signum: int, _frame: Any) -> None:
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    global _shutdown
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    _graceful_stop_mcp_servers()  # Clean up MCP servers first
    _shutdown = True


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


# ═══════════════════════════════════════════════════════════════════════════════
# SUBPROCESS MANAGER
# ═══════════════════════════════════════════════════════════════════════════════


class SubprocessManager:
    """Manages a single child subprocess with health monitoring and restart."""

    def __init__(self, name: str, config: dict[str, Any]) -> None:
        self.name = name
        self.config = config
        self.script = Path(config["script"])
        self.args = config.get("args", [])  # Additional CLI arguments
        self.mode = config["mode"]
        self.restart_delay = config.get("restart_delay_seconds", 5)
        self.max_restart_delay = self.restart_delay * 32  # Cap backoff at 32x base
        self.max_restarts_per_hour = config.get("max_restarts_per_hour", 10)
        self.description = config.get("description", "")
        raw_heartbeat = config.get("heartbeat_file")
        self.heartbeat_file: Path | None = Path(raw_heartbeat) if raw_heartbeat else None
        self.heartbeat_timeout = float(config.get("heartbeat_timeout_seconds", 0) or 0)

        self.process: Popen[Any] | None = None
        self._stderr_file: Any | None = None
        self.restart_timestamps: list[float] = []
        self.total_restarts: int = 0
        self.consecutive_failures: int = 0
        self.last_started: str | None = None
        self.next_restart_at: float = 0  # Timestamp when next restart is allowed
        self.state: str = "stopped"  # stopped | running | scheduled | error

    def __del__(self) -> None:
        """Best-effort cleanup for abandoned manager instances."""
        self._close_stderr()

    def start(self) -> bool:
        """Launch the child subprocess."""
        if self.process and self.process.poll() is None:
            logger.warning(f"[{self.name}] Already running (PID {self.process.pid})")
            return True

        if not self.script.exists():
            logger.error(f"[{self.name}] Script not found: {self.script}")
            self.state = "error"
            return False

        if not PYTHON.exists():
            logger.error(f"[{self.name}] Python not found: {PYTHON}")
            self.state = "error"
            return False

        try:
            # Build command with optional arguments
            cmd = [str(PYTHON), str(self.script)] + self.args

            # Capture stderr to a per-service log file so child crashes are diagnosable
            _STDERR_LOGS_DIR.mkdir(parents=True, exist_ok=True)
            stderr_log_path = _STDERR_LOGS_DIR / f"{self.name}.stderr.log"
            self._stderr_file = open(stderr_log_path, "a")  # noqa: SIM115

            self.process = _popen_command(
                cmd,
                cwd=str(PROJECT_ROOT),
                env={**_augmented_env(), "PYTHONUNBUFFERED": "1"},
                stdout=DEVNULL,
                stderr=self._stderr_file,
            )
            self.state = "running"
            self.last_started = datetime.now().isoformat()
            self._clear_critical_item()
            logger.info(f"[{self.name}] Started (PID {self.process.pid})")
            return True
        except Exception as e:
            logger.error(f"[{self.name}] Failed to start: {e}")
            self._close_stderr()
            self.state = "error"
            return False

    def _close_stderr(self) -> None:
        """Close the stderr log file handle if open."""
        if self._stderr_file is not None:
            try:
                self._stderr_file.close()
            except Exception:
                pass
            self._stderr_file = None

    def stop(self, timeout: int = 10) -> None:
        """Gracefully stop via SIGTERM, then SIGKILL after timeout."""
        if not self.process or self.process.poll() is not None:
            self.state = "stopped"
            self.process = None
            return

        pid = self.process.pid
        logger.info(f"[{self.name}] Stopping (PID {pid})...")

        try:
            self.process.terminate()  # SIGTERM
            try:
                self.process.wait(timeout=timeout)
                logger.info(f"[{self.name}] Stopped gracefully")
            except TimeoutExpired:
                logger.warning(f"[{self.name}] SIGTERM timeout, sending SIGKILL")
                self.process.kill()
                self.process.wait(timeout=5)
        except Exception as e:
            logger.error(f"[{self.name}] Error stopping: {e}")

        self.process = None
        self._close_stderr()
        self.state = "stopped"

    def _backoff_delay(self) -> float:
        """Calculate exponential backoff delay based on consecutive failures."""
        delay = self.restart_delay * (2 ** min(self.consecutive_failures, 5))
        return min(delay, self.max_restart_delay)

    def check_health(self) -> dict[str, Any]:
        """Check if process is running, restart if crashed (persistent mode only)."""
        now = time.time()

        if not self.process:
            # critical_failure = permanently stopped until daemon restart
            if self.state == "critical_failure":
                return self._status_dict()
            # Retry persistent services after a scheduled backoff or circuit-breaker cooldown.
            if self.state in {"error", "scheduled"} and self.mode == "persistent" and not _shutdown:
                # Don't retry if the script doesn't exist (permanent error)
                if not self.script.exists():
                    return self._status_dict()
                # Wait for backoff delay before retrying
                if now < self.next_restart_at:
                    return self._status_dict()
                if self._check_circuit_breaker():
                    logger.info(
                        f"[{self.name}] Circuit breaker recovered, "
                        f"restarting (backoff {self._backoff_delay():.0f}s)..."
                    )
                    self.total_restarts += 1
                    self.restart_timestamps.append(now)
                    self.start()
            return self._status_dict()

        exit_code = self.process.poll()
        if exit_code is None:
            # Still running — reset consecutive failure counter after 60s uptime
            if self.last_started and self.consecutive_failures > 0:
                started_ts = datetime.fromisoformat(self.last_started).timestamp()
                if now - started_ts > 60:
                    self.consecutive_failures = 0
            # Heartbeat supervision: a stuck-but-alive child is a dead index.
            if self.heartbeat_file is not None and self.heartbeat_timeout > 0 and self.last_started:
                started_ts = datetime.fromisoformat(self.last_started).timestamp()
                grace = max(self.heartbeat_timeout * 2, 90.0)
                if now - started_ts > grace:
                    age = self._heartbeat_age_seconds(now)
                    if age is not None and age > self.heartbeat_timeout:
                        logger.error(
                            f"[{self.name}] heartbeat stale ({age:.0f}s > "
                            f"{self.heartbeat_timeout:.0f}s) — killing stuck process"
                        )
                        try:
                            self.process.kill()
                        except OSError:
                            pass
                        # Next check_health poll sees the exit and runs the
                        # standard restart/backoff bookkeeping.
            return self._status_dict()

        # Process exited
        logger.warning(f"[{self.name}] Exited with code {exit_code}")
        self.process = None
        self._close_stderr()
        self.consecutive_failures += 1

        if self.mode == "persistent" and not _shutdown:
            # After MAX_CONSECUTIVE_FAILURES, stop retrying and create critical item
            if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.error(
                    f"[{self.name}] Failed {self.consecutive_failures}x consecutively — "
                    f"stopping retries. Fix the root cause and restart the daemon."
                )
                self.state = "critical_failure"
                self._create_critical_item()
                self._notify_critical(f"Service {self.name} failed {self.consecutive_failures}x — stopped retrying")
                return self._status_dict()

            if self._check_circuit_breaker():
                delay = self._backoff_delay()
                self.next_restart_at = now + delay
                self.total_restarts += 1
                self.restart_timestamps.append(now)
                self.state = "scheduled"
                logger.info(
                    f"[{self.name}] Scheduling restart in {delay:.0f}s "
                    f"(attempt {self.total_restarts}, "
                    f"consecutive failures: {self.consecutive_failures})..."
                )
            else:
                delay = self._backoff_delay()
                self.next_restart_at = now + delay
                logger.error(
                    f"[{self.name}] Circuit breaker tripped — "
                    f"exceeded {self.max_restarts_per_hour} restarts/hour, "
                    f"will retry in {delay:.0f}s"
                )
                self.state = "error"
        elif self.mode == "scheduled":
            self.state = "scheduled"

        return self._status_dict()

    def _heartbeat_age_seconds(self, now: float) -> float | None:
        """Age of the child's heartbeat, or None when unreadable."""
        if not self.heartbeat_file:
            return None
        try:
            state = json.loads(self.heartbeat_file.read_text(encoding="utf-8"))
            raw = state.get("heartbeat_at")
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return now - parsed.timestamp()
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            try:
                return now - self.heartbeat_file.stat().st_mtime
            except OSError:
                return None

    def _check_circuit_breaker(self) -> bool:
        """Return True if restart is allowed (under rate limit)."""
        one_hour_ago = time.time() - 3600
        self.restart_timestamps = [t for t in self.restart_timestamps if t > one_hour_ago]
        return len(self.restart_timestamps) < self.max_restarts_per_hour

    def _create_critical_item(self) -> None:
        """Write a critical backlog item when a service fails repeatedly."""
        CRITICAL_DIR.mkdir(parents=True, exist_ok=True)
        item_path = CRITICAL_DIR / f"service_{self.name}.md"
        now = datetime.now().isoformat()
        content = f"""# Critical Service Failure: {self.name}

**Status**: awaiting_manual_fix
**Created**: {now}
**Consecutive failures**: {self.consecutive_failures}
**Total restarts**: {self.total_restarts}
**Last started**: {self.last_started or 'N/A'}

## Description

Service `{self.name}` has failed {self.consecutive_failures} times consecutively.
The daemon has stopped retrying. Manual investigation is required.

Script: `{self.script}`
{f'Description: {self.description}' if self.description else ''}

## Next Steps

1. Check the service stderr log at `{_service_stderr_log_hint(self.name)}`
2. Fix the root cause
3. Restart the daemon: `python unified_daemon.py restart`
"""
        item_path.write_text(content)
        logger.info(f"Created critical item: {item_path}")

    def _clear_critical_item(self) -> None:
        """Remove stale critical backlog item after a successful restart."""
        item_path = CRITICAL_DIR / f"service_{self.name}.md"
        try:
            item_path.unlink(missing_ok=True)
        except Exception as exc:
            logger.debug("Failed to clear critical item %s: %s", item_path, exc)

    def _notify_critical(self, message: str) -> None:
        """Send a notification with copy-to-clipboard for critical service failure."""
        global _notification_service
        try:
            if _notification_service is None:
                ns_path = str(Path(__file__).resolve().parent)
                if ns_path not in sys.path:
                    sys.path.insert(0, ns_path)
                from notification_service import NotificationService

                _notification_service = NotificationService

            copy_text = (
                f"[DAEMON] Service {self.name} failed {self.consecutive_failures}x consecutively\n"
                f"Script: {self.script}\n"
                f"Total restarts: {self.total_restarts}\n"
                f"Last started: {self.last_started or 'N/A'}\n"
                f"Check logs: {_service_stderr_log_hint(self.name)}"
            )
            svc = _notification_service()
            svc.notify(
                message,
                category="self_heal",
                event="on_detect",
                title="Augur Daemon",
                copy_text=copy_text,
            )
        except Exception as e:
            logger.warning(f"Critical notification failed: {e}")

    def _status_dict(self) -> dict[str, Any]:
        """Return status information for this service."""
        return {
            "state": self.state,
            "pid": self.process.pid if self.process and self.process.poll() is None else None,
            "total_restarts": self.total_restarts,
            "last_started": self.last_started,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# NIGHTLY SCHEDULER
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# PID & STATUS FILE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════


def _write_pid_file() -> None:
    """Write current PID to file."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _remove_pid_file() -> None:
    """Remove PID file on shutdown."""
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception as exc:
        logger.debug("Failed to remove PID file %s: %s", PID_FILE, exc)


def _pid_exists(pid: int) -> bool:
    """Return whether a PID is alive using the platform-safe diagnostics probe."""
    return daemon_diagnostics._default_pid_exists(pid)


def _read_pid() -> int | None:
    """Read PID from file, return None if not found or stale."""
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        return pid if _pid_exists(pid) else None
    except ValueError:
        return None


def _write_status(
    started_at: str,
    managers: dict[str, SubprocessManager],
    ai_sidecar: "AISidecarManager | None" = None,
) -> None:
    """Write daemon status to JSON file."""
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    started = datetime.fromisoformat(started_at)
    uptime = (now - started).total_seconds()

    services = {}
    for name, mgr in managers.items():
        services[name] = mgr._status_dict()

    if ai_sidecar is not None:
        services["ai_monitor_sidecar"] = ai_sidecar._status_dict()

    data = {
        "daemon_pid": os.getpid(),
        "started_at": started_at,
        "uptime_seconds": int(uptime),
        "updated_at": now.isoformat(),
        "services": services,
    }

    STATUS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _job_ledger_sweep() -> None:
    """Best-effort job ledger supervisor sweep + retention."""
    try:
        from job_ledger import retention, supervisor
        from job_ledger.config import load_job_ledger_config

        cfg = load_job_ledger_config()
        supervisor.sweep(config=cfg)
        retention.archive(retention_days=cfg.get("retention_days", 30))
    except Exception as exc:  # noqa: BLE001
        logger.warning("job ledger sweep failed: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN DAEMON LOOP
# ═══════════════════════════════════════════════════════════════════════════════


def _load_sidecar_config() -> dict[str, Any]:
    """Load ai_monitor config from config/system/daemon.yaml."""
    config_path = PROJECT_ROOT / "config" / "system" / "daemon.yaml"
    if not config_path.exists():
        return {"enabled": False}
    try:
        import yaml
        data = yaml.safe_load(config_path.read_text())
        return data.get("ai_monitor", {"enabled": False})
    except Exception as e:
        logger.warning("Failed to load sidecar config: %s", e)
        return {"enabled": False}


def daemon_loop() -> int:
    """Main daemon loop: manage children, write status."""
    global _shutdown

    # Import sidecar manager (optional — skipped if unavailable)
    try:
        from ai_monitor_sidecar import AISidecarManager
    except ImportError:
        AISidecarManager = None

    # Check if already running
    existing_pid = _read_pid()
    if existing_pid:
        logger.error(f"Daemon already running (PID {existing_pid}). Use 'stop' first.")
        return 1

    _write_pid_file()
    started_at = datetime.now().isoformat()

    logger.info(f"Unified daemon starting (PID {os.getpid()})")
    logger.info(f"Managing {len(CHILD_SERVICES)} services: {', '.join(CHILD_SERVICES.keys())}")

    # Create managers
    managers: dict[str, SubprocessManager] = {}
    for name, config in CHILD_SERVICES.items():
        managers[name] = SubprocessManager(name, config)

    # Start persistent services
    for name, mgr in managers.items():
        if mgr.mode == "persistent":
            mgr.start()

    # AI Monitor Sidecar (child #12, managed separately from SubprocessManager)
    ai_sidecar: AISidecarManager | None = None
    if AISidecarManager is not None:
        sidecar_config = _load_sidecar_config()
        if sidecar_config.get("enabled", False):
            ai_sidecar = AISidecarManager(config=sidecar_config)
            ai_sidecar._state_dir = RUNTIME_DIR / "ai_monitor"
            ai_sidecar._fix_lock_file = RUNTIME_DIR / "locks" / "self_heal_fix.lock"
            ai_sidecar._stderr_logs_dir = _STDERR_LOGS_DIR
            ai_sidecar._project_root = PROJECT_ROOT
            ai_sidecar._env = _augmented_env()
            ai_sidecar.start()

    _job_ledger_sweep()

    # Main loop
    while not _shutdown:
        # Check health of all children
        for name, mgr in managers.items():
            if mgr.mode == "persistent":
                mgr.check_health()

        # Check AI sidecar health
        if ai_sidecar is not None:
            ai_sidecar.check_health()

        _job_ledger_sweep()

        # Write status
        try:
            _write_status(started_at, managers, ai_sidecar=ai_sidecar)
        except Exception as e:
            logger.error(f"Failed to write status: {e}")

        # Sleep with shutdown check (30s total, checking every 1s)
        for _ in range(30):
            if _shutdown:
                break
            time.sleep(1)

    # Graceful shutdown
    if ai_sidecar is not None:
        ai_sidecar.stop(timeout=15)

    logger.info("Shutting down all child services...")
    for name, mgr in managers.items():
        mgr.stop(timeout=15)

    _remove_pid_file()

    # Write final status
    try:
        _write_status(started_at, managers, ai_sidecar=ai_sidecar)
    except Exception as exc:
        logger.debug("Failed to write final daemon status: %s", exc)

    logger.info("Unified daemon stopped")
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# CLI COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════


def cmd_stop() -> int:
    """Stop a running daemon via PID file."""
    pid = _read_pid()
    if not pid:
        _out("Daemon is not running")
        return 1

    _out(f"Stopping daemon (PID {pid})...")
    if sys.platform == "win32":
        try:
            result = _run_command(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            result = CompletedProcess(["taskkill"], 1, stdout="", stderr="taskkill not found")
        if result.returncode != 0 and _pid_exists(pid):
            detail = (result.stderr or result.stdout or f"taskkill exit code {result.returncode}").strip()
            _out(f"Error stopping daemon: {detail}")
            return 1
        for _ in range(30):
            if _pid_exists(pid):
                time.sleep(1)
            else:
                _out("Daemon stopped")
                return 0
        _out("Daemon did not stop in time")
        return 1

    try:
        os.kill(pid, signal.SIGTERM)
        # Wait for shutdown
        for _ in range(30):
            if _pid_exists(pid):
                time.sleep(1)
            else:
                _out("Daemon stopped")
                return 0
        _out("Daemon did not stop in time, sending SIGKILL...")
        os.kill(pid, signal.SIGKILL)
        return 0
    except ProcessLookupError:
        _out("Daemon already stopped")
        _remove_pid_file()
        return 0
    except Exception as e:
        _out(f"Error stopping daemon: {e}")
        return 1


def cmd_status() -> int:
    """Show daemon status from status file."""
    diagnostic = daemon_diagnostics.read_daemon_status_file(
        STATUS_FILE,
        max_age_seconds=90,
    )
    status = str(diagnostic.get("status", "unknown"))
    status_label = status.upper()
    status_path = diagnostic.get("path") or str(STATUS_FILE)

    if status == "missing":
        _out(f"Status file: MISSING ({status_path})")
        _out("Daemon: STOPPED")
        return 1

    if status == "malformed":
        _out(f"Status file: MALFORMED ({status_path})")
        issue = diagnostic.get("detail") or diagnostic.get("issue")
        if not issue:
            issues = diagnostic.get("issues")
            if isinstance(issues, list) and issues:
                issue = "; ".join(str(item) for item in issues)
        if issue:
            _out(f"Issue: {issue}")
        _out("Daemon: STOPPED")
        return 1

    data: dict[str, Any] = {}
    try:
        parsed = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        if isinstance(parsed, dict):
            data = parsed
    except Exception as exc:
        logger.debug("Failed to reread daemon status file %s: %s", STATUS_FILE, exc)

    _out(f"Status file: {status_label} ({status_path})")
    age_seconds = diagnostic.get("age_seconds")
    if isinstance(age_seconds, (int, float)):
        _out(f"Status age: {int(age_seconds)}s")

    daemon_pid = diagnostic.get("daemon_pid")
    running = bool(diagnostic.get("pid_alive") and diagnostic.get("fresh"))
    pid_str = f" (PID {daemon_pid})" if isinstance(daemon_pid, int) else ""
    _out(f"Daemon: {'RUNNING' if running else 'STOPPED'}{pid_str}")

    started_at = data.get("started_at")
    if started_at:
        _out(f"Started: {started_at}")
    uptime_seconds = data.get("uptime_seconds")
    if uptime_seconds is not None:
        _out(f"Uptime: {uptime_seconds}s")

    issues = diagnostic.get("issues")
    if isinstance(issues, list):
        for issue in issues:
            _out(f"Issue: {issue}")

    services = diagnostic.get("services")
    if isinstance(services, dict) and services:
        _out()
        for name, info in services.items():
            if not isinstance(info, dict):
                _out(f"  {name}: UNKNOWN")
                continue
            state = str(info.get("state", "unknown")).upper()
            service_pid = info.get("pid")
            service_pid_str = f" (PID {service_pid})" if service_pid else ""
            restarts = info.get("total_restarts", 0)
            restart_str = f" [{restarts} restarts]" if isinstance(restarts, int) and restarts > 0 else ""
            _out(f"  {name}: {state}{service_pid_str}{restart_str}")

    return 0 if running else 1


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Unified Augur Daemon")
    parser.add_argument(
        "command",
        nargs="?",
        default="start",
        choices=["start", "stop", "status", "restart"],
        help="Command to execute (default: start)",
    )
    args = parser.parse_args()

    if args.command == "start":
        return daemon_loop()
    elif args.command == "stop":
        return cmd_stop()
    elif args.command == "status":
        return cmd_status()
    elif args.command == "restart":
        cmd_stop()
        time.sleep(2)
        return daemon_loop()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
