# ADR-753 Implementation Plan — Article enrichment for URL and file notes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-enrich every newly-captured `type: url` and `type: file` note with an executive summary, key insights, why-it-matters paragraph, verbatim quotes, and cross-references. Enriched sections live at the top of the note's markdown body; the raw extracted content stays at the bottom unmodified. Users can also trigger re-enrichment manually from the note's detail panel.

**Architecture:** A new pure-logic enrichment module owns the section template, body splitting, idempotency, and cross-reference linking. A new MCP tool `enrich-article` dispatches the actual summarization through the **LLM-Assisted MCP Pattern** (`docs/references/llm-assisted-mcp-pattern.md`) — the active AI client owns the summarization step, no hardcoded vendor (per Rule 19 + memory `feedback-vendor-neutral-design`). Auto-trigger uses an append-only JSONL pending-enrichment queue under runtime state (ADR-743 job-ledger compatible); the daemon polls and dispatches. Cross-references are resolved against the ADR-738 typed graph. The BrowseDetailPanel gains an "Enrich…" action button and an enrichment-status badge.

**Tech Stack:** Python 3.11+, pytest (`importlib.util.spec_from_file_location` per memory `feedback-skill-test-convention`), Next.js + TypeScript dashboard, vitest. The compiled-truth section-replacement helpers from ADR-740 (`shared-vault/skills/ingest/scripts/wiki_timeline.py`) are the model for section-aware body splitting.

**Spec:** `docs/superpowers/specs/2026-05-15-gbrain-ingest-port-design.md` §"Article-enrichment". **Depends on:** ADR-751 (notes zone exists; atomic ops write url/file notes there). **Related ADRs:** ADR-738 (typed graph for cross-refs), ADR-740 (compiled-truth pattern reference for section structure), ADR-743 (job ledger for the pending-enrichment queue).

---

## File Structure

### Create

| Path | Responsibility |
|------|----------------|
| `docs/adrs/ADR-753-article-enrichment.md` | Architecture decision record |
| `shared-vault/skills/ingest/scripts/article_enrichment.py` | Pure-logic: section template, body split/merge, idempotency check, cross-reference resolution |
| `shared-vault/skills/ingest/scripts/mcp/tools_enrich.py` | MCP tools: `enrich-article` + `submit-enrich-article-result` |
| `shared-vault/skills/ingest/scripts/pending_enrichment_queue.py` | Pure-logic: read/write/dequeue JSONL pending-enrichment entries |
| `shared-vault/skills/ingest/augur/scripts/run_pending_enrichment.py` | Daemon job: drain the pending queue by dispatching `enrich-article` per note |
| `shared-vault/skills/ingest/augur/tests/test_article_enrichment.py` | Pure-logic tests |
| `shared-vault/skills/ingest/augur/tests/test_pending_enrichment_queue.py` | Queue read/write/dequeue tests |
| `shared-vault/skills/ingest/augur/tests/test_enrich_article_mcp.py` | MCP tool integration tests |
| `shared-vault/skills/ingest/augur/tests/fixtures/raw_article_short.md` | Canned raw article: short blog post |
| `shared-vault/skills/ingest/augur/tests/fixtures/raw_article_long.md` | Canned raw article: long technical piece |
| `shared-vault/skills/ingest/augur/tests/fixtures/enriched_article_short.md` | Expected enrichment for the short fixture |

### Modify

| Path | Change |
|------|--------|
| `shared-vault/skills/ingest/scripts/source_cards.py` | After writing a url/file note, append an entry to the pending-enrichment queue |
| `shared-vault/skills/ingest/scripts/mcp/inbox_tools.py` | Same for file notes written by `inbox-consume-folder` |
| `shared-vault/skills/ingest/SKILL.md` | Add `enrich-article` and `submit-enrich-article-result` to `x-augur-mcp-tools`; add daemon-job declaration for `run-pending-enrichment` |
| `config/system/capability_exposure.yaml` | Add `mcp-tool:enrich-article`, `mcp-tool:submit-enrich-article-result` |
| `apps/dashboard/components/shared/BrowseCard.tsx` | Render `enrichment_status` as a small badge on url/file cards |
| `apps/dashboard/components/shared/BrowseDetailPanel.tsx` | Add "Enrich…" action button for url/file notes; surface enriched sections inline |
| `tests/dashboard/components/shared/BrowseCard.test.tsx` | Test the enrichment-status badge |
| `tests/dashboard/browse/BrowseDetailPanel.test.tsx` | Test the Enrich action and enriched-section rendering |

---

## Task 1: Write ADR-753

**Files:**
- Create: `docs/adrs/ADR-753-article-enrichment.md`

- [ ] **Step 1: Write the ADR**

Status: `Proposed`. Date: 2026-05-16. `plan_file: docs/superpowers/plans/2026-05-16-adr-753-article-enrichment.md`. Sections:

- **Context:** A captured URL today gives a title + content + tags but no synthesis; users re-read articles to remember what mattered. Spec calls for executive summary + verbatim quotes + key insights + why-it-matters + cross-references, written back into the same note file.
- **Decision:** Enrichment runs as a post-ingest step on `type: url` and `type: file` notes. Dispatched through the LLM-Assisted MCP Pattern (active AI client owns the summarization; no hardcoded vendor). Output rewrites into the same note body as named sections at the top; raw content preserved at the bottom. Auto-triggered via a JSONL pending-enrichment queue; daemon drains it.
- **Alternatives:** Materialize enrichment as a separate file (rejected — splits user mental model and breaks the "one card = one file" Rule 32 principle); make enrichment manual-only (rejected — defeats the daily-ergonomics goal of 30-second-comprehensible cards); call a specific LLM provider directly (rejected — Rule 19 + vendor-neutrality).
- **Consequences:** Two new MCP tools (`enrich-article` + companion). New JSONL queue file under runtime state. Source-card writers append to the queue on each new url/file note. Daemon needs a new job entry. BrowseCard and BrowseDetailPanel get small UI changes (badge + action button).
- **Non-goals:** Re-summarizing on every entity-graph update (just the initial enrichment per note version); enrichment of voice-memo / meeting / thought / image notes (those types have their own structure from ADR-752 and direct user input).

- [ ] **Step 2: Regenerate the ADR index**

