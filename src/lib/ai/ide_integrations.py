"""IDE Integrations Configuration - Read/write ide_integrations.yaml.

This module manages the IDE integrations configuration file which tracks
per-IDE integration status, config paths, and health information.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

from src.config.paths import get_config_dir as _get_config_dir


def get_config_dir() -> Path:
    """Get the config directory."""
    return _get_config_dir()


def get_integrations_config_path() -> Path:
    """Get the path to ide_integrations.yaml."""
    return get_config_dir() / "ide_integrations.yaml"


def load_integrations_config() -> dict[str, Any]:
    """
    Load IDE integrations configuration.

    Returns:
        dict with IDE names as keys, each containing:
        - enabled (bool)
        - config_paths (list[str])
        - last_applied (str|None): ISO timestamp
        - desired_capabilities (list[str])
        - last_health (dict|None): Health check result
        - last_error (str|None)
    """
    config_path = get_integrations_config_path()

    if not config_path.exists():
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        return config.get("integrations", {})
    except Exception:
        return {}


def save_integrations_config(integrations: dict[str, Any]) -> None:
    """
    Save IDE integrations configuration.

    Args:
        integrations: dict with IDE names as keys
    """
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    config_path = get_integrations_config_path()

    # Load existing config to preserve other keys
    existing_config: dict[str, Any] = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                existing_config = yaml.safe_load(f) or {}
        except Exception:
            pass

    # Update integrations
    existing_config["integrations"] = integrations

    # Write back
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(existing_config, f, default_flow_style=False, sort_keys=False)


def get_ide_config(ide_name: str) -> dict[str, Any]:
    """
    Get configuration for a specific IDE.

    Args:
        ide_name: Name of the IDE (e.g., "cursor", "vscode_copilot")

    Returns:
        IDE configuration dict, or empty dict if not found
    """
    integrations = load_integrations_config()
    return integrations.get(ide_name, {})


def update_ide_config(
    ide_name: str,
    enabled: Optional[bool] = None,
    config_paths: Optional[list[str]] = None,
    desired_capabilities: Optional[list[str]] = None,
    last_health: Optional[dict[str, Any]] = None,
    last_error: Optional[str] = None,
) -> None:
    """
    Update configuration for a specific IDE.

    Args:
        ide_name: Name of the IDE
        enabled: Whether this IDE is enabled
        config_paths: List of config file paths
        desired_capabilities: List of desired capabilities
        last_health: Last health check result
        last_error: Last error message
    """
    integrations = load_integrations_config()

    if ide_name not in integrations:
        integrations[ide_name] = {
            "enabled": False,
            "config_paths": [],
            "last_applied": None,
            "desired_capabilities": [],
            "last_health": None,
            "last_error": None,
        }

    ide_config = integrations[ide_name]

    if enabled is not None:
        ide_config["enabled"] = enabled

    if config_paths is not None:
        ide_config["config_paths"] = config_paths
        ide_config["last_applied"] = datetime.now().isoformat()

    if desired_capabilities is not None:
        ide_config["desired_capabilities"] = desired_capabilities

    if last_health is not None:
        ide_config["last_health"] = last_health

    if last_error is not None:
        ide_config["last_error"] = last_error

    save_integrations_config(integrations)


def update_ide_health(ide_name: str, health_result: dict[str, Any]) -> None:
    """
    Update health check result for an IDE.

    Args:
        ide_name: Name of the IDE
        health_result: Health check result from adapter.health_check()
    """
    update_ide_config(ide_name, last_health=health_result)


def get_enabled_ides() -> list[str]:
    """Get list of enabled IDE names."""
    integrations = load_integrations_config()
    return [name for name, config in integrations.items() if config.get("enabled", False)]


def enable_ide(ide_name: str) -> None:
    """Enable an IDE integration."""
    update_ide_config(ide_name, enabled=True)


def disable_ide(ide_name: str) -> None:
    """Disable an IDE integration."""
    update_ide_config(ide_name, enabled=False)
