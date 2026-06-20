from pathlib import Path

import pytest

import scripts.migrate_staging_to_vault_drafts as staging_migration


def test_copy_repo_staging_to_vault_drafts_copies_when_target_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "repo"
    staged_skill = project_root / "staging" / "r4" / "skills" / "venture"
    staged_skill.mkdir(parents=True)
    (staged_skill / "SKILL.md").write_text("---\nname: venture\n---\n", encoding="utf-8")

    vault_staging = tmp_path / "vault" / "drafts" / "staging"

    monkeypatch.setattr(staging_migration, "get_project_root", lambda: project_root)
    monkeypatch.setattr(staging_migration, "get_vault_staging_dir", lambda: vault_staging)

    source, target, status = staging_migration.copy_repo_staging_to_vault_drafts()

    assert source == project_root / "staging"
    assert target == vault_staging
    assert status == "copied"
    assert (target / "r4" / "skills" / "venture" / "SKILL.md").exists()
    assert not source.exists()


def test_copy_repo_staging_to_vault_drafts_noops_when_already_migrated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "repo"
    vault_staging = tmp_path / "vault" / "drafts" / "staging"
    migrated_skill = vault_staging / "r4" / "skills" / "venture"
    migrated_skill.mkdir(parents=True)
    (migrated_skill / "SKILL.md").write_text("---\nname: venture\n---\n", encoding="utf-8")

    monkeypatch.setattr(staging_migration, "get_project_root", lambda: project_root)
    monkeypatch.setattr(staging_migration, "get_vault_staging_dir", lambda: vault_staging)

    source, target, status = staging_migration.copy_repo_staging_to_vault_drafts()

    assert source == project_root / "staging"
    assert target == vault_staging
    assert status == "already_migrated"
    assert (target / "r4" / "skills" / "venture" / "SKILL.md").exists()


def test_copy_repo_staging_to_vault_drafts_removes_residue_when_already_migrated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "repo"
    residue = project_root / "staging" / "r3" / "skills" / "plugin-pack" / "scripts"
    residue.mkdir(parents=True)
    (residue / ".DS_Store").write_text("ignored\n", encoding="utf-8")
    pycache = residue / "__pycache__"
    pycache.mkdir()
    (pycache / "plugin_assembler.cpython-314.pyc").write_bytes(b"cache")

    vault_staging = tmp_path / "vault" / "drafts" / "staging"
    migrated_skill = vault_staging / "r4" / "skills" / "venture"
    migrated_skill.mkdir(parents=True)
    (migrated_skill / "SKILL.md").write_text("---\nname: venture\n---\n", encoding="utf-8")

    monkeypatch.setattr(staging_migration, "get_project_root", lambda: project_root)
    monkeypatch.setattr(staging_migration, "get_vault_staging_dir", lambda: vault_staging)

    source, target, status = staging_migration.copy_repo_staging_to_vault_drafts()

    assert source == project_root / "staging"
    assert target == vault_staging
    assert status == "already_migrated"
    assert not source.exists()


def test_copy_repo_staging_to_vault_drafts_refuses_existing_target_without_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "repo"
    staged_skill = project_root / "staging" / "r4" / "skills" / "venture"
    staged_skill.mkdir(parents=True)
    (staged_skill / "SKILL.md").write_text("---\nname: venture\n---\n", encoding="utf-8")

    vault_staging = tmp_path / "vault" / "drafts" / "staging"
    stale_file = vault_staging / "old.txt"
    stale_file.parent.mkdir(parents=True)
    stale_file.write_text("stale\n", encoding="utf-8")

    monkeypatch.setattr(staging_migration, "get_project_root", lambda: project_root)
    monkeypatch.setattr(staging_migration, "get_vault_staging_dir", lambda: vault_staging)

    with pytest.raises(FileExistsError):
        staging_migration.copy_repo_staging_to_vault_drafts()

    assert stale_file.exists()


