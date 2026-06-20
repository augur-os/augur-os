"""
Context injection tool implementations.

These are the KEY MOAT tools that provide personalized context
that standalone IDE agents cannot replicate.
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING

from .models import GetContextInput, ResponseFormat

if TYPE_CHECKING:
    pass


def _get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent.parent.parent


def _get_data_dir() -> Path:
    """Get the project root directory."""
    from src.mcp.augur_shared.config import get_project_root

    return get_project_root()


async def get_context_impl(params: GetContextInput, metrics, logger) -> str:
    """Get enriched context for IDE agents - KEY MOAT TOOL.

    This tool provides personalized context that standalone IDE agents
    cannot replicate, including:
    - User preferences and history
    - Active verticals with their data
    - Horizontal enrichment (RAG snippets, voice transcripts, etc.)
    - Factory insights (architect recommendations, patterns)

    Call this before building any vertical skill to receive context
    that makes your output production-ready instead of a generic mock.

    Args:
        params: GetContextInput with optional skill_hint and format
        metrics: MetricsTracker instance
        logger: Logger instance

    Returns:
        str: Enriched context in markdown or JSON format
    """
    from src.mcp.augur_shared.context_injector import ContextInjector

    metrics.track_tool("get_context", skill=params.skill_hint)

    try:
        injector = ContextInjector()
        context = injector.build_context(params.skill_hint)

        if params.format == ResponseFormat.JSON:
            return json.dumps(context.to_dict(), indent=2)

        return context.to_prompt()
    except Exception as e:
        logger.error(f"Error building context: {e}")
        return json.dumps({"error": str(e), "message": "Failed to build context. Check augur configuration."})


async def get_design_standards_impl(metrics, logger) -> str:
    """Get UI design standards for dashboard development.

    Call this BEFORE making any UI changes to understand:
    - Hub page rules (Overview tabs, no duplicate headers)
    - Design patterns (glassmorphism, spacing, typography)
    - Anti-patterns to avoid
    - Component guidelines

    Args:
        metrics: MetricsTracker instance
        logger: Logger instance

    Returns:
        str: Design standards document content
    """
    metrics.track_tool("get_design_standards")

    try:
        project_root = _get_project_root()
        standards_path = project_root / "apps" / "dashboard" / "docs" / "references" / "design-standards.md"

        if standards_path.exists():
            return standards_path.read_text()

        # Fallback - return summary
        return """# Design Standards Not Found

Design standards live at:
  apps/dashboard/docs/references/design-standards.md

## Quick Rules:
1. Hub pages MUST have Overview tab as first tab
2. No duplicate headers between layout.tsx and page.tsx
3. Tabs and tool cards should not show same items
4. Use glass-panel for content containers
"""
    except Exception as e:
        logger.error(f"Error reading design standards: {e}")
        return f"Error: {e}"


async def cross_skill_impl(source: str, target: str, metrics) -> str:
    """Get integration guidance between two skills.

    Args:
        source: Source skill name
        target: Target skill name
        metrics: MetricsTracker instance

    Returns:
        str: JSON with integration guidance
    """
    metrics.track_tool("cross_skill")

    data_dir = _get_data_dir()

    # Hardcoded known integrations for Phase 3
    integrations = {
        "job-analyzer:interview-prep": {
            "type": "src/lib-storage",
            "path": str(data_dir / "career"),
            "workflow": "Analyze job -> Save to career DB -> Read from interview-prep",
        },
        "ideas-capture:project-planner": {
            "type": "conversion",
            "workflow": "Capture idea -> Promote to project -> Create plan",
        },
    }

    key = f"{source}:{target}"
    if key in integrations:
        return json.dumps(integrations[key], indent=2)

    return json.dumps(
        {"status": "no_direct_integration_known", "advice": "Check src/lib data folders manually"}, indent=2
    )


__all__ = [
    "get_context_impl",
    "get_design_standards_impl",
    "cross_skill_impl",
]
