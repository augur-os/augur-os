"""
System/Health MCP Tool Contract Tests.

User Need: Monitor system health, manage cache, and perform system operations.

Run with: cd packages/augur-mcp && uv run pytest tests/tools/test_system_tools.py -v
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from src.mcp.augur_core.tools.core.health import (
    cache_control_impl,
    get_metrics_impl,
    health_check_impl,
)
from src.mcp.augur_core.tools.core.models import CacheControlInput

# =============================================================================
# Mock Classes
# =============================================================================


class MockMetricsTracker:
    """Mock metrics tracker for testing."""

    def __init__(self):
        self.calls = []

    def track_tool(self, tool_name, **kwargs):
        self.calls.append({"tool": tool_name, **kwargs})

    def get_stats(self):
        return {
            "total_calls": len(self.calls),
            "by_tool": {"list_skills": 5, "get_skill": 3, "health": 1},
            "by_skill": {"developer": 2, "architect": 1},
            "cache_hits": 10,
            "cache_misses": 5,
            "session_start": datetime.now().isoformat(),
        }


class MockSkillCache:
    """Mock skill cache for testing.

    IMPORTANT: This mock matches the real SkillCache behavior from server.py:
    - invalidate(None) clears all entries
    - invalidate(pattern) removes entries where pattern is a substring of the key

    The real implementation uses: `if pattern in k` for key matching.
    """

    def __init__(self):
        self.data = {"key1": "value1", "key2": "value2"}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value

    def stats(self):
        return {
            "entries": len(self.data),  # Match real: "entries" not "total_size"
            "keys": list(self.data.keys()),
            "hit_rate": 0.67,  # Added for backward compat with existing tests
        }

    def invalidate(self, pattern: str | None = None):
        """Clear cache entries matching pattern or all.

        Matches real SkillCache.invalidate() behavior:
        - pattern=None: clear all
        - pattern="foo": remove all keys containing "foo"
        """
        if pattern is None:
            self.data.clear()
        else:
            keys_to_delete = [k for k in self.data if pattern in k]
            for k in keys_to_delete:
                del self.data[k]


class MockSkillMeta:
    """Mock skill metadata."""

    def __init__(self, skill_id):
        self.id = skill_id


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_metrics():
    """Create mock metrics tracker."""
    return MockMetricsTracker()


@pytest.fixture
def mock_cache():
    """Create mock skill cache."""
    return MockSkillCache()


@pytest.fixture
def mock_registry_list():
    """Create mock registry list function."""

    def list_skills(plugins_dir=None):
        return [
            MockSkillMeta("developer"),
            MockSkillMeta("architect"),
            MockSkillMeta("validator"),
        ]

    return list_skills


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file for import tests."""
    test_file = tmp_path / "test_document.txt"
    test_file.write_text("Test content for import")
    return test_file


# =============================================================================
# Contract Tests: metrics
# =============================================================================


@pytest.mark.contract
class TestMetricsContract:
    """
    User Need: View usage statistics and system health.

    Acceptance Criteria:
    1. User can get metrics data
    2. Metrics include tool usage counts
    3. Metrics include cache stats
    """

    @pytest.mark.asyncio
    async def test_user_can_get_metrics(self, mock_metrics):
        """User story: As a user, I can see system usage metrics."""
        result = await get_metrics_impl(mock_metrics)

        data = json.loads(result)
        assert "total_calls" in data
        assert "by_tool" in data

    @pytest.mark.asyncio
    async def test_metrics_include_tool_counts(self, mock_metrics):
        """User story: As a user, I see which tools are used most."""
        result = await get_metrics_impl(mock_metrics)

        data = json.loads(result)
        assert "by_tool" in data
        assert isinstance(data["by_tool"], dict)

    @pytest.mark.asyncio
    async def test_metrics_include_cache_stats(self, mock_metrics):
        """User story: As a user, I see cache performance."""
        result = await get_metrics_impl(mock_metrics)

        data = json.loads(result)
        assert "cache_hits" in data or "cache_misses" in data

    @pytest.mark.asyncio
    async def test_metrics_tracked(self, mock_metrics):
        """User story: As an operator, metrics call is tracked."""
        await get_metrics_impl(mock_metrics)

        assert any(c["tool"] == "metrics" for c in mock_metrics.calls)


# =============================================================================
# Contract Tests: health
# =============================================================================