def test_copy_repo_staging_to_vault_drafts_replace_noops_when_target_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "repo"
    staged_skill = project_root / "staging" / "r4" / "skills" / "venture"
    staged_skill.mkdir(parents=True)
    (staged_skill / "SKILL.md").write_text("---\nname: venture\n---\n", encoding="utf-8")

    vault_staging = tmp_path / "vault" / "drafts" / "staging"
    mirrored_skill = vault_staging / "r4" / "skills" / "venture"
    mirrored_skill.mkdir(parents=True)
    (mirrored_skill / "SKILL.md").write_text("---\nname: venture\n---\n", encoding="utf-8")

    monkeypatch.setattr(staging_migration, "get_project_root", lambda: project_root)
    monkeypatch.setattr(staging_migration, "get_vault_staging_dir", lambda: vault_staging)

    source, target, status = staging_migration.copy_repo_staging_to_vault_drafts(replace=True)

    assert source == project_root / "staging"
    assert target == vault_staging
    assert status == "copied"
    assert (target / "r4" / "skills" / "venture" / "SKILL.md").exists()
    assert not source.exists()


def test_copy_repo_staging_to_vault_drafts_replace_overwrites_non_matching_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "repo"
    staged_skill = project_root / "staging" / "r4" / "skills" / "venture"
    staged_skill.mkdir(parents=True)
    (staged_skill / "SKILL.md").write_text("---\nname: venture\n---\n", encoding="utf-8")

    vault_staging = tmp_path / "vault" / "drafts" / "staging"
    live_skill = vault_staging / "r4" / "skills" / "venture"
    live_skill.mkdir(parents=True)
    (live_skill / "SKILL.md").write_text("---\nname: different\n---\n", encoding="utf-8")

    monkeypatch.setattr(staging_migration, "get_project_root", lambda: project_root)
    monkeypatch.setattr(staging_migration, "get_vault_staging_dir", lambda: vault_staging)

    source, target, status = staging_migration.copy_repo_staging_to_vault_drafts(replace=True)

    assert source == project_root / "staging"
    assert target == vault_staging
    assert status == "copied"
    assert (live_skill / "SKILL.md").read_text(encoding="utf-8") == "---\nname: venture\n---\n"
    assert not source.exists()


def test_promote_active_skill_moves_draft_into_vault_skills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = tmp_path / "repo"
    vault_staging = tmp_path / "vault" / "drafts" / "staging"
    vault_skills = tmp_path / "vault" / "skills"
    draft_skill = vault_staging / "r1" / "skills" / "apple"
    draft_skill.mkdir(parents=True)
    (draft_skill / "SKILL.md").write_text("---\nname: apple\n---\n", encoding="utf-8")

    monkeypatch.setattr(staging_migration, "get_project_root", lambda: project_root)
    monkeypatch.setattr(staging_migration, "get_vault_staging_dir", lambda: vault_staging)
    monkeypatch.setattr(staging_migration, "get_vault_skills_dir", lambda: vault_skills)

    target = staging_migration.promote_active_skill("apple", destination="vault")

    assert target == vault_skills / "apple"
    assert (target / "SKILL.md").exists()
    assert not draft_skill.exists()


def test_promote_active_skill_returns_existing_target_when_already_promoted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "repo"
    vault_staging = tmp_path / "vault" / "drafts" / "staging"
    vault_skills = tmp_path / "vault" / "skills"
    target = vault_skills / "apple"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("---\nname: apple\n---\n", encoding="utf-8")

    monkeypatch.setattr(staging_migration, "get_project_root", lambda: project_root)
    monkeypatch.setattr(staging_migration, "get_vault_staging_dir", lambda: vault_staging)
    monkeypatch.setattr(staging_migration, "get_vault_skills_dir", lambda: vault_skills)

    assert staging_migration.promote_active_skill("apple", destination="vault") == target


