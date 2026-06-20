from __future__ import annotations

from pathlib import Path

import pytest

from src.config.paths import (
    get_active_brain_context,
    get_augur_state_dir,
    get_brain_dir,
    get_brain_registry_path,
    get_project_brain_config_dir,
    get_project_brain_dir,
    get_project_brain_mapped_source,
    get_project_brain_mapped_sources,
    get_project_brain_notes_dir,
    get_project_brain_skills_dir,
    get_project_brain_sources_dir,
    get_project_brain_wiki_dir,
    list_brain_ids,
)
from src.lib.brain_registry import clear_cache
from src.lib.brain_registry_io import save_registry
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
)
from src.lib.brain_manifest import BrainManifest, write_brain_manifest


@pytest.fixture
def isolated_state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("AUGUR_STATE_DIR", str(tmp_path / ".augur"))
    clear_cache()
    yield tmp_path / ".augur"
    clear_cache()


def test_get_augur_state_dir_honors_env(isolated_state_dir: Path):
    assert get_augur_state_dir() == isolated_state_dir


def test_get_brain_registry_path_under_state_dir(isolated_state_dir: Path):
    assert get_brain_registry_path() == isolated_state_dir / "brains.yaml"


def test_get_project_brain_dir_returns_repo_project_brain(tmp_path: Path):
    assert get_project_brain_dir(tmp_path) == tmp_path.resolve() / "project-brain"


def test_project_brain_child_helpers_return_v1_layout(tmp_path: Path):
    root = tmp_path / "repo"

    assert get_project_brain_skills_dir(root) == root.resolve() / "project-brain" / "capabilities" / "skills"
    assert get_project_brain_notes_dir(root) == root.resolve() / "project-brain" / "knowledge" / "notes"
    assert get_project_brain_sources_dir(root) == root.resolve() / "project-brain" / "knowledge" / "sources"
    assert get_project_brain_wiki_dir(root) == root.resolve() / "project-brain" / "knowledge" / "wiki"
    assert get_project_brain_config_dir(root) == root.resolve() / "project-brain" / "config"


def test_project_brain_mapped_sources_cover_governed_repo_roots(tmp_path: Path):
    root = (tmp_path / "repo").resolve()

    # decisions/adrs is no longer a mapped source — ADRs moved physically into
    # project-brain/decisions/adrs/ per ADR-811; the mapping would be self-referential.
    assert get_project_brain_mapped_sources(root) == {
        "specs": root / "docs" / "superpowers" / "specs",
        "plans": root / "docs" / "superpowers" / "plans",
        "instructions/topics": root / "docs" / "agent-topics",
        "capabilities/agents": root / "plugins" / "agents",
        "workflows": root / "docs" / "agent-topics" / "WORKFLOWS.md",
    }


def test_project_brain_mapped_source_resolves_known_logical_path(tmp_path: Path):
    root = (tmp_path / "repo").resolve()

    # decisions/adrs was removed from the mapping (ADR-811: ADRs live physically in
    # project-brain/decisions/adrs/ now); verify a still-mapped key works.
    assert get_project_brain_mapped_source("specs", root) == root / "docs" / "superpowers" / "specs"


def test_project_brain_decisions_adrs_not_in_mapped_sources(tmp_path: Path):
    root = (tmp_path / "repo").resolve()

    # ADR-811: decisions/adrs is no longer a mapped source — it is the physical brain location.
    with pytest.raises(KeyError):
        get_project_brain_mapped_source("decisions/adrs", root)


def test_get_brain_dir_returns_data_root(isolated_state_dir: Path):
    brain = Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=Path("/tmp/test-personal"),
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )
    save_registry(
        BrainRegistry(version=1, brains={"personal": brain}),
        isolated_state_dir / "brains.yaml",
    )
    clear_cache()

    assert get_brain_dir("personal").as_posix() == "/tmp/test-personal"


