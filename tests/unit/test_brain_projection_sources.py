from __future__ import annotations

from pathlib import Path

import yaml

from src.lib.brain_registry_models import Brain, BrainType, GitArrangement, GitConfig


def _brain(
    brain_id: str,
    brain_type: BrainType,
    root: Path,
    project: Path | None = None,
) -> Brain:
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


def test_resolve_projection_sources_prefers_project_brain_canonical_roots(
    tmp_path: Path,
) -> None:
    from src.lib.brain_projection import resolve_brain_projection_sources

    project = tmp_path / "repo"
    brain_root = project / "project-brain"
    rules = brain_root / "instructions" / "agent-rules.md"
    rules.parent.mkdir(parents=True)
    rules.write_text("# Project Rules\n", encoding="utf-8")
    for rel in (
        "capabilities/skills",
        "capabilities/agents",
        "policies",
        "workflows",
    ):
        (brain_root / rel).mkdir(parents=True)

    sources = resolve_brain_projection_sources(
        brain=_brain("project-repo", BrainType.PROJECT, brain_root, project),
        attached_project=project,
    )

    assert sources.rules == rules
    assert sources.rules_label.endswith("project-brain/instructions/agent-rules.md")
    assert sources.skill_roots == (brain_root / "capabilities" / "skills",)
    assert sources.agent_roots == (brain_root / "capabilities" / "agents",)
    assert sources.policy_roots == (brain_root / "policies",)
    assert sources.workflow_roots == (brain_root / "workflows",)


def test_resolve_projection_sources_ignores_retired_shared_vault_skill_root(
    tmp_path: Path,
) -> None:
    from src.lib.brain_projection import resolve_brain_projection_sources

    project = tmp_path / "repo"
    brain_root = project / "project-brain"
    project_skills = brain_root / "capabilities" / "skills"
    project_skills.mkdir(parents=True)
    legacy_skills = project / "shared-vault" / "skills"
    legacy_skills.mkdir(parents=True)

    sources = resolve_brain_projection_sources(
        brain=_brain("project-repo", BrainType.PROJECT, brain_root, project),
        attached_project=project,
    )

    assert sources.skill_roots == (project_skills,)


def test_resolve_projection_sources_uses_worktree_skills_not_attached_main(
    tmp_path: Path,
) -> None:
    """In a git worktree the brain data_root differs from attached_project.

    Skills must track the active tree (the worktree's own project-brain),
    consistent with agents/policies/workflows, never the main checkout.
    Sourcing them from attached_project produced an ``ai`` vs ``ai`` routine
    id collision when both tiers were scanned. Regression guard.
    """
    from src.lib.brain_projection import resolve_brain_projection_sources

    worktree = tmp_path / "augur-wt-abc123"
    brain_root = worktree / "project-brain"
    worktree_skills = brain_root / "capabilities" / "skills"
    worktree_skills.mkdir(parents=True)

    main_checkout = tmp_path / "Augur"
    (main_checkout / "project-brain" / "capabilities" / "skills").mkdir(parents=True)

    sources = resolve_brain_projection_sources(
        brain=_brain("project-augur", BrainType.PROJECT, brain_root, main_checkout),
        attached_project=main_checkout,
    )

    assert sources.skill_roots == (worktree_skills,)


def test_resolve_projection_sources_falls_back_to_attached_when_brain_unpopulated(
    tmp_path: Path,
) -> None:
    """ADR-770: when the brain data_root has no skills dir yet, fall back to
    the attached project's project-brain skills."""
    from src.lib.brain_projection import resolve_brain_projection_sources

    brain_root = tmp_path / "unpopulated" / "project-brain"
    brain_root.mkdir(parents=True)
    attached = tmp_path / "repo"
    attached_skills = attached / "project-brain" / "capabilities" / "skills"
    attached_skills.mkdir(parents=True)

    sources = resolve_brain_projection_sources(
        brain=_brain("project-augur", BrainType.PROJECT, brain_root, attached),
        attached_project=attached,
    )

    assert sources.skill_roots == (attached_skills,)


