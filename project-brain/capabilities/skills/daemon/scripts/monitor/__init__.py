"""Dashboard monitor package.

Re-exports all public symbols so that ``from monitor import X`` and
``import dashboard_monitor; dashboard_monitor.X`` continue to work after
the split into submodules.
"""

from __future__ import annotations

# --- _base (shared constants, helpers, logger) ---
from ._base import (
    CHECK_INTERVAL_SECONDS,
    DASHBOARD_PORT,
    DASHBOARD_STDERR_LOG,
    DEFAULT_DASHBOARD_STDERR_LOG,
    FATAL_BUILD_PATTERNS,
    FATAL_NOTIFY_COOLDOWN_SECONDS,
    FATAL_STDERR_MAX_AGE_SECONDS,
    FATAL_STDERR_TAIL_LINES,
    HTTP_FAILURE_THRESHOLD,
    LOCK_CONFLICT_THRESHOLD,
    LOCK_FILE_MAX_AGE_MINUTES,
    MAX_DOWN_SECONDS_BEFORE_FORCE_RECOVERY,
    MAX_RESTART_ATTEMPTS,
    PROJECT_ROOT,
    RECOVERY_STAGES,
    RUNTIME_INCIDENT_WINDOW_SECONDS,
    RUNTIME_TIMEOUT_THRESHOLD,
    _augmented_env,
    _out,
    _popen_command,
    _resolve_command,
    _run_command,
    dashboard_lifecycle,
    get_daemon_mode,
    get_dashboard_dir,
    get_pids_on_port,
    get_repo_context,
    get_worktree_marker,
    is_pid_alive,
    is_production_mode,
    logger,
    notify,
)

# --- locks ---
from .locks import (
    create_lock,
    get_build_lock_info,
    get_locks_dir,
    is_build_lock_held,
    is_build_process_running,
    is_rebuild_in_progress,
    remove_lock,
)

# --- health ---
from .health import (
    attempt_auto_fix,
    check_dashboard_http_health,
    detect_fatal_build_errors,
    detect_runtime_incident,
    get_dashboard_status,
    is_dashboard_running,
    write_status,
)

# --- recovery ---
from .recovery import (
    RECOVERY_FUNCTIONS,
    run_npm_command,
    run_recovery,
    stage_clear_cache,
    stage_full_rebuild,
    stage_reinstall,
    stage_restart,
)

# --- process (monitoring logic) ---
from .process import (
    _recover_unhealthy_server,
    check_and_recover,
    monitor_loop,
)

# Expose mutable module-level state that tests monkeypatch.
# These are kept as module attributes on *this* package so that
# ``import dashboard_monitor; dashboard_monitor._first_down_at`` still works.
from . import process as _process_mod
from . import health as _health_mod

# Proxy mutable state from submodules so monkeypatching on the package works.
_first_down_at = _process_mod._first_down_at
_was_stabilizing = _process_mod._was_stabilizing
_consecutive_http_failures = _process_mod._consecutive_http_failures
_last_runtime_incident_signature = _process_mod._last_runtime_incident_signature
_last_fatal_notify_at = _process_mod._last_fatal_notify_at
_runtime_incident_log_path = _health_mod._runtime_incident_log_path
_runtime_incident_offset = _health_mod._runtime_incident_offset

__all__ = [
    # Constants
    "CHECK_INTERVAL_SECONDS",
    "DASHBOARD_PORT",
    "DASHBOARD_STDERR_LOG",
    "DEFAULT_DASHBOARD_STDERR_LOG",
    "FATAL_BUILD_PATTERNS",
    "FATAL_NOTIFY_COOLDOWN_SECONDS",
    "FATAL_STDERR_MAX_AGE_SECONDS",
    "FATAL_STDERR_TAIL_LINES",
    "HTTP_FAILURE_THRESHOLD",
    "LOCK_CONFLICT_THRESHOLD",
    "LOCK_FILE_MAX_AGE_MINUTES",
    "MAX_DOWN_SECONDS_BEFORE_FORCE_RECOVERY",
    "MAX_RESTART_ATTEMPTS",
    "PROJECT_ROOT",
    "RECOVERY_FUNCTIONS",
    "RECOVERY_STAGES",
    "RUNTIME_INCIDENT_WINDOW_SECONDS",
    "RUNTIME_TIMEOUT_THRESHOLD",
    # Helpers
    "get_daemon_mode",
    "get_dashboard_dir",
    "get_repo_context",
    "get_worktree_marker",
    "is_production_mode",
    "logger",
    "notify",
    # Locks
    "create_lock",
    "get_build_lock_info",
    "get_locks_dir",
    "is_build_lock_held",
    "is_build_process_running",
    "is_rebuild_in_progress",
    "remove_lock",
    # Health
    "attempt_auto_fix",
    "check_dashboard_http_health",
    "detect_fatal_build_errors",
    "detect_runtime_incident",
    "get_dashboard_status",
    "is_dashboard_running",
    "write_status",
    # Recovery
    "run_npm_command",
    "run_recovery",
    "stage_clear_cache",
    "stage_full_rebuild",
    "stage_reinstall",
    "stage_restart",
    # Process / monitoring
    "check_and_recover",
    "monitor_loop",
]
