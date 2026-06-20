# Compiled-Truth Timeline Wiki Pattern Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement ADR-740 by splitting wiki concept pages into a human-owned `## Compiled truth` zone and an append-only, cited `## Timeline` zone, with v3-to-v4 migration and lint enforcement.

**Architecture:** Keep the wiki file-first and markdown-only. New pure helpers own body-zone parsing, timeline validation, and migration transforms; existing compiler and rewrite flows call those helpers so `wiki-update`, `wiki-apply-concept-batch`, and `wiki-apply-top-rewrite-proposal` keep their public command surfaces. Concept pages move to `concept-article-v4`; query and support pages stay on the existing schema.

**Tech Stack:** Python 3.11+, existing ingest skill scripts, YAML schema assets, pytest through `/auto-test-pytest`, real vault validation through wiki MCP/CLI surfaces. No database, no embedded model calls, no dashboard UI change in this ADR.

**Spec:** `docs/superpowers/specs/2026-05-14-compiled-truth-timeline-design.md` · **ADR:** ADR-740

---

## File Structure

**New files:**
- `shared-vault/skills/ingest/scripts/wiki_timeline.py` — pure helpers for heading-zone parsing, compiled-truth replacement, timeline entry creation, ordering, and validation.
- `shared-vault/skills/ingest/scripts/wiki_v4_migration.py` — v3-to-v4 migration transform, dry-run diff generation, runtime backup, and guarded apply.
- `shared-vault/skills/ingest/assets/templates/wiki-page.md` — v4 concept page template.
- `shared-vault/skills/ingest/augur/tests/test_wiki_timeline.py`
- `shared-vault/skills/ingest/augur/tests/test_wiki_v4_migration.py`

**Modified files:**
- `shared-vault/skills/ingest/assets/seeds/wiki-schema/page-types.yaml` — concept v4 required sections.
- `shared-vault/skills/ingest/assets/seeds/wiki-schema/lint-rules.yaml` — v4 lint penalty names.
- `shared-vault/skills/ingest/scripts/wiki_concept_pages.py` — create v4 concept pages, append timeline entries, preserve compiled truth on existing v4 pages.
- `shared-vault/skills/ingest/scripts/wiki_concept_state.py` — bump concept compiler version to `concept-article-v4`.
- `shared-vault/skills/ingest/scripts/wiki_quality.py` — v4 lint/quality flags.
- `shared-vault/skills/ingest/scripts/wiki_maintenance.py` — proposal apply scopes to `## Compiled truth` for v4 concept pages.
- `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py` — expose migration dry-run/apply through the existing wiki command plumbing that matches current command patterns.
- `docs/agent-topics/WIKI.md` — document the human/machine wiki-page boundary.

---

## Phase 1 — v4 Schema and Timeline Helpers

### Task 1: Add `wiki_timeline.py` with pure body-zone helpers

**Files:**
- Create: `shared-vault/skills/ingest/scripts/wiki_timeline.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_wiki_timeline.py`

- [ ] **Step 1: Write the failing tests**

Create `shared-vault/skills/ingest/augur/tests/test_wiki_timeline.py`:

```python
"""Tests for ADR-740 wiki timeline helpers."""
from __future__ import annotations

import pytest

from skills.ingest.scripts.wiki_timeline import (
    TimelineEntry,
    append_timeline_entries,
    extract_compiled_truth,
    extract_timeline,
    replace_compiled_truth,
    validate_timeline_entries,
)


BODY = """# Page

## Compiled truth

### Current Thesis

Keep this human text.

## Timeline

- _at: 2026-05-14T10:00:00Z  _source: vault://a.md
  Latest observation.
"""


def test_extracts_compiled_truth_and_timeline_zones() -> None:
    assert "Keep this human text." in extract_compiled_truth(BODY)
    assert "Latest observation." in extract_timeline(BODY)


def test_replace_compiled_truth_preserves_timeline() -> None:
    updated = replace_compiled_truth(BODY, "### Current Thesis\n\nApproved rewrite.")
    assert "Approved rewrite." in updated
    assert "Latest observation." in updated
    assert "Keep this human text." not in updated


def test_append_timeline_entries_newest_first_and_preserves_truth() -> None:
    updated = append_timeline_entries(
        BODY,
        [
            TimelineEntry(
                at="2026-05-15T08:00:00Z",
                source="graph://edge-1",
                observation="Newer observation.",
            )
        ],
    )
    assert updated.index("Newer observation.") < updated.index("Latest observation.")
    assert "Keep this human text." in updated


def test_validate_rejects_missing_required_fields() -> None:
    with pytest.raises(ValueError, match="_source"):
        TimelineEntry(at="2026-05-15T08:00:00Z", source="", observation="bad")
    with pytest.raises(ValueError, match="_at"):
        TimelineEntry(at="", source="vault://a.md", observation="bad")


def test_validate_reports_out_of_order_warning() -> None:
    body = """# Page

## Compiled truth

text

## Timeline

- _at: 2026-05-13T10:00:00Z  _source: vault://old.md
  Old.
- _at: 2026-05-14T10:00:00Z  _source: vault://new.md
  New.
"""
    result = validate_timeline_entries(body)
    assert result.errors == []
    assert "timeline_out_of_order" in result.warnings
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/ingest/augur/tests/test_wiki_timeline.py`
Expected: FAIL because `skills.ingest.scripts.wiki_timeline` does not exist.

