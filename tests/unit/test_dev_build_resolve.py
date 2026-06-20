import src.lib.dev_build as db


def test_resolve_target_returns_main_instance(monkeypatch, tmp_path):
    class FakeInstance:
        instance_id = "main"
        kind = "main"
        dashboard_port = 3000
        mcp_port = 8080
        project_root = tmp_path
        name = "main"

    monkeypatch.setattr(db, "resolve_dashboard_instance", lambda *a, **k: FakeInstance())
    target = db.resolve_target(project_root=tmp_path)
    assert target.dashboard_port == 3000
    assert target.instance_id == "main"
    assert target.project_root == tmp_path
