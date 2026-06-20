"""
Health and monitoring tool implementations.

Tools for checking system health, viewing metrics, and managing cache.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .models import CacheControlInput

if TYPE_CHECKING:
    pass


def _get_skills_dir() -> Path:
    """Get the skills directory."""
    from src.mcp.augur_shared.config import get_config

    return get_config().plugins_dir


async def get_metrics_impl(metrics) -> str:
    """Get usage statistics and system health.

    Args:
        metrics: MetricsTracker instance

    Returns:
        str: JSON with usage statistics
    """
    metrics.track_tool("metrics")
    stats = metrics.get_stats()
    return json.dumps(stats, indent=2)


async def health_check_impl(skill_cache, registry_list_skills) -> str:
    """Simple health check for monitoring.

    Args:
        skill_cache: SkillCache instance
        registry_list_skills: Function to list skills

    Returns:
        str: JSON with health status
    """
    skills_dir = _get_skills_dir()
    return json.dumps(
        {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "version": "0.3.0",
            "skills_loaded": len(registry_list_skills(plugins_dir=skills_dir)),
            "cache_entries": len(skill_cache.stats()["keys"]),
        },
        indent=2,
    )


async def cache_control_impl(params: CacheControlInput, skill_cache, metrics) -> str:
    """Manage the internal skill cache.

    Use to clear cache after manual edits or to inspect memory usage.

    Args:
        params: CacheControlInput with action and optional skill_name
        skill_cache: SkillCache instance
        metrics: MetricsTracker instance

    Returns:
        str: JSON with cache operation result
    """
    metrics.track_tool("cache_control")

    if params.action == "stats":
        return json.dumps(skill_cache.stats(), indent=2)

    elif params.action == "invalidate":
        skill_cache.invalidate()
        return json.dumps({"status": "cleared_all", "stats": skill_cache.stats()}, indent=2)

    elif params.action == "invalidate_skill":
        if not params.skill_name:
            return json.dumps({"error": "skill_name required for invalidate_skill"}, indent=2)
        skill_cache.invalidate(params.skill_name)
        return json.dumps({"status": f"cleared_{params.skill_name}", "stats": skill_cache.stats()}, indent=2)

    return json.dumps({"error": f"Unknown action: {params.action}"}, indent=2)


__all__ = [
    "get_metrics_impl",
    "health_check_impl",
    "cache_control_impl",
]
