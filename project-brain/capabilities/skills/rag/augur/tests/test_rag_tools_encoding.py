"""Encoding regressions for the unified-search ripgrep helpers.

The helper used to live in skills/rag/scripts/mcp/rag_tools.py; it was
extracted to src/lib/index/unified_search.py alongside unified_rag_search
when the last cross-skill allowlist entry retired (2026-04-30).
"""

from __future__ import annotations

import subprocess


def test_collect_rg_hits_tolerates_non_utf8_stdout(monkeypatch, tmp_path):
    """Ripgrep output with invalid UTF-8 bytes should not crash collection."""
    from src.lib.index import unified_search

    sample_dir = tmp_path / "vault"
    sample_dir.mkdir()

    def fake_check_output(*args, **kwargs):
        return b"/tmp/bad.md:1:Curly quote \x93 survives\n"

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)

    hits = unified_search._collect_rg_hits("Curly", [], [sample_dir], max_hits=10)

    assert hits == [
        {
            "file": "/tmp/bad.md",
            "line": "1",
            "content": "Curly quote \ufffd survives",
        }
    ]