- [ ] **Step 3: Implement the helper module**

Create `shared-vault/skills/ingest/scripts/wiki_timeline.py`:

```python
"""Compiled-truth and timeline helpers for wiki concept pages (ADR-740)."""
from __future__ import annotations

from dataclasses import dataclass
import re


COMPILED_TRUTH_HEADING = "Compiled truth"
TIMELINE_HEADING = "Timeline"
_H2_RE = re.compile(r"(?m)^## (?P<title>.+?)\s*$")
_ENTRY_RE = re.compile(r"(?m)^- _at: (?P<at>\S+)\s+_source: (?P<source>\S+)\s*$")


@dataclass(frozen=True)
class TimelineEntry:
    at: str
    source: str
    observation: str

    def __post_init__(self) -> None:
        if not self.at.strip():
            raise ValueError("Timeline entry requires _at")
        if not self.source.strip():
            raise ValueError("Timeline entry requires _source")
        if not self.observation.strip():
            raise ValueError("Timeline entry requires observation text")

    def render(self) -> str:
        lines = [f"- _at: {self.at.strip()}  _source: {self.source.strip()}"]
        for line in self.observation.strip().splitlines():
            lines.append(f"  {line.strip()}")
        return "\n".join(lines)


@dataclass(frozen=True)
class TimelineValidation:
    errors: list[str]
    warnings: list[str]


def _section_bounds(body: str, heading: str) -> tuple[int, int] | None:
    matches = list(_H2_RE.finditer(body))
    for index, match in enumerate(matches):
        if match.group("title").strip().lower() != heading.lower():
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        return start, end
    return None


def _replace_section(body: str, heading: str, content: str) -> str:
    bounds = _section_bounds(body, heading)
    replacement = f"## {heading}\n\n{content.strip()}\n"
    if bounds is None:
        return body.rstrip() + "\n\n" + replacement
    start, end = bounds
    return body[:start].rstrip() + "\n\n" + content.strip() + "\n" + body[end:]


def extract_compiled_truth(body: str) -> str:
    bounds = _section_bounds(body, COMPILED_TRUTH_HEADING)
    return body[bounds[0]:bounds[1]].strip() if bounds else ""


def extract_timeline(body: str) -> str:
    bounds = _section_bounds(body, TIMELINE_HEADING)
    return body[bounds[0]:bounds[1]].strip() if bounds else ""


def replace_compiled_truth(body: str, compiled_truth: str) -> str:
    return _replace_section(body, COMPILED_TRUTH_HEADING, compiled_truth).rstrip() + "\n"


def append_timeline_entries(body: str, entries: list[TimelineEntry]) -> str:
    if not entries:
        return body
    existing = extract_timeline(body)
    rendered = "\n\n".join(entry.render() for entry in sorted(entries, key=lambda item: item.at, reverse=True))
    content = f"{rendered}\n\n{existing}".strip() if existing else rendered
    return _replace_section(body, TIMELINE_HEADING, content).rstrip() + "\n"


def validate_timeline_entries(body: str) -> TimelineValidation:
    timeline = extract_timeline(body)
    errors: list[str] = []
    warnings: list[str] = []
    seen_times: list[str] = []
    for raw in timeline.splitlines():
        if not raw.startswith("- "):
            continue
        match = _ENTRY_RE.match(raw)
        if match is None:
            errors.append("timeline_entry_missing_at_or_source")
            continue
        seen_times.append(match.group("at"))
    if seen_times != sorted(seen_times, reverse=True):
        warnings.append("timeline_out_of_order")
    return TimelineValidation(errors=errors, warnings=warnings)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `/auto-test-pytest shared-vault/skills/ingest/augur/tests/test_wiki_timeline.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_timeline.py shared-vault/skills/ingest/augur/tests/test_wiki_timeline.py
