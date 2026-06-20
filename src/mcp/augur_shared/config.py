"""
Configuration management for augur-mcp.

All paths are configurable via environment variables with sensible defaults.
This allows the MCP server to run standalone without the full monorepo.

Path resolution delegates to src.config.path_primitives (ADR-466) for
platform-aware directory defaults. The project name comes from the kernel's
get_project_name() when available, otherwise defaults to "Augur".
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from src.config.path_primitives import (
    application_support_dir,
    cache_home_dir,
    documents_home_dir,
    is_macos,
    logs_home_dir,
    state_home_dir,
    vault_home_dir,
)
from src.config.path_primitives import (
    env_path as _env_path,
)
from src.config.path_primitives import (
    expand_path as _expand,
)

if TYPE_CHECKING:
    from src.mcp.augur_shared.interfaces import SkillRegistry


def _get_project_name() -> str:
    """Get project name from kernel when available, else default to 'Augur'."""
    try:
        from src.config.paths import get_project_name

        return get_project_name()
    except ImportError:
        return "Augur"


def _get_application_support_dir() -> Path:
    return _env_path("AUGUR_APP_SUPPORT") or application_support_dir(_get_project_name())


def _get_state_dir() -> Path:
    return _env_path("AUGUR_STATE") or (
        _get_application_support_dir() / "state" if is_macos() else state_home_dir(_get_project_name())
    )


def _get_logs_dir() -> Path:
    return _env_path("AUGUR_LOGS") or logs_home_dir(_get_project_name())


def _get_cache_dir() -> Path:
    return _env_path("AUGUR_CACHE_DIR", "AUGUR_CACHE_PATH") or cache_home_dir(_get_project_name())


def _get_vault_dir() -> Path:
    try:
        from src.config.paths import get_vault_dir

        return get_vault_dir()
    except ImportError:
        return _env_path("AUGUR_VAULT") or vault_home_dir(_get_project_name())


def _get_documents_dir() -> Path:
    try:
        from src.config.paths import get_documents_dir

        return get_documents_dir()
    except ImportError:
        return _env_path("AUGUR_DOCUMENTS") or documents_home_dir(_get_project_name())


def _get_rag_dir() -> Path:
    return _env_path("AUGUR_RAG") or (_get_application_support_dir() / "rag")


def _get_memory_dir() -> Path:
    return _env_path("AUGUR_MEMORY") or (_get_vault_dir() / "memory")


def _is_project_root(candidate: Path) -> bool:
    return (candidate / "pyproject.toml").is_file() and (
        (candidate / "src" / "config" / "paths.py").is_file() or (candidate / "config" / "system").is_dir()
    )


def _get_project_root() -> Path:
    """Get project root from this module checkout, env, or fallback.

    File-location detection wins over AUGUR_ROOT/AUGUR_CORE so a stale global
    env var cannot point a worktree-imported MCP server back at main.

    Raises:
        FileNotFoundError: If project root cannot be found
    """
    for candidate in Path(__file__).resolve().parents:
        if _is_project_root(candidate):
            return candidate

    env_path = os.environ.get("AUGUR_ROOT") or os.environ.get("AUGUR_CORE")
    if env_path:
        path = _expand(env_path)
        if not path.exists():
            raise FileNotFoundError(f"Project root path does not exist: {path}")
        return path

    # File-location detection: 4 levels up from this file
    # config.py -> augur_mcp -> mcp -> src -> PROJECT_ROOT
    project_root = Path(__file__).parent.parent.parent.parent
    if _is_project_root(project_root) or any(
        (project_root / landmark).exists() for landmark in ("plugins", "config", "CLAUDE.md", "src")
    ):
        return project_root

    raise FileNotFoundError(
        f"Project root not found at {project_root}. " f"Set AUGUR_ROOT or AUGUR_CORE environment variable."
    )


def _get_default_plugins_dir() -> Path:
    """Get the canonical skills directory.

    The field name is retained for compatibility with the registry interface,
    but the runtime source of truth is ``project-brain/capabilities/skills``.
    """
    try:
        from src.config.paths import get_project_brain_skills_dir

        return get_project_brain_skills_dir(_get_project_root())
    except ImportError:
        return _get_project_root() / "project-brain" / "capabilities" / "skills"


@dataclass
class MCPConfig:
    """Configuration for MCP server.

    All settings can be overridden via environment variables:
    - AUGUR_ROOT: Project root (for monorepo development)
    - AUGUR_CORE: Project root (legacy alias)
    - AUGUR_LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)
    - AUGUR_METRICS: Enable/disable metrics (true/false)
    - AUGUR_CACHE: Enable/disable caching (true/false)
    - AUGUR_CACHE_TTL: Cache TTL in seconds
    """

    # Paths
    project_root: Path = field(default_factory=_get_project_root)
    plugins_dir: Path = field(default_factory=_get_default_plugins_dir)

    # Features
    enable_metrics: bool = True
    enable_caching: bool = True
    cache_ttl: int = 300  # 5 minutes

    # Logging
    log_level: str = "INFO"
    log_dir: Path | None = None

    # Plugin discovery (can be overridden)
    _skill_registry: SkillRegistry | None = field(default=None, repr=False)

    def __post_init__(self):
        """Ensure paths are Path objects and resolve them."""
        if isinstance(self.project_root, str):
            self.project_root = _expand(self.project_root)
        if isinstance(self.plugins_dir, str):
            self.plugins_dir = _expand(self.plugins_dir)
        if isinstance(self.log_dir, str):
            self.log_dir = _expand(self.log_dir)

    @classmethod
    def from_env(cls) -> MCPConfig:
        """Load configuration from environment variables."""
        return cls(
            project_root=_get_project_root(),
            plugins_dir=_get_default_plugins_dir(),
            log_level=os.environ.get("AUGUR_LOG_LEVEL", "INFO").upper(),
            enable_metrics=os.environ.get("AUGUR_METRICS", "true").lower() == "true",
            enable_caching=os.environ.get("AUGUR_CACHE", "true").lower() == "true",
            cache_ttl=int(os.environ.get("AUGUR_CACHE_TTL", "300")),
        )

    @property
    def mcp_data_dir(self) -> Path:
        """Get MCP-specific metrics directory."""
        return _get_state_dir() / "metrics" / "mcp"

    @property
    def backup_dir(self) -> Path:
        """Get backup directory."""
        return self.mcp_data_dir / "backups"

    @property
    def metrics_file(self) -> Path:
        """Get metrics file path."""
        return self.mcp_data_dir / "mcp-metrics.json"

    @property
    def config_file(self) -> Path:
        """Get main config file path."""
        return self.project_root / "config" / "system" / "config.yaml"

    def get_skill_registry(self) -> SkillRegistry:
        """Get or create the skill registry.

        Returns the configured registry, or creates a default filesystem registry.
        """
        if self._skill_registry is not None:
            return self._skill_registry

        # Create default filesystem registry
        from src.mcp.augur_shared.adapters.filesystem_registry import FilesystemSkillRegistry

        self._skill_registry = FilesystemSkillRegistry(
            plugins_dir=self.plugins_dir,
            config_file=self.config_file,
        )
        return self._skill_registry

    def set_skill_registry(self, registry: SkillRegistry) -> None:
        """Set a custom skill registry."""
        self._skill_registry = registry


# Global config instance (lazily initialized)
_config: MCPConfig | None = None


def get_config() -> MCPConfig:
    """Get the global configuration instance.

    Creates from environment on first call.
    """
    global _config
    if _config is None:
        _config = MCPConfig.from_env()
    return _config


def set_config(config: MCPConfig) -> None:
    """Set the global configuration instance.

    Useful for testing or programmatic configuration.
    """
    global _config
    _config = config


def reset_config() -> None:
    """Reset global config (mainly for testing)."""
    global _config
    _config = None


# ============================================
# Convenience functions matching src/lib.config.paths API
# ============================================


def get_project_root() -> Path:
    """Get the project root directory.

    Returns get_config().project_root, matching src/lib.config.paths API.
    """
    return get_config().project_root


def find_project_root() -> Path:
    """Find the project root without requiring a repo-root skills directory."""
    return _get_project_root()


def get_skill_data_dir(skill: str) -> Path:
    """Get the vault directory for a specific skill."""
    try:
        from src.config.paths import get_skill_vault_relative_dir
        from src.lib.brain_layout import join_brain_relative

        return join_brain_relative(_get_vault_dir(), get_skill_vault_relative_dir(skill))
    except ImportError:
        return _get_vault_dir() / skill


def get_config_dir() -> Path:
    """Get the config directory for YAML configs.

    This contains system configs organized by category:
    - system/ (config.yaml, paths.yaml, llm.yaml)
    - dashboard/ (action_buttons.yaml, app_mode.yaml, mcp_tools.yaml)
    - agents/ (hooks.yaml, ide_integrations.yaml, ide_mcp_configs.yaml,
      model_mapping.yaml, cli_headless_profiles.yaml, agent_weights.yaml)
    - integrations/ (remote_providers.yaml, mcp_config.json)

    Returns:
        Path to config/ directory (project_root/config/)
    """
    return get_config().project_root / "config"


def get_runtime_dir() -> Path:
    """Get the persistent runtime state directory."""
    return _get_state_dir()


def get_preferences_path() -> Path:
    """Get the runtime-backed mutable preferences file."""
    try:
        from src.config.preferences import get_preferences_path as _kernel_get_preferences_path

        return _kernel_get_preferences_path()
    except ImportError:
        return get_runtime_dir() / "preferences.yaml"


def get_memory_dir() -> Path:
    """Get the vault-backed memory directory."""
    return _get_memory_dir()


def get_vault_dir() -> Path:
    return _get_vault_dir()


def get_documents_dir() -> Path:
    return _get_documents_dir()


def get_wiki_dir() -> Path:
    try:
        from src.config.paths import get_wiki_dir as _kernel_get_wiki_dir

        return _kernel_get_wiki_dir()
    except ImportError:
        return _get_vault_dir() / "wiki"


def get_runtime_wiki_dir() -> Path:
    try:
        from src.config.paths import get_runtime_wiki_dir as _kernel_get_runtime_wiki_dir

        return _kernel_get_runtime_wiki_dir()
    except ImportError:
        return _get_state_dir() / "wiki"


def get_ide_integration_dir() -> Path:
    try:
        from src.config.paths import get_ide_integration_dir as _kernel_get_ide_integration_dir

        return _kernel_get_ide_integration_dir()
    except ImportError:
        return _get_state_dir() / "ide-integration"


def get_ide_registry_path() -> Path:
    try:
        from src.config.paths import get_ide_registry_path as _kernel_get_ide_registry_path

        return _kernel_get_ide_registry_path()
    except ImportError:
        return get_ide_integration_dir() / "registry.yaml"


def get_compiled_wiki_dir(wiki_dir: Path | None = None) -> Path:
    try:
        from src.config.paths import get_compiled_wiki_dir as _kernel_get_compiled_wiki_dir

        return _kernel_get_compiled_wiki_dir(wiki_dir)
    except ImportError:
        return wiki_dir or get_wiki_dir()


def get_skill_documents_dir(skill: str) -> Path:
    """Get the documents directory for a specific skill."""
    return _get_documents_dir() / skill


def get_logs_dir() -> Path:
    return _get_logs_dir()


def get_cache_dir() -> Path:
    return _get_cache_dir()


def get_state_dir() -> Path:
    return _get_state_dir()


def get_rag_dir() -> Path:
    return _get_rag_dir()


def get_skill_rag_dir(skill: str) -> Path:
    """Get the RAG directory for a specific skill."""
    return _get_rag_dir() / skill


def get_project_index_path() -> Path:
    return _get_rag_dir() / "project-index.yaml"
