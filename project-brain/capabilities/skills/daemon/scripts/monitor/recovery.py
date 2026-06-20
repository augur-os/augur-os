"""Recovery stages for the dashboard monitor.

Each stage is progressively more aggressive:
1. restart -- kill zombies, start via npm run dev
2. clear_cache -- remove .next cache, then restart
3. reinstall -- remove node_modules, npm install, then restart
4. full_rebuild -- npm run build, start production server
"""

from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import os
import shutil
import signal
import sys
import time
from pathlib import Path
from subprocess import TimeoutExpired

from ._base import (
    RECOVERY_STAGES,
    MAX_RESTART_ATTEMPTS,
    DASHBOARD_PORT,
    DASHBOARD_STDERR_LOG,
    _augmented_env,
    _popen_command,
    _run_command,
    get_dashboard_dir,
    get_pids_on_port,
    logger,
)
from .health import check_dashboard_http_health

# Stability gate: how long after a successful port-bind to wait, then re-verify
# the dashboard is still bound + serving HTTP 200. Without this, stage_restart
# returns True the moment any process touches port 3000 (often a half-started
# process that exits seconds later), turning single transient failures into
# crash loops.
STAGE_RESTART_BIND_WAIT_SECONDS = 60   # wait up to this long for port to bind
STAGE_RESTART_STABILITY_SECONDS = 60   # additional warmup before re-verifying
STAGE_RESTART_HTTP_RETRIES = 5         # HTTP probes after stability window
STAGE_RESTART_HTTP_RETRY_DELAY = 3     # seconds between HTTP probes


def _open_dashboard_stderr_writer():
    """Open DASHBOARD_STDERR_LOG in append-binary mode for subprocess capture.

    Replaces the previous `stderr=DEVNULL` which discarded all dashboard output
    and made FATAL_BUILD_PATTERNS detection impossible. The returned file is
    inherited by the spawned npm subprocess; the parent fd is closed after
    Popen takes over (subprocess dups the fd into the child).
    """
    DASHBOARD_STDERR_LOG.parent.mkdir(parents=True, exist_ok=True)
    return open(DASHBOARD_STDERR_LOG, "ab", buffering=0)
from .locks import create_lock, is_rebuild_in_progress, remove_lock

from subprocess import run  # nosec B404

try:
    from src.config.paths import get_launch_agents_dir, get_project_name
except ImportError:

    def get_launch_agents_dir() -> Path:
        return Path.home() / "Library" / "LaunchAgents"

    def get_project_name() -> str:
        return "Augur"


LAUNCHD_DASHBOARD_LABEL = f"com.{get_project_name().lower()}.dashboard"
LAUNCHD_DASHBOARD_PLIST = get_launch_agents_dir() / f"{LAUNCHD_DASHBOARD_LABEL}.plist"


def is_dashboard_running() -> bool:
    """Check if the dashboard server is running on port 3000."""
    pids = get_pids_on_port(DASHBOARD_PORT)
    return len(pids) > 0


