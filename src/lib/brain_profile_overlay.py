from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from src.lib.brain_manifest import STANDARD_BRAIN_FILES
from src.lib.brain_stack import BrainStack
from src.lib.frontmatter_utils import parse_frontmatter

ProfileOverlay = dict[str, Any]

_PROFILE_FILENAMES = (
    "profile.yaml",
    "profile.yml",
    "profile.json",
    "profile.md",
    "PROFILE.md",
)
_PROFILE_EXTENSIONS = {".yaml", ".yml", ".json", ".md", ".markdown"}
_ROOT_PROFILE_FILES = {"IDENTITY.md", "SOUL.md", "USER.md"}
_DOCUMENT_METADATA_KEYS = {"title", "brain_scope", "status", "owner"}


def resolve_profile_overlay(stack: BrainStack) -> ProfileOverlay:
    """Merge profile data from Global -> User -> Project brain tiers."""
    overlay: ProfileOverlay = {}
    seen_roots: set[Path] = set()
    for brain in stack.ordered():
        brain_root = Path(brain.data_root)
        resolved_root = brain_root.resolve(strict=False)
        if resolved_root in seen_roots:
            continue
        seen_roots.add(resolved_root)
        overlay = _deep_merge(overlay, _load_root_profile_files(brain_root))
        overlay = _deep_merge(overlay, _load_profile_dir(brain_root))
    return overlay


def _load_root_profile_files(brain_root: Path) -> ProfileOverlay:
    merged: ProfileOverlay = {}
    for filename in STANDARD_BRAIN_FILES:
        if filename not in _ROOT_PROFILE_FILES:
            continue
        path = brain_root / filename
        if not path.is_file() or path.suffix.lower() not in {".md", ".markdown"}:
            continue
        merged = _deep_merge(merged, _profile_frontmatter(_load_profile_file(path)))
    return merged


def _profile_frontmatter(data: ProfileOverlay) -> ProfileOverlay:
    return {key: value for key, value in data.items() if key not in _DOCUMENT_METADATA_KEYS}


def _load_profile_dir(brain_root: Path) -> ProfileOverlay:
    profile_dir = brain_root / "profile"
    if not profile_dir.is_dir():
        return {}

    merged: ProfileOverlay = {}
    for path in _profile_files(profile_dir):
        merged = _deep_merge(merged, _load_profile_file(path))
    return merged


def _profile_files(profile_dir: Path) -> tuple[Path, ...]:
    direct_files = {
        path.name: path
        for path in profile_dir.iterdir()
        if path.is_file() and path.suffix.lower() in _PROFILE_EXTENSIONS
    }
    ordered: list[Path] = [direct_files[name] for name in _PROFILE_FILENAMES if name in direct_files]
    seen = {path.name for path in ordered}
    ordered.extend(path for name, path in sorted(direct_files.items()) if name not in seen)
    return tuple(ordered)


def _load_profile_file(path: Path) -> ProfileOverlay:
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    elif suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
    elif suffix in {".md", ".markdown"}:
        data, _body = parse_frontmatter(path, include_sidecar_config=False)
    else:
        return {}

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"profile file must contain a mapping: {path}")
    return dict(data)


def _deep_merge(base: ProfileOverlay, override: ProfileOverlay) -> ProfileOverlay:
    merged = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = value
    return merged