def test_resolve_projection_sources_maps_repo_docs_with_truthful_source_label(
    tmp_path: Path,
) -> None:
    from src.lib.brain_projection import resolve_brain_projection_sources

    project = tmp_path / "repo"
    brain_root = project / "project-brain"
    rules = project / "docs" / "agent-topics" / "agent-rules.md"
    rules.parent.mkdir(parents=True)
    rules.write_text("# Mapped Rules\n", encoding="utf-8")

    sources = resolve_brain_projection_sources(
        brain=_brain("project-repo", BrainType.PROJECT, brain_root, project),
        attached_project=project,
    )

    assert sources.rules == rules
    assert sources.rules_label == (
        "docs/agent-topics/agent-rules.md " "(mapped to project-brain/instructions/topics/agent-rules.md)"
    )


def test_resolve_projection_sources_supports_personal_brain_roots(tmp_path: Path) -> None:
    from src.lib.brain_projection import resolve_brain_projection_sources

    brain_root = tmp_path / "personal"
    rules = brain_root / "instructions" / "agent-rules.md"
    rules.parent.mkdir(parents=True)
    rules.write_text("# Personal Rules\n", encoding="utf-8")

    sources = resolve_brain_projection_sources(
        brain=_brain("personal", BrainType.PERSONAL, brain_root),
    )

    assert sources.rules == rules
    assert sources.rules_label.endswith("personal/instructions/agent-rules.md")
    assert sources.skill_roots == (brain_root / "capabilities" / "skills",)


def test_context_envelope_is_compact_and_client_neutral(tmp_path: Path) -> None:
    from src.lib.brain_context import ActiveBrainContext
    from src.lib.brain_projection import render_augur_context_envelope

    project = tmp_path / "repo"
    brain_root = project / "project-brain"
    (brain_root / "decisions" / "adrs").mkdir(parents=True)
    context = ActiveBrainContext(
        active_brain=_brain("project-repo", BrainType.PROJECT, brain_root, project),
        attached_project=project,
        source="nearest-project-brain",
    )

    payload = yaml.safe_load(render_augur_context_envelope(context))

    assert payload == {
        "augur": {
            "active_brain": {
                "id": "project-repo",
                "type": "project",
                "root": str(brain_root),
            },
            "attached_project": {
                "root": str(project),
                "has_adrs": True,
                "has_runtime": True,
            },
            "generated_projection": True,
        }
    }


def test_stack_envelope_emits_all_three_tiers(tmp_path: Path) -> None:
    from src.lib.brain_context import ActiveBrainContext
    from src.lib.brain_projection import render_augur_stack_envelope
    from src.lib.brain_stack import BrainStack, resolve_global_brain

    project = tmp_path / "repo"
    brain_root = project / "project-brain"
    (brain_root / "decisions" / "adrs").mkdir(parents=True)
    core_root = tmp_path / "augur-install"
    core_root.mkdir()

    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=core_root),
        user_brain=_brain("personal", BrainType.PERSONAL, tmp_path / "personal"),
        project=ActiveBrainContext(
            active_brain=_brain("project-repo", BrainType.PROJECT, brain_root, project),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )

    payload = yaml.safe_load(render_augur_stack_envelope(stack))
    aug = payload["augur"]

    assert aug["active_brain"]["id"] == "project-repo"  # most specific, back-compat
    assert aug["stack"]["global"]["id"] == "augur-core"
    assert aug["stack"]["global"]["type"] == "global"
    assert aug["stack"]["user"]["id"] == "personal"
    assert aug["stack"]["project"]["id"] == "project-repo"
    assert aug["attached_project"]["root"] == str(project)
    assert aug["attached_project"]["has_adrs"] is True
    assert aug["generated_projection"] is True


