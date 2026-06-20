"""
Plugin schema and data models.

Defines the Plugin dataclass and related types for the plugin system.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import json


@dataclass
class PluginHooks:
    """Hook configuration for a plugin."""

    pre_tool_use: list[str] = field(default_factory=list)
    post_tool_use: list[str] = field(default_factory=list)
    session_start: list[str] = field(default_factory=list)
    session_stop: list[str] = field(default_factory=list)


@dataclass
class Plugin:
    """Plugin definition."""

    name: str
    version: str
    description: str
    author: str
    path: Path
    enabled: bool = True
    builtin: bool = True  # False for user-installed plugins
    skills: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    hooks: PluginHooks = field(default_factory=PluginHooks)
    agents: list[str] = field(default_factory=list)
    dependencies: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert plugin to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "path": str(self.path),
            "enabled": self.enabled,
            "builtin": self.builtin,
            "skills": self.skills,
            "commands": self.commands,
            "hooks": {
                "PreToolUse": self.hooks.pre_tool_use,
                "PostToolUse": self.hooks.post_tool_use,
                "SessionStart": self.hooks.session_start,
                "SessionStop": self.hooks.session_stop,
            },
            "agents": self.agents,
            "dependencies": self.dependencies,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: Path) -> "Plugin":
        """Create plugin from dictionary."""
        hooks_data = data.get("hooks", {})
        hooks = PluginHooks(
            pre_tool_use=hooks_data.get("PreToolUse", []),
            post_tool_use=hooks_data.get("PostToolUse", []),
            session_start=hooks_data.get("SessionStart", []),
            session_stop=hooks_data.get("SessionStop", []),
        )

        return cls(
            name=data.get("name", path.name),
            version=data.get("version", "0.0.0"),
            description=data.get("description", ""),
            author=data.get("author", "unknown"),
            path=path,
            enabled=data.get("enabled", True),
            builtin=data.get("builtin", True),
            skills=data.get("skills", []),
            commands=data.get("commands", []),
            hooks=hooks,
            agents=data.get("agents", []),
            dependencies=data.get("dependencies", {}),
        )

    @classmethod
    def from_path(cls, path: Path) -> Optional["Plugin"]:
        """Load plugin from directory path."""
        plugin_json = path / ".augur-plugin" / "plugin.json"

        if not plugin_json.exists():
            return None

        try:
            data = json.loads(plugin_json.read_text())
            return cls.from_dict(data, path)
        except (json.JSONDecodeError, KeyError):
            return None


__all__ = ["Plugin", "PluginHooks"]
