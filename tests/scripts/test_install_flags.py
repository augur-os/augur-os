"""
Tests for install.sh --from and --configure flags (ADR-437, ADR-438).

Run with: pytest tests/scripts/test_install_flags.py -v
"""

import subprocess
import sys

import pytest

from src.config.paths import get_project_root

PROJECT_ROOT = get_project_root()
INSTALL_SCRIPT = PROJECT_ROOT / "scripts" / "install.sh"


class TestInstallShSyntax:
    """Verify install.sh syntax and structure."""

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX install.sh; bash unavailable on native Windows (uses .ps1)")
    def test_bash_syntax_valid(self):
        result = subprocess.run(
            ["bash", "-n", str(INSTALL_SCRIPT)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Bash syntax error: {result.stderr}"

    def test_from_flag_documented(self):
        content = INSTALL_SCRIPT.read_text()
        assert "--from" in content

    def test_configure_flag_documented(self):
        content = INSTALL_SCRIPT.read_text()
        assert "--configure" in content

    def test_install_source_json_path(self):
        content = INSTALL_SCRIPT.read_text()
        assert "install-source.json" in content

    def test_onboard_complete_json_path(self):
        content = INSTALL_SCRIPT.read_text()
        assert "onboard-complete.json" in content

    def test_vault_scaffold_flag(self):
        """Verify --from vault triggers vault scaffolding."""
        content = INSTALL_SCRIPT.read_text()
        assert '"$INSTALL_FROM" = "vault"' in content

    def test_configure_mcp_integration(self):
        """Verify --configure invokes configure_mcp.py."""
        content = INSTALL_SCRIPT.read_text()
        assert "configure_mcp.py" in content
