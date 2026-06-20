# Backlog-Driven Wiki Page Compiler Implementation Plan

> **Superseded by ADR-561.** This artifact describes the retired RAG-backed wiki compile-state model. It remains historical context only. Do not implement or extend the `source-summary`, `wiki_compile_status`, `wiki_targets`, or `wiki-compile-*` backlog semantics from this document.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the phase-one RAG-backed backlog into real compiled wiki pages by consuming small batches of `vault` and `documents` entries, creating `topic`, `query-output`, and `source-summary` pages, and stamping consumed entries as compiled.

**Architecture:** This is phase two of the broader compiler architecture in `docs/superpowers/specs/2026-04-14-llm-wiki-architecture-design.md`. Reuse the existing phase-one backlog and compile-state model, add a page-candidate extraction layer that combines retained `/ask` outcomes with backlog entries, then run a batch compiler that writes first-class wiki pages instead of only strengthening hub overviews. The compiler should stay rate-limited, wiki-first, and grounded in real source bodies rather than path labels.

**Tech Stack:** Python 3.11, YAML frontmatter, existing RAG pointer entries, `WikiPages`, wiki MCP tools, retained `/ask` outcomes, pytest

**Spec:** `docs/superpowers/specs/2026-04-14-llm-wiki-architecture-design.md`

**Prerequisite:** Merge or cherry-pick the phase-one branch `codex/rag-backed-wiki-compile-state` first. This plan assumes `wiki_compile_backlog.py`, `wiki-compile-backlog`, and rewrite-time RAG stamping already exist.

---

## File Structure

### Create

| File | Responsibility |
|---|---|
| `skills/ingest/scripts/wiki_page_candidates.py` | Convert backlog entries plus retained `/ask` outcomes into dynamic page candidates (`topic`, `query-output`, `source-summary`) |
| `skills/ingest/scripts/wiki_compiler.py` | Consume a small compile batch, read source bodies, render compiled pages, write them, and stamp consumed RAG entries |
| `skills/ingest/augur/tests/test_wiki_page_candidates.py` | TDD coverage for dynamic candidate extraction and `/ask`-driven prioritization |
| `skills/ingest/augur/tests/test_wiki_pages.py` | TDD coverage for explicit wiki page types in frontmatter and metadata |
| `skills/ingest/augur/tests/test_wiki_compiler.py` | TDD coverage for batch compilation, page creation, and compile-state stamping |

### Modify

| File | Change |
|---|---|
| `skills/ingest/scripts/wiki_pages.py` | Accept explicit `page_type`, preserve it in frontmatter/metadata, and expose it in index + list outputs |
| `skills/ingest/scripts/mcp/wiki_tools.py` | Add a read-only preview tool and a mutating batch-compile tool for the new compiler |
| `skills/ingest/augur/tests/test_wiki_tools.py` | Verify compile preview and compile batch MCP tools |
| `skills/ingest/SKILL.md` | Document phase-two compiler tools and page taxonomy behavior |

---

## Task 1: Extract Dynamic Page Candidates From Backlog And `/ask`

**Files:**
- Create: `skills/ingest/scripts/wiki_page_candidates.py`
- Create: `skills/ingest/augur/tests/test_wiki_page_candidates.py`

- [ ] **Step 1: Write the failing candidate extraction tests**

Create `skills/ingest/augur/tests/test_wiki_page_candidates.py`:

