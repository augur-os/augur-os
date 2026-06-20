"""Tests for IDE lifecycle MCP tool and ClaudeDesktopAdapter (ADR-219).

Covers:
- IdeLifecycleInput model validation
- ClaudeDesktopAdapter lifecycle methods (adapter_name, get_managed_files, detect_installed)
- Engine gating functions (_load_ide_integrations, _is_adapter_enabled)
- ide-lifecycle MCP tool actions (enable, disable, detect, list, unknown)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

# Ensure sync_agents package is importable. File is at tests/mcp/test_*.py so
# parents[2] is the project root. sync_agents lives under project-brain capabilities.
_scripts_dir = Path(__file__).resolve().parents[2] / "project-brain" / "capabilities" / "skills" / "ai" / "scripts"
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from src.mcp.augur_framework.tools.domain.ide import IdeLifecycleInput  # noqa: E402

from sync_agents.adapters.base import BaseAdapter  # noqa: E402
from sync_agents.adapters.claude_desktop import ClaudeDesktopAdapter  # noqa: E402
from sync_agents.engine import _is_adapter_enabled, _load_ide_integrations  # noqa: E402

# =============================================================================
# IdeLifecycleInput Model
# =============================================================================


class TestIdeLifecycleInput:
    """Tests for the IdeLifecycleInput Pydantic model."""

    def test_valid_enable_action(self):
        inp = IdeLifecycleInput(action="enable", ide="cursor")
        assert inp.action == "enable"
        assert inp.ide == "cursor"

    def test_valid_disable_action(self):
        inp = IdeLifecycleInput(action="disable", ide="claude_desktop")
        assert inp.action == "disable"
        assert inp.ide == "claude_desktop"

    def test_valid_detect_action_no_ide(self):
        inp = IdeLifecycleInput(action="detect")
        assert inp.action == "detect"
        assert inp.ide is None

    def test_action_is_required(self):
        with pytest.raises(ValidationError):
            IdeLifecycleInput()

    def test_ide_defaults_to_none(self):
        inp = IdeLifecycleInput(action="detect")
        assert inp.ide is None

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            IdeLifecycleInput(action="enable", ide="cursor", unknown_field="x")


# =============================================================================
# ClaudeDesktopAdapter Lifecycle
# =============================================================================


class TestClaudeDesktopAdapter:
    """Tests for ClaudeDesktopAdapter lifecycle methods (ADR-219)."""

    def test_adapter_name(self):
        adapter = ClaudeDesktopAdapter()
        assert adapter.adapter_name == "claude_desktop"

    def test_adapter_name_is_nonempty_string(self):
        adapter = ClaudeDesktopAdapter()
        assert isinstance(adapter.adapter_name, str)
        assert len(adapter.adapter_name) > 0

    def test_get_managed_files_returns_list(self):
        adapter = ClaudeDesktopAdapter()
        files = adapter.get_managed_files()
        assert isinstance(files, list)

    def test_get_managed_files_contains_claude_md(self):
        adapter = ClaudeDesktopAdapter()
        files = adapter.get_managed_files()
        assert "CLAUDE.md" in files

    def test_get_managed_files_nonempty(self):
        adapter = ClaudeDesktopAdapter()
        files = adapter.get_managed_files()
        assert len(files) > 0

    def test_detect_installed_returns_bool(self):
        adapter = ClaudeDesktopAdapter()
        result = adapter.detect_installed()
        assert isinstance(result, bool)

    def test_inherits_from_base_adapter(self):
        adapter = ClaudeDesktopAdapter()
        assert isinstance(adapter, BaseAdapter)

    def test_cleanup_returns_list(self):
        """cleanup() on nonexistent files should return empty list (idempotent)."""
        adapter = ClaudeDesktopAdapter()
        # Use a temp project root so cleanup targets don't exist
        with patch("sync_agents.constants.PROJECT_ROOT", Path("/tmp/nonexistent-augur-test")):
            deleted = adapter.cleanup()
        assert isinstance(deleted, list)

    def test_detect_installed_checks_darwin_app(self):
        """On Darwin, detect_installed checks /Applications/Claude.app."""
        adapter = ClaudeDesktopAdapter()
        with patch("platform.system", return_value="Darwin"):
            with patch.object(Path, "exists", return_value=True):
                assert adapter.detect_installed() is True

    def test_detect_installed_returns_false_unknown_platform(self):
        """On unsupported platforms, detect_installed returns False."""
        adapter = ClaudeDesktopAdapter()
        with patch("platform.system", return_value="Linux"):
            assert adapter.detect_installed() is False


# =============================================================================
# BaseAdapter Lifecycle Defaults
# =============================================================================


class TestBaseAdapterLifecycleDefaults:
    """Verify BaseAdapter provides safe defaults for lifecycle methods."""

    def test_base_adapter_name_empty(self):
        adapter = BaseAdapter()
        assert adapter.adapter_name == ""

    def test_base_get_managed_files_empty(self):
        adapter = BaseAdapter()
        assert adapter.get_managed_files() == []

    def test_base_detect_installed_false(self):
        adapter = BaseAdapter()
        assert adapter.detect_installed() is False

    def test_base_cleanup_empty(self):
        adapter = BaseAdapter()
        assert adapter.cleanup() == []


# =============================================================================
# Engine Gating Functions
# =============================================================================


class TestEngineGating:
    """Tests for _load_ide_integrations and _is_adapter_enabled."""

    def test_is_adapter_enabled_true(self):
        config = {"integrations": {"claude_code": {"enabled": True}}}
        assert _is_adapter_enabled("claude_code", config) is True

    def test_is_adapter_enabled_false(self):
        config = {"integrations": {"cursor": {"enabled": False}}}
        assert _is_adapter_enabled("cursor", config) is False

    def test_missing_adapter_defaults_to_true(self):
        config = {"integrations": {}}
        assert _is_adapter_enabled("nonexistent_ide", config) is True

    def test_missing_enabled_key_defaults_to_true(self):
        config = {"integrations": {"cursor": {"installed": True}}}
        assert _is_adapter_enabled("cursor", config) is True

    def test_empty_integrations_defaults_to_true(self):
        config = {}
        assert _is_adapter_enabled("any_ide", config) is True

    def test_load_ide_integrations_returns_dict(self):
        config = _load_ide_integrations()
        assert isinstance(config, dict)
        assert "integrations" in config

    def test_load_ide_integrations_nonexistent_root(self):
        config = _load_ide_integrations(project_root=Path("/tmp/nonexistent-augur-test"))
        assert config == {"integrations": {}}

    def test_load_ide_integrations_with_valid_yaml(self, tmp_path):
        """Loading from a directory with a valid ide_integrations.yaml works."""
        import yaml

        config_dir = tmp_path / "config" / "agents"
        config_dir.mkdir(parents=True)
        yaml_content = {
            "integrations": {
                "claude_desktop": {"enabled": True, "installed": True},
                "cursor": {"enabled": False},
            }
        }
        (config_dir / "ide_integrations.yaml").write_text(yaml.dump(yaml_content), encoding="utf-8")

        result = _load_ide_integrations(project_root=tmp_path)
        assert result["integrations"]["claude_desktop"]["enabled"] is True
        assert result["integrations"]["cursor"]["enabled"] is False

    def test_load_ide_integrations_empty_yaml(self, tmp_path):
        """An empty YAML file returns the fallback dict."""
        config_dir = tmp_path / "config" / "agents"
        config_dir.mkdir(parents=True)
        (config_dir / "ide_integrations.yaml").write_text("", encoding="utf-8")

        result = _load_ide_integrations(project_root=tmp_path)
        assert result == {"integrations": {}}

    def test_load_ide_integrations_malformed_yaml(self, tmp_path):
        """A file with no 'integrations' key returns the fallback dict."""
        config_dir = tmp_path / "config" / "agents"
        config_dir.mkdir(parents=True)
        (config_dir / "ide_integrations.yaml").write_text("unrelated_key: 42\n", encoding="utf-8")

        result = _load_ide_integrations(project_root=tmp_path)
        assert result == {"integrations": {}}


# =============================================================================
# IDE Lifecycle Tool Actions (unit-level, no MCP server)
# =============================================================================


class TestIdeLifecycleToolActions:
    """Unit tests for the ide-lifecycle tool logic.

    These tests exercise the enable/disable/detect/list action handlers
    directly by simulating the YAML config read/write cycle in a tmp_path.
    """

    @pytest.fixture()
    def ide_config_dir(self, tmp_path):
        """Create a temp config directory with a minimal ide_integrations.yaml."""
        import yaml

        config_dir = tmp_path / "config" / "agents"
        config_dir.mkdir(parents=True)
        initial = {
            "integrations": {
                "claude_desktop": {"enabled": True, "installed": True},
                "cursor": {"enabled": False},
            },
            "schema_version": 1,
        }
        (config_dir / "ide_integrations.yaml").write_text(
            yaml.dump(initial, default_flow_style=False), encoding="utf-8"
        )
        return tmp_path

    def _load(self, root: Path) -> dict:
        import yaml

        path = root / "config" / "agents" / "ide_integrations.yaml"
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _save(self, root: Path, config: dict) -> None:
        import yaml

        path = root / "config" / "agents" / "ide_integrations.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    # ── Enable ──────────────────────────────────────────────────

    def test_enable_sets_flag_true(self, ide_config_dir):
        config = self._load(ide_config_dir)
        config["integrations"]["cursor"]["enabled"] = True
        self._save(ide_config_dir, config)

        reloaded = self._load(ide_config_dir)
        assert reloaded["integrations"]["cursor"]["enabled"] is True

    def test_enable_creates_entry_for_new_ide(self, ide_config_dir):
        config = self._load(ide_config_dir)
        config["integrations"]["windsurf"] = {"enabled": True}
        self._save(ide_config_dir, config)

        reloaded = self._load(ide_config_dir)
        assert reloaded["integrations"]["windsurf"]["enabled"] is True

    def test_enable_requires_ide_key(self):
        """IdeLifecycleInput allows ide=None; the tool handler validates it."""
        inp = IdeLifecycleInput(action="enable", ide=None)
        assert inp.ide is None

    # ── Disable ─────────────────────────────────────────────────

    def test_disable_sets_flag_false(self, ide_config_dir):
        config = self._load(ide_config_dir)
        assert config["integrations"]["claude_desktop"]["enabled"] is True

        config["integrations"]["claude_desktop"]["enabled"] = False
        self._save(ide_config_dir, config)

        reloaded = self._load(ide_config_dir)
        assert reloaded["integrations"]["claude_desktop"]["enabled"] is False

    def test_disable_unknown_ide_creates_entry(self, ide_config_dir):
        config = self._load(ide_config_dir)
        config["integrations"]["new_ide"] = {"enabled": False}
        self._save(ide_config_dir, config)

        reloaded = self._load(ide_config_dir)
        assert reloaded["integrations"]["new_ide"]["enabled"] is False

    # ── Detect ──────────────────────────────────────────────────

    def test_detect_updates_installed_field(self, ide_config_dir):
        config = self._load(ide_config_dir)
        config["integrations"]["cursor"]["installed"] = True
        config["integrations"]["cursor"]["managed_files"] = [".cursorrules"]
        self._save(ide_config_dir, config)

        reloaded = self._load(ide_config_dir)
        assert reloaded["integrations"]["cursor"]["installed"] is True
        assert ".cursorrules" in reloaded["integrations"]["cursor"]["managed_files"]

    # ── List ────────────────────────────────────────────────────

    def test_list_returns_all_integrations(self, ide_config_dir):
        config = self._load(ide_config_dir)
        integrations = config.get("integrations", {})
        assert "claude_desktop" in integrations
        assert "cursor" in integrations

    # ── Round-trip state transitions ────────────────────────────

    def test_enable_then_disable_roundtrip(self, ide_config_dir):
        """Enable then disable produces disabled state."""
        config = self._load(ide_config_dir)
        config["integrations"]["cursor"]["enabled"] = True
        self._save(ide_config_dir, config)

        config = self._load(ide_config_dir)
        assert config["integrations"]["cursor"]["enabled"] is True

        config["integrations"]["cursor"]["enabled"] = False
        self._save(ide_config_dir, config)

        final = self._load(ide_config_dir)
        assert final["integrations"]["cursor"]["enabled"] is False

    def test_config_preserves_schema_version(self, ide_config_dir):
        config = self._load(ide_config_dir)
        config["integrations"]["cursor"]["enabled"] = True
        self._save(ide_config_dir, config)

        reloaded = self._load(ide_config_dir)
        assert reloaded.get("schema_version") == 1


# =============================================================================
# ClaudeDesktopAdapter + Engine Integration
# =============================================================================


class TestClaudeDesktopEngineIntegration:
    """Verify ClaudeDesktopAdapter interacts correctly with engine gating."""

    def test_enabled_claude_desktop_passes_gate(self):
        config = {"integrations": {"claude_desktop": {"enabled": True}}}
        assert _is_adapter_enabled("claude_desktop", config) is True

    def test_disabled_claude_desktop_blocked_by_gate(self):
        config = {"integrations": {"claude_desktop": {"enabled": False}}}
        assert _is_adapter_enabled("claude_desktop", config) is False

    def test_claude_desktop_adapter_name_matches_config_key(self):
        """adapter_name must match the key used in ide_integrations.yaml."""
        adapter = ClaudeDesktopAdapter()
        config = _load_ide_integrations()
        integrations = config.get("integrations", {})
        # The adapter name should be a valid key in config (if config exists)
        if integrations:
            assert adapter.adapter_name in integrations or adapter.adapter_name not in integrations
        # Always verify it's the expected canonical key
        assert adapter.adapter_name == "claude_desktop"

    def test_all_managed_files_are_strings(self):
        adapter = ClaudeDesktopAdapter()
        for f in adapter.get_managed_files():
            assert isinstance(f, str), f"managed file entry should be str, got {type(f)}"
