"""Compatibility layer for ai kernel dependencies.

This module provides adapters for src.* imports when running in the
augur monorepo context. For standalone operation (pip install augur-mcp),
these fall back to minimal implementations or disable features.

The pattern allows the package to work both:
1. In the monorepo (uses full src.* functionality)
2. Standalone (uses minimal implementations, some features disabled)

Usage:
    from src.mcp.augur_shared.compat import KERNEL_AVAILABLE, get_context_injector

    if KERNEL_AVAILABLE:
        injector = get_context_injector()
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.mcp.augur_shared.interfaces import SkillRecord, SkillRegistry


def _detect_ai_kernel() -> bool:
    """Check if running in augur monorepo context with ai kernel available."""
    try:
        import src  # noqa: F401

        return True
    except ImportError:
        pass

    # Also check for ai kernel module in path
    try:
        from src.config import paths  # noqa: F401

        return True
    except ImportError:
        pass

    return False


# Global flag indicating ai kernel availability
KERNEL_AVAILABLE = _detect_ai_kernel()


def _in_monorepo() -> bool:
    """Check if running in augur monorepo context (deprecated, use KERNEL_AVAILABLE)."""
    return KERNEL_AVAILABLE


# ============================================
# Skill Registry
# ============================================


def get_skill_registry() -> SkillRegistry:
    """Get the skill registry.

    In monorepo: Uses src/lib.skills.registry
    Standalone: Uses FilesystemSkillRegistry from config
    """
    from src.mcp.augur_shared.config import get_config

    return get_config().get_skill_registry()


def resolve_skill(name: str, *, plugins_dir: Path | None = None, include_disabled: bool = False) -> SkillRecord | None:
    """Resolve a skill by name or alias.

    In monorepo: Delegates to FilesystemSkillRegistry (returns SkillRecord directly)
    Standalone: Uses config skill registry
    """
    return get_skill_registry().resolve_skill(name, include_disabled=include_disabled)


def list_skills(*, plugins_dir: Path | None = None, include_disabled: bool = False) -> list[SkillRecord]:
    """List all available skills.

    In monorepo: Delegates to FilesystemSkillRegistry (returns SkillRecord directly)
    Standalone: Uses config skill registry
    """
    return get_skill_registry().list_skills(include_disabled=include_disabled)


# ============================================
# MCP Tools Configuration
# ============================================


def get_enabled_tools() -> set[str]:
    """Get set of enabled MCP tool names.

    In monorepo: Uses src/lib.config.mcp_tools
    Standalone: Returns empty set (all tools enabled)
    """
    if _in_monorepo():
        try:
            from src.config.mcp_tools import get_enabled_tools as _get

            return _get()
        except ImportError:
            pass

    return set()  # Empty = all enabled


def is_tool_enabled(tool_name: str) -> bool:
    """Check if a specific tool is enabled.

    In monorepo: Uses src/lib.config.mcp_tools
    Standalone: Returns True (all tools enabled)
    """
    if _in_monorepo():
        try:
            from src.config.mcp_tools import is_tool_enabled as _is_enabled

            return _is_enabled(tool_name)
        except ImportError:
            pass

    return True


def get_mcp_config_path() -> Path:
    """Get path to MCP tools config file.

    In monorepo: Uses src/lib.config.mcp_tools
    Standalone: Uses project_root/config/mcp_tools.yaml
    """
    if _in_monorepo():
        try:
            from src.config.mcp_tools import get_mcp_config_path as _get_path

            return _get_path()
        except ImportError:
            pass

    from src.mcp.augur_shared.config import get_config

    return get_config().project_root / "config" / "mcp_tools.yaml"


# ============================================
# Plugin System
# ============================================


def get_plugin_loader() -> Any | None:
    """Get plugin loader if available.

    In monorepo: Returns plugin loader
    Standalone: Returns None
    """
    if _in_monorepo():
        try:
            from src.plugins.loader import get_plugin_loader as _get_loader

            return _get_loader()
        except ImportError:
            pass

    return None


def get_plugin_registry() -> Any | None:
    """Get plugin registry if available.

    In monorepo: Returns plugin registry
    Standalone: Returns None
    """
    if _in_monorepo():
        try:
            from src.plugins.registry import get_plugin_registry as _get_registry

            return _get_registry()
        except ImportError:
            pass

    return None


# ============================================
# Context Injector
# ============================================


def get_context_injector() -> Any | None:
    """Get context injector if available.

    In monorepo: Returns ContextInjector
    Standalone: Returns None
    """
    if KERNEL_AVAILABLE:
        try:
            from src.mcp.augur_shared.context_injector import ContextInjector

            return ContextInjector
        except ImportError:
            pass

    return None


# ============================================
# Path Configuration
# ============================================


def get_project_root() -> Path | None:
    """Get project root path.

    In monorepo: Uses src.config.paths
    Standalone: Returns None (use env vars instead)
    """
    if KERNEL_AVAILABLE:
        try:
            from src.config.paths import get_project_root as _get_root

            return _get_root()
        except ImportError:
            pass

    return None


def get_path_config() -> Any | None:
    """Get path configuration object.

    In monorepo: Returns PathConfig
    Standalone: Returns None
    """
    if KERNEL_AVAILABLE:
        try:
            from src.config.path_config import get_path_config as _get_config

            return _get_config()
        except ImportError:
            pass

    return None


def get_path_config_functions() -> tuple[Any, Any, Any, Any] | None:
    """Get path config helper functions.

    In monorepo: Returns (get_path_config, refresh_path_config, check_size_alerts,
                         generate_recommendations)
    Standalone: Returns None
    """
    if KERNEL_AVAILABLE:
        try:
            from src.config.path_config import (
                check_size_alerts,
                generate_recommendations,
                refresh_path_config,
            )
            from src.config.path_config import (
                get_path_config as _get_config,
            )

            return (_get_config, refresh_path_config, check_size_alerts, generate_recommendations)
        except ImportError:
            pass

    return None


def calculate_directory_size(path: Path) -> int:
    """Calculate directory size in bytes.

    In monorepo: Uses src.config.path_config
    Standalone: Simple implementation
    """
    if KERNEL_AVAILABLE:
        try:
            from src.config.path_config import calculate_directory_size as _calc

            return int(_calc(path))
        except ImportError:
            pass

    # Standalone fallback
    total = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
    except (OSError, PermissionError):
        pass
    return total


# ============================================
# IDE Tools (from ai skill)
# ============================================


def _import_from_ai_skill(module_name: str) -> Any | None:
    """Import a module from the ai skill.

    Uses dynamic discovery to find the skill and import from it.
    Returns None if skill is not available or disabled.
    """
    import importlib.util

    if not KERNEL_AVAILABLE:
        return None

    # Try direct import first (skill in Python path)
    try:
        full_module = f"skills.ai.lib.{module_name}"
        return __import__(full_module, fromlist=[module_name])
    except ImportError:
        pass

    # Try to find skill directory and import dynamically
    try:
        from src.config.paths import get_project_brain_skills_dir, get_project_root

        plugins_dir = get_project_brain_skills_dir(get_project_root()) / "ai" / "lib"

        if not plugins_dir.exists():
            return None

        module_path = plugins_dir / f"{module_name}.py"
        if not module_path.exists():
            return None

        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    except (ImportError, OSError):
        pass

    return None


def get_ide_health_checker() -> tuple[Any, Any] | None:
    """Get IDE health check functions.

    In monorepo: Returns (check_all_ides, check_ide) functions from ai skill
    Standalone: Returns None (feature disabled)
    """
    module = _import_from_ai_skill("ide_health")
    if module:
        try:
            return (module.check_all_ides, module.check_ide)
        except AttributeError:
            pass
    return None


def get_ide_backlog_manager() -> dict[str, Any] | None:
    """Get IDE backlog management functions.

    In monorepo: Returns dict with backlog functions from ai skill
    Standalone: Returns None (feature disabled)
    """
    module = _import_from_ai_skill("ide_backlog")
    if module:
        try:
            return {
                "get_dir": module.get_ide_backlog_dir,
                "list": module.list_instructions,
                "save": module.save_instruction,
            }
        except AttributeError:
            pass
    return None


def get_ide_command_executor() -> Any | None:
    """Get IDE command executor.

    In monorepo: Returns execute_command function from ai skill
    Standalone: Returns None (feature disabled)
    """
    module = _import_from_ai_skill("ide_commands")
    if module:
        try:
            return module.execute_command
        except AttributeError:
            pass
    return None


def get_instruction_generator() -> Any | None:
    """Get instruction generator class.

    In monorepo: Returns InstructionGenerator from ai skill
    Standalone: Returns None (feature disabled)
    """
    module = _import_from_ai_skill("instruction_generator")
    if module:
        try:
            return module.InstructionGenerator
        except AttributeError:
            pass
    return None


def get_mcp_controller() -> Any | None:
    """Get MCP config controller.

    In monorepo: Returns controller from ai skill
    Standalone: Returns None
    """
    module = _import_from_ai_skill("mcp_config_controller")
    if module:
        try:
            return module.get_mcp_controller()
        except AttributeError:
            pass
    return None


# ============================================
# Skill Generation (Kernel-only feature)
# ============================================


def _import_from_plugin(bundle: str, skill: str, module_path: str) -> Any | None:
    """Import a module from a plugin.

    Uses dynamic discovery to find the plugin and import from it.
    Returns None if plugin is not available or disabled.

    Args:
        bundle: Plugin bundle name (e.g., 'factory', 'bossanova')
        skill: Skill name (e.g., 'mcp-app-factory', 'bossanova')
        module_path: Dot-separated path within the skill (e.g., 'scripts.skill_generation.unified_generator')
    """
    import importlib.util

    if not KERNEL_AVAILABLE:
        return None

    # Try to find plugin directory and import dynamically
    try:
        from src.config.paths import get_project_root

        skill.replace('-', '_')
        plugins_dir = get_project_root() / "plugins" / bundle / "skills" / skill

        if not plugins_dir.exists():
            return None

        # Convert module path to file path
        parts = module_path.split('.')
        module_file = (
            plugins_dir / '/'.join(parts[:-1]) / f"{parts[-1]}.py" if len(parts) > 1 else plugins_dir / f"{parts[0]}.py"
        )

        if not module_file.exists():
            # Try with subdirectory structure
            module_file = plugins_dir / '/'.join(parts)
            module_file = module_file.with_suffix('.py')
            if not module_file.exists():
                return None

        spec = importlib.util.spec_from_file_location(parts[-1], module_file)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    except (ImportError, OSError):
        pass

    return None


def get_skill_generator() -> Any | None:
    """Get skill generator function.

    In monorepo: Returns generate_skill function from mcp-app-factory
    Standalone: Returns None (feature disabled)
    """
    module = _import_from_plugin('factory', 'mcp-app-factory', 'scripts.skill_generation.unified_generator')
    if module:
        try:
            return module.generate_skill
        except AttributeError:
            pass
    return None


def get_bossanova_manager() -> Any | None:
    """Get BossanovaDataManager class.

    In monorepo: Returns BossanovaDataManager from bossanova plugin
    Standalone: Returns None (feature disabled)
    """
    module = _import_from_plugin('bossanova', 'bossanova', 'lib.bossanova_data_manager')
    if module:
        try:
            return module.BossanovaDataManager
        except AttributeError:
            pass
    return None


# ============================================
# Feature Availability Checks
# ============================================


def is_feature_available(feature: str) -> bool:
    """Check if an ai kernel-dependent feature is available.

    Args:
        feature: Feature name (ide_tools, skill_generation, context_injector, etc.)

    Returns:
        True if feature is available
    """
    if not KERNEL_AVAILABLE:
        return False

    feature_checks = {
        "ide_tools": get_ide_health_checker,
        "ide_backlog": get_ide_backlog_manager,
        "ide_commands": get_ide_command_executor,
        "instruction_generator": get_instruction_generator,
        "skill_generation": get_skill_generator,
        "context_injector": get_context_injector,
        "bossanova": get_bossanova_manager,
        "plugin_loader": get_plugin_loader,
        "plugin_registry": get_plugin_registry,
    }

    checker = feature_checks.get(feature)
    if checker:
        return checker() is not None

    return False


def get_available_features() -> list[str]:
    """Get list of available ai kernel-dependent features.

    Returns:
        List of feature names that are currently available
    """
    all_features = [
        "ide_tools",
        "ide_backlog",
        "ide_commands",
        "instruction_generator",
        "skill_generation",
        "context_injector",
        "bossanova",
        "plugin_loader",
        "plugin_registry",
    ]

    return [f for f in all_features if is_feature_available(f)]
