"""MCP Config Controller - Smart MCP tool selection based on context.

This module analyzes active sprint and task context to automatically enable/disable
MCP tools, providing focused capabilities to agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from src.logging import get_entity_logger

from src.mcp.augur_shared.context_injector import ContextInjector, SprintContext

logger = get_entity_logger("llm")


@dataclass
class ToolCategory:
    """MCP tool category definition."""

    name: str
    tools: list[str] = field(default_factory=list)
    description: str = ""
    default_enabled: bool = False


# Define MCP tool categories
MCP_CATEGORIES = {
    "core": ToolCategory(
        name="core",
        tools=["skill_registry", "get_context", "execute_skill"],
        description="Core Augur operations",
        default_enabled=True,
    ),
    "context": ToolCategory(
        name="context",
        tools=["list_verticals", "read_vertical_data", "search_knowledge"],
        description="Context reading and search",
        default_enabled=True,
    ),
    "execution": ToolCategory(
        name="execution",
        tools=["write_vertical_data", "create_vertical", "update_config"],
        description="Write and execute operations",
        default_enabled=False,  # Enable based on task
    ),
    "development": ToolCategory(
        name="development",
        tools=["run_tests", "lint_code", "format_code", "analyze_coverage"],
        description="Development and testing tools",
        default_enabled=False,
    ),
    "ui": ToolCategory(
        name="ui",
        tools=["validate_ui", "screenshot_analysis", "component_check"],
        description="UI development and validation",
        default_enabled=False,
    ),
    "data": ToolCategory(
        name="data",
        tools=["query_data", "analyze_metrics", "generate_report"],
        description="Data analysis and reporting",
        default_enabled=False,
    ),
    "diagnostics": ToolCategory(
        name="diagnostics",
        tools=["health_check", "list_logs", "debug_trace"],
        description="Debugging and diagnostics",
        default_enabled=False,
    ),
}


@dataclass
class MCPConfig:
    """MCP configuration with enabled/disabled tools."""

    enabled_tools: list[str] = field(default_factory=list)
    disabled_tools: list[str] = field(default_factory=list)
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled_tools": self.enabled_tools,
            "disabled_tools": self.disabled_tools,
            "reasoning": self.reasoning,
            "enabled_count": len(self.enabled_tools),
            "disabled_count": len(self.disabled_tools),
        }


class MCPConfigController:
    """
    Smart MCP configuration controller.

    Analyzes sprint context and task descriptions to automatically
    enable/disable MCP tools for focused agent capabilities.
    """

    def __init__(self):
        self.injector = ContextInjector()

    def get_focused_config(
        self, task_description: Optional[str] = None, sprint_context: Optional[SprintContext] = None
    ) -> MCPConfig:
        """
        Get focused MCP configuration based on context.

        Args:
            task_description: Optional task description for keyword analysis
            sprint_context: Optional sprint context (auto-loaded if not provided)

        Returns:
            MCPConfig with enabled/disabled tools and reasoning
        """
        # Load sprint context if not provided
        if sprint_context is None:
            sprint_context = getattr(self.injector, "get_active_sprint")()

        # Start with core tools always enabled
        enabled_categories = ["core", "context"]
        reasoning_parts = ["Core and context tools always enabled"]

        # Analyze sprint goal and task for keywords
        text_to_analyze = ""
        if sprint_context and sprint_context.sprint_goal:
            text_to_analyze += sprint_context.sprint_goal.lower() + " "
        if task_description:
            text_to_analyze += task_description.lower()

        # Enable categories based on keywords
        if any(word in text_to_analyze for word in ["test", "coverage", "quality", "lint"]):
            enabled_categories.append("development")
            reasoning_parts.append("Development tools enabled for testing/quality focus")

        if any(word in text_to_analyze for word in ["ui", "component", "dashboard", "frontend", "design"]):
            enabled_categories.append("ui")
            reasoning_parts.append("UI tools enabled for frontend work")

        if any(word in text_to_analyze for word in ["data", "analytics", "metric", "report", "analysis"]):
            enabled_categories.append("data")
            reasoning_parts.append("Data tools enabled for analytics work")

        if any(word in text_to_analyze for word in ["write", "create", "update", "modify", "implement"]):
            enabled_categories.append("execution")
            reasoning_parts.append("Execution tools enabled for write operations")

        if any(word in text_to_analyze for word in ["debug", "fix", "error", "issue", "bug"]):
            enabled_categories.append("diagnostics")
            reasoning_parts.append("Diagnostics tools enabled for debugging")

        # Build tool lists
        enabled_tools = []
        disabled_tools = []

        for category_name, category in MCP_CATEGORIES.items():
            if category_name in enabled_categories:
                enabled_tools.extend(category.tools)
            else:
                disabled_tools.extend(category.tools)

        return MCPConfig(
            enabled_tools=enabled_tools, disabled_tools=disabled_tools, reasoning=". ".join(reasoning_parts)
        )

    def get_preset_config(self, preset: str) -> MCPConfig:
        """
        Get predefined configuration preset.

        Args:
            preset: One of "minimal", "standard", "full", "development", "production"

        Returns:
            MCPConfig for the preset
        """
        if preset == "minimal":
            return MCPConfig(
                enabled_tools=MCP_CATEGORIES["core"].tools,
                disabled_tools=[tool for cat in MCP_CATEGORIES.values() if cat.name != "core" for tool in cat.tools],
                reasoning="Minimal preset - only core tools enabled",
            )

        elif preset == "standard":
            enabled_cats = ["core", "context", "execution"]
            return MCPConfig(
                enabled_tools=[
                    tool for cat in MCP_CATEGORIES.values() if cat.name in enabled_cats for tool in cat.tools
                ],
                disabled_tools=[
                    tool for cat in MCP_CATEGORIES.values() if cat.name not in enabled_cats for tool in cat.tools
                ],
                reasoning="Standard preset - core, context, and execution tools",
            )

        elif preset == "development":
            enabled_cats = ["core", "context", "execution", "development", "diagnostics"]
            return MCPConfig(
                enabled_tools=[
                    tool for cat in MCP_CATEGORIES.values() if cat.name in enabled_cats for tool in cat.tools
                ],
                disabled_tools=[
                    tool for cat in MCP_CATEGORIES.values() if cat.name not in enabled_cats for tool in cat.tools
                ],
                reasoning="Development preset - includes testing and debugging tools",
            )

        elif preset == "production":
            # Production: no execution tools, only reading/diagnostics
            enabled_cats = ["core", "context", "diagnostics"]
            return MCPConfig(
                enabled_tools=[
                    tool for cat in MCP_CATEGORIES.values() if cat.name in enabled_cats for tool in cat.tools
                ],
                disabled_tools=[
                    tool for cat in MCP_CATEGORIES.values() if cat.name not in enabled_cats for tool in cat.tools
                ],
                reasoning="Production preset - read-only with diagnostics",
            )

        else:  # "full"
            return MCPConfig(
                enabled_tools=[tool for cat in MCP_CATEGORIES.values() for tool in cat.tools],
                disabled_tools=[],
                reasoning="Full preset - all tools enabled",
            )


# Singleton instance
_controller: Optional[MCPConfigController] = None


def get_mcp_controller() -> MCPConfigController:
    """Get the global MCP config controller (singleton)."""
    global _controller
    if _controller is None:
        _controller = MCPConfigController()
    return _controller


if __name__ == "__main__":
    """Test MCP config controller."""
    logger.info("Testing MCP Config Controller")
    logger.info("=" * 50)

    controller = get_mcp_controller()

    # Test 1: Focused config based on sprint
    logger.info("--- Test 1: Focused config for UI development ---")
    config = controller.get_focused_config("Build new dashboard UI component")
    logger.info("Enabled: %s tools", len(config.enabled_tools))
    logger.info("Reasoning: %s", config.reasoning)
    logger.info("Tools: %s", config.enabled_tools)

    # Test 2: Preset configs
    logger.info("--- Test 2: Minimal preset ---")
    config = controller.get_preset_config("minimal")
    logger.info("Enabled: %s", config.enabled_tools)

    logger.info("--- Test 3: Development preset ---")
    config = controller.get_preset_config("development")
    logger.info("Enabled: %s tools", len(config.enabled_tools))
    logger.info("Reasoning: %s", config.reasoning)
