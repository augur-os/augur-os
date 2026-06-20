from src.lib.mcp_runtime_inventory import (
    enrich_mcp_server_entries_with_runtime,
    parse_augur_mcp_processes,
)


def test_parse_augur_mcp_processes_maps_core_framework_and_bundle_servers() -> None:
    ps_output = """
101 1 /repo/.venv/bin/python -m augur_core --client-id codex
102 1 /repo/.venv/bin/python -m augur_framework --client-id dashboard-Augur-p1
103 1 /repo/.venv/bin/python -m augur_shared.bundle_server ingest
104 1 /repo/.venv/bin/python -m unrelated_service
"""

    processes = parse_augur_mcp_processes(ps_output)

    assert [(p.pid, p.server_id, p.client_id, p.bundle) for p in processes] == [
        (101, "augur-core", "codex", ""),
        (102, "augur-framework", "dashboard-Augur-p1", ""),
        (103, "augur-ingest", "", "ingest"),
    ]


def test_enrich_mcp_server_entries_marks_running_configured_servers() -> None:
    entries = [
        {
            "id": "augur-core",
            "title": "augur-core",
            "status": "configured",
            "tier": "project-tier",
        }
    ]
    ps_output = "101 1 /repo/.venv/bin/python -m augur_core --client-id codex\n"

    enriched = enrich_mcp_server_entries_with_runtime(entries, ps_output=ps_output)

    assert len(enriched) == 1
    assert enriched[0]["runtime_status"] == "configured-running"
    assert enriched[0]["runtime_pids"] == "101"
    assert enriched[0]["running_clients"] == "codex"
    assert enriched[0]["runtime_process_count"] == 1
    assert enriched[0]["stale_runtime"] is False


def test_enrich_mcp_server_entries_marks_configured_stopped_servers() -> None:
    entries = [
        {
            "id": "augur-vault",
            "title": "augur-vault",
            "status": "configured",
            "tier": "vault-tier",
        }
    ]

    enriched = enrich_mcp_server_entries_with_runtime(entries, ps_output="")

    assert len(enriched) == 1
    assert enriched[0]["runtime_status"] == "configured-stopped"
    assert enriched[0]["runtime_pids"] == ""
    assert enriched[0]["running_clients"] == ""
    assert enriched[0]["runtime_process_count"] == 0
    assert enriched[0]["stale_runtime"] is False


def test_enrich_mcp_server_entries_appends_stale_runtime_rows() -> None:
    entries = [
        {
            "id": "augur-core",
            "title": "augur-core",
            "status": "configured",
            "tier": "project-tier",
        }
    ]
    ps_output = """
101 1 /repo/.venv/bin/python -m augur_core --client-id codex
202 1 /repo/.venv/bin/python -m augur_shared.bundle_server apple
"""

    enriched = enrich_mcp_server_entries_with_runtime(entries, ps_output=ps_output)

    stale = [entry for entry in enriched if entry["id"] == "augur-apple"]
    assert len(stale) == 1
    assert stale[0]["status"] == "stale-runtime"
    assert stale[0]["runtime_status"] == "stale-running"
    assert stale[0]["runtime_pids"] == "202"
    assert stale[0]["runtime_process_count"] == 1
    assert stale[0]["stale_runtime"] is True
    assert "not declared" in stale[0]["description"]
