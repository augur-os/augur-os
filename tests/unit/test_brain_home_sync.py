from __future__ import annotations

from pathlib import Path

from src.lib.brain_context import ActiveBrainContext
from src.lib.brain_registry_models import (
    Brain,
    BrainType,
    GitArrangement,
    GitConfig,
)
from src.lib.brain_stack import BrainStack, resolve_global_brain


def _skill(brain_root: Path, name: str) -> None:
    skill_dir = brain_root / "capabilities" / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\n---\n",
        encoding="utf-8",
    )


def test_home_sync_disabled_by_default(monkeypatch) -> None:
    from src.lib import brain_home_sync

    monkeypatch.delenv("AUGUR_HOME_SYNC", raising=False)
    monkeypatch.setattr(brain_home_sync, "_pref_home_sync", lambda: None)

    assert brain_home_sync.home_sync_enabled() is False


def test_home_sync_enabled_via_env(monkeypatch) -> None:
    from src.lib import brain_home_sync

    monkeypatch.setenv("AUGUR_HOME_SYNC", "1")

    assert brain_home_sync.home_sync_enabled() is True


def test_partition_skills_by_target_splits_by_winning_tier(tmp_path: Path) -> None:
    from src.lib.brain_home_sync import partition_skills_by_target

    core = tmp_path / "core"
    _skill(core, "core-only")
    vault = tmp_path / "vault"
    _skill(vault, "user-only")
    project = tmp_path / "repo"
    project_brain = project / "project-brain"
    _skill(project_brain, "proj-only")
    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=core),
        user_brain=Brain(
            id="personal",
            type=BrainType.PERSONAL,
            data_root=vault,
            git=GitConfig(arrangement=GitArrangement.UNTRACKED),
        ),
        project=ActiveBrainContext(
            active_brain=Brain(
                id="project-repo",
                type=BrainType.PROJECT,
                data_root=project_brain,
                git=GitConfig(
                    arrangement=GitArrangement.BUNDLED,
                    host_repo=project,
                ),
                auto_activate_cwd_under=(project,),
            ),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )

    home, repo = partition_skills_by_target(stack)

    assert home == {"core-only", "user-only"}
    assert repo == {"proj-only"}
