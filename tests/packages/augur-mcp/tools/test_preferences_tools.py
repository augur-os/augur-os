"""
Preferences/Config MCP Tool Contract Tests.

User Need: Manage preferences and path configuration.

Run with: cd packages/augur-mcp && uv run pytest tests/tools/test_preferences_tools.py -v
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from src.mcp.augur_core.tools.core.models import GetPreferencesInput, UpdatePreferenceInput
from src.mcp.augur_core.tools.core.preferences import (
    get_preferences_impl,
    update_preference_impl,
)


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_prefs_dir(tmp_path, monkeypatch):
    """Create isolated preferences directory."""
    config_dir = tmp_path / "config-data"
    config_dir.mkdir()

    monkeypatch.setattr(
        "src.mcp.augur_core.tools.core.preferences._get_preferences_path",
        lambda: config_dir / "preferences.yaml",
    )

    return config_dir


@pytest.fixture
def sample_prefs(temp_prefs_dir):
    """Create sample preferences file."""
    prefs_file = temp_prefs_dir / "preferences.yaml"
    prefs = {
        "theme": "dark",
        "language": "python",
        "editor": "vscode",
        "notifications": {"enabled": True, "sound": False},
    }
    prefs_file.write_text(yaml.dump(prefs))
    return prefs_file


# =============================================================================
# Contract Tests: get-preferences
# =============================================================================


@pytest.mark.contract
class TestGetPreferencesContract:
    """
    User Need: View personal preferences.

    Acceptance Criteria:
    1. User can get all preferences
    2. User can get specific key
    3. Missing key returns empty
    4. No prefs file returns empty dict
    """

    def test_user_can_get_all_preferences(self, sample_prefs):
        """User story: As a user, I can see all my preferences."""
        params = GetPreferencesInput()
        result = _run(get_preferences_impl(params))

        data = json.loads(result)
        assert "theme" in data
        assert "language" in data
        assert "editor" in data

    def test_user_can_get_specific_key(self, sample_prefs):
        """User story: As a user, I can get a specific preference."""
        params = GetPreferencesInput(key="theme")
        result = _run(get_preferences_impl(params))

        data = json.loads(result)
        assert "theme" in data
        assert data["theme"] == "dark"
        assert "language" not in data

    def test_missing_key_returns_empty(self, sample_prefs):
        """User story: As a user, I get empty for missing key."""
        params = GetPreferencesInput(key="nonexistent")
        result = _run(get_preferences_impl(params))

        data = json.loads(result)
        assert data == {}

    def test_no_file_returns_default_preferences(self, temp_prefs_dir):
        """User story: As a new user, I get default preference scaffolding."""
        params = GetPreferencesInput()
        result = _run(get_preferences_impl(params))

        data = json.loads(result)
        assert data == {
            "dispatch_targets": {
                "enabled_groups": None,
                "variant_overrides": {},
            }
        }

    def test_nested_preferences_work(self, sample_prefs):
        """User story: As a user, I can access nested prefs."""
        params = GetPreferencesInput(key="notifications")
        result = _run(get_preferences_impl(params))

        data = json.loads(result)
        assert "notifications" in data
        assert data["notifications"]["enabled"] is True


# =============================================================================
# Contract Tests: update-preference
# =============================================================================


@pytest.mark.contract
class TestUpdatePreferenceContract:
    """
    User Need: Update personal preferences.

    Acceptance Criteria:
    1. User can update existing preference
    2. User can add new preference
    3. Preference is persisted
    4. Returns success confirmation
    """

    def test_user_can_update_preference(self, sample_prefs):
        """User story: As a user, I can change my theme."""
        params = UpdatePreferenceInput(key="theme", value="light")
        result = _run(update_preference_impl(params))

        data = json.loads(result)
        assert data["success"] is True
        assert data["key"] == "theme"
        assert data["value"] == "light"

    def test_user_can_add_new_preference(self, sample_prefs):
        """User story: As a user, I can add new preferences."""
        params = UpdatePreferenceInput(key="new_key", value="new_value")
        result = _run(update_preference_impl(params))

        data = json.loads(result)
        assert data["success"] is True

        # Verify it's persisted
        get_params = GetPreferencesInput(key="new_key")
        get_result = _run(get_preferences_impl(get_params))
        get_data = json.loads(get_result)
        assert get_data["new_key"] == "new_value"

    def test_preference_is_persisted(self, sample_prefs):
        """User story: As a user, my changes are saved."""
        params = UpdatePreferenceInput(key="editor", value="neovim")
        _run(update_preference_impl(params))

        # Verify by loading file directly
        saved_prefs = yaml.safe_load(sample_prefs.read_text())
        assert saved_prefs["editor"] == "neovim"

    def test_can_set_complex_value(self, sample_prefs):
        """User story: As a user, I can set nested values."""
        params = UpdatePreferenceInput(key="new_nested", value={"enabled": True, "option": "value"})
        result = _run(update_preference_impl(params))

        data = json.loads(result)
        assert data["success"] is True

    def test_can_update_nested_preference_with_dotted_key(self, sample_prefs):
        """User story: As a user, I can update a nested preference via dotted key."""
        params = UpdatePreferenceInput(
            key="local_backends.ollama.model",
            value="qwen3.5:latest",
        )
        result = _run(update_preference_impl(params))

        data = json.loads(result)
        assert data["success"] is True
        assert data["key"] == "local_backends.ollama.model"
        assert data["value"] == "qwen3.5:latest"

        saved_prefs = yaml.safe_load(sample_prefs.read_text())
        assert saved_prefs["local_backends"]["ollama"]["model"] == "qwen3.5:latest"
        assert "local_backends.ollama.model" not in saved_prefs

        get_params = GetPreferencesInput(key="local_backends.ollama.model")
        get_result = _run(get_preferences_impl(get_params))
        get_data = json.loads(get_result)
        assert get_data["local_backends.ollama.model"] == "qwen3.5:latest"

    def test_creates_file_if_missing(self, temp_prefs_dir):
        """User story: As a new user, preferences file is created."""
        params = UpdatePreferenceInput(key="first_pref", value="first_value")
        result = _run(update_preference_impl(params))

        data = json.loads(result)
        assert data["success"] is True

        # File should be created
        prefs_file = temp_prefs_dir / "preferences.yaml"
        assert prefs_file.exists()


# =============================================================================
# Mock Path Config for Path Tools Tests
# =============================================================================


class MockPathCategory:
    def __init__(self, id: str, path: Path):
        self.id = id
        self.path = path
        self.git_root = path
        self.size_mb = 100.0
        self.gitignored = id == "runtime"


class MockPathConfig:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.categories = [
            MockPathCategory("core", base_path / "code"),
            MockPathCategory("data", base_path / "data"),
            MockPathCategory("plugins", base_path / "plugins"),
            MockPathCategory("runtime", base_path / "runtime"),
        ]
        self.is_monorepo = True
        self.repo_count = 1
        self.unique_git_roots = [base_path]

        class Alerts:
            large_file_mb = 50

        self.alerts = Alerts()

    def to_dict(self):
        return {
            "categories": {c.id: str(c.path) for c in self.categories},
            "is_monorepo": self.is_monorepo,
        }

    def get_category(self, id: str):
        for c in self.categories:
            if c.id == id:
                return c
        return None

    def refresh_sizes(self):
        pass


# =============================================================================
# Contract Tests: Path Config Tools
# =============================================================================


@pytest.mark.contract
class TestPathConfigContract:
    """
    User Need: Understand and manage path configuration.

    Acceptance Criteria:
    1. User can get current config
    2. User can validate paths
    3. User can see path sizes
    """

    def test_get_path_config_structure(self):
        """User story: As a user, I see path structure."""
        from src.mcp.augur_framework.tools.infrastructure.paths import register_path_tools

        mock_mcp = MagicMock()
        mock_metrics = MagicMock()
        registered_tools = {}

        def capture_tool(name, **kwargs):
            def decorator(func):
                registered_tools[name] = func
                return func

            return decorator

        mock_mcp.tool = capture_tool
        register_path_tools(mock_mcp, lambda f: f, mock_metrics)

        # Verify tools are registered
        assert "get-path-config" in registered_tools
        assert "validate-paths" in registered_tools
        assert "get-path-sizes" in registered_tools

    def test_validate_paths_structure(self):
        """User story: As a user, I can validate my paths."""
        from src.mcp.augur_framework.tools.infrastructure.paths import register_path_tools

        mock_mcp = MagicMock()
        mock_metrics = MagicMock()
        registered_tools = {}

        def capture_tool(name, **kwargs):
            def decorator(func):
                registered_tools[name] = func
                return func

            return decorator

        mock_mcp.tool = capture_tool
        register_path_tools(mock_mcp, lambda f: f, mock_metrics)

        # Tool should be registered
        assert "validate-paths" in registered_tools

    def test_get_path_sizes_structure(self):
        """User story: As a user, I can see directory sizes."""
        from src.mcp.augur_framework.tools.infrastructure.paths import register_path_tools

        mock_mcp = MagicMock()
        mock_metrics = MagicMock()
        registered_tools = {}

        def capture_tool(name, **kwargs):
            def decorator(func):
                registered_tools[name] = func
                return func

            return decorator

        mock_mcp.tool = capture_tool
        register_path_tools(mock_mcp, lambda f: f, mock_metrics)

        # Tool should be registered
        assert "get-path-sizes" in registered_tools
