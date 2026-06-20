"""
Preference tools implementation.

Tools for reading and writing user preferences to preferences.yaml.
"""

from pathlib import Path
from typing import Any

from .models import GetPreferencesInput, UpdatePreferenceInput


def _get_preferences_path() -> Path:
    """Get the path to preferences.yaml."""
    from src.mcp.augur_shared.config import get_preferences_path

    return get_preferences_path()


def _load_preferences() -> dict[str, Any]:
    """Load preferences from yaml file."""
    from src.config.preferences import get_preferences_path, load_preferences

    path = _get_preferences_path()
    prefs = load_preferences() if path == get_preferences_path() else load_preferences(path=path, migrate_legacy=False)

    # Ensure dispatch_targets always has a sensible default
    if "dispatch_targets" not in prefs:
        prefs["dispatch_targets"] = {
            "enabled_groups": None,  # None = all enabled (first-run)
            "variant_overrides": {},
        }

    return prefs


def _save_preferences(prefs: dict[str, Any]) -> None:
    """Save preferences to yaml file."""
    from src.config.preferences import save_preferences

    path = _get_preferences_path()
    save_preferences(prefs, path=path)


def _get_preference_value(prefs: dict[str, Any], key: str) -> Any:
    """Read a preference key, supporting dotted paths for nested settings."""
    if key in prefs:
        return prefs[key]

    current: Any = prefs
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_preference_value(prefs: dict[str, Any], key: str, value: Any) -> None:
    """Set a preference key, supporting dotted paths for nested settings."""
    parts = [part for part in key.split(".") if part]
    if len(parts) <= 1:
        prefs[key] = value
        return

    current = prefs
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value
    prefs.pop(key, None)


async def get_preferences_impl(params: GetPreferencesInput) -> str:
    """Get user preferences.

    Args:
        params: GetPreferencesInput

    Returns:
        JSON string of preferences
    """
    import json

    prefs = _load_preferences()

    if params.key:
        value = _get_preference_value(prefs, params.key)
        result = {params.key: value} if value is not None else {}
    else:
        result = prefs

    return json.dumps(result, indent=2)


async def update_preference_impl(params: UpdatePreferenceInput) -> str:
    """Update a user preference.

    Args:
        params: UpdatePreferenceInput

    Returns:
        Success message or error
    """
    import json

    prefs = _load_preferences()
    _set_preference_value(prefs, params.key, params.value)

    try:
        _save_preferences(prefs)
        return json.dumps({"success": True, "key": params.key, "value": params.value})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


__all__ = ["get_preferences_impl", "update_preference_impl"]
