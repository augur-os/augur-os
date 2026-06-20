"""
Tests for context injection data models (context_models.py).

Validates dataclass construction, serialization (to_prompt, to_dict, to_markdown),
and file loading for UserPreferences, SprintContext, HumanApiProfile, AugurContext, etc.

Run with: pytest tests/packages/augur-mcp/test_context_models.py -v
"""

from datetime import datetime
from pathlib import Path

import pytest

from src.config.paths import invalidate_project_cache
from src.mcp.augur_shared.context_models import (
    AugurContext,
    FactoryInsights,
    HumanApiProfile,
    PluginEnrichment,
    SlashCommand,
    SprintContext,
    UserPreferences,
    VerticalState,
)


def _set_vault(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    invalidate_project_cache()


# =============================================================================
# UserPreferences
# =============================================================================


class TestUserPreferences:
    """Tests for UserPreferences dataclass."""

    def test_defaults(self):
        """Default preferences use English, UTC, no name."""
        prefs = UserPreferences()
        assert prefs.language == "en"
        assert prefs.timezone == "UTC"
        assert prefs.name is None
        assert prefs.custom == {}

    def test_custom_values(self):
        """Can set all fields."""
        prefs = UserPreferences(
            language="he",
            timezone="Asia/Jerusalem",
            name="Test User",
            custom={"theme": "dark"},
        )
        assert prefs.language == "he"
        assert prefs.name == "Test User"
        assert prefs.custom["theme"] == "dark"

    def test_load_missing_file(self, tmp_path: Path, monkeypatch):
        """load() returns defaults when preferences.yaml doesn't exist."""
        monkeypatch.setattr("src.config.preferences.load_preferences", lambda: {})
        prefs = UserPreferences.load()
        assert prefs.language == "en"

    def test_load_valid_file(self, tmp_path: Path, monkeypatch):
        """load() reads preferences from YAML file."""
        monkeypatch.setattr(
            "src.config.preferences.load_preferences",
            lambda: {
                "language": "he",
                "timezone": "Asia/Jerusalem",
                "name": "Test",
                "custom": {"theme": "dark"},
            },
        )
        prefs = UserPreferences.load()
        assert prefs.language == "he"
        assert prefs.timezone == "Asia/Jerusalem"
        assert prefs.name == "Test"
        assert prefs.custom == {"theme": "dark"}

    def test_load_corrupted_file(self, tmp_path: Path, monkeypatch):
        """load() returns defaults on corrupted YAML."""

        def raise_error():
            raise ValueError("invalid yaml")

        monkeypatch.setattr("src.config.preferences.load_preferences", raise_error)
        prefs = UserPreferences.load()
        assert prefs.language == "en"

    def test_load_empty_file(self, tmp_path: Path, monkeypatch):
        """load() returns defaults on empty file (yaml.safe_load returns None)."""
        monkeypatch.setattr("src.config.preferences.load_preferences", lambda: {})
        prefs = UserPreferences.load()
        assert prefs.language == "en"


# =============================================================================
# VerticalState
# =============================================================================


class TestVerticalState:
    """Tests for VerticalState dataclass."""

    def test_construction(self):
        """Basic construction with required and optional fields."""
        state = VerticalState(name="career", category="vertical")
        assert state.name == "career"
        assert state.category == "vertical"
        assert state.last_used is None
        assert state.recent_items == []
        assert state.metadata == {}

    def test_with_recent_items(self):
        """Can include recent items."""
        state = VerticalState(
            name="developer",
            category="vertical",
            recent_items=["fix bug #123", "implement auth"],
        )
        assert len(state.recent_items) == 2


# =============================================================================
# PluginEnrichment
# =============================================================================


class TestPluginEnrichment:
    """Tests for PluginEnrichment dataclass."""

    def test_defaults(self):
        """All lists default to empty."""
        enrichment = PluginEnrichment()
        assert enrichment.resolved_contexts == {}
        assert enrichment.available_providers == []
        assert enrichment.dependency_errors == []
        assert enrichment.memory_snippets == []
        assert enrichment.recent_voice_transcripts == []
        assert enrichment.active_collections == []
        assert enrichment.file_context == []


# =============================================================================
# FactoryInsights
# =============================================================================


class TestFactoryInsights:
    """Tests for FactoryInsights dataclass."""

    def test_defaults(self):
        """All lists default to empty."""
        insights = FactoryInsights()
        assert insights.architect_recommendations == []
        assert insights.developer_patterns == []
        assert insights.recent_adrs == []


# =============================================================================
# SprintContext
# =============================================================================


class TestSprintContext:
    """Tests for SprintContext serialization."""

    def test_defaults(self):
        """Default sprint has empty ID."""
        sprint = SprintContext()
        assert sprint.sprint_id == ""
        assert sprint.velocity == 0.0

    def test_to_markdown_no_sprint(self):
        """Empty sprint ID returns 'No active sprint'."""
        sprint = SprintContext()
        assert sprint.to_markdown() == "No active sprint"

    def test_to_markdown_with_data(self):
        """Populated sprint renders markdown with all sections."""
        sprint = SprintContext(
            sprint_id="S-42",
            sprint_goal="Launch MVP",
            velocity=21.0,
            capacity=30.0,
            committed_points=25.0,
            backlog_items=[
                {"title": "Auth module", "points": 5, "status": "in-progress"},
                {"title": "Dashboard UI", "points": 8, "status": "pending"},
            ],
        )
        md = sprint.to_markdown()
        assert "## Active Sprint: S-42" in md
        assert "**Goal**: Launch MVP" in md
        assert "Velocity: 21.0 points" in md
        assert "[in-progress] Auth module (5 pts)" in md
        assert "[pending] Dashboard UI (8 pts)" in md

    def test_to_markdown_limits_backlog_to_5(self):
        """Markdown output shows at most 5 backlog items."""
        items = [{"title": f"Item {i}", "points": 1, "status": "pending"} for i in range(10)]
        sprint = SprintContext(sprint_id="S-1", backlog_items=items)
        md = sprint.to_markdown()
        # Count the backlog item lines
        item_lines = [line for line in md.split("\n") if line.startswith("- [")]
        assert len(item_lines) == 5

    def test_to_dict(self):
        """to_dict returns structured dict with all fields."""
        sprint = SprintContext(
            sprint_id="S-42",
            sprint_goal="Launch MVP",
            velocity=21.0,
            capacity=30.0,
            committed_points=25.0,
        )
        d = sprint.to_dict()
        assert d["sprint_id"] == "S-42"
        assert d["sprint_goal"] == "Launch MVP"
        assert d["velocity"] == 21.0

    def test_to_dict_limits_backlog(self):
        """to_dict limits backlog_items to 5."""
        items = [{"title": f"Item {i}"} for i in range(10)]
        sprint = SprintContext(sprint_id="S-1", backlog_items=items)
        d = sprint.to_dict()
        assert len(d["backlog_items"]) == 5


# =============================================================================
# SlashCommand
# =============================================================================


class TestSlashCommand:
    """Tests for SlashCommand dataclass."""

    def test_construction(self):
        """Basic construction."""
        cmd = SlashCommand(name="dev-build", description="Build dashboard", category="workflow")
        assert cmd.name == "dev-build"
        assert cmd.description == "Build dashboard"
        assert cmd.category == "workflow"
        assert cmd.usage is None

    def test_with_usage(self):
        """Can include usage string."""
        cmd = SlashCommand(
            name="search",
            description="Search files",
            category="skill",
            usage="/search <query>",
        )
        assert cmd.usage == "/search <query>"


# =============================================================================
# HumanApiProfile
# =============================================================================


class TestHumanApiProfile:
    """Tests for HumanApiProfile loading and rendering."""

    def test_defaults(self):
        """Default profile is empty (not loaded)."""
        profile = HumanApiProfile()
        assert profile.exists is False
        assert profile.role == ""
        assert profile.expertise == []
        assert profile.raw_content == ""

    def test_load_missing_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """load() returns empty profile when profile-human-api.md doesn't exist."""
        _set_vault(monkeypatch, tmp_path)
        profile = HumanApiProfile.load(tmp_path)
        assert profile.exists is False

    def test_load_valid_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """load() extracts structured data from vault/wiki/profile-human-api.md."""
        _set_vault(monkeypatch, tmp_path)
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        profile_file = wiki / "profile-human-api.md"
        profile_file.write_text(
            "## Role\n"
            "Senior Engineer\n\n"
            "## Expertise\n"
            "- Python\n"
            "- TypeScript\n"
            "- System Design\n\n"
            "## Communication Style\n"
            "Concise, code-first\n\n"
            "## Success Criteria\n"
            "- Working code\n"
            "- Clean architecture\n\n"
            "## Context Gaps\n"
            "- Team norms\n"
            "- Deployment process\n"
        )
        profile = HumanApiProfile.load(tmp_path)
        assert profile.exists is True
        assert profile.role == "Senior Engineer"
        assert "Python" in profile.expertise
        assert "TypeScript" in profile.expertise
        assert profile.communication_style == "Concise, code-first"
        assert "Working code" in profile.success_criteria
        assert "Team norms" in profile.context_gaps

    def test_load_malformed_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """load() handles file with missing sections gracefully."""
        _set_vault(monkeypatch, tmp_path)
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        profile_file = wiki / "profile-human-api.md"
        profile_file.write_text("# Just a header\n\nSome text but no structured sections.\n")
        profile = HumanApiProfile.load(tmp_path)
        assert profile.exists is True
        assert profile.role == ""
        assert profile.expertise == []

    def test_load_generated_profile_format(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """load() supports the generated wiki query profile structure."""
        _set_vault(monkeypatch, tmp_path)
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        profile_file = wiki / "profile-human-api.md"
        profile_file.write_text(
            "## Role\n"
            "Founder and lead builder\n\n"
            "## Expertise\n"
            "- Dashboard delivery\n"
            "- MCP workflows\n\n"
            "## Communication Style\n"
            "Direct, concise responses with implementation-level detail.\n\n"
            "## Success Criteria\n"
            "- Verified changes\n"
            "- Root-cause fixes\n\n"
            "## Context Gaps\n"
            "- Current priority\n"
            "- In-bounds paths\n"
            "\n## Evidence\n"
            "MEMORY.md:42\n\n"
            "## Source Basis\n"
            "vault/memory/MEMORY.md\n"
        )

        profile = HumanApiProfile.load(tmp_path)

        assert profile.exists is True
        assert profile.role == "Founder and lead builder"
        assert profile.expertise == ["Dashboard delivery", "MCP workflows"]
        assert profile.communication_style == "Direct, concise responses with implementation-level detail."
        assert profile.success_criteria == ["Verified changes", "Root-cause fixes"]
        assert profile.context_gaps == ["Current priority", "In-bounds paths"]

    def test_to_prompt_section_empty(self):
        """Empty profile returns empty string for prompt."""
        profile = HumanApiProfile()
        assert profile.to_prompt_section() == ""

    def test_to_prompt_section_populated(self):
        """Populated profile renders markdown prompt section."""
        profile = HumanApiProfile(
            exists=True,
            role="CTO",
            expertise=["Architecture", "ML"],
            communication_style="Direct",
            success_criteria=["Ship fast"],
            context_gaps=["Budget"],
        )
        section = profile.to_prompt_section()
        assert "## Human API Profile" in section
        assert "**Role**: CTO" in section
        assert "Architecture" in section
        assert "**Prefers**: Direct" in section
        assert "Ship fast" in section
        assert "Budget" in section


# =============================================================================
# AugurContext
# =============================================================================


class TestAugurContext:
    """Tests for AugurContext prompt generation and serialization."""

    @pytest.fixture
    def minimal_context(self):
        """Create a minimal AugurContext."""
        return AugurContext(
            preferences=UserPreferences(),
            generated_at=datetime(2026, 3, 17, 12, 0),
        )

    @pytest.fixture
    def full_context(self):
        """Create a fully-populated AugurContext."""
        return AugurContext(
            preferences=UserPreferences(language="he", timezone="Asia/Jerusalem", name="Test"),
            human_api_profile=HumanApiProfile(exists=True, role="Engineer"),
            mode="dev",
            active_verticals=[
                VerticalState(name="career", category="vertical", recent_items=["Apply to job"]),
            ],
            plugin_enrichment=PluginEnrichment(
                memory_snippets=["User prefers dark mode"],
                active_collections=["career-docs"],
            ),
            factory_insights=FactoryInsights(
                architect_recommendations=["Use event-driven architecture"],
            ),
            sprint_context=SprintContext(sprint_id="S-42", sprint_goal="Launch"),
            slash_commands=[
                SlashCommand(name="dev-build", description="Build dashboard", category="workflow"),
                SlashCommand(name="career", description="Career tools", category="skill"),
            ],
            skill_hint="career",
            generated_at=datetime(2026, 3, 17, 12, 0),
        )

    def test_to_prompt_minimal(self, minimal_context: AugurContext):
        """Minimal context renders header and preferences."""
        prompt = minimal_context.to_prompt()
        assert "# Augur Context" in prompt
        assert "*Mode: ops*" in prompt
        assert "## User Preferences" in prompt
        assert "**Language**: en" in prompt

    def test_to_prompt_full(self, full_context: AugurContext):
        """Full context renders all sections."""
        prompt = full_context.to_prompt()
        assert "# Augur Context" in prompt
        assert "*Mode: dev*" in prompt
        assert "## Human API Profile" in prompt
        assert "**Name**: Test" in prompt
        assert "## Active Skills" in prompt
        assert "**career** (vertical)" in prompt
        assert "## Available Context" in prompt
        assert "### From Memory (RAG)" in prompt
        assert "## Factory Insights" in prompt
        assert "## Active Sprint: S-42" in prompt
        assert "## Available Commands" in prompt
        assert "### Workflows" in prompt
        assert "`/dev-build`" in prompt
        assert "### Skills" in prompt
        assert "`skill:career`" in prompt
        assert "## Skill Focus: career" in prompt

    def test_to_prompt_excludes_empty_sections(self, minimal_context: AugurContext):
        """Sections with no data are omitted from the prompt."""
        prompt = minimal_context.to_prompt()
        assert "## Active Skills" not in prompt
        assert "## Available Context" not in prompt
        assert "## Factory Insights" not in prompt
        assert "## Available Commands" not in prompt
        assert "## Skill Focus" not in prompt

    def test_to_dict_minimal(self, minimal_context: AugurContext):
        """Minimal context serializes to dict."""
        d = minimal_context.to_dict()
        assert d["mode"] == "ops"
        assert d["preferences"]["language"] == "en"
        assert d["active_verticals"] == []
        assert d["skill_hint"] is None
        assert "generated_at" in d

    def test_to_dict_full(self, full_context: AugurContext):
        """Full context serializes all fields to dict."""
        d = full_context.to_dict()
        assert d["mode"] == "dev"
        assert d["preferences"]["name"] == "Test"
        assert len(d["active_verticals"]) == 1
        assert d["active_verticals"][0]["name"] == "career"
        assert d["plugin_enrichment"]["memory_snippets_count"] == 1
        assert d["sprint_context"]["sprint_id"] == "S-42"
        assert len(d["slash_commands"]) == 2
        assert d["skill_hint"] == "career"

    def test_to_dict_limits_verticals(self):
        """to_dict limits active_verticals to 5."""
        ctx = AugurContext(
            preferences=UserPreferences(),
            active_verticals=[VerticalState(name=f"v{i}", category="vertical") for i in range(10)],
        )
        d = ctx.to_dict()
        assert len(d["active_verticals"]) == 5

    def test_to_dict_limits_slash_commands(self):
        """to_dict limits slash_commands to 20."""
        cmds = [SlashCommand(name=f"cmd{i}", description="test", category="workflow") for i in range(25)]
        ctx = AugurContext(preferences=UserPreferences(), slash_commands=cmds)
        d = ctx.to_dict()
        assert len(d["slash_commands"]) == 20