```python
from skills.ingest.scripts.wiki_page_candidates import derive_page_candidates


def test_derive_page_candidates_builds_topic_from_backlog_and_ask():
    candidates = derive_page_candidates(
        backlog={
            "candidates": [
                {
                    "category": "vault",
                    "name": "startup-ideas",
                    "source_path": "/tmp/startup-ideas.md",
                    "ask_alignment": 40,
                    "score": 160,
                },
                {
                    "category": "documents",
                    "name": "founder-notes",
                    "source_path": "/tmp/founder-notes.md",
                    "ask_alignment": 10,
                    "score": 110,
                },
            ]
        },
        ask_outcomes=[
            {
                "question": "What startup ideas keep recurring?",
                "summary": "Startup ideas are becoming a durable founder thread.",
                "tags": ["startup", "ideas", "founder"],
                "kind": "inferred-pattern",
            }
        ],
        limit=5,
    )

    assert candidates[0]["page"] == "topics/startup-ideas"
    assert candidates[0]["page_type"] == "topic"
    assert candidates[0]["source_paths"] == ["/tmp/startup-ideas.md", "/tmp/founder-notes.md"]
    assert candidates[0]["ask_count"] == 1


def test_derive_page_candidates_creates_query_output_when_ask_has_no_source_match():
    candidates = derive_page_candidates(
        backlog={"candidates": []},
        ask_outcomes=[
            {
                "question": "How should I update my LinkedIn headline?",
                "summary": "Founder-plus-product-builder positioning is the strongest direction.",
                "tags": ["linkedin", "positioning", "founder"],
                "kind": "insight",
            }
        ],
        limit=5,
    )

    assert candidates[0]["page"].startswith("queries/")
    assert candidates[0]["page_type"] == "query-output"
    assert candidates[0]["source_paths"] == []
    assert candidates[0]["ask_count"] == 1


def test_derive_page_candidates_emits_source_summary_for_unclustered_source():
    candidates = derive_page_candidates(
        backlog={
            "candidates": [
                {
                    "category": "documents",
                    "name": "market-map",
                    "source_path": "/tmp/market-map.md",
                    "ask_alignment": 0,
                    "score": 90,
                }
            ]
        },
        ask_outcomes=[],
        limit=5,
    )

    assert candidates[0]["page"] == "sources/market-map"
    assert candidates[0]["page_type"] == "source-summary"
    assert candidates[0]["source_paths"] == ["/tmp/market-map.md"]
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
pytest skills/ingest/augur/tests/test_wiki_page_candidates.py -q
```

Expected:

```text
FAILED ... ModuleNotFoundError: No module named 'skills.ingest.scripts.wiki_page_candidates'
```

- [ ] **Step 3: Implement dynamic candidate extraction**

Create `skills/ingest/scripts/wiki_page_candidates.py`:

```python
"""Derive wiki page candidates from backlog entries and retained `/ask` outcomes."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


def derive_page_candidates(
    *,
    backlog: dict[str, Any],
    ask_outcomes: list[dict[str, Any]],
    limit: int = 10,
) -> list[dict[str, Any]]:
    backlog_items = list(backlog.get("candidates", []))
    ask_outcomes = list(ask_outcomes or [])

    grouped_sources: dict[str, list[dict[str, Any]]] = defaultdict(list)
    grouped_asks: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for item in backlog_items:
        key = _topic_key(item.get("name") or item.get("source_path") or "")
        grouped_sources[key].append(item)

    for ask in ask_outcomes:
        key = _topic_key(" ".join(
            [
                str(ask.get("question") or ""),
                str(ask.get("summary") or ""),
                " ".join(str(tag) for tag in ask.get("tags", [])),
            ]
        ))
        grouped_asks[key].append(ask)

    candidates: list[dict[str, Any]] = []
    used_keys: set[str] = set()

    for key in sorted(set(grouped_sources) | set(grouped_asks)):
        source_group = grouped_sources.get(key, [])
        ask_group = grouped_asks.get(key, [])
        if source_group:
            page_type = "topic" if ask_group or len(source_group) > 1 else "source-summary"
            prefix = "topics" if page_type == "topic" else "sources"
        else:
            page_type = "query-output"
            prefix = "queries"

        page_slug = _slugify(key) or "note"
        used_keys.add(page_slug)
        candidates.append(
            {
                "page": f"{prefix}/{page_slug}",
                "page_type": page_type,
                "title": _title_for(page_slug, page_type),
                "source_paths": sorted(
                    {
                        str(item.get("source_path") or "").strip()
                        for item in source_group
                        if str(item.get("source_path") or "").strip()
                    }
                ),
                "sources": source_group,
                "ask_items": ask_group,
                "ask_count": len(ask_group),
                "score": sum(int(item.get("score") or 0) for item in source_group) + (len(ask_group) * 50),
            }
        )

    candidates.sort(key=lambda item: (item["score"], item["page"]), reverse=True)
    return candidates[: max(limit, 0)]


def _topic_key(text: str) -> str:
    lowered = str(text).lower()
    hints = (
        "startup ideas",
        "founder positioning",
        "learning system",
        "management style",
        "developer workflow",
        "local execution",
    )
    for hint in hints:
        if hint in lowered:
            return hint
    tokens = re.findall(r"[a-z0-9]+", lowered)
    return " ".join(tokens[:4]).strip()


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)


def _title_for(slug: str, page_type: str) -> str:
    words = slug.replace("-", " ").title()
    if page_type == "source-summary":
        return f"{words} Source Summary"
    if page_type == "query-output":
        return f"{words} Query Output"
    return words
```

