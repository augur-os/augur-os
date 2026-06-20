"""Tests for service_availability.py -- external service health checker."""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SCRIPTS_PATH = Path(__file__).resolve().parents[2] / "scripts" / "service_availability.py"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_spec = importlib.util.spec_from_file_location("service_availability", SCRIPTS_PATH)
service_availability = importlib.util.module_from_spec(_spec)
sys.modules["service_availability"] = service_availability
assert _spec.loader is not None
_spec.loader.exec_module(service_availability)

ServiceStatus = service_availability.ServiceStatus


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear the module-level cache between tests."""
    service_availability.clear_cache()
    yield
    service_availability.clear_cache()


class TestCache:
    """Tests for the status caching layer."""

    def test_set_and_get_cached(self):
        s = ServiceStatus(service_id="gh", name="GitHub CLI", type="cli", status="connected")
        service_availability._set_cached("gh", s)
        cached = service_availability._get_cached("gh")
        assert cached is not None
        assert cached.service_id == "gh"

    def test_expired_cache_returns_none(self):
        s = ServiceStatus(service_id="gh", name="GitHub CLI", type="cli", status="connected")
        service_availability._status_cache["gh"] = (s, time.time() - 600)
        cached = service_availability._get_cached("gh")
        assert cached is None

    def test_clear_cache(self):
        s = ServiceStatus(service_id="gh", name="GitHub CLI", type="cli", status="connected")
        service_availability._set_cached("gh", s)
        service_availability.clear_cache()
        assert service_availability._get_cached("gh") is None


class TestCheckMcpService:
    """Tests for MCP service status checks."""

    def test_connected_when_pid_alive(self, tmp_path, monkeypatch):
        pids_file = tmp_path / "mcp_pids.json"
        pids_file.write_text(json.dumps({"servers": {"test-mcp": {"pid": 12345}}}))
        monkeypatch.setattr(service_availability, "get_runtime_dir", lambda: tmp_path)

        with patch.object(service_availability, "_is_pid_alive", return_value=True):
            status = service_availability._check_mcp_service(
                "test-mcp", {"name": "Test MCP", "type": "mcp"}
            )
        assert status.status == "connected"

    def test_disconnected_when_pid_dead(self, tmp_path, monkeypatch):
        pids_file = tmp_path / "mcp_pids.json"
        pids_file.write_text(json.dumps({"servers": {"test-mcp": {"pid": 99999}}}))
        monkeypatch.setattr(service_availability, "get_runtime_dir", lambda: tmp_path)

        with patch.object(service_availability, "_is_pid_alive", return_value=False):
            status = service_availability._check_mcp_service(
                "test-mcp", {"name": "Test MCP", "type": "mcp"}
            )
        assert status.status == "disconnected"

    def test_unknown_when_no_pids_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(service_availability, "get_runtime_dir", lambda: tmp_path)
        status = service_availability._check_mcp_service(
            "test-mcp", {"name": "Test MCP", "type": "mcp"}
        )
        assert status.status == "unknown"
        assert "PID registry" in status.error


class TestCheckCliService:
    """Tests for CLI tool availability checks."""

    def test_connected_when_command_succeeds(self):
        mock_result = MagicMock(returncode=0, stdout="cli 2.0.1\n", stderr="")
        with patch("service_availability.run", return_value=mock_result), \
             patch("service_availability._resolve_command", return_value=["cli", "--version"]):
            status = service_availability._check_cli_service(
                "cli-tool", {"name": "CLI Tool", "type": "cli", "check_command": "cli --version"}
            )
        assert status.status == "connected"
        assert status.version == "cli 2.0.1"

    def test_disconnected_when_command_not_found(self):
        with patch("service_availability.run", side_effect=FileNotFoundError), \
             patch("service_availability._resolve_command", return_value=["missing"]):
            status = service_availability._check_cli_service(
                "missing-cli", {"name": "Missing", "type": "cli", "check_command": "missing --version"}
            )
        assert status.status == "disconnected"
        assert "not found" in status.error.lower()

    def test_unknown_when_no_check_command(self):
        status = service_availability._check_cli_service(
            "no-cmd", {"name": "No Cmd", "type": "cli"}
        )
        assert status.status == "unknown"


class TestServiceStatusDataclass:
    """Tests for ServiceStatus.to_dict."""

    def test_to_dict_omits_none_values(self):
        s = ServiceStatus(service_id="x", name="X", type="cli", status="connected")
        d = s.to_dict()
        assert "version" not in d
        assert "error" not in d
        assert d["service_id"] == "x"

    def test_to_dict_includes_set_values(self):
        s = ServiceStatus(
            service_id="x", name="X", type="cli",
            status="disconnected", error="not found", version="1.0"
        )
        d = s.to_dict()
        assert d["error"] == "not found"
        assert d["version"] == "1.0"
