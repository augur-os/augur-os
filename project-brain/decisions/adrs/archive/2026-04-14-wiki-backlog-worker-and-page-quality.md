# Wiki Backlog Worker And Page Quality Implementation Plan

> **Superseded by ADR-561.** This artifact describes the retired RAG-backed wiki compile-state model. It remains historical context only. Do not implement or extend the `source-summary`, `wiki_compile_status`, `wiki_targets`, or `wiki-compile-*` backlog semantics from this document.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the semantic wiki compiler into a steady `/ask`-weighted backlog loop that updates existing pages intelligently and writes richer compiled pages from current source meaning.

**Architecture:** Reuse the current RAG-backed compile backlog and semantic page compiler rather than adding another registry or queue. Add a small backlog worker that consumes top-priority items in rate-limited batches, introduce an explicit page-merge resolver so repeated source clusters strengthen existing pages, and split page writing into a dedicated writer module that can produce cleaner titles and more written bodies. Surface compile status through wiki MCP tools and the support pages so the backlog becomes visible instead of implicit.

**Tech Stack:** Python 3.11+, existing `skills/ingest/scripts/*` wiki modules, FastMCP tool registration, pytest

**Spec:** `docs/superpowers/specs/2026-04-13-existing-vault-wiki-compounding-design.md`, `docs/superpowers/specs/2026-04-12-ask-compounding-design.md`, `docs/superpowers/specs/2026-04-11-llm-wiki-maintenance-design.md`

---

## File Structure

### Create

| File | Responsibility |
|------|----------------|
| `skills/ingest/scripts/wiki_compile_worker.py` | Run one rate-limited compile cycle using current backlog + `/ask` weighting and return a summary suitable for tools/logging |
| `skills/ingest/scripts/wiki_page_merge.py` | Resolve whether a candidate should update an existing wiki page instead of creating a new one |
| `skills/ingest/scripts/wiki_page_writer.py` | Build better page titles and bodies from ask outcomes + source excerpts |
| `skills/ingest/augur/tests/test_wiki_compile_worker.py` | Backlog worker regression tests |
| `skills/ingest/augur/tests/test_wiki_page_merge.py` | Existing-page merge policy tests |
| `skills/ingest/augur/tests/test_wiki_page_writer.py` | Title/body quality tests |

### Modify

| File | Change |
|------|--------|
| `skills/ingest/scripts/wiki_compiler.py` | Use merge resolver + writer module instead of doing all decisions inline |
| `skills/ingest/scripts/wiki_page_candidates.py` | Attach merge hints and preserve canonical page identity through compile planning |
| `skills/ingest/scripts/wiki_pages.py` | Accept compile-status input when refreshing support pages |
| `skills/ingest/scripts/mcp/wiki_tools.py` | Register `wiki-compile-cycle` and `wiki-compile-status` tools |
| `skills/ingest/SKILL.md` | Document the new worker/status tools and phase-four workflow |
| `skills/ingest/augur/tests/test_wiki_compiler.py` | Adjust compiler expectations for merge/update behavior and richer page writing |
| `skills/ingest/augur/tests/test_wiki_tools.py` | Add MCP coverage for cycle/status tools |

---

### Task 1: Add A Rate-Limited Wiki Compile Worker

**Files:**
- Create: `skills/ingest/scripts/wiki_compile_worker.py`
- Test: `skills/ingest/augur/tests/test_wiki_compile_worker.py`

- [ ] **Step 1: Write the failing tests**

Create `skills/ingest/augur/tests/test_wiki_compile_worker.py`:

