"""Tests for CLI plugin subcommand discovery (ADR-260)."""

import argparse
import logging
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cli_plugins import discover_subcommands


def _make_subparsers():
    parser = argparse.ArgumentParser()
    return parser.add_subparsers(dest="subcommand")


class TestDiscoverSubcommands:
    def test_returns_count(self):
        """discover_subcommands returns an integer count."""
        subparsers = _make_subparsers()
        with patch("src.cli_plugins._get_skill_dirs", return_value=[]):
            result = discover_subcommands(subparsers)
        assert isinstance(result, int)
        assert result == 0

    def test_loads_plugin_with_register_subcommands(self, tmp_path):
        """Plugins with register_subcommands() are discovered."""
        skill = "test-cmd"
        mcp_dir = tmp_path / skill / "scripts" / "mcp"
        mcp_dir.mkdir(parents=True)
        init_file = mcp_dir / "__init__.py"
        init_file.write_text(
            'def register_subcommands(subparsers):\n'
            '    p = subparsers.add_parser("test-cmd", help="test")\n'
            '    p.set_defaults(func=lambda a, r: 0)\n'
        )

        subparsers = _make_subparsers()
        with patch("src.cli_plugins._get_skill_dirs", return_value=[tmp_path]):
            result = discover_subcommands(subparsers)

        assert result == 1
        assert "test-cmd" in subparsers._name_parser_map

    def test_skips_plugin_without_register_subcommands(self, tmp_path):
        """Plugins without register_subcommands() are skipped."""
        skill = "no-cmd"
        mcp_dir = tmp_path / skill / "scripts" / "mcp"
        mcp_dir.mkdir(parents=True)
        init_file = mcp_dir / "__init__.py"
        init_file.write_text('def register_tools(mcp, interceptor, metrics): pass\n')

        subparsers = _make_subparsers()
        with patch("src.cli_plugins._get_skill_dirs", return_value=[tmp_path]):
            result = discover_subcommands(subparsers)

        assert result == 0

    def test_collision_warning(self, tmp_path, caplog):
        """Duplicate subcommand names log a warning, first wins."""
        for skill_name in ("plugin-a", "plugin-b"):
            mcp_dir = tmp_path / skill_name / "scripts" / "mcp"
            mcp_dir.mkdir(parents=True)
            init_file = mcp_dir / "__init__.py"
            init_file.write_text(
                'def register_subcommands(subparsers):\n'
                '    p = subparsers.add_parser("dupe-cmd", help="from ' + skill_name + '")\n'
                '    p.set_defaults(func=lambda a, r: 0)\n'
            )

        subparsers = _make_subparsers()
        with patch("src.cli_plugins._get_skill_dirs", return_value=[tmp_path]):
            with caplog.at_level(logging.WARNING, logger="cli.plugins"):
                discover_subcommands(subparsers)

        assert "already registered" in caplog.text

    def test_handles_broken_plugin(self, tmp_path):
        """Broken plugin modules don't crash discovery."""
        skill = "broken"
        mcp_dir = tmp_path / skill / "scripts" / "mcp"
        mcp_dir.mkdir(parents=True)
        init_file = mcp_dir / "__init__.py"
        init_file.write_text('raise RuntimeError("broken plugin")\n')

        subparsers = _make_subparsers()
        with patch("src.cli_plugins._get_skill_dirs", return_value=[tmp_path]):
            result = discover_subcommands(subparsers)

        assert result == 0  # No crash, graceful skip
