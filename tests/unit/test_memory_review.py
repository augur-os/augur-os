"""Tests for the memory review product core engine (ADR-772, Task 5).

Covers candidate identity, queue classification (pending/promoted/rejected),
approve (writes a canonical entry through the ADR-771 write-destination
resolver), reject + submit persistence, packet-mode refusal, and the personal
vs project memory_dir routing.
"""

from __future__ import annotations

from pathlib import Path

from src.lib import memory_review as mr
from src.lib.brain_manifest import (
    BrainManifest,
    ensure_brain_skeleton,
    write_brain_manifest,
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
from src.lib.brain_write_routing import resolve_write_target


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


def _registry(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
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
    clear_cache()
    save_registry(
        BrainRegistry(
            version=1,
            brains={
                "personal": _brain("personal", BrainType.PERSONAL, personal_root),
                "project-repo": _brain("project-repo", BrainType.PROJECT, project_brain, project=project),
                "team-core": _brain("team-core", BrainType.TEAM, team_root, write_policy="packets_only"),
            },
        ),
        registry_path,
    )
    return registry_path, personal_root, project, team_root


# --------------------------------------------------------------------------- #
# Candidate identity
# --------------------------------------------------------------------------- #


def test_fingerprint_is_stable_and_content_sensitive() -> None:
    a = mr.candidate_fingerprint("claude-code", "Name", "Desc")
    b = mr.candidate_fingerprint("claude-code", "Name", "Desc")
    c = mr.candidate_fingerprint("claude-code", "Name", "Different")
    assert a == b
    assert a != c
    assert a.startswith("mc_")


def test_make_candidate_derives_filename_and_normalizes_kind() -> None:
    cand = mr.make_candidate(
        client="claude-code",
        name="Prefer concise commits",
        description="x",
        body="b",
        kind="bogus-kind",
    )
    assert cand.target_filename == "claude-code_prefer_concise_commits.md"
    assert cand.kind == "insight"  # unknown kind falls back


# --------------------------------------------------------------------------- #
# Queue classification
# --------------------------------------------------------------------------- #


def test_build_queue_classifies_pending_promoted_rejected(tmp_path: Path) -> None:
    registry_path, personal_root, _project, _team = _registry(tmp_path)
    target = resolve_write_target(explicit_brain="personal", registry_path=registry_path)
    store = mr.MemoryReviewStore("personal", root=tmp_path / "runtime")

    # An entry already on disk -> a candidate with the same filename is "promoted".
    entries_dir = target.memory_dir / "entries"
    entries_dir.mkdir(parents=True, exist_ok=True)
    (entries_dir / "claude-code_existing.md").write_text(
        "---\nname: Existing\ndescription: d\ntype: feedback\n---\nbody\n",
        encoding="utf-8",
    )
    promoted = mr.make_candidate(
        client="claude-code",
        name="Existing",
        description="d",
        body="b",
        target_filename="claude-code_existing.md",
    )
    pending = mr.make_candidate(
        client="claude-code",
        name="Fresh fact",
        description="new",
        body="b",
    )
    rejected = mr.make_candidate(
        client="claude-code",
        name="Bad fact",
        description="noise",
        body="b",
    )
    store.add_rejected(rejected.id, name="Bad fact")

    snap = mr.build_queue(
        target=target,
        client_candidates=[promoted, pending, rejected],
        store=store,
        include_resolved=True,
    )
    assert snap["counts"] == {"pending": 1, "promoted": 1, "rejected": 1}
    assert [c["name"] for c in snap["pending"]] == ["Fresh fact"]
    assert snap["writable"] is True


def test_promoted_detection_matches_by_frontmatter_fingerprint(tmp_path: Path) -> None:
    """A legacy entry whose filename differs still counts as promoted by fingerprint."""
    registry_path, _personal, _project, _team = _registry(tmp_path)
    target = resolve_write_target(explicit_brain="personal", registry_path=registry_path)
    store = mr.MemoryReviewStore("personal", root=tmp_path / "runtime")

    entries_dir = target.memory_dir / "entries"
    entries_dir.mkdir(parents=True, exist_ok=True)
    (entries_dir / "claude-code_renamed.md").write_text(
        "---\nname: Same Name\ndescription: same desc\ntype: feedback\n---\nbody\n",
        encoding="utf-8",
    )
    # Different target filename, same client/name/description -> same fingerprint.
    cand = mr.make_candidate(
        client="claude-code",
        name="Same Name",
        description="same desc",
        body="b",
        target_filename="claude-code_other.md",
    )
    snap = mr.build_queue(target=target, client_candidates=[cand], store=store)
    assert snap["counts"]["promoted"] == 1
    assert snap["counts"]["pending"] == 0


# --------------------------------------------------------------------------- #
# Approve / reject / submit
# --------------------------------------------------------------------------- #


def test_approve_writes_entry_to_personal_memory_dir(tmp_path: Path) -> None:
    registry_path, personal_root, _project, _team = _registry(tmp_path)
    target = resolve_write_target(explicit_brain="personal", registry_path=registry_path)
    store = mr.MemoryReviewStore("personal", root=tmp_path / "runtime")

    cand = mr.make_candidate(
        client="claude-code",
        name="Promote me",
        description="a durable fact",
        body="the body text",
        kind="feedback",
    )
    result = mr.approve(target=target, candidate=cand, store=store)
    assert result["success"] is True

    written = personal_root / "knowledge" / "memory" / "entries" / cand.target_filename
    assert written.is_file()
    text = written.read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "name: Promote me" in text
    assert "type: feedback" in text
    assert "PROMOTED via memory review from claude-code" in text
    assert "the body text" in text
    # Now it shows as promoted (not pending).
    snap = mr.build_queue(target=target, client_candidates=[cand], store=store)
    assert snap["counts"]["promoted"] == 1


def test_write_entry_records_client_source_provenance(tmp_path: Path) -> None:
    from src.lib.frontmatter_utils import parse_frontmatter

    registry_path, _personal_root, _project, _team = _registry(tmp_path)
    target = resolve_write_target(explicit_brain="personal", registry_path=registry_path)
    candidate = mr.make_candidate(
        client="codex",
        source="client:codex",
        name="Cross-client fact",
        description="A reviewed Codex memory fact",
        body="Remembered by Codex.",
        created="2026-05-25T12:00:00Z",
        target_filename="codex_cross_client_fact.md",
    )

    path = mr.write_entry(target=target, candidate=candidate)

    meta, body = parse_frontmatter(path, include_sidecar_config=False)
    assert meta["source"] == "client:codex"
    assert meta["source_client"] == "codex"
    assert meta["source_created_at"] == "2026-05-25T12:00:00Z"
    assert "PROMOTED via memory review from codex" in body


def test_approve_routes_project_brain_to_knowledge_memory(tmp_path: Path) -> None:
    registry_path, _personal, project, _team = _registry(tmp_path)
    target = resolve_write_target(cwd=project / "src", registry_path=registry_path)
    assert target.brain.id == "project-repo"
    store = mr.MemoryReviewStore(target.brain.id, root=tmp_path / "runtime")

    cand = mr.make_candidate(client="agent", name="Project fact", description="d", body="b")
    result = mr.approve(target=target, candidate=cand, store=store)
    assert result["success"] is True
    expected = project / "project-brain" / "knowledge" / "memory" / "entries" / cand.target_filename
    assert expected.is_file()


def test_packet_brain_refuses_direct_approve(tmp_path: Path) -> None:
    registry_path, _personal, _project, _team = _registry(tmp_path)
    target = resolve_write_target(explicit_brain="team-core", registry_path=registry_path)
    store = mr.MemoryReviewStore("team-core", root=tmp_path / "runtime")
    cand = mr.make_candidate(client="agent", name="Team fact", description="d", body="b")

    result = mr.approve(target=target, candidate=cand, store=store)
    assert result["success"] is False
    assert "packet" in result["error"].lower()
    # Nothing written.
    assert not (target.memory_dir / "entries" / cand.target_filename).exists()


def test_submit_then_appears_pending_then_reject_removes(tmp_path: Path) -> None:
    registry_path, _personal, _project, _team = _registry(tmp_path)
    target = resolve_write_target(explicit_brain="personal", registry_path=registry_path)
    store = mr.MemoryReviewStore("personal", root=tmp_path / "runtime")

    sub = mr.submit(
        target=target,
        name="Agent observation",
        description="seen in session",
        body="details",
        store=store,
    )
    assert sub["success"] is True
    cid = sub["submitted"]

    snap = mr.build_queue(target=target, client_candidates=[], store=store)
    assert snap["counts"]["pending"] == 1
    assert snap["pending"][0]["id"] == cid

    mr.reject(target=target, candidate_id=cid, store=store, name="Agent observation")
    snap2 = mr.build_queue(target=target, client_candidates=[], store=store, include_resolved=True)
    assert snap2["counts"]["pending"] == 0
    assert snap2["counts"]["rejected"] == 1


def test_submit_requires_name(tmp_path: Path) -> None:
    registry_path, _personal, _project, _team = _registry(tmp_path)
    target = resolve_write_target(explicit_brain="personal", registry_path=registry_path)
    store = mr.MemoryReviewStore("personal", root=tmp_path / "runtime")
    result = mr.submit(target=target, name="  ", description="d", body="b", store=store)
    assert result["success"] is False


def test_approve_clears_submission_and_rejection(tmp_path: Path) -> None:
    registry_path, _personal, _project, _team = _registry(tmp_path)
    target = resolve_write_target(explicit_brain="personal", registry_path=registry_path)
    store = mr.MemoryReviewStore("personal", root=tmp_path / "runtime")

    mr.submit(target=target, name="X", description="d", body="b", store=store)
    cand = store.list_submitted()[0]
    mr.approve(target=target, candidate=cand, store=store)
    assert store.list_submitted() == []
    assert not store.is_rejected(cand.id)


def test_clear_registry_cache_after_test() -> None:
    clear_cache()
