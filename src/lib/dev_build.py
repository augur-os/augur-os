from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from src.config.paths import get_project_root, get_runtime_dir
from src.lib.dashboard_instance import (
    AugurDashboardInstance,
    resolve_dashboard_instance,
)


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
        ["python3", "scripts/worktree_preflight.py", "--root", str(root), "--profile", "dashboard"],
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


def _start_server(instance) -> None:
    dash = Path(get_project_root()) / "apps/dashboard"
    subprocess.Popen(
        ["bash", "scripts/start-dev.sh"],
        cwd=dash,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


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
    """Resolve target → gated scoped stop → start (turbopack dev rebuild) → poll → verify MCP.

    The default refresh relies on start-dev's turbopack recompile, which is safe for a
    live dashboard. ``full_build=True`` first runs a production ``pnpm run build``; that is
    heavier and can leave a production ``.next`` that crash-loops ``next dev`` (see the
    DEBUGGING.md dev-server recovery runbook), so it is opt-in, never the default.
    """
    instance = resolve_target()
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
    rebuilt = (_run_build(instance) == 0) if full_build else True
    _start_server(instance)
    ready = _poll_ready(instance)
    mcp_recycled = _fresh_mcp_present(instance, stop.get("recycled_mcp_pids", []))
    return {
        "ok": bool(rebuilt and ready),
        "port": instance.dashboard_port,
        "rebuilt": rebuilt,
        "mcp_recycled": mcp_recycled,
        "url": f"http://localhost:{instance.dashboard_port}/",
    }