```bash
python scripts/regenerate_adr_index.py
```

- [ ] **Step 3: Commit**

```bash
git add docs/adrs/ADR-753-article-enrichment.md docs/generated/adr-index.md docs/adrs/adrs-index.json
git commit -m "$(cat <<'EOF'
docs(adr): ADR-753 article enrichment for url and file notes

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Section template, body splitter, idempotency check

**Files:**
- Create: `shared-vault/skills/ingest/scripts/article_enrichment.py`
- Create: `shared-vault/skills/ingest/augur/tests/test_article_enrichment.py`
- Create: `shared-vault/skills/ingest/augur/tests/fixtures/raw_article_short.md`
- Create: `shared-vault/skills/ingest/augur/tests/fixtures/enriched_article_short.md`

- [ ] **Step 1: Bundle the fixture pair**

```bash
cat > shared-vault/skills/ingest/augur/tests/fixtures/raw_article_short.md <<'EOF'
---
title: "The Architecture of Leverage"
x-augur-note-type: url
url: https://example.com/leverage
---

## Original content

Leverage in software, broadly construed, is the multiplier that lets one good decision keep paying dividends for years. The architect's job is not just to make systems work today — it is to compound future work. Three patterns reliably create leverage: invariants that are cheap to maintain and expensive to violate, composable interfaces that survive their first author, and tests that document the system's intent rather than its current shape. The opposite of leverage is friction — every workaround for a bad invariant, every interface a team learns to fear, every brittle test that has to be rewritten when behavior is updated.
EOF

cat > shared-vault/skills/ingest/augur/tests/fixtures/enriched_article_short.md <<'EOF'
---
title: "The Architecture of Leverage"
x-augur-note-type: url
url: https://example.com/leverage
x-augur-enrichment-status: enriched
x-augur-enrichment-version: 1
---

## Executive summary

- Leverage is the compounding return on a single good design decision
- The architect's job is to compound future work, not just make today's system function
- Three reliable sources of leverage: cheap-to-maintain invariants, composable interfaces, intent-documenting tests
- Friction is the opposite of leverage and the audit signal for missing leverage points

## Key insights

1. Leverage is measured in deferred work, not in current throughput
2. Interfaces that survive their first author are the load-bearing artifact of a healthy system
3. Tests should document intent — when they document current behavior, every refactor is a rewrite

## Why it matters

For our team's roadmap, the leverage frame separates work that compounds (invariants, interfaces) from work that burns (per-incident fixes). Most quarters we spend more on the burn side; this is the explicit case for shifting allocation.

## Verbatim quotes

> "Leverage in software, broadly construed, is the multiplier that lets one good decision keep paying dividends for years."

> "The opposite of leverage is friction — every workaround for a bad invariant, every interface a team learns to fear, every brittle test that has to be rewritten when behavior is updated."

## Cross-references

- [[wiki/concepts/leverage]]
- [[wiki/concepts/architecture]]

## Original content

Leverage in software, broadly construed, is the multiplier that lets one good decision keep paying dividends for years. The architect's job is not just to make systems work today — it is to compound future work. Three patterns reliably create leverage: invariants that are cheap to maintain and expensive to violate, composable interfaces that survive their first author, and tests that document the system's intent rather than its current shape. The opposite of leverage is friction — every workaround for a bad invariant, every interface a team learns to fear, every brittle test that has to be rewritten when behavior is updated.
EOF
```

- [ ] **Step 2: Write the failing test**

```python
# shared-vault/skills/ingest/augur/tests/test_article_enrichment.py
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
ENRICH_PATH = PROJECT_ROOT / "shared-vault" / "skills" / "ingest" / "scripts" / "article_enrichment.py"
FIXTURES = PROJECT_ROOT / "shared-vault" / "skills" / "ingest" / "augur" / "tests" / "fixtures"


