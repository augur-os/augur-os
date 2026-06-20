"""
Connectivity Watchdog Tests.

User Need: Detect whether the host has internet access for airplane mode auto-detection.

Run with: uv run pytest tests/packages/augur-mcp/tools/test_connectivity.py -v
"""

import socket


from src.mcp.augur_framework.tools.infrastructure.connectivity import check_connectivity

# =============================================================================
# Contract Tests: check_connectivity
# =============================================================================


class TestCheckConnectivity:
    """
    User Need: Know whether the system is online or offline.

    Acceptance Criteria:
    1. Returns online=True when DNS resolves successfully
    2. Returns online=False when DNS fails (gaierror)
    3. Returns online=False when DNS fails (OSError)
    4. Result always includes checked_at ISO timestamp
    5. Result always includes host string
    """

    def test_online_when_dns_resolves(self, monkeypatch):
        """DNS resolution succeeds -> online: True."""
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.connectivity.socket.getaddrinfo",
            lambda host, port: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("104.18.0.1", 443))],
        )

        result = check_connectivity()

        assert result["online"] is True
        assert result["host"] == "api.anthropic.com"
        assert "checked_at" in result

    def test_offline_on_gaierror(self, monkeypatch):
        """DNS resolution raises gaierror -> online: False."""

        def _fail(host, port):
            raise socket.gaierror("Name resolution failed")

        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.connectivity.socket.getaddrinfo",
            _fail,
        )

        result = check_connectivity()

        assert result["online"] is False
        assert result["host"] == "api.anthropic.com"

    def test_offline_on_oserror(self, monkeypatch):
        """DNS resolution raises OSError -> online: False."""

        def _fail(host, port):
            raise OSError("Network unreachable")

        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.connectivity.socket.getaddrinfo",
            _fail,
        )

        result = check_connectivity()

        assert result["online"] is False
        assert result["host"] == "api.anthropic.com"

    def test_checked_at_is_iso_timestamp(self, monkeypatch):
        """Result includes a parseable ISO 8601 timestamp."""
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.connectivity.socket.getaddrinfo",
            lambda host, port: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("104.18.0.1", 443))],
        )

        result = check_connectivity()

        # Should be parseable as ISO format
        from datetime import datetime

        parsed = datetime.fromisoformat(result["checked_at"])
        assert parsed is not None

    def test_custom_host(self, monkeypatch):
        """Custom host is reflected in the result."""
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.connectivity.socket.getaddrinfo",
            lambda host, port: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 443))],
        )

        result = check_connectivity(host="one.one.one.one", port=443)

        assert result["online"] is True
        assert result["host"] == "one.one.one.one"
