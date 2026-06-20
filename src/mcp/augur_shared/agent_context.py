"""Agent context builders for ContextInjector.

Provides build_agent_context and build_enhancement_context methods
that construct context packages optimized for different agent types.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.mcp.augur_shared.context_models import (
    AugurContext,
    UserPreferences,
)
from src.mcp.augur_shared.logging import get_entity_logger

logger = get_entity_logger("mcp.agent_context")


def build_agent_context(
    injector: Any,
    agent_type: str = "cli",
    preset: str = "standard",
    skill_hint: str | None = None,
) -> AugurContext:
    """
    Build context optimized for agent type and preset level.

    Args:
        injector: ContextInjector instance
        agent_type: Type of agent ("cli", "sdk", "ide")
        preset: Context level ("lightweight", "standard", "full")
        skill_hint: Optional skill to focus context on

    Returns:
        AugurContext tailored to agent type and preset
    """
    preferences = UserPreferences.load()
    mode = injector._get_current_mode()

    # Always include sprint and slash commands
    sprint_context = injector.get_active_sprint()
    slash_commands = injector.get_slash_commands()

    if preset == "lightweight":
        # Minimal context: just sprint and command names
        return AugurContext(
            preferences=preferences,
            mode=mode,
            sprint_context=sprint_context,
            slash_commands=slash_commands[:10],  # Top 10 commands
            skill_hint=skill_hint,
        )

    elif preset == "full":
        # Full context: everything
        return AugurContext(
            preferences=preferences,
            mode=mode,
            active_verticals=injector._get_active_verticals(skill_hint),
            plugin_enrichment=injector._get_plugin_enrichment(skill_hint),
            factory_insights=injector._get_factory_insights(skill_hint),
            sprint_context=sprint_context,
            slash_commands=slash_commands,
            skill_hint=skill_hint,
        )

    else:  # standard (default)
        # Standard context: sprint + slash commands + factory insights
        return AugurContext(
            preferences=preferences,
            mode=mode,
            factory_insights=injector._get_factory_insights(skill_hint),
            sprint_context=sprint_context,
            slash_commands=slash_commands,
            skill_hint=skill_hint,
        )


def build_enhancement_context(
    injector: Any,
    dashboard_path: str,
    depth: str = "page_only",
    rag_project_id: str | None = None,
    user_instructions: str | None = None,
) -> str:
    """
    Build context for dashboard enhancement based on configurable depth.

    This is used by the unified wizard to provide context when enhancing
    existing dashboards.

    Args:
        injector: ContextInjector instance
        dashboard_path: Hub path like /career, /brain, /workshop
        depth: Context depth level:
            - "page_only": SKILL.md, scripts, page component
            - "page_related": + horizontal enrichment, RAG snippets
            - "full_system": + factory insights, ADRs, sprint context
        rag_project_id: Optional RAG project ID for indexed documents
        user_instructions: User's enhancement instructions

    Returns:
        Markdown-formatted context string for IDE injection
    """
    sections = []

    # Header
    sections.append("# Dashboard Enhancement Context")
    sections.append(f"**Target Dashboard**: {dashboard_path}")
    sections.append(f"**Context Depth**: {depth}")
    sections.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")

    # Derive the skill name directly from the dashboard path (no hub mapping).
    skill_name = dashboard_path.strip("/")

    # Always include: page context (SKILL.md, scripts, components)
    sections.append("## Page Context")
    sections.append(_get_page_context(injector, skill_name, dashboard_path))
    sections.append("")

    # page_related and full_system: add horizontal enrichment
    if depth in ("page_related", "full_system"):
        enrichment = injector._get_plugin_enrichment(skill_name)
        if enrichment.memory_snippets:
            sections.append("## Related Context")

            sections.append("### From Memory (RAG)")
            for snippet in enrichment.memory_snippets[:5]:
                sections.append(f"- {snippet[:200]}...")
            sections.append("")

    # full_system only: add factory insights, ADRs, sprint
    if depth == "full_system":
        insights = injector._get_factory_insights(skill_name)

        sections.append("## System Context")

        if insights.architect_recommendations:
            sections.append("### Architect Recommendations")
            for rec in insights.architect_recommendations:
                sections.append(f"- {rec}")
            sections.append("")

        if insights.recent_adrs:
            sections.append("### Recent Architecture Decisions")
            for adr in insights.recent_adrs:
                sections.append(f"- {adr}")
            sections.append("")

        if insights.developer_patterns:
            sections.append("### Developer Patterns")
            for pattern in insights.developer_patterns:
                sections.append(f"- {pattern}")
            sections.append("")

        # Sprint context
        sprint = injector.get_active_sprint()
        if sprint.sprint_id:
            sections.append(sprint.to_markdown())
            sections.append("")

        # Slash commands
        commands = injector.get_slash_commands()
        if commands:
            sections.append("### Available Workflows")
            for cmd in commands[:10]:
                sections.append(f"- `/{cmd.name}`: {cmd.description}")
            sections.append("")

    # Always include user instructions if provided
    if user_instructions:
        sections.append("## Enhancement Request")
        sections.append(user_instructions)
        sections.append("")

    # Enhancement guidelines
    sections.append("## Guidelines")
    sections.append("1. Follow existing patterns in the dashboard")
    sections.append("2. Use `src/config/paths.py` for all paths")
    sections.append("3. Data files go in `augur/`, not `augur/`")
    sections.append("4. See `design-standards.md` for UI patterns")
    sections.append("5. Test changes before committing")

    return "\n".join(sections)


def _get_page_context(injector: Any, skill_name: str, dashboard_path: str) -> str:
    """Get context for a specific page/skill."""
    from src.config.paths import get_all_client_skill_dirs
    from src.mcp.augur_shared.config import get_project_root

    project_root = get_project_root()
    context_parts = []

    # Find skill directory in skills dirs (skills/, etc.)
    skill_dir = None
    try:
        for client_skills_dir in get_all_client_skill_dirs():
            candidate = client_skills_dir / skill_name
            if candidate.is_dir():
                skill_dir = candidate
                break
    except Exception:
        pass

    if skill_dir:
        # Read SKILL.md
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            try:
                content = skill_md.read_text(encoding="utf-8")
                # Take first 500 chars as summary
                context_parts.append(f"**SKILL.md** ({skill_dir.relative_to(project_root)}):")
                context_parts.append(f"```\n{content[:500]}...\n```")
            except Exception as e:
                logger.debug("Failed to read SKILL.md %s: %s", skill_md, e)

        # List scripts
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.exists():
            scripts = list(scripts_dir.glob("*.py"))
            if scripts:
                context_parts.append(f"**Scripts**: {', '.join(s.name for s in scripts[:5])}")

    # Find dashboard page component
    dashboard_dir = project_root / "apps" / "dashboard" / "app"
    page_path = dashboard_dir / dashboard_path.strip("/") / "page.tsx"
    if page_path.exists():
        context_parts.append(f"**Page Component**: {page_path.relative_to(project_root)}")

    layout_path = dashboard_dir / dashboard_path.strip("/") / "layout.tsx"
    if layout_path.exists():
        context_parts.append(f"**Layout**: {layout_path.relative_to(project_root)}")

    return "\n".join(context_parts) if context_parts else "No page context found"
