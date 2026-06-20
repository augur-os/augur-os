"""Persisted setup-completeness preferences."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.config.paths import get_runtime_dir


@dataclass(frozen=True)
class PersistedState:
    skipped: list[str] = field(default_factory=list)
    ever_completed: bool = False


def _preferences_path() -> Path:
    return get_runtime_dir() / "preferences.yaml"


def _read_preferences(path: Path | None = None) -> dict:
    target = path or _preferences_path()
    if not target.exists():
        return {}
    data = yaml.safe_load(target.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _write_preferences(data: dict, path: Path | None = None) -> None:
    target = path or _preferences_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def load_persisted_state(path: Path | None = None) -> PersistedState:
    data = _read_preferences(path)
    setup = data.get("setup", {})
    if not isinstance(setup, dict):
        setup = {}
    skipped_raw = setup.get("skipped", [])
    skipped = [str(value) for value in skipped_raw if str(value).strip()] if isinstance(skipped_raw, list) else []
    return PersistedState(skipped=skipped, ever_completed=bool(setup.get("ever_completed", False)))


def save_skipped(skipped: list[str], path: Path | None = None) -> list[str]:
    data = _read_preferences(path)
    setup = data.setdefault("setup", {})
    if not isinstance(setup, dict):
        setup = {}
        data["setup"] = setup
    ordered = sorted(dict.fromkeys(skipped))
    setup["skipped"] = ordered
    _write_preferences(data, path)
    return ordered


def save_ever_completed(value: bool, path: Path | None = None) -> None:
    data = _read_preferences(path)
    setup = data.setdefault("setup", {})
    if not isinstance(setup, dict):
        setup = {}
        data["setup"] = setup
    setup["ever_completed"] = bool(value)
    _write_preferences(data, path)
