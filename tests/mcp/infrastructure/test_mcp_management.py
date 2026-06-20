"""Behavior tests for the MCP management tool surface.

Covers ``src/mcp/augur_framework/tools/infrastructure/mcp_management.py``:

* Pure helpers: ``_map_group_to_category``, ``_categorize_tool``,
  ``_get_category_description``.
* Registered tool behavior captured via a fake FastMCP, exercising the
  happy path AND the error path of each tool, with all external services
  (subprocess, context manager, diagnostics helpers, config dir) mocked.

External services are never started; config IO uses ``tmp_path``.
"""

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

from src.mcp.augur_framework.tools.infrastructure import mcp_management as mm

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class CapturingMCP:
    """Minimal FastMCP stand-in that records registered tool callables by name."""

    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, *args, **kwargs):
        name = kwargs.get("name")
        if name is None and args and isinstance(args[0], str):
            name = args[0]

        def decorator(func):
            self.tools[name or func.__name__] = func
            return func

        return decorator


class RecordingMetrics:
    """Captures track_tool calls so tests can assert telemetry fires."""

    def __init__(self) -> None:
        self.calls: list[tuple[tuple, dict]] = []

    def track_tool(self, *args, **kwargs) -> None:
        self.calls.append((args, kwargs))


@dataclass
class FakeCompletedProcess:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def _register() -> tuple[CapturingMCP, RecordingMetrics]:
    """Register all tools against fresh doubles and return them."""
    mcp = CapturingMCP()
    metrics = RecordingMetrics()
    # interceptor is identity — we test the tool bodies, not interception.
    mm.register_all_mcp_management_tools(mcp, lambda f: f, metrics)
    return mcp, metrics


def _call(tool):
    """Run an async tool callable to completion and parse its JSON result."""

    async def runner():
        return await tool()

    return runner


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


class TestMapGroupToCategory:
    @pytest.mark.parametrize(
        "group,expected",
        [
            ("BRAIN_DATA", "context"),
            ("BRAIN_INTEL", "context"),
            ("BRAIN_BUGS", "diagnostics"),
            ("WORKFORCE_CHAINS", "execution"),
            ("WORKFORCE_SELF_UPDATE", "self-update"),
            ("SETTINGS_MGMT", "settings"),
            ("core_tools", "core"),
        ],
    )
    def test_known_groups_map_to_categories(self, group, expected):
        assert mm._map_group_to_category(group) == expected

    def test_unknown_group_falls_back_to_core(self):
        assert mm._map_group_to_category("TOTALLY_UNKNOWN") == "core"

    def test_empty_group_falls_back_to_core(self):
        assert mm._map_group_to_category("") == "core"


class TestCategorizeTool:
    @pytest.mark.parametrize(
        "tool_name,expected",
        [
            ("run-skill", "execution"),
            ("execute-chain", "execution"),
            ("send-ide-prompt", "agents"),
            ("list-agents", "agents"),
            ("doctor-check", "domain"),
            ("schedule-interview", "domain"),
            ("switch-mcp-context", "context"),
            ("search-documents", "context"),
            ("background-queue", "background-jobs"),
            ("task-runner", "background-jobs"),
            ("run-diagnostic", "diagnostics"),
            ("rollback-change", "rollback"),
            ("train-model", "training"),
            ("self-update-now", "self-update"),
            ("totally-unrelated-thing", "core"),
        ],
    )
    def test_keyword_routing(self, tool_name, expected):
        assert mm._categorize_tool(tool_name) == expected

    def test_categorization_is_case_insensitive(self):
        assert mm._categorize_tool("RUN-SKILL") == "execution"

    def test_earlier_rules_shadow_later_ones(self):
        # The categorizer is an ordered keyword scan: the first matching block
        # wins. "mcp" (context) is checked before "diagnostic", and the domain
        # "job" rule is checked before the background-jobs "job" rule, so these
        # names do NOT land in the category their suffix might suggest.
        assert mm._categorize_tool("get-mcp-diagnostics") == "context"
        assert mm._categorize_tool("enqueue-background-job") == "domain"

    def test_skill_heuristic_failure_is_swallowed(self, monkeypatch):
        """A broken skill registry lookup must not crash categorization."""
        import src.mcp.augur_shared.skill_registry as sr

        def boom(_token):
            raise RuntimeError("registry offline")

        monkeypatch.setattr(sr, "is_known_skill", boom)
        # No domain keyword -> would reach the heuristic -> exception swallowed.
        assert mm._categorize_tool("zzz-token") == "core"


