"""Context enrichment helpers for ContextInjector.

Provides methods that gather enrichment data from verticals,
plugins, factory agents, sprints, and slash commands.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from src.mcp.augur_shared.context_models import (
    FactoryInsights,
    PluginEnrichment,
    SlashCommand,
    SprintContext,
    VerticalState,
)
from src.mcp.augur_shared.logging import get_entity_logger

logger = get_entity_logger("mcp.context_enrichment")


def get_active_verticals(data_dir: Path, skill_hint: str | None = None) -> list[VerticalState]:
    """Get recently active vertical skills."""
    verticals = []

    # Scan vertical data directories for recent activity
    verticals_data_dir = data_dir / "vertical"
    if verticals_data_dir.exists():
        for skill_dir in verticals_data_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            # Check for recent files
            recent_files = sorted(skill_dir.glob("**/*.yaml"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]

            if recent_files:
                recent_items = [f.stem for f in recent_files[:3]]
                verticals.append(
                    VerticalState(
                        name=skill_dir.name,
                        category="vertical",
                        recent_items=recent_items,
                    )
                )

    # Prioritize hinted skill
    if skill_hint:
        verticals.sort(key=lambda v: 0 if v.name == skill_hint else 1)

    return verticals[:5]


def get_plugin_enrichment(skill_hint: str | None = None) -> PluginEnrichment:
    """Get enrichment from plugin dependencies.

    Uses the flat plugin dependency system - see docs/guides/plugin-dependencies.md
    """
    enrichment = PluginEnrichment()

    # Try to import the context resolver
    try:
        from src.plugins.context import (
            list_context_providers,
            resolve_context,
        )
    except ImportError:
        # Context resolver not available
        return enrichment

    # List all plugins that provide context
    try:
        providers = list_context_providers()
        enrichment.available_providers = [p["name"] for p in providers]
    except Exception as e:
        logger.debug("Context providers unavailable: %s", e)

    # If we have a skill hint, resolve its dependencies
    if skill_hint:
        try:
            resolved = resolve_context(skill_hint)
            enrichment.resolved_contexts = resolved.all_provided()
            enrichment.dependency_errors = resolved.errors
        except Exception as e:
            enrichment.dependency_errors.append(str(e))

    return enrichment


def get_factory_insights(data_dir: Path, skill_hint: str | None = None) -> FactoryInsights:
    """Get insights from factory agents."""
    insights = FactoryInsights()

    # Always include core rules hint
    insights.architect_recommendations.append("Full agent rules: docs/agent-rules.md")

    # Add UI guidelines hint when working on dashboard
    if skill_hint and any(kw in skill_hint.lower() for kw in ["dashboard", "app/", "ui", "page.tsx", "layout.tsx"]):
        insights.architect_recommendations.append(
            "UI Rule: Hub pages need Overview tab. No duplicate headers. "
            "Run: get-design-standards for full guidelines"
        )

    # Add path resolution hint when working on Python files
    if skill_hint and any(kw in skill_hint.lower() for kw in [".py", "python", "script", "api"]):
        insights.architect_recommendations.append(
            "Paths: Use src/lib.config.paths for all file operations. NEVER hardcode /Users/ paths!"
        )

    # Add data separation hint when working on storage/data
    if skill_hint and any(kw in skill_hint.lower() for kw in ["data", "yaml", "storage", "save", "write"]):
        insights.architect_recommendations.append("Data: Write user data to augur repo, never to code repo")

    # Architect ADRs
    architect_dir = data_dir / "factory" / "architect"
    if architect_dir.exists():
        adrs_dir = architect_dir / "adrs"
        if adrs_dir.exists():
            recent_adrs = sorted(adrs_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:3]

            for adr_path in recent_adrs:
                insights.recent_adrs.append(adr_path.stem)

    # Developer patterns from retrospectives
    developer_dir = data_dir / "factory" / "developer"
    if developer_dir.exists():
        patterns_file = developer_dir / "learned_patterns.yaml"
        if patterns_file.exists():
            try:
                with open(patterns_file, encoding="utf-8") as f:
                    patterns = yaml.safe_load(f) or {}
                for pattern_name in list(patterns.keys())[:3]:
                    insights.developer_patterns.append(pattern_name)
            except Exception as e:
                logger.debug("Failed to parse developer patterns from %s: %s", patterns_file, e)

    return insights


def get_active_sprint(data_dir: Path) -> SprintContext:
    """
    Load current sprint goal, velocity, and backlog items.

    Returns:
        SprintContext with active sprint data
    """
    sprint_context = SprintContext()

    # Find latest sprint file
    sprints_dir = data_dir / "factory" / "executor" / "sprints"
    if not sprints_dir.exists():
        return sprint_context

    # Get most recent sprint file
    sprint_files = sorted(sprints_dir.glob("sprint-*.md"), key=lambda p: p.name, reverse=True)

    if not sprint_files:
        return sprint_context

    latest_sprint = sprint_files[0]
    sprint_context.sprint_id = latest_sprint.stem

    # Parse sprint file
    try:
        content = latest_sprint.read_text(encoding="utf-8")

        # Extract sprint goal (support both "Sprint Goal" and "Goals")
        goal_match = re.search(r"## (?:Sprint )?Goals?\s*\n\s*(.+)", content, re.DOTALL)
        if goal_match:
            goal_text = goal_match.group(1).strip()
            lines = goal_text.split("\n")
            relevant_goals = [line.strip().lstrip("-").strip() for line in lines if line.strip()]
            sprint_context.sprint_goal = relevant_goals[0] if relevant_goals else goal_text.split("\n")[0]

        # Extract metrics
        velocity_match = re.search(r"(?:Average )?Velocity:\s*(\d+\.?\d*)", content)
        if velocity_match:
            sprint_context.velocity = float(velocity_match.group(1))

        capacity_match = re.search(r"Target Points(?: \(\d+%\))?:\s*(\d+\.?\d*)", content)
        if not capacity_match:
            capacity_match = re.search(r"Capacity:\s*(\d+\.?\d*)", content)

        if capacity_match:
            sprint_context.capacity = float(capacity_match.group(1))

        committed_match = re.search(r"Committed(?: Points)?:\s*(\d+\.?\d*)", content)
        if committed_match:
            sprint_context.committed_points = float(committed_match.group(1))

        # Extract backlog items
        # Format 1: Bullet points
        item_pattern_1 = r"-\s*\[[ xX]?\]\s*(.+?)\s*\((\d+)\s*pts?\)"
        for match in re.finditer(item_pattern_1, content):
            title = match.group(1).strip()
            points = int(match.group(2))
            status = "completed" if "[x]" in match.group(0) or "[X]" in match.group(0) else "pending"

            sprint_context.backlog_items.append({"title": title, "points": points, "status": status})

        # Format 2: Headers (as seen in sprint-20260106.md)
        if not sprint_context.backlog_items:
            item_pattern_2 = r"###\s*(?:.+?:\s*)?(.+?)\s*\((\d+)\s*pts?\)"
            for match in re.finditer(item_pattern_2, content):
                title = match.group(1).strip()
                points = int(match.group(2))
                status = "pending"

                sprint_context.backlog_items.append({"title": title, "points": points, "status": status})

    except Exception as e:
        logger.debug("Failed to parse active sprint file %s: %s", latest_sprint, e)

    return sprint_context


def get_slash_commands(project_root: Path) -> list[SlashCommand]:
    """
    Load available slash commands from CLAUDE.md.

    Returns:
        List of SlashCommand objects
    """
    commands: list[SlashCommand] = []

    # Read CLAUDE.md from project root
    claude_md_path = project_root / "CLAUDE.md"
    if not claude_md_path.exists():
        return commands

    try:
        content = claude_md_path.read_text(encoding="utf-8")

        # Parse workflow chains (### Workflows (Chains))
        workflow_section = re.search(r"### Workflows \(Chains\)(.*?)(?=###|\Z)", content, re.DOTALL)
        if workflow_section:
            for match in re.finditer(r"-\s*`/(\w+)`:\s*(.+)", workflow_section.group(1)):
                commands.append(
                    SlashCommand(name=match.group(1), description=match.group(2).strip(), category="workflow")
                )

        # Parse core skills (### Core Skills)
        skills_section = re.search(r"### Core Skills(.*?)(?=###|\Z)", content, re.DOTALL)
        if skills_section:
            for match in re.finditer(r"-\s*`skill:(\w+)`:\s*(.+)", skills_section.group(1)):
                commands.append(SlashCommand(name=match.group(1), description=match.group(2).strip(), category="skill"))

        # Parse manual workflows (### Manual Workflows)
        manual_section = re.search(r"### Manual Workflows.*?\(Agent Actions\)(.*?)(?=###|\Z)", content, re.DOTALL)
        if manual_section:
            for match in re.finditer(r"-\s*`/([^`]+)`:\s*(.+)", manual_section.group(1)):
                commands.append(
                    SlashCommand(name=match.group(1), description=match.group(2).strip(), category="manual")
                )

    except Exception as e:
        logger.debug("Failed to parse slash commands from %s: %s", claude_md_path, e)

    return commands
