"""
Plugin Context Resolution

Resolves dependencies between plugins and handles context injection.
Each plugin can:
- Declare dependencies on other plugins (in SKILL.md)
- Require context from dependencies (context_requires)
- Provide context to other plugins (context_provides + context.py)

Usage:
    from src.plugins.context import resolve_context, get_provided_context

    # Get all context for a skill (resolves dependencies)
    ctx = resolve_context("career")
    # ctx = {"notifications": {"send_alert": <fn>, ...}, "knowledge": {...}}

    # Get what a specific plugin provides
    provided = get_provided_context("notifications")
    # provided = {"send_alert": <fn>, "raise_review": <fn>}
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from src.logging import get_entity_logger
from src.plugins.skill_discovery import (
    resolve_skill,
    list_skills,
)

logger = get_entity_logger("plugins.context")


@dataclass
class PluginContext:
    """Context provided by a single plugin."""

    plugin_name: str
    provided: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class ResolvedContext:
    """Combined context from all dependencies."""

    skill_name: str
    contexts: dict[str, PluginContext] = field(default_factory=dict)
    missing_deps: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def get(self, plugin_name: str, key: str, default: Any = None) -> Any:
        """Get a specific context value from a plugin."""
        ctx = self.contexts.get(plugin_name)
        if ctx is None:
            return default
        return ctx.provided.get(key, default)

    def get_plugin(self, plugin_name: str) -> Optional[PluginContext]:
        """Get full context from a plugin."""
        return self.contexts.get(plugin_name)

    def all_provided(self) -> dict[str, dict[str, Any]]:
        """Get all provided context as a nested dict."""
        return {name: ctx.provided for name, ctx in self.contexts.items()}


def _load_context_module(skill_path: Path) -> Optional[Any]:
    """Load the context.py module from a skill directory."""
    context_file = skill_path / "context.py"
    if not context_file.exists():
        return None

    try:
        spec = importlib.util.spec_from_file_location(
            f"plugin_context_{skill_path.name}",
            context_file,
        )
        if spec is None or spec.loader is None:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        # Log but don't fail
        logger.warning("Failed to load context.py from %s: %s", skill_path, e)
        return None


def get_provided_context(skill_name: str) -> PluginContext:
    """
    Get the context provided by a specific plugin.

    The plugin must have a context.py file with a get_provided_context() function.

    Args:
        skill_name: Name of the skill/plugin

    Returns:
        PluginContext with the provided data
    """
    skill = resolve_skill(skill_name)
    if skill is None:
        return PluginContext(
            plugin_name=skill_name,
            error=f"Skill not found: {skill_name}",
        )

    if not skill.has_context:
        return PluginContext(
            plugin_name=skill_name,
            error=f"Skill has no context.py: {skill_name}",
        )

    module = _load_context_module(skill.path)
    if module is None:
        return PluginContext(
            plugin_name=skill_name,
            error=f"Failed to load context.py: {skill_name}",
        )

    # Call the get_provided_context function
    get_ctx_fn = getattr(module, "get_provided_context", None)
    if not callable(get_ctx_fn):
        return PluginContext(
            plugin_name=skill_name,
            error=f"context.py missing get_provided_context(): {skill_name}",
        )

    try:
        provided = get_ctx_fn()
        if not isinstance(provided, dict):
            provided = {}
        return PluginContext(plugin_name=skill_name, provided=provided)
    except Exception as e:
        return PluginContext(
            plugin_name=skill_name,
            error=f"get_provided_context() failed: {e}",
        )


def resolve_context(skill_name: str) -> ResolvedContext:
    """
    Resolve all dependencies for a skill and collect their context.

    Args:
        skill_name: Name of the skill needing context

    Returns:
        ResolvedContext with all dependency contexts
    """
    result = ResolvedContext(skill_name=skill_name)

    skill = resolve_skill(skill_name)
    if skill is None:
        result.errors.append(f"Skill not found: {skill_name}")
        return result

    # Get declared plugin dependencies
    dep_plugins = skill.dependencies.plugins

    # Resolve each dependency
    for dep_name in dep_plugins:
        dep_skill = resolve_skill(dep_name)
        if dep_skill is None:
            result.missing_deps.append(dep_name)
            continue

        # Get the context from this dependency
        ctx = get_provided_context(dep_name)
        if ctx.error:
            result.errors.append(f"{dep_name}: {ctx.error}")
        result.contexts[dep_name] = ctx

    return result


def validate_dependencies(skill_name: str) -> dict[str, Any]:
    """
    Validate that a skill's dependencies can be resolved.

    Useful at plugin creation time to verify the skill is properly configured.

    Args:
        skill_name: Name of the skill to validate

    Returns:
        dict with validation results
    """
    skill = resolve_skill(skill_name)
    if skill is None:
        return {
            "valid": False,
            "error": f"Skill not found: {skill_name}",
        }

    resolved: list[dict[str, Any]] = []
    missing: list[str] = []
    warnings: list[str] = []
    result: dict[str, Any] = {
        "valid": True,
        "skill": skill_name,
        "dependencies": {
            "plugins": list(skill.dependencies.plugins),
            "context_requires": [
                {"from": r.from_plugin, "data": list(r.data)} for r in skill.dependencies.context_requires
            ],
            "context_provides": list(skill.dependencies.context_provides),
        },
        "resolved": resolved,
        "missing": missing,
        "warnings": warnings,
    }

    # Check each plugin dependency exists
    for dep_name in skill.dependencies.plugins:
        dep_skill = resolve_skill(dep_name)
        if dep_skill is None:
            missing.append(dep_name)
            result["valid"] = False
        else:
            resolved.append(
                {
                    "name": dep_name,
                    "has_context": dep_skill.has_context,
                    "provides": list(dep_skill.dependencies.context_provides),
                }
            )

    # Check context_requires match what dependencies provide
    for req in skill.dependencies.context_requires:
        dep_skill = resolve_skill(req.from_plugin)
        if dep_skill is None:
            continue  # Already reported as missing

        # Check if the dependency provides what we need
        provides = set(dep_skill.dependencies.context_provides)
        for data_key in req.data:
            if data_key not in provides:
                warnings.append(f"{req.from_plugin} does not declare '{data_key}' in context_provides")

    # Check if skill declares context_provides but has no context.py
    if skill.dependencies.context_provides and not skill.has_context:
        warnings.append("Skill declares context_provides but has no context.py")

    return result


def list_context_providers() -> list[dict[str, Any]]:
    """
    List all plugins that provide context.

    Returns:
        List of plugins with their context_provides declarations
    """
    providers = []
    for skill in list_skills():
        if skill.dependencies.context_provides or skill.has_context:
            providers.append(
                {
                    "name": skill.id,
                    "bundle": skill.layer,
                    "has_context_py": skill.has_context,
                    "provides": list(skill.dependencies.context_provides),
                }
            )
    return providers


def get_dependency_graph() -> dict[str, list[str]]:
    """
    Build a dependency graph of all plugins.

    Returns:
        Dict mapping skill names to their plugin dependencies
    """
    graph = {}
    for skill in list_skills():
        if skill.dependencies:
            graph[skill.id] = list(skill.dependencies)
    return graph
