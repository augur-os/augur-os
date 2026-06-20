"""Shared constants, logger, and utility functions for dashboard monitor submodules."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
import importlib.util
from pathlib import Path
from subprocess import DEVNULL, CompletedProcess, Popen, run  # nosec B404
from typing import Any

_BOOTSTRAP_PATH = Path(__file__).resolve().parents[1] / "bootstrap_paths.py"
_BOOTSTRAP_SPEC = importlib.util.spec_from_file_location(
    "_augur_daemon_bootstrap_paths",
    _BOOTSTRAP_PATH,
)
if _BOOTSTRAP_SPEC is None or _BOOTSTRAP_SPEC.loader is None:
    raise RuntimeError(f"Unable to load daemon bootstrap from {_BOOTSTRAP_PATH}")
_BOOTSTRAP = importlib.util.module_from_spec(_BOOTSTRAP_SPEC)
sys.modules[_BOOTSTRAP_SPEC.name] = _BOOTSTRAP
_BOOTSTRAP_SPEC.loader.exec_module(_BOOTSTRAP)
ensure_project_paths = _BOOTSTRAP.ensure_project_paths
project_python_env = _BOOTSTRAP.project_python_env

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
            handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger


from src.config.paths import get_project_port, get_runtime_dir

# Local imports — these live alongside the monitor package in daemon/scripts/
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


try:
    from cleanup_processes import get_pids_on_port, is_pid_alive
except ImportError:

    def get_pids_on_port(port: int = 3000):
        return set()

    def is_pid_alive(pid: str):
        return False


logger = get_entity_logger("dashboard_monitor")

try:
    import dashboard_lifecycle
except ImportError:
    dashboard_lifecycle = None  # Fallback: operate without lifecycle gate

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------
DASHBOARD_PORT = get_project_port()
CHECK_INTERVAL_SECONDS = 30
LOCK_FILE_MAX_AGE_MINUTES = 5
RECOVERY_STAGES = ["restart", "clear_cache", "full_rebuild"]
MAX_RESTART_ATTEMPTS = len(RECOVERY_STAGES)
MAX_DOWN_SECONDS_BEFORE_FORCE_RECOVERY = 120

DASHBOARD_STDERR_LOG = Path.home() / "Library" / "Logs" / "Augur" / "dashboard.stderr.log"
DEFAULT_DASHBOARD_STDERR_LOG = DASHBOARD_STDERR_LOG
FATAL_NOTIFY_COOLDOWN_SECONDS = 300
HTTP_FAILURE_THRESHOLD = 3
RUNTIME_INCIDENT_WINDOW_SECONDS = 180
RUNTIME_TIMEOUT_THRESHOLD = 3
LOCK_CONFLICT_THRESHOLD = 2
FATAL_STDERR_TAIL_LINES = 80
FATAL_STDERR_MAX_AGE_SECONDS = 300

# Fatal error detection — patterns in dashboard.stderr.log that a plain restart
# cannot fix, paired with auto-fix commands that CAN fix them.
# Each tuple: (regex, description, auto_fix_commands | None, manual_fix_hint)
FATAL_BUILD_PATTERNS: list[tuple[re.Pattern, str, list[list[str]] | None, str]] = [
    (
        re.compile(r"<{7}|>{7}"),
        "Git merge conflict markers in generated file",
        [["npm", "run", "mount-plugins"]],
        "If conflict is in hand-written source: resolve manually",
    ),
    (
        re.compile(r"SyntaxError:"),
        "JavaScript/TypeScript syntax error",
        None,
        "Fix the syntax error in the file shown in stderr",
    ),
    (
        re.compile(r"Module not found: Can't resolve"),
        "Missing module import",
        [["npm", "install"]],
        "If import path is wrong, fix it manually",
    ),
    (
        re.compile(
            r"TypeError: Cannot read properties of (?:undefined|null)"
            r".*(?:navigation|assembled-hubs)"
        ),
        "Corrupted generated config (assembled-hubs/navigation)",
        [["npm", "run", "mount-plugins"]],
        "Regenerate plugin mounts",
    ),
]

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def get_repo_context() -> dict:
    """Detect if running in a worktree."""
    creationflags = 0x08000000 if sys.platform == "win32" else 0
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, creationflags=creationflags
    )
    main_repo = (
        subprocess.run(
            ["git", "worktree", "list", "--porcelain"], capture_output=True, text=True, creationflags=creationflags
        )
        .stdout.split("worktree ")[1]
        .split("\n")[0]
    )

    current = result.stdout.strip()
    is_worktree = current != main_repo
    return {"is_worktree": is_worktree, "path": current, "main": main_repo}


def get_worktree_marker() -> dict | None:
    """Read .augur-worktree.yaml marker if present."""
    marker_path = Path.cwd() / ".augur-worktree.yaml"
    if marker_path.exists():
        import yaml

        return yaml.safe_load(marker_path.read_text())
    return None


def get_dashboard_dir() -> Path:
    """Get the dashboard directory."""
    return PROJECT_ROOT / "apps" / "dashboard"


_EXTRA_PATHS = [
    "/usr/bin",
    "/usr/sbin",
    "/opt/homebrew/bin",
    "/usr/local/bin",
    str(Path.home() / ".nvm" / "current" / "bin"),
    str(Path.home() / ".volta" / "bin"),
    "/usr/local/nodejs/bin",
]


def _augmented_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """Return environment with extra tool directories prepended to PATH.

    Daemon child processes (macOS LaunchAgent) inherit a minimal PATH that
    excludes Homebrew, nvm, Volta, etc.  By prepending these directories we
    ensure that *both* the resolved command and any child processes it spawns
    (e.g. npm invoking node) can locate their dependencies.
    """
    base = project_python_env(PROJECT_ROOT)
    if env is not None:
        base.update(env)
    current_path = base.get("PATH", "")
    extra = os.pathsep.join(p for p in _EXTRA_PATHS if p not in current_path)
    if extra:
        base["PATH"] = extra + os.pathsep + current_path if current_path else extra
    return base


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve command executable to an absolute path when available."""
    if not command:
        return command

    exe = command[0]

    resolved = shutil.which(exe)
    if resolved:
        return [resolved, *command[1:]]

    augmented_path = _augmented_env().get("PATH", "")
    resolved = shutil.which(exe, path=augmented_path)
    if resolved:
        logger.debug(f"Resolved '{exe}' via augmented PATH: {resolved}")
        return [resolved, *command[1:]]

    logger.warning(
        f"Could not resolve '{exe}' in PATH or augmented paths: {_EXTRA_PATHS}"
    )
    return command


_NO_WINDOW_CREATIONFLAGS = (
    getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0)
    if sys.platform == "win32"
    else 0
)


def _run_command(command: list[str], **kwargs: Any) -> CompletedProcess[Any]:
    """Run subprocess command with resolved executable path and augmented env."""
    if "env" not in kwargs:
        kwargs["env"] = _augmented_env()
    if _NO_WINDOW_CREATIONFLAGS:
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | _NO_WINDOW_CREATIONFLAGS
    return run(_resolve_command(command), **kwargs)  # nosec B603


def _popen_command(command: list[str], **kwargs: Any) -> Popen[Any]:
    """Start background process with resolved executable path and augmented env."""
    if "env" not in kwargs:
        kwargs["env"] = _augmented_env()
    if _NO_WINDOW_CREATIONFLAGS:
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | _NO_WINDOW_CREATIONFLAGS
    return Popen(_resolve_command(command), **kwargs)  # nosec B603