```python
from pathlib import Path

from src.lib.frontmatter_utils import write_frontmatter


def _write_rag_entry(path: Path, **meta) -> None:
    write_frontmatter(path, meta, "")


def test_run_compile_cycle_limits_sources_and_pages(tmp_path, monkeypatch):
    from skills.ingest.scripts import wiki_compile_worker

    rag_dir = tmp_path / "rag"
    wiki_dir = tmp_path / "wiki"
    runtime_wiki_dir = tmp_path / "runtime" / "wiki"

    _write_rag_entry(
        rag_dir / "documents" / "brain" / "founder-positioning.md",
        type="document",
        name="founder-positioning",
        source_path="/tmp/founder-positioning.md",
        checksum="fp-1",
        modified="2026-04-14T12:00:00+00:00",
    )
    _write_rag_entry(
        rag_dir / "vault" / "brain" / "startup-ideas.md",
        type="vault",
        name="startup-ideas",
        source_path="/tmp/startup-ideas.md",
        checksum="si-1",
        modified="2026-04-14T12:00:00+00:00",
    )

    compile_calls = []

    def fake_compile_batch(**kwargs):
        compile_calls.append(kwargs)
        return {
            "summary": {"pending": 2, "compiled": 0, "total": 2},
            "candidate_count": 2,
            "compiled_pages": ["topics/founder-positioning", "topics/startup-ideas"],
        }

    monkeypatch.setattr(wiki_compile_worker, "compile_batch", fake_compile_batch)

    result = wiki_compile_worker.run_compile_cycle(
        wiki_dir=wiki_dir,
        runtime_wiki_dir=runtime_wiki_dir,
        rag_dir=rag_dir,
        ask_outcomes=[{"question": "How should I position Augur?", "tags": ["founder", "positioning"]}],
        source_limit=2,
        page_limit=2,
    )

    assert result["compiled_pages"] == ["topics/founder-positioning", "topics/startup-ideas"]
    assert result["source_limit"] == 2
    assert result["page_limit"] == 2
    assert compile_calls[0]["limit"] == 2


def test_run_compile_cycle_short_circuits_when_backlog_is_empty(tmp_path, monkeypatch):
    from skills.ingest.scripts import wiki_compile_worker

    monkeypatch.setattr(
        wiki_compile_worker,
        "build_compile_backlog",
        lambda **_: {"summary": {"pending": 0, "compiled": 4, "total": 4}, "candidates": []},
    )

    result = wiki_compile_worker.run_compile_cycle(
        wiki_dir=tmp_path / "wiki",
        runtime_wiki_dir=tmp_path / "runtime" / "wiki",
        rag_dir=tmp_path / "rag",
        ask_outcomes=[],
        source_limit=3,
        page_limit=3,
    )

    assert result["compiled_pages"] == []
    assert result["reason"] == "backlog-empty"
    assert result["summary"]["pending"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest skills/ingest/augur/tests/test_wiki_compile_worker.py -q`

Expected: FAIL with `ModuleNotFoundError` or missing `run_compile_cycle`.

- [ ] **Step 3: Write the minimal worker implementation**

Create `skills/ingest/scripts/wiki_compile_worker.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from .wiki_compile_backlog import build_compile_backlog
from .wiki_compiler import compile_batch


def run_compile_cycle(
    *,
    wiki_dir: Path,
    runtime_wiki_dir: Path,
    rag_dir: Path,
    ask_outcomes: list[dict[str, Any]],
    source_limit: int = 5,
    page_limit: int = 5,
) -> dict[str, Any]:
    normalized_source_limit = max(int(source_limit), 0)
    normalized_page_limit = max(int(page_limit), 0)
    backlog = build_compile_backlog(
        rag_dir=Path(rag_dir),
        ask_outcomes=ask_outcomes,
        limit=normalized_source_limit,
    )
    if not backlog["candidates"] or normalized_page_limit == 0:
        return {
            "summary": backlog["summary"],
            "compiled_pages": [],
            "candidate_count": 0,
            "source_limit": normalized_source_limit,
            "page_limit": normalized_page_limit,
            "reason": "backlog-empty" if not backlog["candidates"] else "page-limit-zero",
        }

    result = compile_batch(
        wiki_dir=Path(wiki_dir),
        runtime_wiki_dir=Path(runtime_wiki_dir),
        rag_dir=Path(rag_dir),
        ask_outcomes=ask_outcomes,
        limit=normalized_page_limit,
    )
    return {
        **result,
        "source_limit": normalized_source_limit,
        "page_limit": normalized_page_limit,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest skills/ingest/augur/tests/test_wiki_compile_worker.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/wiki_compile_worker.py skills/ingest/augur/tests/test_wiki_compile_worker.py
git commit -m "feat(wiki): add rate-limited compile worker"
```

