"""Tests for scoped_restart.py — launchd-safe, instance-scoped restart primitive."""

import sys
from pathlib import Path

PROJECT_ROOT = next(
    (p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()),
    Path(__file__).resolve().parents[-1],
)
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import scoped_restart as sr  # noqa: E402


class Inst:
    instance_id = "main"
    dashboard_port = 3000
    mcp_port = 8080
    project_root = Path("/proj")


def test_stop_instance_targets_only_instance_port_and_scoped_mcp(monkeypatch):
    calls = {"port_kills": [], "mcp_kills": [], "launchd": 0, "gate": [], "released": []}

    monkeypatch.setattr(sr, "request_gate", lambda **k: (calls["gate"].append(k) or {"decision": "granted"}))
    monkeypatch.setattr(sr, "release_gate_stopped", lambda **k: (calls["released"].append(k) or {"state": "stopped"}))
    monkeypatch.setattr(sr, "pids_on_port", lambda port: {"100"} if port == 3000 else set())
    monkeypatch.setattr(sr, "scan_dev_server_candidates", lambda: [])
    monkeypatch.setattr(sr, "scan_mcp_candidates", lambda: [
        {"pid": "200", "client_id": "dashboard-Augur-abc", "cwd": "/proj"},   # → kill
        {"pid": "201", "client_id": "cowork",              "cwd": "/proj"},   # wrong prefix → skip
        {"pid": "202", "client_id": "dashboard-Other-xyz", "cwd": "/other"},  # wrong cwd → skip
    ])
    monkeypatch.setattr(sr, "_own_tree_pids", lambda: set())
    monkeypatch.setattr(sr, "kill_process_group", lambda pid, **k: calls["port_kills"].append(pid) or True)
    monkeypatch.setattr(sr, "kill_pid", lambda pid, **k: calls["mcp_kills"].append(pid) or True)
    monkeypatch.setattr(sr, "stop_launchd_service", lambda *a, **k: calls.__setitem__("launchd", calls["launchd"] + 1))
    result = sr.stop_instance(Inst())
    assert calls["port_kills"] == ["100"]
    assert calls["mcp_kills"] == ["200"]
    assert calls["launchd"] == 0
    assert calls["gate"] and calls["gate"][0]["action"]
    # The completed stop releases the gate to 'stopped' so the following start is grantable.
    assert calls["released"] and calls["released"][0]["instance_id"] == "main"
    assert result["stopped_port_pids"] == ["100"]
    assert result["recycled_mcp_pids"] == ["200"]


def test_stop_instance_releases_gate_to_stopped_even_with_no_processes(monkeypatch):
    """Cold-start regression: when nothing is running (no port/MCP pids), the
    stop must still release the gate to 'stopped'. Otherwise the gate, set to
    'starting' by the restart grab, strands and the build-lock start deadlocks."""
    calls = {"released": []}

    monkeypatch.setattr(sr, "request_gate", lambda **k: {"decision": "granted"})
    monkeypatch.setattr(sr, "release_gate_stopped", lambda **k: (calls["released"].append(k) or {"state": "stopped"}))
    monkeypatch.setattr(sr, "pids_on_port", lambda port: set())        # nothing on the port
    monkeypatch.setattr(sr, "scan_dev_server_candidates", lambda: [])   # no drifted dev servers
    monkeypatch.setattr(sr, "scan_mcp_candidates", lambda: [])          # no MCP children
    monkeypatch.setattr(sr, "_own_tree_pids", lambda: set())
    monkeypatch.setattr(sr, "kill_process_group", lambda pid, **k: True)
    monkeypatch.setattr(sr, "kill_pid", lambda pid, **k: True)

    result = sr.stop_instance(Inst())
    assert result["decision"] == "granted"
    assert result["stopped_port_pids"] == [] and result["recycled_mcp_pids"] == []
    assert len(calls["released"]) == 1
    assert calls["released"][0]["instance_id"] == "main"


def test_stop_instance_dry_run_does_not_release_gate(monkeypatch):
    """A dry run inspects only — it must not mutate the gate."""
    calls = {"released": []}

    monkeypatch.setattr(sr, "request_gate", lambda **k: {"decision": "granted"})
    monkeypatch.setattr(sr, "release_gate_stopped", lambda **k: calls["released"].append(k))
    monkeypatch.setattr(sr, "pids_on_port", lambda port: {"100"} if port == 3000 else set())
    monkeypatch.setattr(sr, "scan_dev_server_candidates", lambda: [])
    monkeypatch.setattr(sr, "scan_mcp_candidates", lambda: [])
    monkeypatch.setattr(sr, "_own_tree_pids", lambda: set())
    monkeypatch.setattr(sr, "kill_process_group", lambda pid, **k: True)
    monkeypatch.setattr(sr, "kill_pid", lambda pid, **k: True)

    result = sr.stop_instance(Inst(), dry_run=True)
    assert result["dry_run"] is True
    assert calls["released"] == []


