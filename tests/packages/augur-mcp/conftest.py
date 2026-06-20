"""
MCP Tool Test Configuration and Fixtures.

Shared fixtures for testing MCP tools across the augur.
These fixtures can be imported by plugin tests via:

    from packages.augur_mcp.tests.conftest import mock_skill_cache, ...

Or pytest will auto-discover them when running from the repo root.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

MONOREPO_ROOT = Path(__file__).parent.parent.parent.parent
ROOT_SCRIPTS = MONOREPO_ROOT / "scripts" / "__init__.py"


def _prefer_repo_root_scripts_package() -> None:
    if str(MONOREPO_ROOT) in sys.path:
        sys.path.remove(str(MONOREPO_ROOT))
    sys.path.insert(0, str(MONOREPO_ROOT))

    loaded_scripts = sys.modules.get("scripts")
    if loaded_scripts is not None and Path(getattr(loaded_scripts, "__file__", "")).resolve() != ROOT_SCRIPTS:
        sys.modules.pop("scripts", None)


_prefer_repo_root_scripts_package()


@pytest.fixture(autouse=True)
def _restore_repo_root_scripts_package():
    _prefer_repo_root_scripts_package()


# =============================================================================
# Path Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def mcp_repo_root() -> Path:
    """Return the augur-mcp package root."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def monorepo_root() -> Path:
    """Return the monorepo root directory."""
    return Path(__file__).parent.parent.parent.parent


@pytest.fixture
def mcp_test_data_dir(tmp_path: Path) -> Path:
    """Create isolated test data directory for MCP tests.

    Creates standard subdirectories expected by MCP tools.
    """
    data_dir = tmp_path / "augur-data"
    data_dir.mkdir()

    # Create standard subdirectories
    (data_dir / "runtime" / "logs").mkdir(parents=True)
    (data_dir / "config").mkdir()
    (data_dir / "cache").mkdir()
    (data_dir / "crew").mkdir()

    return data_dir


# =============================================================================
# Mock Skill Metadata
# =============================================================================


@dataclass
class MockSkillEntry:
    """Mock skill entry matching the SkillEntry interface."""

    id: str
    display_name: str
    description: str
    triggers: tuple[str, ...]
    capabilities: tuple[str, ...]
    token_estimate: int
    has_modules: bool
    has_scripts: bool
    has_references: bool
    aliases: tuple[str, ...]
    path: Path | None = None

    @property
    def name(self) -> str:
        """Source code accesses .name (matches SkillRecord interface)."""
        return self.id

    def __post_init__(self):
        if self.path is None:
            # Create a mock path
            self.path = Path(f"/mock/plugins/skills/{self.id}")


@pytest.fixture
def sample_skill_entries() -> list[MockSkillEntry]:
    """Sample skill entries for testing list-skills and find-skill."""
    return [
        MockSkillEntry(
            id="careers",
            display_name="Career Consultant",
            description="Manage job applications, track interviews, and prepare for career moves.",
            triggers=("job", "career", "interview", "resume"),
            capabilities=("sync_jobs", "apply_job", "track_interview"),
            token_estimate=1500,
            has_modules=True,
            has_scripts=False,
            has_references=True,
            aliases=("career", "jobs"),
        ),
        MockSkillEntry(
            id="developer",
            display_name="Developer",
            description="Implement features, fix bugs, and manage code quality.",
            triggers=("code", "implement", "fix", "bug"),
            capabilities=("implement_feature", "fix_bug", "code_review"),
            token_estimate=2000,
            has_modules=True,
            has_scripts=True,
            has_references=True,
            aliases=("dev", "coding"),
        ),
        MockSkillEntry(
            id="rag",
            display_name="RAG System",
            description="Index and search documents using retrieval-augmented generation.",
            triggers=("search", "index", "documents", "rag"),
            capabilities=("index_documents", "search", "stats"),
            token_estimate=1000,
            has_modules=False,
            has_scripts=True,
            has_references=False,
            aliases=("search", "docs"),
        ),
    ]


# =============================================================================
# Mock Dependencies
# =============================================================================


@pytest.fixture
def mock_skill_cache() -> MagicMock:
    """Mock skill cache for testing.

    Default behavior: cache miss (returns None).
    Tests can override with: mock_skill_cache.get.return_value = "cached_result"
    """
    cache = MagicMock()
    cache.get = MagicMock(return_value=None)  # Cache miss by default
    cache.set = MagicMock()
    cache.stats = MagicMock(return_value={"keys": [], "hits": 0, "misses": 0})
    cache.invalidate = MagicMock()
    return cache


@pytest.fixture
def mock_metrics() -> MagicMock:
    """Mock metrics tracker for testing."""
    metrics = MagicMock()
    metrics.track_tool = MagicMock()
    metrics.get_stats = MagicMock(
        return_value={
            "tool_calls": {},
            "skill_usage": {},
            "errors": [],
            "sessions": 1,
        }
    )
    return metrics