def test_get_brain_dir_raises_for_missing(isolated_state_dir: Path):
    save_registry(
        BrainRegistry(version=1, brains={}),
        isolated_state_dir / "brains.yaml",
    )
    clear_cache()

    with pytest.raises(KeyError, match="missing"):
        get_brain_dir("missing")


def test_list_brain_ids_returns_registry_keys(isolated_state_dir: Path):
    brain_a = Brain(
        id="a",
        type=BrainType.PERSONAL,
        data_root=Path("/a"),
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )
    brain_b = Brain(
        id="b",
        type=BrainType.TEAM,
        data_root=Path("/b"),
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )
    save_registry(
        BrainRegistry(version=1, brains={"a": brain_a, "b": brain_b}),
        isolated_state_dir / "brains.yaml",
    )
    clear_cache()

    assert sorted(list_brain_ids()) == ["a", "b"]


def test_get_active_brain_context_uses_registry_and_cwd(
    tmp_path: Path,
    isolated_state_dir: Path,
):
    personal = Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=tmp_path / "personal",
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )
    save_registry(
        BrainRegistry(version=1, brains={"personal": personal}),
        isolated_state_dir / "brains.yaml",
    )
    clear_cache()

    ctx = get_active_brain_context(cwd=tmp_path)

    assert ctx.active_brain.id == "personal"
    assert ctx.attached_project is None


def test_get_active_brain_stack_returns_global_and_user(
    tmp_path: Path,
    isolated_state_dir: Path,
):
    from src.config.paths import get_active_brain_stack

    personal = Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=tmp_path / "personal",
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )
    save_registry(
        BrainRegistry(version=1, brains={"personal": personal}),
        isolated_state_dir / "brains.yaml",
    )
    clear_cache()

    stack = get_active_brain_stack(cwd=tmp_path)

    assert [b.type for b in stack.ordered()] == [BrainType.GLOBAL, BrainType.PERSONAL]
    assert stack.project is None
    assert stack.most_specific().id == "personal"


def test_get_vault_skills_dir_uses_capabilities_layout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    from src.config import paths as paths_mod

    monkeypatch.setattr(paths_mod, "get_vault_dir", lambda: tmp_path / "vault")
    assert paths_mod.get_vault_skills_dir() == tmp_path / "vault" / "capabilities" / "skills"


def test_get_configured_vault_skills_dir_uses_capabilities_layout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    from src.config import paths as paths_mod

    monkeypatch.setattr(paths_mod, "get_configured_vault_dir", lambda project_root=None: tmp_path / "cv")
    assert paths_mod.get_configured_vault_skills_dir() == tmp_path / "cv" / "capabilities" / "skills"


def test_get_managed_skill_source_dirs_uses_layered_stack(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    isolated_state_dir: Path,
):
    from src.config import paths as paths_mod

    project = (tmp_path / "repo").resolve()
    project_brain = project / "project-brain"
    write_brain_manifest(
        project_brain,
        BrainManifest(
            schema_version=1,
            id="project-repo",
            type=BrainType.PROJECT,
            root=str(project_brain),
            attached_project=str(project),
        ),
    )
    project_skills = project_brain / "capabilities" / "skills"
    (project_skills / "project-only").mkdir(parents=True)

    personal_root = (tmp_path / "personal").resolve()
    personal_skills = personal_root / "capabilities" / "skills"
    (personal_skills / "user-only").mkdir(parents=True)
    personal = Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=personal_root,
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )
    save_registry(
        BrainRegistry(version=1, brains={"personal": personal}),
        isolated_state_dir / "brains.yaml",
    )
    clear_cache()

    configured_vault = tmp_path / "configured-vault"
    monkeypatch.setattr(
        paths_mod,
        "get_configured_vault_dir",
        lambda project_root=None: configured_vault,
    )

    dirs = paths_mod.get_managed_skill_source_dirs(project)

    assert personal_skills in dirs
    assert dirs.index(personal_skills) < dirs.index(project_skills)
