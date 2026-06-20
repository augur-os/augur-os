"""Filesystem-based skill registry.

Delegates discovery to the canonical `skill_discovery` module and returns
`SkillRecord` objects directly — no conversion layer.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from src.mcp.augur_shared.interfaces import SkillRecord, SkillRegistry
from src.plugins.skill_discovery import discover_all_skills, normalize_skill_id
from src.plugins.skill_ui_state import read_disabled_skills

# Core skills that should never be disabled
CORE_SKILLS = {"augur-mcp", "setup-manager"}


class FilesystemSkillRegistry(SkillRegistry):
    """Default registry that scans filesystem for skills.

    This implementation:
    - Scans managed skill source directories
    - Parses SKILL.md files for metadata
    - Respects disabled skills from runtime local state
    - Caches results for performance

    Example:
        registry = FilesystemSkillRegistry(
            plugins_dir=Path("/path/to/project"),
            config_file=Path("/path/to/config.yaml"),
        )
        skills = registry.list_skills()
    """

    def __init__(
        self,
        plugins_dir: Path,
        config_file: Path | None = None,
        bundles: tuple[str, ...] = (),
    ):
        """Initialize the registry.

        Args:
            plugins_dir: Project root directory (used to locate client skill dirs).
            config_file: Unused legacy compatibility parameter.
            bundles: Unused, kept for API compatibility.
        """
        self._plugins_dir = plugins_dir
        self._config_file = config_file
        self._bundles = bundles
        self._cache: list[SkillRecord] | None = None
        self._index: dict[str, SkillRecord] | None = None

    def get_plugins_dir(self) -> Path:
        """Get the plugins directory path."""
        return self._plugins_dir

    def list_skills(self, *, include_disabled: bool = False) -> list[SkillRecord]:
        """List all available skills.

        Results are cached for performance. Use invalidate_cache() to refresh.

        Args:
            include_disabled: If True, include disabled skills.

        Returns:
            List of SkillRecord sorted by name.
        """
        if self._cache is None:
            self._cache = self._scan_skills()

        if include_disabled:
            return self._cache

        return [s for s in self._cache if not s.disabled or s.name in CORE_SKILLS]

    def resolve_skill(self, name: str, *, include_disabled: bool = False) -> SkillRecord | None:
        """Resolve a skill by canonical name.

        Args:
            name: Skill name or canonical ID.
            include_disabled: If True, include disabled skills.

        Returns:
            SkillRecord if found, None otherwise.
        """
        if not name or not name.strip():
            return None

        if self._index is None:
            self._build_index()

        normalized = normalize_skill_id(name)
        skill = self._index.get(normalized) if self._index else None

        if skill is None:
            return None

        if skill.disabled and not include_disabled and skill.name not in CORE_SKILLS:
            return None

        return skill

    def invalidate_cache(self) -> None:
        """Clear cached skill data to force re-scan on next access."""
        self._cache = None
        self._index = None

    def _scan_skills(self) -> list[SkillRecord]:
        """Scan filesystem for skills via canonical discovery."""
        disabled_ids = self._load_disabled_skills()
        # Canonical discovery owns managed-root selection, parsing, and
        # deduplication.
        records = discover_all_skills(project_root=self._project_root())
        results: list[SkillRecord] = []
        for rec in records:
            # Apply local disabled config on top of canonical result
            if disabled_ids and normalize_skill_id(rec.name) in disabled_ids:
                rec = replace(rec, disabled=True)
            results.append(rec)
        return sorted(results, key=lambda s: s.name)

    def _project_root(self) -> Path:
        """Resolve the project root implied by this registry's configured path."""
        configured = self._plugins_dir.resolve()
        if (configured / "pyproject.toml").is_file() and (
            (configured / "src" / "config" / "paths.py").is_file() or (configured / "config" / "system").is_dir()
        ):
            return configured
        if (
            configured.name == "skills"
            and configured.parent.name == "capabilities"
            and configured.parent.parent.name == "project-brain"
        ):
            return configured.parent.parent.parent
        # ADR-770 compatibility: legacy registry paths may still point at the
        # retired shared-vault skill root; resolve them back to the host repo.
        if configured.name == "skills" and configured.parent.name == "shared-vault":
            return configured.parent.parent
        return configured

    def _build_index(self) -> None:
        """Build lookup index from cached skills."""
        skills = self.list_skills(include_disabled=True)
        self._index = {}

        # First pass: add by canonical name
        for skill in skills:
            self._index.setdefault(skill.name, skill)

        # Canonical names only (no alias indexing).

    def _load_disabled_skills(self) -> set[str]:
        """Load set of disabled skill IDs from runtime local state."""
        return {normalize_skill_id(entry) for entry in read_disabled_skills()}

    # Parsing helpers (_extract_frontmatter, _extract_triggers, etc.)
    # removed — discovery is now delegated to skill_discovery.discover_all_skills().
