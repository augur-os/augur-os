"""IDE Health Engine - Orchestrates health checks across all IDE adapters."""

from __future__ import annotations

from typing import Any

from .ide_integrations import (
    load_integrations_config,
    update_ide_health,
)
from skills.ai.augur.adapters.registry import get_registry
from .ide_pillars import get_pillar_status


def check_all_ides() -> dict[str, Any]:
    """
    Run health checks for all registered IDE adapters.

    Returns:
        dict with IDE names as keys, each containing health check results
    """
    registry = get_registry()
    results = {}

    for adapter in registry.get_all():
        try:
            health = adapter.health_check()
            results[adapter.ide_name] = health

            # Update config store
            update_ide_health(adapter.ide_name, health)
        except Exception as e:
            results[adapter.ide_name] = {
                "healthy": False,
                "status": "error",
                "checks": {},
                "last_check": None,
                "error": str(e),
            }

    return results


def check_ide(ide_name: str) -> dict[str, Any]:
    """
    Run health check for a specific IDE.

    Args:
        ide_name: Name of the IDE to check

    Returns:
        Health check result dict
    """
    registry = get_registry()
    adapter = registry.get(ide_name)

    if not adapter:
        return {
            "healthy": False,
            "status": "not_found",
            "checks": {},
            "last_check": None,
            "error": f"Adapter for '{ide_name}' not found",
        }

    try:
        health = adapter.health_check()
        update_ide_health(ide_name, health)
        return health
    except Exception as e:
        return {"healthy": False, "status": "error", "checks": {}, "last_check": None, "error": str(e)}


def get_all_ide_status() -> dict[str, Any]:
    """
    Get status for all IDEs (from config store, doesn't run new checks).

    Returns:
        dict with IDE names as keys, containing config + last health + pillars
    """
    registry = get_registry()
    integrations = load_integrations_config()
    results = {}

    for adapter in registry.get_all():
        ide_name = adapter.ide_name
        ide_config = integrations.get(ide_name, {})

        # Get detection info
        detection = adapter.detect()

        # Get pillar status
        pillars = get_pillar_status(ide_name)

        results[ide_name] = {
            "ide_name": ide_name,
            "enabled": ide_config.get("enabled", False),
            "installed": detection.get("installed", False),
            "running": detection.get("running", False),
            "path": detection.get("path"),
            "last_health": ide_config.get("last_health"),
            "last_error": ide_config.get("last_error"),
            "config_paths": ide_config.get("config_paths", []),
            "execution_mode": adapter.get_execution_mode(),
            "supported_fallbacks": adapter.get_supported_fallbacks(),
            "pillars": pillars,
        }

    return results
