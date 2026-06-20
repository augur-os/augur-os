"""Per-tier cap application for wiki-update batches."""
from __future__ import annotations

from typing import Any


def _source_tier(source: Any) -> str:
    if isinstance(source, dict):
        return str(source.get("tier") or "medium")
    metadata = getattr(source, "metadata", {}) or {}
    if isinstance(metadata, dict):
        return str(metadata.get("tier") or "medium")
    return "medium"


def apply_tier_caps(sources: list[Any], caps: dict[str, int]) -> list[Any]:
    """Keep up to caps[tier] sources from each tier, preserving input order."""
    counts: dict[str, int] = {}
    out: list[Any] = []
    for source in sources:
        tier = _source_tier(source)
        cap = int(caps.get(tier, 10**9))
        used = counts.get(tier, 0)
        if used >= cap:
            continue
        counts[tier] = used + 1
        out.append(source)
    return out