def test_stack_envelope_personal_mode_omits_project(tmp_path: Path) -> None:
    from src.lib.brain_projection import render_augur_stack_envelope
    from src.lib.brain_stack import BrainStack, resolve_global_brain

    core_root = tmp_path / "augur-install"
    core_root.mkdir()
    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=core_root),
        user_brain=_brain("personal", BrainType.PERSONAL, tmp_path / "personal"),
        project=None,
    )

    aug = yaml.safe_load(render_augur_stack_envelope(stack))["augur"]

    assert aug["active_brain"]["id"] == "personal"
    assert "project" not in aug["stack"]
    assert aug["attached_project"] is None


def test_collect_standard_brain_files_reads_existing_root_files(
    tmp_path: Path,
) -> None:
    from src.lib.brain_context import ActiveBrainContext
    from src.lib.brain_projection import collect_standard_brain_files
    from src.lib.brain_stack import BrainStack, resolve_global_brain

    project = tmp_path / "repo"
    project_brain = project / "project-brain"
    project_brain.mkdir(parents=True)
    (project_brain / "SOUL.md").write_text(
        "---\ntitle: Project Soul\n---\n\n# Project Soul\n\nProject values.\n",
        encoding="utf-8",
    )
    (project_brain / "USER.md").write_text(
        "---\ntitle: Project User\n---\n\n# Project User\n\nTeam context.\n",
        encoding="utf-8",
    )

    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=tmp_path / "core"),
        user_brain=None,
        project=ActiveBrainContext(
            active_brain=_brain(
                "project-repo",
                BrainType.PROJECT,
                project_brain,
                project,
            ),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )

    files = collect_standard_brain_files(stack, project_root=project)

    assert [(item.tier.value, item.name) for item in files] == [
        ("project", "SOUL.md"),
        ("project", "USER.md"),
    ]
    assert files[0].label == "project-brain/SOUL.md"


def test_collect_standard_brain_files_orders_stack_from_global_to_project(
    tmp_path: Path,
) -> None:
    from src.lib.brain_context import ActiveBrainContext
    from src.lib.brain_projection import collect_standard_brain_files
    from src.lib.brain_stack import BrainStack, resolve_global_brain

    core = tmp_path / "core"
    core.mkdir()
    (core / "SOUL.md").write_text("# Global Soul\n", encoding="utf-8")
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "SOUL.md").write_text("# User Soul\n", encoding="utf-8")
    project = tmp_path / "repo"
    project_brain = project / "project-brain"
    project_brain.mkdir(parents=True)
    (project_brain / "SOUL.md").write_text("# Project Soul\n", encoding="utf-8")

    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=core),
        user_brain=_brain("personal", BrainType.PERSONAL, vault),
        project=ActiveBrainContext(
            active_brain=_brain(
                "project-repo",
                BrainType.PROJECT,
                project_brain,
                project,
            ),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )

    files = collect_standard_brain_files(stack, project_root=project)

    assert [(item.tier.value, item.name, item.brain_id) for item in files] == [
        ("global", "SOUL.md", "augur-core"),
        ("personal", "SOUL.md", "personal"),
        ("project", "SOUL.md", "project-repo"),
    ]


def test_collect_standard_brain_files_dedupes_coincident_global_project_root(
    tmp_path: Path,
) -> None:
    from src.lib.brain_context import ActiveBrainContext
    from src.lib.brain_projection import collect_standard_brain_files
    from src.lib.brain_stack import BrainStack, resolve_global_brain

    project = tmp_path / "repo"
    project_brain = project / "project-brain"
    project_brain.mkdir(parents=True)
    (project_brain / "SOUL.md").write_text("# Shared Soul\n", encoding="utf-8")

    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=project_brain),
        user_brain=None,
        project=ActiveBrainContext(
            active_brain=_brain(
                "project-repo",
                BrainType.PROJECT,
                project_brain,
                project,
            ),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )

    files = collect_standard_brain_files(stack, project_root=project)

    assert [(item.tier.value, item.name, item.brain_id) for item in files] == [
        ("global", "SOUL.md", "augur-core"),
    ]


