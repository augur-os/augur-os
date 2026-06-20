from __future__ import annotations

from pathlib import Path

import pytest

from src.lib.brain_registry import clear_cache, get_registry
from src.lib.brain_registry_io import load_registry, save_registry
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
)


def _write_vault_yaml(project_root: Path) -> None:
    config_dir = project_root / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "vault.yaml").write_text(
        "vault:\n"
        "  path: ~/Projects/Au-vault\n"
        "  git:\n"
        "    auto_commit: true\n"
        "    auto_push: true\n"
        "    remote: origin\n"
        "    branch: main\n"
        "  remote: \"https://example.com/x.git\"\n",
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def _reset_cache():
    clear_cache()
    yield
    clear_cache()


def test_get_registry_bootstraps_when_missing(tmp_path: Path):
    registry_path = tmp_path / ".augur" / "brains.yaml"
    _write_vault_yaml(tmp_path)
    (tmp_path / "shared-vault").mkdir()

    registry = get_registry(registry_path=registry_path, project_root=tmp_path)

    assert registry_path.is_file()
    assert registry.ids() == ["personal"]


def test_get_registry_reads_existing_file(tmp_path: Path):
    registry_path = tmp_path / ".augur" / "brains.yaml"
    brain = Brain(
        id="custom",
        type=BrainType.PROJECT,
        data_root=Path("/tmp/project"),
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )
    save_registry(BrainRegistry(version=1, brains={"custom": brain}), registry_path)

    registry = get_registry(registry_path=registry_path, project_root=tmp_path)

    assert registry.ids() == ["custom"]
    # Bootstrap was not triggered (vault.yaml absent and we didn't fail).


def test_get_registry_prunes_legacy_shared_vault_team_brain(tmp_path: Path):
    registry_path = tmp_path / ".augur" / "brains.yaml"
    _write_vault_yaml(tmp_path)
    shared_vault = tmp_path / "shared-vault"
    shared_vault.mkdir()
    personal = Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=tmp_path / "personal",
        git=GitConfig(arrangement=GitArrangement.STANDALONE),
    )
    legacy_team = Brain(
        id="team-augur",
        type=BrainType.TEAM,
        data_root=shared_vault,
        git=GitConfig(
            arrangement=GitArrangement.BUNDLED,
            host_repo=tmp_path,
        ),
        description="Augur OSS team brain (bundled with harness repo)",
    )
    save_registry(
        BrainRegistry(version=1, brains={"personal": personal, "team-augur": legacy_team}),
        registry_path,
    )

    registry = get_registry(registry_path=registry_path, project_root=tmp_path)

    assert registry.ids() == ["personal"]
    assert load_registry(registry_path).ids() == ["personal"]


def test_get_registry_prunes_ephemeral_temp_project_brain(tmp_path: Path):
    registry_path = tmp_path / ".augur" / "brains.yaml"
    _write_vault_yaml(tmp_path)
    personal = Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=tmp_path / "personal",
        git=GitConfig(arrangement=GitArrangement.STANDALONE),
    )
    temp_project = tmp_path / "tmp.vEh3EZrLtd"
    temp_project.mkdir()
    temp_brain = Brain(
        id="project-tmp-veh3ezrltd",
        type=BrainType.PROJECT,
        data_root=temp_project / "project-brain",
        git=GitConfig(
            arrangement=GitArrangement.BUNDLED,
            host_repo=temp_project,
        ),
        description="tmp.vEh3EZrLtd project brain",
    )
    save_registry(
        BrainRegistry(version=1, brains={"personal": personal, temp_brain.id: temp_brain}),
        registry_path,
    )

    registry = get_registry(registry_path=registry_path, project_root=tmp_path)

    assert registry.ids() == ["personal"]
    assert load_registry(registry_path).ids() == ["personal"]


def test_get_registry_preserves_real_team_brain(tmp_path: Path):
    registry_path = tmp_path / ".augur" / "brains.yaml"
    _write_vault_yaml(tmp_path)
    team_root = tmp_path / "team-brain"
    team_root.mkdir()
    team = Brain(
        id="team-augur",
        type=BrainType.TEAM,
        data_root=team_root,
        git=GitConfig(arrangement=GitArrangement.STANDALONE),
    )
    save_registry(BrainRegistry(version=1, brains={"team-augur": team}), registry_path)

    registry = get_registry(registry_path=registry_path, project_root=tmp_path)

    assert registry.ids() == ["team-augur"]
    assert load_registry(registry_path).ids() == ["team-augur"]


def test_get_registry_reloads_when_registry_file_changes(tmp_path: Path):
    registry_path = tmp_path / ".augur" / "brains.yaml"
    _write_vault_yaml(tmp_path)
    (tmp_path / "shared-vault").mkdir()

    first = get_registry(registry_path=registry_path, project_root=tmp_path)
    assert first.ids() == ["personal"]

    # Mutate the file on disk while the process cache is warm; the next read
    # should notice the registry changed instead of serving stale Browse context.
    save_registry(BrainRegistry(version=1, brains={}), registry_path)
    second = get_registry(registry_path=registry_path, project_root=tmp_path)
    assert second is not first
    assert second.ids() == []
