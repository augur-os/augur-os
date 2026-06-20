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


def test_skill_parity_holds_when_layered_superset_of_single(
    tmp_path: Path,
) -> None:
    from src.lib.brain_parity import assert_skill_parity

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

    result = assert_skill_parity(stack, single_brain_skills={"proj-only"})

    assert result.ok is True
    assert result.added == {"core-only", "user-only"}
    assert result.dropped == set()


def test_skill_parity_fails_when_layered_drops_a_single_brain_skill(
    tmp_path: Path,
) -> None:
    from src.lib.brain_parity import assert_skill_parity

    core = tmp_path / "core"
    _skill(core, "core-only")
    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=core),
        user_brain=None,
        project=None,
    )

    result = assert_skill_parity(
        stack,
        single_brain_skills={"core-only", "vanished"},
    )

    assert result.ok is False
    assert result.dropped == {"vanished"}
