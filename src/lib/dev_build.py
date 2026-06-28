from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from src.config.paths import get_logs_dir, get_project_root, get_runtime_dir
from src.lib.dashboard_instance import (
    AugurDashboardInstance,
    resolve_dashboard_instance,
)

IS_WINDOWS = sys.platform == "win32"


def resolve_target(project_root: Path | None = None) -> AugurDashboardInstance:
    """Resolve the dashboard instance to build/restart for this checkout."""
    root = Path(project_root) if project_root is not None else Path.cwd()
    return resolve_dashboard_instance(root, runtime_dir=get_runtime_dir(), interactive=False)


# ---------------------------------------------------------------------------
# Mockable seams — thin wrappers over real I/O; replaced in unit tests.
# ---------------------------------------------------------------------------


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _daemon_scripts_on_path() -> None:
    p = str(Path(get_project_root()) / "project-brain/capabilities/skills/daemon/scripts")
    if p not in sys.path:
        sys.path.insert(0, p)


def _preflight_ok(instance) -> bool:
    """True if the dashboard CAN start (worktree preflight passes). Read-only.

    Guards against stopping a dashboard we cannot restart — e.g. the main checkout
    on a feature branch fails the `main_checkout_branch` preflight check, so
    `start-dev.sh` would exit silently and strand :3000.
    """
    root = get_project_root()
    proc = subprocess.run(
        [sys.executable, "scripts/worktree_preflight.py", "--root", str(root), "--profile", "dashboard"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return bool(json.loads(proc.stdout).get("verify_passed"))
    except (ValueError, json.JSONDecodeError):
        return False


def _stop_instance(instance) -> dict:
    _daemon_scripts_on_path()
    import scoped_restart  # noqa: PLC0415

    return scoped_restart.stop_instance(instance)


def _run_build(instance) -> int:
    dash = Path(get_project_root()) / "apps/dashboard"
    return subprocess.run(
        ["node", "scripts/build-lock.mjs", "pnpm", "run", "build"],
        cwd=dash,
        check=False,
    ).returncode


def _server_log_path(instance) -> Path:
    """File that captures the detached dashboard server's stdout+stderr.

    Previously the server was spawned with stdout/stderr -> DEVNULL, which
    silently discarded production 500 stack traces (a /login 500 from a
    deleted .next was invisible in every log and had to be diagnosed from the
    filesystem). Routing to a real file under get_logs_dir() makes server-side
    errors visible. Appends so a crash log survives a self-heal restart;
    rotation/truncation is a separate follow-up.
    """
    try:
        logs_dir = get_logs_dir()
    except Exception:  # pragma: no cover - fall back to runtime dir
        logs_dir = get_runtime_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    port = getattr(instance, "dashboard_port", None) or getattr(instance, "port", None) or "main"
    return logs_dir / f"dashboard.{port}.log"


def _start_server(instance, *, prod: bool = False) -> None:
    dash = Path(get_project_root()) / "apps/dashboard"
    # Capture the detached server's output instead of dropping it to DEVNULL so
    # production errors (500s, chunk-load failures) leave a trace. The child
    # inherits a dup of this fd and keeps writing after this process exits.
    log_fp = open(_server_log_path(instance), "ab")  # noqa: SIM115 - lives with the child
    kwargs: dict = {"cwd": dash, "stdout": log_fp, "stderr": subprocess.STDOUT}
    # The main :3000 dashboard must always be production (ADR-787); worktrees and
    # isolated instances run the Turbopack dev server on their own ports. `--prod`
    # makes start-dev serve the prebuilt production bundle (see run_dev_build).
    prod_args = ["--prod"] if prod else []
    if IS_WINDOWS:
        # start-dev.sh is POSIX-only (python3/lsof/ln -s + `set -euo pipefail`);
        # start-dev.mjs is the cross-platform entry that runs a native Windows
        # startup path. Detach so the long-lived server outlives this build process.
        cmd = ["node", "scripts/start-dev.mjs", *prod_args]
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        cmd = ["bash", "scripts/start-dev.sh", *prod_args]
        kwargs["start_new_session"] = True
    subprocess.Popen(cmd, **kwargs)


def _poll_ready(instance, timeout: int = 90) -> bool:
    url = f"http://localhost:{instance.dashboard_port}/"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if not url.lower().startswith(("http://", "https://")):
                raise ValueError(f"Non-HTTP URL rejected: {url!r}")
            with urllib.request.urlopen(url, timeout=5) as r:  # nosec B310  # scheme-validated above (http/https only)
                if r.status == 200:
                    return True
        except Exception:
            pass
        _sleep(2)
    return False


def _fresh_mcp_present(instance, prev_pids) -> bool:
    _daemon_scripts_on_path()
    import scoped_restart  # noqa: PLC0415

    now = set(scoped_restart.instance_mcp_pids(instance))
    return any(p not in set(prev_pids) for p in now)


# ---------------------------------------------------------------------------
# Orchestration entry point
# ---------------------------------------------------------------------------


def run_dev_build(max_gate_retries: int = 3, full_build: bool = False) -> dict:
    """Resolve target → gated scoped stop → (build) → start → poll → verify MCP.

    The main :3000 dashboard is ALWAYS served in production mode (ADR-787): a build
    is produced and served as a static production bundle. Only worktree/isolated run
    on their own ports as the Turbopack dev server, where the default refresh relies
    on start-dev's turbopack recompile (``full_build=True`` opt-in there forces a
    production ``pnpm run build`` first — heavier, never the dev default).
    """
    instance = resolve_target()
    is_main = instance.kind == "main"
    if not _preflight_ok(instance):
        return {
            "ok": False,
            "reason": (
                "preflight failed: the dashboard cannot start (e.g. the main checkout is on a "
                "feature branch — use a worktree or merge to main first). Not stopping the "
                "running dashboard."
            ),
            "port": instance.dashboard_port,
        }
    stop = _stop_instance(instance)
    tries = 0
    while stop.get("decision") == "denied" and tries < max_gate_retries:
        _sleep(5)
        tries += 1
        stop = _stop_instance(instance)
    if stop.get("decision") != "granted":
        return {
            "ok": False,
            "reason": f"gate denied: {stop.get('reason', '')}",
            "port": instance.dashboard_port,
        }
    # Main always builds (prod serve needs a fresh .next/BUILD_ID); worktrees build
    # only when explicitly asked (full_build), otherwise turbopack recompiles live.
    if is_main or full_build:
        rebuilt = _run_build(instance) == 0
    else:
        rebuilt = True
    _start_server(instance, prod=is_main)
    ready = _poll_ready(instance)
    mcp_recycled = _fresh_mcp_present(instance, stop.get("recycled_mcp_pids", []))
    return {
        "ok": bool(rebuilt and ready),
        "port": instance.dashboard_port,
        "mode": "production" if is_main else "dev",
        "rebuilt": rebuilt,
        "mcp_recycled": mcp_recycled,
        "url": f"http://localhost:{instance.dashboard_port}/",
    }
