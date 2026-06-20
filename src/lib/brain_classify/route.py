"""Deterministic write-time brain routing from a page's/entry's sources."""

from __future__ import annotations

from src.lib.brain_classify.evidence import _classify_token


def target_brain_for_sources(sources: list[str]) -> str:
    """Return 'project' or 'personal' from referenced-artifact tallies.

    Privacy-safe default: personal (never auto-route ambiguous content into the
    publicly-tracked project repo).
    """
    project = personal = 0
    for s in sources:
        verdict = _classify_token(s)
        if verdict == "project":
            project += 1
        elif verdict == "personal":
            personal += 1
    if project > personal:
        return "project"
    return "personal"
