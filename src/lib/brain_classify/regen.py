"""Regenerate derived wiki surfaces (index.md/overview.md) after a move.

Durable concepts/ pages are never recompiled; only membership/index surfaces.
Uses the concept-pages support-page writer, which recomputes concept_count and
the source fingerprint from the on-disk page set.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def regenerate_wiki_metadata(*, wiki_dir: Path, timestamp: str | None = None) -> None:
    """Rebuild index.md/overview.md from the on-disk concepts/ + queries/ set."""
    import sys

    from src.config.paths import get_project_root

    caps = str(get_project_root() / "project-brain" / "capabilities")
    if caps not in sys.path:
        sys.path.insert(0, caps)
    from skills.wiki.scripts.wiki_concept_pages import write_wiki_support_pages

    ts = timestamp or datetime.now(tz=timezone.utc).isoformat()
    write_wiki_support_pages(wiki_dir, timestamp=ts)


def reindex_rag(category: str = "wiki") -> None:
    """Rebuild the RAG index for the wiki category (real-data step, Task 11)."""
    from src.config.paths import get_project_root
    from src.lib.index.incremental import sync_categories

    sync_categories({category}, project_root=get_project_root(), full=True)