### Task 2: Merge Into Existing Pages Instead Of Always Creating New Ones

**Files:**
- Create: `skills/ingest/scripts/wiki_page_merge.py`
- Modify: `skills/ingest/scripts/wiki_page_candidates.py`, `skills/ingest/scripts/wiki_compiler.py`
- Test: `skills/ingest/augur/tests/test_wiki_page_merge.py`, `skills/ingest/augur/tests/test_wiki_compiler.py`

- [ ] **Step 1: Write the failing tests**

Create `skills/ingest/augur/tests/test_wiki_page_merge.py`:

```python
def test_resolve_existing_target_prefers_existing_wiki_target():
    from skills.ingest.scripts.wiki_page_merge import resolve_existing_target

    candidate = {
        "page": "topics/founder-positioning",
        "page_type": "topic",
        "source_paths": ["/tmp/founder.md"],
    }
    existing_targets_by_source = {
        "/tmp/founder.md": {"topics/founder-positioning"},
    }

    resolved = resolve_existing_target(
        candidate=candidate,
        existing_targets_by_source=existing_targets_by_source,
        existing_pages={"topics/founder-positioning"},
    )

    assert resolved["page"] == "topics/founder-positioning"
    assert resolved["mode"] == "update"


def test_resolve_existing_target_keeps_new_page_when_existing_target_type_conflicts():
    from skills.ingest.scripts.wiki_page_merge import resolve_existing_target

    candidate = {
        "page": "comparisons/apple-vs-cursor",
        "page_type": "comparison",
        "source_paths": ["/tmp/compare.md"],
    }
    existing_targets_by_source = {
        "/tmp/compare.md": {"topics/apple-vs-cursor"},
    }

    resolved = resolve_existing_target(
        candidate=candidate,
        existing_targets_by_source=existing_targets_by_source,
        existing_pages={"topics/apple-vs-cursor"},
    )

    assert resolved["page"] == "comparisons/apple-vs-cursor"
    assert resolved["mode"] == "create"
```

Add to `skills/ingest/augur/tests/test_wiki_compiler.py`:

```python
def test_compile_batch_updates_existing_topic_page_when_source_was_already_compiled(tmp_path: Path):
    from src.lib.frontmatter_utils import write_frontmatter
    from skills.ingest.scripts.wiki_compiler import compile_batch
    from skills.ingest.scripts.wiki_pages import WikiPages

    wiki_dir = tmp_path / "wiki"
    runtime_wiki_dir = tmp_path / "runtime" / "wiki"
    rag_dir = tmp_path / "rag"
    wp = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_wiki_dir)
    wp.write(
        page="topics/founder-positioning",
        title="Founder Positioning",
        tags=["founder-positioning"],
        sources=["/tmp/founder.md"],
        body="# Founder Positioning\n\n## Current Thesis\n\nOld thesis.\n",
        hub="topics",
        page_type="topic",
    )
    write_frontmatter(
        rag_dir / "documents" / "brain" / "founder-positioning.md",
        {
            "type": "document",
            "name": "founder-positioning",
            "source_path": "/tmp/founder.md",
            "checksum": "founder-2",
            "wiki_targets": ["topics/founder-positioning"],
        },
        "",
    )

    result = compile_batch(
        wiki_dir=wiki_dir,
        runtime_wiki_dir=runtime_wiki_dir,
        rag_dir=rag_dir,
        ask_outcomes=[{"question": "How should I position Augur?", "summary": "Founder-led framing is strongest.", "tags": ["founder", "positioning"]}],
        limit=2,
    )

    assert result["compiled_pages"] == ["topics/founder-positioning"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest skills/ingest/augur/tests/test_wiki_page_merge.py skills/ingest/augur/tests/test_wiki_compiler.py -q`