@pytest.fixture
def mock_registry_list_skills(sample_skill_entries: list[MockSkillEntry]):
    """Mock registry_list_skills function."""

    def _list_skills(plugins_dir: Path | None = None) -> list[MockSkillEntry]:
        return sample_skill_entries

    return _list_skills


@pytest.fixture
def mock_resolve_skill_entry(sample_skill_entries: list[MockSkillEntry]):
    """Mock resolve_skill_entry function."""
    skill_map = {entry.id: entry for entry in sample_skill_entries}
    # Also map aliases
    for entry in sample_skill_entries:
        for alias in entry.aliases:
            skill_map[alias] = entry

    def _resolve(skill_name: str, include_disabled: bool = False) -> MockSkillEntry | None:
        return skill_map.get(skill_name)

    return _resolve


@pytest.fixture
def mock_available_skill_ids(sample_skill_entries: list[MockSkillEntry]):
    """Mock available_skill_ids function."""

    def _available() -> list[str]:
        return [entry.id for entry in sample_skill_entries]

    return _available


@pytest.fixture
def mock_logger() -> MagicMock:
    """Mock logger for testing."""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.debug = MagicMock()
    return logger


# =============================================================================
# Assertion Helpers
# =============================================================================


def assert_mcp_success(result: str) -> dict[str, Any]:
    """Assert MCP tool returned a successful JSON response.

    Args:
        result: JSON string from MCP tool

    Returns:
        Parsed JSON data

    Raises:
        AssertionError: If result contains an error or is invalid JSON
    """
    try:
        data = json.loads(result)
    except json.JSONDecodeError as e:
        raise AssertionError(f"MCP tool returned invalid JSON: {e}\nResult: {result[:500]}") from e

    if "error" in data and data.get("success") is False:
        raise AssertionError(f"MCP tool returned error: {data.get('error')}")

    return data


def assert_mcp_error(result: str, expected_substring: str | None = None) -> dict[str, Any] | str:
    """Assert MCP tool returned an error response.

    Args:
        result: Response string from MCP tool (may be JSON or plain text)
        expected_substring: Optional substring expected in error message

    Returns:
        Parsed data (dict if JSON, str if plain text error)

    Raises:
        AssertionError: If result does not indicate an error
    """
    # Try to parse as JSON first
    try:
        data = json.loads(result)
        has_error = "error" in data or data.get("success") is False
        if not has_error:
            raise AssertionError(f"Expected error but got success: {data}")

        if expected_substring:
            error_msg = data.get("error", "")
            if expected_substring.lower() not in error_msg.lower():
                raise AssertionError(f"Expected '{expected_substring}' in error message, got: {error_msg}")
        return data
    except json.JSONDecodeError:
        # Plain text error (like "Error: Skill 'foo' not found")
        if "Error" not in result and "error" not in result.lower():
            raise AssertionError(f"Expected error response, got: {result[:200]}") from None

        if expected_substring and expected_substring.lower() not in result.lower():
            raise AssertionError(f"Expected '{expected_substring}' in error message, got: {result[:200]}") from None
        return result


def assert_json_structure(data: dict, required_keys: list[str]) -> None:
    """Assert JSON data contains required keys.

    Args:
        data: Parsed JSON data
        required_keys: List of keys that must be present

    Raises:
        AssertionError: If any required key is missing
    """
    missing = [key for key in required_keys if key not in data]
    if missing:
        raise AssertionError(f"Missing required keys: {missing}. Got keys: {list(data.keys())}")


# =============================================================================
# Environment Setup
# =============================================================================


@pytest.fixture(autouse=True)
def mcp_test_environment(mcp_test_data_dir: Path, monkeypatch):
    """Setup test environment for MCP tests.

    Auto-applied to every test to ensure isolation.
    """
    monkeypatch.setenv("AUGUR_DATA_DIR", str(mcp_test_data_dir))
    monkeypatch.setenv("AUGUR_TEST_MODE", "true")

    # Reset config if available
    try:
        from src.mcp.augur_shared.config import reset_config

        reset_config()
    except ImportError:
        pass


# =============================================================================
# Export Helpers for Use in Plugin Tests
# =============================================================================


__all__ = [
    # Fixtures (auto-discovered by pytest)
    "mcp_repo_root",
    "monorepo_root",
    "mcp_test_data_dir",
    "sample_skill_entries",
    "mock_skill_cache",
    "mock_metrics",
    "mock_registry_list_skills",
    "mock_resolve_skill_entry",
    "mock_available_skill_ids",
    "mock_logger",
    "mcp_test_environment",
    # Helpers (import explicitly)
    "assert_mcp_success",
    "assert_mcp_error",
    "assert_json_structure",
    "MockSkillEntry",
]
