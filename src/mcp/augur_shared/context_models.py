"""
Data models for the Context Injector.

Contains all dataclass definitions used by the context injection system:
- UserPreferences
- VerticalState
- PluginEnrichment
- FactoryInsights
- SprintContext
- SlashCommand
- HumanApiProfile
- AugurContext
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.mcp.augur_shared.logging import get_entity_logger

logger = get_entity_logger("mcp.context.models")

_H2_SECTION_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)


@dataclass
class UserPreferences:
    """User preferences from the runtime preferences file."""

    language: str = "en"
    timezone: str = "UTC"
    name: str | None = None
    custom: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls) -> UserPreferences:
        """Load preferences from config file."""
        try:
            from src.config.preferences import load_preferences

            data = load_preferences()

            return cls(
                language=data.get("language", "en"),
                timezone=data.get("timezone", "UTC"),
                name=data.get("name"),
                custom=data.get("custom", {}),
            )
        except Exception:
            return cls()


@dataclass
class VerticalState:
    """State of an active vertical skill."""

    name: str
    category: str  # vertical, horizontal, factory
    last_used: datetime | None = None
    recent_items: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginEnrichment:
    """Data enrichment from plugin dependencies.

    Populated by resolving dependencies declared in SKILL.md:
    - resolved_contexts: Context from dependency plugins
    - available_providers: List of plugins that provide context
    """

    resolved_contexts: dict[str, dict[str, Any]] = field(default_factory=dict)
    available_providers: list[str] = field(default_factory=list)
    dependency_errors: list[str] = field(default_factory=list)

    # Legacy fields (kept for compatibility, will be removed)
    memory_snippets: list[str] = field(default_factory=list)
    recent_voice_transcripts: list[str] = field(default_factory=list)
    active_collections: list[str] = field(default_factory=list)
    file_context: list[str] = field(default_factory=list)


@dataclass
class FactoryInsights:
    """Insights and recommendations from factory agents."""

    architect_recommendations: list[str] = field(default_factory=list)
    developer_patterns: list[str] = field(default_factory=list)
    recent_adrs: list[str] = field(default_factory=list)


@dataclass
class SprintContext:
    """Active sprint information for agent injection."""

    sprint_id: str = ""
    sprint_goal: str = ""
    velocity: float = 0.0
    capacity: float = 0.0
    committed_points: float = 0.0
    backlog_items: list[dict[str, Any]] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Format sprint context as markdown for CLI agents."""
        if not self.sprint_id:
            return "No active sprint"

        md = f"""## Active Sprint: {self.sprint_id}

**Goal**: {self.sprint_goal}

**Metrics**:
- Velocity: {self.velocity} points
- Capacity: {self.capacity} points
- Committed: {self.committed_points} points

**Top Backlog Items**:
"""
        for item in self.backlog_items[:5]:
            title = item.get("title", "Untitled")
            points = item.get("points", "?")
            status = item.get("status", "pending")
            md += f"- [{status}] {title} ({points} pts)\n"

        return md

    def to_dict(self) -> dict[str, Any]:
        """Format sprint context as dict for SDK agents."""
        return {
            "sprint_id": self.sprint_id,
            "sprint_goal": self.sprint_goal,
            "velocity": self.velocity,
            "capacity": self.capacity,
            "committed_points": self.committed_points,
            "backlog_items": self.backlog_items[:5],
        }


@dataclass
class SlashCommand:
    """Slash command definition."""

    name: str
    description: str
    category: str  # workflow, skill, manual
    usage: str | None = None


