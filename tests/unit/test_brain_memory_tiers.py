from __future__ import annotations

from pathlib import Path

from src.lib.brain_context import ActiveBrainContext
from src.lib.brain_registry_models import Brain, BrainType, GitArrangement, GitConfig
from src.lib.brain_stack import BrainStack


def _brain(
    brain_id: str,
    brain_type: BrainType,
    root: Path,
    *,
    write_policy: str = "free",
    attached_project: Path | None = None,
) -> Brain:
    return Brain(
        id=brain_id,
        type=brain_type,
        data_root=root,
        git=(
            GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=attached_project)
            if brain_type is BrainType.PROJECT and attached_project is not None
            else GitConfig(arrangement=GitArrangement.UNTRACKED)
        ),
        write_policy=write_policy,
        auto_activate_cwd_under=(attached_project,) if attached_project is not None else (),
    )


def _stack(
    tmp_path: Path,
    *,
    include_project: bool = True,
) -> tuple[BrainStack, Path, Path, Path]:
    global_root = tmp_path / "global"
    user_root = tmp_path / "user"
    project_repo = tmp_path / "repo"
    project_root = project_repo / "project-brain"
    global_brain = _brain(
        "augur-core",
        BrainType.GLOBAL,
        global_root,
        write_policy="read_only",
    )
    user_brain = _brain("personal", BrainType.PERSONAL, user_root)
    project = None
    if include_project:
        project_brain = _brain(
            "project-repo",
            BrainType.PROJECT,
            project_root,
            attached_project=project_repo,
        )
        project = ActiveBrainContext(
            active_brain=project_brain,
            attached_project=project_repo,
            source="test",
        )
    return (
        BrainStack(global_brain=global_brain, user_brain=user_brain, project=project),
        global_root / "memory",
        user_root / "memory",
        project_root / "knowledge" / "memory",
    )


def _write_entry(
    memory_dir: Path,
    filename: str,
    *,
    name: str,
    description: str,
    body: str,
) -> None:
    entries_dir = memory_dir / "entries"
    entries_dir.mkdir(parents=True, exist_ok=True)
    (entries_dir / filename).write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                f"description: {description}",
                "type: preference",
                "---",
                "",
                body,
            ]
        ),
        encoding="utf-8",
    )


def test_read_memory_union_and_write_target(tmp_path: Path) -> None:
    from src.lib.brain_memory_tiers import (
        read_memory_union,
        resolve_memory_write_target,
        tier_memory_dirs,
    )

    stack, global_memory, user_memory, project_memory = _stack(tmp_path)
    _write_entry(global_memory, "global-only.md", name="global-only", description="global", body="G")
    _write_entry(user_memory, "shared.md", name="shared-key", description="user", body="U")
    _write_entry(project_memory, "shared.md", name="shared-key", description="project", body="P")

    assert tier_memory_dirs(stack) == (global_memory, user_memory, project_memory)

    union = read_memory_union(stack)

    assert union["global-only"].tier is BrainType.GLOBAL
    assert union["shared-key"].tier is BrainType.PROJECT
    assert union["shared-key"].description == "project"
    assert resolve_memory_write_target(stack) == project_memory

    no_project, _global_memory, no_project_user, _project_memory = _stack(
        tmp_path / "no-project",
        include_project=False,
    )
    assert resolve_memory_write_target(no_project) == no_project_user

    global_only = BrainStack(
        global_brain=no_project.global_brain,
        user_brain=None,
        project=None,
    )
    assert resolve_memory_write_target(global_only) is None


