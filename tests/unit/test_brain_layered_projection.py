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


def _brain(brain_id: str, brain_type: BrainType, root: Path, project: Path | None = None) -> Brain:
    git = (
        GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project)
        if brain_type is BrainType.PROJECT and project is not None
        else GitConfig(arrangement=GitArrangement.UNTRACKED)
    )
    return Brain(
        id=brain_id,
        type=brain_type,
        data_root=root,
        git=git,
        auto_activate_cwd_under=(project,) if project is not None else (),
    )


def _mk_skill_root(brain_root: Path, *skills: str) -> Path:
    skills_dir = brain_root / "capabilities" / "skills"
    for name in skills:
        (skills_dir / name).mkdir(parents=True)
    if not skills:
        skills_dir.mkdir(parents=True, exist_ok=True)
    return skills_dir


def _stack(tmp_path: Path) -> BrainStack:
    core_root = tmp_path / "core"
    _mk_skill_root(core_root, "core-skill")
    user_root = tmp_path / "vault"
    _mk_skill_root(user_root, "user-skill")
    project = tmp_path / "repo"
    project_brain = project / "project-brain"
    _mk_skill_root(project_brain, "proj-skill")
    return BrainStack(
        global_brain=resolve_global_brain(core_root=core_root),
        user_brain=_brain("personal", BrainType.PERSONAL, user_root),
        project=ActiveBrainContext(
            active_brain=_brain("project-repo", BrainType.PROJECT, project_brain, project),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )


def test_resolve_layered_projection_one_layer_per_tier_in_order(tmp_path: Path) -> None:
    from src.lib.brain_layered_projection import resolve_layered_projection

    proj = resolve_layered_projection(_stack(tmp_path))

    assert [layer.tier for layer in proj.layers] == [
        BrainType.GLOBAL,
        BrainType.PERSONAL,
        BrainType.PROJECT,
    ]
    assert [layer.brain_id for layer in proj.layers] == [
        "augur-core",
        "personal",
        "project-repo",
    ]
    # each layer carries its own skill root
    assert proj.layers[0].sources.skill_roots == (tmp_path / "core" / "capabilities" / "skills",)
    assert proj.layers[1].sources.skill_roots == (tmp_path / "vault" / "capabilities" / "skills",)
    assert proj.layers[2].sources.skill_roots == (tmp_path / "repo" / "project-brain" / "capabilities" / "skills",)


def test_ordered_roots_precedence_order_and_distinct_roots(tmp_path: Path) -> None:
    from src.lib.brain_layered_projection import resolve_layered_projection

    proj = resolve_layered_projection(_stack(tmp_path))

    # general -> specific, all distinct here
    assert proj.ordered_skill_roots() == (
        tmp_path / "core" / "capabilities" / "skills",
        tmp_path / "vault" / "capabilities" / "skills",
        tmp_path / "repo" / "project-brain" / "capabilities" / "skills",
    )


def test_ordered_skill_roots_dedupes_coincident_global_and_project_root(
    tmp_path: Path,
) -> None:
    # ADR-781 D10: in the Augur repo, Global and project-augur share project-brain.
    from src.lib.brain_layered_projection import resolve_layered_projection

    project = tmp_path / "repo"
    project_brain = project / "project-brain"
    _mk_skill_root(project_brain, "shared-skill")
    user_root = tmp_path / "vault"
    _mk_skill_root(user_root, "user-skill")

    stack = BrainStack(
        # Global core root == the project brain root → coincident
        global_brain=resolve_global_brain(core_root=project_brain),
        user_brain=_brain("personal", BrainType.PERSONAL, user_root),
        project=ActiveBrainContext(
            active_brain=_brain("project-repo", BrainType.PROJECT, project_brain, project),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )

    proj = resolve_layered_projection(stack)
    roots = proj.ordered_skill_roots()

    project_skills = project_brain / "capabilities" / "skills"
    user_skills = user_root / "capabilities" / "skills"
    # coincident global+project root appears exactly once; user root distinct
    assert roots.count(project_skills) == 1
    assert set(roots) == {project_skills, user_skills}
    assert len(roots) == 2


def test_layered_skill_source_dirs_returns_ordered_deduped_roots(
    tmp_path: Path,
) -> None:
    from src.lib.brain_layered_projection import layered_skill_source_dirs

    roots = layered_skill_source_dirs(_stack(tmp_path))

    assert roots == (
        tmp_path / "core" / "capabilities" / "skills",
        tmp_path / "vault" / "capabilities" / "skills",
        tmp_path / "repo" / "project-brain" / "capabilities" / "skills",
    )
