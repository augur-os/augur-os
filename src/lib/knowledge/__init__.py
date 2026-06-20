"""
Two-Layer Memory Architecture for Augur

Part of the Knowledge plugin - provides session memory and decision tracking.

This module implements the Clawdbot-inspired memory pattern:
- Layer 1: Daily logs (ephemeral session events)
- Layer 2: Curated MEMORY.md (persistent decisions/patterns)
- Hybrid search via ripgrep + YAML index (no binary dependencies)
- Unified search across all knowledge scopes (ADR-033)

See: get_adr_dir()/ADR-028-two-layer-memory-architecture.md
See: get_adr_dir()/ADR-033-rag-search-hardening.md
"""

from .daily_logger import DailyLogger, EventType, MemoryEvent
from .memory_store import MemoryStore, MemoryEntry
from .curator import MemoryCurator
from .unified_search import UnifiedSearcher

__all__ = [
    # Core classes
    "DailyLogger",
    "MemoryStore",
    "MemoryCurator",
    "UnifiedSearcher",
    # Data classes
    "EventType",
    "MemoryEvent",
    "MemoryEntry",
]