def run_npm_command(
    cmd: list[str], cwd: Path, timeout: int = 120
) -> tuple[bool, str]:
    """Run an npm command and return success status and output."""
    try:
        result = _run_command(
            ["npm"] + cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except TimeoutExpired:
        return False, "Command timed out"
    except FileNotFoundError:
        augmented = _augmented_env().get("PATH", "")
        return False, (
            f"npm not found in PATH. "
            f"Searched: {augmented[:200]}. "
            f"Install Node.js or add its bin directory to _EXTRA_PATHS."
        )
    except Exception as e:
        return False, str(e)


def _kill_zombie_dashboard_processes() -> int:
    """Kill any next-server or npm-run-dev processes not bound to DASHBOARD_PORT.

    These zombies block recovery by consuming resources without serving traffic.
    Returns the number of processes killed.
    """
    killed = 0
    serving_pids = get_pids_on_port(DASHBOARD_PORT)

    for pattern in ["next-server", "next dev", "npm run dev"]:
        try:
            result = run(  # nosec B603 B607
                ["pgrep", "-f", pattern],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                for pid_str in result.stdout.strip().splitlines():
                    pid_str = pid_str.strip()
                    if pid_str and pid_str not in serving_pids:
                        try:
                            os.kill(int(pid_str), signal.SIGTERM)
                            killed += 1
                            logger.info(
                                f"Killed zombie dashboard process {pid_str} "
                                f"(matched '{pattern}')"
                            )
                        except (ProcessLookupError, PermissionError):
                            pass
        except Exception:
            pass

    if killed:
        time.sleep(2)  # Let processes clean up
    return killed


def _start_launchd_dashboard_service() -> bool:
    """Start the dashboard through its LaunchAgent when one is installed."""
    if sys.platform != "darwin" or not LAUNCHD_DASHBOARD_PLIST.exists():
        return False

    loaded = _run_command(
        ["launchctl", "list", LAUNCHD_DASHBOARD_LABEL],
        capture_output=True,
        text=True,
        check=False,
    )
    if loaded.returncode == 0:
        service = f"gui/{os.getuid()}/{LAUNCHD_DASHBOARD_LABEL}"
        result = _run_command(
            ["launchctl", "kickstart", "-k", service],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            logger.info(f"Restarted launchd dashboard service '{LAUNCHD_DASHBOARD_LABEL}'")
            return True
        logger.warning(
            "Failed to kickstart launchd dashboard service "
            f"'{LAUNCHD_DASHBOARD_LABEL}': {result.stderr.strip()}"
        )

    result = _run_command(
        ["launchctl", "load", str(LAUNCHD_DASHBOARD_PLIST)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        logger.info(f"Loaded launchd dashboard service '{LAUNCHD_DASHBOARD_LABEL}'")
        return True

    logger.warning(
        "Failed to load launchd dashboard service "
        f"'{LAUNCHD_DASHBOARD_LABEL}': {result.stderr.strip()}"
    )
    return False


def _spawn_dashboard_process(command: list[str], dashboard_dir: Path) -> None:
    stderr_fp = _open_dashboard_stderr_writer()
    try:
        popen_kwargs = {
            "cwd": str(dashboard_dir),
            "stdout": stderr_fp,
            "stderr": stderr_fp,
            "start_new_session": True,
        }
        if sys.platform == "win32":
            popen_kwargs["shell"] = True

        _popen_command(
            command,
            **popen_kwargs,
        )
    finally:
        stderr_fp.close()


def _start_dashboard_dev(dashboard_dir: Path) -> None:
    if _start_launchd_dashboard_service():
        return
    _spawn_dashboard_process(["npm", "run", "dev"], dashboard_dir)


def _start_dashboard_after_rebuild(dashboard_dir: Path) -> None:
    if _start_launchd_dashboard_service():
        return
    _spawn_dashboard_process(["npm", "run", "start"], dashboard_dir)


def _clear_next_dir(next_dir: Path) -> None:
    if next_dir.is_symlink():
        target = next_dir.resolve(strict=False)
        next_dir.unlink()
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        return

    if next_dir.exists():
        shutil.rmtree(next_dir)


def stage_restart() -> bool:
    """Stage 1: Kill zombies, then restart via npm run dev."""
    logger.info("Recovery Stage 1: Attempting restart...")
    dashboard_dir = get_dashboard_dir()

    zombies = _kill_zombie_dashboard_processes()
    if zombies:
        logger.info(f"Cleaned up {zombies} zombie process(es) before restart")

    try:
        _start_dashboard_dev(dashboard_dir)

        # Step 1: wait for port binding (process became reachable)
        bound = False
        for _ in range(STAGE_RESTART_BIND_WAIT_SECONDS):
            time.sleep(1)
            if is_dashboard_running():
                bound = True
                break
        if not bound:
            logger.warning(
                f"Restart: port {DASHBOARD_PORT} never bound within "
                f"{STAGE_RESTART_BIND_WAIT_SECONDS}s — declaring failure."
            )
            return False

        # Step 2: stability window — wait, then verify still bound.
        # Catches "port bound for a few seconds then process exits" scenarios.
        time.sleep(STAGE_RESTART_STABILITY_SECONDS)
        if not is_dashboard_running():
            logger.warning(
                f"Restart: dashboard exited during {STAGE_RESTART_STABILITY_SECONDS}s "
                "stability window — declaring failure so recovery can escalate."
            )
            return False

        # Step 3: HTTP probe — verify the server actually serves requests.
        # Catches "process alive but server crashed internally" scenarios.
        for attempt in range(STAGE_RESTART_HTTP_RETRIES):
            status_code = check_dashboard_http_health(timeout=5)
            if status_code == 200:
                logger.info(
                    f"Dashboard restarted successfully (port bound, stable, "
                    f"HTTP 200 after {attempt + 1} probe(s))."
                )
                return True
            if attempt < STAGE_RESTART_HTTP_RETRIES - 1:
                time.sleep(STAGE_RESTART_HTTP_RETRY_DELAY)

        logger.warning(
            f"Restart: dashboard bound + stable but HTTP probe failed "
            f"(last status: {status_code}). Declaring failure."
        )
        return False
    except Exception as e:
        logger.error(f"Restart failed: {e}")
        return False


def stage_clear_cache() -> bool:
    """Stage 2: Clear .next cache and restart."""
    if is_rebuild_in_progress():
        logger.info(
            "Skipping cache clear while another rebuild/restart is active"
        )
        return False

    logger.info("Recovery Stage 2: Clearing cache...")
    dashboard_dir = get_dashboard_dir()

    next_dir = dashboard_dir / ".next"
    try:
        _clear_next_dir(next_dir)
        logger.info("Cleared .next cache")
    except Exception as e:
        logger.warning(f"Failed to clear cache: {e}")

    return stage_restart()


def stage_reinstall() -> bool:
    """Stage 3: Reinstall node_modules and restart."""
    logger.info("Recovery Stage 3: Reinstalling dependencies...")
    dashboard_dir = get_dashboard_dir()

    node_modules = dashboard_dir / "node_modules"
    if node_modules.exists():
        try:
            shutil.rmtree(node_modules)
            logger.info("Removed node_modules")
        except Exception as e:
            logger.warning(f"Failed to remove node_modules: {e}")

    success, output = run_npm_command(["install"], dashboard_dir, timeout=300)
    if not success:
        logger.error(f"npm install failed: {output}")
        return False

    return stage_restart()


def stage_full_rebuild() -> bool:
    """Stage 4: Full rebuild with npm run build."""
    logger.info("Recovery Stage 4: Full rebuild...")
    dashboard_dir = get_dashboard_dir()

    success, output = run_npm_command(["run", "build"], dashboard_dir, timeout=300)
    if not success:
        logger.error(f"npm run build failed: {output}")
        return False

    try:
        _start_dashboard_after_rebuild(dashboard_dir)

        for _ in range(30):
            time.sleep(1)
            if is_dashboard_running():
                logger.info("Dashboard rebuilt and started successfully")
                return True

        return False
    except Exception as e:
        logger.error(f"Full rebuild failed: {e}")
        return False


RECOVERY_FUNCTIONS = {
    "restart": stage_restart,
    "clear_cache": stage_clear_cache,
    "reinstall": stage_reinstall,
    "full_rebuild": stage_full_rebuild,
}


def run_recovery(max_attempts: int | None = None) -> tuple[bool, str, float]:
    """Run recovery stages until dashboard is up or all stages fail.

    Args:
        max_attempts: Maximum number of recovery attempts (defaults to MAX_RESTART_ATTEMPTS)

    Returns:
        (success, last_stage, duration_seconds)
    """
    attempts_limit = (
        max_attempts if max_attempts is not None else MAX_RESTART_ATTEMPTS
    )
    start_time = time.time()
    create_lock("recovery", "auto-recovery")

    try:
        attempts = 0
        for stage in RECOVERY_STAGES:
            if attempts >= attempts_limit:
                logger.error(f"Max recovery attempts ({attempts_limit}) reached")
                break

            recovery_func = RECOVERY_FUNCTIONS.get(stage)
            if not recovery_func:
                continue

            attempts += 1
            if recovery_func():
                duration = time.time() - start_time
                return True, stage, duration

        duration = time.time() - start_time
        return False, RECOVERY_STAGES[-1], duration

    finally:
        remove_lock("recovery")
