"""
Plugin loader.

Handles loading, unloading, and reloading plugins at runtime.
"""

from typing import Optional

from src.logging import get_entity_logger
from src.plugins.schema import Plugin

logger = get_entity_logger("plugins")


class PluginLoader:
    """Loader for managing plugin lifecycle at runtime."""

    _instance: Optional["PluginLoader"] = None

    def __init__(self) -> None:
        self._loaded: dict[str, Plugin] = {}

    def load_plugin(self, plugin: Plugin) -> bool:
        """Load a plugin and register its components."""
        if plugin.name in self._loaded:
            logger.debug(f"Plugin already loaded: {plugin.name}")
            return True

        try:
            # Register skills from the plugin
            skills_dir = plugin.path / "skills"
            if skills_dir.exists():
                skill_count = sum(1 for _ in skills_dir.iterdir() if _.is_dir())
                logger.debug(f"Plugin {plugin.name} has {skill_count} skills")

            # Register commands from the plugin
            commands_dir = plugin.path / "commands"
            if commands_dir.exists():
                cmd_count = sum(1 for _ in commands_dir.glob("*.md"))
                logger.debug(f"Plugin {plugin.name} has {cmd_count} commands")

            # Register hooks from the plugin
            if plugin.hooks.pre_tool_use or plugin.hooks.post_tool_use:
                logger.debug(f"Plugin {plugin.name} has hooks configured")

            self._loaded[plugin.name] = plugin
            logger.info(f"Loaded plugin: {plugin.name} v{plugin.version}")
            return True

        except Exception as e:
            logger.error(f"Failed to load plugin {plugin.name}: {e}")
            return False

    def unload_plugin(self, name: str) -> bool:
        """Unload a plugin and unregister its components."""
        if name not in self._loaded:
            logger.debug(f"Plugin not loaded: {name}")
            return False

        try:
            plugin = self._loaded[name]

            # Unregister components (hooks, commands, etc.)
            logger.debug(f"Unregistering components for plugin: {name}")

            del self._loaded[name]
            logger.info(f"Unloaded plugin: {plugin.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to unload plugin {name}: {e}")
            return False

    def reload_plugin(self, name: str) -> bool:
        """Reload a plugin to pick up changes."""
        from src.plugins.registry import get_plugin_registry

        registry = get_plugin_registry()
        plugin = registry.get_plugin(name)

        if not plugin:
            logger.error(f"Plugin not found: {name}")
            return False

        # Unload if loaded
        if name in self._loaded:
            self.unload_plugin(name)

        # Reload plugin definition from disk
        reloaded = Plugin.from_path(plugin.path)
        if not reloaded:
            logger.error(f"Failed to reload plugin definition: {name}")
            return False

        # Copy state from registry
        reloaded.enabled = plugin.enabled
        reloaded.builtin = plugin.builtin

        # Load the reloaded plugin
        return self.load_plugin(reloaded)

    def is_loaded(self, name: str) -> bool:
        """Check if a plugin is loaded."""
        return name in self._loaded

    def get_loaded_plugins(self) -> list[Plugin]:
        """Get all loaded plugins."""
        return list(self._loaded.values())


# Singleton accessor
_loader: Optional[PluginLoader] = None


def get_plugin_loader() -> PluginLoader:
    """Get the singleton plugin loader."""
    global _loader
    if _loader is None:
        _loader = PluginLoader()
    return _loader


__all__ = ["PluginLoader", "get_plugin_loader"]
