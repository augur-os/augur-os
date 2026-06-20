"""Unit tests for src.lib.mvp_staging_migration.

Covers migrate_non_mvp_skills end-to-end behavior plus the private helpers
that build release manifests and prune residual skill directories. The module
reads x-augur-release frontmatter from live skills under
``<project_root>/project-brain/capabilities/skills`` and moves non-MVP skills
into the vault drafts/staging release tree (``get_vault_staging_dir()/<release>``).

``get_project_brain_skills_dir`` is pure path math off ``project_root`` so it
needs no patching; only ``get_vault_staging_dir`` is redirected at a tmp tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import src.lib.mvp_staging_migration as migration
from src.lib.frontmatter_utils import parse_frontmatter


def _make_skill(skills_root: Path, name: str, release: str | None) -> Path:
    skill_dir = skills_root / name
    skill_dir.mkdir(parents=True)
    if release is None:
        fm = f"---\nname: {name}\n---\n"
    else:
        fm = f"---\nname: {name}\nx-augur-release: {release}\n---\n"
    (skill_dir / "SKILL.md").write_text(fm, encoding="utf-8")
    return skill_dir


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Wire a tmp project root + tmp vault staging dir."""
    project_root = tmp_path / "repo"
    skills_root = project_root / "project-brain" / "capabilities" / "skills"
    skills_root.mkdir(parents=True)
    vault_staging = tmp_path / "vault" / "drafts" / "staging"

    monkeypatch.setattr(migration, "get_vault_staging_dir", lambda: vault_staging)

    return project_root, skills_root, vault_staging


def test_keeps_mvp_skills_in_place(env) -> None:
    project_root, skills_root, vault_staging = env
    _make_skill(skills_root, "ask", "mvp")

    result = migration.migrate_non_mvp_skills(project_root)

    assert result["kept"] == ["ask"]
    assert result["moved"] == []
    assert result["staged_releases"] == []
    # MVP skill stays in the live tree and nothing was staged.
    assert (skills_root / "ask" / "SKILL.md").exists()
    assert not vault_staging.exists()


def test_moves_non_mvp_skill_into_release_tree(env) -> None:
    project_root, skills_root, vault_staging = env
    _make_skill(skills_root, "venture", "r4")

    result = migration.migrate_non_mvp_skills(project_root)

    assert result["moved"] == ["venture"]
    assert result["kept"] == []
    assert result["staged_releases"] == ["r4"]

    moved_to = vault_staging / "r4" / "skills" / "venture" / "SKILL.md"
    assert moved_to.exists()
    # Source removed from the live skills tree.
    assert not (skills_root / "venture").exists()


def test_partitions_mvp_and_non_mvp(env) -> None:
    project_root, skills_root, vault_staging = env
    _make_skill(skills_root, "ask", "mvp")
    _make_skill(skills_root, "keep", "mvp")
    _make_skill(skills_root, "apple", "r1")
    _make_skill(skills_root, "venture", "r4")

    result = migration.migrate_non_mvp_skills(project_root)

    # Results are sorted.
    assert result["kept"] == ["ask", "keep"]
    assert result["moved"] == ["apple", "venture"]
    assert result["staged_releases"] == ["r1", "r4"]

    assert (skills_root / "ask").exists()
    assert (skills_root / "keep").exists()
    assert (vault_staging / "r1" / "skills" / "apple" / "SKILL.md").exists()
    assert (vault_staging / "r4" / "skills" / "venture" / "SKILL.md").exists()


def test_writes_release_manifest_with_motive_skills_and_pages_scaffold(env) -> None:
    project_root, skills_root, vault_staging = env
    _make_skill(skills_root, "apple", "r1")

    migration.migrate_non_mvp_skills(project_root)

    manifest_path = vault_staging / "r1" / "manifest.md"
    assert manifest_path.exists()
    metadata, _body = parse_frontmatter(manifest_path, include_sidecar_config=False)
    assert metadata["release"] == "r1"
    assert metadata["motive"] == migration.RELEASE_MOTIVES["r1"]
    assert metadata["skills"] == ["apple"]
    assert metadata["pages"] == []
    assert metadata["prerequisites"] == []

    # pages/ scaffold + .gitkeep are created so the payload tree is valid.
    keep = vault_staging / "r1" / "pages" / ".gitkeep"
    assert keep.exists()
    assert keep.read_text(encoding="utf-8") == ""


