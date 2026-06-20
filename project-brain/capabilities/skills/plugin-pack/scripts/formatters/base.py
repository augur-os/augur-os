"""Base formatter interface for plugin assembly targets."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BaseFormatter(ABC):
    """Abstract base for platform-specific plugin formatters."""

    def plugin_dir(self, output_dir: Path) -> Path:
        """Return the plugin root directory for this formatter's assembled output."""
        return output_dir / "plugins" / "augur"

    @abstractmethod
    def write_manifest(self, plugin_dir: Path, version: str) -> None:
        """Write the plugin manifest file (e.g., plugin.json)."""

    @abstractmethod
    def write_mcp_config(self, plugin_dir: Path, project_root: Path, python_path: str) -> None:
        """Write MCP server configuration."""

    @abstractmethod
    def write_marketplace(self, output_dir: Path, version: str) -> None:
        """Write marketplace discovery manifest."""

    @abstractmethod
    def write_skills(self, plugin_dir: Path, skills: dict[str, str]) -> None:
        """Write transformed SKILL.md files. skills is {name: transformed_content}."""

    @abstractmethod
    def write_commands(self, plugin_dir: Path, commands: dict[str, dict]) -> None:
        """Write command files. commands is {name: {description, body}}."""

    @abstractmethod
    def install(self, output_dir: Path, version: str) -> bool:
        """Install the assembled plugin to the target platform. Returns True on success."""