def test_promote_active_skill_refuses_existing_target_without_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "repo"
    vault_staging = tmp_path / "vault" / "drafts" / "staging"
    vault_skills = tmp_path / "vault" / "skills"
    draft_skill = vault_staging / "r1" / "skills" / "apple"
    draft_skill.mkdir(parents=True)
    (draft_skill / "SKILL.md").write_text("---\nname: apple\n---\n", encoding="utf-8")
    target = vault_skills / "apple"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("---\nname: apple\n---\n", encoding="utf-8")

    monkeypatch.setattr(staging_migration, "get_project_root", lambda: project_root)
    monkeypatch.setattr(staging_migration, "get_vault_staging_dir", lambda: vault_staging)
    monkeypatch.setattr(staging_migration, "get_vault_skills_dir", lambda: vault_skills)

    with pytest.raises(FileExistsError):
        staging_migration.promote_active_skill("apple", destination="vault")

    assert draft_skill.exists()


def test_promote_active_skill_preserves_existing_target_on_ambiguous_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "repo"
    vault_staging = tmp_path / "vault" / "drafts" / "staging"
    vault_skills = tmp_path / "vault" / "skills"
    for release in ("r1", "r4"):
        draft_skill = vault_staging / release / "skills" / "apple"
        draft_skill.mkdir(parents=True)
        (draft_skill / "SKILL.md").write_text("---\nname: apple\n---\n", encoding="utf-8")
    target = vault_skills / "apple"
    target.mkdir(parents=True)
    sentinel = target / "keep.txt"
    sentinel.write_text("preserve\n", encoding="utf-8")

    monkeypatch.setattr(staging_migration, "get_project_root", lambda: project_root)
    monkeypatch.setattr(staging_migration, "get_vault_staging_dir", lambda: vault_staging)
    monkeypatch.setattr(staging_migration, "get_vault_skills_dir", lambda: vault_skills)

    with pytest.raises(ValueError, match="Expected exactly one draft match"):
        staging_migration.promote_active_skill("apple", destination="vault", replace=True)

    assert target.exists()
    assert sentinel.exists()


def test_promote_active_skill_replace_noops_when_draft_matches_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "repo"
    vault_staging = tmp_path / "vault" / "drafts" / "staging"
    vault_skills = tmp_path / "vault" / "skills"
    draft_skill = vault_staging / "r1" / "skills" / "apple"
    draft_skill.mkdir(parents=True)
    (draft_skill / "SKILL.md").write_text("---\nname: apple\n---\n", encoding="utf-8")
    target = vault_skills / "apple"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("---\nname: apple\n---\n", encoding="utf-8")

    monkeypatch.setattr(staging_migration, "get_project_root", lambda: project_root)
    monkeypatch.setattr(staging_migration, "get_vault_staging_dir", lambda: vault_staging)
    monkeypatch.setattr(staging_migration, "get_vault_skills_dir", lambda: vault_skills)

    assert staging_migration.promote_active_skill("apple", destination="vault", replace=True) == target
    assert target.exists()
    assert not draft_skill.exists()


def test_promote_active_skill_replace_overwrites_non_matching_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "repo"
    vault_staging = tmp_path / "vault" / "drafts" / "staging"
    vault_skills = tmp_path / "vault" / "skills"
    draft_skill = vault_staging / "r1" / "skills" / "apple"
    draft_skill.mkdir(parents=True)
    (draft_skill / "SKILL.md").write_text("---\nname: apple\n---\n", encoding="utf-8")
    target = vault_skills / "apple"
    target.mkdir(parents=True)
    existing = target / "SKILL.md"
    existing.write_text("---\nname: different\n---\n", encoding="utf-8")

    monkeypatch.setattr(staging_migration, "get_project_root", lambda: project_root)
    monkeypatch.setattr(staging_migration, "get_vault_staging_dir", lambda: vault_staging)
    monkeypatch.setattr(staging_migration, "get_vault_skills_dir", lambda: vault_skills)

    assert staging_migration.promote_active_skill("apple", destination="vault", replace=True) == target

    assert not draft_skill.exists()
    assert existing.read_text(encoding="utf-8") == "---\nname: apple\n---\n"


