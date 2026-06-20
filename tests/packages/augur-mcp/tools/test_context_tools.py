"""
Context/Design MCP Tool Contract Tests.

User Need: Get personalized context and design standards for development.

Run with: cd packages/augur-mcp && uv run pytest tests/tools/test_context_tools.py -v
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.mcp.augur_core.tools.core.context import (
    cross_skill_impl,
    get_context_impl,
    get_design_standards_impl,
)
from src.mcp.augur_core.tools.core.models import GetContextInput, ResponseFormat

# =============================================================================
# Mock Classes
# =============================================================================


class MockContext:
    """Mock context for testing."""

    def __init__(self):
        self.preferences = {"theme": "dark", "language": "python"}
        self.skill_hint = "developer"
        self.verticals = ["career", "health"]
        self.rag_snippets = ["# Code Pattern\nUse dependency injection..."]

    def to_dict(self):
        return {
            "preferences": self.preferences,
            "skill_hint": self.skill_hint,
            "verticals": self.verticals,
            "enrichment": {"rag_snippets": self.rag_snippets},
        }

    def to_prompt(self):
        return """# User Context

## Preferences
- Theme: dark
- Language: python

## Active Verticals
- career
- health

## RAG Enrichment
# Code Pattern
Use dependency injection...
"""


class MockContextInjector:
    """Mock context injector for testing."""

    def build_context(self, skill_hint: str = None):
        ctx = MockContext()
        if skill_hint:
            ctx.skill_hint = skill_hint
        return ctx


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_metrics():
    return MagicMock()


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def temp_standards_file(tmp_path):
    """Create temporary design standards file."""
    standards_dir = tmp_path / "apps" / "dashboard" / "docs" / "references"
    standards_dir.mkdir(parents=True)
    standards_file = standards_dir / "design-standards.md"
    standards_file.write_text("""# Design Standards

## Hub Page Rules
1. Overview tab MUST be first
2. No duplicate headers
3. Tabs ≠ Tool Cards

