"""
CLI Argument Verification Tests.

Verify that CLI arguments used in MCP tool wrappers match
actual CLI interfaces. These are live tests requiring CLIs installed.

Run with: pytest tests/mcp/test_cli_args.py -v -m integration
"""

import sys
from pathlib import Path

import pytest

# Add augur-mcp src to path
_pkg_src = Path(__file__).parent.parent / "src"
if str(_pkg_src) not in sys.path:
    sys.path.insert(0, str(_pkg_src))

from src.mcp.augur_shared.cli_bridge import CLIBridge  # noqa: E402


@pytest.mark.integration
class TestCLIArguments:
    """Verify MCP wrapper CLI args match actual CLI --help output."""

    EXPECTED_SUBCOMMANDS = {
        "remindctl": ["list", "add", "complete"],
        "imsg": ["chats", "read", "send"],
        "openhue": ["get", "set"],
        "gog": ["gmail", "calendar", "drive", "docs"],
        "peekaboo": ["screenshot", "inspect"],
    }

    @pytest.mark.parametrize(
        "cli,subcmds",
        list(EXPECTED_SUBCOMMANDS.items()),
        ids=list(EXPECTED_SUBCOMMANDS.keys()),
    )
    def test_cli_accepts_expected_subcommands(self, cli, subcmds):
        """Run `cli --help` and verify expected subcommands appear."""
        bridge = CLIBridge(cli)
        if not bridge.is_installed():
            pytest.skip(f"{cli} not installed")

        result = bridge.run(["--help"], timeout=10)
        help_text = (result.get("stdout", "") + result.get("stderr", "")).lower()

        # Some CLIs (e.g., openhue) require initial setup before --help works
        if "not configured" in help_text or "please run" in help_text:
            pytest.skip(f"{cli} needs initial setup before --help works")

        for subcmd in subcmds:
            assert subcmd.lower() in help_text, (
                f"{cli} --help output does not contain expected subcommand '{subcmd}'. "
                f"This may indicate a mismatch between the MCP wrapper args and the actual CLI interface."
            )

    EXPECTED_FLAGS = {
        "wacli": ["chats", "read", "send", "search"],
        "summarize": ["url", "youtube", "file"],
    }

    @pytest.mark.parametrize(
        "cli,keywords",
        list(EXPECTED_FLAGS.items()),
        ids=list(EXPECTED_FLAGS.keys()),
    )
    def test_cli_help_contains_keywords(self, cli, keywords):
        """Verify CLI help contains expected keywords (flags or subcommands)."""
        bridge = CLIBridge(cli)
        if not bridge.is_installed():
            pytest.skip(f"{cli} not installed")

        result = bridge.run(["--help"], timeout=10)
        help_text = (result.get("stdout", "") + result.get("stderr", "")).lower()

        for keyword in keywords:
            assert keyword.lower() in help_text, (
                f"{cli} --help output does not contain expected keyword '{keyword}'. "
                f"CLI interface may have changed."
            )


@pytest.mark.integration
class TestCLIAvailability:
    """Verify which CLIs are installed on this system."""

    ALL_CLIS = {
        "gog": "Google Workspace",
        "imsg": "iMessage",
        "wacli": "WhatsApp",
        "openhue": "Philips Hue",
        "sonos": "Sonos",
        "summarize": "URL Summarizer",
        "nano-pdf": "PDF Editor",
        "peekaboo": "macOS Screenshots",
        "whisper": "Speech-to-Text",
        "remindctl": "Apple Reminders",
    }

    @pytest.mark.parametrize(
        "cli,description",
        list(ALL_CLIS.items()),
        ids=list(ALL_CLIS.keys()),
    )
    def test_cli_availability(self, cli, description):
        """Check if CLI is installed (informational, does not fail)."""
        bridge = CLIBridge(cli)
        installed = bridge.is_installed()
        # This test always passes -- it's informational
        if not installed:
            pytest.skip(f"{cli} ({description}) not installed")
