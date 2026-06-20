from __future__ import annotations

from pathlib import Path

from src.lib.brain_context import ActiveBrainContext
from src.lib.brain_layered_projection import resolve_layered_projection
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


def _skill(brain_root: Path, name: str) -> None:
    d = brain_root / "capabilities" / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")


def _stack(tmp_path: Path) -> BrainStack:
    core = tmp_path / "core"
    _skill(core, "shared")  # appears in global
    _skill(core, "core-only")
    vault = tmp_path / "vault"
    _skill(vault, "user-only")
    project = tmp_path / "repo"
    pbrain = project / "project-brain"
    _skill(pbrain, "shared")  # project overrides "shared"
    _skill(pbrain, "proj-only")
    return BrainStack(
        global_brain=resolve_global_brain(core_root=core),
        user_brain=_brain("personal", BrainType.PERSONAL, vault),
        project=ActiveBrainContext(
            active_brain=_brain("project-repo", BrainType.PROJECT, pbrain, project),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )


def test_compute_effective_skills_most_specific_wins_and_records_shadowed(tmp_path: Path) -> None:
    from src.lib.brain_effective import compute_effective_skills
    from src.lib.brain_registry_models import BrainType as BT

    eff = compute_effective_skills(resolve_layered_projection(_stack(tmp_path)))

    # "shared" defined in global + project -> project wins, global shadowed
    shared = eff.entries["shared"]
    assert shared.winner_tier is BT.PROJECT
    assert shared.winner.name == "shared"
    assert [tier for tier, _ in shared.shadowed] == [BT.GLOBAL]

    # tier-exclusive skills win at their own tier with no shadow
    assert eff.entries["core-only"].winner_tier is BT.GLOBAL
    assert eff.entries["core-only"].shadowed == ()
    assert eff.entries["user-only"].winner_tier is BT.PERSONAL
    assert eff.entries["proj-only"].winner_tier is BT.PROJECT

    assert set(eff.names()) == {"shared", "core-only", "user-only", "proj-only"}
    assert eff.shadowed_names() == ["shared"]


def test_compute_effective_skills_dedupes_coincident_global_project_root(tmp_path: Path) -> None:
    from src.lib.brain_effective import compute_effective_skills
    from src.lib.brain_registry_models import BrainType as BT

    project = tmp_path / "repo"
    pbrain = project / "project-brain"
    _skill(pbrain, "shared")  # the single coincident root holds "shared"
    vault = tmp_path / "vault"
    _skill(vault, "user-only")

    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=pbrain),  # Global root == project brain root
        user_brain=_brain("personal", BT.PERSONAL, vault),
        project=ActiveBrainContext(
            active_brain=_brain("project-repo", BT.PROJECT, pbrain, project),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )

    eff = compute_effective_skills(resolve_layered_projection(stack))

    # "shared" came from the coincident root once, attributed to the general tier (GLOBAL),
    # NOT shadowed by itself
    assert eff.entries["shared"].winner_tier is BT.GLOBAL
    assert eff.entries["shared"].shadowed == ()
    assert eff.entries["user-only"].winner_tier is BT.PERSONAL
    assert eff.shadowed_names() == []


def test_effective_summary_reports_skill_counts(tmp_path: Path) -> None:
    from src.lib.brain_effective import effective_summary

    summary = effective_summary(_stack(tmp_path))

    assert summary["skills"]["effective"] == 4  # shared, core-only, user-only, proj-only
    assert summary["skills"]["shadowed"] == ["shared"]