def test_memory_store_reads_union_and_writes_to_most_specific_tier(tmp_path: Path) -> None:
    from src.lib.knowledge.memory_store import MemoryStore

    stack, global_memory, user_memory, project_memory = _stack(tmp_path)
    _write_entry(global_memory, "global-only.md", name="global-only", description="global", body="G")
    _write_entry(user_memory, "shared.md", name="shared-key", description="user", body="U")
    _write_entry(project_memory, "shared.md", name="shared-key", description="project", body="P")

    store = MemoryStore(stack=stack)

    content = store.get_memory_content()
    assert "global-only" in content
    assert "project" in content
    assert "user" not in content

    store.add_preference("Communication", "tone", "direct")

    assert (project_memory / "MEMORY.md").is_file()
    assert "tone" in (project_memory / "MEMORY.md").read_text(encoding="utf-8")


def test_render_memory_handoff_is_compact_and_project_wins(tmp_path: Path) -> None:
    from src.lib.brain_memory_tiers import render_memory_handoff_markdown

    stack, global_memory, user_memory, project_memory = _stack(tmp_path)
    _write_entry(global_memory, "global.md", name="global-context", description="global context", body="G")
    _write_entry(user_memory, "shared.md", name="shared-key", description="from user", body="U")
    _write_entry(project_memory, "shared.md", name="shared-key", description="from project", body="P")

    handoff = render_memory_handoff_markdown(stack, max_entries=3, max_bytes=900)

    assert "# Augur Cross-Client Handoff" in handoff
    assert "Full recall is pull-based" in handoff
    assert "from project" in handoff
    assert "from user" not in handoff
    assert "tier=project" in handoff
    assert len(handoff.encode("utf-8")) <= 900


def test_render_memory_handoff_respects_entry_limit(tmp_path: Path) -> None:
    from src.lib.brain_memory_tiers import render_memory_handoff_markdown

    stack, _global_memory, _user_memory, project_memory = _stack(tmp_path)
    _write_entry(project_memory, "first.md", name="first-key", description="first", body="first")
    _write_entry(project_memory, "second.md", name="second-key", description="second", body="second")

    handoff = render_memory_handoff_markdown(stack, max_entries=1, max_bytes=900)

    assert handoff.count("- **") == 1


def test_personal_memory_dir_ignores_knowledge_dir_in_legacy_layout(tmp_path: Path) -> None:
    """Regression: the PERSONAL tier never uses the knowledge/ subdir.

    The real legacy vault HAS a knowledge/ directory (notes, sources, wiki live
    under it), but its live memory tier is flat root/memory. A
    knowledge-dir-exists probe must not reroute the personal tier to the stale
    knowledge/memory path.
    """
    from src.lib.brain_layout import brain_layout
    from src.lib.brain_memory_tiers import memory_dir_for_brain

    brain_layout.cache_clear()
    try:
        root = tmp_path / "legacy-vault"
        # knowledge/ PRESENT (as on the real vault) — plus stale entries there.
        (root / "knowledge" / "memory" / "entries").mkdir(parents=True)
        (root / "memory" / "entries").mkdir(parents=True)

        personal = _brain("personal", BrainType.PERSONAL, root)
        assert memory_dir_for_brain(personal) == root / "memory"

        # GLOBAL tier with knowledge/ present keeps its knowledge/memory path.
        global_brain = _brain("augur-core", BrainType.GLOBAL, root)
        assert memory_dir_for_brain(global_brain) == root / "knowledge" / "memory"
    finally:
        brain_layout.cache_clear()


def test_personal_memory_dir_in_domains_layout_is_under_machine_dir(tmp_path: Path) -> None:
    """Domains layout: live memory moves to _augur/memory (never knowledge/)."""
    from src.lib.brain_layout import brain_layout
    from src.lib.brain_memory_tiers import memory_dir_for_brain

    brain_layout.cache_clear()
    try:
        root = tmp_path / "domains-vault"
        root.mkdir()
        (root / "BRAIN.yaml").write_text(
            "schema_version: 1\nid: personal\ntype: personal\nlayout: domains\n",
            encoding="utf-8",
        )

        personal = _brain("personal", BrainType.PERSONAL, root)
        assert memory_dir_for_brain(personal) == root / "_augur" / "memory"
    finally:
        brain_layout.cache_clear()