git commit -m "feat(wiki): add compiled-truth timeline helpers for ADR-740"
```

### Task 2: Update schema assets and quality lint for v4

**Files:**
- Modify: `shared-vault/skills/ingest/assets/seeds/wiki-schema/page-types.yaml`
- Modify: `shared-vault/skills/ingest/assets/seeds/wiki-schema/lint-rules.yaml`
- Modify: `shared-vault/skills/ingest/scripts/wiki_quality.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_wiki_schema.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_wiki_quality.py`

- [ ] **Step 1: Write failing schema/quality tests**

Add to `shared-vault/skills/ingest/augur/tests/test_wiki_schema.py`:

```python
from skills.ingest.scripts.wiki_schema import page_schema


def test_concept_schema_requires_compiled_truth_and_timeline() -> None:
    schema = page_schema(page="concepts/example", page_type="concept")
    assert "Compiled truth" in schema["required_sections"]
    assert "Timeline" in schema["required_sections"]
```

Add to `shared-vault/skills/ingest/augur/tests/test_wiki_quality.py`:

```python
from skills.ingest.scripts.wiki_quality import assess_page_quality


def test_v4_quality_flags_malformed_timeline() -> None:
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


def test_v4_quality_flags_source_lines_inside_compiled_truth() -> None:
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/auto-test-pytest shared-vault/skills/ingest/augur/tests/test_wiki_schema.py shared-vault/skills/ingest/augur/tests/test_wiki_quality.py`
Expected: FAIL because v4 required sections and lint flags are absent.

- [ ] **Step 3: Update schema and quality logic**

Change the `concept.required_sections` list in `page-types.yaml` to require the v4 H2 wrappers:

```yaml
concept:
  description: Synthesized durable concept page generated from merged evidence.
  required_sections:
    - Compiled truth
    - Timeline
  min_tags: 2
  min_cross_links: 1
```

Add penalties in `lint-rules.yaml`:

```yaml
  timeline_entry_missing_at_or_source: 40
  compiled_truth_contains_source_marker: 40
  timeline_out_of_order: 8
  legacy_concept_article_v3: 10
```

In `wiki_quality.py`, import the helpers and append the v4 flags for concept pages:

```python
from skills.ingest.scripts.wiki_timeline import (
    extract_compiled_truth,
    validate_timeline_entries,
)
```

Inside `assess_page_quality()`, after the existing concept-specific block:

```python
        validation = validate_timeline_entries(body)
        flags.extend(validation.errors)
        flags.extend(validation.warnings)
        if "_source:" in extract_compiled_truth(body):
            flags.append("compiled_truth_contains_source_marker")
        if "compiler_version: concept-article-v3" in body or "_compiler_version: concept-article-v3" in body:
            flags.append("legacy_concept_article_v3")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/auto-test-pytest shared-vault/skills/ingest/augur/tests/test_wiki_schema.py shared-vault/skills/ingest/augur/tests/test_wiki_quality.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/assets/seeds/wiki-schema/page-types.yaml shared-vault/skills/ingest/assets/seeds/wiki-schema/lint-rules.yaml shared-vault/skills/ingest/scripts/wiki_quality.py shared-vault/skills/ingest/augur/tests/test_wiki_schema.py shared-vault/skills/ingest/augur/tests/test_wiki_quality.py
git commit -m "feat(wiki): enforce concept v4 schema and timeline lint"
```

---

## Phase 2 — Concept Writer and Proposal Gate

### Task 3: Write v4 concept pages and append timeline entries

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/wiki_concept_state.py`
- Modify: `shared-vault/skills/ingest/scripts/wiki_concept_pages.py`
- Create: `shared-vault/skills/ingest/assets/templates/wiki-page.md`
- Test: `shared-vault/skills/ingest/augur/tests/test_wiki_concept_pages.py`

- [ ] **Step 1: Write failing tests for new and existing pages**

Add to `shared-vault/skills/ingest/augur/tests/test_wiki_concept_pages.py`:

```python
def test_write_concept_pages_creates_v4_compiled_truth_and_timeline(tmp_path):
    concept = _merged_concept_with_evidence("compiled-truth-test")
    written = write_concept_pages(tmp_path, [concept], timestamp="2026-05-14T10:00:00Z")
    assert written
    text = (tmp_path / "concepts" / "compiled-truth-test.md").read_text(encoding="utf-8")
    assert "compiler_version: concept-article-v4" in text
    assert "## Compiled truth" in text
    assert "### Current Thesis" in text
    assert "## Timeline" in text
    assert "_at: 2026-05-14T10:00:00Z" in text
    assert "_source:" in text


def test_write_concept_pages_preserves_existing_compiled_truth(tmp_path):
    concept = _merged_concept_with_evidence("preserve-human-truth")
    first = write_concept_pages(tmp_path, [concept], timestamp="2026-05-14T10:00:00Z")
    assert first
    target = tmp_path / "concepts" / "preserve-human-truth.md"
    text = target.read_text(encoding="utf-8")
    target.write_text(text.replace("### Current Thesis", "### Current Thesis\n\nHuman-edited thesis."), encoding="utf-8")

    second = write_concept_pages(tmp_path, [concept], timestamp="2026-05-15T10:00:00Z")
    assert second
    updated = target.read_text(encoding="utf-8")
    assert "Human-edited thesis." in updated
    assert "_at: 2026-05-15T10:00:00Z" in updated
```