class TestGetCategoryDescription:
    def test_known_category_returns_specific_text(self):
        assert mm._get_category_description("core") == "Core system tools for basic operations"

    def test_unknown_category_uses_titlecased_fallback(self):
        assert mm._get_category_description("weird") == "Weird tools"

    def test_all_documented_categories_have_specific_descriptions(self):
        # Each known category resolves to a curated string, not the generic
        # "<Title> tools" fallback used for unknown categories.
        for cat in [
            "core",
            "context",
            "execution",
            "agents",
            "domain",
            "background-jobs",
            "diagnostics",
            "rollback",
            "training",
            "self-update",
            "settings",
        ]:
            desc = mm._get_category_description(cat)
            assert desc, f"{cat} has no description"
            assert desc != f"{cat.title()} tools", f"{cat} fell through to generic fallback"


# ---------------------------------------------------------------------------
# Registration surface
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_all_expected_tools_registered(self):
        mcp, _ = _register()
        assert set(mcp.tools) == {
            "test-mcp-connection",
            "list-mcp-tools",
            "configure-mcp-server",
            "switch-mcp-context",
            "preload-mcp-context",
            "get-mcp-context-stats",
            "discover-augur",
            "get-mcp-diagnostics",
            "get-api-route-stats",
        }

    def test_base_registration_only_adds_base_tools(self):
        mcp = CapturingMCP()
        mm.register_mcp_management_tools(mcp, lambda f: f, RecordingMetrics())
        assert set(mcp.tools) == {"test-mcp-connection", "list-mcp-tools"}


# ---------------------------------------------------------------------------
# test-mcp-connection
# ---------------------------------------------------------------------------


class TestTestMcpConnection:
    def test_reports_success_with_timestamp(self):
        mcp, metrics = _register()
        result = json.loads(asyncio.run(mcp.tools["test-mcp-connection"]()))
        assert result["ok"] is True
        assert result["success"] is True
        assert "MCP server connection successful" in result["message"]
        assert result["timestamp"]
        assert metrics.calls == [(("test_mcp_connection",), {})]


# ---------------------------------------------------------------------------
# list-mcp-tools
# ---------------------------------------------------------------------------


def _write_yaml_config(config_dir: Path, payload: dict) -> None:
    (config_dir / "dashboard").mkdir(parents=True, exist_ok=True)
    (config_dir / "dashboard" / "mcp_tool_groups.yaml").write_text(yaml.safe_dump(payload))


