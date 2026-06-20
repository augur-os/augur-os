"""Smoke tests for the src.lib.knowledge public API.

Verifies the migrated memory subsystem is reachable via clean Python imports,
without sys.path tricks. Functional behavior is covered by the existing
skill-side tests in project-brain/capabilities/skills/knowledge/augur/tests/.
"""

from __future__ import annotations


def test_public_api_importable():
    """The 7 documented public symbols are importable from src.lib.knowledge."""
    from src.lib.knowledge import (  # noqa: F401
        DailyLogger,
        EventType,
        MemoryCurator,
        MemoryEntry,
        MemoryEvent,
        MemoryStore,
        UnifiedSearcher,
    )


def test_public_api_origin():
    """Public symbols originate in src.lib.knowledge.* (not the legacy skill path)."""
    from src.lib.knowledge import DailyLogger, MemoryStore, MemoryCurator, UnifiedSearcher

    assert (
        DailyLogger.__module__ == "src.lib.knowledge.daily_logger"
    ), f"DailyLogger should come from src.lib.knowledge.daily_logger; got {DailyLogger.__module__}"
    assert (
        MemoryStore.__module__ == "src.lib.knowledge.memory_store"
    ), f"MemoryStore should come from src.lib.knowledge.memory_store; got {MemoryStore.__module__}"
    assert (
        MemoryCurator.__module__ == "src.lib.knowledge.curator"
    ), f"MemoryCurator should come from src.lib.knowledge.curator; got {MemoryCurator.__module__}"
    assert (
        UnifiedSearcher.__module__ == "src.lib.knowledge.unified_search"
    ), f"UnifiedSearcher should come from src.lib.knowledge.unified_search; got {UnifiedSearcher.__module__}"


def test_submodule_symbols_reachable():
    """Symbols not in __init__.__all__ but used by consumers (via submodule paths) still work."""
    from src.lib.knowledge.search import MemorySearcher  # noqa: F401
    from src.lib.knowledge._types import SearchMode  # noqa: F401


def test_memory_entry_is_dataclass():
    """MemoryEntry is the dataclass consumers expect."""
    from dataclasses import is_dataclass

    from src.lib.knowledge import MemoryEntry

    assert is_dataclass(MemoryEntry), "MemoryEntry should be a dataclass"
