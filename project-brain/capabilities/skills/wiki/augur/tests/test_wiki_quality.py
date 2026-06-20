"""Auto-generated importability test for wiki_quality."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_wiki_quality_importable():
    """Verify that wiki_quality can be imported without errors."""
    import importlib
    mod = importlib.import_module("wiki_quality")
    assert mod is not None


def test_v4_quality_flags_malformed_timeline() -> None:
    from skills.wiki.scripts.wiki_quality import assess_page_quality

    body = """# Example

## Compiled truth

### Current Thesis

Human text.

## Timeline

- Missing metadata.
"""

    result = assess_page_quality(
        page="concepts/example",
        page_type="concept",
        hub="brain",
        tags=["example", "wiki"],
        sources=["vault://a.md", "vault://b.md", "vault://c.md"],
        body=body,
        cross_ref_count=1,
    )

    assert "timeline_entry_missing_at_or_source" in result["quality_flags"]


def test_v4_quality_flags_missing_timeline_observation() -> None:
    from skills.wiki.scripts.wiki_quality import assess_page_quality

    body = """# Example

## Compiled truth

### Current Thesis

Human text.

## Timeline

- _at: 2026-05-14T10:00:00Z  _source: vault://a.md
"""

    result = assess_page_quality(
        page="concepts/example",
        page_type="concept",
        hub="brain",
        tags=["example", "wiki"],
        sources=["vault://a.md", "vault://b.md", "vault://c.md"],
        body=body,
        cross_ref_count=1,
    )

    assert "timeline_entry_missing_observation" in result["quality_flags"]


def test_v4_quality_flags_source_lines_inside_compiled_truth() -> None:
    from skills.wiki.scripts.wiki_quality import assess_page_quality

    body = """# Example

## Compiled truth

_source: vault://a.md

## Timeline

- _at: 2026-05-14T10:00:00Z  _source: vault://a.md
  Observation.
"""

    result = assess_page_quality(
        page="concepts/example",
        page_type="concept",
        hub="brain",
        tags=["example", "wiki"],
        sources=["vault://a.md", "vault://b.md", "vault://c.md"],
        body=body,
        cross_ref_count=1,
    )

    assert "compiled_truth_contains_source_marker" in result["quality_flags"]


def test_v4_quality_allows_source_marker_prose_inside_compiled_truth() -> None:
    from skills.wiki.scripts.wiki_quality import assess_page_quality

    body = """# Example

## Compiled truth

This page explains that `_source:` belongs in timeline entries.

## Timeline

- _at: 2026-05-14T10:00:00Z  _source: vault://a.md
  Observation.
"""

    result = assess_page_quality(
        page="concepts/example",
        page_type="concept",
        hub="brain",
        tags=["example", "wiki"],
        sources=["vault://a.md", "vault://b.md", "vault://c.md"],
        body=body,
        cross_ref_count=1,
    )

    assert "compiled_truth_contains_source_marker" not in result["quality_flags"]


def test_v4_quality_flags_timeline_source_line_inside_compiled_truth() -> None:
    from skills.wiki.scripts.wiki_quality import assess_page_quality

    body = """# Example

## Compiled truth

- _at: 2026-05-14T10:00:00Z  _source: vault://a.md
  This belongs in the timeline, not compiled truth.

## Timeline

- _at: 2026-05-14T10:00:00Z  _source: vault://a.md
  Observation.
"""

    result = assess_page_quality(
        page="concepts/example",
        page_type="concept",
        hub="brain",
        tags=["example", "timeline"],
        sources=["vault://a.md", "vault://b.md", "vault://c.md"],
        body=body,
        cross_ref_count=1,
    )

    assert "compiled_truth_contains_source_marker" in result["quality_flags"]


def test_v4_quality_uses_compiled_truth_for_shallow_synthesis() -> None:
    from skills.wiki.scripts.wiki_quality import assess_page_quality

    compiled_truth = " ".join(
        f"durable synthesis sentence {index} connects current evidence to user value."
        for index in range(55)
    )
    body = f"""# Example

## Compiled truth

### Current Thesis

{compiled_truth}

## Timeline

- _at: 2026-05-14T10:00:00Z  _source: vault://a.md
  Observation.
"""

    result = assess_page_quality(
        page="concepts/example",
        page_type="concept",
        hub="brain",
        tags=["example", "timeline"],
        sources=[
            "vault://a.md",
            "vault://b.md",
            "vault://c.md",
            "vault://d.md",
            "vault://e.md",
            "vault://f.md",
            "vault://g.md",
            "vault://h.md",
        ],
        body=body,
        cross_ref_count=1,
    )

    assert "shallow_synthesis" not in result["quality_flags"]


def test_v4_quality_flags_legacy_v3_concept_marker() -> None:
    from skills.wiki.scripts.wiki_quality import assess_page_quality

    body = """# Example

## Compiled truth

Human text.

## Timeline

- _at: 2026-05-14T10:00:00Z  _source: vault://a.md
  Observation.
"""

    result = assess_page_quality(
        page="concepts/example",
        page_type="concept",
        hub="brain",
        tags=["example", "wiki"],
        sources=["vault://a.md", "vault://b.md", "vault://c.md"],
        body=body,
        cross_ref_count=1,
        compiler_version="concept-article-v3",
    )

    assert "legacy_concept_article_v3" in result["quality_flags"]


def test_v4_quality_allows_legacy_version_text_when_metadata_is_current() -> None:
    from skills.wiki.scripts.wiki_quality import assess_page_quality

    body = """# Example

## Compiled truth

This page references `compiler_version: concept-article-v3` as historical context.

## Timeline

- _at: 2026-05-14T10:00:00Z  _source: vault://a.md
  Observation.
"""

    result = assess_page_quality(
        page="concepts/example",
        page_type="concept",
        hub="brain",
        tags=["example", "timeline"],
        sources=["vault://a.md", "vault://b.md", "vault://c.md"],
        body=body,
        cross_ref_count=1,
        compiler_version="concept-article-v4",
    )

    assert "legacy_concept_article_v3" not in result["quality_flags"]


def test_v4_quality_warns_on_out_of_order_timeline() -> None:
    from skills.wiki.scripts.wiki_quality import assess_page_quality

    body = """# Example

## Compiled truth

Human text.

## Timeline

- _at: 2026-05-13T10:00:00Z  _source: vault://a.md
  Older listed first.

- _at: 2026-05-14T10:00:00Z  _source: vault://b.md
  Newer listed second.
"""

    result = assess_page_quality(
        page="concepts/example",
        page_type="concept",
        hub="brain",
        tags=["example", "wiki"],
        sources=["vault://a.md", "vault://b.md", "vault://c.md"],
        body=body,
        cross_ref_count=1,
    )

    assert "timeline_out_of_order" in result["quality_flags"]