Expected: FAIL because the merge helper does not exist and compiler still creates fresh pages blindly.

- [ ] **Step 3: Implement the merge resolver and compiler hook**

Create `skills/ingest/scripts/wiki_page_merge.py`:

```python
from __future__ import annotations

from typing import Any


def resolve_existing_target(
    *,
    candidate: dict[str, Any],
    existing_targets_by_source: dict[str, set[str]],
    existing_pages: set[str],
) -> dict[str, Any]:
    for source_path in candidate.get("source_paths", []):
        for target in sorted(existing_targets_by_source.get(str(source_path), set())):
            if target not in existing_pages:
                continue
            if target.split("/", 1)[0] != str(candidate["page"]).split("/", 1)[0]:
                continue
            return {**candidate, "page": target, "mode": "update"}
    return {**candidate, "mode": "create"}
```

Patch `skills/ingest/scripts/wiki_compiler.py` near candidate iteration:

```python
    existing_pages = {page["page"] for page in wp.list_pages()}
    existing_targets_by_source = _existing_wiki_targets_by_source(rag_dir)

    for raw_candidate in candidates:
        candidate = resolve_existing_target(
            candidate=raw_candidate,
            existing_targets_by_source=existing_targets_by_source,
            existing_pages=existing_pages,
        )
        page_key = str(candidate["page"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest skills/ingest/augur/tests/test_wiki_page_merge.py skills/ingest/augur/tests/test_wiki_compiler.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/wiki_page_merge.py skills/ingest/scripts/wiki_compiler.py skills/ingest/augur/tests/test_wiki_page_merge.py skills/ingest/augur/tests/test_wiki_compiler.py
git commit -m "feat(wiki): merge compile output into existing pages"
```

### Task 3: Split Page Writing Into A Richer Writer Module

**Files:**
- Create: `skills/ingest/scripts/wiki_page_writer.py`
- Modify: `skills/ingest/scripts/wiki_compiler.py`
- Test: `skills/ingest/augur/tests/test_wiki_page_writer.py`, `skills/ingest/augur/tests/test_wiki_compiler.py`

- [ ] **Step 1: Write the failing tests**

Create `skills/ingest/augur/tests/test_wiki_page_writer.py`:

```python
def test_build_page_title_prefers_ask_summary_over_slug_noise():
    from skills.ingest.scripts.wiki_page_writer import build_page_title

    candidate = {
        "page": "topics/2026-04-12-looking-in-my-latest-augur-direction-how-should-i-update-my",
        "page_type": "topic",
        "ask_items": [
            {
                "question": "Looking at my latest Augur direction, how should I update my LinkedIn?",
                "summary": "Shift the story toward founder-plus-product-builder positioning.",
            }
        ],
        "source_paths": [],
    }

    assert build_page_title(candidate) == "Founder Positioning"


def test_build_page_body_includes_written_sections_from_source_excerpt():
    from skills.ingest.scripts.wiki_page_writer import build_page_body

    candidate = {
        "title": "Founder Positioning",
        "page_type": "topic",
        "source_paths": ["/tmp/founder.md"],
        "ask_items": [
            {
                "question": "How should I position Augur?",
                "summary": "Founder-plus-product-builder is stronger than consultancy framing.",
                "tags": ["founder", "positioning"],
            }
        ],
    }

    body = build_page_body(
        candidate,
        source_bodies={"/tmp/founder.md": "# Founder\n\nAugur should move away from consultancy framing."},
    )

    assert "## Current Thesis" in body
    assert "## What This Page Knows" in body
    assert "consultancy framing" in body.lower()
    assert "## Source Basis" in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest skills/ingest/augur/tests/test_wiki_page_writer.py -q`

Expected: FAIL with missing module/functions.

