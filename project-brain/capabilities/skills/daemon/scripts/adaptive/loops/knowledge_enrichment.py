"""Knowledge enrichment adaptive loop — DEPRECATED shell (ADR-200).

This class has been decomposed into standalone auto-command modules.
The engine discovers and runs each category independently via the
OpsCommand protocol (scan-fix).

Replaced by (ADR-200):
  - rag-reindex        → skills/ai/scripts/ops/rag_reindex.py
  - project-index-rebuild → skills/ai/scripts/ops/project_index.py
  - index-new-files    → skills/ai/scripts/ops/index_notes.py
  - analytics-generation → skills/ai/scripts/ops/analytics.py
  - generate-descriptions → skills/ai/scripts/ops/descriptions.py

Kept here for backward compatibility with any code that imports this class
by name. scan() returns [] and execute_action() returns an error directing
callers to the replacement modules.
"""
from __future__ import annotations

from pathlib import Path

from .base_loop import BaseLoop, LoopResult


class KnowledgeEnrichmentLoop(BaseLoop):
    """DEPRECATED — see module docstring and ADR-200 for replacement locations."""

    NAME = "knowledge-enrichment"
    TRIGGER = "nightly"

    def __init__(self, project_root: Path, cli_path: str | None = None) -> None:
        self._root = project_root
        self._cli = cli_path

    # ------------------------------------------------------------------
    # Scan — returns empty; auto-commands handle discovery now
    # ------------------------------------------------------------------

    def scan(self, difficulties: dict[str, int] | None = None) -> list[dict]:
        """DEPRECATED — returns [] since ADR-200 extraction.

        Each former category is now a standalone auto-command discovered by
        the engine via SKILL.md x-augur-commands entries with
        protocol: scan-fix and loop.name: knowledge-enrichment.
        """
        return []

    # ------------------------------------------------------------------
    # Execute — always errors; callers should use auto-command modules
    # ------------------------------------------------------------------

    def execute_action(self, action: dict) -> LoopResult:
        """DEPRECATED — always returns error since ADR-200 extraction.

        Use the corresponding auto-command module instead:
          rag-reindex        → scripts/ops/rag_reindex.py
          project-index-rebuild → scripts/ops/project_index.py
          index-new-files    → scripts/ops/index_notes.py
          analytics-generation → scripts/ops/analytics.py
          generate-descriptions → scripts/ops/descriptions.py
        """
        category = action.get("category", "unknown")
        return LoopResult(
            success=False,
            action=action.get("action", "unknown"),
            category=category,
            error=(
                f"KnowledgeEnrichmentLoop is deprecated (ADR-200). "
                f"Category '{category}' is now handled by the corresponding "
                f"auto-command module in skills/ai/scripts/ops/."
            ),
        )

    # ------------------------------------------------------------------
    # Finalize — no-op (RAG batch flushing moved to rag_reindex.py)
    # ------------------------------------------------------------------

    def finalize(self) -> None:
        """No-op — RAG batch commit logic moved to rag_reindex._flush_rag_batch()."""
