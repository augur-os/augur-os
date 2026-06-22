"""Scoped dashboard restart: stop ONE instance's server + its MCP children.

Launchd-safe (never unloads the service) and instance-scoped (never uses the
broad `pgrep -f mcp`). Used by the `aug dev build` engine and `/dev build`.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from typing import Any

import cleanup_processes as _cp
import dashboard_lifecycle as _gate

try:
    from src.logging import get_entity_logger
except ImportError:  # pragma: no cover - fallback when src is unavailable

    def get_entity_logger(name: str) -> logging.Logger:
        log = logging.getLogger(name)
        if not log.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
            log.addHandler(handler)
            log.setLevel(logging.INFO)
        return log


logger = get_entity_logger("scoped_restart")

pids_on_port = _cp.get_pids_on_port
kill_process_group = _cp.kill_process_group
kill_pid = _cp.kill_pid


def stop_launchd_service(*_a: Any, **_kw: Any) -> None:
    """Never unload launchd from a scoped restart. Hard guard against regressions."""
    raise RuntimeError("scoped_restart must never unload launchd")


def request_gate(*, actor: str, action: str, reason: str, instance_id: str) -> dict:
    return _gate.request_action(actor=actor, action=action, reason=reason, instance_id=instance_id)


def release_gate_stopped(*, actor: str, reason: str, instance_id: str) -> dict:
    """Release the gate to a clean 'stopped' resting state after the stop completes.

    The restart grab in stop_instance leaves the gate 'starting'; without this
    release, start-dev.sh's build-lock 'start' is denied ("dashboard is
    starting") and the gate strands. See dashboard_lifecycle.mark_stopped.
    """
    return _gate.mark_stopped(actor, reason, instance_id=instance_id)


def scan_mcp_candidates() -> list[dict[str, str]]:
    system = platform.system()
    if system == "Darwin":
        # macOS `ps -E` inlines the process env into the command column, so
        # AUGUR_MCP_CLIENT_ID is visible directly in the listed line.
        out = subprocess.run(["ps", "-E", "-o", "pid=,command="], capture_output=True, text=True, check=False).stdout
        rows: list[dict[str, str]] = []
        for line in out.splitlines():
            if "-m augur_core" not in line and "-m augur_framework" not in line:
                continue
            parts = line.strip().split(None, 1)
            if len(parts) != 2:
                continue
            pid, cmd = parts
            client_id = ""
            for tok in cmd.split():
                if tok.startswith("AUGUR_MCP_CLIENT_ID="):
                    client_id = tok.split("=", 1)[1]
            rows.append({"pid": pid, "client_id": client_id, "cwd": _proc_cwd(pid)})
        return rows
    if system == "Linux":
        # Linux `ps` has no env-inlining flag; read env + cwd from /proc instead.
        out = subprocess.run(["ps", "-e", "-o", "pid=,args="], capture_output=True, text=True, check=False).stdout
        rows = []
        for line in out.splitlines():
            if "-m augur_core" not in line and "-m augur_framework" not in line:
                continue
            parts = line.strip().split(None, 1)
            if len(parts) != 2:
                continue
            pid, _cmd = parts
            rows.append({"pid": pid, "client_id": _proc_env_value(pid, "AUGUR_MCP_CLIENT_ID"), "cwd": _proc_cwd(pid)})
        return rows
    raise NotImplementedError(f"scan_mcp_candidates is unsupported on {system}; extend for this platform")


def _proc_env_value(pid: str, key: str) -> str:
    """Read one env var of a process from /proc/<pid>/environ (Linux)."""
    try:
        with open(f"/proc/{pid}/environ", "rb") as fh:
            for entry in fh.read().split(b"\0"):
                if entry.startswith(key.encode() + b"="):
                    return entry.split(b"=", 1)[1].decode("utf-8", "replace")
    except OSError:
        pass
    return ""


def _proc_cwd(pid: str) -> str:
    if platform.system() == "Linux":
        try:
            return os.readlink(f"/proc/{pid}/cwd")
        except OSError:
            return ""
    out = subprocess.run(
        ["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"], capture_output=True, text=True, check=False
    ).stdout
    for ln in out.splitlines():
        if ln.startswith("n"):
            return ln[1:]
    return ""


def _own_tree_pids() -> set[str]:
    pids, pid = set(), os.getpid()
    for _ in range(12):
        pids.add(str(pid))
        try:
            ppid = int(
                subprocess.run(
                    ["ps", "-o", "ppid=", "-p", str(pid)], capture_output=True, text=True, check=False
                ).stdout.strip()
                or "0"
            )
        except ValueError:
            break
        if ppid <= 1:
            break
        pid = ppid
    return pids


def instance_mcp_pids(instance: Any, own: set[str] | None = None) -> list[str]:
    """Dashboard MCP children for THIS instance: env AUGUR_MCP_CLIENT_ID starts
    with 'dashboard-' (set by scopeDashboardProcessClientId, preflight.ts) AND cwd
    is the instance's project_root. The agent's own session MCP / Cowork use a
    different client-id; own-tree exclusion is the backstop."""
    own = _own_tree_pids() if own is None else own
    proj = str(instance.project_root)
    return sorted(
        c["pid"]
        for c in scan_mcp_candidates()
        if c["client_id"].startswith("dashboard-") and c["cwd"] == proj and c["pid"] not in own
    )


DEV_SERVER_MARKERS = ("next dev", "next-server", "start-dev.sh", "start-dev.mjs", "npm run dev")


def scan_dev_server_candidates() -> list[dict[str, str]]:
    out = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True, check=False).stdout
    rows: list[dict[str, str]] = []
    for line in out.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        pid, cmd = parts
        if any(marker in cmd for marker in DEV_SERVER_MARKERS):
            rows.append({"pid": pid, "command": cmd, "cwd": _proc_cwd(pid)})
    return rows


def instance_dev_server_pids(instance: Any, own: set[str] | None = None) -> list[str]:
    """Dev-server processes for THIS instance regardless of bound port.

    pids_on_port() only sees the canonical port, so a port-drifted respawn is
    invisible to it — e.g. a hung server holds :3000, the self-heal daemon's
    `npm run dev` auto-increments to :3002, and the drifted instance then owns
    Next's dev-singleton lock, starving every new :3000 start. Match by
    command marker + cwd inside the instance's checkout instead; an unknown
    cwd (lsof failure) is skipped, never killed. Worktrees have their own
    project_root, so cross-instance kills are excluded by construction."""
    own = _own_tree_pids() if own is None else own
    root = str(instance.project_root).rstrip("/")
    prefix = root + "/"
    return sorted(
        c["pid"]
        for c in scan_dev_server_candidates()
        if c["pid"] not in own and (c["cwd"] == root or c["cwd"].startswith(prefix))
    )


def stop_instance(instance: Any, *, dry_run: bool = False) -> dict:
    decision = request_gate(
        actor="agent:aug-dev-build",
        action="restart",
        reason="aug dev build scoped restart",
        instance_id=instance.instance_id,
    )
    logger.info("scoped restart gate for %s: %s", instance.instance_id, decision.get("decision"))
    if decision.get("decision") != "granted":
        return {
            "decision": "denied",
            "reason": decision.get("reason", ""),
            "stopped_port_pids": [],
            "recycled_mcp_pids": [],
            "stopped_drifted_pids": [],
        }
    own = _own_tree_pids()
    port_pids = sorted(p for p in pids_on_port(instance.dashboard_port) if p not in own)
    drifted_pids = [p for p in instance_dev_server_pids(instance, own=own) if p not in port_pids]
    mcp_pids = instance_mcp_pids(instance, own=own)
    logger.info(
        "scoped restart for %s: port pids %s, drifted dev-server pids %s, mcp pids %s",
        instance.instance_id,
        port_pids,
        drifted_pids,
        mcp_pids,
    )
    if dry_run:
        return {
            "decision": "granted",
            "stopped_port_pids": port_pids,
            "recycled_mcp_pids": mcp_pids,
            "stopped_drifted_pids": drifted_pids,
            "dry_run": True,
        }
    for pid in port_pids:
        kill_process_group(pid, graceful=True)
    for pid in drifted_pids:
        kill_process_group(pid, graceful=True)
    for pid in mcp_pids:
        kill_pid(pid, graceful=True)
    # Release the gate to 'stopped' so the start that follows (start-dev.sh's
    # build-lock) is grantable. The restart grab above left it 'starting', which
    # would otherwise deadlock the build-lock 'start' and strand the gate.
    release_gate_stopped(
        actor="agent:aug-dev-build",
        reason="scoped stop complete; gate released for restart",
        instance_id=instance.instance_id,
    )
    return {
        "decision": "granted",
        "stopped_port_pids": port_pids,
        "recycled_mcp_pids": mcp_pids,
        "stopped_drifted_pids": drifted_pids,
    }
