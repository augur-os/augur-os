#!/usr/bin/env python3
"""In-process daemon supervisor (ADR-787 Part B).

Runs the background daemon loops as crash-restarting THREADS inside a single
process, instead of one OS subprocess per daemon. Collapses ~18 daemon
processes (a bootstrap-reexec parent + worker per daemon) into ~1.

Each daemon already exposes a continuous loop callable (run_loop / monitor_loop
/ monitor_logs / _run_loop / daemon_loop). The supervisor imports the daemon
modules once and runs each callable in a daemon thread wrapped with backoff +
circuit-breaker restart, mirroring unified_daemon's SubprocessManager semantics
at the thread level. Python exceptions in one loop are caught and that loop is
restarted; they no longer take down the others.

One daemon — adaptive_loop_executor — keeps running as an isolated child
subprocess because its loop is intertwined with argparse modes and per-checkout
env rebinding that is unsafe to share a process with. The supervisor manages it
alongside the threads.

Usage:
    python daemon_supervisor.py            # start (default)
    python daemon_supervisor.py status     # show thread/subprocess status
    python daemon_supervisor.py stop       # stop a running supervisor via PID file
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os

os.environ.setdefault("AUGUR_DAEMON", "1")

import signal
import sys
import threading
from datetime import datetime
from pathlib import Path
from subprocess import DEVNULL, Popen  # nosec B404
from typing import Any, Callable

try:
    from bootstrap_paths import ensure_project_paths, project_python_env
except ImportError:
    _BOOT = Path(__file__).resolve().parent
    if str(_BOOT) not in sys.path:
        sys.path.insert(0, str(_BOOT))
    from bootstrap_paths import ensure_project_paths, project_python_env

PROJECT_ROOT = ensure_project_paths(__file__)

from src.config.paths import (  # noqa: E402
    get_logs_dir,
    get_python_executable,
    get_runtime_dir,
)


def _bind_headless_streams() -> None:
    """Point stdout/stderr at log files when launched under pythonw.exe.

    The com.augur.daemon scheduled task runs this under pythonw (no console), so
    sys.stdout/sys.stderr are None. This MUST run before any logger is created —
    logging.StreamHandler captures the stream at construction, so a None stream
    would make every log call raise.
    """
    if sys.platform != "win32":
        return
    if sys.stdout is not None and sys.stderr is not None:
        return
    logs_dir = get_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
    if sys.stdout is None:
        sys.stdout = open(logs_dir / "daemon_supervisor.stdout.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = open(logs_dir / "daemon_supervisor.stderr.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115


_bind_headless_streams()

from src.logging import get_entity_logger  # noqa: E402

logger = get_entity_logger("daemon_supervisor")

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

RUNTIME_DIR = get_runtime_dir()
PID_FILE = RUNTIME_DIR / "daemon_supervisor.pid"
STATUS_FILE = RUNTIME_DIR / "stats" / "daemon_supervisor_status.json"

MAX_CONSECUTIVE_FAILURES = 5
BASE_RESTART_DELAY = 5.0
MAX_RESTART_DELAY = 300.0

_shutdown = threading.Event()


def _load_daemon(name: str) -> Any:
    """Import a daemon module by file path (they live next to this script)."""
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load daemon module {name}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Daemon profiles (ADR-787). The full fleet is 9 polling loops; most are either
# dev-time or act on shared state. We run a lean, role-scoped set:
#
#   - Singleton, shared-state daemons (cron, notifications, job queue, self-heal,
#     overnight loops) act globally and MUST run on exactly one owner: the main
#     production instance. Running them on a worktree too would double-fire.
#   - Per-instance dev daemons (skill-change watcher) only make sense while you
#     are editing skills, i.e. in a worktree.
#
# PROD_DAEMONS / DEV_DAEMONS are the defaults per role; override with an explicit
# allowlist via AUGUR_SUPERVISOR_DAEMONS="name1,name2" (empty string = none).
PROD_DAEMONS = {"notification_service", "log_monitor", "adaptive_loop_executor", "rag_watcher"}
DEV_DAEMONS = {"plugin_watcher"}

# Singleton daemons act on SHARED state (cron schedules, notifications, job queue,
# self-heal/overnight loops, insight generation) and must run on exactly ONE owner
# — the main checkout. They are stripped from any non-main supervisor even if an
# AUGUR_SUPERVISOR_DAEMONS override lists them, so a worktree that inherits an
# exported override can never double-fire them.
SINGLETON_DAEMONS = {
    "schedule_executor",
    "notification_service",
    "continuous_executor",
    "adaptive_loop_executor",
    "insight_scanner",
    "log_monitor",
    # rag_watcher syncs the SHARED RAG index — exactly one owner (main checkout).
    # Dropped in the ADR-787 unified_daemon->supervisor migration; restored by
    # spec 2026-06-12-retrieval-freshness (the index silently died on 2026-06-10).
    "rag_watcher",
}
# Every daemon the supervisor knows how to run — used to report what is OFF.
ALL_DAEMONS = SINGLETON_DAEMONS | DEV_DAEMONS | {
    "dashboard_monitor",
    "mcp_health_monitor",
}


def _is_main_checkout() -> bool:
    """True for the main checkout (.git is a directory); worktrees use a gitdir file."""
    return (PROJECT_ROOT / ".git").is_dir()


def _active_daemons() -> set[str]:
    """Resolve which daemons this supervisor should run (role default or override).

    On a non-main checkout, shared-state singletons are always stripped — even from
    an explicit override — so a worktree can never run a second copy of a daemon
    that must have exactly one owner.
    """
    override = os.environ.get("AUGUR_SUPERVISOR_DAEMONS")
    is_main = _is_main_checkout()
    if override is not None:
        active = {name.strip() for name in override.split(",") if name.strip()}
    else:
        active = set(PROD_DAEMONS) if is_main else set(DEV_DAEMONS)
    if not is_main:
        dropped = active & SINGLETON_DAEMONS
        if dropped:
            logger.warning(
                "Worktree supervisor: refusing to run singleton daemons %s "
                "(they belong to the main instance only).",
                sorted(dropped),
            )
        active -= SINGLETON_DAEMONS
    return active


def _build_registry(active: set[str]) -> dict[str, Callable[[], None]]:
    """Map each ACTIVE in-process daemon to a zero-arg loop callable.

    Built lazily so an import failure in one daemon does not abort the rest.
    """
    registry: dict[str, Callable[[], None]] = {}

    def add(name: str, make: Callable[[Any], Callable[[], None]]) -> None:
        if name not in active:
            return
        try:
            mod = _load_daemon(name)
            registry[name] = make(mod)
        except Exception as exc:  # noqa: BLE001 - one bad daemon must not sink the rest
            logger.error("Daemon %s unavailable for in-process run: %s", name, exc)

    add("plugin_watcher", lambda m: m.run_loop)
    add("rag_watcher", lambda m: m.run_loop)
    add("schedule_executor", lambda m: m.run_loop)
    add("dashboard_monitor", lambda m: m.monitor_loop)
    add("mcp_health_monitor", lambda m: m.monitor_loop)
    add("log_monitor", lambda m: m.monitor_logs)
    add("notification_service", lambda m: m._run_loop)
    add("insight_scanner", lambda m: (lambda: m.run_loop(m.load_config())))
    add("continuous_executor", lambda m: m.run_loop)
    return registry


class ThreadService:
    """Runs one daemon loop in a thread, restarting it on crash with backoff."""

    def __init__(self, name: str, loop: Callable[[], None]) -> None:
        self.name = name
        self.loop = loop
        self.thread: threading.Thread | None = None
        self.consecutive_failures = 0
        self.total_restarts = 0
        self.last_started: str | None = None
        self.state = "stopped"  # running | restarting | critical

    def _run(self) -> None:
        while not _shutdown.is_set():
            self.last_started = datetime.now().isoformat()
            self.state = "running"
            try:
                self.loop()  # daemon loops normally never return
                # A clean return is unexpected for a continuous loop; treat as a
                # crash for restart accounting so it does not silently stop.
                raise RuntimeError("loop returned unexpectedly")
            except Exception as exc:  # noqa: BLE001 - isolate per-daemon failures
                if _shutdown.is_set():
                    return
                self.consecutive_failures += 1
                self.total_restarts += 1
                logger.error(
                    "[%s] loop crashed (failure %d/%d): %s",
                    self.name, self.consecutive_failures, MAX_CONSECUTIVE_FAILURES, exc,
                    exc_info=True,
                )
                if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    self.state = "critical"
                    logger.error("[%s] giving up after %d failures", self.name, self.consecutive_failures)
                    return
                delay = min(BASE_RESTART_DELAY * (2 ** (self.consecutive_failures - 1)), MAX_RESTART_DELAY)
                self.state = "restarting"
                _shutdown.wait(delay)

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name=f"daemon:{self.name}", daemon=True)
        self.thread.start()

    def status(self) -> dict[str, Any]:
        alive = bool(self.thread and self.thread.is_alive())
        return {
            "kind": "thread",
            "state": self.state if alive or self.state == "critical" else "stopped",
            "alive": alive,
            "total_restarts": self.total_restarts,
            "last_started": self.last_started,
        }


class SubprocessService:
    """Manages adaptive_loop_executor as an isolated child (loop too tangled to thread)."""

    def __init__(self, name: str, script: Path, args: list[str]) -> None:
        self.name = name
        self.script = script
        self.args = args
        self.process: Popen[Any] | None = None
        self.total_restarts = 0
        self.last_started: str | None = None

    def start(self) -> None:
        if not self.script.exists():
            logger.error("[%s] script missing: %s", self.name, self.script)
            return
        env = {**project_python_env(PROJECT_ROOT), "PYTHONUNBUFFERED": "1"}
        self.process = Popen(  # nosec B603
            [str(get_python_executable()), str(self.script), *self.args],
            cwd=str(PROJECT_ROOT), env=env, stdout=DEVNULL, stderr=DEVNULL,
        )
        self.last_started = datetime.now().isoformat()
        logger.info("[%s] started subprocess (PID %s)", self.name, self.process.pid)

    def check(self) -> None:
        if self.process and self.process.poll() is not None and not _shutdown.is_set():
            logger.warning("[%s] subprocess exited (code %s) — restarting", self.name, self.process.returncode)
            self.total_restarts += 1
            self.start()

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
            except Exception:  # noqa: BLE001
                self.process.kill()

    def status(self) -> dict[str, Any]:
        alive = bool(self.process and self.process.poll() is None)
        return {
            "kind": "subprocess",
            "state": "running" if alive else "stopped",
            "pid": self.process.pid if alive else None,
            "total_restarts": self.total_restarts,
            "last_started": self.last_started,
        }


def _write_status(started_at: str, threads: dict[str, ThreadService], subs: dict[str, SubprocessService]) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    services = {n: s.status() for n, s in threads.items()}
    services.update({n: s.status() for n, s in subs.items()})
    data = {
        "supervisor_pid": os.getpid(),
        "started_at": started_at,
        "updated_at": datetime.now().isoformat(),
        "services": services,
    }
    STATUS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _read_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        from skills.daemon.scripts import daemon_diagnostics
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        return pid if daemon_diagnostics._default_pid_exists(pid) else None
    except Exception:  # noqa: BLE001
        return None


def _port_is_open(port: int, host: str = "127.0.0.1") -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def _resolve_node() -> str | None:
    """Find the node executable, robust to a minimal logon-task PATH.

    The com.augur.daemon scheduled task has no EnvironmentVariables block, so a
    node installed only on a per-shell PATH (nvm/volta/fnm) may be invisible to
    `which`. Fall back to common install locations before giving up.
    """
    import shutil

    found = shutil.which("node")
    if found:
        return found

    candidates: list[Path] = []
    if sys.platform == "win32":
        exe = "node.exe"
        for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
            base = os.environ.get(var)
            if base:
                candidates.append(Path(base) / "nodejs" / exe)
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / "Volta" / "bin" / exe)
            candidates.append(Path(local) / "fnm_multishells" / exe)  # best-effort
            candidates.append(Path(local) / "Programs" / "nodejs" / exe)
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(Path(appdata) / "nvm" / exe)
    else:
        candidates += [
            Path("/usr/local/bin/node"),
            Path("/opt/homebrew/bin/node"),
            Path("/usr/bin/node"),
            Path.home() / ".volta" / "bin" / "node",
        ]
        nvm_root = Path.home() / ".nvm" / "versions" / "node"
        if nvm_root.is_dir():
            versions = sorted((p for p in nvm_root.iterdir() if p.is_dir()), reverse=True)
            candidates += [v / "bin" / "node" for v in versions]

    for cand in candidates:
        if cand.is_file():
            return str(cand)
    return None


def _ensure_prod_dashboard() -> None:
    """Bring up the main :3000 production dashboard at supervisor startup (ADR-787).

    This is the reboot-survival path: the com.augur.daemon logon task starts this
    supervisor, and the supervisor in turn ensures the production dashboard the
    user expects on :3000 is serving — without a second scheduled task to race.

    It is a one-time ensure, NOT crash recovery (recovery stays off — see
    dashboard_monitor). Guard rails:
      - only the main checkout (`.git` is a directory; worktrees use a gitdir file
        and their own ports),
      - only when a completed build exists (`.next/BUILD_ID`) — never builds here,
      - only when nothing is already serving :3000 (don't fight a user/dev server),
      - opt out with AUGUR_SUPERVISOR_SERVE_DASHBOARD=0.
    """
    if os.environ.get("AUGUR_SUPERVISOR_SERVE_DASHBOARD") == "0":
        return
    if not _is_main_checkout():
        logger.info("Not the main checkout; skipping prod dashboard ensure.")
        return

    dashboard_dir = PROJECT_ROOT / "apps" / "dashboard"
    if not (dashboard_dir / ".next" / "BUILD_ID").exists():
        logger.warning(
            "No production build (.next/BUILD_ID) — skipping dashboard ensure. "
            "Run `pnpm prod` once to produce the build."
        )
        return
    if _port_is_open(3000):
        logger.info("Dashboard already serving on :3000; not starting another.")
        return

    node = _resolve_node()
    if not node:
        logger.warning(
            "`node` not found on PATH or common install locations; cannot start "
            "prod dashboard. Add node to the machine PATH or start it with `pnpm prod`."
        )
        return

    logger.info("Starting production dashboard on :3000 (start-dev --prod)...")
    try:
        Popen(  # nosec B603
            [node, "scripts/start-dev.mjs", "--prod"],
            cwd=str(dashboard_dir),
            stdin=DEVNULL,  # never inherit the supervisor's stdin (avoids the bridge-style hang)
            stdout=DEVNULL,
            stderr=DEVNULL,
            close_fds=True,
        )
    except OSError as exc:
        logger.warning("Failed to start prod dashboard: %s", exc)


def run() -> int:
    if _read_pid():
        logger.error("Supervisor already running (PID %s). Use 'stop' first.", _read_pid())
        return 1

    # Survive stray console Ctrl+C (HMR/process churn); stop only on SIGTERM or
    # an explicit stop. Mirrors the MCP bridge fix (ADR-787 sibling).
    def _on_term(_sig: int, _frame: Any) -> None:
        _shutdown.set()

    for signame in ("SIGINT", "SIGBREAK"):
        sig = getattr(signal, signame, None)
        if sig is not None:
            try:
                signal.signal(sig, signal.SIG_IGN)
            except (ValueError, OSError):
                pass
    try:
        signal.signal(signal.SIGTERM, _on_term)
    except (ValueError, OSError):
        pass

    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    started_at = datetime.now().isoformat()

    active = _active_daemons()
    role = "main/prod" if _is_main_checkout() else "worktree/dev"
    registry = _build_registry(active)
    threads = {name: ThreadService(name, loop) for name, loop in registry.items()}
    subs: dict[str, SubprocessService] = {}
    if "adaptive_loop_executor" in active:
        subs["adaptive_loop_executor"] = SubprocessService(
            "adaptive_loop_executor", SCRIPTS_DIR / "adaptive_loop_executor.py", ["--loop"]
        )

    disabled = sorted(ALL_DAEMONS - active)
    logger.info(
        "Supervisor starting (PID %s, role=%s): %d in-process + %d subprocess daemons. "
        "ON=%s OFF=%s%s",
        os.getpid(), role, len(threads), len(subs), sorted(active), disabled,
        " (set AUGUR_SUPERVISOR_DAEMONS to change)" if disabled else "",
    )
    for svc in threads.values():
        svc.start()
    for svc in subs.values():
        svc.start()

    try:
        _ensure_prod_dashboard()
    except Exception as exc:  # noqa: BLE001
        logger.warning("prod dashboard ensure failed: %s", exc)

    try:
        while not _shutdown.is_set():
            for svc in subs.values():
                svc.check()
            try:
                _write_status(started_at, threads, subs)
            except Exception as exc:  # noqa: BLE001
                logger.warning("status write failed: %s", exc)
            _shutdown.wait(15)
    finally:
        logger.info("Supervisor shutting down...")
        for svc in subs.values():
            svc.stop()
        try:
            PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass
    return 0


def cmd_status() -> int:
    if not STATUS_FILE.exists():
        print("Supervisor: STOPPED (no status file)")
        return 1
    data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    running = _read_pid() is not None
    print(f"Supervisor: {'RUNNING' if running else 'STOPPED'} (PID {data.get('supervisor_pid')})")
    for name, info in (data.get("services") or {}).items():
        print(f"  {name}: {str(info.get('state','?')).upper()} [{info.get('kind')}] restarts={info.get('total_restarts',0)}")
    return 0 if running else 1


def cmd_stop() -> int:
    pid = _read_pid()
    if not pid:
        print("Supervisor not running")
        return 1
    print(f"Stopping supervisor (PID {pid})...")
    if sys.platform == "win32":
        os.system(f"taskkill /PID {pid} /T /F >nul 2>&1")  # nosec B605
    else:
        os.kill(pid, signal.SIGTERM)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="In-process Augur daemon supervisor (ADR-787 Part B)")
    parser.add_argument("command", nargs="?", default="start", choices=["start", "stop", "status"])
    args = parser.parse_args()
    if args.command == "start":
        return run()
    if args.command == "status":
        return cmd_status()
    if args.command == "stop":
        return cmd_stop()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
