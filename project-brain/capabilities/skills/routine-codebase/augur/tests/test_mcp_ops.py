"""Tests for auto-test-mcp vertical."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.lib.ops_protocol import make_test_ctx

# Hyphenated skill directory requires importlib-based import
_skill_dir = Path(__file__).resolve().parents[2]
_mod_file = _skill_dir / "scripts" / "test_mcp_ops.py"
_spec = importlib.util.spec_from_file_location("test_mcp_ops", _mod_file)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["test_mcp_ops"] = _mod
_spec.loader.exec_module(_mod)

scan = _mod.scan
fix = _mod.fix
_PATCH_TARGET = "test_mcp_ops._check_mcp_health"


def test_scan_health_ok(tmp_path):
    with patch(_PATCH_TARGET) as mock_health:
        mock_health.return_value = {
            "ok": True,
            "tools": 42,
            "tool_names": ["get-system-health", "discover-augur", "list-mcp-tools"],
        }
        result = scan(make_test_ctx(tmp_path, difficulty=1))
    assert result.severity == "info"
    assert not result.issues
    assert "42" in result.summary


def test_scan_health_fail(tmp_path):
    with patch(_PATCH_TARGET) as mock_health:
        mock_health.return_value = {"ok": False, "error": "connection refused"}
        result = scan(make_test_ctx(tmp_path, difficulty=1))
    assert result.severity == "error"
    assert len(result.issues) == 1


def test_scan_d2_flags_missing_core_tools(tmp_path):
    with patch(_PATCH_TARGET) as mock_health:
        mock_health.return_value = {
            "ok": True,
            "tools": 60,
            "tool_names": ["get-system-health"],
        }
        result = scan(make_test_ctx(tmp_path, difficulty=2))
    assert result.severity == "error"
    assert result.issues[0]["category"] == "missing-core-tools"


def test_scan_d2_flags_low_tool_count(tmp_path):
    with patch(_PATCH_TARGET) as mock_health:
        mock_health.return_value = {
            "ok": True,
            "tools": 3,
            "tool_names": ["get-system-health", "discover-augur", "list-mcp-tools"],
        }
        result = scan(make_test_ctx(tmp_path, difficulty=2, config={"min_tools": 10}))
    assert result.severity == "error"
    assert result.issues[0]["category"] == "tool-count-low"


def test_scan_d0_uses_surface_check_without_handshake(tmp_path):
    mcp_main = tmp_path / "src" / "mcp" / "augur_framework"
    mcp_main.mkdir(parents=True)
    (mcp_main / "__main__.py").write_text("print('ok')\n")
    venv_python = tmp_path / ".venv" / "bin"
    venv_python.mkdir(parents=True)
    (venv_python / "python").write_text("#!/bin/sh\n")

    with patch(_PATCH_TARGET, side_effect=AssertionError("d0 scan should not open MCP")):
        result = scan(make_test_ctx(tmp_path, difficulty=0))

    assert result.severity == "info"
    assert not result.issues
    assert "prerequisites" in result.summary.lower()


def test_scan_d2_client_config_failure_reports_issue(tmp_path):
    """Client-config validation at d2+ should report startup failures."""
    with patch(_PATCH_TARGET) as mock_health, \
         patch("test_mcp_ops._scan_client_configs") as mock_cc:
        mock_health.return_value = {
            "ok": True,
            "tools": 60,
            "tool_names": ["get-system-health", "discover-augur", "list-mcp-tools"],
        }
        mock_cc.return_value = [{
            "error": "MCP startup failed under claude_desktop config: lock conflict",
            "level": "client-config",
            "category": "client-config-startup-fail",
            "client": "claude_desktop",
        }]
        result = scan(make_test_ctx(tmp_path, difficulty=2))
    assert result.severity == "error"
    assert any(i["category"] == "client-config-startup-fail" for i in result.issues)


def test_scan_d2_client_config_ok_no_issues(tmp_path):
    """When client configs start OK, no extra issues at d2."""
    with patch(_PATCH_TARGET) as mock_health, \
         patch("test_mcp_ops._scan_client_configs") as mock_cc:
        mock_health.return_value = {
            "ok": True,
            "tools": 60,
            "tool_names": ["get-system-health", "discover-augur", "list-mcp-tools"],
        }
        mock_cc.return_value = []
        result = scan(make_test_ctx(tmp_path, difficulty=2))
    assert result.severity == "info"
    assert not result.issues


def test_load_client_configs_missing_file(tmp_path):
    """Skips clients whose config file doesn't exist."""
    _load = _mod._load_client_configs
    with patch.dict(_mod._CLIENT_CONFIGS, {
        "test_client": {
            "config_path": tmp_path / "nonexistent.json",
            "server_key": "augur",
        }
    }, clear=True):
        assert _load() == []


def test_load_client_configs_parses_valid(tmp_path):
    """Parses valid client config into structured dict."""
    _load = _mod._load_client_configs
    config_file = tmp_path / "config.json"
    config_file.write_text('{"mcpServers":{"augur":{"command":"/usr/bin/python","args":["-m","augur_framework"],"env":{"FOO":"bar"},"cwd":"/tmp"}}}')
    with patch.dict(_mod._CLIENT_CONFIGS, {
        "test_client": {
            "config_path": config_file,
            "server_key": "augur",
        }
    }, clear=True):
        configs = _load()
    assert len(configs) == 1
    assert configs[0]["client"] == "test_client"
    assert configs[0]["command"] == "/usr/bin/python"
    assert configs[0]["args"] == ["-m", "augur_framework"]


def test_fix_dry_run(tmp_path):
    ctx = make_test_ctx(tmp_path, dry_run=True)
    result = fix(ctx, [{"error": "unreachable"}])
    assert result.success
    assert "Dry run" in result.summary


def test_fix_writes_report(tmp_path):
    import os

    with patch.dict(os.environ, {"AUGUR_STATE": str(tmp_path / "runtime")}):
        result = fix(make_test_ctx(tmp_path), [{"error": "unreachable"}])
    assert result.success
    report = tmp_path / "runtime/reports/test-mcp-latest.json"
    assert report.exists()
