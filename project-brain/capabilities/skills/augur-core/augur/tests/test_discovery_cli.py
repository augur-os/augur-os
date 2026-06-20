"""Unit tests for the discovery CLI subcommand — manifest markdown formatting.

Run with: pytest skills/discovery/augur/tests/test_discovery_cli.py -v
"""

import importlib.util
import sys
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

_project_root = Path(__file__).resolve().parents[4]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import from scripts/mcp/__init__.py via importlib to avoid package chain issues
_mcp_init_path = (
    Path(__file__).resolve().parents[2] / "scripts" / "mcp" / "__init__.py"
)
_spec = importlib.util.spec_from_file_location("discovery_mcp", _mcp_init_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_print_manifest_markdown = _mod._print_manifest_markdown
register_subcommands = _mod.register_subcommands
_run_discover = _mod._run_discover


# =============================================================================
# Tests: _print_manifest_markdown
# =============================================================================


class TestPrintManifestMarkdown:
    def _capture(self, manifest):
        """Run _print_manifest_markdown and capture stdout."""
        buf = StringIO()
        with patch("sys.stdout", buf):
            _print_manifest_markdown(manifest)
        return buf.getvalue()

    def test_prints_heading_with_description(self):
        manifest = {
            "manifest": {"description": "Personal knowledge system"},
            "focus": {},
            "recommended_tools": [],
        }
        output = self._capture(manifest)
        assert "# Augur" in output
        assert "Personal knowledge system" in output

    def test_prints_hub_focus(self):
        manifest = {
            "manifest": {"description": ""},
            "focus": {"hub": "career"},
            "recommended_tools": [],
        }
        output = self._capture(manifest)
        assert "career" in output

    def test_prints_tool_table(self):
        manifest = {
            "manifest": {"description": "Test"},
            "focus": {},
            "recommended_tools": [
                {"name": "rag-search", "skill": "knowledge", "hub": "ai", "tier": "1"},
                {"name": "list-tasks", "skill": "eisenhower", "hub": "productivity", "tier": "2"},
            ],
        }
        output = self._capture(manifest)
        assert "Recommended Tools (2)" in output
        assert "rag-search" in output
        assert "list-tasks" in output
        assert "| Tool |" in output

    def test_prints_hubs_section(self):
        manifest = {
            "manifest": {
                "description": "Test",
                "hubs": [
                    {"id": "ai", "skills": ["knowledge", "ai"]},
                    {"id": "career", "skills": ["growth"]},
                ],
            },
            "focus": {},
            "recommended_tools": [],
        }
        output = self._capture(manifest)
        assert "Hubs (2)" in output
        assert "**ai**" in output
        assert "knowledge, ai" in output

    def test_empty_manifest(self):
        manifest = {"manifest": {}, "focus": {}, "recommended_tools": []}
        output = self._capture(manifest)
        # Should not crash, just print minimal output
        assert "# Augur" in output


# =============================================================================
# Tests: register_subcommands
# =============================================================================


class TestRegisterSubcommands:
    def test_registers_discover_subparser(self):
        """The discover subcommand should be registered with expected arguments."""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register_subcommands(subparsers)

        # Parse a discover command to verify it was registered
        args = parser.parse_args(["discover", "--hub", "ai", "--compact"])
        assert args.hub == "ai"
        assert args.compact is True
        assert hasattr(args, "func")


class TestRunDiscover:
    def test_uses_created_session_for_manifest(self, tmp_path, monkeypatch):
        """The plugin command must not fall back to stale global focus state."""
        from src.config import paths as paths_mod
        from src.mcp.augur_framework.tools.domain import discovery as discovery_mod
        from src.mcp.augur_framework.tools.domain import sessions as sessions_mod

        captured = {}

        def fake_create_session(sessions_dir, session_id, source, hub=None, skill=None):
            captured["created_session_id"] = session_id
            captured["sessions_dir"] = sessions_dir
            captured["source"] = source
            return {}

        def fake_assemble_manifest(runtime_dir, hub=None, tier=None, session_id=None):
            captured["runtime_dir"] = runtime_dir
            captured["hub"] = hub
            captured["tier"] = tier
            captured["manifest_session_id"] = session_id
            return {"manifest": {}, "focus": {}, "recommended_tools": []}

        monkeypatch.setattr(paths_mod, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(paths_mod, "get_runtime_dir", lambda: tmp_path / "state")
        monkeypatch.setattr(sessions_mod, "create_session", fake_create_session)
        monkeypatch.setattr(sessions_mod, "delete_session", lambda sessions_dir, session_id: None)
        monkeypatch.setattr(discovery_mod, "assemble_manifest", fake_assemble_manifest)

        args = SimpleNamespace(
            hub=None,
            tier=None,
            compact=False,
            discover_format="json",
        )

        assert _run_discover(args, []) == 0
        assert captured["manifest_session_id"] == captured["created_session_id"]
        assert captured["source"] == "cli"
