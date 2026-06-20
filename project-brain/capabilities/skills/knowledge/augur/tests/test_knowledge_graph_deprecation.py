"""knowledge-graph is superseded by graph-stats (ADR-738).

Asserts the legacy knowledge-graph tool's payload now carries the deprecation
pointer. Imports via importlib per the repo test convention.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_knowledge_graph_payload_carries_deprecation_pointer():
    """The legacy knowledge-graph payload points callers at graph-stats."""
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.rag_search")
    payload = mod.knowledge_graph_deprecation_payload({"skills": 1, "documents": 2})

    assert payload["success"] is True
    assert payload["deprecated"] is True
    assert payload["superseded_by"] == "graph-stats"
    assert "graph-stats" in payload["message"]
    assert "ADR-738" in payload["message"]
    # legacy RAG-manifest counts still ride along for one release
    assert payload["stats"] == {"skills": 1, "documents": 2}
