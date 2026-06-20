"""Tests for auto-test-mcp-commands vertical."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import yaml

from src.lib.ops_protocol import make_test_ctx

# Hyphenated skill directory requires importlib-based import
_skill_dir = Path(__file__).resolve().parents[2]
_mod_file = _skill_dir / "scripts" / "test_mcp_commands_ops.py"
_spec = importlib.util.spec_from_file_location("test_mcp_commands_ops", _mod_file)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["test_mcp_commands_ops"] = _mod
_spec.loader.exec_module(_mod)

classify_tool = _mod.classify_tool
scan = _mod.scan
fix = _mod.fix
_PATCH_BASE = "test_mcp_commands_ops"


def _make_skill_md(tmp_path, skill, tools):
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / skill
    skill_dir.mkdir(parents=True)
    frontmatter = yaml.dump(
        {
            "name": skill,
            "x-augur-mcp-tools": tools,
        },
        sort_keys=False,
    ).strip()
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n")


def test_classify_read_safe():
    assert classify_tool("get-career-jobs", ["create-", "delete-"]) == "read"


def test_classify_mutating():
    assert classify_tool("create-plugin", ["create-", "delete-"]) == "mutating"


def test_classify_unknown_defaults_read():
    assert classify_tool("health", ["create-"]) == "read"


def test_scan_no_tools(tmp_path):
    result = scan(make_test_ctx(tmp_path))
    assert result.severity == "info"
    assert "No MCP tools" in result.summary


def test_scan_read_tool_ok(tmp_path):
    _make_skill_md(tmp_path, "resume", ["get-career-jobs"])
    with patch(f"{_PATCH_BASE}._fetch_tool_list", return_value=(True, "get-career-jobs\n")):
        with patch(f"{_PATCH_BASE}._invoke_tool") as mock_invoke:
            mock_invoke.return_value = {"ok": True, "stdout": '{"jobs":[]}'}
            result = scan(make_test_ctx(tmp_path))
    assert result.severity == "info"


def test_scan_read_tool_fail(tmp_path):
    _make_skill_md(tmp_path, "resume", ["get-career-jobs"])
    with patch(f"{_PATCH_BASE}._fetch_tool_list", return_value=(True, "get-career-jobs\n")):
        with patch(f"{_PATCH_BASE}._invoke_tool") as mock_invoke:
            mock_invoke.return_value = {"ok": False, "stderr": "Error: tool not found"}
            result = scan(make_test_ctx(tmp_path, difficulty=2))
    assert result.severity == "warning"
    assert result.issues[0]["kind"] == "maintenance"


def test_scan_d0_only_verifies_registration(tmp_path):
    _make_skill_md(tmp_path, "resume", ["get-career-jobs"])
    with patch(f"{_PATCH_BASE}._fetch_tool_list", return_value=(True, "get-career-jobs\n")):
        with patch(f"{_PATCH_BASE}._invoke_tool") as mock_invoke:
            result = scan(make_test_ctx(tmp_path, difficulty=0))
    assert result.severity == "info"
    mock_invoke.assert_not_called()


def test_scan_missing_registration_is_actionable(tmp_path):
    _make_skill_md(tmp_path, "resume", ["get-career-jobs"])
    with patch(f"{_PATCH_BASE}._fetch_tool_list", return_value=(True, "")):
        result = scan(make_test_ctx(tmp_path, difficulty=0))
    assert result.severity == "warning"
    assert result.issues[0]["kind"] == "actionable"


def test_scan_skips_tools_not_approved_for_direct_mcp(tmp_path):
    _make_skill_md(tmp_path, "resume", ["get-career-jobs"])
    policy_dir = tmp_path / "config" / "system"
    policy_dir.mkdir(parents=True)
    (policy_dir / "capability_exposure.yaml").write_text(
        "version: 1\n"
        "capabilities:\n"
        "  mcp-tool:get-career-jobs:\n"
        "    classification_status: approved\n"
        "    export_to:\n"
        "      - cli\n"
        "      - agents-md\n"
        "      - browse\n",
        encoding="utf-8",
    )

    with patch(f"{_PATCH_BASE}._fetch_tool_list", return_value=(True, "")):
        result = scan(make_test_ctx(tmp_path, difficulty=0))

    assert result.severity == "info"
    assert result.issues == []


def test_scan_still_flags_mcp_approved_tool_missing_registration(tmp_path):
    _make_skill_md(tmp_path, "resume", ["get-career-jobs"])
    policy_dir = tmp_path / "config" / "system"
    policy_dir.mkdir(parents=True)
    (policy_dir / "capability_exposure.yaml").write_text(
        "version: 1\n"
        "capabilities:\n"
        "  mcp-tool:get-career-jobs:\n"
        "    classification_status: approved\n"
        "    export_to:\n"
        "      - cli\n"
        "      - mcp\n",
        encoding="utf-8",
    )

    with patch(f"{_PATCH_BASE}._fetch_tool_list", return_value=(True, "")):
        result = scan(make_test_ctx(tmp_path, difficulty=0))

    assert result.severity == "warning"
    assert result.issues[0]["tool"] == "get-career-jobs"
    assert result.issues[0]["tool_category"] == "stale_config"


def test_scan_mutating_tool_schema_only(tmp_path):
    _make_skill_md(tmp_path, "resume", ["delete-career-job"])
    with patch(f"{_PATCH_BASE}._fetch_tool_list") as mock_list:
        mock_list.return_value = (True, "delete-career-job\nget-career-jobs\n")
        with patch(f"{_PATCH_BASE}._invoke_tool") as mock_invoke:
            result = scan(make_test_ctx(tmp_path))
    mock_invoke.assert_not_called()  # Mutating tools should NOT be invoked
    mock_list.assert_called_once()


def test_server_params_target_framework_with_dashboard_core_tools(tmp_path):
    params = _mod._get_server_params(tmp_path)

    assert params.args[:2] == ["-m", "src.mcp.augur_framework"]
    assert params.env["AUGUR_DASHBOARD_MCP_INCLUDE_CORE_TOOLS"] == "1"


def test_fix_dry_run(tmp_path):
    ctx = make_test_ctx(tmp_path, dry_run=True)
    result = fix(ctx, [{"tool": "get-x", "error": "fail"}])
    assert result.success
    assert "Dry run" in result.summary


def test_fix_writes_report(tmp_path):
    result = fix(make_test_ctx(tmp_path), [{"tool": "get-x", "error": "fail"}])
    assert result.success
    report = Path(result.actions[0]["report"])
    assert report.exists()
