"""Abstract interface for skill registry.

This module defines the contract for skill discovery and resolution.
Implementations can use filesystem scanning, database queries, or any other source.

The canonical type is ``SkillRecord`` from ``src.plugins.skill_discovery``.
When the kernel is not available (standalone pip install), a minimal
dataclass with the same field names is defined locally so that type
annotations and basic attribute access still work.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Import or define SkillRecord depending on kernel availability
# ---------------------------------------------------------------------------


def _kernel_available() -> bool:
    """Detect kernel availability without importing compat (avoids circular imports)."""
    try:
        import src.config.paths  # noqa: F401

        return True
    except ImportError:
        return False


if _kernel_available():
    from src.plugins.skill_discovery import SkillRecord
else:
    # Frozen standalone mirror of the canonical SkillRecord field names so
    # non-kernel callers can still type-check and access attributes safely.
    @dataclass(frozen=True)
    class SkillRecord:  # type: ignore[no-redef]
        """Standalone SkillRecord mirror for non-kernel mode.

        Field names match the canonical ``src.plugins.skill_discovery.SkillRecord``
        so that downstream code can use a single type regardless of runtime context.
        """

        name: str
        description: str
        path: Path
        author: str = "bundled"
        hub: str = ""
        visibility: str = ""
        loop_config: dict = field(default_factory=dict)
        dependencies: dict = field(default_factory=dict)
        mcp_tools: list = field(default_factory=list)
        dashboard_pages: list = field(default_factory=list)
        commands: list = field(default_factory=list)
        config: dict = field(default_factory=dict)
        agent: dict | None = None
        skill_type: str = ""
        tags: tuple[str, ...] = ()
        tier: int = 3
        origin: str = ""
        ownership: str = "augur"
        upstream: dict = field(default_factory=dict)
        source: str = "augur"
        source_root: str = "project-brain"
        canonical: bool = True
        client_sources: tuple[str, ...] = field(default_factory=tuple)

        file_intake: dict = field(default_factory=dict)

        master: str = ""
        sync_enabled: bool = False
        display_name: str = ""
        triggers: tuple[str, ...] = ()
        capabilities: tuple[str, ...] = ()
        token_estimate: int = 0
        has_modules: bool = False
        has_scripts: bool = False
        has_references: bool = False
        has_context: bool = False
        aliases: tuple[str, ...] = ()
        layer: str | None = None
        disabled: bool = False
        alias: str | None = None
        group: str | None = None
        release: str | None = None
        plugin: str | None = None
        category: str = ""
        requires_platform: bool = False


class SkillRegistry(ABC):
    """Abstract base for skill registry implementations.

    A skill registry is responsible for:
    - Discovering available skills from some source
    - Resolving skill names/aliases to metadata
    - Tracking enabled/disabled state

    Implementations might:
    - Scan a filesystem directory (FilesystemSkillRegistry)
    - Query a database
    - Fetch from a remote API
    - Use a combination of sources

    Example:
        class MyRegistry(SkillRegistry):
            def list_skills(self, *, include_disabled: bool = False):
                return [SkillRecord(...)]

            def resolve_skill(self, name: str, *, include_disabled: bool = False):
                # Look up by name or alias
                ...

            def get_plugins_dir(self) -> Path:
                return Path("/my/skills")
    """

    @abstractmethod
    def list_skills(self, *, include_disabled: bool = False) -> list[SkillRecord]:
        """List all available skills.

        Args:
            include_disabled: If True, include disabled skills in the result.
                            Defaults to False.

        Returns:
            List of SkillRecord objects, sorted by skill name.
        """
        ...

    @abstractmethod
    def resolve_skill(self, name: str, *, include_disabled: bool = False) -> SkillRecord | None:
        """Resolve a skill by name or alias.

        Args:
            name: Skill name, ID, or alias to look up.
            include_disabled: If True, include disabled skills in resolution.

        Returns:
            SkillRecord if found, None otherwise.
        """
        ...

    @abstractmethod
    def get_plugins_dir(self) -> Path:
        """Get the canonical managed skills directory path.

        Returns:
            Path to the managed skills directory.
        """
        ...

    def list_skill_ids(self, *, include_disabled: bool = False) -> list[str]:
        """List just the skill IDs (convenience method).

        Args:
            include_disabled: If True, include disabled skills.

        Returns:
            List of skill name strings.
        """
        return [skill.name for skill in self.list_skills(include_disabled=include_disabled)]

    def resolve_skill_path(self, name: str, *, include_disabled: bool = False) -> Path | None:
        """Resolve a skill name to its filesystem path.

        Args:
            name: Skill name to resolve.
            include_disabled: If True, include disabled skills.

        Returns:
            Path to skill directory if found, None otherwise.
        """
        skill = self.resolve_skill(name, include_disabled=include_disabled)
        return skill.path if skill else None

    def is_skill_disabled(self, name: str) -> bool:
        """Check if a skill is disabled.

        Args:
            name: Skill name to check.

        Returns:
            True if the skill exists and is disabled, False otherwise.
        """
        skill = self.resolve_skill(name, include_disabled=True)
        return skill.disabled if skill else False

    def get_skill_modules(self, name: str) -> list[str]:
        """List modules available in a skill.

        Args:
            name: Skill name.

        Returns:
            List of module names (without .md extension).
        """
        skill = self.resolve_skill(name)
        if not skill or not skill.has_modules:
            return []

        modules_dir = skill.path / "modules"
        if not modules_dir.exists():
            return []

        return sorted(f.stem for f in modules_dir.iterdir() if f.is_file() and f.suffix == ".md")

    def get_skill_scripts(self, name: str) -> list[str]:
        """List scripts available in a skill.

        Args:
            name: Skill name.

        Returns:
            List of script names (without .py extension).
        """
        skill = self.resolve_skill(name)
        if not skill or not skill.has_scripts:
            return []

        scripts_dir = skill.path / "scripts"
        if not scripts_dir.exists():
            return []

        return sorted(
            f.stem for f in scripts_dir.iterdir() if f.is_file() and f.suffix == ".py" and f.stem != "__init__"
        )

    def get_skill_references(self, name: str) -> list[str]:
        """List references available in a skill.

        Args:
            name: Skill name.

        Returns:
            List of reference names (without .md extension).
        """
        skill = self.resolve_skill(name)
        if not skill or not skill.has_references:
            return []

        refs_dir = skill.path / "references"
        if not refs_dir.exists():
            return []

        return sorted(f.stem for f in refs_dir.iterdir() if f.is_file() and f.suffix == ".md")