## Color Palette
- Primary: blue-500
- Background: slate-900
""")
    return tmp_path


# =============================================================================
# Contract Tests: get-context
# =============================================================================


@pytest.mark.contract
class TestGetContextContract:
    """
    User Need: Get personalized context for development.

    Acceptance Criteria:
    1. User gets preferences and history
    2. User gets vertical-specific data
    3. JSON and markdown formats work
    4. Skill hint filters context
    """

    @pytest.mark.asyncio
    async def test_user_gets_context(self, mock_metrics, mock_logger):
        """User story: As a user, I get personalized context."""
        with patch("src.mcp.augur_shared.context_injector.ContextInjector", MockContextInjector):
            params = GetContextInput(format=ResponseFormat.MARKDOWN)
            result = await get_context_impl(params, mock_metrics, mock_logger)

            assert "Preferences" in result
            assert "dark" in result
            assert "Verticals" in result

    @pytest.mark.asyncio
    async def test_json_format_works(self, mock_metrics, mock_logger):
        """User story: As a user, I can get JSON format."""
        with patch("src.mcp.augur_shared.context_injector.ContextInjector", MockContextInjector):
            params = GetContextInput(format=ResponseFormat.JSON)
            result = await get_context_impl(params, mock_metrics, mock_logger)

            data = json.loads(result)
            assert "preferences" in data
            assert "verticals" in data

    @pytest.mark.asyncio
    async def test_skill_hint_included(self, mock_metrics, mock_logger):
        """User story: As a user, I can specify skill context."""
        with patch("src.mcp.augur_shared.context_injector.ContextInjector", MockContextInjector):
            params = GetContextInput(skill_hint="architect", format=ResponseFormat.JSON)
            result = await get_context_impl(params, mock_metrics, mock_logger)

            data = json.loads(result)
            assert data["skill_hint"] == "architect"

    @pytest.mark.asyncio
    async def test_metrics_tracked(self, mock_metrics, mock_logger):
        """User story: As a user, my usage is tracked for improvement."""
        with patch("src.mcp.augur_shared.context_injector.ContextInjector", MockContextInjector):
            params = GetContextInput(skill_hint="developer")
            await get_context_impl(params, mock_metrics, mock_logger)

            mock_metrics.track_tool.assert_called_once_with("get_context", skill="developer")

    @pytest.mark.asyncio
    async def test_error_returns_helpful_message(self, mock_metrics, mock_logger):
        """User story: As a user, I get helpful error on failure."""
        with patch("src.mcp.augur_shared.context_injector.ContextInjector") as mock_injector:
            mock_injector.return_value.build_context.side_effect = Exception("Test error")

            params = GetContextInput()
            result = await get_context_impl(params, mock_metrics, mock_logger)

            data = json.loads(result)
            assert "error" in data
            assert "message" in data


# =============================================================================
# Contract Tests: get-design-standards
# =============================================================================


@pytest.mark.contract
class TestGetDesignStandardsContract:
    """
    User Need: Know UI design standards before making changes.

    Acceptance Criteria:
    1. User gets design standards content
    2. Fallback when file missing
    3. Contains hub page rules
    """

    @pytest.mark.asyncio
    async def test_user_gets_design_standards(self, mock_metrics, mock_logger, temp_standards_file):
        """User story: As a user, I see design standards before UI work."""
        with patch("src.mcp.augur_core.tools.core.context._get_project_root", return_value=temp_standards_file):
            result = await get_design_standards_impl(mock_metrics, mock_logger)

            assert "Design Standards" in result
            assert "Hub Page Rules" in result

    @pytest.mark.asyncio
    async def test_fallback_when_file_missing(self, mock_metrics, mock_logger, tmp_path):
        """User story: As a user, I get fallback content if file missing."""
        with patch("src.mcp.augur_core.tools.core.context._get_project_root", return_value=tmp_path):
            result = await get_design_standards_impl(mock_metrics, mock_logger)

            # Should get fallback with quick rules
            assert "Quick Rules" in result
            assert "Overview tab" in result

    @pytest.mark.asyncio
    async def test_contains_critical_rules(self, mock_metrics, mock_logger, temp_standards_file):
        """User story: As a user, I see critical rules."""
        with patch("src.mcp.augur_core.tools.core.context._get_project_root", return_value=temp_standards_file):
            result = await get_design_standards_impl(mock_metrics, mock_logger)

            assert "Overview" in result
            assert "duplicate" in result.lower() or "header" in result.lower()

    @pytest.mark.asyncio
    async def test_metrics_tracked(self, mock_metrics, mock_logger, temp_standards_file):
        """User story: As a user, my usage is tracked."""
        with patch("src.mcp.augur_core.tools.core.context._get_project_root", return_value=temp_standards_file):
            await get_design_standards_impl(mock_metrics, mock_logger)

            mock_metrics.track_tool.assert_called_once_with("get_design_standards")


# =============================================================================
# Contract Tests: cross-skill
# =============================================================================


@pytest.mark.contract
class TestCrossSkillContract:
    """
    User Need: Understand how to integrate skills.

    Acceptance Criteria:
    1. Known integrations return guidance
    2. Unknown integrations return helpful advice
    3. Response is valid JSON
    """

    @pytest.mark.asyncio
    async def test_known_integration_returns_guidance(self, mock_metrics):
        """User story: As a user, I get integration guidance."""
        result = await cross_skill_impl("job-analyzer", "interview-prep", mock_metrics)

        data = json.loads(result)
        assert "type" in data
        assert "workflow" in data

    @pytest.mark.asyncio
    async def test_unknown_integration_returns_advice(self, mock_metrics):
        """User story: As a user, I get advice for unknown integrations."""
        result = await cross_skill_impl("unknown-skill", "other-skill", mock_metrics)

        data = json.loads(result)
        assert data["status"] == "no_direct_integration_known"
        assert "advice" in data

    @pytest.mark.asyncio
    async def test_response_is_valid_json(self, mock_metrics):
        """User story: As a user, I get valid JSON response."""
        result = await cross_skill_impl("ideas-capture", "project-planner", mock_metrics)

        # Should not raise
        data = json.loads(result)
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_metrics_tracked(self, mock_metrics):
        """User story: As a user, my usage is tracked."""
        await cross_skill_impl("skill-a", "skill-b", mock_metrics)

        mock_metrics.track_tool.assert_called_once_with("cross_skill")
