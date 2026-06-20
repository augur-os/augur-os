"""Memory review MCP tools (ADR-772, Task 5).

The reviewed promotion path into canonical brain memory. Client-native memory is
*input*: ``memory-review-queue`` surfaces un-promoted client summaries plus
agent-submitted observations as candidates; ``memory-review-approve`` writes one
approved candidate into the active brain's canonical ``memory/entries`` (via the
ADR-771 write-destination resolver); ``memory-review-reject`` records a rejection
so it never resurfaces; ``memory-review-submit`` stages an agent-curated fact.

Like ``brain-discovery``, the heavy lifting lives in the pure core engine
(:mod:`src.lib.memory_review`). These thin wrappers inject the client-native
candidates — which require the skill-tree ``memory_assembler`` to discover —
so the core engine stays free of skill-tree imports.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _candidate_project_roots() -> list[Path]:
    """Project roots whose client memory dirs we scan for candidates.

    Client-native memory is keyed to the repo path the client ran in. In a
    worktree the live client memory is encoded under the *main* checkout path,
    so include both the current project root and the worktree's ``main_repo``.
    """
    roots: list[Path] = []
    try:
        from src.config.paths import get_project_root

        roots.append(get_project_root())
    except Exception:
        pass

    # Worktree marker points at the main checkout, where client memory lives.
    for base in list(roots) or [Path.cwd()]:
        marker = base / ".augur-worktree.yaml"
        if not marker.is_file():
            continue
        try:
            import yaml

            data = yaml.safe_load(marker.read_text(encoding="utf-8")) or {}
            main_repo = data.get("main_repo")
            if main_repo:
                roots.append(Path(str(main_repo)))
        except Exception:
            continue

    # De-dupe while preserving order.
    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        key = str(root.resolve()) if root.exists() else str(root)
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def _import_assembler():
    """Best-effort import of the memory assembler discovery API (skills tree).

    Resolves the skills tree via ``get_skills_dir()`` so it follows the ADR-770
    project-brain migration (``project-brain/capabilities/skills``) without
    hardcoding a path.
    """
    try:
        import sys

        from src.config.paths import get_skills_dir

        ops_dir = get_skills_dir() / "ai" / "scripts" / "ops"
        if ops_dir.is_dir() and str(ops_dir) not in sys.path:
            sys.path.insert(0, str(ops_dir))
        import memory_assembler  # type: ignore[import-not-found]

        return memory_assembler
    except Exception:
        return None


def _collect_client_candidates() -> list[Any]:
    """Discover client-native memory summaries as review candidates.

    Returns a list of :class:`src.lib.memory_review.Candidate` via the assembler's
    shared collector, scanning both the current project root and (in a worktree)
    the main checkout where client memory is actually keyed.
    """
    assembler = _import_assembler()
    if assembler is None:
        return []
    try:
        return assembler.collect_review_candidates(_candidate_project_roots())
    except Exception:
        return []


def _resolve_target(brain: str | None):
    from src.lib.memory_review import resolve_target

    return resolve_target(explicit_brain=brain or None, cwd=Path.cwd())


async def memory_review_queue_impl(
    brain: str | None = None,
    include_resolved: bool = False,
) -> str:
    """Return the review queue for the active (or named) brain as JSON."""
    from src.lib.memory_review import build_queue

    try:
        target = _resolve_target(brain)
    except KeyError as exc:
        return json.dumps({"success": False, "error": str(exc)})

    client_candidates = _collect_client_candidates()
    snapshot = build_queue(
        target=target,
        client_candidates=client_candidates,
        include_resolved=include_resolved,
    )
    return json.dumps(snapshot, indent=2, default=str)


def _find_candidate(target, candidate_id: str):
    """Locate a candidate by id among submitted + live client candidates."""
    from src.lib.memory_review import MemoryReviewStore

    store = MemoryReviewStore(target.brain.id)
    for cand in store.list_submitted():
        if cand.id == candidate_id:
            return cand, store
    for cand in _collect_client_candidates():
        if cand.id == candidate_id:
            return cand, store
    return None, store


async def memory_review_approve_impl(candidate_id: str, brain: str | None = None) -> str:
    """Approve one candidate → write it as a canonical brain memory entry."""
    from src.lib.memory_review import approve

    if not candidate_id:
        return json.dumps({"success": False, "error": "candidate_id is required"})
    try:
        target = _resolve_target(brain)
    except KeyError as exc:
        return json.dumps({"success": False, "error": str(exc)})

    candidate, store = _find_candidate(target, candidate_id)
    if candidate is None:
        return json.dumps({"success": False, "error": f"candidate not found: {candidate_id}"})
    result = approve(target=target, candidate=candidate, store=store)
    if result.get("success"):
        # Keep the brain's human-readable MEMORY.md index in lockstep with the
        # entries dir (ADR-772). Best-effort: a reindex failure never fails the
        # approve — the canonical entry is already written.
        _reindex_brain_memory(target)
    return json.dumps(result, indent=2, default=str)


def _reindex_brain_memory(target) -> None:
    assembler = _import_assembler()
    if assembler is None:
        return
    try:
        assembler.reindex_brain_memory(target.memory_dir)
    except Exception:
        pass


async def memory_review_reject_impl(
    candidate_id: str,
    reason: str = "",
    brain: str | None = None,
) -> str:
    """Reject one candidate so it never resurfaces in the queue."""
    from src.lib.memory_review import reject

    if not candidate_id:
        return json.dumps({"success": False, "error": "candidate_id is required"})
    try:
        target = _resolve_target(brain)
    except KeyError as exc:
        return json.dumps({"success": False, "error": str(exc)})

    candidate, store = _find_candidate(target, candidate_id)
    name = candidate.name if candidate is not None else ""
    result = reject(
        target=target,
        candidate_id=candidate_id,
        store=store,
        reason=reason,
        name=name,
    )
    return json.dumps(result, indent=2, default=str)


async def memory_review_submit_impl(
    name: str,
    description: str = "",
    body: str = "",
    kind: str = "insight",
    brain: str | None = None,
) -> str:
    """Stage an agent-curated observation as a pending review candidate."""
    from src.lib.memory_review import submit

    try:
        target = _resolve_target(brain)
    except KeyError as exc:
        return json.dumps({"success": False, "error": str(exc)})

    result = submit(
        target=target,
        name=name,
        description=description,
        body=body,
        kind=kind,
    )
    return json.dumps(result, indent=2, default=str)