def test_stop_instance_dry_run_kills_nothing(monkeypatch):
    calls = {"port_kills": [], "mcp_kills": []}

    monkeypatch.setattr(sr, "request_gate", lambda **k: {"decision": "granted"})
    monkeypatch.setattr(sr, "pids_on_port", lambda port: {"100"} if port == 3000 else set())
    monkeypatch.setattr(sr, "scan_dev_server_candidates", lambda: [])
    monkeypatch.setattr(sr, "scan_mcp_candidates", lambda: [
        {"pid": "200", "client_id": "dashboard-Augur-abc", "cwd": "/proj"},
    ])
    monkeypatch.setattr(sr, "_own_tree_pids", lambda: set())
    monkeypatch.setattr(sr, "kill_process_group", lambda pid, **k: calls["port_kills"].append(pid) or True)
    monkeypatch.setattr(sr, "kill_pid", lambda pid, **k: calls["mcp_kills"].append(pid) or True)
    result = sr.stop_instance(Inst(), dry_run=True)
    assert result["dry_run"] is True
    assert result["stopped_port_pids"] == ["100"]
    assert result["recycled_mcp_pids"] == ["200"]
    assert calls["port_kills"] == [] and calls["mcp_kills"] == []


def test_stop_instance_reaps_port_drifted_dev_server(monkeypatch):
    """Port-drift regression (2026-06-11): a hung server on :3000 made the
    self-heal daemon's respawn bind :3002; after the hung pid died, the drifted
    chain owned Next's dev-singleton lock and starved every new :3000 start,
    while pids_on_port(3000) saw nothing to stop. The stop must reap dev-server
    processes by checkout cwd, not just canonical port."""
    calls = {"group_kills": [], "released": []}

    monkeypatch.setattr(sr, "request_gate", lambda **k: {"decision": "granted"})
    monkeypatch.setattr(sr, "release_gate_stopped", lambda **k: (calls["released"].append(k) or {"state": "stopped"}))
    monkeypatch.setattr(sr, "pids_on_port", lambda port: set())  # :3000 already free
    monkeypatch.setattr(sr, "scan_dev_server_candidates", lambda: [
        {"pid": "300", "command": "npm run dev", "cwd": "/proj"},                          # drifted root → kill
        {"pid": "301", "command": "next-server (v16.2.6)", "cwd": "/proj/apps/dashboard"},  # drifted server → kill
        {"pid": "302", "command": "next-server (v16.2.6)", "cwd": "/other-worktree/apps/dashboard"},  # other checkout → skip
        {"pid": "303", "command": "npm run dev", "cwd": "/proj-other"},                    # prefix trap → skip
        {"pid": "304", "command": "next dev", "cwd": ""},                                  # unknown cwd → skip
    ])
    monkeypatch.setattr(sr, "scan_mcp_candidates", lambda: [])
    monkeypatch.setattr(sr, "_own_tree_pids", lambda: set())
    monkeypatch.setattr(sr, "kill_process_group", lambda pid, **k: calls["group_kills"].append(pid) or True)
    monkeypatch.setattr(sr, "kill_pid", lambda pid, **k: True)

    result = sr.stop_instance(Inst())
    assert result["stopped_drifted_pids"] == ["300", "301"]
    assert calls["group_kills"] == ["300", "301"]
    assert len(calls["released"]) == 1


def test_drifted_pids_exclude_port_and_own_tree(monkeypatch):
    """A pid already covered by the port kill must not be double-reported as
    drifted, and the agent's own process tree is never a kill target."""
    monkeypatch.setattr(sr, "scan_dev_server_candidates", lambda: [
        {"pid": "100", "command": "next dev", "cwd": "/proj/apps/dashboard"},  # on the port
        {"pid": "400", "command": "next dev", "cwd": "/proj/apps/dashboard"},  # own tree
        {"pid": "500", "command": "next dev", "cwd": "/proj/apps/dashboard"},  # drifted
    ])
    assert sr.instance_dev_server_pids(Inst(), own={"400"}) == ["100", "500"]

    calls = {"group_kills": []}
    monkeypatch.setattr(sr, "request_gate", lambda **k: {"decision": "granted"})
    monkeypatch.setattr(sr, "release_gate_stopped", lambda **k: {"state": "stopped"})
    monkeypatch.setattr(sr, "pids_on_port", lambda port: {"100"} if port == 3000 else set())
    monkeypatch.setattr(sr, "scan_mcp_candidates", lambda: [])
    monkeypatch.setattr(sr, "_own_tree_pids", lambda: {"400"})
    monkeypatch.setattr(sr, "kill_process_group", lambda pid, **k: calls["group_kills"].append(pid) or True)
    monkeypatch.setattr(sr, "kill_pid", lambda pid, **k: True)

    result = sr.stop_instance(Inst())
    assert result["stopped_port_pids"] == ["100"]
    assert result["stopped_drifted_pids"] == ["500"]
    assert calls["group_kills"] == ["100", "500"]


def test_stop_instance_denied_gate_kills_nothing(monkeypatch):
    calls = {"port_kills": [], "mcp_kills": []}

    monkeypatch.setattr(sr, "request_gate", lambda **k: {"decision": "denied", "reason": "compiling"})
    monkeypatch.setattr(sr, "kill_process_group", lambda pid, **k: calls["port_kills"].append(pid))
    monkeypatch.setattr(sr, "kill_pid", lambda pid, **k: calls["mcp_kills"].append(pid))
    result = sr.stop_instance(Inst())
    assert result["decision"] == "denied"
    assert calls["port_kills"] == [] and calls["mcp_kills"] == []
