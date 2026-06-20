"""Tests for knowledge enrichment adaptive loop — deprecated stub (ADR-200).

Verifies the deprecated KnowledgeEnrichmentLoop returns empty scans and error
results. The real scan/fix logic is now in skills/ai/scripts/ops/ modules.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from skills.daemon.scripts.adaptive.loops.knowledge_enrichment import KnowledgeEnrichmentLoop
from skills.daemon.scripts.adaptive.loops.base_loop import LoopResult


class TestDeprecatedKnowledgeEnrichment:
    def test_name_and_trigger(self):
        loop = KnowledgeEnrichmentLoop(project_root=Path("/tmp"))
        assert loop.NAME == "knowledge-enrichment"
        assert loop.TRIGGER == "nightly"

    def test_scan_returns_empty(self, tmp_path):
        loop = KnowledgeEnrichmentLoop(project_root=tmp_path)
        assert loop.scan() == []

    def test_scan_with_difficulties_returns_empty(self, tmp_path):
        loop = KnowledgeEnrichmentLoop(project_root=tmp_path)
        assert loop.scan(difficulties={"rag-reindex": 2}) == []

    def test_execute_returns_failure(self, tmp_path):
        loop = KnowledgeEnrichmentLoop(project_root=tmp_path)
        result = loop.execute_action({
            "action": "rag-reindex-test",
            "category": "rag-reindex",
        })
        assert result.success is False
        assert "ADR-200" in result.error
        assert "rag-reindex" in result.error
        assert result.action == "rag-reindex-test"
        assert result.category == "rag-reindex"

    def test_finalize_is_noop(self, tmp_path):
        loop = KnowledgeEnrichmentLoop(project_root=tmp_path)
        loop.finalize()  # Should not raise
