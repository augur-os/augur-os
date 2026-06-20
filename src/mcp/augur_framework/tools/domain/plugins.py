"""
Plugin & Skill Management MCP Tools.

MCP tools for managing plugins and skills:
- Plugin level: list, toggle, install, uninstall, health check, reload
- Skill level: toggle, uninstall (individual skills within plugins)

NOTE: Uses compat layer for src/lib.* imports to support standalone operation.

Merged from:
- domain/plugins.py (plugin management)
- domain/skills.py (skill management)
"""

import asyncio
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field
from src.config.paths import (
    get_managed_skill_source_dirs,
    get_project_brain_skills_dir,
)
from src.mcp.augur_shared.annotations import tool_annotations
from src.mcp.augur_shared.compat import get_plugin_loader, get_plugin_registry
from src.mcp.augur_shared.config import get_project_root as get_mcp_project_root
from src.mcp.augur_shared.logging import get_entity_logger
from src.plugins.skill_ui_state import (
    is_skill_enabled as is_skill_enabled_runtime,
)
from src.plugins.skill_ui_state import (
    remove_skill_local_state,
    set_skill_enabled,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_entity_logger("mcp")

PROJECT_ROOT = get_mcp_project_root()


def _resolve_project_skill_target(name: str, skills_dir: Path | None = None) -> tuple[str, Path]:
    """Validate a plugin name and resolve its project-brain target path."""
    plugin_name = (name or "").strip()
    if not plugin_name or plugin_name in {".", ".."}:
        raise ValueError("Plugin name cannot be empty, '.', or '..'")
    if "/" in plugin_name or "\\" in plugin_name:
        raise ValueError(f"Invalid plugin name: {plugin_name}")

    root = skills_dir or get_project_brain_skills_dir(PROJECT_ROOT)
    target_dir = root / plugin_name
    if not target_dir.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Plugin path escapes project-brain skills directory: {plugin_name}")
    return plugin_name, target_dir


# =============================================================================
# Pydantic Input Models
# =============================================================================


class ListPluginsInput(BaseModel):
    """Input for list-plugins MCP tool."""

    model_config = ConfigDict(extra="forbid")
    enabled_only: bool = Field(False, description="Only show enabled plugins")


class TogglePluginInput(BaseModel):
    """Input for toggle-plugin MCP tool."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., description="Plugin name to toggle")
    enabled: bool | None = Field(None, description="Set enabled state (or toggle if not specified)")


class InstallPluginInput(BaseModel):
    """Input for install-plugin MCP tool."""

    model_config = ConfigDict(extra="forbid")
    source: str = Field(..., description="Git URL, local path, or marketplace ID")
    name: str | None = Field(None, description="Override plugin name")


class UninstallPluginInput(BaseModel):
    """Input for uninstall-plugin MCP tool."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., description="Plugin name to uninstall")


# =============================================================================
# Tool Registration
# =============================================================================


def register_plugin_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable,
    metrics: Any,
) -> None:
    """
    Register Plugin tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        mcp_tool_interceptor: Decorator for tool interception
        metrics: MetricsTracker instance for telemetry
    """

    @mcp.tool(
        name="list-plugins",
        annotations=tool_annotations(
            {
                "title": "List Plugins",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_plugins_tool(enabled_only: bool = False) -> str:
        """List all installed plugins with their status.

        Args:
            enabled_only: Only show enabled plugins

        Returns:
            str: JSON with list of plugins
        """
        metrics.track_tool("list_plugins")

        try:
            registry = get_plugin_registry()
            if not registry:
                return json.dumps({"success": False, "error": "Plugin registry not available"})

            plugins = registry.list_plugins(enabled_only=enabled_only)

            return json.dumps(
                {
                    "success": True,
                    "total": len(plugins),
                    "plugins": [p.to_dict() for p in plugins],
                },
                indent=2,
            )

        except Exception as e:
            logger.error(f"Failed to list plugins: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="toggle-plugin",
        annotations=tool_annotations(
            {
                "title": "Toggle Plugin",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def toggle_plugin_tool(name: str, enabled: bool | None = None) -> str:
        """Enable or disable a plugin.

        Args:
            name: Plugin name to toggle
            enabled: Set enabled state (or toggle if not specified)

        Returns:
            str: JSON with new plugin state
        """
        metrics.track_tool("toggle_plugin")

        try:
            registry = get_plugin_registry()
            loader = get_plugin_loader()

            if not registry or not loader:
                return json.dumps({"success": False, "error": "Plugin system not available"})

            plugin = registry.get_plugin(name)
            if not plugin:
                return json.dumps({"success": False, "error": f"Plugin not found: {name}"})

            if enabled is not None:
                if enabled:
                    registry.enable_plugin(name)
                    loader.load_plugin(plugin)
                else:
                    registry.disable_plugin(name)
                    loader.unload_plugin(name)
                new_state = enabled
            else:
                new_state = registry.toggle_plugin(name)
                if new_state:
                    loader.load_plugin(plugin)
                else:
                    loader.unload_plugin(name)

            return json.dumps(
                {
                    "success": True,
                    "plugin": name,
                    "enabled": new_state,
                },
                indent=2,
            )

        except Exception as e:
            logger.error(f"Failed to toggle plugin: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="install-plugin",
        annotations=tool_annotations(
            {
                "title": "Install Plugin",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def install_plugin_tool(source: str, name: str | None = None) -> str:
        """Install a plugin from a git URL, local path, or tarball.

        Args:
            source: Git URL (.git), local directory path, or tarball (.tar.gz/.tgz)
            name: Override plugin name (defaults to directory/repo name)

        Hubs were retired in ADR-802; the installed plugin no longer carries a
        hub assignment (reported as "unknown").

        Returns:
            str: JSON with installation result
        """
        metrics.track_tool("install_plugin")

        try:
            import tarfile
            import tempfile

            from src.mcp.augur_shared.safe_subprocess import safe_run

            # Hub values are self-declared via SKILL.md frontmatter — no allowlist needed.
            # Skills install into project-brain/capabilities/skills/{name}/.
            skills_dir = get_project_brain_skills_dir(PROJECT_ROOT)
            skills_dir.mkdir(parents=True, exist_ok=True)

            source_path = Path(source).expanduser()

            # Determine source type and extract/clone
            if source.endswith(".git") or source.startswith("https://") or source.startswith("git@"):
                # Git clone
                plugin_name, target_dir = _resolve_project_skill_target(
                    name or source.rstrip("/").split("/")[-1].replace(".git", ""),
                    skills_dir,
                )

                if target_dir.exists():
                    return json.dumps({"success": False, "error": f"Plugin directory already exists: {target_dir}"})

                result = await asyncio.to_thread(
                    safe_run,
                    ["git", "clone", "--depth", "1", source, str(target_dir)],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode != 0:
                    return json.dumps({"success": False, "error": f"Git clone failed: {result.stderr}"})

                # Remove .git directory from cloned plugin
                git_dir = target_dir / ".git"
                if git_dir.exists():
                    await asyncio.to_thread(shutil.rmtree, git_dir)

            elif source_path.is_dir():
                # Local directory copy
                plugin_name, target_dir = _resolve_project_skill_target(name or source_path.name, skills_dir)

                if target_dir.exists():
                    return json.dumps({"success": False, "error": f"Plugin directory already exists: {target_dir}"})

                await asyncio.to_thread(shutil.copytree, str(source_path), str(target_dir))

            elif source.endswith((".tar.gz", ".tgz")):
                # Tarball extraction
                if not source_path.is_file():
                    return json.dumps({"success": False, "error": f"Tarball not found: {source}"})

                with tempfile.TemporaryDirectory() as tmp:
                    with tarfile.open(str(source_path), "r:gz") as tar:
                        # Validate no path traversal in tarball
                        tmp_resolved = Path(tmp).resolve()
                        for member in tar.getmembers():
                            member_path = (tmp_resolved / member.name).resolve()
                            if not str(member_path).startswith(str(tmp_resolved)):
                                return json.dumps({"success": False, "error": "Tarball contains path traversal"})
                        tar.extractall(tmp, filter="data")

                    # Find the root directory in the extracted content
                    extracted = list(Path(tmp).iterdir())
                    if len(extracted) == 1 and extracted[0].is_dir():
                        extract_root = extracted[0]
                    else:
                        extract_root = Path(tmp)

                    plugin_name, target_dir = _resolve_project_skill_target(name or extract_root.name, skills_dir)

                    if target_dir.exists():
                        return json.dumps({"success": False, "error": f"Plugin directory already exists: {target_dir}"})

                    await asyncio.to_thread(shutil.copytree, str(extract_root), str(target_dir))
            else:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Unknown source type: {source}. Provide a git URL, local path, or .tar.gz",
                    }
                )

            # Validate: SKILL.md must exist
            skill_md = target_dir / "SKILL.md"
            if not skill_md.exists():
                await asyncio.to_thread(shutil.rmtree, str(target_dir))
                return json.dumps({"success": False, "error": "Invalid plugin: SKILL.md not found. Plugin removed."})

            # Enable plugin via the canonical runtime-backed local skill state.
            set_skill_enabled(plugin_name, True)

            return json.dumps(
                {
                    "success": True,
                    "plugin": plugin_name,
                    # Hubs were retired in ADR-802; skills no longer declare one.
                    "hub": "unknown",
                    "path": str(target_dir),
                    "message": f"Plugin '{plugin_name}' installed to project-brain/capabilities/skills/{plugin_name}/ and enabled",
                },
                indent=2,
            )

        except Exception as e:
            logger.error(f"Failed to install plugin: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="uninstall-plugin",
        annotations=tool_annotations(
            {
                "title": "Uninstall Plugin",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def uninstall_plugin_tool(name: str) -> str:
        """Uninstall a user-installed plugin.

        Removes the plugin directory and its local enablement state.
        Core plugins (shipped with the repo via git) cannot be uninstalled.
        Plugins with enabled dependents cannot be uninstalled.

        Args:
            name: Plugin name to uninstall

        Returns:
            str: JSON with uninstallation result
        """
        metrics.track_tool("uninstall_plugin")

        try:
            import yaml as _yaml
            from src.mcp.augur_shared.safe_subprocess import safe_run

            # Find the plugin directory in project-brain/capabilities/skills.
            plugin_name, plugin_dir = _resolve_project_skill_target(name)
            if not plugin_dir.is_dir():
                return json.dumps({"success": False, "error": f"Plugin not found: {name}"})

            # Check if this is a core plugin (tracked by git)
            try:
                result = safe_run(
                    ["git", "ls-files", str(plugin_dir.relative_to(PROJECT_ROOT))],
                    capture_output=True,
                    text=True,
                    cwd=str(PROJECT_ROOT),
                    timeout=10,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return json.dumps(
                        {
                            "success": False,
                            "error": f"Cannot uninstall core plugin '{name}'. Core plugins ship with the repository.",
                        }
                    )
            except Exception:
                pass  # If git check fails, allow uninstall

            # Check for required dependents via SKILL.md x-augur-dependencies frontmatter
            dependents: list[str] = []
            for skills_root in get_managed_skill_source_dirs(PROJECT_ROOT):
                for skill_dir in skills_root.iterdir():
                    if not skill_dir.is_dir() or skill_dir.name == plugin_name:
                        continue
                    skill_md = skill_dir / "SKILL.md"
                    if not skill_md.exists():
                        continue
                    try:
                        # Parse YAML frontmatter from SKILL.md
                        content = skill_md.read_text()
                        if not content.startswith("---"):
                            continue
                        end = content.index("---", 3)
                        frontmatter = _yaml.safe_load(content[3:end])
                        if not isinstance(frontmatter, dict):
                            continue
                        deps = frontmatter.get("x-augur-dependencies", {})
                        if not isinstance(deps, dict):
                            continue
                        required = deps.get("required", [])
                        if not isinstance(required, list):
                            continue
                        if plugin_name in required and is_skill_enabled_runtime(skill_dir.name):
                            dependents.append(skill_dir.name)
                    except Exception:
                        continue

            if dependents:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Cannot uninstall '{plugin_name}': required by enabled plugins: {', '.join(dependents)}",
                        "dependents": dependents,
                    }
                )

            # Remove plugin directory
            await asyncio.to_thread(shutil.rmtree, str(plugin_dir))

            # Also clear any runtime-backed local skill state.
            remove_skill_local_state(plugin_name)

            return json.dumps(
                {
                    "success": True,
                    "plugin": plugin_name,
                    "message": f"Plugin '{plugin_name}' uninstalled and removed from disk",
                },
                indent=2,
            )

        except Exception as e:
            logger.error(f"Failed to uninstall plugin: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="plugin-health",
        annotations=tool_annotations(
            {
                "title": "Plugin Health Check",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def plugin_health_tool() -> str:
        """Run health check on all plugins.

        Returns:
            str: JSON with health status for all plugins
        """
        metrics.track_tool("plugin_health")

        try:
            registry = get_plugin_registry()
            if not registry:
                return json.dumps({"success": False, "error": "Plugin registry not available"})

            health = registry.health_check()

            return json.dumps(
                {
                    "success": True,
                    **health,
                },
                indent=2,
            )

        except Exception as e:
            logger.error(f"Failed to check plugin health: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="reload-plugin",
        annotations=tool_annotations(
            {
                "title": "Reload Plugin",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def reload_plugin_tool(name: str) -> str:
        """Reload a plugin to pick up changes.

        Args:
            name: Plugin name to reload

        Returns:
            str: JSON with reload result
        """
        metrics.track_tool("reload_plugin")

        try:
            loader = get_plugin_loader()
            if not loader:
                return json.dumps({"success": False, "error": "Plugin loader not available"})

            success = loader.reload_plugin(name)

            if success:
                return json.dumps(
                    {
                        "success": True,
                        "message": f"Plugin '{name}' reloaded",
                    },
                    indent=2,
                )
            else:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Plugin not found: {name}",
                    },
                    indent=2,
                )

        except Exception as e:
            logger.error(f"Failed to reload plugin: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    # =========================================================================
    # Skill Management Tools (merged from domain/skills.py)
    # =========================================================================

    @mcp.tool(
        name="toggle-skill",
        annotations=tool_annotations(
            {
                "title": "Toggle Skill",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def toggle_skill_tool(
        skill_id: str, enabled: bool, capability: str | None = None, toggle_type: str = "skill"
    ) -> str:
        """Toggle skill or capability enabled state.

        Args:
            skill_id: ID of the skill to toggle
            enabled: Whether to enable or disable
            capability: Specific capability to toggle (if type is 'capability')
            toggle_type: Type of toggle ('skill' or 'capability')

        Returns:
            str: JSON with toggle result
        """
        metrics.track_tool("toggle_skill")

        try:
            from src.plugins.skill_ui_state import (
                read_disabled_skills,
                set_capability_enabled,
                set_skill_enabled,
            )

            # Prevent disabling core skills
            CORE_SKILLS = {"augur-mcp", "setup-manager"}
            if skill_id in CORE_SKILLS and not enabled:
                return json.dumps({"success": False, "error": "Cannot disable core skills"})

            if toggle_type == "skill":
                state = await asyncio.to_thread(set_skill_enabled, skill_id, enabled)
                return json.dumps(
                    {
                        "success": True,
                        "disabled": state.get("disabled", sorted(read_disabled_skills())),
                        "message": f"{'Enabled' if enabled else 'Disabled'} {skill_id}",
                    },
                    indent=2,
                )
            elif toggle_type == "capability" and capability:
                state = await asyncio.to_thread(
                    set_capability_enabled,
                    skill_id,
                    capability,
                    enabled,
                )
                return json.dumps(
                    {
                        "success": True,
                        "partial": state.get("partial", {}),
                        "message": f"{'Enabled' if enabled else 'Disabled'} {capability}",
                    },
                    indent=2,
                )
            else:
                return json.dumps({"success": False, "error": "Invalid toggle type"})

        except Exception as e:
            logger.error(f"Failed to toggle skill: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="get-plugin-load-status",
        annotations=tool_annotations(
            {
                "title": "Plugin Load Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_plugin_load_status_tool() -> str:
        """Return which plugin skills failed to load MCP tools and why."""
        from src.mcp.augur_shared.plugin_tools import get_failed_plugins

        failed = get_failed_plugins()
        return json.dumps(
            {
                "failed_plugins": failed,
                "total_failed": len(failed),
                "status": "healthy" if not failed else "degraded",
            }
        )

    # NOTE: list-skills tool is provided by core/__init__.py
    # The version here was removed to avoid duplicate registration


__all__ = ["register_plugin_tools"]
