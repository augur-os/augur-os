from __future__ import annotations

from pathlib import Path, PurePath, PurePosixPath
from typing import Any

import yaml

from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
    PropagationPolicy,
)

_SUPPORTED_VERSIONS = frozenset({1})


def load_registry(path: Path) -> BrainRegistry:
    if not path.is_file():
        raise FileNotFoundError(f"brain registry not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _registry_from_dict(raw)


def save_registry(registry: BrainRegistry, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _registry_to_dict(registry)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def _registry_from_dict(raw: dict[str, Any]) -> BrainRegistry:
    version = raw.get("version")
    if version not in _SUPPORTED_VERSIONS:
        raise ValueError(f"unsupported registry version: {version}")
    brains_raw = raw.get("brains") or {}
    brains: dict[str, Brain] = {}
    for brain_id, body in brains_raw.items():
        brains[brain_id] = _brain_from_dict(brain_id, body)
    return BrainRegistry(version=version, brains=brains)


def _brain_from_dict(brain_id: str, body: dict[str, Any]) -> Brain:
    try:
        brain_type = BrainType(body["type"])
    except ValueError as exc:
        raise ValueError(f"invalid brain type for '{brain_id}': {body.get('type')}") from exc

    git = _git_from_dict(body.get("git") or {})
    propagation_raw = body.get("propagation") or {}
    propagation = PropagationPolicy(
        allow_from=tuple(propagation_raw.get("allow_from") or ()),
        allow_to=tuple(propagation_raw.get("allow_to") or ()),
    )
    cwd_under = tuple(_registry_path(p) for p in (body.get("auto_activate_when", {}).get("cwd_under") or ()))
    skills_allow_raw = body.get("skills_allow")
    skills_allow = tuple(skills_allow_raw) if skills_allow_raw is not None else None
    return Brain(
        id=brain_id,
        type=brain_type,
        data_root=_registry_path(body["data_root"]),
        git=git,
        description=body.get("description"),
        write_policy=body.get("write_policy", "free"),
        auto_activate_cwd_under=cwd_under,
        propagation=propagation,
        skills_allow=skills_allow,
        skills_deny=tuple(body.get("skills_deny") or ()),
    )


def _git_from_dict(body: dict[str, Any]) -> GitConfig:
    try:
        arrangement = GitArrangement(body.get("arrangement", "untracked"))
    except ValueError as exc:
        raise ValueError(f"invalid git arrangement: {body.get('arrangement')}") from exc
    host_repo = body.get("host_repo")
    return GitConfig(
        arrangement=arrangement,
        remote=body.get("remote"),
        branch=body.get("branch", "main"),
        auto_commit=bool(body.get("auto_commit", True)),
        auto_push=bool(body.get("auto_push", True)),
        host_repo=_registry_path(host_repo) if host_repo else None,
    )


def _registry_path(value: str | Path) -> PurePath:
    text = str(value)
    if text.startswith("/") and not text.startswith("//"):
        return PurePosixPath(text)
    return Path(text)


def _registry_to_dict(registry: BrainRegistry) -> dict[str, Any]:
    return {
        "version": registry.version,
        "brains": {brain_id: _brain_to_dict(brain) for brain_id, brain in registry.brains.items()},
    }


def _brain_to_dict(brain: Brain) -> dict[str, Any]:
    out: dict[str, Any] = {
        "type": brain.type.value,
        "data_root": str(brain.data_root),
        "git": _git_to_dict(brain.git),
        "write_policy": brain.write_policy,
    }
    if brain.description is not None:
        out["description"] = brain.description
    if brain.auto_activate_cwd_under:
        out["auto_activate_when"] = {"cwd_under": [str(p) for p in brain.auto_activate_cwd_under]}
    if brain.propagation.allow_from or brain.propagation.allow_to:
        out["propagation"] = {
            "allow_from": list(brain.propagation.allow_from),
            "allow_to": list(brain.propagation.allow_to),
        }
    if brain.skills_allow is not None:
        out["skills_allow"] = list(brain.skills_allow)
    if brain.skills_deny:
        out["skills_deny"] = list(brain.skills_deny)
    return out


def _git_to_dict(git: GitConfig) -> dict[str, Any]:
    out: dict[str, Any] = {
        "arrangement": git.arrangement.value,
        "branch": git.branch,
        "auto_commit": git.auto_commit,
        "auto_push": git.auto_push,
    }
    if git.remote is not None:
        out["remote"] = git.remote
    if git.host_repo is not None:
        out["host_repo"] = str(git.host_repo)
    return out