class TestListMcpTools:
    def test_list_action_flattens_core_and_groups(self, monkeypatch, tmp_path):
        _write_yaml_config(
            tmp_path,
            {
                "core_tools": ["ping", "status"],
                "tool_groups": {
                    "BRAIN_DATA": ["search-documents"],
                    "WORKFORCE_CHAINS": ["run-chain"],
                },
            },
        )
        monkeypatch.setattr(mm, "get_config_dir", lambda: tmp_path)
        mcp, _ = _register()

        result = json.loads(asyncio.run(mcp.tools["list-mcp-tools"](action="list")))
        names = [t["name"] for t in result["tools"]]
        assert names == ["ping", "status", "search-documents", "run-chain"]
        cats = {t["name"]: t["category"] for t in result["tools"]}
        assert cats == {
            "ping": "core",
            "status": "core",
            "search-documents": "context",
            "run-chain": "execution",
        }

    def test_inline_comments_are_stripped_from_tool_names(self, monkeypatch, tmp_path):
        _write_yaml_config(
            tmp_path,
            {"tool_groups": {"BRAIN_DATA": ["search-documents          # RAG search"]}},
        )
        monkeypatch.setattr(mm, "get_config_dir", lambda: tmp_path)
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["list-mcp-tools"]()))
        assert [t["name"] for t in result["tools"]] == ["search-documents"]

    def test_duplicate_tool_across_core_and_group_is_deduped(self, monkeypatch, tmp_path):
        _write_yaml_config(
            tmp_path,
            {
                "core_tools": ["search-documents"],
                "tool_groups": {"BRAIN_DATA": ["search-documents"]},
            },
        )
        monkeypatch.setattr(mm, "get_config_dir", lambda: tmp_path)
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["list-mcp-tools"]()))
        assert [t["name"] for t in result["tools"]] == ["search-documents"]
        # core_tools wins the category assignment.
        assert result["tools"][0]["category"] == "core"

    def test_malformed_entries_are_skipped(self, monkeypatch, tmp_path):
        # Empty strings, None, non-str, comment-only entries, and non-list
        # groups are all dropped. (Whitespace-only entries are covered
        # separately below — they currently leak through.)
        _write_yaml_config(
            tmp_path,
            {
                "core_tools": ["valid", "", None, 123],
                "tool_groups": {
                    "BRAIN_DATA": ["good", "", "#only-comment"],
                    "BROKEN": "not-a-list",
                },
            },
        )
        monkeypatch.setattr(mm, "get_config_dir", lambda: tmp_path)
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["list-mcp-tools"]()))
        assert [t["name"] for t in result["tools"]] == ["valid", "good"]

    def test_whitespace_only_group_entry_leaks_through(self, monkeypatch, tmp_path):
        # Edge case / latent quirk: a whitespace-only group entry has no "#",
        # so the comment-stripping (which also trims) is skipped, and a
        # non-empty whitespace string is truthy — so it survives the filter
        # unstripped. Pinned so a future cleanup is a deliberate change.
        _write_yaml_config(tmp_path, {"tool_groups": {"BRAIN_DATA": ["good", "  "]}})
        monkeypatch.setattr(mm, "get_config_dir", lambda: tmp_path)
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["list-mcp-tools"]()))
        assert [t["name"] for t in result["tools"]] == ["good", "  "]

    def test_summary_action_builds_rich_structure(self, monkeypatch, tmp_path):
        _write_yaml_config(
            tmp_path,
            {
                "core_tools": ["ping"],
                "tool_groups": {"WORKFORCE_CHAINS": ["run-chain"]},
            },
        )
        monkeypatch.setattr(mm, "get_config_dir", lambda: tmp_path)
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["list-mcp-tools"](action="summary")))

        assert result["total_tools"] == 2
        assert result["enabled_tools"] == 2
        assert result["active_preset"] == "auto"
        assert set(result["presets"]) == {"minimal", "standard", "full", "auto"}
        # categories aggregate per-tool counts
        assert result["categories"]["core"]["tools"] == ["ping"]
        assert result["categories"]["execution"]["tools"] == ["run-chain"]
        assert result["categories"]["core"]["tools_total"] == 1
        # tools_config map mirrors the flat list
        assert set(result["tools_config"]) == {"ping", "run-chain"}

    def test_summary_with_empty_config_uses_core_fallback_block(self, monkeypatch, tmp_path):
        # No config file present at all -> empty groups -> fallback core category.
        (tmp_path / "dashboard").mkdir()
        monkeypatch.setattr(mm, "get_config_dir", lambda: tmp_path)
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["list-mcp-tools"](action="summary")))
        assert result["total_tools"] == 0
        assert list(result["categories"]) == ["core"]
        assert result["categories"]["core"]["description"] == "Core system tools"

    def test_json_config_takes_precedence_over_yaml(self, monkeypatch, tmp_path):
        gen = tmp_path / "dashboard" / "generated"
        gen.mkdir(parents=True)
        (gen / "assembled_tool_config.json").write_text(json.dumps({"core_tools": ["from-json"], "tool_groups": {}}))
        # YAML present but should be ignored.
        _write_yaml_config(tmp_path, {"core_tools": ["from-yaml"], "tool_groups": {}})
        monkeypatch.setattr(mm, "get_config_dir", lambda: tmp_path)
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["list-mcp-tools"]()))
        assert [t["name"] for t in result["tools"]] == ["from-json"]

    def test_non_dict_config_is_treated_as_empty(self, monkeypatch, tmp_path):
        (tmp_path / "dashboard").mkdir()
        (tmp_path / "dashboard" / "mcp_tool_groups.yaml").write_text("- just\n- a\n- list\n")
        monkeypatch.setattr(mm, "get_config_dir", lambda: tmp_path)
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["list-mcp-tools"]()))
        assert result["tools"] == []

    def test_error_path_returns_error_and_empty_tools(self, monkeypatch):
        def boom():
            raise RuntimeError("config boom")

        monkeypatch.setattr(mm, "get_config_dir", boom)
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["list-mcp-tools"]()))
        assert result["error"] == "config boom"
        assert result["tools"] == []


# ---------------------------------------------------------------------------
# configure-mcp-server
# ---------------------------------------------------------------------------


