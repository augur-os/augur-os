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
    # Plain string (not Path) so cwd string-matching is separator-consistent on
    # every OS — Path("/proj") stringifies to "\proj" on Windows and breaks the
    # forward-slash cwd literals below. Production coerces via str()/Path().
    project_root = "/proj"


def test_stop_instance_targets_only_instance_port_and_scoped_mcp(monkeypatch):
    calls = {"port_kills": [], "mcp_kills": [], "launchd": 0, "gate": [], "released": []}

    monkeypatch.setattr(sr, "IS_WINDOWS", False)  # POSIX cwd-scoped MCP matching
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

    monkeypatch.setattr(sr, "IS_WINDOWS", False)  # POSIX cwd-scoped MCP matching
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


def test_client_id_from_cmd_parses_argv_and_env_forms():
    assert sr._client_id_from_cmd("py -m augur_framework --client-id dashboard-A-1 --force") == "dashboard-A-1"
    assert sr._client_id_from_cmd("py -m augur_core --client-id=claude") == "claude"
    assert sr._client_id_from_cmd("AUGUR_MCP_CLIENT_ID=dashboard-B-2 py -m augur_core") == "dashboard-B-2"
    assert sr._client_id_from_cmd("py -m augur_core") == ""


def test_instance_client_id_matches_worktree_preflight():
    """Drift guard: must equal scripts/worktree_preflight.py:_client_id, the
    source start-dev exports as AUGUR_MCP_CLIENT_ID. If this drifts, Windows
    scoping silently misses the instance's MCP children."""
    import hashlib

    root = Path(Inst.project_root)
    digest = hashlib.sha1(str(root).encode("utf-8")).hexdigest()[:8]
    assert sr._instance_client_id(Inst()) == f"dashboard-{root.name}-{digest}"


def test_windows_scan_mcp_candidates_reads_client_id_off_cmdline(monkeypatch):
    """The Windows scan identifies MCP processes by the augur_core/augur_framework
    marker and reads --client-id off the CIM CommandLine (no env block read)."""
    monkeypatch.setattr(sr.platform, "system", lambda: "Windows")
    monkeypatch.setattr(sr, "_windows_proc_table", lambda: [
        {"pid": "200", "ppid": "1", "cmd": "python.exe -m augur_framework --client-id dashboard-Augur-06e1cb97-p20276 --force"},
        {"pid": "201", "ppid": "1", "cmd": "python.exe -m augur_core --client-id claude"},
        {"pid": "202", "ppid": "1", "cmd": "node next-server"},  # not an MCP → excluded
    ])
    assert sr.scan_mcp_candidates() == [
        {"pid": "200", "client_id": "dashboard-Augur-06e1cb97-p20276", "cwd": ""},
        {"pid": "201", "client_id": "claude", "cwd": ""},
    ]


def test_instance_mcp_pids_windows_scopes_by_client_id_excludes_session(monkeypatch):
    """On Windows there is no per-process cwd, so MCP children are scoped by the
    instance's deterministic client-id prefix: this checkout's dashboard children
    are reaped while the agent's own 'claude' session and other checkouts are not."""
    monkeypatch.setattr(sr, "IS_WINDOWS", True)
    expected = sr._instance_client_id(Inst())
    monkeypatch.setattr(sr, "scan_mcp_candidates", lambda: [
        {"pid": "200", "client_id": f"{expected}-p20276", "cwd": ""},          # this instance → kill
        {"pid": "201", "client_id": "claude", "cwd": ""},                       # agent session → skip
        {"pid": "202", "client_id": "dashboard-Other-deadbeef-p9", "cwd": ""},  # other checkout → skip
    ])
    monkeypatch.setattr(sr, "_own_tree_pids", lambda: set())
    assert sr.instance_mcp_pids(Inst()) == ["200"]


def test_windows_own_tree_walks_parent_chain(monkeypatch):
    """_own_tree_pids on Windows walks ParentProcessId via the CIM table; the
    own tree is never a kill target, so the walk must terminate cleanly."""
    monkeypatch.setattr(sr.os, "getpid", lambda: 500)
    monkeypatch.setattr(sr, "_windows_proc_table", lambda: [
        {"pid": "500", "ppid": "400", "cmd": ""},
        {"pid": "400", "ppid": "300", "cmd": ""},
        {"pid": "300", "ppid": "0", "cmd": ""},
        {"pid": "999", "ppid": "1", "cmd": ""},  # unrelated
    ])
    assert sr._windows_own_tree_pids() == {"500", "400", "300"}


def test_stop_instance_denied_gate_kills_nothing(monkeypatch):
    calls = {"port_kills": [], "mcp_kills": []}

    monkeypatch.setattr(sr, "request_gate", lambda **k: {"decision": "denied", "reason": "compiling"})
    monkeypatch.setattr(sr, "kill_process_group", lambda pid, **k: calls["port_kills"].append(pid))
    monkeypatch.setattr(sr, "kill_pid", lambda pid, **k: calls["mcp_kills"].append(pid))
    result = sr.stop_instance(Inst())
    assert result["decision"] == "denied"
    assert calls["port_kills"] == [] and calls["mcp_kills"] == []
