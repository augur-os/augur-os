"""Auto-generated importability test for wiki_maintenance_ops."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_wiki_maintenance_ops_importable():
    """Verify that wiki_maintenance_ops can be imported without errors."""
    import importlib
    mod = importlib.import_module("wiki_maintenance_ops")
    assert mod is not None


def test_wiki_maintenance_ops_reads_v4_timeline_citations():
    """V4 timeline entries participate in citation freshness checks."""
    import importlib

    mod = importlib.import_module("wiki_maintenance_ops")
    body = """# Example

## Compiled truth

### Current Thesis

Human text.

## Timeline

- _at: 2026-05-14T10:00:00Z  _source: vault://a.md
  A cited observation.
"""

    assert mod._evidence_source_ids(body) == {"vault://a.md"}
    assert mod._evidence_entries(body) == [
        {"source_id": "vault://a.md", "quote": "A cited observation."}
    ]


def test_wiki_maintenance_ops_keeps_legacy_evidence_citations():
    """Legacy query pages still expose their Evidence section."""
    import importlib

    mod = importlib.import_module("wiki_maintenance_ops")
    body = """# Query

## Evidence

- `vault://query.md`: Query citation.
"""

    assert mod._evidence_source_ids(body) == {"vault://query.md"}
    assert mod._evidence_entries(body) == [
        {"source_id": "vault://query.md", "quote": "Query citation."}
    ]
