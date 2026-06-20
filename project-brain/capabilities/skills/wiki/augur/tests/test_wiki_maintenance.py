"""Auto-generated importability test for wiki_maintenance."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_wiki_maintenance_importable():
    """Verify that wiki_maintenance can be imported without errors."""
    import importlib
    mod = importlib.import_module("wiki_maintenance")
    assert mod is not None


def test_lint_wiki_allows_root_query_output_entrypoints(tmp_path: Path) -> None:
    """Registered root query outputs are entrypoints, not broken orphan pages."""
    from skills.wiki.scripts.wiki_maintenance import lint_wiki

    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    (wiki_dir / "index.md").write_text(
        """---
title: Wiki Index
page_type: overview
---
# Wiki Index
""",
        encoding="utf-8",
    )
    (wiki_dir / "overview.md").write_text(
        """---
title: Wiki Overview
page_type: overview
---
# Wiki Overview
""",
        encoding="utf-8",
    )
    (wiki_dir / "active-projects.md").write_text(
        """---
title: Active Projects
page_type: query
query_id: active-projects
sources:
  - git log --since=14 days ago
source_fingerprint: abc
---
# Active Projects

## Answer

Current work summary.
""",
        encoding="utf-8",
    )

    result = lint_wiki(wiki_dir=wiki_dir)

    assert result["ok"] is True
    assert result["orphan_pages"] == []


def test_lint_wiki_ignores_readme_files(tmp_path: Path) -> None:
    """Directory READMEs document ownership and are not compiled wiki pages."""
    from skills.wiki.scripts.wiki_maintenance import lint_wiki

    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    (wiki_dir / "index.md").write_text(
        """---
title: Wiki Index
page_type: overview
---
# Wiki Index
""",
        encoding="utf-8",
    )
    (wiki_dir / "overview.md").write_text(
        """---
title: Wiki Overview
page_type: overview
---
# Wiki Overview
""",
        encoding="utf-8",
    )
    (wiki_dir / "README.md").write_text(
        """---
title: Wiki Folder README
---
# Wiki Folder README

This file explains folder ownership.
""",
        encoding="utf-8",
    )

    result = lint_wiki(wiki_dir=wiki_dir)

    assert result["ok"] is True
    assert "README" not in result["orphan_pages"]


def test_apply_rewrite_proposal_for_v4_concept_preserves_timeline(tmp_path, monkeypatch):
    """V4 concept rewrites update compiled truth without overwriting timeline history."""
    import importlib

    wiki_maintenance = importlib.import_module("wiki_maintenance")
    wiki_dir = tmp_path / "wiki"
    runtime_dir = tmp_path / "runtime" / "wiki"
    target = wiki_dir / "concepts" / "example.md"
    target.parent.mkdir(parents=True)
    target.write_text(
        """---
title: Example
type: wiki-page
page_type: concept
hub: workspace
tags:
  - example
  - wiki
sources:
  - vault://a.md
compiler_version: concept-article-v4
---
# Example

## Compiled truth

### Current Thesis

Human text.

## Timeline

- _at: 2026-05-14T10:00:00Z  _source: vault://a.md
  Cited observation.
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        wiki_maintenance,
        "build_rewrite_proposals",
        lambda **_: [{
            "page": "concepts/example",
            "title": "Example",
            "hub": "brain",
            "reasons": ["stale_synthesis"],
            "quality_score": 50,
            "new_signal_counts": {"ask_clusters": 0, "ask_items": 0, "git_history": 0, "project_deltas": 0},
            "ask_clusters": [],
            "change_signals": {},
            "rewrite_brief": "Approved replacement.",
            "priority_score": 1.0,
            "proposal_fingerprint": "abc",
        }],
    )

    result = wiki_maintenance.apply_rewrite_proposals(
        wiki_dir=wiki_dir,
        runtime_wiki_dir=runtime_dir,
        limit=1,
    )

    assert result
    metadata, updated_body = wiki_maintenance.parse_frontmatter(target)
    assert metadata["compiler_version"] == "concept-article-v4"
    assert metadata["rewrite_signal_fingerprint"] == "abc"
    heading_lines = {line for line in updated_body.splitlines() if line.startswith("#")}
    assert "## Compiled truth" in updated_body
    assert "### Current Thesis" in heading_lines
    assert "## Current Thesis" not in heading_lines
    assert "## Timeline" in updated_body
    assert "Cited observation." in updated_body
    assert "### Recent Additions" in heading_lines
    assert "### Evidence" not in heading_lines
