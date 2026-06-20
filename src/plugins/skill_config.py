"""Legacy .config reader for enable/disable compatibility only.

New dashboard novelty state now lives in runtime-backed ``skill_ui_state``.
This module remains only for the still-supported ``enabled`` flag and
legacy settings blobs while the repo finishes retiring ``.config`` files.
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_project_brain_skills_dir, get_project_root
from src.plugins.skill_ui_state import (
    is_skill_enabled as is_skill_enabled_runtime,
    migrate_legacy_skill_config,
    set_skill_enabled as set_skill_enabled_runtime,
)

# Cache TTL in seconds
_CACHE_TTL = 5.0
_config_cache: dict[str, tuple[float, "SkillConfig"]] = {}


@dataclass
class SkillConfig:
    """Parsed .config file contents."""

    enabled: bool = True
    settings: dict[str, Any] = field(default_factory=dict)
    resolved_deps: dict[str, bool] = field(default_factory=dict)


def _default_config() -> SkillConfig:
    """Return default config (enabled, stable)."""
    return SkillConfig()


def read_config_file(dir_path: Path) -> SkillConfig:
    """
    Read a .config file from the given directory.
    Returns default config (enabled: True) if no .config file exists.
    """
    cache_key = str(dir_path)
    now = time.monotonic()

    if cache_key in _config_cache:
        cached_time, cached_config = _config_cache[cache_key]
        if now - cached_time < _CACHE_TTL:
            return cached_config

    root = get_project_root()
    config_path = dir_path / ".config"
    project_skills_root = get_project_brain_skills_dir(root)
    canonical_skill_dir = (
        dir_path.parent == project_skills_root and dir_path.is_dir() and not dir_path.name.startswith(".")
    )

    if canonical_skill_dir:
        if config_path.exists():
            migrate_legacy_skill_config(dir_path, delete_file=True)
        legacy_raw: dict[str, Any] = {}
        if config_path.exists():
            try:
                loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
                legacy_raw = loaded if isinstance(loaded, dict) else {}
            except Exception:
                legacy_raw = {}
        result = SkillConfig(
            enabled=is_skill_enabled_runtime(dir_path.name),
            settings=legacy_raw.get("settings", {}),
            resolved_deps=legacy_raw.get("resolved_deps", {}),
        )
        _config_cache[cache_key] = (now, result)
        return result

    if not config_path.exists():
        result = _default_config()
        _config_cache[cache_key] = (now, result)
        return result

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

        result = SkillConfig(
            enabled=raw.get("enabled", True) is not False,
            settings=raw.get("settings", {}),
            resolved_deps=raw.get("resolved_deps", {}),
        )
        _config_cache[cache_key] = (now, result)
        return result
    except Exception:
        result = _default_config()
        _config_cache[cache_key] = (now, result)
        return result


def read_skill_config(hub: str, skill: str) -> SkillConfig:
    """Read a skill's .config file."""
    root = get_project_root()
    return read_config_file(get_project_brain_skills_dir(root) / skill)


def read_hub_config(hub: str) -> SkillConfig:
    """Read a hub-level .config file."""
    root = get_project_root()
    return read_config_file(get_project_brain_skills_dir(root))


def is_skill_enabled(hub: str, skill: str) -> bool:
    """
    Check if a skill is enabled.
    A skill is disabled if its own .config or its hub's .config has enabled: false.
    """
    hub_config = read_hub_config(hub)
    if not hub_config.enabled:
        return False
    skill_config = read_skill_config(hub, skill)
    return skill_config.enabled


def is_plugin_enabled_by_config(dir_path: Path) -> bool:
    """
    Check if a directory is enabled via its .config file.
    Drop-in replacement for checking plugin_state.json or .disabled markers.
    """
    config = read_config_file(dir_path)
    return config.enabled


def write_config_file(dir_path: Path, **kwargs: Any) -> None:
    """
    Write or update a .config file.

    Merges with existing config if present.
    Only writes keys that are provided.
    """
    root = get_project_root()
    project_skills_root = get_project_brain_skills_dir(root)
    canonical_skill_dir = (
        dir_path.parent == project_skills_root and dir_path.is_dir() and not dir_path.name.startswith(".")
    )
    if canonical_skill_dir and "enabled" in kwargs:
        set_skill_enabled_runtime(dir_path.name, kwargs["enabled"] is not False)
        cache_key = str(dir_path)
        _config_cache.pop(cache_key, None)
        return

    config_path = dir_path / ".config"

    # Read existing
    existing = read_config_file(dir_path)
    data: dict[str, Any] = {}

    data["enabled"] = kwargs.get("enabled", existing.enabled)
    settings = {**existing.settings, **kwargs.get("settings", {})}
    if settings:
        data["settings"] = settings

    resolved = {**existing.resolved_deps, **kwargs.get("resolved_deps", {})}
    if resolved:
        data["resolved_deps"] = resolved

    config_path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")

    # Invalidate cache
    cache_key = str(dir_path)
    _config_cache.pop(cache_key, None)


def clear_config_cache() -> None:
    """Clear the config cache."""
    _config_cache.clear()
