"""Tests for wiki MCP tool plumbing."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from skills.wiki.scripts.mcp import wiki_tools


V3_PAGE = """---
title: Example
page_type: concept
compiler_version: concept-article-v3
updated: '2026-05-14T10:00:00Z'
---
# Example

## Current Thesis

Old thesis.

## Evidence

- `vault:/a.md`: A cited claim.
"""


def test_wiki_v4_migration_dry_run_reports_changed_pages(
    tmp_path: Path,
    monkeypatch,
) -> None:
    wiki_dir = tmp_path / "wiki"
    runtime_dir = tmp_path / "runtime"
    page = wiki_dir / "concepts" / "example.md"
    page.parent.mkdir(parents=True)
    page.write_text(V3_PAGE, encoding="utf-8")
    original = page.read_text(encoding="utf-8")

    monkeypatch.setattr(wiki_tools, "get_wiki_dir", lambda: wiki_dir)
    monkeypatch.setattr(wiki_tools, "resolve_wiki_dir", lambda: wiki_dir)
    monkeypatch.setattr(wiki_tools, "get_runtime_dir", lambda: runtime_dir)

    payload = json.loads(asyncio.run(wiki_tools._run_wiki_migrate_v4(apply=False)))

    assert payload["success"] is True
    assert payload["apply"] is False
    assert payload["changed_pages"] == [str(page)]
    assert payload["backup_dir"] is None
    assert str(page) in payload["diffs"]
    assert payload["skipped_pages"] == []
    assert payload["warnings"] == {}
    assert page.read_text(encoding="utf-8") == original
