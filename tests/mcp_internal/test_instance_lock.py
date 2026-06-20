from src.mcp.augur_shared.instance_lock import _resolve_lock_client_id


def test_resolve_lock_client_id_opencode_uses_per_process_lock(monkeypatch):
    monkeypatch.setattr("os.getpid", lambda: 4242)

    lock_id = _resolve_lock_client_id(client_id="opencode", transport="stdio", port=None)

    assert lock_id == "opencode-pid4242"
