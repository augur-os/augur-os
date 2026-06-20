from __future__ import annotations

from pathlib import Path

import pytest

from src.lib.brain_manifest import BrainManifest, ensure_brain_skeleton, write_brain_manifest
from src.lib.brain_registry_io import save_registry
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
)


def _brain(
    brain_id: str,
    brain_type: BrainType,
    root: Path,
    *,
    project: Path | None = None,
    write_policy: str = "free",
) -> Brain:
    return Brain(
        id=brain_id,
        type=brain_type,
        data_root=root,
        git=(
            GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project)
            if brain_type is BrainType.PROJECT and project is not None
            else GitConfig(arrangement=GitArrangement.UNTRACKED)
        ),
        write_policy=write_policy,
        auto_activate_cwd_under=(project,) if project is not None else (),
    )


def _write_registry(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    personal_root = tmp_path / "personal"
    team_root = tmp_path / "team"
    project = tmp_path / "repo"
    project_brain = project / "project-brain"
    ensure_brain_skeleton(project_brain)
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
    registry_path = tmp_path / "brains.yaml"
    save_registry(
        BrainRegistry(
            version=1,
            brains={
                "personal": _brain("personal", BrainType.PERSONAL, personal_root),
                "project-repo": _brain(
                    "project-repo",
                    BrainType.PROJECT,
                    project_brain,
                    project=project,
                ),
                "team-core": _brain(
                    "team-core",
                    BrainType.TEAM,
                    team_root,
                    write_policy="packets_only",
                ),
            },
        ),
        registry_path,
    )
    return registry_path, personal_root, project, team_root


def test_explicit_destination_wins_over_cwd_project(tmp_path: Path) -> None:
    from src.lib.brain_write_routing import resolve_write_target

    registry_path, personal_root, project, _team_root = _write_registry(tmp_path)

    target = resolve_write_target(
        explicit_brain="personal",
        cwd=project / "src",
        registry_path=registry_path,
    )

    assert target.brain.id == "personal"
    assert target.reason == "explicit"
    assert target.mode == "direct"
    assert target.notes_vault_dir == personal_root


def test_project_cwd_wins_over_personal_fallback(tmp_path: Path) -> None:
    from src.lib.brain_write_routing import resolve_write_target

    registry_path, _personal_root, project, _team_root = _write_registry(tmp_path)

    target = resolve_write_target(cwd=project / "src" / "pkg", registry_path=registry_path)

    assert target.brain.id == "project-repo"
    assert target.reason == "active-project"
    assert target.mode == "direct"
    assert target.notes_vault_dir == project / "project-brain"


def test_personal_fallback_is_used_outside_project(tmp_path: Path) -> None:
    from src.lib.brain_write_routing import resolve_write_target

    registry_path, personal_root, _project, _team_root = _write_registry(tmp_path)

    target = resolve_write_target(cwd=tmp_path / "outside", registry_path=registry_path)

    assert target.brain.id == "personal"
    assert target.reason == "personal-fallback"
    assert target.mode == "direct"
    assert target.notes_vault_dir == personal_root


def test_default_registry_path_is_used_for_cwd_routing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.lib.brain_registry import clear_cache
    from src.lib.brain_write_routing import resolve_write_target

    state = tmp_path / "state"
    registry_path = state / "brains.yaml"
    personal_root = tmp_path / "personal"
    registry_path.parent.mkdir(parents=True)
    monkeypatch.setenv("AUGUR_STATE_DIR", str(state))
    save_registry(
        BrainRegistry(
            version=1,
            brains={
                "personal": _brain("personal", BrainType.PERSONAL, personal_root),
            },
        ),
        registry_path,
    )
    clear_cache()

    try:
        target = resolve_write_target(cwd=tmp_path / "outside")

        assert target.brain.id == "personal"
        assert target.reason == "personal-fallback"
        assert target.notes_vault_dir == personal_root
    finally:
        clear_cache()


def test_packets_only_team_brain_routes_to_packet_mode(tmp_path: Path) -> None:
    from src.lib.brain_write_routing import resolve_write_target

    registry_path, _personal_root, _project, team_root = _write_registry(tmp_path)

    target = resolve_write_target(explicit_brain="team-core", registry_path=registry_path)

    assert target.brain.id == "team-core"
    assert target.mode == "packet"
    assert target.packet_root == team_root / "inbox" / "propagation"


def test_missing_explicit_destination_is_an_error(tmp_path: Path) -> None:
    from src.lib.brain_write_routing import resolve_write_target

    registry_path, _personal_root, _project, _team_root = _write_registry(tmp_path)

    with pytest.raises(KeyError, match="brain not registered: missing"):
        resolve_write_target(explicit_brain="missing", registry_path=registry_path)