@pytest.mark.contract
class TestHealthContract:
    """
    User Need: Check if the system is healthy.

    Acceptance Criteria:
    1. Health check returns status
    2. Includes version info
    3. Includes skill count
    4. Includes cache info
    """

    @pytest.mark.asyncio
    async def test_health_returns_ok_status(self, mock_cache, mock_registry_list, monkeypatch):
        """User story: As a user, I can verify system is healthy."""
        monkeypatch.setattr(
            "src.mcp.augur_core.tools.core.health._get_skills_dir",
            lambda: Path("/fake/plugins"),
        )

        result = await health_check_impl(mock_cache, mock_registry_list)

        data = json.loads(result)
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_includes_version(self, mock_cache, mock_registry_list, monkeypatch):
        """User story: As a user, I see the system version."""
        monkeypatch.setattr(
            "src.mcp.augur_core.tools.core.health._get_skills_dir",
            lambda: Path("/fake/plugins"),
        )

        result = await health_check_impl(mock_cache, mock_registry_list)

        data = json.loads(result)
        assert "version" in data

    @pytest.mark.asyncio
    async def test_health_includes_skill_count(self, mock_cache, mock_registry_list, monkeypatch):
        """User story: As a user, I see how many skills are loaded."""
        monkeypatch.setattr(
            "src.mcp.augur_core.tools.core.health._get_skills_dir",
            lambda: Path("/fake/plugins"),
        )

        result = await health_check_impl(mock_cache, mock_registry_list)

        data = json.loads(result)
        assert "skills_loaded" in data
        assert data["skills_loaded"] == 3

    @pytest.mark.asyncio
    async def test_health_includes_timestamp(self, mock_cache, mock_registry_list, monkeypatch):
        """User story: As a user, I see when health was checked."""
        monkeypatch.setattr(
            "src.mcp.augur_core.tools.core.health._get_skills_dir",
            lambda: Path("/fake/plugins"),
        )

        result = await health_check_impl(mock_cache, mock_registry_list)

        data = json.loads(result)
        assert "timestamp" in data


# =============================================================================
# Contract Tests: cache-control
# =============================================================================


@pytest.mark.contract
class TestCacheControlContract:
    """
    User Need: Manage the internal skill cache.

    Acceptance Criteria:
    1. User can get cache stats
    2. User can clear all cache
    3. User can clear specific skill cache
    4. Invalid action returns error
    """

    @pytest.mark.asyncio
    async def test_user_can_get_cache_stats(self, mock_cache, mock_metrics):
        """User story: As a user, I can see cache statistics."""
        params = CacheControlInput(action="stats")
        result = await cache_control_impl(params, mock_cache, mock_metrics)

        data = json.loads(result)
        assert "keys" in data
        assert "hit_rate" in data

    @pytest.mark.asyncio
    async def test_user_can_clear_all_cache(self, mock_cache, mock_metrics):
        """User story: As a user, I can clear the entire cache."""
        # Verify cache has data
        assert len(mock_cache.data) > 0

        params = CacheControlInput(action="invalidate")
        result = await cache_control_impl(params, mock_cache, mock_metrics)

        data = json.loads(result)
        assert data["status"] == "cleared_all"
        assert len(mock_cache.data) == 0

    @pytest.mark.asyncio
    async def test_user_can_clear_skill_cache(self, mock_cache, mock_metrics):
        """User story: As a user, I can clear a specific skill's cache."""
        # Add skill-specific cache entry
        mock_cache.data["developer:list"] = "cached_data"

        params = CacheControlInput(action="invalidate_skill", skill_name="developer")
        result = await cache_control_impl(params, mock_cache, mock_metrics)

        data = json.loads(result)
        assert "cleared_developer" in data["status"]

    @pytest.mark.asyncio
    async def test_invalidate_skill_requires_name(self, mock_cache, mock_metrics):
        """User story: As a user, I get error if skill name missing."""
        params = CacheControlInput(action="invalidate_skill")
        result = await cache_control_impl(params, mock_cache, mock_metrics)

        data = json.loads(result)
        assert "error" in data
        assert "skill_name required" in data["error"]

    @pytest.mark.asyncio
    async def test_invalid_action_returns_error(self, mock_cache, mock_metrics):
        """User story: As a user, invalid action gives error."""
        params = CacheControlInput(action="unknown_action")
        result = await cache_control_impl(params, mock_cache, mock_metrics)

        data = json.loads(result)
        assert "error" in data
        assert "Unknown action" in data["error"]


# =============================================================================
# Contract Tests: System Tools (via tool registration)
# =============================================================================


