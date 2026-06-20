"""
Dynamic tool controller for context-aware MCP tool selection.

ADR-250: Page-scoped filtering is only active for web-chat clients.
CLI/IDE clients bypass this entirely (they have deferred tool loading).

Also filters tools based on plugin enabled/disabled state.
"""

import json
from pathlib import Path

import yaml
from src.mcp.augur_shared.config import get_config_dir
from src.mcp.augur_shared.logging import get_entity_logger
from src.plugins.skill_config import is_plugin_enabled_by_config

logger = get_entity_logger("mcp")


class ToolController:
    """
    Context-aware tool registry controller.

    Dynamically enables/disables MCP tools based on:
    - Active sprint focus
    - Current dashboard page
    - Chain execution state
    - User workflow phase
    - Plugin enabled/disabled state
    """

    def __init__(self, config_path: Path | None = None):
        """
        Initialize tool controller.

        Args:
            config_path: Path to mcp_tool_groups.yaml (default: augur/config/)
        """
        if config_path is None:
            # ADR-260: Try assembled_tool_config.json first, fall back to mcp_tool_groups.yaml
            assembled = get_config_dir() / "dashboard" / "generated" / "assembled_tool_config.json"
            config_path = assembled if assembled.exists() else get_config_dir() / "mcp_tool_groups.yaml"

        self.config_path = config_path
        self.tool_groups = self._load_tool_groups()
        self.max_tools = 80

        # Load plugin state for filtering
        self.plugin_state = self._load_plugin_state()
        self._plugin_prefixes_cache: list[str] | None = None

    def _load_tool_groups(self) -> dict[str, list[str]]:
        """
        Load tool groups from YAML configuration.

        Returns:
            Dictionary mapping group names to tool lists
        """
        if not self.config_path.exists():
            logger.warning(f"Tool groups config not found: {self.config_path}. Using defaults.")
            return self._get_default_tool_groups()

        try:
            with open(self.config_path, encoding="utf-8") as f:
                if self.config_path.suffix == ".json":
                    config = json.load(f)
                else:
                    config = yaml.safe_load(f)
                return config.get("tool_groups", self._get_default_tool_groups())
        except Exception as e:
            logger.error(f"Failed to load tool groups: {e}", exc_info=True)
            return self._get_default_tool_groups()

    def _get_default_tool_groups(self) -> dict[str, list[str]]:
        """
        Get default tool groups if config doesn't exist.

        ADR-250: Removed dead default groups (UI, BACKEND, CHAIN, DATA, BUG,
        SKILL_MGMT) that referenced non-existent tools. Only CORE remains
        as a fallback.
        """
        return {
            "CORE": [
                "list-skills",
                "get-skill",
                "load-module",
                "skill-action",
                "health",
                "metrics",
            ],
        }

    def _load_plugin_state(self) -> dict[str, bool]:
        """
        Build plugin state by scanning local plugin state for legacy bundles.

        Returns:
            Dict mapping plugin/hub names to their enabled state.
        """
        from src.config.paths import get_project_root

        state: dict[str, bool] = {}
        plugins_dir = get_project_root() / "plugins"

        if not plugins_dir.exists():
            return state

        for hub_dir in plugins_dir.iterdir():
            if not hub_dir.is_dir() or hub_dir.name.startswith("."):
                continue

            # Hub-level enabled state
            hub_enabled = is_plugin_enabled_by_config(hub_dir)
            state[hub_dir.name] = hub_enabled

            # Skill-level enabled state
            skills_dir = hub_dir / "skills"
            if skills_dir.exists():
                for skill_dir in skills_dir.iterdir():
                    if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                        # A skill is disabled if its hub is disabled or its local state says so.
                        skill_enabled = hub_enabled and is_plugin_enabled_by_config(skill_dir)
                        # Preserve hub key when skill name collides with hub name (e.g. career/career).
                        # Keep plain key for backward compatibility and add a namespaced key.
                        if skill_dir.name == hub_dir.name:
                            state[f"skill:{hub_dir.name}/{skill_dir.name}"] = skill_enabled
                            continue
                        if not hub_enabled:
                            state[skill_dir.name] = False
                        else:
                            state[skill_dir.name] = skill_enabled

        return state

    def is_plugin_enabled(self, plugin_name: str) -> bool:
        """
        Check if a plugin is enabled via local skill state.

        Args:
            plugin_name: Name of the plugin/skill or hub

        Returns:
            True if enabled, False otherwise (default enabled if no .config)
        """
        base_enabled = self.plugin_state.get(plugin_name, True)

        # Handle hub/skill name collisions (e.g. career hub + career skill).
        # If namespaced skill entries exist for this name, require at least one
        # enabled skill in addition to the base hub/skill key.
        suffix = f"/{plugin_name}"
        matching_skill_states = [
            enabled for key, enabled in self.plugin_state.items() if key.startswith("skill:") and key.endswith(suffix)
        ]
        if matching_skill_states:
            return base_enabled and any(matching_skill_states)

        return base_enabled

    def is_tool_enabled_for_plugin_state(self, tool_name: str, plugin_name: str | None = None) -> bool:
        """
        Check if a tool should be enabled based on its plugin's state.

        Tools from disabled plugins are filtered out. Core tools are always enabled.

        Args:
            tool_name: Name of the MCP tool
            plugin_name: Optional plugin/skill name that owns this tool

        Returns:
            True if tool should be loaded
        """
        # Core tools are always enabled
        core_tools = [
            "list-skills",
            "get-skill",
            "load-module",
            "skill-action",
            "execute-chain",
            "list-chains",
            "switch-mcp-context",
            "get-config",
            "get-context",
            "get-chat-session",
            "update-chat-session",
            "metrics",
            "health",
        ]
        # Normalize tool name (replace underscores with hyphens for comparison)
        normalized_tool = tool_name.replace("_", "-").lower()
        if normalized_tool in core_tools or tool_name in core_tools:
            return True

        # If plugin name is provided, check its state
        if plugin_name:
            return self.is_plugin_enabled(plugin_name)

        # ADR-250: Derive plugin prefixes from discovery instead of hardcoding.
        for prefix in self._get_plugin_prefixes():
            if tool_name.startswith(prefix + "-") or tool_name.startswith(prefix + "_"):
                return self.is_plugin_enabled(prefix)

        # If we can't determine the plugin, allow the tool
        return True

    def _get_plugin_prefixes(self) -> list[str]:
        """Derive plugin prefixes from plugin_state keys.

        ADR-250: Replaces hardcoded plugin_prefixes list. Derived from the
        same plugin state already loaded by _load_plugin_state(), avoiding
        a redundant filesystem scan. Cached after first call.
        """
        if self._plugin_prefixes_cache is not None:
            return self._plugin_prefixes_cache

        self._plugin_prefixes_cache = [k for k in self.plugin_state if not k.startswith("skill:")]
        return self._plugin_prefixes_cache

    def reload_plugin_state(self) -> None:
        """Reload plugin state from file."""
        self.plugin_state = self._load_plugin_state()
        self._plugin_prefixes_cache = None

    def get_active_tools(self, context: dict) -> list[str]:
        """
        Get list of active tools based on context.

        ADR-250: Simplified — only used by web-chat clients for page-scoped
        filtering. CLI/IDE clients bypass this entirely.

        Args:
            context: Context dictionary with keys:
                - current_page: str (e.g., "/career", "/health")

        Returns:
            List of tool names (max 80)
        """
        tools: set[str] = set()

        # Always include core tools
        tools.update(self.tool_groups.get("CORE", []))

        # Add page-specific tool groups from config
        current_page = context.get("current_page", "")
        for group_name, group_tools in self.tool_groups.items():
            if group_name == "CORE":
                continue
            tools.update(group_tools)

        # Limit to max_tools
        tool_list = list(tools)[: self.max_tools]

        logger.debug(
            f"Selected {len(tool_list)}/{len(tools)} tools for page '{current_page}'",
            extra={"context": context, "tool_count": len(tool_list)},
        )

        return tool_list

    def get_tool_count(self, context: dict) -> int:
        """
        Get count of active tools for given context.

        Args:
            context: Context dictionary

        Returns:
            Number of tools that would be active
        """
        return len(self.get_active_tools(context))

    def reload_config(self) -> None:
        """Reload tool groups and plugin state from configuration files."""
        logger.info("Reloading tool controller configuration")
        self.tool_groups = self._load_tool_groups()
        self.plugin_state = self._load_plugin_state()
        self._plugin_prefixes_cache = None

    def get_all_tool_groups(self) -> dict[str, list[str]]:
        """
        Get all tool groups.

        Returns:
            Dictionary of all tool groups
        """
        return self.tool_groups.copy()

    def validate_context(self, context: dict) -> bool:
        """
        Validate that context has required fields.

        Args:
            context: Context dictionary to validate

        Returns:
            True if valid, False otherwise
        """
        # Context is optional, so empty dict is valid
        if not isinstance(context, dict):
            logger.warning(f"Invalid context type: {type(context)}")
            return False

        return True


# Singleton instance
_controller_instance: ToolController | None = None


def get_tool_controller() -> ToolController:
    """
    Get singleton tool controller instance.

    Returns:
        ToolController instance
    """
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = ToolController()
    return _controller_instance


def reload_tool_controller() -> None:
    """Force reload of tool controller configuration."""
    global _controller_instance
    if _controller_instance is not None:
        _controller_instance.reload_config()
