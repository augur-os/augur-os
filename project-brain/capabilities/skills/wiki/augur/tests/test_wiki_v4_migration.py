"""Tests for ADR-740 v3-to-v4 wiki concept migration."""
from __future__ import annotations

from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter
from skills.wiki.scripts.wiki_v4_migration import (
    migrate_concept_page_text,
    migrate_wiki_dir,
)


V3_PAGE = """---
title: Example
page_type: concept
compiler_version: concept-article-v3
updated: '2026-05-14T10:00:00Z'
review_owner: user-kept
---
# Example

## Current Thesis

Old thesis.

## Evidence

- `vault:/a.md`: A cited claim.

## Source Basis

- `vault:/a.md`: A cited quote.
"""


def test_migrate_concept_page_text_demotes_truth_and_builds_timeline() -> None:
    migrated = migrate_concept_page_text(
        V3_PAGE,
        fallback_updated="2026-05-14T10:00:00Z",
    )

    assert "compiler_version: concept-article-v4" in migrated
    assert "review_owner: user-kept" in migrated
    assert "## Compiled truth" in migrated
    assert "### Current Thesis" in migrated
    assert "Old thesis." in migrated
    assert "### Source Basis" in migrated
    assert "## Timeline" in migrated
    assert "_at: 2026-05-14T10:00:00Z" in migrated
    assert "_source: vault:/a.md" in migrated
    assert "A cited claim." in migrated
    assert "## Evidence" not in migrated


def test_migrate_wiki_dir_dry_run_does_not_write(tmp_path: Path) -> None:
    page = tmp_path / "concepts" / "example.md"
    page.parent.mkdir(parents=True)
    page.write_text(V3_PAGE, encoding="utf-8")

    result = migrate_wiki_dir(
        wiki_dir=tmp_path,
        runtime_dir=tmp_path / "runtime",
        apply=False,
    )

    assert result.changed_pages == [page]
    assert str(page) in result.diffs
    assert "concept-article-v4" in result.diffs[str(page)]
    assert result.backup_dir is None
    assert not (tmp_path / "runtime").exists()
    assert "## Evidence" in page.read_text(encoding="utf-8")


def test_migrate_wiki_dir_apply_creates_backup_and_is_idempotent(
    tmp_path: Path,
) -> None:
    page = tmp_path / "concepts" / "example.md"
    page.parent.mkdir(parents=True)
    page.write_text(V3_PAGE, encoding="utf-8")
    runtime = tmp_path / "runtime"

    first = migrate_wiki_dir(wiki_dir=tmp_path, runtime_dir=runtime, apply=True)

    assert first.changed_pages == [page]
    assert first.backup_dir is not None
    assert (first.backup_dir / "concepts" / "example.md").read_text(
        encoding="utf-8",
    ) == V3_PAGE
    meta, body = parse_frontmatter(page, include_sidecar_config=False)
    assert meta["compiler_version"] == "concept-article-v4"
    assert meta["review_owner"] == "user-kept"
    assert "## Compiled truth" in body
    assert "## Timeline" in body
    assert "## Evidence" not in body

    second = migrate_wiki_dir(wiki_dir=tmp_path, runtime_dir=runtime, apply=True)

    assert second.changed_pages == []
    assert second.diffs == {}
    assert second.backup_dir is None


def test_migrate_wiki_dir_selects_underscored_metadata_aliases(
    tmp_path: Path,
) -> None:
    page = tmp_path / "concepts" / "aliased.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        """---
title: Aliased
_page_type: concept
_compiler_version: concept-article-v3
_updated: '2026-05-13T09:30:00Z'
---
# Aliased

## Current Thesis

Aliased metadata should be selected.

## Evidence

- `vault:/aliased.md`: Aliased evidence.
""",
        encoding="utf-8",
    )

    result = migrate_wiki_dir(
        wiki_dir=tmp_path,
        runtime_dir=tmp_path / "runtime",
        apply=False,
    )

    assert result.changed_pages == [page]
    assert "_source: vault:/aliased.md" in result.diffs[str(page)]
    assert "_at: 2026-05-13T09:30:00Z" in result.diffs[str(page)]


def test_migrate_wiki_dir_uses_created_when_updated_missing(tmp_path: Path) -> None:
    page = tmp_path / "concepts" / "created-only.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        """---
title: Created Only
page_type: concept
compiler_version: concept-article-v3
created: '2026-05-12T08:00:00Z'
---
# Created Only

## Current Thesis

Created timestamp should feed the migrated timeline.

## Evidence

- `vault:/created.md`: Created-only evidence.
""",
        encoding="utf-8",
    )

    result = migrate_wiki_dir(
        wiki_dir=tmp_path,
        runtime_dir=tmp_path / "runtime",
        apply=False,
    )

    assert result.changed_pages == [page]
    assert "_at: 2026-05-12T08:00:00Z" in result.diffs[str(page)]


def test_migrate_wiki_dir_normalizes_date_only_updated(tmp_path: Path) -> None:
    page = tmp_path / "concepts" / "date-only.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        """---
title: Date Only
page_type: concept
compiler_version: concept-article-v3
updated: 2026-05-14
---
# Date Only

## Current Thesis

Date-only updated values should still produce valid timeline timestamps.

## Evidence

- `vault:/date.md`: Date-only evidence.
""",
        encoding="utf-8",
    )

    result = migrate_wiki_dir(
        wiki_dir=tmp_path,
        runtime_dir=tmp_path / "runtime",
        apply=False,
    )

    assert result.changed_pages == [page]
    assert "_at: 2026-05-14T00:00:00Z" in result.diffs[str(page)]


def test_migrate_wiki_dir_skips_unparsed_evidence_without_writing(
    tmp_path: Path,
) -> None:
    page = tmp_path / "concepts" / "unsafe.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        """---
title: Unsafe
page_type: concept
compiler_version: concept-article-v3
updated: '2026-05-14T10:00:00Z'
---
# Unsafe

## Current Thesis

Unparsed evidence must not be silently discarded.

## Evidence

- Evidence without a cited source.
""",
        encoding="utf-8",
    )

    result = migrate_wiki_dir(
        wiki_dir=tmp_path,
        runtime_dir=tmp_path / "runtime",
        apply=True,
    )

    assert result.changed_pages == []
    assert result.skipped_pages == [page]
    assert str(page) in result.warnings
    assert "concept-article-v3" in page.read_text(encoding="utf-8")
    assert not (tmp_path / "runtime").exists()