@dataclass
class HumanApiProfile:
    """Human API Profile - user's interface definition for AI interactions (ADR-030)."""

    exists: bool = False
    role: str = ""
    expertise: list[str] = field(default_factory=list)
    communication_style: str = ""
    success_criteria: list[str] = field(default_factory=list)
    context_gaps: list[str] = field(default_factory=list)
    raw_content: str = ""

    @classmethod
    def load(cls, data_dir: Path) -> HumanApiProfile:
        """Load Human API profile from the wiki query output."""
        try:
            from src.config.paths import get_vault_dir

            profile_path = get_vault_dir() / "wiki" / "profile-human-api.md"
        except Exception:
            return cls()

        if not profile_path.exists():
            return cls()
        try:
            content = profile_path.read_text(encoding="utf-8")
            profile = cls(exists=True, raw_content=content)
            sections = _extract_h2_sections(content)
            profile.role = _first_text(sections.get("Role", ""))
            profile.expertise = _list_items(sections.get("Expertise", ""))
            profile.communication_style = _normalize_text(sections.get("Communication Style", ""))
            profile.success_criteria = _list_items(sections.get("Success Criteria", ""))
            profile.context_gaps = _list_items(sections.get("Context Gaps", ""))

            return profile
        except Exception:
            return cls()

    def to_prompt_section(self) -> str:
        """Format as prompt section."""
        if not self.exists:
            return ""

        lines = ["## Human API Profile (Who You're Working With)"]
        if self.role:
            lines.append(f"- **Role**: {self.role}")
        if self.expertise:
            lines.append(f"- **Expertise**: {', '.join(self.expertise[:3])}")
        if self.communication_style:
            lines.append(f"- **Prefers**: {self.communication_style}")
        if self.success_criteria:
            lines.append("- **Success looks like**: " + "; ".join(self.success_criteria[:3]))
        if self.context_gaps:
            lines.append("- **Ask about**: " + ", ".join(self.context_gaps[:3]))
        lines.append("")
        return "\n".join(lines)


def _extract_h2_sections(content: str) -> dict[str, str]:
    matches = list(_H2_SECTION_RE.finditer(content))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = match.group("title").strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        sections[title] = content[start:end].strip()
    return sections


def _normalize_text(section: str) -> str:
    return " ".join(line.strip() for line in section.splitlines() if line.strip())


def _first_text(section: str) -> str:
    for paragraph in section.split("\n\n"):
        text = _normalize_text(paragraph)
        if text:
            return text
    return ""


def _list_items(section: str) -> list[str]:
    items: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            item = stripped[2:].strip()
            if item:
                items.append(item)
    if items:
        return items
    text = _normalize_text(section)
    return [text] if text else []


