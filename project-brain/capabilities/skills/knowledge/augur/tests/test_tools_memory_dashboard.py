"""Auto-generated importability test for tools_memory_dashboard."""
from __future__ import annotations

import sys
from pathlib import Path

SHARED_VAULT_ROOT = Path(__file__).resolve().parents[4]
if str(SHARED_VAULT_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_VAULT_ROOT))

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

SKILL_PATH = Path(__file__).resolve().parents[2] / "SKILL.md"
CAPABILITY_PATH = PROJECT_ROOT / "config" / "system" / "capability_exposure.yaml"


def test_tools_memory_dashboard_importable():
    """Verify that tools_memory_dashboard can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")
    assert mod is not None


def test_build_source_metadata_for_existing_file(tmp_path):
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")
    source = tmp_path / "MEMORY.md"
    source.write_text("| Date | Client | Type | Name | Description |\n", encoding="utf-8")

    metadata = mod._build_source_metadata(source, label="Curated memory", kind="file")

    assert metadata["label"] == "Curated memory"
    assert metadata["kind"] == "file"
    assert metadata["exists"] is True
    assert metadata["path"] == str(source)
    assert metadata["modifiedAt"]
    assert metadata["sizeBytes"] > 0


def test_build_source_metadata_for_missing_file(tmp_path):
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")
    source = tmp_path / "missing.md"

    metadata = mod._build_source_metadata(source, label="Missing source", kind="file")

    assert metadata == {
        "label": "Missing source",
        "kind": "file",
        "path": str(source),
        "exists": False,
        "modifiedAt": None,
        "sizeBytes": None,
    }


def test_build_stats_payload_preserves_dashboard_shape():
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")

    payload = mod._build_stats_payload(
        {
            "totalDecisions": 3,
            "totalPatterns": 2,
            "totalPreferences": 1,
            "dailyLogs": 4,
            "lastCurated": "2026-04-22",
            "recentDecisions": [],
            "categoryCounts": {"feedback": 3},
        },
        {"memory": {"exists": True}},
    )

    assert payload["totalDecisions"] == 3
    assert payload["categoryCounts"] == {"feedback": 3}
    assert payload["sources"] == {"memory": {"exists": True}}


def test_collect_memory_file_inventory_includes_vault_runtime_and_client_files(tmp_path):
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")

    mem_dir = tmp_path / "vault" / "memory"
    runtime_mem_dir = tmp_path / "runtime" / "memory"
    client_dir = tmp_path / "home" / ".codex"
    profile_file = tmp_path / "vault" / "wiki" / "profile-human-api.md"
    (mem_dir / "entries").mkdir(parents=True)
    (runtime_mem_dir / "daily").mkdir(parents=True)
    client_dir.mkdir(parents=True)
    profile_file.parent.mkdir(parents=True)

    (mem_dir / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")
    (mem_dir / "entries" / "codex-note.md").write_text("---\nname: note\n---\n", encoding="utf-8")
    (runtime_mem_dir / "daily" / "2026-05-13.md").write_text("# Daily\n", encoding="utf-8")
    (client_dir / "augur-memory.md").write_text("# Client\n", encoding="utf-8")
    (client_dir / "auth.json").write_text("{}", encoding="utf-8")
    (client_dir / "session_index.jsonl").write_text("{}", encoding="utf-8")
    (client_dir / "plugins" / "cache").mkdir(parents=True)
    (client_dir / "plugins" / "cache" / "plugin.json").write_text("{}", encoding="utf-8")
    profile_file.write_text("# Profile\n", encoding="utf-8")

    files = mod._collect_memory_file_inventory(
        mem_dir=mem_dir,
        runtime_mem_dir=runtime_mem_dir,
        profile_file=profile_file,
        client_memory_plan={
            "sources": {"codex": client_dir},
            "outputs": [{"client": "codex", "kind": "flat_index", "path": client_dir / "augur-memory.md"}],
        },
    )

    paths = {entry["path"] for entry in files}
    assert str(mem_dir / "MEMORY.md") in paths
    assert str(mem_dir / "entries" / "codex-note.md") in paths
    assert str(runtime_mem_dir / "daily" / "2026-05-13.md") in paths
    assert str(client_dir / "augur-memory.md") in paths
    assert str(client_dir / "session_index.jsonl") in paths
    assert str(client_dir / "auth.json") not in paths
    assert str(client_dir / "plugins" / "cache" / "plugin.json") not in paths
    assert str(profile_file) in paths
    assert len(paths) == len(files)


def test_parse_memory_entries_counts_section_based_curated_memory():
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")

    content = """# Augur Memory