class TestConfigureMcpServer:
    def test_success_returns_ide_in_message(self, monkeypatch):
        monkeypatch.setattr(mm, "subprocess_run", lambda *a, **k: FakeCompletedProcess(0, "done", ""))
        mcp, metrics = _register()
        result = json.loads(asyncio.run(mcp.tools["configure-mcp-server"](ide="vscode")))
        assert result == {
            "ok": True,
            "success": True,
            "message": "MCP server configured for vscode",
            "ide": "vscode",
        }
        assert metrics.calls == [(("configure_mcp_server",), {})]

    def test_nonzero_exit_with_stderr_is_failure(self, monkeypatch):
        monkeypatch.setattr(mm, "subprocess_run", lambda *a, **k: FakeCompletedProcess(1, "", "boom error"))
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["configure-mcp-server"]()))
        assert result["ok"] is False
        assert result["success"] is False
        assert result["error"] == "boom error"

    def test_warning_only_stderr_is_treated_as_success(self, monkeypatch):
        monkeypatch.setattr(
            mm,
            "subprocess_run",
            lambda *a, **k: FakeCompletedProcess(1, "", "Warning: deprecated flag"),
        )
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["configure-mcp-server"]()))
        assert result["ok"] is True
        assert result["ide"] == "cursor"

    def test_subprocess_exception_is_caught(self, monkeypatch):
        def boom(*a, **k):
            raise OSError("python3 not found")

        monkeypatch.setattr(mm, "subprocess_run", boom)
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["configure-mcp-server"]()))
        assert result["success"] is False
        assert "python3 not found" in result["error"]
        assert result["statusCode"] == 200


# ---------------------------------------------------------------------------
# Context-manager backed tools
# ---------------------------------------------------------------------------


class FakeContextManager:
    def __init__(self) -> None:
        self.switch_calls: list[tuple[str, bool]] = []
        self.preload_calls: list[str] = []

    async def switch_context(self, target_page, preloaded=False):
        self.switch_calls.append((target_page, preloaded))
        return {"success": True, "loaded_page": target_page, "preloaded": preloaded}

    async def preload_context(self, target_page):
        self.preload_calls.append(target_page)

    def get_stats(self):
        return {"switches": 5, "cache_hits": 2}


class TestSwitchMcpContext:
    def test_delegates_to_context_manager(self, monkeypatch):
        fake = FakeContextManager()
        import src.mcp.augur_shared.context_manager as cm

        monkeypatch.setattr(cm, "get_context_manager", lambda mcp: fake)
        mcp, metrics = _register()
        result = json.loads(asyncio.run(mcp.tools["switch-mcp-context"](current_page="/brain", preloaded=True)))
        assert result["success"] is True
        assert result["loaded_page"] == "/brain"
        assert fake.switch_calls == [("/brain", True)]
        assert metrics.calls and metrics.calls[0][0] == ("switch_mcp_context",)

    def test_error_path_returns_page_and_status(self, monkeypatch):
        import src.mcp.augur_shared.context_manager as cm

        def boom(mcp):
            raise RuntimeError("ctx offline")

        monkeypatch.setattr(cm, "get_context_manager", boom)
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["switch-mcp-context"](current_page="/x")))
        assert result["success"] is False
        assert result["error"] == "ctx offline"
        assert result["current_page"] == "/x"
        assert result["statusCode"] == 200


class TestPreloadMcpContext:
    def test_success_returns_preloaded_message(self, monkeypatch):
        fake = FakeContextManager()
        import src.mcp.augur_shared.context_manager as cm

        monkeypatch.setattr(cm, "get_context_manager", lambda mcp: fake)
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["preload-mcp-context"](target_page="/dev")))
        assert result["success"] is True
        assert result["target_page"] == "/dev"
        assert fake.preload_calls == ["/dev"]

    def test_error_path_returns_target_page(self, monkeypatch):
        import src.mcp.augur_shared.context_manager as cm

        def boom(mcp):
            raise RuntimeError("nope")

        monkeypatch.setattr(cm, "get_context_manager", boom)
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["preload-mcp-context"](target_page="/dev")))
        assert result["success"] is False
        assert result["target_page"] == "/dev"
        assert result["statusCode"] == 200


class TestGetMcpContextStats:
    def test_returns_stats_from_manager(self, monkeypatch):
        import src.mcp.augur_shared.context_manager as cm

        monkeypatch.setattr(cm, "get_context_manager", lambda mcp: FakeContextManager())
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["get-mcp-context-stats"]()))
        assert result == {"switches": 5, "cache_hits": 2}

    def test_error_path_returns_error_only(self, monkeypatch):
        import src.mcp.augur_shared.context_manager as cm

        def boom(mcp):
            raise RuntimeError("stats unavailable")

        monkeypatch.setattr(cm, "get_context_manager", boom)
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["get-mcp-context-stats"]()))
        assert result == {"error": "stats unavailable"}


# ---------------------------------------------------------------------------
# discover-augur
# ---------------------------------------------------------------------------


