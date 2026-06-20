"""
MCP Core Tool Contract Tests.

Tests verify each tool:
1. Accepts documented inputs
2. Returns documented output structure
3. Handles error cases gracefully

Run with: pytest packages/augur-mcp/tests/tools/test_core_tools.py -v
"""

import json
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mcp.augur_core.tools.core.health import (
    cache_control_impl,
    get_metrics_impl,
    health_check_impl,
)
from src.mcp.augur_core.tools.core.models import (
    CacheControlInput,
    FindSkillInput,
    GetSkillInput,
    ListSkillsInput,
    ResponseFormat,
)
from src.mcp.augur_core.tools.core.skills import (
    find_skill_impl,
    get_skill_impl,
    list_skills_impl,
)

# Import helpers from sibling conftest.py using a file-path loader so tests
# work with pytest --import-mode=importlib.
_helper_spec = importlib.util.spec_from_file_location(
    "mcp_test_helpers",
    Path(__file__).resolve().parents[1] / "conftest.py",
)
if _helper_spec is None or _helper_spec.loader is None:
    raise ImportError("Failed to load MCP test helpers from tests/packages/augur-mcp/conftest.py")
_helpers = importlib.util.module_from_spec(_helper_spec)
_helper_spec.loader.exec_module(_helpers)
assert_json_structure = _helpers.assert_json_structure
assert_mcp_error = _helpers.assert_mcp_error
assert_mcp_success = _helpers.assert_mcp_success

# =============================================================================
# list-skills Tool Tests
# =============================================================================


class TestListSkillsTool:
    """Contract tests for list-skills MCP tool.

    User need: Discover available skills to understand what the augur can do.
    """

    @pytest.mark.asyncio
    async def test_returns_json_with_skills_array(self, mock_skill_cache, mock_metrics, mock_registry_list_skills):
        """Happy path: Returns valid JSON with skills array and count."""
        params = ListSkillsInput(format=ResponseFormat.JSON)

        result = await list_skills_impl(params, mock_skill_cache, mock_metrics, mock_registry_list_skills)

        data = assert_mcp_success(result)
        assert_json_structure(data, ["skills", "count"])
        assert isinstance(data["skills"], list)
        assert data["count"] == len(data["skills"])
        assert data["count"] > 0

    @pytest.mark.asyncio
    async def test_skill_has_required_fields(self, mock_skill_cache, mock_metrics, mock_registry_list_skills):
        """Each skill in response has required metadata fields."""
        params = ListSkillsInput(format=ResponseFormat.JSON)

        result = await list_skills_impl(params, mock_skill_cache, mock_metrics, mock_registry_list_skills)

        data = json.loads(result)
        required_fields = [
            "name",
            "display_name",
            "description",
            "triggers",
            "token_estimate",
            "ownership",
            "upstream",
            "origin",
        ]

        for skill in data["skills"]:
            for field in required_fields:
                assert field in skill, f"Skill missing required field: {field}"

    @pytest.mark.asyncio
    async def test_returns_markdown_format(self, mock_skill_cache, mock_metrics, mock_registry_list_skills):
        """Returns markdown when format=markdown."""
        params = ListSkillsInput(format=ResponseFormat.MARKDOWN)

        result = await list_skills_impl(params, mock_skill_cache, mock_metrics, mock_registry_list_skills)

        assert "# Available Augur Skills" in result
        assert "## careers" in result
        assert "**Triggers**" in result

    @pytest.mark.asyncio
    async def test_uses_cache_when_available(self, mock_skill_cache, mock_metrics, mock_registry_list_skills):
        """Returns cached result when cache hit."""
        cached_result = '{"skills": [], "count": 0}'
        mock_skill_cache.get.return_value = cached_result
        params = ListSkillsInput(format=ResponseFormat.JSON)

        result = await list_skills_impl(params, mock_skill_cache, mock_metrics, mock_registry_list_skills)

        assert result == cached_result
        # Registry should not be called on cache hit
        # (registry_list_skills is a fixture function, so we verify via cache.get call)
        mock_skill_cache.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_registry_returns_empty_list(self, mock_skill_cache, mock_metrics):
        """Handles empty skill registry gracefully."""
        empty_registry = MagicMock(return_value=[])
        params = ListSkillsInput(format=ResponseFormat.JSON)

        result = await list_skills_impl(params, mock_skill_cache, mock_metrics, empty_registry)

        data = assert_mcp_success(result)
        assert data["skills"] == []
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_tracks_metrics(self, mock_skill_cache, mock_metrics, mock_registry_list_skills):
        """Tool usage is tracked in metrics."""
        params = ListSkillsInput(format=ResponseFormat.JSON)

        await list_skills_impl(params, mock_skill_cache, mock_metrics, mock_registry_list_skills)

        mock_metrics.track_tool.assert_called_once_with("list_skills")