If the test file lacks a fixture builder, add a local helper in the test file that constructs the existing `MergedConcept`, `ConceptEvidence`, and `SourceDescriptor` dataclasses used by nearby tests.

- [ ] **Step 2: Run tests to verify they fail**

Run: `/auto-test-pytest shared-vault/skills/ingest/augur/tests/test_wiki_concept_pages.py`
Expected: FAIL because writer still emits `concept-article-v3`, direct H2 sections, and `## Evidence`.

- [ ] **Step 3: Bump concept compiler version**

In `wiki_concept_state.py`, change:

```python
COMPILER_VERSION = "concept-article-v4"
```

In `wiki_concept_pages.py`, use a concept-specific constant:

```python
CONCEPT_COMPILER_VERSION = "concept-article-v4"
QUERY_COMPILER_VERSION = "concept-article-v3"
```

Set concept metadata `compiler_version` to `CONCEPT_COMPILER_VERSION` and query metadata to `QUERY_COMPILER_VERSION`.

- [ ] **Step 4: Render v4 concept bodies**

Refactor `_concept_body()` to render:

```python
lines = [
    f"# {concept.title}",
    "",
    "## Compiled truth",
    "",
    "### Current Thesis",
    "",
    _canonicalize_wikilinks(core_thesis, known_slugs=known_slugs),
    "",
    "### What This Page Knows",
    "",
    _canonicalize_wikilinks(source_synthesis, known_slugs=known_slugs),
    "",
    "### Key Dimensions",
    "",
    *_bullet_lines(key_dimensions, known_slugs=known_slugs),
    "",
    "### Recent Shifts",
    "",
    *_bullet_lines(recent_shifts, known_slugs=known_slugs),
    "",
    "### Open Tensions",
    "",
    *_bullet_lines(open_tensions, known_slugs=known_slugs),
    "",
    "### How to Use This",
    "",
    _canonicalize_wikilinks(how_to_use, known_slugs=known_slugs),
    "",
]
```

Append `### Open Questions`, `### Source Basis`, and `### Related Concepts` under `## Compiled truth` when the current data has those sections. Replace `## Evidence` with `## Timeline` entries built from selected evidence:

```python
from skills.ingest.scripts.wiki_timeline import TimelineEntry, append_timeline_entries


def _timeline_entries_from_evidence(
    evidence: list[ConceptEvidence],
    *,
    timestamp: str,
) -> list[TimelineEntry]:
    return [
        TimelineEntry(
            at=timestamp,
            source=item.source_id if "://" in item.source_id else f"vault://{item.source_id}",
            observation=_evidence_claim_text(item),
        )
        for item in evidence
        if _evidence_claim_text(item)
    ]
```

For an existing v4 concept page, preserve `extract_compiled_truth(existing_body)` and only append new entries to the timeline. For a brand-new concept page, initial compiled truth may be written because no human-owned zone exists yet.

- [ ] **Step 5: Add the template**

Create `shared-vault/skills/ingest/assets/templates/wiki-page.md`:

```markdown
---
title: Untitled Wiki Concept
page_type: concept
compiler_version: concept-article-v4
---

# Untitled Wiki Concept

## Compiled truth

### Current Thesis

### What This Page Knows

### Key Dimensions

### Recent Shifts

### Open Tensions

### How to Use This

### Open Questions

### Source Basis

## Timeline
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `/auto-test-pytest shared-vault/skills/ingest/augur/tests/test_wiki_concept_pages.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_concept_state.py shared-vault/skills/ingest/scripts/wiki_concept_pages.py shared-vault/skills/ingest/assets/templates/wiki-page.md shared-vault/skills/ingest/augur/tests/test_wiki_concept_pages.py
git commit -m "feat(wiki): write concept article v4 pages"
```

### Task 4: Scope rewrite proposal application to compiled truth

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/wiki_maintenance.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_wiki_maintenance.py`

- [ ] **Step 1: Write failing proposal-gate test**

Add to `shared-vault/skills/ingest/augur/tests/test_wiki_maintenance.py`:

```python
def test_apply_rewrite_proposal_for_v4_concept_preserves_timeline(tmp_path, monkeypatch):
    wiki_dir = tmp_path / "wiki"
    runtime_dir = tmp_path / "runtime" / "wiki"
    target = wiki_dir / "concepts" / "example.md"
    target.parent.mkdir(parents=True)
    target.write_text(
        """---
title: Example
page_type: concept
hub: brain
tags: [example, wiki]
sources: [vault://a.md]
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
        "skills.ingest.scripts.wiki_maintenance.build_rewrite_proposals",
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

    result = apply_rewrite_proposals(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_dir, limit=1)
    assert result
    updated = target.read_text(encoding="utf-8")
    assert "Approved replacement." in updated
    assert "Cited observation." in updated
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/ingest/augur/tests/test_wiki_maintenance.py`
Expected: FAIL because rewrite application rewrites whole page bodies.

- [ ] **Step 3: Implement v4 concept rewrite scoping**

In `wiki_maintenance.py`, import:

```python
from skills.ingest.scripts.wiki_timeline import replace_compiled_truth
```

Add:

```python
def _is_v4_concept(existing: dict[str, Any]) -> bool:
    return (
        str(existing.get("page_type") or "").strip() == "concept"
        and str(existing.get("compiler_version") or "").strip() == "concept-article-v4"
    )
```

In `apply_rewrite_proposals()`, replace the body selection with:

```python
        rendered = _render_rewrite_body(existing_for_render, proposal)
        if _is_v4_concept(existing):
            body = replace_compiled_truth(str(existing.get("body") or ""), _compiled_truth_from_rendered_rewrite(rendered))
        else:
            body = rendered
```

Implement `_compiled_truth_from_rendered_rewrite()` as a deterministic adapter from the existing rewrite renderer into v4 subsections:

```python
def _compiled_truth_from_rendered_rewrite(rendered: str) -> str:
    return rendered.replace("## ", "### ").lstrip("#").strip()
```

Keep non-concept and non-v4 pages on the current whole-body rewrite path.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/auto-test-pytest shared-vault/skills/ingest/augur/tests/test_wiki_maintenance.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_maintenance.py shared-vault/skills/ingest/augur/tests/test_wiki_maintenance.py
git commit -m "feat(wiki): gate rewrite proposals to compiled truth"
```

---

## Phase 3 — Migration

### Task 5: Add dry-run-first v3-to-v4 migration with runtime backups

**Files:**
- Create: `shared-vault/skills/ingest/scripts/wiki_v4_migration.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_wiki_v4_migration.py`

- [ ] **Step 1: Write failing migration tests**

Create `shared-vault/skills/ingest/augur/tests/test_wiki_v4_migration.py`:

```python
"""Tests for ADR-740 v3-to-v4 wiki concept migration."""
from __future__ import annotations

from pathlib import Path

from skills.ingest.scripts.wiki_v4_migration import migrate_concept_page_text, migrate_wiki_dir


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

## Source Basis

- `vault:/a.md`: A cited quote.
"""


def test_migrate_concept_page_text_demotes_truth_and_builds_timeline() -> None:
    migrated = migrate_concept_page_text(V3_PAGE, fallback_updated="2026-05-14T10:00:00Z")
    assert "compiler_version: concept-article-v4" in migrated
    assert "## Compiled truth" in migrated
    assert "### Current Thesis" in migrated
    assert "Old thesis." in migrated
    assert "## Timeline" in migrated
    assert "_at: 2026-05-14T10:00:00Z" in migrated
    assert "_source: vault:/a.md" in migrated
    assert "## Evidence" not in migrated


def test_migrate_wiki_dir_dry_run_does_not_write(tmp_path: Path) -> None:
    page = tmp_path / "concepts" / "example.md"
    page.parent.mkdir(parents=True)
    page.write_text(V3_PAGE, encoding="utf-8")
    result = migrate_wiki_dir(wiki_dir=tmp_path, runtime_dir=tmp_path / "runtime", apply=False)
    assert result.changed_pages == [page]
    assert "## Evidence" in page.read_text(encoding="utf-8")


def test_migrate_wiki_dir_apply_creates_backup_and_is_idempotent(tmp_path: Path) -> None:
    page = tmp_path / "concepts" / "example.md"
    page.parent.mkdir(parents=True)
    page.write_text(V3_PAGE, encoding="utf-8")
    runtime = tmp_path / "runtime"
    first = migrate_wiki_dir(wiki_dir=tmp_path, runtime_dir=runtime, apply=True)
    assert first.backup_dir is not None
    assert (first.backup_dir / "concepts" / "example.md").exists()
    assert "concept-article-v4" in page.read_text(encoding="utf-8")
    second = migrate_wiki_dir(wiki_dir=tmp_path, runtime_dir=runtime, apply=True)
    assert second.changed_pages == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/auto-test-pytest shared-vault/skills/ingest/augur/tests/test_wiki_v4_migration.py`
Expected: FAIL because `wiki_v4_migration.py` does not exist.

- [ ] **Step 3: Implement migration module**

Create `wiki_v4_migration.py` with:

```python
"""Dry-run-first concept page migration for ADR-740."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import difflib
import shutil

