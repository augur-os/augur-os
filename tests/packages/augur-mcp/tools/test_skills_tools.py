"""
Skills/Modules MCP Tool Contract Tests.

User Need: Discover and load augur skills and their modules.

Run with: cd packages/augur-mcp && uv run pytest tests/tools/test_skills_tools.py -v
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from src.mcp.augur_core.tools.core.models import (
    FindSkillInput,
    GetSkillInput,
    ListSkillsInput,
    LoadModuleInput,
    LoadReferenceInput,
    ResponseFormat,
)
from src.mcp.augur_core.tools.core.skills import (
    find_skill_impl,
    get_config_impl,
    get_skill_impl,
    list_skills_impl,
    load_module_impl,
    load_reference_impl,
)

# =============================================================================
# Mock Classes
# =============================================================================


class MockSkillMeta:
    """Mock skill metadata."""

    def __init__(
        self,
        skill_id: str,
        description: str = "",
        triggers: list[str] = None,
        capabilities: list[str] = None,
        aliases: list[str] = None,
    ):
        self.id = skill_id
        self.name = skill_id  # Source code accesses .name
        self.display_name = skill_id.replace("-", " ").title()
        self.description = description or f"The {skill_id} skill"
        self.triggers = set(triggers or [skill_id])
        self.capabilities = set(capabilities or [])
        self.aliases = set(aliases or [])
        self.token_estimate = 500
        self.has_modules = True
        self.has_scripts = False
        self.has_references = True


class MockSkillEntry:
    """Mock skill entry for get/load operations."""

    def __init__(self, skill_id: str, path: Path):
        self.id = skill_id
        self.name = skill_id  # Source code accesses .name
        self.path = path
        self.aliases = set()


class MockSkillCache:
    """Mock skill cache."""

    def __init__(self):
        self.data = {}

    def get(self, key: str):
        return self.data.get(key)

    def set(self, key: str, value: str):
        self.data[key] = value


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_cache():
    """Create mock skill cache."""
    return MockSkillCache()


@pytest.fixture
def mock_metrics():
    """Create mock metrics tracker."""
    return MagicMock()


@pytest.fixture
def temp_skills_dir(tmp_path):
    """Create isolated skills directory with sample skills."""
    skills_dir = tmp_path / "plugins"
    skills_dir.mkdir()

    # Create developer skill
    developer_dir = skills_dir / "developer"
    developer_dir.mkdir()
    (developer_dir / "SKILL.md").write_text("""# Developer Skill

Helps with code development tasks.

## Commands
- `generate-code`: Generate code snippets
- `review-code`: Review code for issues
""")

    # Create modules
    modules_dir = developer_dir / "modules"
    modules_dir.mkdir()
    (modules_dir / "testing.md").write_text("# Testing Module\n\nGuidelines for testing.")
    (modules_dir / "debugging.md").write_text("# Debugging Module\n\nDebugging techniques.")

    # Create references
    refs_dir = developer_dir / "references"
    refs_dir.mkdir()
    (refs_dir / "setup.md").write_text("# Setup Guide\n\nHow to set up the environment.")

    # Create config
    config_dir = developer_dir / "config"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text("editor: vscode\nlanguage: python")

    # Create architect skill
    architect_dir = skills_dir / "architect"
    architect_dir.mkdir()
    (architect_dir / "SKILL.md").write_text("""# Architect Skill

Design system architecture.