@dataclass
class AugurContext:
    """
    Complete context package for IDE agents.

    This is what makes Augur valuable - the IDE agent receives
    enriched, personalized context that creates mind-blowing apps
    instead of generic mocks.
    """

    preferences: UserPreferences
    human_api_profile: HumanApiProfile = field(default_factory=HumanApiProfile)
    mode: str = "ops"  # ADR-030: Current operating mode (dev/ops)
    active_verticals: list[VerticalState] = field(default_factory=list)
    plugin_enrichment: PluginEnrichment = field(default_factory=PluginEnrichment)
    factory_insights: FactoryInsights = field(default_factory=FactoryInsights)
    sprint_context: SprintContext | None = None
    slash_commands: list[SlashCommand] = field(default_factory=list)
    skill_hint: str | None = None
    generated_at: datetime = field(default_factory=datetime.now)

    def to_prompt(self) -> str:
        """
        Convert context to a prompt string for IDE agents.

        Returns:
            Markdown-formatted context ready for injection into prompts.
        """
        sections = []

        # Header
        sections.append("# Augur Context")
        sections.append(f"*Generated: {self.generated_at.strftime('%Y-%m-%d %H:%M')}*")
        sections.append(f"*Mode: {self.mode}*\n")

        # Human API Profile (ADR-030) - Include first for immediate context
        if self.human_api_profile.exists:
            sections.append(self.human_api_profile.to_prompt_section())

        # User Preferences
        sections.append("## User Preferences")
        if self.preferences.name:
            sections.append(f"- **Name**: {self.preferences.name}")
        sections.append(f"- **Language**: {self.preferences.language}")
        sections.append(f"- **Timezone**: {self.preferences.timezone}")
        if self.preferences.custom:
            for key, value in self.preferences.custom.items():
                sections.append(f"- **{key}**: {value}")
        sections.append("")

        # Active Verticals
        if self.active_verticals:
            sections.append("## Active Skills")
            for vertical in self.active_verticals[:5]:  # Limit to 5
                sections.append(f"- **{vertical.name}** ({vertical.category})")
                if vertical.recent_items:
                    for item in vertical.recent_items[:3]:
                        sections.append(f"  - {item}")
            sections.append("")

        # Horizontal Enrichment
        enrichment = self.plugin_enrichment
        if any(
            [
                enrichment.memory_snippets,
                enrichment.recent_voice_transcripts,
                enrichment.active_collections,
            ]
        ):
            sections.append("## Available Context")

            if enrichment.memory_snippets:
                sections.append("### From Memory (RAG)")
                for snippet in enrichment.memory_snippets[:5]:
                    sections.append(f"- {snippet[:200]}...")
                sections.append("")

            if enrichment.recent_voice_transcripts:
                sections.append("### Recent Voice Notes")
                for transcript in enrichment.recent_voice_transcripts[:3]:
                    sections.append(f"- {transcript[:150]}...")
                sections.append("")

            if enrichment.active_collections:
                sections.append("### Active Collections")
                for collection in enrichment.active_collections[:5]:
                    sections.append(f"- {collection}")
                sections.append("")

        # Factory Insights
        insights = self.factory_insights
        if any([insights.architect_recommendations, insights.developer_patterns]):
            sections.append("## Factory Insights")

            if insights.architect_recommendations:
                sections.append("### Architect Recommendations")
                for rec in insights.architect_recommendations[:3]:
                    sections.append(f"- {rec}")
                sections.append("")

            if insights.developer_patterns:
                sections.append("### Developer Patterns")
                for pattern in insights.developer_patterns[:3]:
                    sections.append(f"- {pattern}")
                sections.append("")

        # Sprint Context
        if self.sprint_context and self.sprint_context.sprint_id:
            sections.append(self.sprint_context.to_markdown())
            sections.append("")

        # Slash Commands
        if self.slash_commands:
            sections.append("## Available Commands")
            sections.append("Use these slash commands to invoke Augur workflows:\n")

            # Group by category
            workflows = [c for c in self.slash_commands if c.category == "workflow"]
            skills = [c for c in self.slash_commands if c.category == "skill"]

            if workflows:
                sections.append("### Workflows")
                for cmd in workflows[:10]:  # Limit to 10
                    sections.append(f"- `/{cmd.name}`: {cmd.description}")
                sections.append("")

            if skills:
                sections.append("### Skills")
                for cmd in skills[:10]:  # Limit to 10
                    sections.append(f"- `skill:{cmd.name}`: {cmd.description}")
                sections.append("")

        # Skill-specific hint
        if self.skill_hint:
            sections.append(f"## Skill Focus: {self.skill_hint}")
            sections.append("Use horizontal services and factory insights relevant to this skill.\n")

        return "\n".join(sections)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "mode": self.mode,
            "preferences": {
                "language": self.preferences.language,
                "timezone": self.preferences.timezone,
                "name": self.preferences.name,
                "custom": self.preferences.custom,
            },
            "active_verticals": [
                {
                    "name": v.name,
                    "category": v.category,
                    "recent_items": v.recent_items[:3],
                }
                for v in self.active_verticals[:5]
            ],
            "plugin_enrichment": {
                "memory_snippets_count": len(self.plugin_enrichment.memory_snippets),
                "voice_transcripts_count": len(self.plugin_enrichment.recent_voice_transcripts),
                "active_collections": self.plugin_enrichment.active_collections[:5],
            },
            "factory_insights": {
                "recommendations_count": len(self.factory_insights.architect_recommendations),
                "patterns_count": len(self.factory_insights.developer_patterns),
            },
            "skill_hint": self.skill_hint,
            "generated_at": self.generated_at.isoformat(),
        }

        # Add sprint context if available
        if self.sprint_context:
            result["sprint_context"] = self.sprint_context.to_dict()

        # Add slash commands
        if self.slash_commands:
            result["slash_commands"] = [
                {"name": cmd.name, "description": cmd.description, "category": cmd.category}
                for cmd in self.slash_commands[:20]  # Limit to 20
            ]

        return result