# =============================================================================
# get-skill Tool Tests
# =============================================================================


class TestGetSkillTool:
    """Contract tests for get-skill MCP tool.

    User need: Load detailed documentation for a specific skill.
    """

    @pytest.fixture
    def mock_skill_with_content(self, sample_skill_entries, tmp_path):
        """Create a mock skill entry with readable SKILL.md file."""
        skill = sample_skill_entries[0]  # careers skill
        skill_dir = tmp_path / "skills" / skill.id
        skill_dir.mkdir(parents=True)

        skill_content = """# Career Consultant

Manage your career with AI assistance.

## Commands

- `/sync-jobs` - Sync job applications
- `/apply-job` - Apply to a job
"""
        (skill_dir / "SKILL.md").write_text(skill_content)
        skill.path = skill_dir
        return skill

    @pytest.mark.asyncio
    async def test_returns_skill_content(self, mock_skill_with_content, mock_metrics, mock_available_skill_ids):
        """Happy path: Returns SKILL.md content for valid skill."""

        def resolve(name, include_disabled=False):
            if name == mock_skill_with_content.id:
                return mock_skill_with_content
            return None

        params = GetSkillInput(skill_name="careers")

        result = await get_skill_impl(params, resolve, mock_available_skill_ids, mock_metrics)

        assert "# Career Consultant" in result
        assert "/sync-jobs" in result

    @pytest.mark.asyncio
    async def test_skill_not_found_returns_error(self, mock_metrics, mock_available_skill_ids):
        """Error case: Returns helpful error for unknown skill."""

        def resolve_none(name, include_disabled=False):
            return None

        params = GetSkillInput(skill_name="nonexistent-skill")

        result = await get_skill_impl(params, resolve_none, mock_available_skill_ids, mock_metrics)

        assert_mcp_error(result, "nonexistent-skill")
        assert "Available:" in result

    @pytest.mark.asyncio
    async def test_tracks_metrics_with_skill_name(
        self, mock_skill_with_content, mock_metrics, mock_available_skill_ids
    ):
        """Tool usage is tracked with skill name."""

        def resolve(name, include_disabled=False):
            return mock_skill_with_content if name == "careers" else None

        params = GetSkillInput(skill_name="careers")

        await get_skill_impl(params, resolve, mock_available_skill_ids, mock_metrics)

        mock_metrics.track_tool.assert_called_once_with("get_skill", skill="careers")


# =============================================================================
# find-skill Tool Tests
# =============================================================================


class TestFindSkillTool:
    """Contract tests for find-skill MCP tool.

    User need: Find the best skill for a natural language query.
    """

    @pytest.mark.asyncio
    async def test_returns_matches_for_valid_query(self, mock_skill_cache, mock_metrics, mock_registry_list_skills):
        """Happy path: Returns matching skills with scores."""
        params = FindSkillInput(query="prepare for job interview", top_k=3)

        result = await find_skill_impl(params, mock_skill_cache, mock_metrics, mock_registry_list_skills)

        data = assert_mcp_success(result)
        assert_json_structure(data, ["query", "matches"])
        assert data["query"] == "prepare for job interview"
        assert isinstance(data["matches"], list)

    @pytest.mark.asyncio
    async def test_matches_have_required_fields(self, mock_skill_cache, mock_metrics, mock_registry_list_skills):
        """Each match has skill name, score, and description."""
        params = FindSkillInput(query="code bug fix", top_k=3)

        result = await find_skill_impl(params, mock_skill_cache, mock_metrics, mock_registry_list_skills)

        data = json.loads(result)
        if data["matches"]:  # May have matches
            match = data["matches"][0]
            assert "skill" in match
            assert "score" in match
            assert "description" in match
            assert match["score"] > 0

    @pytest.mark.asyncio
    async def test_respects_top_k_limit(self, mock_skill_cache, mock_metrics, mock_registry_list_skills):
        """Returns at most top_k matches."""
        params = FindSkillInput(query="skill", top_k=1)

        result = await find_skill_impl(params, mock_skill_cache, mock_metrics, mock_registry_list_skills)

        data = json.loads(result)
        assert len(data["matches"]) <= 1

    @pytest.mark.asyncio
    async def test_no_matches_returns_empty_list(self, mock_skill_cache, mock_metrics):
        """Returns empty matches for query with no hits."""
        empty_registry = MagicMock(return_value=[])
        params = FindSkillInput(query="xyznonexistent", top_k=3)

        result = await find_skill_impl(params, mock_skill_cache, mock_metrics, empty_registry)

        data = assert_mcp_success(result)
        assert data["matches"] == []

    @pytest.mark.asyncio
    async def test_uses_cache(self, mock_skill_cache, mock_metrics, mock_registry_list_skills):
        """Returns cached result when available."""
        cached = '{"query": "test", "matches": []}'
        mock_skill_cache.get.return_value = cached
        params = FindSkillInput(query="test", top_k=3)

        result = await find_skill_impl(params, mock_skill_cache, mock_metrics, mock_registry_list_skills)

        assert result == cached