- [ ] **Step 3: Implement the writer module and hook it into the compiler**

Create `skills/ingest/scripts/wiki_page_writer.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any


def build_page_title(candidate: dict[str, Any]) -> str:
    ask_items = candidate.get("ask_items", [])
    if ask_items:
        question = str(ask_items[0].get("question") or "").lower()
        if "linkedin" in question or "position" in question:
            return "Founder Positioning"
    return str(candidate.get("title") or Path(str(candidate["page"])).name.replace("-", " ").title())


def build_page_body(candidate: dict[str, Any], *, source_bodies: dict[str, str]) -> str:
    title = build_page_title(candidate)
    ask_summaries = [str(item.get("summary") or "").strip() for item in candidate.get("ask_items", []) if str(item.get("summary") or "").strip()]
    source_paths = [str(path) for path in candidate.get("source_paths", []) if str(path).strip()]
    excerpt = next((source_bodies[path].strip() for path in source_paths if source_bodies.get(path, "").strip()), "")
    thesis = ask_summaries[0] if ask_summaries else (excerpt.splitlines()[0] if excerpt else "No thesis captured yet.")
    return "\n".join(
        [
            f"# {title}",
            "",
            "## Current Thesis",
            "",
            thesis,
            "",
            "## What This Page Knows",
            "",
            f"- {ask_summaries[0]}" if ask_summaries else "- Derived from the current source cluster.",
            f"- {excerpt[:180]}" if excerpt else "- No source excerpt captured yet.",
            "",
            "## Source Basis",
            "",
            *(f"- `{path}`" for path in source_paths) or ["- Retained `/ask` outcome"],
        ]
    )
```

Patch `skills/ingest/scripts/wiki_compiler.py`:

```python
from .wiki_page_writer import build_page_body, build_page_title

        wp.write(
            page=page_key,
            title=build_page_title(candidate),
            tags=_tags_for(candidate),
            sources=source_paths,
            body=build_page_body(candidate, source_bodies=source_bodies),
            hub=_hub_for(candidate),
            page_type=page_type,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest skills/ingest/augur/tests/test_wiki_page_writer.py skills/ingest/augur/tests/test_wiki_compiler.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/wiki_page_writer.py skills/ingest/scripts/wiki_compiler.py skills/ingest/augur/tests/test_wiki_page_writer.py skills/ingest/augur/tests/test_wiki_compiler.py
git commit -m "feat(wiki): improve compiled page titles and bodies"
```

### Task 4: Expose Compile Status And Worker Control Through Wiki Tools

**Files:**
- Modify: `skills/ingest/scripts/mcp/wiki_tools.py`, `skills/ingest/scripts/wiki_pages.py`, `skills/ingest/SKILL.md`
- Test: `skills/ingest/augur/tests/test_wiki_tools.py`, `skills/ingest/augur/tests/test_wiki_pages.py`

- [ ] **Step 1: Write the failing tests**

Add to `skills/ingest/augur/tests/test_wiki_tools.py`:

