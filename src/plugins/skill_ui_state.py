"""Runtime-backed per-skill local state.

This state is user-local and machine-local. It holds local dashboard/runtime
behavior such as:

- whether a skill is new to this user's dashboard
- whether a skill is locally disabled
- whether specific capabilities are locally disabled

It should not live inside repo-owned files such as ``skills/{skill}/.config``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_runtime_dir


def get_skill_ui_state_path(runtime_dir: Path | None = None) -> Path:
    """Return the runtime YAML file that stores local skill state."""
    base = Path(runtime_dir) if runtime_dir is not None else get_runtime_dir()
    return base / "dashboard" / "skills-state.yaml"


def _empty_state() -> dict[str, Any]:
    return {
        "version": 1,
        "disabled": [],
        "partial": {},
        "skills": {},
    }


def _normalize_state(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return _empty_state()

    disabled = data.get("disabled")
    if not isinstance(disabled, list):
        disabled = []
    else:
        disabled = [item.strip() for item in disabled if isinstance(item, str) and item.strip()]

    partial_raw = data.get("partial")
    partial: dict[str, list[str]] = {}
    if isinstance(partial_raw, dict):
        for skill, capabilities in partial_raw.items():
            if not isinstance(skill, str) or not skill.strip():
                continue
            if not isinstance(capabilities, list):
                continue
            caps = [
                capability.strip() for capability in capabilities if isinstance(capability, str) and capability.strip()
            ]
            if caps:
                partial[skill.strip()] = sorted(set(caps))

    skills_raw = data.get("skills")
    skills: dict[str, dict[str, Any]] = {}
    if isinstance(skills_raw, dict):
        for skill, entry in skills_raw.items():
            if isinstance(skill, str) and skill.strip() and isinstance(entry, dict):
                skills[skill.strip()] = dict(entry)

    return {
        "version": data.get("version", 1),
        "disabled": sorted(set(disabled)),
        "partial": partial,
        "skills": skills,
    }


def _read_state_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_state()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return _empty_state()
    return _normalize_state(data)


def _write_state_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(_normalize_state(data), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def read_skill_local_state(*, runtime_dir: Path | None = None) -> dict[str, Any]:
    """Return the full runtime skill-state document."""
    path = get_skill_ui_state_path(runtime_dir)
    return _read_state_file(path)


def write_skill_local_state(data: dict[str, Any], *, runtime_dir: Path | None = None) -> None:
    """Write the full runtime skill-state document."""
    path = get_skill_ui_state_path(runtime_dir)
    _write_state_file(path, data)


def read_disabled_skills(*, runtime_dir: Path | None = None) -> set[str]:
    """Return the locally disabled skills set."""
    data = read_skill_local_state(runtime_dir=runtime_dir)
    return set(data.get("disabled", []))


def read_disabled_capabilities(
    skill: str,
    *,
    runtime_dir: Path | None = None,
) -> set[str]:
    """Return locally disabled capabilities for a given skill."""
    data = read_skill_local_state(runtime_dir=runtime_dir)
    partial = data.get("partial", {})
    caps = partial.get(skill, []) if isinstance(partial, dict) else []
    return {cap for cap in caps if isinstance(cap, str) and cap}


def is_skill_enabled(skill: str, *, runtime_dir: Path | None = None) -> bool:
    """Check whether a skill is locally enabled."""
    return skill not in read_disabled_skills(runtime_dir=runtime_dir)


def set_skill_enabled(
    skill: str,
    enabled: bool,
    *,
    runtime_dir: Path | None = None,
) -> dict[str, Any]:
    """Persist local enabled/disabled state for a skill."""
    data = read_skill_local_state(runtime_dir=runtime_dir)
    disabled = set(data.get("disabled", []))
    partial = data.get("partial", {})
    if enabled:
        disabled.discard(skill)
        if isinstance(partial, dict):
            partial.pop(skill, None)
    else:
        disabled.add(skill)
    data["disabled"] = sorted(disabled)
    data["partial"] = partial if isinstance(partial, dict) else {}
    write_skill_local_state(data, runtime_dir=runtime_dir)
    return read_skill_local_state(runtime_dir=runtime_dir)


def set_capability_enabled(
    skill: str,
    capability: str,
    enabled: bool,
    *,
    runtime_dir: Path | None = None,
) -> dict[str, Any]:
    """Persist local enabled/disabled state for one skill capability."""
    data = read_skill_local_state(runtime_dir=runtime_dir)
    partial = data.get("partial", {})
    if not isinstance(partial, dict):
        partial = {}

    caps = set(partial.get(skill, []))
    if enabled:
        caps.discard(capability)
        if caps:
            partial[skill] = sorted(caps)
        else:
            partial.pop(skill, None)
    else:
        caps.add(capability)
        partial[skill] = sorted(caps)

    data["partial"] = partial
    write_skill_local_state(data, runtime_dir=runtime_dir)
    return read_skill_local_state(runtime_dir=runtime_dir)


def remove_skill_local_state(
    skill: str,
    *,
    runtime_dir: Path | None = None,
) -> dict[str, Any]:
    """Remove all local state for a skill."""
    data = read_skill_local_state(runtime_dir=runtime_dir)
    disabled = set(data.get("disabled", []))
    disabled.discard(skill)
    data["disabled"] = sorted(disabled)
    partial = data.get("partial", {})
    if isinstance(partial, dict):
        partial.pop(skill, None)
        data["partial"] = partial
    skills = data.get("skills", {})
    if isinstance(skills, dict):
        skills.pop(skill, None)
        data["skills"] = skills
    write_skill_local_state(data, runtime_dir=runtime_dir)
    return read_skill_local_state(runtime_dir=runtime_dir)


def read_skill_dashboard_state(skill: str, *, runtime_dir: Path | None = None) -> dict[str, Any]:
    """Return the runtime UI state for a single skill."""
    data = read_skill_local_state(runtime_dir=runtime_dir)
    raw = data.get("skills", {}).get(skill, {})
    return raw if isinstance(raw, dict) else {}


def mark_skill_new_to_dashboard(
    skill: str,
    *,
    hub: str | None = None,
    runtime_dir: Path | None = None,
) -> None:
    """Mark a skill as newly surfaced in the dashboard for this user."""
    data = read_skill_local_state(runtime_dir=runtime_dir)
    skills = data.setdefault("skills", {})
    entry = skills.get(skill)
    if not isinstance(entry, dict):
        entry = {}
    entry["is_new_to_dashboard"] = True
    entry.setdefault("first_seen_at", datetime.now(timezone.utc).isoformat())
    if hub:
        entry["hub"] = hub
    skills[skill] = entry
    write_skill_local_state(data, runtime_dir=runtime_dir)


def acknowledge_skill_in_dashboard(
    skill: str,
    *,
    runtime_dir: Path | None = None,
) -> None:
    """Clear the novelty flag once a user has acknowledged the skill."""
    data = read_skill_local_state(runtime_dir=runtime_dir)
    skills = data.setdefault("skills", {})
    entry = skills.get(skill)
    if not isinstance(entry, dict):
        return
    entry["is_new_to_dashboard"] = False
    entry["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
    skills[skill] = entry
    write_skill_local_state(data, runtime_dir=runtime_dir)


def migrate_legacy_skill_config(
    skill_dir: Path,
    *,
    runtime_dir: Path | None = None,
    delete_file: bool = False,
) -> bool:
    """Migrate a legacy `skills/{skill}/.config` file into runtime state."""
    config_path = Path(skill_dir) / ".config"
    if not config_path.exists():
        return False
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    if not isinstance(raw, dict):
        return False

    skill = Path(skill_dir).name
    enabled_raw = raw.get("enabled", True)
    enabled = enabled_raw is not False
    set_skill_enabled(skill, enabled, runtime_dir=runtime_dir)

    if raw.get("status") == "new":
        mark_skill_new_to_dashboard(skill, runtime_dir=runtime_dir)

    if delete_file:
        try:
            config_path.unlink()
        except OSError:
            pass

    return True
