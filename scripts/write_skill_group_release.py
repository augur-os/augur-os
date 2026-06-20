#!/usr/bin/env python3
"""Write x-augur-group and x-augur-release tags for every first-party skill."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter
from src.lib.staged_skill_catalog import iter_all_release_skill_dirs
from src.lib.skill_release import (
    RELEASE_ORDER,
    ensure_valid_group,
    ensure_valid_release,
    validate_dependency_closure,
)

SKILL_TAGS: dict[str, tuple[str, str]] = {
    "advisor": ("business", "r3"),
    "ai": ("augur_core", "mvp"),
    "apple": ("productivity", "r1"),
    "attention": ("life", "r4"),
    "augur-core": ("augur_core", "mvp"),
    "auto-skill-quality": ("augur_autoloops", "mvp"),
    "books": ("productivity", "r2"),
    "career-ops": ("career", "r4"),
    "channels": ("dev", "r4"),
    "consulting-template": ("templates", "later"),
    "content": ("business", "r2"),
    "daemon": ("augur_admin", "mvp"),
    "document-extractor": ("brain", "mvp"),
    "eisenhower": ("productivity", "r1"),
    "evolve": ("dev", "r3"),
    "file-manager": ("productivity", "mvp"),
    "finance": ("life", "r1"),
    "google-workspace": ("productivity", "r1"),
    "health": ("life", "r1"),
    "home-automation": ("life", "r4"),
    "import": ("productivity", "r2"),
    "ingest": ("brain", "mvp"),
    "knowledge": ("brain", "mvp"),
    "lifestyle": ("life", "r4"),
    "loop-docs": ("augur_autoloops", "mvp"),
    "loop-hub-coverage": ("augur_autoloops", "mvp"),
    "loop-memory": ("augur_autoloops", "mvp"),
    "loop-observability": ("augur_autoloops", "mvp"),
    "loop-ops": ("augur_autoloops", "mvp"),
    "loop-quality": ("augur_autoloops", "mvp"),
    "loop-repo": ("augur_autoloops", "mvp"),
    "loop-test": ("augur_autoloops", "mvp"),
    "loop-wiring": ("augur_autoloops", "mvp"),
    "observe": ("augur_admin", "r3"),
    "obsidian": ("brain", "r1"),
    "onboard": ("augur_core", "mvp"),
    "patterns": ("dev", "r3"),
    "platform-admin": ("augur_admin", "mvp"),
    "plugin-pack": ("augur_admin", "r3"),
    "project-dev": ("dev", "r3"),
    "rag": ("brain", "mvp"),
    "scraper": ("websites", "r2"),
    "skillstore": ("augur_admin", "r3"),
    "smb-client-template": ("templates", "later"),
    "system-cleanup": ("augur_admin", "r3"),
    "terminal-automation-template": ("templates", "later"),
    "updater": ("augur_admin", "r3"),
    "validator": ("augur_admin", "r3"),
    "venture": ("business", "r4"),
    "websites": ("websites", "r2"),
}


def _skill_paths() -> list[Path]:
    return iter_all_release_skill_dirs(root)


def _skill_names() -> list[str]:
    return sorted(skill_dir.name for skill_dir in _skill_paths())


def _ordered_metadata(metadata: dict[str, object], group: str, release: str) -> dict[str, object]:
    ordered: dict[str, object] = {}
    if "name" in metadata:
        ordered["name"] = metadata["name"]
    if "x-augur-type" in metadata:
        ordered["x-augur-type"] = metadata["x-augur-type"]

    ordered["x-augur-group"] = group
    ordered["x-augur-release"] = release

    for key, value in metadata.items():
        if key in {"name", "x-augur-type", "x-augur-group", "x-augur-release", "x-augur-category"}:
            continue
        ordered[key] = value
    return ordered


def _validate_skill_map(skill_names: list[str]) -> None:
    expected = set(skill_names)
    actual = set(SKILL_TAGS)
    if expected != actual:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(
            f"SKILL_TAGS drifted from skills/*: missing={missing or []}, extra={extra or []}"
        )

    for skill_name, (group, release) in SKILL_TAGS.items():
        ensure_valid_group(group)
        ensure_valid_release(release)


def _validate_dependency_staging(skill_paths: list[Path]) -> None:
    records: list[SimpleNamespace] = []
    for skill_dir in skill_paths:
        skill_name = skill_dir.name
        metadata, _ = parse_frontmatter(
            skill_dir / "SKILL.md",
            include_sidecar_config=False,
        )
        _group, release = SKILL_TAGS[skill_name]
        records.append(
            SimpleNamespace(
                name=skill_name,
                release=release,
                dependencies=metadata.get("x-augur-dependencies") or {},
            )
        )

    for target_release in RELEASE_ORDER:
        errors = validate_dependency_closure(records, target_release)
        if errors:
            raise ValueError(
                f"Release dependency closure failed for {target_release}: {', '.join(sorted(errors))}"
            )


def main() -> None:
    skill_paths = _skill_paths()
    skill_names = sorted(skill_dir.name for skill_dir in skill_paths)
    _validate_skill_map(skill_names)
    _validate_dependency_staging(skill_paths)

    for skill_dir in skill_paths:
        skill_name = skill_dir.name
        skill_md = skill_dir / "SKILL.md"
        metadata, body = parse_frontmatter(skill_md, include_sidecar_config=False)
        group, release = SKILL_TAGS[skill_name]
        write_frontmatter(skill_md, _ordered_metadata(metadata, group, release), body)

    print(f"Updated {len(skill_names)} skills with x-augur-group and x-augur-release")


if __name__ == "__main__":
    main()
