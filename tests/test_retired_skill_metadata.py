"""Guards for retired skill metadata fields."""

from __future__ import annotations

from pathlib import Path

from src.config.paths import get_configured_vault_skills_dir, get_project_brain_skills_dir

RETIRED_FIELD = "x-augur-visibility"


def _canonical_skill_files(repo_root: Path) -> list[Path]:
    skill_files = sorted(get_project_brain_skills_dir(repo_root).glob("*/SKILL.md"))
    vault_skills = get_configured_vault_skills_dir(repo_root)
    if vault_skills.is_dir():
        skill_files.extend(sorted(vault_skills.glob("*/SKILL.md")))
    return skill_files


def test_retired_visibility_metadata_is_not_in_canonical_skill_sources(repo_root: Path) -> None:
    violations = [
        path for path in _canonical_skill_files(repo_root) if RETIRED_FIELD in path.read_text(encoding="utf-8")
    ]

    assert violations == [], f"{RETIRED_FIELD} is retired; remove it from canonical SKILL.md sources: " + ", ".join(
        str(path) for path in violations
    )


def test_retired_visibility_metadata_is_not_in_skill_template(repo_root: Path) -> None:
    template = repo_root / "config" / "system" / "skill-template.yaml"

    assert RETIRED_FIELD not in template.read_text(encoding="utf-8")