from src.lib.frontmatter_utils import parse_frontmatter, write_vault_frontmatter


@dataclass(frozen=True)
class MigrationResult:
    changed_pages: list[Path]
    diffs: dict[str, str]
    backup_dir: Path | None = None


def migrate_concept_page_text(raw: str, *, fallback_updated: str) -> str:
    # Parse frontmatter in a temporary file when path-level metadata is required;
    # keep this function pure in tests.
    # by delegating path-level parsing to migrate_wiki_dir().
    body = raw
    fm = ""
    if raw.startswith("---"):
        end = raw.find("\n---", 4)
        if end != -1:
            fm = raw[: end + 4]
            body = raw[end + 4 :].lstrip("\n")
    body = body.replace("compiler_version: concept-article-v3", "compiler_version: concept-article-v4")
    body = body.replace("_compiler_version: concept-article-v3", "_compiler_version: concept-article-v4")
    lines = body.splitlines()
    compiled: list[str] = []
    timeline: list[str] = []
    in_evidence = False
    for line in lines:
        if line == "## Evidence":
            in_evidence = True
            continue
        if line.startswith("## ") and in_evidence:
            in_evidence = False
        if in_evidence:
            stripped = line.strip()
            if stripped.startswith("- `") and "`:" in stripped:
                source = stripped.split("`", 2)[1]
                observation = stripped.split("`:", 1)[1].strip()
                timeline.extend([
                    f"- _at: {fallback_updated}  _source: {source}",
                    f"  {observation}",
                ])
            continue
        if line.startswith("## "):
            compiled.append("### " + line[3:])
        else:
            compiled.append(line)
    migrated_body = "\n".join([
        *compiled[:1],
        "",
        "## Compiled truth",
        "",
        *compiled[1:],
        "",
        "## Timeline",
        "",
        *(timeline or [f"- _at: {fallback_updated}  _source: vault://unknown", "  Migrated from a v3 concept page with no usable evidence entries."]),
    ]).strip() + "\n"
    return (fm + "\n" + migrated_body) if fm else migrated_body
```

Then implement `migrate_wiki_dir()` using `parse_frontmatter()` to select only `page_type: concept` pages with `compiler_version: concept-article-v3`, write backups under `runtime_dir / "garbage_collector" / f"wiki-pre-740-{timestamp}"`, and return unified diffs from `difflib.unified_diff()`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/auto-test-pytest shared-vault/skills/ingest/augur/tests/test_wiki_v4_migration.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_v4_migration.py shared-vault/skills/ingest/augur/tests/test_wiki_v4_migration.py
git commit -m "feat(wiki): add v3 to v4 concept migration"
```

---

## Phase 4 — Command Wiring and Docs

### Task 6: Wire migration and wiki command surfaces

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py`
- Modify: `shared-vault/skills/ingest/commands/wiki-update.md`
- Modify: `shared-vault/skills/ingest/commands/wiki-rebuild.md`
- Test: `shared-vault/skills/ingest/augur/tests/test_wiki_tools.py`

- [ ] **Step 1: Add tests for migration command plumbing**

Add tests that call the pure Python wiki tools entry point already used by nearby tests. The expected behavior:

```python
def test_wiki_v4_migration_dry_run_reports_changed_pages(tmp_path, monkeypatch):
    # Arrange a real v3 concept page in the monkeypatched wiki dir.
    # Call the new dry-run helper exposed from wiki_tools.py.
    # Assert success=True, apply=False, changed_pages contains the page, and no file was modified.
```

Use the existing monkeypatch pattern in `test_wiki_tools.py` for `get_wiki_dir()` and `get_runtime_dir()`.

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/ingest/augur/tests/test_wiki_tools.py`
Expected: FAIL because the migration entry point is absent.

- [ ] **Step 3: Implement command plumbing**

Add a private helper in `wiki_tools.py`:

```python
async def _run_wiki_migrate_v4(apply: bool = False) -> str:
    from src.config.paths import get_runtime_dir, get_wiki_dir
    from skills.ingest.scripts.wiki_v4_migration import migrate_wiki_dir

    result = migrate_wiki_dir(
        wiki_dir=get_wiki_dir(),
        runtime_dir=get_runtime_dir(),
        apply=bool(apply),
    )
    return json.dumps(
        {
            "success": True,
            "apply": bool(apply),
            "changed_pages": [str(path) for path in result.changed_pages],
            "backup_dir": str(result.backup_dir) if result.backup_dir else None,
            "diffs": result.diffs,
        },
        indent=2,
        default=str,
    )
```