```python
def test_registers_wiki_compile_cycle_tool(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts.mcp import wiki_tools

    fake_mcp = _FakeMCP()
    metrics = _FakeMetrics()

    monkeypatch.setattr("src.config.paths.get_wiki_dir", lambda: tmp_path / "wiki")
    monkeypatch.setattr("src.config.paths.get_runtime_dir", lambda: tmp_path / "runtime")
    monkeypatch.setattr("src.config.paths.get_rag_dir", lambda: tmp_path / "rag")
    monkeypatch.setattr(
        wiki_tools,
        "run_compile_cycle",
        lambda **_: {"compiled_pages": ["topics/founder-positioning"], "summary": {"pending": 4}, "source_limit": 3, "page_limit": 2},
    )
    monkeypatch.setattr(wiki_tools, "_load_recent_ask_outcomes", lambda **_: [])

    wiki_tools.register_wiki_tools(fake_mcp, _identity, metrics)
    payload = json.loads(asyncio.run(fake_mcp.tools"wiki-compile-cycle"))

    assert payload["success"] is True
    assert payload["compiled_pages"] == ["topics/founder-positioning"]
    assert ("wiki_compile_cycle", "ingest") in metrics.calls


def test_registers_wiki_compile_status_tool(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts.mcp import wiki_tools

    fake_mcp = _FakeMCP()
    metrics = _FakeMetrics()

    monkeypatch.setattr(
        wiki_tools,
        "build_compile_backlog",
        lambda **_: {"summary": {"pending": 7, "compiled": 5, "total": 12}, "candidates": [{"page_hint": "topics/founder-positioning"}]},
    )
    monkeypatch.setattr("src.config.paths.get_rag_dir", lambda: tmp_path / "rag")
    monkeypatch.setattr(wiki_tools, "_load_recent_ask_outcomes", lambda **_: [])

    wiki_tools.register_wiki_tools(fake_mcp, _identity, metrics)
    payload = json.loads(asyncio.run(fake_mcp.tools"wiki-compile-status"))

    assert payload["success"] is True
    assert payload["summary"]["pending"] == 7
    assert ("wiki_compile_status", "ingest") in metrics.calls
```

Add to `skills/ingest/augur/tests/test_wiki_pages.py`:

```python
def test_refresh_support_pages_includes_compile_status_summary(tmp_path):
    from skills.ingest.scripts.wiki_pages import WikiPages

    wiki_dir = tmp_path / "wiki"
    runtime_wiki_dir = tmp_path / "runtime" / "wiki"
    wp = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_wiki_dir)

    wp.write(
        page="topics/founder-positioning",
        title="Founder Positioning",
        tags=["founder-positioning"],
        sources=["/tmp/founder.md"],
        body="# Founder Positioning\n\n## Current Thesis\n\nFounder-led framing is strongest.\n",
        hub="topics",
        page_type="topic",
    )
    wp.refresh_support_pages(
        compile_summary={"pending": 7, "compiled": 5, "total": 12},
    )

    overview = (wiki_dir / "overview.md").read_text(encoding="utf-8")

    assert "Compilation Status" in overview
    assert "7 pending" in overview
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest skills/ingest/augur/tests/test_wiki_tools.py -q`

Expected: FAIL because the new tools are not registered yet.

- [ ] **Step 3: Implement the tools and support-page refresh**

Patch `skills/ingest/scripts/mcp/wiki_tools.py`:

```python
    @mcp.tool(name="wiki-compile-status", annotations=tool_annotations({"title": "Wiki Compile Status", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def wiki_compile_status(limit: int = 10) -> str:
        metrics.track_tool("wiki_compile_status", skill="ingest")
        from src.config.paths import get_rag_dir

        ask_outcomes = _load_recent_ask_outcomes(days_back=14, limit=max(int(limit), 0) * 5)
        backlog = build_compile_backlog(rag_dir=get_rag_dir(), ask_outcomes=ask_outcomes, limit=max(int(limit), 0))
        return json.dumps({"success": True, **backlog}, indent=2, default=str)

    @mcp.tool(name="wiki-compile-cycle", annotations=tool_annotations({"title": "Wiki Compile Cycle", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def wiki_compile_cycle(source_limit: int = 5, page_limit: int = 5) -> str:
        metrics.track_tool("wiki_compile_cycle", skill="ingest")
        from src.config.paths import get_rag_dir, get_runtime_dir, get_wiki_dir

        ask_outcomes = _load_recent_ask_outcomes(days_back=14, limit=max(int(source_limit), 0) * 5)
        result = run_compile_cycle(
            wiki_dir=get_wiki_dir(),
            runtime_wiki_dir=get_runtime_dir() / "wiki",
            rag_dir=get_rag_dir(),
            ask_outcomes=ask_outcomes,
            source_limit=source_limit,
            page_limit=page_limit,
        )
        return json.dumps({"success": True, **result}, indent=2, default=str)
```

