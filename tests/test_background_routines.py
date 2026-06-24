"""Auto-generated importability test for background_routines."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_background_routines_importable():
    """Verify that background_routines can be imported without errors."""
    import src.mcp.augur_framework.tools.infrastructure.browse.background_routines

    assert src.mcp.augur_framework.tools.infrastructure.browse.background_routines is not None


def test_declared_routine_deduped_against_scheduling_prompt():
    """A declared routine that a schedule actually runs is the same routine twice.

    The codex/claude schedule (richer: real cadence + drift) invokes the declared
    routine via `/a-loops run <id>`, so the declared twin is dropped (ADR-813).
    """
    from src.mcp.augur_framework.tools.infrastructure.browse.background_routines import (
        dedupe_routine_items_against_schedules,
    )

    routine_items = [
        {"id": "code-quality", "metadata": {"source_kind": "declared-routine"}},
        {"id": "self-heal", "metadata": {"source_kind": "declared-routine"}},
        # A non-declared routine is never dropped, even on an id collision.
        {"id": "dream", "metadata": {"source_kind": "daemon-service"}},
    ]
    scheduled_items = [
        {"id": "codex:codex-dev-loop-code-quality", "description": "/a-loops run code-quality"},
        {"id": "codex:codex-dream-nightly", "description": "/a-loops run dream"},
        # Free-form prompt invokes no declared routine.
        {"id": "claude:weekly-disk-cleanup-report", "description": "Keep the report tight."},
    ]

    kept = dedupe_routine_items_against_schedules(routine_items, scheduled_items)
    kept_ids = [item["id"] for item in kept]

    assert "code-quality" not in kept_ids  # scheduled in codex -> declared twin dropped
    assert "self-heal" in kept_ids  # no schedule runs it -> kept
    assert "dream" in kept_ids  # daemon-service, not a declared twin -> kept
