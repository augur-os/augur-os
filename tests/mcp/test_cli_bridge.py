"""
CLIBridge Unit Tests.

Tests the src/lib CLIBridge utility in isolation using mocks.
No real CLI tools needed.

Run with: pytest tests/mcp/test_cli_bridge.py -v
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add augur-mcp src to path
_pkg_src = Path(__file__).parent.parent / "src"
if str(_pkg_src) not in sys.path:
    sys.path.insert(0, str(_pkg_src))

from src.mcp.augur_shared.cli_bridge import CLIBridge  # noqa: E402

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def bridge():
    """Create a CLIBridge with install hint."""
    return CLIBridge("testcli", install_hint="brew install testcli")


@pytest.fixture
def bridge_no_hint():
    """Create a CLIBridge without install hint."""
    return CLIBridge("testcli")


# =============================================================================
# is_installed()
# =============================================================================


class TestIsInstalled:
    @patch("shutil.which", return_value="/usr/local/bin/testcli")
    def test_is_installed_true(self, mock_which, bridge):
        assert bridge.is_installed() is True
        mock_which.assert_called_once_with("testcli")

    @patch("shutil.which", return_value=None)
    def test_is_installed_false(self, mock_which, bridge):
        assert bridge.is_installed() is False
        mock_which.assert_called_once_with("testcli")


# =============================================================================
# run()
# =============================================================================


class TestRun:
    @patch("shutil.which", return_value=None)
    def test_run_not_installed(self, mock_which, bridge):
        result = bridge.run(["arg1"])
        assert "error" in result
        assert "not installed" in result["error"]
        assert "brew install testcli" in result["error"]
        assert result["returncode"] == -1

    @patch("shutil.which", return_value="/usr/local/bin/testcli")
    @patch("subprocess.run")
    def test_run_success(self, mock_run, mock_which, bridge):
        mock_run.return_value = MagicMock(
            stdout="output data\n",
            stderr="",
            returncode=0,
        )
        result = bridge.run(["list", "--format", "json"])
        assert result["stdout"] == "output data\n"
        assert result["stderr"] == ""
        assert result["returncode"] == 0
        mock_run.assert_called_once_with(
            ["testcli", "list", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=30,
        )

    @patch("shutil.which", return_value="/usr/local/bin/testcli")
    @patch("subprocess.run")
    def test_run_failure(self, mock_run, mock_which, bridge):
        mock_run.return_value = MagicMock(
            stdout="",
            stderr="Error: invalid argument\n",
            returncode=1,
        )
        result = bridge.run(["bad-arg"])
        assert result["returncode"] == 1
        assert "invalid argument" in result["stderr"]

    @patch("shutil.which", return_value="/usr/local/bin/testcli")
    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="testcli", timeout=30))
    def test_run_timeout(self, mock_run, mock_which, bridge):
        result = bridge.run(["slow-command"], timeout=30)
        assert "error" in result
        assert "timed out" in result["error"]
        assert "30s" in result["error"]
        assert result["returncode"] == -2

    @patch("shutil.which", return_value="/usr/local/bin/testcli")
    @patch("subprocess.run", side_effect=FileNotFoundError())
    def test_run_file_not_found(self, mock_run, mock_which, bridge):
        result = bridge.run(["arg"])
        assert "error" in result
        assert "not found" in result["error"]
        assert "brew install testcli" in result["error"]
        assert result["returncode"] == -1

    @patch("shutil.which", return_value="/usr/local/bin/testcli")
    @patch("subprocess.run")
    def test_run_json_output(self, mock_run, mock_which, bridge):
        json_data = {"items": [1, 2, 3], "count": 3}
        mock_run.return_value = MagicMock(
            stdout=json.dumps(json_data),
            stderr="",
            returncode=0,
        )
        result = bridge.run(["list"], json_output=True)
        assert result["returncode"] == 0
        assert "data" in result
        assert result["data"] == json_data

    @patch("shutil.which", return_value="/usr/local/bin/testcli")
    @patch("subprocess.run")
    def test_run_json_invalid(self, mock_run, mock_which, bridge):
        mock_run.return_value = MagicMock(
            stdout="not valid json {{{",
            stderr="",
            returncode=0,
        )
        result = bridge.run(["list"], json_output=True)
        assert result["returncode"] == 0
        assert "data" not in result
        assert result["stdout"] == "not valid json {{{"

    @patch("shutil.which", return_value="/usr/local/bin/testcli")
    @patch("subprocess.run")
    def test_run_json_output_on_failure_skips_parse(self, mock_run, mock_which, bridge):
        mock_run.return_value = MagicMock(
            stdout="error output",
            stderr="",
            returncode=1,
        )
        result = bridge.run(["list"], json_output=True)
        assert result["returncode"] == 1
        assert "data" not in result


# =============================================================================
# run_or_error()
# =============================================================================


class TestRunOrError:
    @patch("shutil.which", return_value="/usr/local/bin/testcli")
    @patch("subprocess.run")
    def test_run_or_error_success(self, mock_run, mock_which, bridge):
        mock_run.return_value = MagicMock(
            stdout="  success output  \n",
            stderr="",
            returncode=0,
        )
        result = bridge.run_or_error(["arg"])
        assert result == "success output"

    @patch("shutil.which", return_value="/usr/local/bin/testcli")
    @patch("subprocess.run")
    def test_run_or_error_failure_with_stderr(self, mock_run, mock_which, bridge):
        mock_run.return_value = MagicMock(
            stdout="",
            stderr="  something went wrong  \n",
            returncode=1,
        )
        result = bridge.run_or_error(["bad-arg"])
        assert result == "something went wrong"

    @patch("shutil.which", return_value="/usr/local/bin/testcli")
    @patch("subprocess.run")
    def test_run_or_error_failure_no_stderr(self, mock_run, mock_which, bridge):
        mock_run.return_value = MagicMock(
            stdout="",
            stderr="",
            returncode=42,
        )
        result = bridge.run_or_error(["bad-arg"])
        assert "exit code 42" in result

    @patch("shutil.which", return_value=None)
    def test_run_or_error_not_installed(self, mock_which, bridge):
        result = bridge.run_or_error(["arg"])
        assert "not installed" in result
        assert "brew install testcli" in result


# =============================================================================
# Install hint propagation
# =============================================================================


class TestInstallHint:
    @patch("shutil.which", return_value=None)
    def test_install_hint_in_run_error(self, mock_which, bridge):
        result = bridge.run(["arg"])
        assert "brew install testcli" in result["error"]

    @patch("shutil.which", return_value=None)
    def test_install_hint_in_run_or_error(self, mock_which, bridge):
        result = bridge.run_or_error(["arg"])
        assert "brew install testcli" in result

    @patch("shutil.which", return_value=None)
    def test_no_hint_still_works(self, mock_which, bridge_no_hint):
        result = bridge_no_hint.run(["arg"])
        assert "not installed" in result["error"]
        assert result["error"] == "testcli not installed."

    @patch("shutil.which", return_value="/usr/local/bin/testcli")
    @patch("subprocess.run", side_effect=FileNotFoundError())
    def test_install_hint_in_file_not_found(self, mock_run, mock_which, bridge):
        result = bridge.run(["arg"])
        assert "brew install testcli" in result["error"]


# =============================================================================
# Custom timeout
# =============================================================================


class TestTimeout:
    @patch("shutil.which", return_value="/usr/local/bin/testcli")
    @patch("subprocess.run")
    def test_custom_timeout(self, mock_run, mock_which, bridge):
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        bridge.run(["arg"], timeout=120)
        mock_run.assert_called_once_with(
            ["testcli", "arg"],
            capture_output=True,
            text=True,
            timeout=120,
        )
