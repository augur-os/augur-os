"""Page scoring and registry persistence."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DIMENSION_WEIGHTS: dict[str, float] = {
    "accessibility": 0.30,
    "interaction": 0.25,
    "design_system": 0.25,
    "responsiveness": 0.20,
}


def compute_page_score(dimension_scores: dict[str, float]) -> float:
    """Compute weighted page score from dimension scores.

    Only dimensions present in dimension_scores contribute.
    Missing dimensions are excluded and weights renormalized.
    """
    total_weight = 0.0
    weighted_sum = 0.0
    for dim, score in dimension_scores.items():
        weight = _DIMENSION_WEIGHTS.get(dim, 0.0)
        if weight > 0:
            total_weight += weight
            weighted_sum += score * weight
    if total_weight == 0:
        return 0.0
    return weighted_sum / total_weight


def load_registry(registry_path: Path) -> dict[str, Any]:
    """Load page score registry from JSON file."""
    if not registry_path.exists():
        return {}
    try:
        return json.loads(registry_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_registry(registry: dict[str, Any], registry_path: Path) -> None:
    """Save page score registry to JSON file."""
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2))


def priority_sort(pages: dict[str, dict]) -> list[str]:
    """Sort page keys by priority: never audited first, then lowest score.

    Tie-breaking: oldest last_audit > most issues.
    """
    def sort_key(page_key: str) -> tuple:
        entry = pages[page_key]
        never_audited = entry.get("last_audit") is None
        score = entry.get("score", 0)
        last_audit = entry.get("last_audit") or "0000-00-00"
        return (
            0 if never_audited else 1,  # never audited first
            score,                       # lowest score next
            last_audit,                  # oldest audit next
        )
    return sorted(pages.keys(), key=sort_key)