Expose it through the existing wiki maintenance command pattern if there is already a command dispatcher slot; otherwise keep it as a pure helper used by the implementation session and document the one-shot script invocation in `wiki-update.md`.

- [ ] **Step 4: Update command docs**

In `wiki-update.md` and `wiki-rebuild.md`, add the invariant:

```markdown
Concept pages use ADR-740 v4 layout. `wiki-update` and `wiki-apply-concept-batch`
append cited observations to `## Timeline`; they do not overwrite an existing
`## Compiled truth` section. Truth changes are proposed through the rewrite
proposal flow and applied only by the explicit `wiki-apply-top-rewrite-proposal`
step.
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `/auto-test-pytest shared-vault/skills/ingest/augur/tests/test_wiki_tools.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/ingest/scripts/mcp/wiki_tools.py shared-vault/skills/ingest/commands/wiki-update.md shared-vault/skills/ingest/commands/wiki-rebuild.md shared-vault/skills/ingest/augur/tests/test_wiki_tools.py
git commit -m "feat(wiki): wire ADR-740 migration and command contract"
```

### Task 7: Update documentation and generated instructions

**Files:**
- Modify: `docs/agent-topics/WIKI.md`
- Generated: agent instruction outputs from `python3 -m skills.ai.scripts.sync_agents sync agents all`

- [ ] **Step 1: Patch WIKI topic doc**

Add to `docs/agent-topics/WIKI.md` under "Wiki Compounding":

```markdown
- Concept pages use the ADR-740 body split: `## Compiled truth` is human-owned and changed only by an explicit rewrite-proposal apply step; `## Timeline` is machine-owned and append-only with `_at:` and `_source:` on every entry.
- `wiki-update` and `wiki-apply-concept-batch` may create a new concept page with initial compiled truth, but for an existing v4 concept page they preserve compiled truth and append cited observations to the timeline.
```

- [ ] **Step 2: Regenerate instructions**

Run: `python3 -m skills.ai.scripts.sync_agents sync agents all`
Expected: generated agent instruction files refresh successfully.

- [ ] **Step 3: Commit**

```bash
git add docs/agent-topics/WIKI.md AGENTS.md CLAUDE.md GEMINI.md .codex/skills/adr/SKILL.md
git commit -m "docs(wiki): document compiled truth timeline contract"
```

---

## Phase 5 — Validation and Controlled Real-Data Migration

### Task 8: Focused test and stale-reference validation

**Files:** no source edits expected.

- [ ] **Step 1: Run focused Python tests**

Run: `/auto-test-pytest shared-vault/skills/ingest/augur/tests/test_wiki_timeline.py shared-vault/skills/ingest/augur/tests/test_wiki_v4_migration.py shared-vault/skills/ingest/augur/tests/test_wiki_concept_pages.py shared-vault/skills/ingest/augur/tests/test_wiki_quality.py shared-vault/skills/ingest/augur/tests/test_wiki_maintenance.py shared-vault/skills/ingest/augur/tests/test_wiki_tools.py`
Expected: PASS.

- [ ] **Step 2: Run repo lint loop**

Run: `/auto-lint`
Expected: PASS or auto-fixed changes staged for review.

- [ ] **Step 3: Scan stale references from the Impact Manifest**

Run these POSIX/macOS checks from the worktree:

```bash
rg -n "concept-article-v3|## Evidence|Compiled truth|Timeline|wiki-pre-740|wiki_timeline|wiki_v4_migration" shared-vault/skills/ingest docs tests
```

Expected: `concept-article-v3` remains only in migration tests, query-version compatibility, and explicit legacy warnings. Existing concept writers and docs should point at v4.

- [ ] **Step 4: Commit any validation-only fixes**

If stale references required edits:

```bash
git add <specific files>
git commit -m "fix(wiki): finish ADR-740 reference migration"
```

### Task 9: Real vault dry-run, manual gate, apply, and value validation

**Files:**
- Real data input: configured `get_wiki_dir()` (`Au-vault/wiki/`)
- Runtime backup output: `get_runtime_dir()/garbage_collector/wiki-pre-740-<timestamp>/`
- Vault output after approval: migrated concept pages in the configured vault repo

- [ ] **Step 1: Run migration dry-run on the real vault**

Run:

```bash
python3 - <<'PY'
import json
from src.config.paths import get_runtime_dir, get_wiki_dir
from skills.ingest.scripts.wiki_v4_migration import migrate_wiki_dir