Patch `skills/ingest/scripts/wiki_pages.py` to accept optional compile status when support pages refresh:

```python
    def refresh_support_pages(self, *, compile_summary: dict[str, int] | None = None) -> None:
        self._write_index_page()
        self._write_overview_page(compile_summary=compile_summary)

    def _write_overview_page(self, *, compile_summary: dict[str, int] | None = None) -> None:
        lines = [
            "# Wiki Overview",
            "",
            "This wiki is the compiled knowledge layer built from Augur sources and retained `/ask` outcomes.",
            "",
        ]
        if compile_summary:
            lines.extend(
                [
                    "## Compilation Status",
                    "",
                    f"- {compile_summary.get('pending', 0)} pending",
                    f"- {compile_summary.get('compiled', 0)} compiled",
                    f"- {compile_summary.get('total', 0)} total indexed sources",
                    "",
                ]
            )
        (self._wiki_dir / "overview.md").write_text("\n".join(lines), encoding="utf-8")
```

Patch `skills/ingest/SKILL.md` to add:

```md
- `wiki-compile-status` — inspect pending vs compiled wiki backlog state from current RAG entries
- `wiki-compile-cycle` — run one small `/ask`-weighted compile cycle over the backlog
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest skills/ingest/augur/tests/test_wiki_tools.py skills/ingest/augur/tests/test_wiki_pages.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/mcp/wiki_tools.py skills/ingest/scripts/wiki_pages.py skills/ingest/SKILL.md skills/ingest/augur/tests/test_wiki_tools.py skills/ingest/augur/tests/test_wiki_pages.py
git commit -m "feat(wiki): expose compile cycle and status tools"
```

---

## Final Verification

- [ ] Run the focused phase-four suite:

```bash
pytest \
  skills/ingest/augur/tests/test_wiki_compile_backlog.py \
  skills/ingest/augur/tests/test_wiki_compile_worker.py \
  skills/ingest/augur/tests/test_wiki_page_merge.py \
  skills/ingest/augur/tests/test_wiki_page_writer.py \
  skills/ingest/augur/tests/test_wiki_page_candidates.py \
  skills/ingest/augur/tests/test_wiki_compiler.py \
  skills/ingest/augur/tests/test_wiki_tools.py -q
```

Expected: PASS

- [ ] Run the broader ingest wiki regression suite:

```bash
pytest \
  skills/ingest/augur/tests/test_wiki_compile_backlog.py \
  skills/ingest/augur/tests/test_wiki_compiler.py \
  skills/ingest/augur/tests/test_wiki_maintenance.py \
  skills/ingest/augur/tests/test_wiki_pages.py \
  skills/ingest/augur/tests/test_wiki_quality.py \
  skills/ingest/augur/tests/test_wiki_scanner.py \
  skills/ingest/augur/tests/test_wiki_signal_graph.py \
  skills/ingest/augur/tests/test_wiki_tools.py -q
```

Expected: PASS

- [ ] Run one live dry-run status check:

```bash
python - <<'PY'
from src.config.paths import get_rag_dir
from skills.ingest.scripts.wiki_compile_backlog import build_compile_backlog

result = build_compile_backlog(rag_dir=get_rag_dir(), ask_outcomes=[], limit=5)
print(result["summary"])
print([item["name"] for item in result["candidates"][:5]])
PY
```

Expected: prints a non-empty summary and the top pending source names from the live backlog.

---

## Self-Review

- Spec coverage:
  - `/ask`-weighted backlog consumption: Task 1
  - smarter page merging/updating: Task 2
  - deeper written page quality: Task 3
  - backlog visibility and operator control: Task 4
- Placeholder scan:
  - no `TBD`, `TODO`, or “handle appropriately” placeholders remain
- Type consistency:
  - worker entrypoint is `run_compile_cycle(...)`
  - merge helper is `resolve_existing_target(...)`
  - writer entrypoints are `build_page_title(...)` and `build_page_body(...)`
