"""
Plugin system for Augur.

Provides plugin discovery, registration, and management functionality.
See ADR-008 for design details.
"""

from src.plugins.schema import Plugin, PluginHooks
from src.plugins.registry import PluginRegistry, get_plugin_registry
from src.plugins.loader import PluginLoader, get_plugin_loader

__all__ = [
    "Plugin",
    "PluginHooks",
    "PluginRegistry",
    "PluginLoader",
    "get_plugin_registry",
    "get_plugin_loader",
]