- [ ] **Step 4: Run the tests to verify candidate extraction passes**

Run:

```bash
pytest skills/ingest/augur/tests/test_wiki_page_candidates.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/wiki_page_candidates.py \
  skills/ingest/augur/tests/test_wiki_page_candidates.py
git commit -m "feat(wiki): derive dynamic page candidates"
```

---

## Task 2: Teach Wiki Pages About Page Types

**Files:**
- Create: `skills/ingest/augur/tests/test_wiki_pages.py`
- Modify: `skills/ingest/scripts/wiki_pages.py`

- [ ] **Step 1: Write the failing page-type tests**

Create `skills/ingest/augur/tests/test_wiki_pages.py`:

```python
from pathlib import Path

from skills.ingest.scripts.wiki_pages import WikiPages


def test_wiki_pages_write_persists_page_type(tmp_path: Path):
    wiki_dir = tmp_path / "wiki"
    runtime_dir = tmp_path / "runtime" / "wiki"
    wp = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_dir)

    path = wp.write(
        page="topics/startup-ideas",
        title="Startup Ideas",
        tags=["startup", "ideas"],
        sources=["/tmp/startup-ideas.md"],
        body="# Startup Ideas\n\nCompiled page.\n",
        hub="brain",
        page_type="topic",
    )

    page = wp.read("topics/startup-ideas")
    assert path.exists()
    assert page["page_type"] == "topic"
    assert wp.list_pages()[0]["page_type"] == "topic"
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:

```bash
pytest skills/ingest/augur/tests/test_wiki_pages.py::test_wiki_pages_write_persists_page_type -q
```

Expected:

```text
FAILED ... TypeError: write() got an unexpected keyword argument 'page_type'
```

- [ ] **Step 3: Add explicit page-type support to `WikiPages`**

Update `skills/ingest/scripts/wiki_pages.py`:

```python
class WikiPages:
    def write(
        self,
        *,
        page: str,
        title: str,
        tags: list[str],
        sources: list[str],
        body: str,
        hub: str,
        page_type: str = "overview",
    ) -> Path:
        metadata: dict[str, Any] = {
            "title": title,
            "type": "wiki-page",
            "page_type": page_type,
            "hub": hub,
            "tags": tags,
            "sources": sources,
            "updated": now,
            "source_fingerprint": compute_source_fingerprint(sources),
        }
```

Also update `read()`, `list_pages()`, and `_rebuild_metadata()`:

```python
return {
    "title": meta.get("title", page_path.stem),
    "page_type": meta.get("page_type", "overview"),
    ...
}
```

- [ ] **Step 4: Run the targeted compiler test**

Run:

```bash
pytest skills/ingest/augur/tests/test_wiki_pages.py::test_wiki_pages_write_persists_page_type -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/wiki_pages.py \
  skills/ingest/augur/tests/test_wiki_pages.py
git commit -m "feat(wiki): preserve explicit page types"
```

---

## Task 3: Compile A Small Backlog Batch Into Real Wiki Pages

**Files:**
- Create: `skills/ingest/scripts/wiki_compiler.py`
- Create: `skills/ingest/augur/tests/test_wiki_compiler.py`
- Modify: `skills/ingest/scripts/wiki_pages.py`

- [ ] **Step 1: Write the failing batch compiler tests**

Create `skills/ingest/augur/tests/test_wiki_compiler.py`:

```python
from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter

from skills.ingest.scripts.wiki_compiler import compile_batch
from skills.ingest.scripts.wiki_pages import WikiPages