def test_copy_repo_staging_to_vault_drafts_replace_restores_target_on_failed_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "repo"
    staged_skill = project_root / "staging" / "r4" / "skills" / "venture"
    staged_skill.mkdir(parents=True)
    (staged_skill / "SKILL.md").write_text("---\nname: venture\n---\n", encoding="utf-8")

    vault_staging = tmp_path / "vault" / "drafts" / "staging"
    live_skill = vault_staging / "r4" / "skills" / "venture"
    live_skill.mkdir(parents=True)
    live_text = "---\nname: existing\n---\n"
    (live_skill / "SKILL.md").write_text(live_text, encoding="utf-8")

    monkeypatch.setattr(staging_migration, "get_project_root", lambda: project_root)
    monkeypatch.setattr(staging_migration, "get_vault_staging_dir", lambda: vault_staging)

    original_verify = staging_migration._assert_tree_matches_signature

    def fail_after_replace(root: Path, signature, *, label: str) -> None:
        if root == vault_staging:
            raise ValueError("boom")
        original_verify(root, signature, label=label)

    monkeypatch.setattr(staging_migration, "_assert_tree_matches_signature", fail_after_replace)

    with pytest.raises(ValueError, match="boom"):
        staging_migration.copy_repo_staging_to_vault_drafts(replace=True)

    assert (live_skill / "SKILL.md").read_text(encoding="utf-8") == live_text
    assert (staged_skill / "SKILL.md").exists()


def test_promote_active_skill_replace_restores_target_on_failed_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "repo"
    vault_staging = tmp_path / "vault" / "drafts" / "staging"
    vault_skills = tmp_path / "vault" / "skills"
    draft_skill = vault_staging / "r1" / "skills" / "apple"
    draft_skill.mkdir(parents=True)
    (draft_skill / "SKILL.md").write_text("---\nname: apple\n---\n", encoding="utf-8")
    target = vault_skills / "apple"
    target.mkdir(parents=True)
    existing = target / "SKILL.md"
    live_text = "---\nname: existing\n---\n"
    existing.write_text(live_text, encoding="utf-8")

    monkeypatch.setattr(staging_migration, "get_project_root", lambda: project_root)
    monkeypatch.setattr(staging_migration, "get_vault_staging_dir", lambda: vault_staging)
    monkeypatch.setattr(staging_migration, "get_vault_skills_dir", lambda: vault_skills)

    original_verify = staging_migration._assert_tree_matches_signature

    def fail_after_replace(root: Path, signature, *, label: str) -> None:
        if root == target:
            raise ValueError("boom")
        original_verify(root, signature, label=label)

    monkeypatch.setattr(staging_migration, "_assert_tree_matches_signature", fail_after_replace)

    with pytest.raises(ValueError, match="boom"):
        staging_migration.promote_active_skill("apple", destination="vault", replace=True)

    assert (draft_skill / "SKILL.md").exists()
    assert existing.read_text(encoding="utf-8") == live_text


