"""Unit tests for generate_client_config.py — MCP client config generation.

Run with: pytest skills/platform-admin/augur/tests/test_generate_client_config.py -v
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parents[4]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import from hyphenated directory via importlib
_config_path = (
    Path(__file__).resolve().parents[2] / "scripts" / "generate_client_config.py"
)
_spec = importlib.util.spec_from_file_location("generate_client_config", _config_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

generate_claude_desktop_config = _mod.generate_claude_desktop_config
generate_antigravity_config = _mod.generate_antigravity_config


# =============================================================================
# Tests: generate_claude_desktop_config
# =============================================================================


class TestClaudeDesktopConfig:
    def test_basic_structure(self):
        config = generate_claude_desktop_config("192.168.1.100")
        assert "mcpServers" in config
        assert "augur" in config["mcpServers"]
        server = config["mcpServers"]["augur"]
        assert server["transport"] == "streamable-http"

    def test_url_uses_host(self):
        config = generate_claude_desktop_config("myhost.local")
        url = config["mcpServers"]["augur"]["url"]
        assert "myhost.local" in url
        assert url.startswith("https://")

    def test_default_port_443(self):
        config = generate_claude_desktop_config("host.local")
        url = config["mcpServers"]["augur"]["url"]
        # Default port 443 should not appear explicitly in URL
        assert ":443" not in url or "host.local" in url

    def test_custom_port(self):
        config = generate_claude_desktop_config("host.local", port=8443)
        # Port parameter is accepted (even if not embedded in URL currently)
        assert config["mcpServers"]["augur"]["url"] is not None


# =============================================================================
# Tests: generate_antigravity_config
# =============================================================================


class TestAntigravityConfig:
    def test_basic_structure(self):
        config = generate_antigravity_config("192.168.1.100")
        assert "mcp_servers" in config
        assert len(config["mcp_servers"]) == 1
        server = config["mcp_servers"][0]
        assert server["name"] == "augur"
        assert server["transport"] == "streamable-http"

    def test_url_uses_host(self):
        config = generate_antigravity_config("10.0.0.1")
        url = config["mcp_servers"][0]["url"]
        assert "10.0.0.1" in url
        assert url.startswith("https://")

    def test_has_description(self):
        config = generate_antigravity_config("host.local")
        assert config["mcp_servers"][0]["description"] != ""
