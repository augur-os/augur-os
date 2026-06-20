"""
Issue registry persistence for AI Self-Healer.

Handles loading, saving, and compacting the self-heal issue registry
stored at RUNTIME_DIR/self_heal_registry.json.

Retention: resolved entries (fixed, abandoned, dismissed, failed) older than
30 minutes are automatically pruned on save.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

# Only keep resolved entries for 30 minutes
REGISTRY_RETENTION_SECONDS = 1800

if TYPE_CHECKING:
    from ai_self_healer import RegistryEntry


def _get_paths():
    """Lazy import of path constants to avoid circular imports."""
    import ai_self_healer as _healer
    return _healer.REGISTRY_FILE, _healer.logger


def load_registry() -> dict[str, "RegistryEntry"]:
    """Load the issue registry from disk."""
    from ai_self_healer import RegistryEntry as RE

    REGISTRY_FILE, logger = _get_paths()
    if not REGISTRY_FILE.exists():
        return {}

    try:
        data = json.loads(REGISTRY_FILE.read_text())
        issues = data.get("issues", {})
        # Inject dedup_key from the dict key so from_dict always has it,
        # even if the serialised entry is missing the field.
        return {k: RE.from_dict({**v, "dedup_key": v.get("dedup_key", k)}) for k, v in issues.items()}
    except Exception as e:
        logger.warning(f"Failed to load registry: {e}")
        return {}


def _prune_stale_entries(
    registry: dict[str, "RegistryEntry"],
) -> dict[str, "RegistryEntry"]:
    """Remove resolved entries older than REGISTRY_RETENTION_SECONDS."""
    resolved_statuses = {"fixed", "abandoned", "dismissed", "failed"}
    cutoff = (datetime.now() - timedelta(seconds=REGISTRY_RETENTION_SECONDS)).isoformat()
    pruned: dict[str, "RegistryEntry"] = {}
    for key, entry in registry.items():
        if entry.status in resolved_statuses and entry.last_seen and entry.last_seen < cutoff:
            continue  # drop stale resolved entry
        pruned[key] = entry
    return pruned


def save_registry(registry: dict[str, "RegistryEntry"]) -> None:
    """Persist registry to disk, pruning resolved entries older than 30 min."""
    REGISTRY_FILE, _ = _get_paths()
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    registry = _prune_stale_entries(registry)
    data = {
        "issues": {k: v.to_dict() for k, v in registry.items()},
        "last_scan": datetime.now().isoformat(),
    }
    REGISTRY_FILE.write_text(json.dumps(data, indent=2))


def compact_dismissed_registry_entries(
    registry: dict[str, "RegistryEntry"],
) -> tuple[dict[str, "RegistryEntry"], int]:
    """Collapse duplicate dismissed entries produced by log rotation.

    Returns (new_registry, compacted_count) where compacted_count is the number
    of entries removed by compaction.
    """
    from ai_self_healer import RegistryEntry as RE
    from self_heal.scanner import _generate_dedup_key

    _, logger = _get_paths()

    if not registry:
        return registry, 0

    compacted: dict[str, "RegistryEntry"] = {}
    dismissed_groups: dict[str, "RegistryEntry"] = {}

    for key, entry in registry.items():
        if entry.status != "dismissed":
            compacted[key] = entry
            continue

        canonical_key = _generate_dedup_key(entry.message, entry.file)
        grouped = dismissed_groups.get(canonical_key)
        if grouped is None:
            clone = RE.from_dict(entry.to_dict())
            clone.dedup_key = canonical_key
            dismissed_groups[canonical_key] = clone
            continue

        grouped.occurrences += max(1, entry.occurrences)
        grouped.fix_attempts = max(grouped.fix_attempts, entry.fix_attempts)
        if entry.first_seen and (not grouped.first_seen or entry.first_seen < grouped.first_seen):
            grouped.first_seen = entry.first_seen
        if entry.last_seen and (not grouped.last_seen or entry.last_seen > grouped.last_seen):
            grouped.last_seen = entry.last_seen

    collisions = 0
    for key, entry in dismissed_groups.items():
        if key in compacted:
            collisions += 1
            alt_key = f"{key}_dismissed"
            entry.dedup_key = alt_key
            compacted[alt_key] = entry
            continue
        compacted[key] = entry

    compacted_count = max(0, len(registry) - len(compacted))
    if collisions:
        logger.warning(f"Dismissed registry compaction key collisions: {collisions}")
    return compacted, compacted_count