def test_manifest_lists_multiple_skills_in_same_release_sorted(env) -> None:
    project_root, skills_root, vault_staging = env
    _make_skill(skills_root, "zebra", "r2")
    _make_skill(skills_root, "alpha", "r2")

    migration.migrate_non_mvp_skills(project_root)

    metadata, _ = parse_frontmatter(vault_staging / "r2" / "manifest.md", include_sidecar_config=False)
    assert metadata["skills"] == ["alpha", "zebra"]


def test_manifest_counts_preexisting_pages(env) -> None:
    project_root, skills_root, vault_staging = env
    # A page already exists in the release tree before migration runs.
    page = vault_staging / "r3" / "pages" / "command" / "validator.tsx"
    page.parent.mkdir(parents=True)
    page.write_text("export default null\n", encoding="utf-8")
    # Hidden files must be ignored by the page scanner.
    (vault_staging / "r3" / "pages" / ".hidden").write_text("x\n", encoding="utf-8")

    _make_skill(skills_root, "validator", "r3")

    migration.migrate_non_mvp_skills(project_root)

    metadata, _ = parse_frontmatter(vault_staging / "r3" / "manifest.md", include_sidecar_config=False)
    assert metadata["pages"] == ["pages/command/validator.tsx"]


def test_existing_target_is_replaced_not_merged(env) -> None:
    project_root, skills_root, vault_staging = env
    # Stale target with a leftover file that should NOT survive replacement.
    stale = vault_staging / "r1" / "skills" / "apple"
    stale.mkdir(parents=True)
    (stale / "STALE.md").write_text("old\n", encoding="utf-8")
    (stale / "SKILL.md").write_text("---\nname: stale\n---\n", encoding="utf-8")

    _make_skill(skills_root, "apple", "r1")

    migration.migrate_non_mvp_skills(project_root)

    target = vault_staging / "r1" / "skills" / "apple"
    assert (target / "SKILL.md").read_text(encoding="utf-8") == ("---\nname: apple\nx-augur-release: r1\n---\n")
    # The stale leftover file is gone — the dir was rmtree'd before move.
    assert not (target / "STALE.md").exists()


def test_missing_release_frontmatter_raises(env) -> None:
    project_root, skills_root, vault_staging = env
    _make_skill(skills_root, "broken", release=None)

    with pytest.raises(ValueError, match="broken is missing x-augur-release"):
        migration.migrate_non_mvp_skills(project_root)


def test_unsupported_staged_release_raises(env) -> None:
    project_root, skills_root, vault_staging = env
    # "mvp" is the only MVP value; an arbitrary release that is neither mvp nor
    # in STAGED_RELEASES must be rejected by ensure_valid_staged_release.
    _make_skill(skills_root, "weird", "r9")

    with pytest.raises(ValueError, match="unsupported staged release"):
        migration.migrate_non_mvp_skills(project_root)


def test_residual_dirs_without_skill_md_are_pruned(env) -> None:
    project_root, skills_root, vault_staging = env
    # A directory left behind with no SKILL.md (e.g. emptied after a move).
    residual = skills_root / "leftover"
    residual.mkdir()
    (residual / "scratch.txt").write_text("junk\n", encoding="utf-8")
    _make_skill(skills_root, "ask", "mvp")

    result = migration.migrate_non_mvp_skills(project_root)

    assert result["removed_residual_dirs"] == ["leftover"]
    assert not residual.exists()
    # Real MVP skill with a SKILL.md is untouched.
    assert (skills_root / "ask" / "SKILL.md").exists()


def test_no_skills_returns_empty_result(env) -> None:
    project_root, skills_root, vault_staging = env

    result = migration.migrate_non_mvp_skills(project_root)

    assert result == {
        "kept": [],
        "moved": [],
        "removed_residual_dirs": [],
        "staged_releases": [],
    }


def test_accepts_string_project_root(env) -> None:
    project_root, skills_root, vault_staging = env
    _make_skill(skills_root, "apple", "r1")

    # migrate_non_mvp_skills coerces str -> Path.
    result = migration.migrate_non_mvp_skills(str(project_root))

    assert result["moved"] == ["apple"]
    assert (vault_staging / "r1" / "skills" / "apple" / "SKILL.md").exists()


def test_later_release_is_supported(env) -> None:
    project_root, skills_root, vault_staging = env
    _make_skill(skills_root, "someday", "later")

    result = migration.migrate_non_mvp_skills(project_root)

    assert result["moved"] == ["someday"]
    assert result["staged_releases"] == ["later"]
    metadata, _ = parse_frontmatter(vault_staging / "later" / "manifest.md", include_sidecar_config=False)
    assert metadata["motive"] == migration.RELEASE_MOTIVES["later"]
