#!/usr/bin/env python3
"""Generate docs/generated/skill-release-matrix.json from managed live skills."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from src.config.paths import get_managed_skill_source_dirs
from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.generated_artifacts import write_stable_json
from src.lib.skill_release_matrix import build_skill_release_matrix
from src.plugins.skill_discovery import normalize_skill_id


def _dependencies_for_frontmatter(frontmatter: dict[str, Any]) -> dict[str, Any]:
    raw_dependencies = frontmatter.get("x-augur-dependencies")
    if isinstance(raw_dependencies, dict):
        return raw_dependencies

    augur_config = frontmatter.get("x-augur-config")
    if isinstance(augur_config, dict):
        config_dependencies = augur_config.get("dependencies")
        if isinstance(config_dependencies, dict):
            return config_dependencies

    return {}


def _record_from_skill_dir(skill_dir: Path) -> SimpleNamespace:
    frontmatter, _body = parse_frontmatter(skill_dir / "SKILL.md")
    return SimpleNamespace(
        name=normalize_skill_id(str(frontmatter.get("name") or skill_dir.name)),
        path=skill_dir,
        hub=str(frontmatter.get("x-augur-hub") or ""),
        tier=0,
        group=frontmatter.get("x-augur-group"),
        release=frontmatter.get("x-augur-release"),
        # x-augur-visibility removed in Track 4 of the cross-client bundle
        # migration; SkillRelease accepts visibility for backward compat.
        visibility="",
        requires_platform=bool(frontmatter.get("x-augur-requires-platform", False)),
        dependencies=_dependencies_for_frontmatter(frontmatter),
    )


def collect_release_records(project_root: Path) -> list[SimpleNamespace]:
    records: list[SimpleNamespace] = []
    seen_names: set[str] = set()
    for skills_root in get_managed_skill_source_dirs(project_root):
        if not skills_root.is_dir():
            continue
        for skill_dir in sorted(skills_root.iterdir(), key=lambda item: item.name):
            if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").is_file():
                continue
            record = _record_from_skill_dir(skill_dir)
            if record.name in seen_names:
                continue
            seen_names.add(record.name)
            records.append(record)
    return sorted(records, key=lambda record: record.name)


def main() -> None:
    matrix = build_skill_release_matrix(collect_release_records(root), root)
    out_path = root / "docs" / "generated" / "skill-release-matrix.json"
    write_stable_json(out_path, matrix, volatile_keys=["generated_at"])
    print(f"Generated {out_path}: {matrix['count']} skills")


if __name__ == "__main__":
    main()