*Last curated: 2026-04-23*

## Decisions

### Career
- **Ship Brain overview hardening**: Turn the hub home into a real brief. (2026-04-23)

### Workflow
- **Use page-by-page review loops**: Fix issues one page at a time. (2026-04-22)

## Learned Patterns

### Workflow Patterns
- **Observed Pattern**: Search quality improves when the query is topic-shaped. (2026-04-21)

## User Preferences

### Communication
- **Response style**: Keep the answer concise and direct. (2026-04-20)
"""

    entries = mod._parse_memory_entries(content)
    stats = mod._build_stats(entries, daily_logs=4, last_curated="2026-04-23")

    assert stats["totalDecisions"] == 2
    assert stats["totalPatterns"] == 1
    assert stats["totalPreferences"] == 1
    assert stats["dailyLogs"] == 4
    assert stats["lastCurated"] == "2026-04-23"
    assert stats["categoryCounts"] == {"career": 1, "workflow": 1}
    assert stats["recentDecisions"][0]["topic"] == "Ship Brain overview hardening"


def test_parse_last_curated_reads_memory_marker():
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")

    assert mod._parse_last_curated("# Augur Memory\n\n*Last curated: 2026-04-18*\n") == "2026-04-18"


def test_list_daily_logs_reads_runtime_markdown_files(tmp_path, monkeypatch):
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")

    daily_dir = tmp_path / "runtime" / "memory" / "daily"
    daily_dir.mkdir(parents=True)
    (daily_dir / "2026-04-21.md").write_text(
        "# Session Log: 2026-04-21\n\n## 18:56 - Decision\n**Decision**: Keep Brain pages flat.\n",
        encoding="utf-8",
    )
    (daily_dir / "2026-04-13.md").write_text(
        "# Session Log: 2026-04-13\n\n## 17:51 - User Preference\n**Preference**: Keep responses concise.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "get_runtime_dir", lambda: tmp_path / "runtime")

    logs = mod._list_daily_logs_from_runtime()

    assert [entry["date"] for entry in logs] == ["2026-04-21", "2026-04-13"]
    assert logs[0]["entryCount"] == 1
    assert logs[0]["preview"] == "Keep Brain pages flat."
    assert logs[0]["kindCounts"] == {"decision": 1}


def test_read_daily_log_uses_runtime_markdown_content(tmp_path, monkeypatch):
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")

    daily_dir = tmp_path / "runtime" / "memory" / "daily"
    daily_dir.mkdir(parents=True)
    log_path = daily_dir / "2026-04-21.md"
    log_path.write_text(
        "# Session Log: 2026-04-21\n\n## 18:56 - Decision\n**Decision**: Keep Brain pages flat.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "get_runtime_dir", lambda: tmp_path / "runtime")

    payload = mod._read_daily_log_from_runtime("2026-04-21")

    assert payload["date"] == "2026-04-21"
    assert payload["content"].startswith("# Session Log: 2026-04-21")
    assert payload["size"] == 1
    assert payload["preview"] == "Keep Brain pages flat."
    assert payload["kindCounts"] == {"decision": 1}


def test_daily_log_tools_are_available_to_dashboard_mcp_runtime():
    import yaml
    from src.lib.capabilities.export_filter import (
        allowed_mcp_runtime_tool_names,
        reset_export_filter_cache,
    )

    required_tools = {
        "knowledge-memory-daily-logs",
        "knowledge-memory-daily-logs-read",
        "knowledge-memory-daily-logs-open",
    }

    _, skill_yaml, _ = SKILL_PATH.read_text(encoding="utf-8").split("---\n", 2)
    skill_meta = yaml.safe_load(skill_yaml)
    assert required_tools <= set(skill_meta["x-augur-mcp-tools"])

    capability = yaml.safe_load(CAPABILITY_PATH.read_text(encoding="utf-8"))
    capabilities = capability["capabilities"]
    for tool in required_tools:
        record = capabilities[f"mcp-tool:{tool}"]
        assert record["classification_status"] == "approved"
        assert record["preferred_client"] == "dashboard"
        assert record["primary_surface"] == "mcp via dashboard"

    reset_export_filter_cache()
    allowed = allowed_mcp_runtime_tool_names(
        sorted(required_tools),
        target="dashboard-augur-wt-smoke",
    )
    assert required_tools <= allowed
