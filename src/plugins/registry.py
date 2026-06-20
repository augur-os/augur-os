"""
Plugin registry.

Manages plugin discovery, installation, and state.
Uses per-skill .config files (ADR-129) instead of centralized plugin_state.json.
"""

import shutil
from pathlib import Path
from subprocess import CompletedProcess, run  # nosec B404
from typing import Optional

from src.logging import get_entity_logger
from src.config.paths import get_project_root
from src.plugins.schema import Plugin
from src.plugins.skill_config import is_plugin_enabled_by_config, write_config_file

logger = get_entity_logger("plugins")

# Plugin directories
PROJECT_ROOT = Path(__file__).parent.parent.parent
BUILTIN_PLUGINS_DIR = PROJECT_ROOT / "plugins"
USER_PLUGINS_DIR = get_project_root() / "plugins"


def _resolve_command(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise FileNotFoundError(f"Required executable not found in PATH: {name}")
    return resolved


class PluginRegistry:
    """Registry for managing plugins."""

    _instance: Optional["PluginRegistry"] = None

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        self._discover_plugins()

    def _discover_plugins(self) -> None:
        """Discover all plugins from builtin and user directories."""
        self._plugins = {}

        # Discover builtin plugins
        if BUILTIN_PLUGINS_DIR.exists():
            for plugin_dir in BUILTIN_PLUGINS_DIR.iterdir():
                if plugin_dir.is_dir() and not plugin_dir.name.startswith("."):
                    plugin = Plugin.from_path(plugin_dir)
                    if plugin:
                        plugin.builtin = True
                        # ADR-129: Read .config file for enabled state
                        plugin.enabled = is_plugin_enabled_by_config(plugin_dir)
                        self._plugins[plugin.name] = plugin
                        logger.debug(f"Discovered builtin plugin: {plugin.name}")

        # Discover user-installed plugins
        if USER_PLUGINS_DIR.exists():
            for plugin_dir in USER_PLUGINS_DIR.iterdir():
                if plugin_dir.is_dir() and not plugin_dir.name.startswith("."):
                    plugin = Plugin.from_path(plugin_dir)
                    if plugin:
                        plugin.builtin = False
                        # ADR-129: Read .config file for enabled state
                        plugin.enabled = is_plugin_enabled_by_config(plugin_dir)
                        self._plugins[plugin.name] = plugin
                        logger.debug(f"Discovered user plugin: {plugin.name}")

        logger.info(f"Discovered {len(self._plugins)} plugins")

    def list_plugins(self, enabled_only: bool = False) -> list[Plugin]:
        """List all plugins."""
        plugins = list(self._plugins.values())
        if enabled_only:
            plugins = [p for p in plugins if p.enabled]
        return sorted(plugins, key=lambda p: p.name)

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def enable_plugin(self, name: str) -> bool:
        """Enable a plugin by writing .config (ADR-129)."""
        if name not in self._plugins:
            return False
        self._plugins[name].enabled = True
        write_config_file(self._plugins[name].path, enabled=True)
        logger.info(f"Enabled plugin: {name}")
        return True

    def disable_plugin(self, name: str) -> bool:
        """Disable a plugin by writing .config (ADR-129)."""
        if name not in self._plugins:
            return False
        self._plugins[name].enabled = False
        write_config_file(self._plugins[name].path, enabled=False)
        logger.info(f"Disabled plugin: {name}")
        return True

    def toggle_plugin(self, name: str) -> bool:
        """Toggle plugin enabled state. Returns new state."""
        if name not in self._plugins:
            raise ValueError(f"Plugin not found: {name}")
        new_state = not self._plugins[name].enabled
        if new_state:
            self.enable_plugin(name)
        else:
            self.disable_plugin(name)
        return new_state

    def install_plugin(self, source: str, name: Optional[str] = None) -> Plugin:
        """Install a plugin from a source (git URL or local path)."""
        USER_PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

        source_path = Path(source)

        if source_path.exists():
            # Local path installation
            plugin_name = name or source_path.name
            target_dir = USER_PLUGINS_DIR / plugin_name

            if target_dir.exists():
                raise ValueError(f"Plugin already exists: {plugin_name}")

            shutil.copytree(source_path, target_dir)
            logger.info(f"Installed plugin from local path: {plugin_name}")

        elif source.startswith("http") or source.startswith("git@"):
            # Git URL installation
            plugin_name = name or source.split("/")[-1].replace(".git", "")
            target_dir = USER_PLUGINS_DIR / plugin_name

            if target_dir.exists():
                raise ValueError(f"Plugin already exists: {plugin_name}")

            result: CompletedProcess[str] = run(
                [_resolve_command("git"), "clone", source, str(target_dir)],
                capture_output=True,
                text=True,
                check=False,
            )  # nosec B603
            if result.returncode != 0:
                raise ValueError(f"Failed to clone plugin: {result.stderr}")
            logger.info(f"Installed plugin from git: {plugin_name}")

        else:
            raise ValueError(f"Invalid source: {source}")

        # Load the installed plugin
        plugin = Plugin.from_path(target_dir)
        if not plugin:
            shutil.rmtree(target_dir)
            raise ValueError("Invalid plugin: missing .augur-plugin/plugin.json")

        plugin.builtin = False
        plugin.enabled = True
        self._plugins[plugin.name] = plugin
        write_config_file(plugin.path, enabled=True)

        return plugin

    def uninstall_plugin(self, name: str) -> bool:
        """Uninstall a user-installed plugin."""
        plugin = self._plugins.get(name)
        if not plugin:
            return False

        if plugin.builtin:
            raise ValueError(f"Cannot uninstall builtin plugin: {name}")

        # Remove plugin directory
        if plugin.path.exists():
            shutil.rmtree(plugin.path)

        # Remove from registry
        del self._plugins[name]

        logger.info(f"Uninstalled plugin: {name}")
        return True

    def health_check(self) -> dict:
        """Run health check on all plugins."""
        healthy = []
        unhealthy = []
        disabled = []

        for plugin in self._plugins.values():
            if not plugin.enabled:
                disabled.append(plugin.name)
                continue

            # Check plugin directory exists
            if not plugin.path.exists():
                unhealthy.append(
                    {
                        "name": plugin.name,
                        "error": "Plugin directory not found",
                    }
                )
                continue

            # Check plugin.json exists
            plugin_json = plugin.path / ".augur-plugin" / "plugin.json"
            if not plugin_json.exists():
                unhealthy.append(
                    {
                        "name": plugin.name,
                        "error": "Missing .augur-plugin/plugin.json",
                    }
                )
                continue

            healthy.append(plugin.name)

        return {
            "total": len(self._plugins),
            "healthy": healthy,
            "unhealthy": unhealthy,
            "disabled": disabled,
        }

    def refresh(self) -> None:
        """Refresh plugin discovery."""
        self._discover_plugins()


# Singleton accessor
_registry: Optional[PluginRegistry] = None


def get_plugin_registry() -> PluginRegistry:
    """Get the singleton plugin registry."""
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry


__all__ = ["PluginRegistry", "get_plugin_registry"]
