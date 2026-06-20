"""Readers for .augur-lifecycle.yaml and .milestones.json sidecar files."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class LifecycleConfigError(ValueError):
    """Raised on malformed lifecycle config or milestones file."""


VALID_CANONICAL_STRATEGIES = frozenset({"highest_version", "explicit", "not_a_group"})


@dataclass(frozen=True)
class KnownGroup:
    name: str
    canonical_strategy: str
    pattern: str | None = None
    members: tuple[str, ...] | None = None
    canonical: str | None = None
    decided_at: str | None = None
    decided_by: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class LifecycleConfig:
    enabled: bool = True
    pattern_hints: list[str] = field(default_factory=list)
    keep_latest: int | None = None
    deploy_root: bool = False
    notes: str | None = None
    known_groups: tuple[KnownGroup, ...] = ()


@dataclass(frozen=True)
class MilestonePin:
    relative_path: str
    tag: str
    tagged_at: str | None
    note: str | None


def read_lifecycle_config(folder: Path) -> LifecycleConfig | None:
    """Read .augur-lifecycle.yaml from `folder`, return None if absent."""
    path = folder / ".augur-lifecycle.yaml"
    if not path.is_file():
        return None
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise LifecycleConfigError(f"failed to parse {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise LifecycleConfigError(f"{path}: top-level must be a mapping")

    enabled = raw.get("enabled", True)
    if not isinstance(enabled, bool):
        raise LifecycleConfigError(f"{path}: 'enabled' must be a bool")

    pattern_hints = raw.get("pattern_hints", [])
    if not isinstance(pattern_hints, list) or not all(isinstance(s, str) for s in pattern_hints):
        raise LifecycleConfigError(f"{path}: 'pattern_hints' must be a list of strings")

    keep_latest = raw.get("keep_latest")
    if keep_latest is not None and not isinstance(keep_latest, int):
        raise LifecycleConfigError(f"{path}: 'keep_latest' must be an int")

    deploy_root = raw.get("deploy_root", False)
    if not isinstance(deploy_root, bool):
        raise LifecycleConfigError(f"{path}: 'deploy_root' must be a bool")

    notes = raw.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise LifecycleConfigError(f"{path}: 'notes' must be a string")

    raw_groups = raw.get("known_groups", [])
    if not isinstance(raw_groups, list):
        raise LifecycleConfigError(f"{path}: 'known_groups' must be a list")
    known_groups: list[KnownGroup] = []
    for idx, entry in enumerate(raw_groups):
        if not isinstance(entry, dict):
            raise LifecycleConfigError(f"{path}: known_groups[{idx}] must be a mapping")
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise LifecycleConfigError(
                f"{path}: known_groups[{idx}].name must be a non-empty string"
            )
        strategy = entry.get("canonical_strategy")
        if strategy not in VALID_CANONICAL_STRATEGIES:
            raise LifecycleConfigError(
                f"{path}: known_groups[{idx}].canonical_strategy must be one of "
                f"{sorted(VALID_CANONICAL_STRATEGIES)}; got {strategy!r}"
            )
        pattern = entry.get("pattern")
        if pattern is not None and not isinstance(pattern, str):
            raise LifecycleConfigError(f"{path}: known_groups[{idx}].pattern must be a string")
        members_raw = entry.get("members")
        members: tuple[str, ...] | None = None
        if members_raw is not None:
            if not isinstance(members_raw, list) or not all(
                isinstance(member, str) for member in members_raw
            ):
                raise LifecycleConfigError(
                    f"{path}: known_groups[{idx}].members must be a list of strings"
                )
            members = tuple(members_raw)
        canonical = entry.get("canonical")
        if canonical is not None and not isinstance(canonical, str):
            raise LifecycleConfigError(f"{path}: known_groups[{idx}].canonical must be a string")
        decided_at = entry.get("decided_at")
        if decided_at is not None and not isinstance(decided_at, str):
            raise LifecycleConfigError(f"{path}: known_groups[{idx}].decided_at must be a string")
        decided_by = entry.get("decided_by")
        if decided_by is not None and not isinstance(decided_by, str):
            raise LifecycleConfigError(f"{path}: known_groups[{idx}].decided_by must be a string")
        note = entry.get("note")
        if note is not None and not isinstance(note, str):
            raise LifecycleConfigError(f"{path}: known_groups[{idx}].note must be a string")
        if strategy == "highest_version" and pattern is None:
            raise LifecycleConfigError(
                f"{path}: known_groups[{idx}] strategy=highest_version requires 'pattern'"
            )
        if strategy in {"explicit", "not_a_group"} and members is None:
            raise LifecycleConfigError(
                f"{path}: known_groups[{idx}] strategy={strategy} requires 'members'"
            )
        if strategy == "explicit" and canonical is None:
            raise LifecycleConfigError(
                f"{path}: known_groups[{idx}] strategy=explicit requires 'canonical'"
            )
        known_groups.append(
            KnownGroup(
                name=name,
                canonical_strategy=strategy,
                pattern=pattern,
                members=members,
                canonical=canonical,
                decided_at=decided_at,
                decided_by=decided_by,
                note=note,
            )
        )

    return LifecycleConfig(
        enabled=enabled,
        pattern_hints=list(pattern_hints),
        keep_latest=keep_latest,
        deploy_root=deploy_root,
        notes=notes,
        known_groups=tuple(known_groups),
    )


def read_milestones(folder: Path) -> list[MilestonePin]:
    """Read .milestones.json from `folder`, return [] if absent."""
    path = folder / ".milestones.json"
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise LifecycleConfigError(f"failed to parse {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise LifecycleConfigError(f"{path}: top-level must be an object")

    pins: list[MilestonePin] = []
    for rel_path, entry in raw.items():
        if not isinstance(entry, dict):
            raise LifecycleConfigError(f"{path}: entry for {rel_path!r} must be an object")
        tag = entry.get("tag")
        if not isinstance(tag, str) or not tag:
            raise LifecycleConfigError(f"{path}: entry for {rel_path!r} must have a non-empty 'tag'")
        tagged_at = entry.get("tagged_at")
        if tagged_at is not None and not isinstance(tagged_at, str):
            raise LifecycleConfigError(f"{path}: entry for {rel_path!r}: 'tagged_at' must be a string")
        note = entry.get("note")
        if note is not None and not isinstance(note, str):
            raise LifecycleConfigError(f"{path}: entry for {rel_path!r}: 'note' must be a string")
        pins.append(MilestonePin(relative_path=rel_path, tag=tag, tagged_at=tagged_at, note=note))
    return pins