class TestDiscoverAugur:
    def test_returns_assembled_manifest(self, monkeypatch, tmp_path):
        import src.mcp.augur_framework.tools.domain.discovery as discovery
        import src.mcp.augur_shared.config as cfg

        captured = {}

        def fake_assemble(runtime_dir, hub=None, tier=None, session_id=None):
            captured.update(runtime_dir=runtime_dir, hub=hub, tier=tier, session_id=session_id)
            return {"skills": ["a", "b"], "hub": hub}

        monkeypatch.setattr(discovery, "assemble_manifest", fake_assemble)
        monkeypatch.setattr(cfg, "get_runtime_dir", lambda: tmp_path)
        mcp, metrics = _register()
        result = json.loads(asyncio.run(mcp.tools["discover-augur"](tier="public", hub="brain")))
        assert result["skills"] == ["a", "b"]
        assert result["hub"] == "brain"
        assert captured["hub"] == "brain"
        assert captured["tier"] == "public"
        assert captured["runtime_dir"] == tmp_path
        assert captured["session_id"].startswith("mcp-")
        assert metrics.calls[0] == (("discover_augur",), {"hub": "brain", "tier": "public"})

    def test_error_path_returns_error_envelope(self, monkeypatch):
        import src.mcp.augur_framework.tools.domain.discovery as discovery

        def boom(*a, **k):
            raise RuntimeError("manifest failed")

        monkeypatch.setattr(discovery, "assemble_manifest", boom)
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["discover-augur"]()))
        assert result["error"] == "manifest failed"
        assert result["statusCode"] == 200


# ---------------------------------------------------------------------------
# get-mcp-diagnostics
# ---------------------------------------------------------------------------


class TestGetMcpDiagnostics:
    def test_passes_input_flags_to_summary_builder(self, monkeypatch):
        captured = {}

        def fake_summary(*, include_processes, include_configs, project_root):
            captured.update(
                include_processes=include_processes,
                include_configs=include_configs,
                project_root=project_root,
            )
            return {"status": "healthy"}

        monkeypatch.setattr(mm, "build_mcp_diagnostics_summary", fake_summary)
        mcp, _ = _register()
        params = mm.GetMcpDiagnosticsInput(include_processes=False, include_configs=True)
        result = json.loads(asyncio.run(mcp.tools["get-mcp-diagnostics"](params=params)))
        assert result == {"status": "healthy"}
        assert captured["include_processes"] is False
        assert captured["include_configs"] is True
        assert isinstance(captured["project_root"], Path)

    def test_defaults_include_processes_and_configs(self, monkeypatch):
        captured = {}

        def fake_summary(*, include_processes, include_configs, project_root):
            captured.update(processes=include_processes, configs=include_configs)
            return {}

        monkeypatch.setattr(mm, "build_mcp_diagnostics_summary", fake_summary)
        mcp, _ = _register()
        asyncio.run(mcp.tools["get-mcp-diagnostics"]())
        assert captured == {"processes": True, "configs": True}

    def test_error_path_returns_error(self, monkeypatch):
        def boom(**k):
            raise RuntimeError("diag failed")

        monkeypatch.setattr(mm, "build_mcp_diagnostics_summary", boom)
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["get-mcp-diagnostics"]()))
        assert result == {"error": "diag failed"}


# ---------------------------------------------------------------------------
# get-api-route-stats
# ---------------------------------------------------------------------------


class TestGetApiRouteStats:
    def test_returns_route_counts(self, monkeypatch):
        monkeypatch.setattr(mm, "count_api_routes", lambda root: {"total": 17})
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["get-api-route-stats"]()))
        assert result == {"total": 17}

    def test_error_path_returns_error(self, monkeypatch):
        def boom(root):
            raise RuntimeError("route scan failed")

        monkeypatch.setattr(mm, "count_api_routes", boom)
        mcp, _ = _register()
        result = json.loads(asyncio.run(mcp.tools["get-api-route-stats"]()))
        assert result == {"error": "route scan failed"}


# ---------------------------------------------------------------------------
# Pydantic input models
# ---------------------------------------------------------------------------


class TestInputModels:
    def test_diagnostics_input_defaults(self):
        params = mm.GetMcpDiagnosticsInput()
        assert params.include_processes is True
        assert params.include_configs is True

    def test_diagnostics_input_forbids_extra_fields(self):
        with pytest.raises(Exception):
            mm.GetMcpDiagnosticsInput(unexpected_field=True)

    def test_api_route_stats_input_forbids_extra_fields(self):
        with pytest.raises(Exception):
            mm.GetApiRouteStatsInput(extra="nope")