def test_compile_batch_creates_topic_and_source_summary_pages(tmp_path: Path):
    vault_dir = tmp_path / "vault"
    wiki_dir = vault_dir / "wiki"
    runtime_wiki_dir = tmp_path / "runtime" / "wiki"
    rag_dir = tmp_path / "rag"

    source_path = vault_dir / "brain" / "startup-ideas.md"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        "# Startup Ideas\n\nRecurring founder startup ideas keep showing up.\n",
        encoding="utf-8",
    )

    write_frontmatter(
        rag_dir / "vault" / "brain" / "startup-ideas.md",
        {
            "type": "vault",
            "name": "startup-ideas",
            "source_path": str(source_path),
            "checksum": "ideas-1",
            "modified": "2026-04-14T10:00:00+00:00",
        },
        "",
    )

    result = compile_batch(
        wiki_dir=wiki_dir,
        runtime_wiki_dir=runtime_wiki_dir,
        rag_dir=rag_dir,
        ask_outcomes=[
            {
                "question": "What startup ideas keep recurring?",
                "summary": "Startup ideas are a durable founder thread.",
                "tags": ["startup", "ideas", "founder"],
                "kind": "inferred-pattern",
            }
        ],
        limit=5,
    )

    wp = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_wiki_dir)
    topic_page = wp.read("topics/startup-ideas")
    source_page = wp.read("sources/startup-ideas")
    rag_meta, _ = parse_frontmatter(rag_dir / "vault" / "brain" / "startup-ideas.md")

    assert result["compiled_pages"] == ["sources/startup-ideas", "topics/startup-ideas"]
    assert topic_page["page_type"] == "topic"
    assert "Current Thesis" in topic_page["body"]
    assert source_page["page_type"] == "source-summary"
    assert rag_meta["wiki_compile_status"] == "compiled"
    assert "topics/startup-ideas" in rag_meta["wiki_targets"]


def test_compile_batch_creates_query_output_for_unmatched_durable_ask(tmp_path: Path):
    wiki_dir = tmp_path / "wiki"
    runtime_wiki_dir = tmp_path / "runtime" / "wiki"
    rag_dir = tmp_path / "rag"

    result = compile_batch(
        wiki_dir=wiki_dir,
        runtime_wiki_dir=runtime_wiki_dir,
        rag_dir=rag_dir,
        ask_outcomes=[
            {
                "question": "How should I position Augur on LinkedIn?",
                "summary": "Founder-plus-product-builder framing is strongest.",
                "tags": ["linkedin", "founder", "positioning"],
                "kind": "insight",
            }
        ],
        limit=5,
    )

    wp = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_wiki_dir)
    page_key = result["compiled_pages"][0]
    query_page = wp.read(page_key)

    assert page_key.startswith("queries/")
    assert query_page["page_type"] == "query-output"
    assert "Source Basis" in query_page["body"]