result = migrate_wiki_dir(wiki_dir=get_wiki_dir(), runtime_dir=get_runtime_dir(), apply=False)
print(json.dumps({
    "changed_count": len(result.changed_pages),
    "sample_pages": [str(path) for path in result.changed_pages[:5]],
    "has_diffs": bool(result.diffs),
}, indent=2))
PY
```

Expected: nonzero `changed_count` on a vault that still has v3 concept pages, with sample real concept page paths.

- [ ] **Step 2: STOP for manual verification before applying**

Show the user:
- changed page count
- five sample pages
- one representative diff
- the planned backup root under `get_runtime_dir()/garbage_collector/wiki-pre-740-<timestamp>/`

Do not run apply until the user confirms.

- [ ] **Step 3: Apply migration after confirmation**

Run:

```bash
python3 - <<'PY'
import json
from src.config.paths import get_runtime_dir, get_wiki_dir
from skills.ingest.scripts.wiki_v4_migration import migrate_wiki_dir

result = migrate_wiki_dir(wiki_dir=get_wiki_dir(), runtime_dir=get_runtime_dir(), apply=True)
print(json.dumps({
    "changed_count": len(result.changed_pages),
    "backup_dir": str(result.backup_dir) if result.backup_dir else None,
    "sample_pages": [str(path) for path in result.changed_pages[:5]],
}, indent=2))
PY
```

Expected: backup directory exists and contains the pre-migration copies; changed pages now contain `## Compiled truth`, `## Timeline`, and `compiler_version: concept-article-v4`.

- [ ] **Step 4: Run wiki lint/status on real data**

Run the canonical wiki checks through the existing command surface:

```bash
python3 - <<'PY'
import asyncio
import json
from skills.ingest.scripts.mcp import wiki_tools

async def main():
    print(await wiki_tools._run_wiki_update(limit=1))

asyncio.run(main())
PY
```

Then run the existing `wiki-lint` surface used by this repo. Expected value evidence:
- a real migrated concept page path
- compiled truth text preserved
- timeline entries with `_at:` and `_source:`
- no malformed-timeline lint errors on migrated pages

- [ ] **Step 5: Commit vault changes separately if the vault repo is dirty**

If `get_wiki_dir()` is inside the configured Au-vault repo, commit the vault payload separately from code:

```bash
VAULT_ROOT="$(python3 - <<'PY'
from src.config.paths import get_vault_dir
print(get_vault_dir())
PY
)"
git -C "$VAULT_ROOT" status --short
git -C "$VAULT_ROOT" add wiki/concepts
git -C "$VAULT_ROOT" commit -m "data(wiki): migrate concept pages to ADR-740 timeline schema"
```

Use the actual vault path from `src.config.paths`, not a hardcoded path in scripts.

### Task 10: ADR closeout after implementation

**Files:**
- Modify: `docs/adrs/ADR-740-compiled-truth-and-timeline-wiki-pattern.md`
- Generated: `docs/adrs/adrs-index.json`, `docs/generated/adr-index.md`, ADR RAG index outputs, generated agent instructions

- [ ] **Step 1: Run completion gates**

Run:
- `/auto-test-pytest`
- `/auto-lint`
- targeted wiki value-validation commands from Task 9

Expected: all pass, and real data shows at least one migrated concept page with useful compiled truth over cited timeline entries.

- [ ] **Step 2: Flip ADR status only after gates pass**

Run the ADR status update path:

```bash
/adr set 740 Implemented
```

Expected: ADR-740 status becomes Implemented and the ADR post-write hook regenerates central ADR JSON, markdown ADR index, ADR RAG pointer index, and agent instructions.

- [ ] **Step 3: Commit ADR closeout**

```bash
git add docs/adrs/ADR-740-compiled-truth-and-timeline-wiki-pattern.md docs/adrs/adrs-index.json docs/generated/adr-index.md
git add <generated agent instruction files touched by sync_agents>
git commit -m "docs(adr): mark ADR-740 implemented"
```

---

## Completion Gates

- All v4 helper, writer, migration, quality, maintenance, and wiki-tool tests pass through `/auto-test-pytest`.
- `wiki-update`, `wiki-apply-concept-batch`, and `wiki-apply-top-rewrite-proposal` preserve `## Compiled truth` for existing v4 concept pages and append cited timeline entries.
- `wiki-lint` reports malformed timeline entries as failures and out-of-order timeline entries as warnings.
- The migration dry-run shows real changed concept pages before apply.
- The migration apply creates a runtime backup under `get_runtime_dir()/garbage_collector/wiki-pre-740-<timestamp>/`.
- Real vault value validation names at least one migrated concept page and shows useful compiled truth plus timeline entries carrying `_at:` and `_source:`.
- ADR-740 is marked Implemented only after code, docs, tests, real-data migration, and generated indexes are complete.