def test_promote_active_skill_moves_draft_into_shared_vault_skills(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "repo"
    vault_staging = tmp_path / "vault" / "drafts" / "staging"
    draft_skill = vault_staging / "r3" / "skills" / "plugin-pack"
    draft_skill.mkdir(parents=True)
    (draft_skill / "SKILL.md").write_text("---\nname: plugin-pack\n---\n", encoding="utf-8")

    monkeypatch.setattr(staging_migration, "get_project_root", lambda: project_root)
    monkeypatch.setattr(staging_migration, "get_vault_staging_dir", lambda: vault_staging)
    monkeypatch.setattr(staging_migration, "get_vault_skills_dir", lambda: tmp_path / "vault" / "skills")

    target = staging_migration.promote_active_skill("plugin-pack", destination="repo")

    assert target == project_root / "project-brain" / "capabilities" / "skills" / "plugin-pack"
    assert (target / "SKILL.md").exists()
    assert not draft_skill.exists()


def test_promote_runtime_blockers_moves_known_skills_to_expected_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "repo"
    vault_staging = tmp_path / "vault" / "drafts" / "staging"
    vault_skills = tmp_path / "vault" / "skills"
    for release, name in (("r1", "apple"), ("r4", "lifestyle"), ("r3", "plugin-pack")):
        draft_skill = vault_staging / release / "skills" / name
        draft_skill.mkdir(parents=True)
        (draft_skill / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")

    monkeypatch.setattr(staging_migration, "get_project_root", lambda: project_root)
    monkeypatch.setattr(staging_migration, "get_vault_staging_dir", lambda: vault_staging)
    monkeypatch.setattr(staging_migration, "get_vault_skills_dir", lambda: vault_skills)

    targets = staging_migration.promote_runtime_blockers()

    assert targets == [
        vault_skills / "apple",
        vault_skills / "lifestyle",
        project_root / "project-brain" / "capabilities" / "skills" / "plugin-pack",
    ]


def test_main_promote_command_executes_named_promotions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project_root = tmp_path / "repo"
    vault_staging = tmp_path / "vault" / "drafts" / "staging"
    vault_skills = tmp_path / "vault" / "skills"
    for release, name in (("r1", "apple"), ("r3", "plugin-pack")):
        draft_skill = vault_staging / release / "skills" / name
        draft_skill.mkdir(parents=True)
        (draft_skill / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")

    monkeypatch.setattr(staging_migration, "get_project_root", lambda: project_root)
    monkeypatch.setattr(staging_migration, "get_vault_staging_dir", lambda: vault_staging)
    monkeypatch.setattr(staging_migration, "get_vault_skills_dir", lambda: vault_skills)

    rc = staging_migration.main(["promote", "apple:vault", "plugin-pack:repo"])

    assert rc == 0
    assert (vault_skills / "apple" / "SKILL.md").exists()
    assert (project_root / "project-brain" / "capabilities" / "skills" / "plugin-pack" / "SKILL.md").exists()
    assert capsys.readouterr().out.splitlines() == [
        str(vault_skills / "apple"),
        str(project_root / "project-brain" / "capabilities" / "skills" / "plugin-pack"),
    ]


def test_main_copy_command_noops_after_cutover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project_root = tmp_path / "repo"
    vault_staging = tmp_path / "vault" / "drafts" / "staging"
    migrated_skill = vault_staging / "r4" / "skills" / "venture"
    migrated_skill.mkdir(parents=True)
    (migrated_skill / "SKILL.md").write_text("---\nname: venture\n---\n", encoding="utf-8")

    monkeypatch.setattr(staging_migration, "get_project_root", lambda: project_root)
    monkeypatch.setattr(staging_migration, "get_vault_staging_dir", lambda: vault_staging)

    rc = staging_migration.main(["copy"])

    assert rc == 0
    assert capsys.readouterr().out.splitlines() == [
        str(project_root / "staging"),
        str(vault_staging),
        "already_migrated",
    ]


def test_main_promote_runtime_blockers_executes_known_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project_root = tmp_path / "repo"
    vault_staging = tmp_path / "vault" / "drafts" / "staging"
    vault_skills = tmp_path / "vault" / "skills"
    for release, name in (("r1", "apple"), ("r4", "lifestyle"), ("r3", "plugin-pack")):
        draft_skill = vault_staging / release / "skills" / name
        draft_skill.mkdir(parents=True)
        (draft_skill / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")

    monkeypatch.setattr(staging_migration, "get_project_root", lambda: project_root)
    monkeypatch.setattr(staging_migration, "get_vault_staging_dir", lambda: vault_staging)
    monkeypatch.setattr(staging_migration, "get_vault_skills_dir", lambda: vault_skills)

    rc = staging_migration.main(["promote-runtime-blockers"])

    assert rc == 0
    assert capsys.readouterr().out.splitlines() == [
        str(vault_skills / "apple"),
        str(vault_skills / "lifestyle"),
        str(project_root / "project-brain" / "capabilities" / "skills" / "plugin-pack"),
    ]
