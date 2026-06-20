"""Tier table, weight resolution, and filter logic for wiki signal priority."""
from __future__ import annotations

from typing import Any


_TIER_BY_SURFACE: dict[str, str] = {
    "save_events": "critical",
    "ask_outcomes": "critical",
    "client_memory": "critical",
    "memory_files": "critical",
    "episodic": "critical",
    "codex_threads": "critical",
    "vault": "high",
    "gemini": "high",
    "copilot": "high",
    "external_client": "high",
    "documents": "medium",
    "skills": "medium",
    "repo_docs": "medium",
    "project_deltas": "medium",
    "adr_targets": "medium",
    "git_history": "low",
    "runtime_memory": "low",
    "logs": "noise",
}

_WEIGHT_BY_TIER: dict[str, float] = {
    "critical": 3.0,
    "high": 2.0,
    "medium": 1.0,
    "low": 0.4,
    "noise": 0.0,
}

_TIER_RANK: dict[str, int] = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    "noise": 0,
}

ALL_TIERS = ("critical", "high", "medium", "low", "noise")


def normalize_tier(value: Any, *, default: str = "medium") -> str:
    """Return a recognized tier string, falling back to default."""
    tier = str(value or "").strip().lower()
    if tier in _WEIGHT_BY_TIER:
        return tier
    return default


def tier_for_surface(surface: str) -> str:
    """Return the default tier for a source surface; unknown surfaces are medium."""
    return _TIER_BY_SURFACE.get(str(surface or "").strip(), "medium")


def weight_for_tier(tier: str) -> float:
    """Return the extraction weight for a tier; unknown tiers use medium weight."""
    return _WEIGHT_BY_TIER.get(normalize_tier(tier), _WEIGHT_BY_TIER["medium"])


def rank_for_tier(tier: str) -> int:
    """Return an ordering rank where higher means stronger signal."""
    return _TIER_RANK.get(normalize_tier(tier), _TIER_RANK["medium"])


def tier_meets_filter(source_tier: str, filter_tier: str) -> bool:
    """Return True when source_tier passes filter_tier.

    Empty filter means every tier except noise. A specific filter includes that
    tier and all stronger tiers.
    """
    source_tier = normalize_tier(source_tier)
    filter_tier = normalize_tier(filter_tier, default="") if filter_tier else ""
    if not filter_tier:
        return source_tier != "noise"
    return rank_for_tier(source_tier) >= rank_for_tier(filter_tier)
