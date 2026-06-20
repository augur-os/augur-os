#!/usr/bin/env python3
"""
Context Injector - Builds enriched context plugins for IDE agents.

This is a KEY MOAT component. When IDE agents call `exo_get_context`,
they receive personalized context that standalone agents cannot replicate:

- User preferences and history
- Active verticals with their data
- Horizontal enrichment (RAG snippets, voice transcripts, etc.)
- Factory insights (architect recommendations, patterns)

Usage:
    from context_injector import ContextInjector

    injector = ContextInjector()
    context = injector.build_context(skill_hint="recipes")
    prompt_context = context.to_prompt()
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

# Add project root to path
project_root = Path(__file__).resolve().parents[4]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.mcp.augur_shared.agent_context import (  # noqa: E402
    build_agent_context as _build_agent_context_impl,
)
from src.mcp.augur_shared.agent_context import (  # noqa: E402
    build_enhancement_context as _build_enhancement_context_impl,
)
from src.mcp.augur_shared.config import get_project_root  # noqa: E402
from src.mcp.augur_shared.context_enrichment import (  # noqa: E402
    get_active_sprint as _get_active_sprint_impl,
)

# Import extracted modules
from src.mcp.augur_shared.context_enrichment import (  # noqa: E402
    get_active_verticals as _get_active_verticals_impl,
)
from src.mcp.augur_shared.context_enrichment import (  # noqa: E402
    get_factory_insights as _get_factory_insights_impl,
)
from src.mcp.augur_shared.context_enrichment import (  # noqa: E402
    get_plugin_enrichment as _get_plugin_enrichment_impl,
)
from src.mcp.augur_shared.context_enrichment import (  # noqa: E402
    get_slash_commands as _get_slash_commands_impl,
)

# Re-export models for backward compatibility
from src.mcp.augur_shared.context_models import (  # noqa: E402,F401
    AugurContext,
    FactoryInsights,
    HumanApiProfile,
    PluginEnrichment,
    SlashCommand,
    SprintContext,
    UserPreferences,
    VerticalState,
)
from src.mcp.augur_shared.logging import get_entity_logger  # noqa: E402

# Re-export registry functions for backward compatibility
from src.mcp.augur_shared.registry_loader import (  # noqa: E402,F401
    load_registry as _load_registry,
)

logger = get_entity_logger("mcp.context")


class ContextInjector:
    """
    Builds enriched context plugins for IDE agents.

    This is the KEY MOAT service - it provides personalized context
    that standalone IDE agents cannot replicate because they don't
    have access to:

    1. User's historical data and preferences
    2. Horizontal services (RAG, voice, collections)
    3. Factory agent insights and patterns
    """

    def __init__(self):
        self.data_dir = get_project_root()
        self._registry: dict[str, Any] | None = None

    def _get_current_mode(self) -> str:
        """Get the current operating mode from persistent config.

        Delegates to the unified ContextManager (ADR-030 Section 4).

        Returns:
            "dev" or "ops" (default: "ops")
        """
        from src.mcp.augur_shared.context_manager import DEFAULT_MODE, VALID_MODES

        try:
            config_path = self.data_dir / "config" / "system" / "config.yaml"
            if not config_path.exists():
                return DEFAULT_MODE

            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            augur_config = config.get("augur", {})
            if not isinstance(augur_config, dict):
                return DEFAULT_MODE

            mode = augur_config.get("mode", DEFAULT_MODE)
            if mode in VALID_MODES:
                return mode

            logger.warning("Invalid mode '%s' in config, defaulting to '%s'", mode, DEFAULT_MODE)
            return DEFAULT_MODE
        except Exception as e:
            logger.warning("Failed to read mode from config: %s", e)
            return DEFAULT_MODE

    def _get_registry(self) -> dict[str, Any]:
        """Get the unified registry, loading if needed."""
        if self._registry is None:
            self._registry = _load_registry()
        return self._registry

    def get_page_skills(self, page: str, mode: str = "operation") -> list[str]:
        """
        Return skills relevant to a page, filtered by mode.

        Args:
            page: Dashboard page path (e.g., "/career", "/workforce")
            mode: "operation" or "dev"

        Returns:
            List of skill names filtered by mode
        """
        registry = self._get_registry()
        page_context = registry["page_contexts"].get(page, {})
        skills = page_context.get("skills", [])

        if mode == "operation":
            # Filter out dev-only skills
            return [s for s in skills if registry["skills"].get(s, {}).get("mode") != "dev"]
        # Dev mode sees all skills
        return skills

    def get_suggested_chains(self, page: str, mode: str = "operation") -> list[dict[str, Any]]:
        """
        Return chains relevant to a page, filtered by mode.

        Args:
            page: Dashboard page path
            mode: "operation" or "dev"

        Returns:
            List of chain dicts with name, description, category
        """
        registry = self._get_registry()
        page_context = registry["page_contexts"].get(page, {})
        chain_names = page_context.get("chains", [])

        chains = []
        for name in chain_names:
            chain_data = registry["chains"].get(name, {})
            chain_mode = chain_data.get("mode", "operation")

            # In operation mode, filter out dev chains
            if mode == "operation" and chain_mode == "dev":
                continue

            chains.append(
                {
                    "name": name,
                    "description": chain_data.get("description", f"{name} chain"),
                    "category": chain_data.get("category", "general"),
                    "mode": chain_mode,
                }
            )

        return chains

    def get_relevant_workflows(self, page: str, mode: str = "operation") -> list[dict[str, Any]]:
        """
        Return workflows relevant to a page, filtered by mode.

        Args:
            page: Dashboard page path
            mode: "operation" or "dev"

        Returns:
            List of workflow dicts with name, description, command
        """
        registry = self._get_registry()
        page_context = registry["page_contexts"].get(page, {})
        workflow_names = page_context.get("workflows", [])

        workflows = []
        for name in workflow_names:
            workflow_data = registry["workflows"].get(name, {})
            workflow_mode = workflow_data.get("mode", "operation")

            # In operation mode, filter out dev workflows
            if mode == "operation" and workflow_mode == "dev":
                continue

            workflows.append(
                {
                    "name": name,
                    "description": workflow_data.get("description", f"{name} workflow"),
                    "command": workflow_data.get("command", f"/{name}"),
                    "mode": workflow_mode,
                }
            )

        return workflows

    def get_available_commands(self, page: str | None = None, mode: str = "operation") -> list[dict[str, Any]]:
        """
        Return slash commands for current context, filtered by mode.

        Args:
            page: Optional dashboard page path for context filtering
            mode: "operation" or "dev"

        Returns:
            List of command dicts with name, description, type, mode
        """
        registry = self._get_registry()
        commands = []

        # Get workflows as commands
        for name, workflow in registry["workflows"].items():
            workflow_mode = workflow.get("mode", "operation")

            # In operation mode, filter out dev workflows
            if mode == "operation" and workflow_mode == "dev":
                continue

            commands.append(
                {
                    "name": name,
                    "description": workflow.get("description", f"Execute {name}"),
                    "type": "workflow",
                    "command": workflow.get("command", f"/{name}"),
                    "mode": workflow_mode,
                }
            )

        # Get chains as commands (with /chain: prefix)
        for name, chain in registry["chains"].items():
            chain_mode = chain.get("mode", "operation")

            # In operation mode, filter out dev chains
            if mode == "operation" and chain_mode == "dev":
                continue

            commands.append(
                {
                    "name": name,
                    "description": chain.get("description", f"Execute {name} chain"),
                    "type": "chain",
                    "command": f"/chain:{name}",
                    "mode": chain_mode,
                }
            )

        # If page provided, prioritize page-relevant commands
        if page:
            page_context = registry["page_contexts"].get(page, {})
            page_workflows = set(page_context.get("workflows", []))
            page_chains = set(page_context.get("chains", []))

            # Sort: page-relevant first, then alphabetically
            commands.sort(
                key=lambda c: (0 if c["name"] in page_workflows or c["name"] in page_chains else 1, c["name"])
            )

        return commands

    def get_mode_context(self, page: str | None = None, mode: str | None = None) -> dict[str, Any]:
        """
        Get complete mode-aware context for a page.

        This is the primary method for mode-aware filtering, returning
        all relevant skills, chains, workflows, and commands.

        Args:
            page: Optional dashboard page path
            mode: "operation" or "dev" (default: read from persistent config)

        Returns:
            Dict with skills, chains, workflows, commands filtered by mode
        """
        if mode is None:
            # ADR-030: Read mode from persistent config
            persisted = self._get_current_mode()
            mode = "dev" if persisted == "dev" else "operation"

        context: dict[str, Any] = {
            "mode": mode,
            "page": page,
        }

        if page:
            context["skills"] = self.get_page_skills(page, mode)
            context["chains"] = self.get_suggested_chains(page, mode)
            context["workflows"] = self.get_relevant_workflows(page, mode)

        context["commands"] = self.get_available_commands(page, mode)

        return context

    def build_context(self, skill_hint: str | None = None) -> AugurContext:
        """
        Build a complete context package.

        Args:
            skill_hint: Optional skill name to focus context on

        Returns:
            AugurContext with all available enrichment
        """
        preferences = UserPreferences.load()
        human_api_profile = HumanApiProfile.load(self.data_dir)
        mode = self._get_current_mode()
        active_verticals = self._get_active_verticals(skill_hint)
        plugin_enrichment = self._get_plugin_enrichment(skill_hint)
        factory_insights = self._get_factory_insights(skill_hint)

        sprint_context = self.get_active_sprint()
        slash_commands = self.get_slash_commands()

        return AugurContext(
            preferences=preferences,
            human_api_profile=human_api_profile,
            mode=mode,
            active_verticals=active_verticals,
            plugin_enrichment=plugin_enrichment,
            factory_insights=factory_insights,
            sprint_context=sprint_context,
            slash_commands=slash_commands,
            skill_hint=skill_hint,
        )

    # Delegate to extracted modules

    def _get_active_verticals(self, skill_hint: str | None = None) -> list[VerticalState]:
        """Get recently active vertical skills."""
        return _get_active_verticals_impl(self.data_dir, skill_hint)

    def _get_plugin_enrichment(self, skill_hint: str | None = None) -> PluginEnrichment:
        """Get enrichment from plugin dependencies."""
        return _get_plugin_enrichment_impl(skill_hint)

    def _get_factory_insights(self, skill_hint: str | None = None) -> FactoryInsights:
        """Get insights from factory agents."""
        return _get_factory_insights_impl(self.data_dir, skill_hint)

    def get_active_sprint(self) -> SprintContext:
        """Load current sprint goal, velocity, and backlog items."""
        return _get_active_sprint_impl(self.data_dir)

    def get_slash_commands(self) -> list[SlashCommand]:
        """Load available slash commands from CLAUDE.md."""
        return _get_slash_commands_impl(project_root)

    def build_agent_context(
        self, agent_type: str = "cli", preset: str = "standard", skill_hint: str | None = None
    ) -> AugurContext:
        """Build context optimized for agent type and preset level."""
        return _build_agent_context_impl(self, agent_type, preset, skill_hint)

    def build_enhancement_context(
        self,
        dashboard_path: str,
        depth: str = "page_only",
        rag_project_id: str | None = None,
        user_instructions: str | None = None,
    ) -> str:
        """Build context for dashboard enhancement based on configurable depth."""
        return _build_enhancement_context_impl(self, dashboard_path, depth, rag_project_id, user_instructions)


# Convenience functions for direct import
def get_context(skill_hint: str | None = None) -> AugurContext:
    """Get enriched context for IDE agents."""
    return ContextInjector().build_context(skill_hint)


def get_mode_context(page: str | None = None, mode: str | None = None) -> dict[str, Any]:
    """
    Get mode-aware context for IDE agents.

    This is the primary entry point for mode-aware filtering,
    returning skills, chains, workflows, and commands filtered by mode.

    Args:
        page: Optional dashboard page path (e.g., "/career")
        mode: "operation" or "dev" (default: read from persistent config)

    Returns:
        Dict with mode-filtered context:
        - mode: Current mode
        - page: Current page (if provided)
        - skills: Relevant skills for page
        - chains: Available chains filtered by mode
        - workflows: Available workflows filtered by mode
        - commands: All available slash commands
    """
    return ContextInjector().get_mode_context(page, mode)


def list_context_commands(page: str | None = None, mode: str | None = None) -> list[dict[str, Any]]:
    """
    List available slash commands for current page/mode.

    Args:
        page: Optional dashboard page path
        mode: "operation" or "dev" (default: read from persistent config)

    Returns:
        List of command dicts with name, description, type, command, mode
    """
    return ContextInjector().get_available_commands(page, mode or "operation")


if __name__ == "__main__":
    """Test context injection."""
    import json

    logger.info("Testing Context Injector")
    logger.info("=" * 50)

    injector = ContextInjector()

    # Test basic context
    context = injector.build_context()
    logger.info("--- Context as Prompt ---")
    logger.info(context.to_prompt())

    logger.info("--- Context as Dict ---")
    logger.info(json.dumps(context.to_dict(), indent=2))

    # Test mode-aware filtering
    logger.info("\n" + "=" * 50)
    logger.info("Testing Mode-Aware Filtering")
    logger.info("=" * 50)

    # Test operation mode for /career page
    logger.info("\n--- Operation Mode: /career ---")
    career_context = injector.get_mode_context("/career", "operation")
    logger.info(json.dumps(career_context, indent=2))

    # Test dev mode for /workforce page
    logger.info("\n--- Dev Mode: /workforce ---")
    workforce_context = injector.get_mode_context("/workforce", "dev")
    logger.info(json.dumps(workforce_context, indent=2))

    # Test available commands in operation mode
    logger.info("\n--- Available Commands (Operation Mode) ---")
    op_commands = injector.get_available_commands(mode="operation")
    logger.info(f"Found {len(op_commands)} commands in operation mode")
    for cmd in op_commands[:5]:
        logger.info(f"  /{cmd['name']}: {cmd['description'][:50]}...")

    # Test available commands in dev mode
    logger.info("\n--- Available Commands (Dev Mode) ---")
    dev_commands = injector.get_available_commands(mode="dev")
    logger.info(f"Found {len(dev_commands)} commands in dev mode")
    for cmd in dev_commands[:5]:
        logger.info(f"  /{cmd['name']}: {cmd['description'][:50]}...")
