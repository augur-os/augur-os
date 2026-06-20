import src.lib.dev_build as db


def test_run_dev_build_happy_path(monkeypatch, tmp_path):
    class Inst:
        instance_id = "main"
        dashboard_port = 3000
        mcp_port = 8080
        project_root = tmp_path

    monkeypatch.setattr(db, "resolve_target", lambda **k: Inst())
    monkeypatch.setattr(db, "_preflight_ok", lambda inst: True)
    monkeypatch.setattr(db, "_stop_instance", lambda inst: {"decision": "granted", "recycled_mcp_pids": ["200"]})
    monkeypatch.setattr(db, "_run_build", lambda inst: 0)
    monkeypatch.setattr(db, "_start_server", lambda inst: None)
    monkeypatch.setattr(db, "_poll_ready", lambda inst, timeout=90: True)
    monkeypatch.setattr(db, "_fresh_mcp_present", lambda inst, prev: True)
    result = db.run_dev_build()
    assert result["ok"] is True and result["port"] == 3000
    assert result["rebuilt"] is True and result["mcp_recycled"] is True


def test_run_dev_build_denied_gate_does_not_force(monkeypatch, tmp_path):
    class Inst:
        instance_id = "main"
        dashboard_port = 3000
        mcp_port = 8080
        project_root = tmp_path

    monkeypatch.setattr(db, "resolve_target", lambda **k: Inst())
    monkeypatch.setattr(db, "_preflight_ok", lambda inst: True)
    monkeypatch.setattr(db, "_stop_instance", lambda inst: {"decision": "denied", "reason": "compiling"})
    called = {"build": 0}
    monkeypatch.setattr(db, "_run_build", lambda inst: called.__setitem__("build", 1) or 0)
    monkeypatch.setattr(db, "_sleep", lambda s: None)
    result = db.run_dev_build(max_gate_retries=2)
    assert result["ok"] is False and "denied" in result["reason"]
    assert called["build"] == 0  # never built past a denied gate


def test_run_dev_build_default_skips_production_build(monkeypatch, tmp_path):
    class Inst:
        instance_id = "main"
        dashboard_port = 3000
        mcp_port = 8080
        project_root = tmp_path

    monkeypatch.setattr(db, "resolve_target", lambda **k: Inst())
    monkeypatch.setattr(db, "_preflight_ok", lambda inst: True)
    monkeypatch.setattr(db, "_stop_instance", lambda inst: {"decision": "granted", "recycled_mcp_pids": ["200"]})
    called = {"build": 0}
    monkeypatch.setattr(db, "_run_build", lambda inst: called.__setitem__("build", 1) or 0)
    monkeypatch.setattr(db, "_start_server", lambda inst: None)
    monkeypatch.setattr(db, "_poll_ready", lambda inst, timeout=90: True)
    monkeypatch.setattr(db, "_fresh_mcp_present", lambda inst, prev: True)
    result = db.run_dev_build()  # full_build defaults False
    assert result["ok"] is True and result["rebuilt"] is True
    assert called["build"] == 0  # default refresh never runs the production build


def test_run_dev_build_full_build_runs_production_build(monkeypatch, tmp_path):
    class Inst:
        instance_id = "main"
        dashboard_port = 3000
        mcp_port = 8080
        project_root = tmp_path

    monkeypatch.setattr(db, "resolve_target", lambda **k: Inst())
    monkeypatch.setattr(db, "_preflight_ok", lambda inst: True)
    monkeypatch.setattr(db, "_stop_instance", lambda inst: {"decision": "granted", "recycled_mcp_pids": ["200"]})
    called = {"build": 0}
    monkeypatch.setattr(db, "_run_build", lambda inst: called.__setitem__("build", 1) or 0)
    monkeypatch.setattr(db, "_start_server", lambda inst: None)
    monkeypatch.setattr(db, "_poll_ready", lambda inst, timeout=90: True)
    monkeypatch.setattr(db, "_fresh_mcp_present", lambda inst, prev: True)
    result = db.run_dev_build(full_build=True)
    assert result["ok"] is True and result["rebuilt"] is True
    assert called["build"] == 1  # opt-in production build ran


def test_run_dev_build_refuses_when_preflight_fails(monkeypatch, tmp_path):
    """If the dashboard cannot start (preflight fails), do NOT stop it — never strand :3000."""

    class Inst:
        instance_id = "main"
        dashboard_port = 3000
        mcp_port = 8080
        project_root = tmp_path

    monkeypatch.setattr(db, "resolve_target", lambda **k: Inst())
    monkeypatch.setattr(db, "_preflight_ok", lambda inst: False)
    stopped = {"n": 0}
    monkeypatch.setattr(
        db,
        "_stop_instance",
        lambda inst: stopped.__setitem__("n", 1) or {"decision": "granted", "recycled_mcp_pids": []},
    )
    result = db.run_dev_build()
    assert result["ok"] is False
    assert "preflight" in result["reason"]
    assert stopped["n"] == 0  # never stopped the dashboard it could not restart