## Commands
- `design`: Create system design
""")

    return skills_dir


@pytest.fixture
def sample_skill_metas():
    """Create sample skill metadata."""
    return [
        MockSkillMeta(
            "developer",
            description="Code development and implementation",
            triggers=["develop", "code", "implement"],
            capabilities=["code-generation", "review"],
        ),
        MockSkillMeta(
            "architect",
            description="System architecture and design",
            triggers=["design", "architecture", "plan"],
            capabilities=["design", "planning"],
        ),
        MockSkillMeta(
            "validator",
            description="Code validation and testing",
            triggers=["test", "validate", "check"],
        ),
    ]


@pytest.fixture
def mock_registry_list(sample_skill_metas):
    """Create mock registry list function."""

    def list_skills(plugins_dir=None):
        return sample_skill_metas

    return list_skills


# =============================================================================
# Contract Tests: list-skills
# =============================================================================


@pytest.mark.contract
class TestListSkillsContract:
    """
    User Need: Discover available skills to choose the right one.

    Acceptance Criteria:
    1. User can list all skills
    2. Skills have required metadata
    3. Both JSON and markdown formats work
    4. Results are cached
    """

    @pytest.mark.asyncio
    async def test_user_can_list_skills_json(self, mock_cache, mock_metrics, mock_registry_list):
        """User story: As a user, I can see all available skills."""
        params = ListSkillsInput(format=ResponseFormat.JSON)
        result = await list_skills_impl(params, mock_cache, mock_metrics, mock_registry_list)

        data = json.loads(result)
        assert "skills" in data
        assert "count" in data
        assert data["count"] == 3

    @pytest.mark.asyncio
    async def test_skills_have_required_fields(self, mock_cache, mock_metrics, mock_registry_list):
        """User story: As a user, each skill has essential info."""
        params = ListSkillsInput(format=ResponseFormat.JSON)
        result = await list_skills_impl(params, mock_cache, mock_metrics, mock_registry_list)

        data = json.loads(result)
        for skill in data["skills"]:
            assert "name" in skill
            assert "description" in skill
            assert "triggers" in skill
            assert "token_estimate" in skill
            assert "ownership" in skill
            assert "upstream" in skill
            assert "origin" in skill

    @pytest.mark.asyncio
    async def test_markdown_format_works(self, mock_cache, mock_metrics, mock_registry_list):
        """User story: As a user, I can get readable markdown list."""
        params = ListSkillsInput(format=ResponseFormat.MARKDOWN)
        result = await list_skills_impl(params, mock_cache, mock_metrics, mock_registry_list)

        assert "# Available Augur Skills" in result
        assert "## developer" in result
        assert "**Triggers**:" in result

    @pytest.mark.asyncio
    async def test_results_are_cached(self, mock_cache, mock_metrics, mock_registry_list):
        """User story: As a user, repeated calls are fast (cached)."""
        params = ListSkillsInput(format=ResponseFormat.JSON)

        # First call
        result1 = await list_skills_impl(params, mock_cache, mock_metrics, mock_registry_list)

        # Verify cache was set
        cache_key = f"list_skills:{params.format}:{params.ownership or 'all'}"
        assert mock_cache.get(cache_key) == result1

        # Second call should return cached
        result2 = await list_skills_impl(params, mock_cache, mock_metrics, mock_registry_list)
        assert result2 == result1

    @pytest.mark.asyncio
    async def test_metrics_tracked(self, mock_cache, mock_metrics, mock_registry_list):
        """User story: As an operator, usage is tracked."""
        params = ListSkillsInput()
        await list_skills_impl(params, mock_cache, mock_metrics, mock_registry_list)

        mock_metrics.track_tool.assert_called_once_with("list_skills")


# =============================================================================
# Contract Tests: get-skill
# =============================================================================


@pytest.mark.contract
class TestGetSkillContract:
    """
    User Need: Get detailed info about a specific skill.

    Acceptance Criteria:
    1. User can get skill documentation
    2. Unknown skill returns helpful error
    3. include_modules option works
    """

    @pytest.mark.asyncio
    async def test_user_can_get_skill(self, temp_skills_dir, mock_metrics):
        """User story: As a user, I can get skill details."""
        developer_path = temp_skills_dir / "developer"
        mock_entry = MockSkillEntry("developer", developer_path)

        def resolve(name):
            if name == "developer":
                return mock_entry
            return None

        def available_ids():
            return ["developer", "architect"]

        params = GetSkillInput(skill_name="developer")
        result = await get_skill_impl(params, resolve, available_ids, mock_metrics)

        assert "# Developer Skill" in result
        assert "generate-code" in result

    @pytest.mark.asyncio
    async def test_unknown_skill_returns_error(self, mock_metrics):
        """User story: As a user, unknown skill gives helpful error."""

        def resolve(name):
            return None

        def available_ids():
            return ["developer", "architect"]

        params = GetSkillInput(skill_name="nonexistent")
        result = await get_skill_impl(params, resolve, available_ids, mock_metrics)

        assert "Error" in result
        assert "nonexistent" in result
        assert "Available:" in result

    @pytest.mark.asyncio
    async def test_include_modules_shows_modules(self, temp_skills_dir, mock_metrics):
        """User story: As a user, I can see available modules."""
        developer_path = temp_skills_dir / "developer"
        mock_entry = MockSkillEntry("developer", developer_path)

        def resolve(name):
            return mock_entry

        def available_ids():
            return ["developer"]

        params = GetSkillInput(skill_name="developer", include_modules=True)
        result = await get_skill_impl(params, resolve, available_ids, mock_metrics)

        assert "## Available Modules" in result
        assert "testing" in result
        assert "debugging" in result
        assert "## Available References" in result
        assert "setup" in result


# =============================================================================
# Contract Tests: load-module
# =============================================================================


@pytest.mark.contract
class TestLoadModuleContract:
    """
    User Need: Load specific module documentation.

    Acceptance Criteria:
    1. User can load module content
    2. Unknown module returns helpful error
    3. Shows available modules on error
    """

    @pytest.mark.asyncio
    async def test_user_can_load_module(self, temp_skills_dir, mock_metrics, monkeypatch):
        """User story: As a user, I can load module documentation."""
        developer_path = temp_skills_dir / "developer"
        mock_entry = MockSkillEntry("developer", developer_path)

        # Patch data dir
        monkeypatch.setattr(
            "src.mcp.augur_core.tools.core.skills_docs._get_data_dir",
            lambda: temp_skills_dir.parent / "data",
        )

        def resolve(name):
            return mock_entry

        params = LoadModuleInput(skill_name="developer", module_name="testing")
        result = await load_module_impl(params, resolve, mock_metrics)

        assert "# Module: testing" in result
        assert "Testing Module" in result

    @pytest.mark.asyncio
    async def test_unknown_module_returns_error(self, temp_skills_dir, mock_metrics, monkeypatch):
        """User story: As a user, unknown module gives helpful error."""
        developer_path = temp_skills_dir / "developer"
        mock_entry = MockSkillEntry("developer", developer_path)

        monkeypatch.setattr(
            "src.mcp.augur_core.tools.core.skills_docs._get_data_dir",
            lambda: temp_skills_dir.parent / "data",
        )

        def resolve(name):
            return mock_entry

        params = LoadModuleInput(skill_name="developer", module_name="nonexistent")
        result = await load_module_impl(params, resolve, mock_metrics)

        assert "Error" in result
        assert "nonexistent" in result
        assert "Available:" in result

    @pytest.mark.asyncio
    async def test_unknown_skill_returns_error(self, mock_metrics, monkeypatch, tmp_path):
        """User story: As a user, unknown skill gives error."""
        monkeypatch.setattr(
            "src.mcp.augur_core.tools.core.skills_docs._get_data_dir",
            lambda: tmp_path / "data",
        )

        def resolve(name):
            return None

        params = LoadModuleInput(skill_name="nonexistent", module_name="test")
        result = await load_module_impl(params, resolve, mock_metrics)

        assert "Error" in result
        assert "nonexistent" in result


# =============================================================================
# Contract Tests: load-reference
# =============================================================================


@pytest.mark.contract
class TestLoadReferenceContract:
    """
    User Need: Load reference documentation for skills.

    Acceptance Criteria:
    1. User can load reference content
    2. Unknown reference returns helpful error
    """

    @pytest.mark.asyncio
    async def test_user_can_load_reference(self, temp_skills_dir):
        """User story: As a user, I can load reference docs."""
        developer_path = temp_skills_dir / "developer"
        mock_entry = MockSkillEntry("developer", developer_path)

        def resolve(name):
            return mock_entry

        params = LoadReferenceInput(skill_name="developer", reference_name="setup")
        result = await load_reference_impl(params, resolve)

        assert "# Setup Guide" in result

    @pytest.mark.asyncio
    async def test_unknown_reference_returns_error(self, temp_skills_dir):
        """User story: As a user, unknown ref gives helpful error."""
        developer_path = temp_skills_dir / "developer"
        mock_entry = MockSkillEntry("developer", developer_path)

        def resolve(name):
            return mock_entry

        params = LoadReferenceInput(skill_name="developer", reference_name="nonexistent")
        result = await load_reference_impl(params, resolve)

        assert "Error" in result
        assert "nonexistent" in result
        assert "Available:" in result

    @pytest.mark.asyncio
    async def test_unknown_skill_returns_error(self):
        """User story: As a user, unknown skill gives error."""

        def resolve(name):
            return None

        params = LoadReferenceInput(skill_name="nonexistent", reference_name="test")
        result = await load_reference_impl(params, resolve)

        assert "Error" in result
        assert "nonexistent" in result


# =============================================================================
# Contract Tests: get-config
# =============================================================================


@pytest.mark.contract
class TestGetConfigContract:
    """
    User Need: Get skill configuration.

    Acceptance Criteria:
    1. User can get skill config
    2. Missing config handled gracefully
    """

    @pytest.mark.asyncio
    async def test_user_can_get_config(self, temp_skills_dir, monkeypatch):
        """User story: As a user, I can get skill configuration."""
        developer_path = temp_skills_dir / "developer"
        mock_entry = MockSkillEntry("developer", developer_path)

        monkeypatch.setattr(
            "src.mcp.augur_core.tools.core.skills_docs._get_data_dir",
            lambda: temp_skills_dir.parent / "data",
        )

        def resolve(name, include_disabled=False):
            return mock_entry

        result = await get_config_impl("developer", resolve)

        assert "# Config:" in result
        assert "editor: vscode" in result

    @pytest.mark.asyncio
    async def test_missing_config_handled(self, temp_skills_dir, monkeypatch):
        """User story: As a user, missing config gives message."""
        # Architect skill has no config
        architect_path = temp_skills_dir / "architect"
        mock_entry = MockSkillEntry("architect", architect_path)

        monkeypatch.setattr(
            "src.mcp.augur_core.tools.core.skills_docs._get_data_dir",
            lambda: temp_skills_dir.parent / "data",
        )

        def resolve(name, include_disabled=False):
            return mock_entry

        result = await get_config_impl("architect", resolve)

        assert "No configuration found" in result


# =============================================================================
# Contract Tests: find-skill
# =============================================================================


@pytest.mark.contract
class TestFindSkillContract:
    """
    User Need: Find the best skill for a natural language query.

    Acceptance Criteria:
    1. User can search by natural language
    2. Returns scored matches
    3. Respects top_k parameter
    4. Results are cached
    """

    @pytest.mark.asyncio
    async def test_user_can_find_skill(self, mock_cache, mock_metrics, mock_registry_list):
        """User story: As a user, I can find skills by description."""
        params = FindSkillInput(query="help me write code")
        result = await find_skill_impl(params, mock_cache, mock_metrics, mock_registry_list)

        data = json.loads(result)
        assert "query" in data
        assert "matches" in data
        assert data["query"] == "help me write code"

    @pytest.mark.asyncio
    async def test_returns_scored_matches(self, mock_cache, mock_metrics, mock_registry_list):
        """User story: As a user, matches have relevance scores."""
        params = FindSkillInput(query="develop")
        result = await find_skill_impl(params, mock_cache, mock_metrics, mock_registry_list)

        data = json.loads(result)
        for match in data["matches"]:
            assert "skill" in match
            assert "score" in match
            assert "description" in match

    @pytest.mark.asyncio
    async def test_top_k_parameter_works(self, mock_cache, mock_metrics, mock_registry_list):
        """User story: As a user, I can limit results."""
        params = FindSkillInput(query="test", top_k=1)
        result = await find_skill_impl(params, mock_cache, mock_metrics, mock_registry_list)

        data = json.loads(result)
        assert len(data["matches"]) <= 1

    @pytest.mark.asyncio
    async def test_results_cached(self, mock_cache, mock_metrics, mock_registry_list):
        """User story: As a user, repeated searches are fast."""
        params = FindSkillInput(query="design system")

        result1 = await find_skill_impl(params, mock_cache, mock_metrics, mock_registry_list)

        cache_key = f"find:{params.query}:{params.top_k}"
        assert mock_cache.get(cache_key) == result1

    @pytest.mark.asyncio
    async def test_no_matches_returns_empty(self, mock_cache, mock_metrics):
        """User story: As a user, no matches returns empty list."""

        def empty_registry(plugins_dir=None):
            return []

        params = FindSkillInput(query="something random")
        result = await find_skill_impl(params, mock_cache, mock_metrics, empty_registry)

        data = json.loads(result)
        assert data["matches"] == []


# =============================================================================
# Input Validation Tests
# =============================================================================


@pytest.mark.contract
class TestInputValidation:
    """
    User Need: Get clear validation errors for bad input.

    Acceptance Criteria:
    1. Required fields are enforced
    2. Length limits are enforced
    """

    def test_get_skill_requires_name(self):
        """User story: As a user, I must provide skill name."""
        with pytest.raises(ValidationError):
            GetSkillInput()

    def test_skill_name_max_length(self):
        """User story: As a user, skill name has reasonable limit."""
        with pytest.raises(ValidationError):
            GetSkillInput(skill_name="a" * 100)

    def test_find_skill_min_query_length(self):
        """User story: As a user, query must be meaningful."""
        with pytest.raises(ValidationError):
            FindSkillInput(query="ab")

    def test_find_skill_top_k_bounds(self):
        """User story: As a user, top_k has reasonable limits."""
        # Valid
        FindSkillInput(query="test query", top_k=5)

        # Too high
        with pytest.raises(ValidationError):
            FindSkillInput(query="test query", top_k=100)

    def test_load_module_requires_both_params(self):
        """User story: As a user, I must provide both skill and module."""
        with pytest.raises(ValidationError):
            LoadModuleInput(skill_name="test")

        with pytest.raises(ValidationError):
            LoadModuleInput(module_name="test")