# =============================================================================
# health Tool Tests
# =============================================================================


class TestHealthTool:
    """Contract tests for health MCP tool.

    User need: Verify the MCP server is running and healthy.
    """

    @pytest.mark.asyncio
    async def test_returns_healthy_status(self, mock_skill_cache, mock_registry_list_skills):
        """Happy path: Returns ok status with metadata."""
        with patch("src.mcp.augur_core.tools.core.health._get_skills_dir") as mock_dir:
            mock_dir.return_value = Path("/mock/plugins")

            result = await health_check_impl(mock_skill_cache, mock_registry_list_skills)

        data = assert_mcp_success(result)
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert "version" in data
        assert "skills_loaded" in data
        assert "cache_entries" in data

    @pytest.mark.asyncio
    async def test_reports_skills_count(self, mock_skill_cache, mock_registry_list_skills):
        """Reports correct number of loaded skills."""
        with patch("src.mcp.augur_core.tools.core.health._get_skills_dir") as mock_dir:
            mock_dir.return_value = Path("/mock/plugins")

            result = await health_check_impl(mock_skill_cache, mock_registry_list_skills)

        data = json.loads(result)
        assert data["skills_loaded"] == 3  # From sample_skill_entries


# =============================================================================
# metrics Tool Tests
# =============================================================================


class TestMetricsTool:
    """Contract tests for metrics MCP tool.

    User need: View usage statistics and system health.
    """

    @pytest.mark.asyncio
    async def test_returns_usage_stats(self, mock_metrics):
        """Happy path: Returns usage statistics."""
        result = await get_metrics_impl(mock_metrics)

        data = assert_mcp_success(result)
        assert "tool_calls" in data
        assert "skill_usage" in data

    @pytest.mark.asyncio
    async def test_tracks_own_usage(self, mock_metrics):
        """Metrics tool tracks its own usage."""
        await get_metrics_impl(mock_metrics)

        mock_metrics.track_tool.assert_called_once_with("metrics")


# =============================================================================
# cache-control Tool Tests
# =============================================================================


class TestCacheControlTool:
    """Contract tests for cache-control MCP tool.

    User need: Manage skill cache for debugging and after manual edits.
    """

    @pytest.mark.asyncio
    async def test_stats_action_returns_cache_info(self, mock_skill_cache, mock_metrics):
        """Happy path: Stats action returns cache information."""
        params = CacheControlInput(action="stats")

        result = await cache_control_impl(params, mock_skill_cache, mock_metrics)

        data = assert_mcp_success(result)
        assert "keys" in data or "hits" in data or "misses" in data

    @pytest.mark.asyncio
    async def test_invalidate_clears_cache(self, mock_skill_cache, mock_metrics):
        """Invalidate action clears all cache entries."""
        params = CacheControlInput(action="invalidate")

        result = await cache_control_impl(params, mock_skill_cache, mock_metrics)

        data = assert_mcp_success(result)
        assert data["status"] == "cleared_all"
        mock_skill_cache.invalidate.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_skill_requires_skill_name(self, mock_skill_cache, mock_metrics):
        """Error case: invalidate_skill without skill_name returns error."""
        params = CacheControlInput(action="invalidate_skill", skill_name=None)

        result = await cache_control_impl(params, mock_skill_cache, mock_metrics)

        assert_mcp_error(result, "skill_name required")

    @pytest.mark.asyncio
    async def test_invalidate_skill_with_name(self, mock_skill_cache, mock_metrics):
        """Invalidate_skill with name clears specific skill."""
        params = CacheControlInput(action="invalidate_skill", skill_name="careers")

        result = await cache_control_impl(params, mock_skill_cache, mock_metrics)

        data = assert_mcp_success(result)
        assert "careers" in data["status"]
        mock_skill_cache.invalidate.assert_called_once_with("careers")

    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self, mock_skill_cache, mock_metrics):
        """Error case: Unknown action returns error."""
        params = CacheControlInput(action="unknown_action")

        result = await cache_control_impl(params, mock_skill_cache, mock_metrics)

        assert_mcp_error(result, "Unknown action")
