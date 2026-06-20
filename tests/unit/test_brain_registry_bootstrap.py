from __future__ import annotations

from pathlib import Path

import pytest

import src.config.paths as paths
from src.config.paths import get_vault_dir
from src.lib.brain_registry_bootstrap import build_default_registry
from src.lib.brain_registry_models import BrainType, GitArrangement


def _write_vault_yaml(tmp_path: Path, vault_path: str, remote: str) -> Path:
    config_dir = tmp_path / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "vault.yaml").write_text(
        "vault:\n"
        f"  path: {vault_path}\n"
        "  git:\n"
        "    auto_commit: true\n"
        "    auto_push: true\n"
        "    remote: origin\n"
        "    branch: main\n"
        f"  remote: \"{remote}\"\n",
        encoding="utf-8",
    )
    return tmp_path


def test_bootstrap_produces_personal_and_project_augur_when_project_brain_exists(
    tmp_path: Path,
):
    project_root = _write_vault_yaml(tmp_path, "~/Projects/Au-vault", "https://github.com/x/au-vault.git")
    brain_root = project_root / "project-brain"
    brain_root.mkdir()
    (brain_root / "BRAIN.yaml").write_text(
        "schema_version: 1\n"
        "id: project-augur\n"
        "type: project\n"
        f"root: {brain_root}\n"
        f"attached_project: {project_root}\n",
        encoding="utf-8",
    )
    (project_root / "shared-vault").mkdir()

    registry = build_default_registry(project_root=project_root)

    assert registry.version == 1
    assert sorted(registry.ids()) == ["personal", "project-augur"]

    personal = registry.get("personal")
    assert personal is not None
    assert personal.type is BrainType.PERSONAL
    assert personal.data_root == Path("~/Projects/Au-vault").expanduser()
    assert personal.git.arrangement is GitArrangement.STANDALONE
    assert personal.git.remote == "https://github.com/x/au-vault.git"
    assert personal.git.branch == "main"

    project = registry.get("project-augur")
    assert project is not None
    assert project.type is BrainType.PROJECT
    assert project.data_root == brain_root.resolve()
    assert project.git.arrangement is GitArrangement.BUNDLED
    assert project.git.host_repo == project_root.resolve()
    assert project.write_policy == "free"
    assert project.description == "Project brain"
    assert project.auto_activate_cwd_under == (project_root.resolve(),)


def test_bootstrap_does_not_create_team_from_shared_vault(tmp_path: Path):
    project_root = _write_vault_yaml(tmp_path, "~/Projects/Au-vault", "https://example.com/x.git")
    (project_root / "shared-vault").mkdir()

    registry = build_default_registry(project_root=project_root)

    assert registry.ids() == ["personal"]


def test_bootstrap_rejects_non_project_project_brain_manifest(tmp_path: Path):
    project_root = _write_vault_yaml(tmp_path, "~/Projects/Au-vault", "https://example.com/x.git")
    brain_root = project_root / "project-brain"
    brain_root.mkdir()
    (brain_root / "BRAIN.yaml").write_text(
        "schema_version: 1\n" "id: personal\n" "type: personal\n" f"root: {brain_root}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="project brain manifest must have type=project"):
        build_default_registry(project_root=project_root)


def test_bootstrap_uses_live_path_helper_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    project_root = _write_vault_yaml(tmp_path, str(tmp_path / "legacy-vault-yaml"), "https://example.com/x.git")
    (project_root / "project.yaml").write_text(
        "name: Test\n" "paths:\n" f"  vault: {tmp_path / 'project-yaml-vault'}\n",
        encoding="utf-8",
    )
    env_vault = tmp_path / "env-vault"
    env_vault.mkdir()
    monkeypatch.setenv("AUGUR_VAULT", str(env_vault))
    monkeypatch.chdir(project_root)
    paths.invalidate_project_cache()

    registry = build_default_registry(project_root=project_root)

    assert registry.get("personal").data_root == get_vault_dir()
    assert registry.ids() == ["personal"]


def test_bootstrap_uses_project_yaml_when_project_is_active(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    project_root = _write_vault_yaml(tmp_path, str(tmp_path / "legacy-vault-yaml"), "https://example.com/x.git")
    project_vault = tmp_path / "project-yaml-vault"
    project_vault.mkdir()
    (project_root / "project.yaml").write_text(
        "name: Test\n" "paths:\n" f"  vault: {project_vault}\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("AUGUR_VAULT", raising=False)
    monkeypatch.setenv("AUGUR_ROOT", str(project_root))
    monkeypatch.chdir(project_root)
    paths.invalidate_project_cache()

    registry = build_default_registry(project_root=project_root)

    assert registry.get("personal").data_root == get_vault_dir()
    assert registry.get("personal").data_root == project_vault


def test_bootstrap_raises_when_vault_yaml_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="vault.yaml not found"):
        build_default_registry(project_root=tmp_path)