def test_render_standard_brain_files_context_renders_pointers_and_labels_tiers(
    tmp_path: Path,
) -> None:
    from src.lib.brain_context import ActiveBrainContext
    from src.lib.brain_projection import render_standard_brain_files_context
    from src.lib.brain_stack import BrainStack, resolve_global_brain

    project = tmp_path / "repo"
    project_brain = project / "project-brain"
    project_brain.mkdir(parents=True)
    (project_brain / "SOUL.md").write_text(
        "---\ntitle: Project Soul\n---\n\n# Project Soul\n\nProject values.\n",
        encoding="utf-8",
    )

    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=tmp_path / "core"),
        user_brain=None,
        project=ActiveBrainContext(
            active_brain=_brain(
                "project-repo",
                BrainType.PROJECT,
                project_brain,
                project,
            ),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )

    rendered = render_standard_brain_files_context(stack, project_root=project)

    # Pointer-only projection: tier-labelled source pointer, no embedded body.
    assert "## Standard Brain Files" in rendered
    assert "- Project / SOUL.md — `project-brain/SOUL.md`" in rendered
    assert "Project values." not in rendered
    assert "title: Project Soul" not in rendered


def test_render_standard_brain_files_context_respects_max_bytes(
    tmp_path: Path,
) -> None:
    from src.lib.brain_context import ActiveBrainContext
    from src.lib.brain_projection import render_standard_brain_files_context
    from src.lib.brain_stack import BrainStack, resolve_global_brain

    project = tmp_path / "repo"
    project_brain = project / "project-brain"
    project_brain.mkdir(parents=True)
    (project_brain / "SOUL.md").write_text(
        "---\ntitle: Project Soul\n---\n\n# Project Soul\n\nProject values.\n",
        encoding="utf-8",
    )

    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=tmp_path / "core"),
        user_brain=None,
        project=ActiveBrainContext(
            active_brain=_brain(
                "project-repo",
                BrainType.PROJECT,
                project_brain,
                project,
            ),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )

    full = render_standard_brain_files_context(stack, project_root=project, max_bytes=10_000)
    assert "- Project / SOUL.md — `project-brain/SOUL.md`" in full

    # A budget too small for the pointer drops it and keeps output within budget.
    budget = len(full.encode("utf-8")) - 1
    rendered = render_standard_brain_files_context(
        stack,
        project_root=project,
        max_bytes=budget,
    )

    assert len(rendered.encode("utf-8")) <= budget
    assert "- Project / SOUL.md" not in rendered


def test_render_standard_brain_files_context_caps_pointer_list(
    tmp_path: Path,
) -> None:
    from src.lib.brain_context import ActiveBrainContext
    from src.lib.brain_projection import render_standard_brain_files_context
    from src.lib.brain_stack import BrainStack, resolve_global_brain

    core = tmp_path / "core"
    core.mkdir()
    (core / "SOUL.md").write_text("# Global Soul\n\nGlobal values.\n", encoding="utf-8")
    project = tmp_path / "repo"
    project_brain = project / "project-brain"
    project_brain.mkdir(parents=True)
    (project_brain / "SOUL.md").write_text("# Project Soul\n\nProject values.\n", encoding="utf-8")

    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=core),
        user_brain=None,
        project=ActiveBrainContext(
            active_brain=_brain(
                "project-repo",
                BrainType.PROJECT,
                project_brain,
                project,
            ),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )

    full = render_standard_brain_files_context(stack, project_root=project, max_bytes=10_000)
    assert full.count("\n- ") == 2  # both tiers render a pointer

    # A budget one byte short of the full list drops the last pointer.
    budget = len(full.encode("utf-8")) - 1
    rendered = render_standard_brain_files_context(
        stack,
        project_root=project,
        max_bytes=budget,
    )

    assert len(rendered.encode("utf-8")) <= budget
    assert rendered.count("\n- ") < full.count("\n- ")
