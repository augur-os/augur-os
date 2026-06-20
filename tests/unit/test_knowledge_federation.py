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


def _stack(tmp_path: Path) -> BrainStack:
    project_repo = tmp_path / "repo"
    project_brain = project_repo / "project-brain"
    return BrainStack(
        global_brain=_brain(
            "augur-core",
            BrainType.GLOBAL,
            tmp_path / "global",
            write_policy="read_only",
        ),
        user_brain=_brain("personal", BrainType.PERSONAL, tmp_path / "user"),
        project=ActiveBrainContext(
            active_brain=_brain(
                "project-repo",
                BrainType.PROJECT,
                project_brain,
                attached_project=project_repo,
            ),
            attached_project=project_repo,
            source="test",
        ),
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_unified_search_federates_knowledge_tiers_with_source_brain(
    tmp_path: Path,
) -> None:
    from src.lib.knowledge.unified_search import UnifiedSearcher

    stack = _stack(tmp_path)
    for brain in stack.ordered():
        root = Path(brain.data_root)
        knowledge_dir = root / "knowledge"
        _write(
            knowledge_dir / "notes" / f"{brain.id}.md",
            f"{brain.id} carries adr784-federated-signal in {brain.type.value}",
        )
        _write(
            knowledge_dir / "index" / f"{brain.id}-index.md",
            f"{brain.id} index carries adr784-index-signal",
        )

    searcher = UnifiedSearcher(scopes=["knowledge"], stack=stack)

    results = searcher.search("adr784-federated-signal", scopes=["knowledge"], top_k=10)

    assert {result["source_brain"] for result in results} == {
        "augur-core",
        "personal",
        "project-repo",
    }
    assert {result["brain_id"] for result in results} == {
        "augur-core",
        "personal",
        "project-repo",
    }
    assert {result["source_brain_tier"] for result in results} == {
        "global",
        "personal",
        "project",
    }

    index_results = searcher.search("adr784-index-signal", scopes=["knowledge"], top_k=10)
    assert {result["source_brain"] for result in index_results} == {
        "augur-core",
        "personal",
        "project-repo",
    }


def test_unified_search_dedupes_coincident_roots_to_most_specific_brain(
    tmp_path: Path,
) -> None:
    from src.lib.knowledge.unified_search import UnifiedSearcher

    project_repo = tmp_path / "repo"
    shared_brain_root = project_repo / "project-brain"
    stack = BrainStack(
        global_brain=_brain(
            "augur-core",
            BrainType.GLOBAL,
            shared_brain_root,
            write_policy="read_only",
        ),
        user_brain=None,
        project=ActiveBrainContext(
            active_brain=_brain(
                "project-repo",
                BrainType.PROJECT,
                shared_brain_root,
                attached_project=project_repo,
            ),
            attached_project=project_repo,
            source="test",
        ),
    )
    _write(
        shared_brain_root / "knowledge" / "notes" / "shared.md",
        "shared root carries adr784-coincident-root-signal",
    )

    results = UnifiedSearcher(scopes=["knowledge"], stack=stack).search(
        "adr784-coincident-root-signal",
        scopes=["knowledge"],
        top_k=10,
    )

    assert len(results) == 1
    assert results[0]["source_brain"] == "project-repo"
    assert results[0]["source_brain_tier"] == "project"
