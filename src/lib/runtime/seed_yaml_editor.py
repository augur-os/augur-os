"""Surgical updates to a single entry in a routine-schedule.yaml seed file.

The editor uses round-trip YAML (load → mutate → dump) and intentionally
accepts the formatting changes PyYAML produces on re-serialization. Seed
files are tracked in git, so cosmetic diff churn on the touched entry is
acceptable; preserving SEMANTICS across other entries is what matters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def update_seed_entry(
    seed_path: Path,
    *,
    schedule_id: str,
    new_fields: dict[str, Any],
) -> bool:
    """Update one schedule entry in a routine-schedule.yaml.

    Returns True if a matching entry was found and rewritten, False otherwise.
    Other entries pass through untouched (semantically; serialization may
    normalize whitespace and quoting).
    """
    raw = yaml.safe_load(seed_path.read_text(encoding="utf-8")) or {}
    schedules = raw.get("schedules") if isinstance(raw, dict) else None
    if not isinstance(schedules, list):
        return False

    target_index = next(
        (
            index
            for index, entry in enumerate(schedules)
            if isinstance(entry, dict) and str(entry.get("id", "")) == schedule_id
        ),
        None,
    )
    if target_index is None:
        return False

    schedules[target_index].update(new_fields)
    seed_path.write_text(
        yaml.safe_dump(raw, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return True