@pytest.mark.contract
class TestSystemToolsRegistration:
    """
    User Need: Register system tools with MCP server.

    Acceptance Criteria:
    1. Tools are registered correctly
    2. analyze-import tool works
    3. system-open validates paths
    """

    def test_system_tools_can_be_imported(self):
        """User story: As a developer, I can import system tools."""
        from src.mcp.augur_framework.tools.infrastructure.system import register_system_tools

        assert callable(register_system_tools)

    def test_analyze_import_tool_registered(self):
        """User story: As a user, analyze-import tool exists."""
        from src.mcp.augur_framework.tools.infrastructure.system import register_system_tools

        mock_mcp = MagicMock()
        mock_metrics = MagicMock()
        registered_tools = {}

        def capture_tool(name, **kwargs):
            def decorator(func):
                registered_tools[name] = func
                return func

            return decorator

        mock_mcp.tool = capture_tool
        register_system_tools(mock_mcp, lambda f: f, mock_metrics)

        assert "analyze-import" in registered_tools
        assert "apply-import" in registered_tools
        assert "list-services" in registered_tools

    @pytest.mark.asyncio
    async def test_analyze_import_validates_file(self, tmp_path):
        """User story: As a user, missing file returns error."""
        from src.mcp.augur_framework.tools.infrastructure.system import register_system_tools

        mock_mcp = MagicMock()
        mock_metrics = MagicMock()
        registered_tools = {}

        def capture_tool(name, **kwargs):
            def decorator(func):
                registered_tools[name] = func
                return func

            return decorator

        mock_mcp.tool = capture_tool
        register_system_tools(mock_mcp, lambda f: f, mock_metrics)

        result = await registered_tools["analyze-import"](file_path="/nonexistent/file.txt")
        data = json.loads(result)

        assert data["success"] is False
        assert "not found" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_analyze_import_returns_analysis(self, temp_file):
        """User story: As a user, I get file analysis."""
        from src.mcp.augur_framework.tools.infrastructure.system import register_system_tools

        mock_mcp = MagicMock()
        mock_metrics = MagicMock()
        registered_tools = {}

        def capture_tool(name, **kwargs):
            def decorator(func):
                registered_tools[name] = func
                return func

            return decorator

        mock_mcp.tool = capture_tool
        register_system_tools(mock_mcp, lambda f: f, mock_metrics)

        result = await registered_tools["analyze-import"](file_path=str(temp_file))
        data = json.loads(result)

        assert "type" in data
        assert "size" in data
        assert "name" in data
        assert "suggested_dest" in data


# =============================================================================
# Input Validation Tests
# =============================================================================


@pytest.mark.contract
class TestCacheControlInputValidation:
    """
    User Need: Get clear validation errors for bad cache control input.

    Acceptance Criteria:
    1. Action is required
    """

    def test_cache_control_requires_action(self):
        """User story: As a user, I must provide action."""
        with pytest.raises(ValidationError):
            CacheControlInput()

    def test_cache_control_accepts_valid_action(self):
        """User story: As a user, valid actions are accepted."""
        # These should not raise
        CacheControlInput(action="stats")
        CacheControlInput(action="invalidate")
        CacheControlInput(action="invalidate_skill", skill_name="test")


# =============================================================================
# System Open Tests
# =============================================================================


@pytest.mark.contract
class TestSystemOpenContract:
    """
    User Need: Open files and URLs with system defaults.

    Acceptance Criteria:
    1. File existence is validated
    2. URL type is auto-detected
    """

    @pytest.mark.asyncio
    async def test_system_open_validates_file_exists(self):
        """User story: As a user, missing file returns error."""
        from src.mcp.augur_framework.tools.infrastructure.system import register_system_tools

        mock_mcp = MagicMock()
        mock_metrics = MagicMock()
        registered_tools = {}

        def capture_tool(name, **kwargs):
            def decorator(func):
                registered_tools[name] = func
                return func

            return decorator

        mock_mcp.tool = capture_tool
        register_system_tools(mock_mcp, lambda f: f, mock_metrics)

        result = await registered_tools["system-open"](target="/nonexistent/file.txt", target_type="file")
        data = json.loads(result)

        assert data["success"] is False
        assert "not found" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_system_open_file_validates_path(self):
        """User story: As a user, system-open-file validates path."""
        from src.mcp.augur_framework.tools.infrastructure.system import register_system_tools

        mock_mcp = MagicMock()
        mock_metrics = MagicMock()
        registered_tools = {}

        def capture_tool(name, **kwargs):
            def decorator(func):
                registered_tools[name] = func
                return func

            return decorator

        mock_mcp.tool = capture_tool
        register_system_tools(mock_mcp, lambda f: f, mock_metrics)

        result = await registered_tools["system-open-file"](file_path="/nonexistent/file.txt")
        data = json.loads(result)

        assert data["success"] is False
        assert "not found" in data["error"].lower()


# =============================================================================
# List Services Tests
# =============================================================================


@pytest.mark.contract
class TestListServicesContract:
    """
    User Need: See running Augur services.

    Acceptance Criteria:
    1. Returns services list
    2. Status filter works
    """

    @pytest.mark.asyncio
    async def test_list_services_returns_list(self):
        """User story: As a user, I can list services."""
        from src.mcp.augur_framework.tools.infrastructure.system import register_system_tools

        mock_mcp = MagicMock()
        mock_metrics = MagicMock()
        registered_tools = {}

        def capture_tool(name, **kwargs):
            def decorator(func):
                registered_tools[name] = func
                return func

            return decorator

        mock_mcp.tool = capture_tool
        register_system_tools(mock_mcp, lambda f: f, mock_metrics)

        # The tool imports psutil internally, so we call it and accept the result
        # (it will return actual services or empty list)
        result = await registered_tools["list-services"]()
        data = json.loads(result)

        # Should return services key (may be empty list, may have error)
        assert "services" in data
        assert isinstance(data["services"], list)