```

- [ ] **Step 2: Run the compiler tests to verify they fail**

Run:

```bash
pytest skills/ingest/augur/tests/test_wiki_compiler.py -q
```

Expected:

```text
FAILED ... ModuleNotFoundError: No module named 'skills.ingest.scripts.wiki_compiler'
```

- [ ] **Step 3: Implement the batch compiler**

Create `skills/ingest/scripts/wiki_compiler.py`:

```python
"""Compile backlog candidates into real wiki pages."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .wiki_compile_backlog import build_compile_backlog, mark_rag_entries_compiled
from .wiki_page_candidates import derive_page_candidates
from .wiki_pages import WikiPages


def compile_batch(
    *,
    wiki_dir: Path,
    runtime_wiki_dir: Path,
    rag_dir: Path,
    ask_outcomes: list[dict[str, Any]],
    limit: int = 5,
) -> dict[str, Any]:
    wp = WikiPages(wiki_dir=Path(wiki_dir), runtime_wiki_dir=Path(runtime_wiki_dir))
    backlog = build_compile_backlog(rag_dir=Path(rag_dir), ask_outcomes=ask_outcomes, limit=limit)
    candidates = derive_page_candidates(backlog=backlog, ask_outcomes=ask_outcomes, limit=limit)

    compiled_pages: list[str] = []
    consumed_sources: dict[str, set[str]] = {}

    for candidate in candidates:
        page_key = candidate["page"]
        body = _render_page_body(candidate)
        wp.write(
            page=page_key,
            title=candidate["title"],
            tags=_tags_for(candidate),
            sources=candidate["source_paths"],
            body=body,
            hub=_hub_for(candidate),
            page_type=candidate["page_type"],
        )
        compiled_pages.append(page_key)

        for source_path in candidate["source_paths"]:
            consumed_sources.setdefault(source_path, set()).add(page_key)

        if candidate["page_type"] == "topic" and len(candidate["source_paths"]) == 1:
            source_slug = page_key.split("/", 1)[1]
            source_page = f"sources/{source_slug}"
            wp.write(
                page=source_page,
                title=f"{candidate['title']} Source Summary",
                tags=["source-summary"],
                sources=candidate["source_paths"],
                body=_render_source_summary(candidate),
                hub=_hub_for(candidate),
                page_type="source-summary",
            )
            compiled_pages.insert(-1, source_page)
            consumed_sources.setdefault(candidate["source_paths"][0], set()).add(source_page)

    for source_path, wiki_targets in consumed_sources.items():
        mark_rag_entries_compiled(
            rag_dir=Path(rag_dir),
            source_paths=[source_path],
            wiki_targets=sorted(wiki_targets),
        )

    return {
        "summary": backlog["summary"],
        "candidate_count": len(candidates),
        "compiled_pages": compiled_pages,
    }


def _render_page_body(candidate: dict[str, Any]) -> str:
    ask_lines = [str(item.get("summary") or "").strip() for item in candidate["ask_items"] if str(item.get("summary") or "").strip()]
    source_lines = [Path(path).name for path in candidate["source_paths"]]
    return "\n".join(
        [
            f"# {candidate['title']}",
            "",
            "## Current Thesis",
            "",
            ask_lines[0] if ask_lines else f"This page compiles the strongest current signal around {candidate['title'].lower()}.",
            "",
            "## What This Page Knows",
            "",
            *(f"- {line}" for line in (ask_lines or source_lines or ["No evidence captured yet."])),
            "",
            "## Source Basis",
            "",
            *(f"- `{path}`" for path in candidate["source_paths"]) or ["- Retained `/ask` outcome"],
        ]
    )


def _render_source_summary(candidate: dict[str, Any]) -> str:
    source_path = candidate["source_paths"][0]
    return "\n".join(
        [
            f"# {candidate['title']} Source Summary",
            "",
            "## Summary",
            "",
            f"This page captures the currently compiled value of `{source_path}`.",
            "",
            "## Source Basis",
            "",
            f"- `{source_path}`",
        ]
    )


def _tags_for(candidate: dict[str, Any]) -> list[str]:
    base = [candidate["page_type"]]
    if candidate["page_type"] == "topic":
        base.append("compiled")
    return base


def _hub_for(candidate: dict[str, Any]) -> str:
    if candidate["source_paths"]:
        path = Path(candidate["source_paths"][0])
        return path.parent.name or "general"
    return "knowledge"
```

- [ ] **Step 4: Run the compiler tests to verify they pass**

Run:

```bash
pytest skills/ingest/augur/tests/test_wiki_compiler.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/wiki_compiler.py \
  skills/ingest/augur/tests/test_wiki_compiler.py \
  skills/ingest/scripts/wiki_pages.py
git commit -m "feat(wiki): compile backlog batches into real pages"
```

---

## Task 4: Expose Batch Compilation Through Wiki MCP Tools

**Files:**
- Modify: `skills/ingest/scripts/mcp/wiki_tools.py`
- Modify: `skills/ingest/augur/tests/test_wiki_tools.py`
- Modify: `skills/ingest/SKILL.md`

- [ ] **Step 1: Write the failing MCP tool tests**

Append to `skills/ingest/augur/tests/test_wiki_tools.py`:

```python
def test_registers_wiki_compile_preview_tool(monkeypatch) -> None:
    from skills.ingest.scripts.mcp import wiki_tools

    fake_mcp = _FakeMCP()
    metrics = _FakeMetrics()

    monkeypatch.setattr(
        wiki_tools,
        "derive_page_candidates",
        lambda **_: [{"page": "topics/startup-ideas", "page_type": "topic", "score": 150}],
    )
    monkeypatch.setattr(
        wiki_tools,
        "build_compile_backlog",
        lambda **_: {"summary": {"pending": 2}, "candidates": []},
    )
    monkeypatch.setattr(wiki_tools, "_load_recent_ask_outcomes", lambda **_: [])

    wiki_tools.register_wiki_tools(fake_mcp, _identity, metrics)
    payload = json.loads(asyncio.run(fake_mcp.tools"wiki-compile-preview"))

    assert payload["success"] is True
    assert payload["candidates"][0]["page"] == "topics/startup-ideas"


def test_registers_wiki_compile_batch_tool(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts.mcp import wiki_tools

    fake_mcp = _FakeMCP()
    metrics = _FakeMetrics()

    monkeypatch.setattr("src.config.paths.get_wiki_dir", lambda: tmp_path / "wiki")
    monkeypatch.setattr("src.config.paths.get_runtime_dir", lambda: tmp_path / "runtime")
    monkeypatch.setattr("src.config.paths.get_rag_dir", lambda: tmp_path / "rag")
    monkeypatch.setattr(
        wiki_tools,
        "compile_batch",
        lambda **_: {"compiled_pages": ["topics/startup-ideas"], "candidate_count": 1, "summary": {"pending": 2}},
    )
    monkeypatch.setattr(wiki_tools, "_load_recent_ask_outcomes", lambda **_: [])

    wiki_tools.register_wiki_tools(fake_mcp, _identity, metrics)
    payload = json.loads(asyncio.run(fake_mcp.tools"wiki-compile-batch"))

    assert payload["success"] is True
    assert payload["compiled_pages"] == ["topics/startup-ideas"]
```

- [ ] **Step 2: Run the MCP tests to verify they fail**

Run:

```bash
pytest skills/ingest/augur/tests/test_wiki_tools.py::test_registers_wiki_compile_preview_tool \
  skills/ingest/augur/tests/test_wiki_tools.py::test_registers_wiki_compile_batch_tool -q
```

Expected:

```text
FAILED ... KeyError: 'wiki-compile-preview'
```

- [ ] **Step 3: Register preview + compile tools**

Update `skills/ingest/scripts/mcp/wiki_tools.py`:

```python
    @mcp.tool(
        name="wiki-compile-preview",
        annotations=tool_annotations({"title": "Wiki Compile Preview", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_compile_preview(limit: int = 5) -> str:
        metrics.track_tool("wiki_compile_preview", skill="ingest")
        from src.config.paths import get_rag_dir
        from wiki_compile_backlog import build_compile_backlog
        from wiki_page_candidates import derive_page_candidates

        ask_outcomes = _load_recent_ask_outcomes(days_back=14, limit=limit * 5)
        backlog = build_compile_backlog(rag_dir=get_rag_dir(), ask_outcomes=ask_outcomes, limit=limit * 2)
        candidates = derive_page_candidates(backlog=backlog, ask_outcomes=ask_outcomes, limit=limit)
        return json.dumps({"success": True, "summary": backlog["summary"], "candidates": candidates}, indent=2, default=str)


    @mcp.tool(
        name="wiki-compile-batch",
        annotations=tool_annotations({"title": "Wiki Compile Batch", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_compile_batch(limit: int = 5) -> str:
        metrics.track_tool("wiki_compile_batch", skill="ingest")
        from src.config.paths import get_rag_dir, get_runtime_dir, get_wiki_dir
        from wiki_compiler import compile_batch

        ask_outcomes = _load_recent_ask_outcomes(days_back=14, limit=limit * 5)
        result = compile_batch(
            wiki_dir=get_wiki_dir(),
            runtime_wiki_dir=get_runtime_dir() / "wiki",
            rag_dir=get_rag_dir(),
            ask_outcomes=ask_outcomes,
            limit=limit,
        )
        return json.dumps({"success": True, **result}, indent=2, default=str)
```

Update `skills/ingest/SKILL.md` to add:

```md
- wiki-compile-preview
- wiki-compile-batch
```

and document:

```md
Phase 2 compiler behavior consumes the phase-1 backlog in small batches, creates first-class `topic`, `query-output`, and `source-summary` pages, and stamps consumed `vault` / `documents` entries as compiled.
```

- [ ] **Step 4: Run the MCP tests to verify they pass**

Run:

```bash
pytest skills/ingest/augur/tests/test_wiki_tools.py::test_registers_wiki_compile_preview_tool \
  skills/ingest/augur/tests/test_wiki_tools.py::test_registers_wiki_compile_batch_tool -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/mcp/wiki_tools.py \
  skills/ingest/augur/tests/test_wiki_tools.py \
  skills/ingest/SKILL.md
git commit -m "feat(wiki): expose batch compiler tools"
```

---

## Task 5: Run The Phase-Two Proving Slice

**Files:**
- Modify: `skills/ingest/augur/tests/test_wiki_page_candidates.py`
- Modify: `skills/ingest/augur/tests/test_wiki_compiler.py`
- Modify: `skills/ingest/augur/tests/test_wiki_tools.py`

- [ ] **Step 1: Run the focused compiler suite**

Run:

```bash
pytest \
  skills/ingest/augur/tests/test_wiki_page_candidates.py \
  skills/ingest/augur/tests/test_wiki_pages.py \
  skills/ingest/augur/tests/test_wiki_compiler.py \
  skills/ingest/augur/tests/test_wiki_tools.py \
  skills/ingest/augur/tests/test_wiki_compile_backlog.py \
  skills/ingest/augur/tests/test_wiki_maintenance.py -q
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 2: Verify live preview returns real page candidates**

Run:

```bash
PYTHONPATH="$(pwd):$(pwd)/src/mcp" python3 - <<'PY'
from src.config.paths import get_rag_dir
from skills.ingest.scripts.ask_sync import load_recent_ask_outcomes
from skills.ingest.scripts.wiki_compile_backlog import build_compile_backlog
from skills.ingest.scripts.wiki_page_candidates import derive_page_candidates

ask_outcomes = load_recent_ask_outcomes(limit=25)
backlog = build_compile_backlog(
    rag_dir=get_rag_dir(),
    ask_outcomes=ask_outcomes,
    limit=10,
)
candidates = derive_page_candidates(
    backlog=backlog,
    ask_outcomes=ask_outcomes,
    limit=5,
)
print(backlog["summary"])
print(candidates[:3])
PY
```

Expected:

```text
summary dict with pending / compiled counts
top 3 candidate pages with `page` and `page_type`
```

- [ ] **Step 3: Verify a live compile batch creates new non-overview pages**

Run:

```bash
PYTHONPATH="$(pwd):$(pwd)/src/mcp" python3 - <<'PY'
from src.config.paths import get_rag_dir, get_runtime_dir, get_wiki_dir
from skills.ingest.scripts.ask_sync import load_recent_ask_outcomes
from skills.ingest.scripts.wiki_compiler import compile_batch
from skills.ingest.scripts.wiki_pages import WikiPages

result = compile_batch(
    wiki_dir=get_wiki_dir(),
    runtime_wiki_dir=get_runtime_dir() / "wiki",
    rag_dir=get_rag_dir(),
    ask_outcomes=load_recent_ask_outcomes(limit=20),
    limit=3,
)
print(result)

wp = WikiPages(wiki_dir=get_wiki_dir(), runtime_wiki_dir=get_runtime_dir() / "wiki")
for page in result["compiled_pages"]:
    print(page, wp.read(page)["page_type"])
PY
```

Expected:

```text
compiled_pages list contains `topics/...`, `queries/...`, or `sources/...`
each printed page shows non-overview `page_type`
```

- [ ] **Step 4: Commit**

```bash
git add skills/ingest/scripts/wiki_page_candidates.py \
  skills/ingest/scripts/wiki_compiler.py \
  skills/ingest/scripts/wiki_pages.py \
  skills/ingest/scripts/mcp/wiki_tools.py \
  skills/ingest/augur/tests/test_wiki_page_candidates.py \
  skills/ingest/augur/tests/test_wiki_pages.py \
  skills/ingest/augur/tests/test_wiki_compiler.py \
  skills/ingest/augur/tests/test_wiki_tools.py \
  skills/ingest/SKILL.md
git commit -m "feat(wiki): compile backlog into first-class pages"
```

---

## Notes For The Next Plan

This slice intentionally stops after proving real backlog-to-page compilation. After it lands, the next plan should cover:

- deeper multi-source clustering beyond simple topic keys
- entity and comparison page creation
- better source-body summarization than filename/title-based thesis seeding
- batch scheduling / rate limiting policy for long backlogs
- stronger lint rules for thin or duplicate compiled pages
