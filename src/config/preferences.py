"""Runtime-backed user preferences.

Mutable user preferences are local machine state. Defaults may live in repo
config, but writes should go to the external runtime/state directory so git
never sees airplane mode, local model, or routing changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_config_dir, get_runtime_dir


def get_preferences_path() -> Path:
    """Return the canonical mutable preferences file."""
    return get_runtime_dir() / "preferences.yaml"


def get_legacy_preferences_paths() -> list[Path]:
    """Return old repo-local preference locations used before runtime storage."""
    canonical = get_preferences_path()
    candidates = [
        get_config_dir() / "preferences.yaml",
        get_config_dir() / "system" / "preferences.yaml",
    ]

    out: list[Path] = []
    for candidate in candidates:
        if candidate == canonical or candidate in out:
            continue
        out.append(candidate)
    return out


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_preferences(
    *,
    path: Path | None = None,
    migrate_legacy: bool = True,
) -> dict[str, Any]:
    """Load preferences from runtime, optionally migrating an old repo-local file."""
    target = path or get_preferences_path()
    if target.exists():
        return _read_yaml(target)

    if path is not None or not migrate_legacy:
        return {}

    for legacy_path in get_legacy_preferences_paths():
        if not legacy_path.exists():
            continue
        prefs = _read_yaml(legacy_path)
        if prefs:
            save_preferences(prefs)
        return prefs

    return {}


def save_preferences(prefs: dict[str, Any], *, path: Path | None = None) -> None:
    """Persist preferences to the runtime path unless a test path is supplied."""
    target = path or get_preferences_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        yaml.safe_dump(prefs, f, default_flow_style=False, sort_keys=True)


__all__ = [
    "get_legacy_preferences_paths",
    "get_preferences_path",
    "load_preferences",
    "save_preferences",
]
