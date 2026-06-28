import src.lib.dev_build as db


class _Inst:
    """Minimal stand-in for AugurDashboardInstance."""

    def __init__(self, kind="main", port=3000):
        self.kind = kind
        self.instance_id = kind
        self.dashboard_port = port
        self.mcp_port = 8080
        self.project_root = None


def _wire(monkeypatch, inst, *, build_rc=0, stop=None):
    """Wire the mockable seams; return a dict recording build calls + the prod flag."""
    rec = {"build": 0, "prod": None}
    monkeypatch.setattr(db, "resolve_target", lambda **k: inst)
    monkeypatch.setattr(db, "_preflight_ok", lambda i: True)
    monkeypatch.setattr(db, "_stop_instance", lambda i: stop or {"decision": "granted", "recycled_mcp_pids": ["200"]})
    monkeypatch.setattr(db, "_run_build", lambda i: rec.__setitem__("build", 1) or build_rc)
    monkeypatch.setattr(db, "_start_server", lambda i, *, prod=False: rec.__setitem__("prod", prod))
    monkeypatch.setattr(db, "_poll_ready", lambda i, timeout=90: True)
    monkeypatch.setattr(db, "_fresh_mcp_present", lambda i, prev: True)
    monkeypatch.setattr(db, "_sleep", lambda s: None)
    return rec


def test_start_server_captures_output_to_log_not_devnull(monkeypatch, tmp_path):
    """Regression: the detached dashboard server's stdout/stderr must be captured
    to a real log file (not DEVNULL). Routing to DEVNULL silently discarded a
    production /login 500 stack trace and forced filesystem-level forensics."""
    import subprocess

    inst = _Inst(kind="main", port=3000)
    monkeypatch.setattr(db, "get_logs_dir", lambda: tmp_path)
    monkeypatch.setattr(db, "get_project_root", lambda: tmp_path)
    captured: dict = {}
    monkeypatch.setattr(db.subprocess, "Popen", lambda cmd, **kw: captured.update(cmd=cmd, kw=kw))
    db._start_server(inst, prod=True)

    stdout = captured["kw"]["stdout"]
    assert stdout is not subprocess.DEVNULL, "server output must not be discarded"
    assert hasattr(stdout, "write"), "stdout must be a real writable file object"
    assert captured["kw"]["stderr"] is subprocess.STDOUT, "stderr must merge into the log"
    assert (tmp_path / "dashboard.3000.log").exists(), "log file must be created"


def test_main_always_production(monkeypatch, tmp_path):
    """The main :3000 dashboard ALWAYS builds + serves prod (ADR-787), even by default."""
    inst = _Inst(kind="main", port=3000)
    inst.project_root = tmp_path
    rec = _wire(monkeypatch, inst)
    result = db.run_dev_build()  # full_build defaults False
    assert result["ok"] is True and result["port"] == 3000
    assert result["mode"] == "production"
    assert rec["build"] == 1  # main builds unconditionally
    assert rec["prod"] is True  # served via next start, not the dev server


def test_worktree_default_runs_dev_without_build(monkeypatch, tmp_path):
    """A worktree on its own port runs the Turbopack dev server; default skips the prod build."""
    inst = _Inst(kind="worktree", port=3003)
    inst.project_root = tmp_path
    rec = _wire(monkeypatch, inst)
    result = db.run_dev_build()
    assert result["ok"] is True and result["port"] == 3003
    assert result["mode"] == "dev"
    assert rec["build"] == 0  # turbopack recompiles live; no production build
    assert rec["prod"] is False  # dev mode, not the production serve


def test_worktree_full_build_runs_production_build(monkeypatch, tmp_path):
    """full_build=True forces a production build even for a worktree (opt-in)."""
    inst = _Inst(kind="worktree", port=3003)
    inst.project_root = tmp_path
    rec = _wire(monkeypatch, inst)
    result = db.run_dev_build(full_build=True)
    assert result["ok"] is True
    assert rec["build"] == 1


def test_denied_gate_does_not_force(monkeypatch, tmp_path):
    inst = _Inst(kind="main", port=3000)
    inst.project_root = tmp_path
    rec = _wire(monkeypatch, inst, stop={"decision": "denied", "reason": "compiling"})
    result = db.run_dev_build(max_gate_retries=2)
    assert result["ok"] is False and "denied" in result["reason"]
    assert rec["build"] == 0  # never built past a denied gate


def test_refuses_when_preflight_fails(monkeypatch, tmp_path):
    """If the dashboard cannot start (preflight fails), do NOT stop it — never strand :3000."""
    inst = _Inst(kind="main", port=3000)
    inst.project_root = tmp_path
    monkeypatch.setattr(db, "resolve_target", lambda **k: inst)
    monkeypatch.setattr(db, "_preflight_ok", lambda i: False)
    stopped = {"n": 0}
    monkeypatch.setattr(
        db,
        "_stop_instance",
        lambda i: stopped.__setitem__("n", 1) or {"decision": "granted", "recycled_mcp_pids": []},
    )
    result = db.run_dev_build()
    assert result["ok"] is False
    assert "preflight" in result["reason"]
    assert stopped["n"] == 0  # never stopped the dashboard it could not restart