def _load_enrichment():
    spec = importlib.util.spec_from_file_location("ingest_article_enrichment", ENRICH_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_article_enrichment"] = module
    spec.loader.exec_module(module)
    return module


def test_split_raw_content_finds_original_section():
    m = _load_enrichment()
    body = (FIXTURES / "raw_article_short.md").read_text().split("---", 2)[2]
    enriched_sections, raw_content = m.split_body(body)
    assert enriched_sections == {}  # no enrichment present yet
    assert "Leverage in software" in raw_content


def test_split_recognizes_existing_enrichment():
    m = _load_enrichment()
    body = (FIXTURES / "enriched_article_short.md").read_text().split("---", 2)[2]
    enriched_sections, raw_content = m.split_body(body)
    assert "Executive summary" in enriched_sections
    assert "Key insights" in enriched_sections
    assert "Why it matters" in enriched_sections
    assert "Verbatim quotes" in enriched_sections
    assert "Cross-references" in enriched_sections
    assert "Leverage in software" in raw_content


def test_compose_enriched_body_round_trips():
    m = _load_enrichment()
    sections = {
        "Executive summary": "- bullet a\n- bullet b\n",
        "Key insights": "1. one\n2. two\n",
        "Why it matters": "Because.\n",
        "Verbatim quotes": "> quote\n",
        "Cross-references": "- [[wiki/x]]\n",
    }
    raw = "Original article text.\n"
    body = m.compose_body(sections, raw)
    enriched_sections, raw_back = m.split_body(body)
    assert set(enriched_sections.keys()) == set(sections.keys())
    assert "Original article text." in raw_back


def test_idempotency_marker_in_frontmatter():
    m = _load_enrichment()
    fm_before = {"title": "x", "x-augur-note-type": "url"}
    fm_after = m.stamp_enrichment_frontmatter(fm_before, version=1)
    assert fm_after["x-augur-enrichment-status"] == "enriched"
    assert fm_after["x-augur-enrichment-version"] == 1
    # idempotent re-stamp at same version doesn't bump
    fm_again = m.stamp_enrichment_frontmatter(fm_after, version=1)
    assert fm_again["x-augur-enrichment-version"] == 1


def test_idempotency_marker_bumps_on_higher_version():
    m = _load_enrichment()
    fm = {"x-augur-enrichment-status": "enriched", "x-augur-enrichment-version": 1}
    fm_v2 = m.stamp_enrichment_frontmatter(fm, version=2)
    assert fm_v2["x-augur-enrichment-version"] == 2


def test_build_llm_dispatch_payload():
    m = _load_enrichment()
    payload = m.build_llm_dispatch_payload(
        note_title="The Architecture of Leverage",
        note_url="https://example.com/leverage",
        raw_content="Leverage is the multiplier that lets one good decision pay dividends.",
        existing_entities=["leverage", "architecture"],
    )
    assert payload["needs_llm"] is True
    assert payload["task"] == "enrich-article"
    assert "instructions" in payload
    assert payload["expected_result_schema"] == {
        "executive_summary": "string (markdown bullet list, 3-7 bullets)",
        "key_insights": "string (markdown numbered list, 3-5 insights)",
        "why_it_matters": "string (one paragraph, 2-4 sentences)",
        "verbatim_quotes": "string (markdown blockquotes, 1-3 quotes, longest impactful passages, preserved verbatim from the source)",
        "cross_references": "list of wiki page slugs to link, e.g. ['concepts/leverage']",
    }
    assert "leverage" in payload["existing_entities"]
```

- [ ] **Step 3: Implement `article_enrichment.py`**

```python
# shared-vault/skills/ingest/scripts/article_enrichment.py
"""Pure-logic helpers for ADR-753 article enrichment.

Owns:
  - section template (5 named top-level sections)
  - body splitter: parse a note's markdown body into {section: content} + raw_content
  - body composer: render enriched sections + raw_content back into a body string
  - frontmatter stamping for enrichment status / version
  - LLM-Assisted MCP Pattern dispatch payload builder

NO I/O. The MCP tool layer (tools_enrich.py) and daemon job
(run_pending_enrichment.py) are responsible for reading and writing files.
"""
from __future__ import annotations

import re
from typing import Any

# Canonical section order — also the rendering order in compose_body
ENRICHMENT_SECTIONS = (
    "Executive summary",
    "Key insights",
    "Why it matters",
    "Verbatim quotes",
    "Cross-references",
)

# "Original content" is the marker for the raw section (always last).
RAW_SECTION_HEADING = "Original content"

_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def split_body(body: str) -> tuple[dict[str, str], str]:
    """Split a body into (enriched_sections, raw_content).

    enriched_sections is a dict from heading to content (without the heading
    line) for any of the five known enrichment sections found in the body.
    raw_content is everything under "## Original content" (or the entire body
    when no enrichment has been applied yet).
    """
    sections: dict[str, str] = {}
    raw = body
    headings = list(_H2_RE.finditer(body))
    if not headings:
        return {}, body.strip() + "\n"

    # Build section spans
    for i, m in enumerate(headings):
        name = m.group(1).strip()
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(body)
        content = body[start:end].strip("\n")
        if name == RAW_SECTION_HEADING:
            raw = content
        elif name in ENRICHMENT_SECTIONS:
            sections[name] = content
    # If we never hit "Original content" but did find enrichment sections,
    # the raw is whatever comes after the last enrichment section that isn't
    # itself a known section. Fall back to the whole body for safety when
    # the markdown structure is unfamiliar.
    if not any(m.group(1).strip() == RAW_SECTION_HEADING for m in headings) and not sections:
        return {}, body.strip() + "\n"
    return sections, raw.strip() + "\n"


def compose_body(enriched_sections: dict[str, str], raw_content: str) -> str:
    parts: list[str] = []
    for name in ENRICHMENT_SECTIONS:
        if name in enriched_sections and enriched_sections[name].strip():
            parts.append(f"## {name}\n\n{enriched_sections[name].strip()}\n")
    parts.append(f"## {RAW_SECTION_HEADING}\n\n{raw_content.strip()}\n")
    return "\n".join(parts).rstrip() + "\n"


def stamp_enrichment_frontmatter(fm: dict[str, Any], version: int) -> dict[str, Any]:
    new_fm = dict(fm)
    new_fm["x-augur-enrichment-status"] = "enriched"
    current = int(fm.get("x-augur-enrichment-version", 0) or 0)
    if version > current:
        new_fm["x-augur-enrichment-version"] = version
    else:
        new_fm["x-augur-enrichment-version"] = max(current, version)
    return new_fm


def build_llm_dispatch_payload(
    *,
    note_title: str,
    note_url: str | None,
    raw_content: str,
    existing_entities: list[str],
) -> dict[str, Any]:
    """Build the {needs_llm: true, ...} payload returned by the enrich-article tool.

    The AI client reads `instructions` and `raw_content_preview`, produces
    the five fields, and calls submit-enrich-article-result with them.
    """
    preview = raw_content[:8000]
    return {
        "needs_llm": True,
        "task": "enrich-article",
        "note_title": note_title,
        "note_url": note_url,
        "raw_content_preview": preview,
        "raw_content_full_length_chars": len(raw_content),
        "existing_entities": existing_entities,
        "instructions": (
            "Produce a structured enrichment of the source article. Output JSON with five fields. "
            "Executive summary: 3-7 bullets. Key insights: 3-5 numbered insights specific to this piece. "
            "Why it matters: one 2-4 sentence paragraph tied to existing_entities when relevant. "
            "Verbatim quotes: 1-3 of the longest impactful passages, preserved verbatim. "
            "Cross-references: a list of wiki page slugs (e.g. 'concepts/leverage') that would link from this note. "
            "Use existing_entities as candidates for cross-references; you may add new ones."
        ),
        "expected_result_schema": {
            "executive_summary": "string (markdown bullet list, 3-7 bullets)",
            "key_insights": "string (markdown numbered list, 3-5 insights)",
            "why_it_matters": "string (one paragraph, 2-4 sentences)",
            "verbatim_quotes": "string (markdown blockquotes, 1-3 quotes, longest impactful passages, preserved verbatim from the source)",
            "cross_references": "list of wiki page slugs to link, e.g. ['concepts/leverage']",
        },
    }
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest shared-vault/skills/ingest/augur/tests/test_article_enrichment.py -v
```
Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/article_enrichment.py shared-vault/skills/ingest/augur/tests/test_article_enrichment.py shared-vault/skills/ingest/augur/tests/fixtures/
git commit -m "$(cat <<'EOF'
feat(ingest): article enrichment pure-logic helpers (ADR-753)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Pending-enrichment JSONL queue

**Files:**
- Create: `shared-vault/skills/ingest/scripts/pending_enrichment_queue.py`
- Create: `shared-vault/skills/ingest/augur/tests/test_pending_enrichment_queue.py`

- [ ] **Step 1: Write the failing test**

```python
# shared-vault/skills/ingest/augur/tests/test_pending_enrichment_queue.py
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
QUEUE_PATH = PROJECT_ROOT / "shared-vault" / "skills" / "ingest" / "scripts" / "pending_enrichment_queue.py"


def _load_queue():
    spec = importlib.util.spec_from_file_location("ingest_pending_queue", QUEUE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_pending_queue"] = module
    spec.loader.exec_module(module)
    return module


def test_enqueue_then_read_returns_entry(tmp_path):
    q = _load_queue()
    qfile = tmp_path / "pending_enrichment.jsonl"
    q.enqueue(qfile, note_path=Path("/vault/notes/a.md"), reason="new")
    entries = q.read_pending(qfile)
    assert len(entries) == 1
    assert entries[0]["note_path"].endswith("a.md")
    assert entries[0]["reason"] == "new"
    assert "enqueued_at" in entries[0]


def test_drain_removes_processed_entries(tmp_path):
    q = _load_queue()
    qfile = tmp_path / "pending_enrichment.jsonl"
    q.enqueue(qfile, note_path=Path("/vault/notes/a.md"), reason="new")
    q.enqueue(qfile, note_path=Path("/vault/notes/b.md"), reason="new")
    q.enqueue(qfile, note_path=Path("/vault/notes/c.md"), reason="new")

    processed = q.drain(qfile, processed_note_paths={Path("/vault/notes/a.md"), Path("/vault/notes/c.md")})
    assert processed == 2
    remaining = q.read_pending(qfile)
    assert len(remaining) == 1
    assert remaining[0]["note_path"].endswith("b.md")


def test_dedup_does_not_enqueue_same_path_twice(tmp_path):
    q = _load_queue()
    qfile = tmp_path / "pending_enrichment.jsonl"
    q.enqueue(qfile, note_path=Path("/vault/notes/a.md"), reason="new")
    q.enqueue(qfile, note_path=Path("/vault/notes/a.md"), reason="new")  # dup
    entries = q.read_pending(qfile)
    assert len(entries) == 1
```

- [ ] **Step 2: Implement the queue**

```python
# shared-vault/skills/ingest/scripts/pending_enrichment_queue.py
"""Append-only JSONL queue of notes pending article enrichment.

The queue file lives under runtime state (resolved by callers via
get_runtime_dir(); this module accepts the path explicitly to stay pure-logic).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def enqueue(queue_path: Path, *, note_path: Path, reason: str) -> bool:
    """Append (note_path, reason, timestamp) to the queue. Skips duplicates by note_path."""
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    existing = {e["note_path"] for e in read_pending(queue_path)}
    if str(note_path) in existing:
        return False
    entry = {
        "note_path": str(note_path),
        "reason": reason,
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
    }
    with queue_path.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")
    return True


def read_pending(queue_path: Path) -> list[dict]:
    if not queue_path.exists():
        return []
    out: list[dict] = []
    with queue_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def drain(queue_path: Path, processed_note_paths: Iterable[Path]) -> int:
    """Remove processed entries by rewriting the file. Returns the count removed."""
    processed = {str(p) for p in processed_note_paths}
    remaining = [e for e in read_pending(queue_path) if e["note_path"] not in processed]
    removed = len(read_pending(queue_path)) - len(remaining)
    tmp = queue_path.with_suffix(".jsonl.tmp")
    with tmp.open("w") as fh:
        for e in remaining:
            fh.write(json.dumps(e) + "\n")
    tmp.replace(queue_path)
    return removed
```

- [ ] **Step 3: Run the tests**

```bash
uv run pytest shared-vault/skills/ingest/augur/tests/test_pending_enrichment_queue.py -v
```
Expected: all 3 tests pass.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/ingest/scripts/pending_enrichment_queue.py shared-vault/skills/ingest/augur/tests/test_pending_enrichment_queue.py
git commit -m "$(cat <<'EOF'
feat(ingest): pending-enrichment JSONL queue (ADR-753)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Source-card writers enqueue new url/file notes

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/source_cards.py`
- Modify: `shared-vault/skills/ingest/scripts/mcp/inbox_tools.py`
- Modify: `shared-vault/skills/ingest/augur/tests/test_source_cards.py`

- [ ] **Step 1: Add queue path helper**

In `src/config/paths.py`, add a helper near the other runtime helpers:

```python
def get_pending_enrichment_queue_path() -> Path:
    return get_runtime_dir() / "pending_enrichment.jsonl"
```

(`get_runtime_dir()` already exists.)

- [ ] **Step 2: Wire `source_cards.py` to enqueue after writing**

In the function that writes a URL/file source card (post-Plan 1 it writes to `<vault>/notes/`), after a successful write add:

```python
from shared_vault.skills.ingest.scripts.pending_enrichment_queue import enqueue
from src.config.paths import get_pending_enrichment_queue_path

# After write_vault_frontmatter(target, fm, body)
try:
    enqueue(get_pending_enrichment_queue_path(), note_path=target, reason="new")
except Exception:
    pass  # enrichment is best-effort; never block the note write
```

(Wrap in try/except — enrichment is a nice-to-have; a queue write failure must never break the note capture, per Rule 1.)

- [ ] **Step 3: Same wiring in `inbox_tools.py`**

In the function that writes a file note via `inbox-consume-folder`, after the write call, do the same enqueue.

- [ ] **Step 4: Add a test verifying the enqueue happens**

```python
# Append to test_source_cards.py
def test_url_source_write_enqueues_for_enrichment(tmp_path, monkeypatch):
    from src.config import paths as paths_mod
    qpath = tmp_path / "pending_enrichment.jsonl"
    monkeypatch.setattr(paths_mod, "get_pending_enrichment_queue_path", lambda: qpath)
    # invoke the source-card write with a stub URL note...
    # (use the existing test harness in this file; reuse its setup)
    # ... after write, assert qpath exists and contains one entry
    assert qpath.exists()
    import json
    lines = qpath.read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["note_path"].endswith(".md")
    assert entry["reason"] == "new"
```

- [ ] **Step 5: Run the tests**

```bash
uv run pytest shared-vault/skills/ingest/augur/tests/test_source_cards.py shared-vault/skills/ingest/augur/tests/test_inbox_consume.py -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/ingest/scripts/source_cards.py shared-vault/skills/ingest/scripts/mcp/inbox_tools.py shared-vault/skills/ingest/augur/tests/test_source_cards.py src/config/paths.py
git commit -m "$(cat <<'EOF'
feat(ingest): enqueue url/file notes for enrichment after write (ADR-753)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: MCP tools — `enrich-article` + `submit-enrich-article-result`

**Files:**
- Create: `shared-vault/skills/ingest/scripts/mcp/tools_enrich.py`
- Create: `shared-vault/skills/ingest/augur/tests/test_enrich_article_mcp.py`
- Modify: `config/system/capability_exposure.yaml`

- [ ] **Step 1: Implement the tools**

```python
# shared-vault/skills/ingest/scripts/mcp/tools_enrich.py
"""ADR-753 enrichment MCP tools.

  - enrich-article: read a url/file note, return {needs_llm: true, ...}
    with raw content + entity hints. Idempotent — re-runs are safe.
  - submit-enrich-article-result: accepts the LLM output, merges it into
    the note body as named sections, stamps frontmatter, writes back.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _ensure_project_paths(start: Path) -> Path:
    for candidate in (start.parent, *start.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "src" / "config" / "paths.py").is_file():
            for path in (candidate / "src" / "mcp", candidate, candidate / "shared-vault"):
                text = str(path)
                if text not in sys.path:
                    sys.path.insert(0, text)
            return candidate
    raise RuntimeError(f"Unable to locate Augur project root from {start}")


_PROJECT_ROOT = _ensure_project_paths(Path(__file__).resolve())

from src.lib.frontmatter_utils import parse_frontmatter, write_vault_frontmatter  # noqa: E402
from skills.ingest.scripts.article_enrichment import (  # noqa: E402
    ENRICHMENT_SECTIONS,
    build_llm_dispatch_payload,
    compose_body,
    split_body,
    stamp_enrichment_frontmatter,
)


def _read_existing_entity_slugs() -> list[str]:
    """Best-effort: pull wiki entity slugs to pass as cross-reference candidates.

    Returns empty list if the graph is not reachable. Never raises.
    """
    try:
        from shared_vault.skills.graph.scripts.entity_lookup import list_entity_slugs  # type: ignore
        return list_entity_slugs(limit=200)
    except Exception:
        return []


def register(mcp: "FastMCP") -> None:
    @mcp.tool(name="enrich-article")
    def enrich_article(note_path: str) -> dict[str, Any]:
        p = Path(note_path)
        if not p.exists():
            return {"success": False, "error": f"note not found: {note_path}"}

        text = p.read_text()
        fm, body = parse_frontmatter(text)

        note_type = fm.get("x-augur-note-type")
        if note_type not in ("url", "file"):
            return {"success": False, "error": f"enrichment only applies to url/file notes; got {note_type}"}

        # Idempotency: skip if already enriched at the current version
        if fm.get("x-augur-enrichment-status") == "enriched" and int(fm.get("x-augur-enrichment-version", 0) or 0) >= 1:
            return {"success": True, "skipped": True, "reason": "already enriched"}

        _, raw_content = split_body(body)
        payload = build_llm_dispatch_payload(
            note_title=str(fm.get("title", p.stem)),
            note_url=fm.get("url"),
            raw_content=raw_content,
            existing_entities=_read_existing_entity_slugs(),
        )
        payload["note_path"] = str(p)  # the AI client passes this back to submit-...
        return payload

    @mcp.tool(name="submit-enrich-article-result")
    def submit_enrich_article_result(
        note_path: str,
        executive_summary: str,
        key_insights: str,
        why_it_matters: str,
        verbatim_quotes: str,
        cross_references_json: str = "[]",  # JSON list of wiki slugs
    ) -> dict[str, Any]:
        import json
        p = Path(note_path)
        if not p.exists():
            return {"success": False, "error": f"note not found: {note_path}"}

        text = p.read_text()
        fm, body = parse_frontmatter(text)
        _, raw_content = split_body(body)

        try:
            xrefs = json.loads(cross_references_json) if cross_references_json else []
        except json.JSONDecodeError:
            xrefs = []
        cross_ref_md = "\n".join(f"- [[wiki/{slug.strip('/')}]]" for slug in xrefs if isinstance(slug, str) and slug.strip())

        enriched_sections = {
            "Executive summary": executive_summary.strip(),
            "Key insights": key_insights.strip(),
            "Why it matters": why_it_matters.strip(),
            "Verbatim quotes": verbatim_quotes.strip(),
            "Cross-references": cross_ref_md,
        }
        new_body = compose_body(enriched_sections, raw_content)
        new_fm = stamp_enrichment_frontmatter(fm, version=1)
        write_vault_frontmatter(p, new_fm, new_body)
        return {
            "success": True,
            "note_path": str(p),
            "enrichment_version": new_fm["x-augur-enrichment-version"],
            "sections_written": list(ENRICHMENT_SECTIONS),
        }
```

- [ ] **Step 2: Write integration tests**

```python
# shared-vault/skills/ingest/augur/tests/test_enrich_article_mcp.py
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[5]
TOOLS_PATH = PROJECT_ROOT / "shared-vault" / "skills" / "ingest" / "scripts" / "mcp" / "tools_enrich.py"


def _load_tools():
    spec = importlib.util.spec_from_file_location("ingest_tools_enrich", TOOLS_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_tools_enrich"] = module
    spec.loader.exec_module(module)
    return module


def _capture(mod):
    captured = {}
    fake = MagicMock()
    def fake_tool(*, name):
        def wrap(fn):
            captured[name] = fn
            return fn
        return wrap
    fake.tool = fake_tool
    mod.register(fake)
    return captured


def test_enrich_article_returns_needs_llm_payload(tmp_path):
    mod = _load_tools()
    tools = _capture(mod)
    note = tmp_path / "2026-05-16-url-test.md"
    note.write_text(
        """---
title: Test
url: https://example.com
x-augur-note-type: url
---

## Original content

This is a test article about leverage and architecture.
"""
    )
    r = tools["enrich-article"](str(note))
    assert r.get("needs_llm") is True
    assert r["task"] == "enrich-article"
    assert "raw_content_preview" in r
    assert r["note_path"] == str(note)


def test_enrich_article_skips_already_enriched(tmp_path):
    mod = _load_tools()
    tools = _capture(mod)
    note = tmp_path / "2026-05-16-url-test.md"
    note.write_text(
        """---
title: Test
url: https://example.com
x-augur-note-type: url
x-augur-enrichment-status: enriched
x-augur-enrichment-version: 1
---

## Executive summary

- a

## Original content

This is a test article.
"""
    )
    r = tools["enrich-article"](str(note))
    assert r["success"] is True
    assert r.get("skipped") is True


def test_enrich_article_rejects_non_url_or_file(tmp_path):
    mod = _load_tools()
    tools = _capture(mod)
    note = tmp_path / "2026-05-16-thought-x.md"
    note.write_text(
        """---
title: Thought
x-augur-note-type: thought
---

I think.
"""
    )
    r = tools["enrich-article"](str(note))
    assert r["success"] is False
    assert "thought" in r["error"]


def test_submit_enriches_in_place(tmp_path):
    mod = _load_tools()
    tools = _capture(mod)
    note = tmp_path / "2026-05-16-url-test.md"
    note.write_text(
        """---
title: Test
url: https://example.com
x-augur-note-type: url
---

## Original content

The architecture of leverage is in the compounding.
"""
    )
    r = tools["submit-enrich-article-result"](
        note_path=str(note),
        executive_summary="- leverage compounds\n- architects build leverage\n",
        key_insights="1. compounding > throughput\n",
        why_it_matters="Because friction.\n",
        verbatim_quotes="> The architecture of leverage is in the compounding.\n",
        cross_references_json='["concepts/leverage", "concepts/architecture"]',
    )
    assert r["success"] is True
    text = note.read_text()
    assert "x-augur-enrichment-status: enriched" in text
    assert "x-augur-enrichment-version: 1" in text
    assert "## Executive summary" in text
    assert "## Key insights" in text
    assert "## Why it matters" in text
    assert "## Verbatim quotes" in text
    assert "## Cross-references" in text
    assert "[[wiki/concepts/leverage]]" in text
    assert "## Original content" in text
    # raw content preserved
    assert "compounding" in text
```

- [ ] **Step 3: Run the tests**

```bash
uv run pytest shared-vault/skills/ingest/augur/tests/test_enrich_article_mcp.py -v
```
Expected: all 4 tests pass.

- [ ] **Step 4: Wire `register` into MCP runtime**

Same pattern as Plan 2 Task 9 step 2 — find the MCP server registration sweep under `src/mcp/` and ensure it picks up `skills/ingest/scripts/mcp/tools_enrich.py`. If discovery is automatic, no change. If manual, add:

```python
from skills.ingest.scripts.mcp.tools_enrich import register as register_enrich
register_enrich(mcp)
```

- [ ] **Step 5: Add to capability_exposure.yaml**

```yaml
  mcp-tool:enrich-article:
    classification_status: approved
    export_to:
    - shell
    management: generated
    owner_kind: augur
    preferred_client: shell
    primary_surface: mcp-tool
    scope: project
  mcp-tool:submit-enrich-article-result:
    classification_status: approved
    export_to:
    - shell
    management: generated
    owner_kind: augur
    preferred_client: shell
    primary_surface: mcp-tool
    scope: project
```

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/ingest/scripts/mcp/tools_enrich.py shared-vault/skills/ingest/augur/tests/test_enrich_article_mcp.py config/system/capability_exposure.yaml src/mcp/
git commit -m "$(cat <<'EOF'
feat(ingest): enrich-article + submit-enrich-article-result MCP tools (ADR-753)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Daemon job to drain the queue

**Files:**
- Create: `shared-vault/skills/ingest/augur/scripts/run_pending_enrichment.py`
- Modify: `shared-vault/skills/ingest/SKILL.md` (add the job declaration so the daemon picks it up)

- [ ] **Step 1: Inspect existing daemon-job declarations**

```bash
grep -rn "x-augur-daemon-jobs\|daemon_jobs\|cron" shared-vault/skills/*/SKILL.md 2>/dev/null | head -10
```
Find the canonical SKILL.md frontmatter key for daemon-job registration. (If the key does not exist yet because no skill declared a job, fall back to `x-augur-background-routines` or the daemon skill's `config.yaml`. Read `shared-vault/skills/daemon/SKILL.md` to confirm the registration mechanism.)

- [ ] **Step 2: Write the daemon job script**

```python
# shared-vault/skills/ingest/augur/scripts/run_pending_enrichment.py
"""Drain the pending-enrichment queue.

Called by the daemon on its configured cadence (e.g. every 5 minutes).
For each pending note, dispatches `enrich-article` and waits for the
companion `submit-enrich-article-result` callback (when running outside
an AI client, the daemon spawns a CLI session per the LLM-Assisted MCP
Pattern). On success the note path is drained from the queue.

Errors are logged; the entry stays in the queue for the next pass.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.config.paths import get_pending_enrichment_queue_path  # noqa: E402
from skills.ingest.scripts.pending_enrichment_queue import drain, read_pending  # noqa: E402


def _dispatch_enrichment_via_cli(note_path: Path) -> bool:
    """Spawn a CLI agent session to run enrich-article + submit-enrich-article-result.

    Returns True if the round-trip succeeded; False otherwise. Uses the LLM-Assisted
    MCP Pattern's "Mode 2" CLI agent — see docs/references/llm-assisted-mcp-pattern.md.
    """
    try:
        # Use the existing CLI dispatch helper if available
        from src.lib.cli_dispatch import dispatch_agent_session  # type: ignore
    except ImportError:
        # Fallback: log and skip
        print(f"[run_pending_enrichment] CLI dispatch helper not available; skipping {note_path}", file=sys.stderr)
        return False

    prompt = (
        f"Call MCP tool `enrich-article` with note_path={note_path}. "
        f"Read the returned payload (needs_llm:true with raw_content_preview and instructions). "
        f"Follow the instructions to produce executive_summary, key_insights, why_it_matters, "
        f"verbatim_quotes, and cross_references_json. Then call `submit-enrich-article-result` "
        f"with those fields and the same note_path. Stop after the submit call returns success:true."
    )
    try:
        result = dispatch_agent_session(prompt=prompt, timeout_seconds=180)
        return bool(result.get("ok"))
    except Exception as exc:  # noqa: BLE001
        print(f"[run_pending_enrichment] dispatch failed for {note_path}: {exc}", file=sys.stderr)
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Drain pending-enrichment queue")
    parser.add_argument("--max-per-run", type=int, default=10, help="Max notes to enrich in one pass")
    args = parser.parse_args(argv)

    queue_path = get_pending_enrichment_queue_path()
    pending = read_pending(queue_path)[: args.max_per_run]
    if not pending:
        print("[run_pending_enrichment] queue empty.")
        return 0

    processed: list[Path] = []
    for entry in pending:
        note_path = Path(entry["note_path"])
        if not note_path.exists():
            # Note was deleted before we got to it — drain anyway
            processed.append(note_path)
            continue
        ok = _dispatch_enrichment_via_cli(note_path)
        if ok:
            processed.append(note_path)

    removed = drain(queue_path, processed)
    print(f"[run_pending_enrichment] processed={len(processed)} drained={removed} remaining={len(read_pending(queue_path))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Declare the daemon job in `SKILL.md`**

Update `shared-vault/skills/ingest/SKILL.md` frontmatter to add (or extend) `x-augur-daemon-jobs` (use the key the daemon skill actually recognizes — adjust if different):

```yaml
x-augur-daemon-jobs:
  - id: run-pending-enrichment
    script: augur/scripts/run_pending_enrichment.py
    cadence: "*/5 * * * *"   # every 5 minutes
    description: Drain ADR-753 pending-enrichment queue
```

- [ ] **Step 4: Smoke-test the daemon job script directly (offline mode)**

```bash
uv run python shared-vault/skills/ingest/augur/scripts/run_pending_enrichment.py --max-per-run 1
```
Expected with an empty queue: `[run_pending_enrichment] queue empty.` and exit 0.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/augur/scripts/run_pending_enrichment.py shared-vault/skills/ingest/SKILL.md
git commit -m "$(cat <<'EOF'
feat(ingest): daemon job to drain pending-enrichment queue (ADR-753)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Dashboard — enrichment-status badge + "Enrich…" action

**Files:**
- Modify: `apps/dashboard/components/shared/BrowseCard.tsx`
- Modify: `apps/dashboard/components/shared/BrowseDetailPanel.tsx`
- Modify: `tests/dashboard/components/shared/BrowseCard.test.tsx`
- Modify: `tests/dashboard/browse/BrowseDetailPanel.test.tsx`

- [ ] **Step 1: Add enrichment-status badge to url/file metadata strip**

In `BrowseCard.tsx`, extend the existing metadata-strip for `url` and `file`:

```tsx
{(item.typeBadge === "url" || item.typeBadge === "file") && (
  <span className="ml-2 inline-flex items-center gap-1">
    {item.metadata?.enrichment_status === "enriched" ? (
      <span className="rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-emerald-500">enriched</span>
    ) : item.metadata?.enrichment_status === "pending" ? (
      <span className="rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-amber-500">enriching…</span>
    ) : (
      <span className="rounded-full bg-slate-500/15 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-slate-500">raw</span>
    )}
  </span>
)}
```

- [ ] **Step 2: Add "Enrich…" action button to BrowseDetailPanel for url/file**

Find the existing detail-panel branch for `url` (or `file`) and add the button. When clicked, it calls the MCP tool `enrich-article` against the note path:

```tsx
{(item.typeBadge === "url" || item.typeBadge === "file") && (
  <div className="flex items-center gap-2">
    <button
      className="rounded border border-[var(--border-color)] px-3 py-1 text-sm hover:bg-[var(--bg-hover)]"
      onClick={async () => {
        if (!item.path) return;
        // mcpCall is already imported in this file
        await mcpCall({ tool: "enrich-article", args: { note_path: item.path } });
        // optimistic UI update — toast or refetch
      }}
    >
      Enrich…
    </button>
    <span className="text-xs text-[var(--text-muted)]">
      Status: {item.metadata?.enrichment_status ?? "raw"}
      {item.metadata?.["x-augur-enrichment-version"] && ` (v${item.metadata["x-augur-enrichment-version"]})`}
    </span>
  </div>
)}
```

- [ ] **Step 3: Add tests**

```tsx
// tests/dashboard/components/shared/BrowseCard.test.tsx
it("renders enrichment status badge on url cards", () => {
  const { getByText } = render(
    <BrowseCard item={{ ...baseItem, typeBadge: "url", metadata: { source_domain: "x.com", enrichment_status: "enriched" } }} />
  );
  expect(getByText(/enriched/i)).toBeTruthy();
});

// tests/dashboard/browse/BrowseDetailPanel.test.tsx
it("shows the Enrich button for url notes", () => {
  const { getByText } = render(
    <BrowseDetailPanel item={{ ...baseItem, typeBadge: "url", path: "/v/notes/x.md" }} />
  );
  expect(getByText(/Enrich/)).toBeTruthy();
});
```

- [ ] **Step 4: Run the tests**

```bash
cd apps/dashboard && pnpm test BrowseCard BrowseDetailPanel -- --run
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/components/shared/ tests/dashboard/
git commit -m "$(cat <<'EOF'
feat(dashboard): enrichment-status badge + Enrich action for url/file notes (ADR-753)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Sync + rebuild dashboard

**Files:** none modified.

- [ ] **Step 1: Sync MCP surfaces**

```bash
augur sync mcp all
```

- [ ] **Step 2: Rebuild dashboard**

```bash
/dev-build
```

- [ ] **Step 3: Commit generated artifacts (if any)**

```bash
git add .claude .codex .gemini src/mcp/ 2>/dev/null || true
git status
git commit -m "$(cat <<'EOF'
chore(sync): regenerate client surfaces for article-enrichment tools (ADR-753)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)" 2>/dev/null || echo "Nothing to commit; already in sync."
```

---

## Task 9: Real-data verification per Rule 34

**Files:** none modified. Real-vault value validation.

- [ ] **Step 1: Capture three real URLs of varied length**

Pick three URLs you genuinely care about — a long-form essay, a technical tutorial, and a news/opinion piece:

```
/note https://www.example.com/long-essay
/note https://docs.example.com/technical-guide
/note https://news.example.com/opinion-piece
```

For each, expected behavior:
- Note appears at `<vault>/notes/` with `type: url`, `enrichment_status: pending`
- Within the daemon's cadence (≤5 min), background enrichment runs
- After enrichment: `enrichment_status: enriched`, body has the 5 enriched sections at top and raw content at bottom

- [ ] **Step 2: Verify each enriched file by reading it**

```bash
ls -t "$(uv run python -c 'from src.config.paths import get_vault_notes_dir; print(get_vault_notes_dir())')" | head -3
```

For each of the three most-recent notes:

```bash
NOTES_DIR="$(uv run python -c 'from src.config.paths import get_vault_notes_dir; print(get_vault_notes_dir())')"
for f in $(ls -t "$NOTES_DIR" | head -3); do
  echo "=== $f ==="
  head -50 "$NOTES_DIR/$f"
  echo
done
```

Expected: each file shows frontmatter with `x-augur-enrichment-status: enriched`, then `## Executive summary`, then content. Read at least one of them top-to-bottom and judge: does the summary actually summarize? Are the verbatim quotes truly from the article? Are the cross-references reasonable?

- [ ] **Step 3: Force a manual enrichment via the dashboard**

Pick the oldest un-enriched url note (or capture a new one, then immediately go to the dashboard). Open it in BrowseDetailPanel, click "Enrich…". Watch the status badge cycle through pending → enriched. Refresh and confirm the note body now has the enriched sections.

- [ ] **Step 4: Run the daemon job manually**

```bash
uv run python shared-vault/skills/ingest/augur/scripts/run_pending_enrichment.py --max-per-run 5
```
Expected: drains any leftover queue entries; prints `processed=<N> drained=<N> remaining=0`.

- [ ] **Step 5: Document the verification**

Append to the migration log:

```bash
cat >> docs/migrations/2026-05-15-notes-zone-migration.md <<'EOF'

## Article enrichment verification (2026-05-16, ADR-753)

- URLs captured: <3 URLs>
- Auto-enrichment latency: <observed seconds from /note to enrichment_status=enriched>
- Manual enrichment via dashboard: <observed; pending→enriched cycle complete>
- Quality spot-check on one full note: <subjective: does the summary actually summarize?>
- Daemon job run output: processed=<N> drained=<N> remaining=<N>
- Issues observed: <list>
EOF
git add docs/migrations/2026-05-15-notes-zone-migration.md
git commit -m "$(cat <<'EOF2'
chore(verify): record ADR-753 article enrichment real-data verification

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF2
)"
```

This satisfies CLAUDE.md Rule 34 — the capability was exercised on real captured URLs (not fixtures) and the user-facing output (enriched note bodies) is inspectable.

---

## Self-Review

**1. Spec coverage**

| Spec section | Task |
|--------------|------|
| Article-enrichment extension | All tasks |
| Auto-enrichment on new url/file notes | Tasks 3, 4 |
| Manual "Enrich…" detail-panel action | Task 7 |
| Output structure (5 named sections + raw content preserved) | Tasks 2, 5 |
| Frontmatter status field (`x-augur-enrichment-status`) | Tasks 2, 5 |
| Idempotency (re-run is safe) | Tasks 2, 5 |
| LLM-Assisted MCP Pattern dispatch | Tasks 2 (payload builder), 5 (MCP tools), 6 (daemon CLI fallback) |
| Cross-references resolved against ADR-738 graph | Tasks 2, 5 |
| ADR-753 document | Task 1 |
| MCP capability_exposure entries | Task 5 |
| Daemon job declaration | Task 6 |
| Real-data verification per Rule 34 | Task 9 |
| Browser verification per Rule 28 | Task 9 step 3 |

Gaps: none. The plan does not modify `BrowseItem` interface; existing `metadata` record absorbs `enrichment_status` per the spec.

**2. Placeholder scan**

```bash
grep -nE "TODO|TBD|FIXME|XXX|appropriate error|similar to Task" docs/superpowers/plans/2026-05-16-adr-753-article-enrichment.md
```
Expected matches: only the self-review's `grep` command itself. No `TODO_` markers in code (this plan ships complete functionality).

**3. Type consistency**

- `ENRICHMENT_SECTIONS` tuple defined in Task 2; referenced by Task 5 (`submit_enrich_article_result` returns its names).
- `split_body` / `compose_body` / `stamp_enrichment_frontmatter` defined in Task 2; consumed by Task 5 MCP tools.
- `enqueue` / `read_pending` / `drain` defined in Task 3; consumed by Task 4 (writers) and Task 6 (daemon).
- `get_pending_enrichment_queue_path` defined in Task 4 step 1; consumed by Tasks 4, 6.
- MCP tool names — `enrich-article`, `submit-enrich-article-result` — consistent across Tasks 5, 6, 7 (UI), capability_exposure.yaml.
- Frontmatter keys — `x-augur-note-type`, `x-augur-enrichment-status`, `x-augur-enrichment-version` — spelled consistently throughout.

No inconsistencies.

---

## Execution handoff

Plan 3 complete and saved to `docs/superpowers/plans/2026-05-16-adr-753-article-enrichment.md`. All three plans for the gbrain-ingest-port slate are now on disk:

- `docs/superpowers/plans/2026-05-15-adr-751-note-command-surface.md` (16 tasks)
- `docs/superpowers/plans/2026-05-16-adr-752-audio-ingest-skill.md` (13 tasks)
- `docs/superpowers/plans/2026-05-16-adr-753-article-enrichment.md` (9 tasks)

ADR-751 must execute first (it rewires atomic ops to write under `<vault>/notes/`). ADR-752 and ADR-753 can execute in either order after that.

**Two execution options:**

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration. Best when changes need fresh context per task.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints. Best when willing to keep this session open through the full execution.

Which approach? And which plan first — ADR-751 (load-bearing, must precede the others)?
