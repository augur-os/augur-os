"""
MCP Context Manager - Dynamic Tool Loading & ADR-030 Merge Algorithm

Manages context-aware tool loading based on dashboard page navigation.
Dynamically adds/removes MCP tools to optimize performance and reduce cognitive load.

Also implements the ADR-030 unified context merge algorithm:
- Skill/MCP overlap resolution
- Mode-based filtering (dev/ops)
- User settings overrides
- Client capability detection

Architecture:
- Core tools (10): Always loaded
- Page tools (20-30): Loaded based on current page
- External mode (10): Dashboard closed, minimal context

Merge Priority (Highest to Lowest):
    1. User Settings - Always override
    2. Dev/Operation Mode - Different tool sets
    3. Open Web Page Context - Browser integration
    4. Core Skills - MCP basic tools (no plugins required)
    5. Linked Skills - Project-specific, may overlap with MCP
    6. MCP Commands - Auto-disabled if covered by higher-priority skill

Performance:
- Tool swap: ~15ms for 50 tools (POC-proven)
- Target: < 100ms p95
- Preload on hover for 0ms perceived latency
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import yaml
from mcp.server.fastmcp import FastMCP
from src.mcp.augur_shared.config import get_config_dir, get_project_root
from src.mcp.augur_shared.context_types import (
    CLIENT_CAPABILITIES,
    DEFAULT_MODE,
    VALID_MODES,
    WEB_CHAT_CLIENT,
    AugurMode,
    ClientCapability,
    MCPToolState,
    MergedContext,
    PageContext,
    Skill,
    UserSettings,
)
from src.mcp.augur_shared.logging import get_entity_logger

logger = get_entity_logger("mcp.context")

# Re-exported for backwards-compatible imports from this module. The data
# models live in context_types (a leaf); ContextManager + the singleton stay
# here. Importers of src.mcp.augur_shared.context_manager are unchanged.
__all__ = [
    "AugurMode",
    "ClientCapability",
    "Skill",
    "MCPToolState",
    "UserSettings",
    "PageContext",
    "MergedContext",
    "ContextManager",
    "DEFAULT_MODE",
    "VALID_MODES",
    "CLIENT_CAPABILITIES",
    "WEB_CHAT_CLIENT",
    "get_context_manager",
    "get_context_manager_if_ready",
    "reset_context_manager",
]


class ContextManager:
    """
    Dynamic MCP tool manager for context-aware loading and ADR-030 merge.

    Loads/unloads tools based on:
    - Current dashboard page (/brain, /workforce, /settings)
    - Dashboard open/closed state
    - User preferences

    Also implements ADR-030 merge algorithm:
    - Skill/MCP overlap resolution (full-capability clients)
    - Mode-based skill filtering (dev/ops)
    - User settings overrides (highest priority)
    """

    def __init__(
        self,
        mcp_instance: FastMCP,
        config_path: Path | None = None,
        client: str = "claude_code",
    ):
        """
        Initialize context manager.

        Args:
            mcp_instance: FastMCP server instance
            config_path: Path to mcp_tool_groups.yaml (default: augur/config/)
            client: AI client identifier for capability detection
        """
        self.mcp = mcp_instance
        # ADR-260: Try assembled_tool_config.json first, fall back to mcp_tool_groups.yaml
        self.config_path = config_path or self._resolve_config_path()

        # ADR-030: Client capability detection
        self.client = client
        self.capability = CLIENT_CAPABILITIES.get(client, ClientCapability.NONE)
        self._cached_mode: str | None = None

        # Load configuration
        self.config = self._load_config()
        self.core_tools: set[str] = set(self.config.get("core_tools", []))
        self.tool_groups: dict[str, list[str]] = self.config.get("tool_groups", {})
        self.pages: dict[str, dict] = self.config.get("pages", {})
        self.skill_tool_groups: dict[str, dict] = self.config.get("skill_tool_groups", {})

        # State tracking
        self.current_page: str = "/"
        self.active_tools: set[str] = set()
        self.tool_registry: dict[str, Any] = {}  # tool_name -> tool_function

        # Performance tracking
        self.switch_count: int = 0
        self.total_switch_time_ms: float = 0.0
        self.preload_hits: int = 0
        self.preload_requests: int = 0

        logger.info(
            "Context manager initialized",
            extra={
                "core_tools": len(self.core_tools),
                "total_tool_groups": len(self.tool_groups),
                "pages": len(self.pages),
            },
        )

    @staticmethod
    def _resolve_config_path() -> Path:
        """ADR-260: Resolve config path — assembled JSON first, YAML fallback."""
        assembled = get_config_dir() / "dashboard" / "generated" / "assembled_tool_config.json"
        if assembled.exists():
            return assembled
        # Try config/dashboard/ first, then config/ (canonical location)
        dashboard_yaml = get_config_dir() / "dashboard" / "mcp_tool_groups.yaml"
        if dashboard_yaml.exists():
            return dashboard_yaml
        return get_config_dir() / "mcp_tool_groups.yaml"

    def _load_config(self) -> dict:
        """Load configuration from JSON or YAML file."""
        if not self.config_path.exists():
            logger.warning(f"Config not found: {self.config_path}, using defaults")
            return self._get_default_config()

        try:
            with open(self.config_path) as f:
                if self.config_path.suffix == ".json":
                    config = json.load(f)
                else:
                    config = yaml.safe_load(f)
                logger.info(f"Loaded config from {self.config_path}")
                return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}", exc_info=True)
            return self._get_default_config()

    def _get_default_config(self) -> dict:
        """Get default configuration if YAML not found."""
        return {
            "version": "2.0.0",
            "core_tools": [
                "list-skills",
                "get-skill",
                "load-module",
                "skill-action",
                "find-skill",
                "get-config",
                "health",
                "metrics",
                "system-open",
                "system-open-file",
                "switch-mcp-context",
                "configure-mcp-server",
                "get-mcp-context-stats",
                "list-mcp-tools",
                "test-mcp-connection",
                "get-mcp-diagnostics",
                "get-api-route-stats",
                "preload-mcp-context",
                "get-chat-session",
                "update-chat-session",
                "list-jobs",
            ],
            "pages": {
                "/": {"groups": [], "max_tools": 10},
                "/brain": {"groups": ["BRAIN_DATA", "BRAIN_BUGS", "BRAIN_INTEL"], "max_tools": 30},
                "/workforce": {"groups": ["WORKFORCE_CHAINS", "WORKFORCE_SELF_UPDATE"], "max_tools": 30},
                "/settings": {"groups": ["SETTINGS_MGMT"], "max_tools": 19},
            },
            "tool_groups": {},
            "context_switching": {"enabled": True},
        }

    def register_tool(self, tool_name: str, tool_function: Any):
        """
        Register a tool for dynamic loading.

        Args:
            tool_name: Tool identifier (e.g., "search-documents")
            tool_function: Async function decorated with @mcp.tool
        """
        self.tool_registry[tool_name] = tool_function
        logger.debug(f"Registered tool: {tool_name}")

    def initialize_core_tools(self):
        """Mark core tools as active (they're already registered at startup)."""
        self.active_tools = self.core_tools.copy()
        logger.info("Initialized core tools", extra={"count": len(self.active_tools), "tools": list(self.active_tools)})

    def get_tools_for_page(self, page: str) -> set[str]:
        """
        Get tool names for a specific page.

        Args:
            page: Page path (e.g., "/brain", "/workforce")

        Returns:
            Set of tool names for that page
        """
        # Always include core tools
        tools = self.core_tools.copy()

        # Get page configuration
        page_config = self.pages.get(page, self.pages.get("/", {}))
        groups = page_config.get("groups", [])

        # Add tools from each group
        for group_name in groups:
            group_tools = self.tool_groups.get(group_name, [])
            tools.update(group_tools)

        logger.debug(f"Tools for page {page}", extra={"count": len(tools), "groups": groups})

        return tools

    async def switch_context(self, target_page: str, preloaded: bool = False) -> dict[str, Any]:
        """
        Switch active tools to match target page.

        Args:
            target_page: Target page path (e.g., "/workforce")
            preloaded: Whether tools were preloaded on hover

        Returns:
            Dict with switch metrics:
            {
                "success": bool,
                "removed": List[str],
                "added": List[str],
                "active_count": int,
                "duration_ms": float,
                "preloaded": bool
            }
        """
        start_time = time.time()

        try:
            # Get tools for target page
            target_tools = self.get_tools_for_page(target_page)

            # Calculate diff
            current_non_core = self.active_tools - self.core_tools
            target_non_core = target_tools - self.core_tools

            to_remove = current_non_core - target_non_core
            to_add = target_non_core - current_non_core

            logger.info(
                f"Context switch: {self.current_page} → {target_page}",
                extra={"remove": len(to_remove), "add": len(to_add), "preloaded": preloaded},
            )

            # Keep all runtime tools registered. Context switching only changes
            # the visibility/active set used for filtering and diagnostics.
            removed = sorted(to_remove)
            added = sorted(to_add)

            # Update state
            self.current_page = target_page
            self.active_tools = target_tools

            # Track performance
            duration_ms = (time.time() - start_time) * 1000
            self.switch_count += 1
            self.total_switch_time_ms += duration_ms

            if preloaded:
                self.preload_hits += 1

            result = {
                "success": True,
                "removed": removed,
                "added": added,
                "active_count": len(self.active_tools),
                "duration_ms": round(duration_ms, 2),
                "preloaded": preloaded,
                "current_page": target_page,
            }

            logger.info(
                "Context switch complete",
                extra={"duration_ms": result["duration_ms"], "active_tools": result["active_count"]},
            )

            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Context switch failed: {e}",
                exc_info=True,
                extra={"target_page": target_page, "duration_ms": duration_ms},
            )
            return {"success": False, "error": str(e), "duration_ms": round(duration_ms, 2)}

    async def switch_context_by_groups(
        self, enable_groups: list[str], disable_groups: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Switch active tools based on explicit group lists.

        Args:
            enable_groups: Tool group names to enable
            disable_groups: Tool group names to disable

        Returns:
            Dict with switch results
        """
        start_time = time.time()
        disabled = set(disable_groups or [])
        enabled = {group for group in enable_groups if group not in disabled}

        try:
            target_tools = self.core_tools.copy()
            for group_name in enabled:
                group_tools = self.tool_groups.get(group_name, [])
                target_tools.update(group_tools)

            current_non_core = self.active_tools - self.core_tools
            target_non_core = target_tools - self.core_tools

            to_remove = current_non_core - target_non_core
            to_add = target_non_core - current_non_core

            # Keep all runtime tools registered. Group switches only change the
            # active set used for visibility tracking.
            removed = sorted(to_remove)
            added = sorted(to_add)

            self.active_tools = target_tools
            self.current_page = "/custom"

            duration_ms = (time.time() - start_time) * 1000
            self.switch_count += 1
            self.total_switch_time_ms += duration_ms

            return {
                "success": True,
                "removed": removed,
                "added": added,
                "active_count": len(self.active_tools),
                "duration_ms": round(duration_ms, 2),
                "enabled_groups": sorted(enabled),
                "disabled_groups": sorted(disabled),
            }
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Context switch by groups failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "duration_ms": round(duration_ms, 2),
                "enabled_groups": sorted(enabled),
                "disabled_groups": sorted(disabled),
            }

    async def _remove_tools(self, tool_names: set[str]) -> list[str]:
        """
        Remove tools from MCP.

        Args:
            tool_names: Set of tool names to remove

        Returns:
            List of successfully removed tool names
        """
        removed = []

        for tool_name in tool_names:
            try:
                self.mcp.remove_tool(tool_name)
                removed.append(tool_name)
                logger.debug(f"Removed tool: {tool_name}")
            except Exception as e:
                logger.warning(f"Failed to remove tool {tool_name}: {e}")

        return removed

    async def _add_tools(self, tool_names: set[str]) -> list[str]:
        """
        Add tools to MCP.

        Args:
            tool_names: Set of tool names to add

        Returns:
            List of successfully added tool names
        """
        added = []

        for tool_name in tool_names:
            # Check if tool is in registry
            if tool_name not in self.tool_registry:
                logger.warning(f"Tool not in registry: {tool_name}")
                continue

            try:
                tool_func = self.tool_registry[tool_name]
                # Extract underlying function from Tool object if needed
                # FastMCP stores Tool objects in _tools but add_tool() expects a function
                if hasattr(tool_func, "fn") and callable(tool_func.fn):
                    tool_func = tool_func.fn
                # Actually add the tool to FastMCP
                self.mcp.add_tool(tool_func)
                added.append(tool_name)
                logger.debug(f"Added tool: {tool_name}")
            except Exception as e:
                logger.warning(f"Failed to add tool {tool_name}: {e}")

        return added

    async def preload_context(self, target_page: str):
        """
        Preload tools for a page (called on hover).

        Args:
            target_page: Page to preload tools for
        """
        self.preload_requests += 1

        logger.debug(f"Preload requested for: {target_page}")

        # Get tools for target page
        target_tools = self.get_tools_for_page(target_page)

        # Calculate what would be added
        target_non_core = target_tools - self.core_tools
        current_non_core = self.active_tools - self.core_tools
        to_add = target_non_core - current_non_core

        # Cache tool functions in memory (lightweight operation)
        for tool_name in to_add:
            if tool_name in self.tool_registry:
                # Tool already in registry, preload is just cache warming
                pass

        logger.debug(f"Preload complete for {target_page}", extra={"tools_ready": len(to_add)})

    def get_stats(self) -> dict[str, Any]:
        """
        Get context manager statistics.

        Returns:
            Dict with performance metrics and active tool names
        """
        avg_switch_time = self.total_switch_time_ms / self.switch_count if self.switch_count > 0 else 0

        preload_hit_rate = self.preload_hits / self.preload_requests if self.preload_requests > 0 else 0

        return {
            "current_page": self.current_page,
            "active_tools": len(self.active_tools),
            "active_tool_names": sorted(list(self.active_tools)),  # NEW: List of active tool names
            "registered_tools": len(self.tool_registry),
            "switch_count": self.switch_count,
            "avg_switch_time_ms": round(avg_switch_time, 2),
            "total_switch_time_ms": round(self.total_switch_time_ms, 2),
            "preload_requests": self.preload_requests,
            "preload_hits": self.preload_hits,
            "preload_hit_rate": round(preload_hit_rate, 2),
        }

    def get_active_tools(self) -> list[str]:
        """Get list of currently active tool names."""
        return sorted(list(self.active_tools))

    # =========================================================================
    # ADR-030: Mode Detection
    # =========================================================================

    def _get_current_mode(self) -> str:
        """Get the current operating mode from persistent config.

        Reads from config/system/config.yaml under augur.mode.
        Implements ADR-030 Section 4: Mode Detection.

        Returns:
            "dev" or "ops" (default: "ops")
        """
        try:
            project_root = get_project_root()
            config_path = project_root / "config" / "system" / "config.yaml"
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

    @property
    def current_mode(self) -> str:
        """Get the current operating mode (cached per access)."""
        return self._get_current_mode()

    def invalidate_mode_cache(self) -> None:
        """Invalidate cached mode (legacy hook; set-augur-mode retired in Track 3a PR 2)."""
        self._cached_mode = None

    # =========================================================================
    # ADR-030: Context Merge Algorithm
    # =========================================================================

    def build_merged_context(
        self,
        *,
        skills: list[Skill],
        mcp_tools: list[MCPToolState],
        user_settings: UserSettings | None = None,
        page_context: PageContext | None = None,
        mode: AugurMode | None = None,
    ) -> MergedContext:
        """Build merged context using the ADR-030 priority algorithm.

        Args:
            skills: All available skills
            mcp_tools: All available MCP tools
            user_settings: User-level overrides
            page_context: Currently open dashboard page context
            mode: Operating mode override (default: read from config)

        Returns:
            MergedContext with properly prioritized tools and skills
        """
        if user_settings is None:
            user_settings = UserSettings()

        if mode is None:
            raw_mode = self._get_current_mode()
            mode = AugurMode.DEV if raw_mode == "dev" else AugurMode.OPS

        merge_log: list[str] = []
        merge_log.append(f"Client: {self.client} (capability: {self.capability.value})")
        merge_log.append(f"Mode: {mode.value}")

        # --- Priority 6 (lowest): Start with all MCP tools enabled ---
        mcp_by_name: dict[str, MCPToolState] = {t.name: t for t in mcp_tools}
        for tool in mcp_by_name.values():
            tool.enabled = True
            tool.disabled_reason = None

        # --- Priority 5: Linked Skills (filter by mode) ---
        filtered_skills = self._filter_skills_by_mode(skills, mode, merge_log)

        # --- Priority 4: Core Skills override MCP ---
        if self.capability == ClientCapability.FULL:
            self._apply_skill_mcp_overlap(filtered_skills, mcp_by_name, merge_log)
        else:
            merge_log.append(
                f"Skipping MCP auto-disable: client '{self.client}' has {self.capability.value} skill support"
            )

        # --- Priority 3: Page Context ---
        if page_context and page_context.active_tools:
            merge_log.append(f"Page context: {page_context.page_id} ({len(page_context.active_tools)} tools)")

        # --- Priority 2: Mode already applied in priority 5 ---

        # --- Priority 1 (highest): User Settings override everything ---
        self._apply_user_overrides(filtered_skills, mcp_by_name, user_settings, merge_log)

        # Build result
        enabled_skills = [s for s in filtered_skills if s.enabled]
        disabled_skills = [s for s in filtered_skills if not s.enabled]
        enabled_mcp = [t for t in mcp_by_name.values() if t.enabled]
        disabled_mcp = [t for t in mcp_by_name.values() if not t.enabled]

        merge_log.append(f"Result: {len(enabled_skills)} skills, {len(enabled_mcp)} MCP tools enabled")

        return MergedContext(
            mode=mode,
            enabled_skills=enabled_skills,
            disabled_skills=disabled_skills,
            enabled_mcp_tools=enabled_mcp,
            disabled_mcp_tools=disabled_mcp,
            page_context=page_context,
            merge_log=merge_log,
        )

    def _filter_skills_by_mode(self, skills: list[Skill], mode: AugurMode, log: list[str]) -> list[Skill]:
        """Filter skills based on current mode."""
        result = []
        skipped = 0
        for skill in skills:
            if skill.is_dev_only and mode != AugurMode.DEV:
                skill.enabled = False
                skipped += 1
            elif skill.is_ops_only and mode != AugurMode.OPS:
                skill.enabled = False
                skipped += 1
            result.append(skill)

        if skipped:
            log.append(f"Mode filter: {skipped} skills disabled (mode={mode.value})")
        return result

    def _apply_skill_mcp_overlap(
        self,
        skills: list[Skill],
        mcp_by_name: dict[str, MCPToolState],
        log: list[str],
    ) -> None:
        """Disable MCP tools that are covered by enabled skills."""
        disabled_count = 0
        for skill in skills:
            if not skill.enabled:
                continue
            for mcp_name in skill.mcp_overlaps:
                if mcp_name in mcp_by_name and mcp_by_name[mcp_name].enabled:
                    mcp_by_name[mcp_name].enabled = False
                    mcp_by_name[mcp_name].disabled_reason = f"Covered by skill '{skill.name}'"
                    disabled_count += 1

        if disabled_count:
            log.append(f"MCP auto-disable: {disabled_count} tools disabled (covered by skills)")

    def _apply_user_overrides(
        self,
        skills: list[Skill],
        mcp_by_name: dict[str, MCPToolState],
        settings: UserSettings,
        log: list[str],
    ) -> None:
        """Apply user overrides (highest priority)."""
        override_count = 0

        # Skill overrides
        for skill in skills:
            if skill.name in settings.disabled_skills:
                skill.enabled = False
                override_count += 1
            elif skill.name in settings.enabled_skills:
                skill.enabled = True
                override_count += 1

        # MCP overrides (user can re-enable auto-disabled tools)
        for tool_name, enabled in settings.mcp_overrides.items():
            if tool_name in mcp_by_name:
                mcp_by_name[tool_name].enabled = enabled
                if enabled:
                    mcp_by_name[tool_name].disabled_reason = None
                else:
                    mcp_by_name[tool_name].disabled_reason = "Disabled by user"
                override_count += 1

        if override_count:
            log.append(f"User overrides: {override_count} changes applied")

    # =========================================================================
    # Skill-Aware Context (ADR-059 superseded by ADR-254)
    # =========================================================================

    def get_skill_tools(self, skill_name: str) -> set[str]:
        """Get tool names for a specific skill from skill_tool_groups config.

        Reads skill_tool_groups from mcp_tool_groups.yaml, resolves
        include_groups references, falls back to _default if skill
        has no explicit config.

        Args:
            skill_name: Skill identifier (e.g., "career", "venture")

        Returns:
            Set of tool names for the skill
        """
        tools: set[str] = set()

        # Get skill config or fall back to _default
        skill_config = self.skill_tool_groups.get(skill_name, self.skill_tool_groups.get("_default", {}))

        # Resolve include_groups
        for group_name in skill_config.get("include_groups", []):
            group_tools = self.tool_groups.get(group_name, [])
            tools.update(group_tools)

        # Add skill-specific tools
        tools.update(skill_config.get("tools", []))

        return tools


# Singleton instance
_context_manager_instance: ContextManager | None = None


def get_context_manager_if_ready() -> ContextManager | None:
    """Return the context manager if already initialized, else None.

    Unlike get_context_manager(), this never creates a new instance.
    Used by list_tools filtering to avoid creating the manager prematurely.
    """
    return _context_manager_instance


def get_context_manager(
    mcp_instance: FastMCP | None = None,
    client: str = "claude_code",
) -> ContextManager:
    """
    Get singleton context manager instance.

    Args:
        mcp_instance: FastMCP instance (required on first call)
        client: AI client identifier for capability detection

    Returns:
        ContextManager instance
    """
    global _context_manager_instance

    if _context_manager_instance is None:
        if mcp_instance is None:
            raise ValueError("mcp_instance required on first call to get_context_manager()")

        _context_manager_instance = ContextManager(mcp_instance, client=client)

    return _context_manager_instance


def reset_context_manager():
    """Reset singleton (for testing)."""
    global _context_manager_instance
    _context_manager_instance = None
