# RAG-Backed Wiki Compile State Implementation Plan

> **Superseded by ADR-561.** This artifact describes the retired RAG-backed wiki compile-state model. It remains historical context only. Do not implement or extend the `source-summary`, `wiki_compile_status`, `wiki_targets`, or `wiki-compile-*` backlog semantics from this document.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the new LLM-wiki architecture by reusing existing RAG entries as the indexed-source inventory, adding wiki compile-state semantics to those entries, exposing a prioritized backlog, and stamping sources as compiled when wiki rewrites consume them.

**Architecture:** This is phase 1 of the broader compiler architecture in `docs/superpowers/specs/2026-04-14-llm-wiki-architecture-design.md`. Extend existing RAG entry frontmatter rather than creating a second registry, add a small backlog module that classifies `pending` vs `needs-recompile` using current RAG metadata plus retained `/ask` signals, then hook the current wiki rewrite flow so successful rewrites mark matching RAG entries as compiled for their current checksum.

**Tech Stack:** Python 3.11, YAML frontmatter, existing RAG pointer entries in `get_rag_dir()`, existing wiki maintenance + MCP tools, pytest

**Spec:** `docs/superpowers/specs/2026-04-14-llm-wiki-architecture-design.md`

---

## File Structure

### Create

| File | Responsibility |
|---|---|
| `skills/ingest/scripts/wiki_compile_backlog.py` | Read RAG entry files, classify compile status, score candidates, and stamp entries as compiled |
| `skills/ingest/augur/tests/test_wiki_compile_backlog.py` | TDD coverage for compile-state classification, `/ask`-weighted prioritization, and mark-compiled behavior |

### Modify

| File | Change |
|---|---|
| `skills/rag/scripts/_indexer_helpers.py` | Preserve existing wiki compile metadata when a RAG entry is rewritten by reindexing |
| `skills/rag/augur/tests/test_index_reader.py` | Verify index entry reads expose compile-state fields unchanged |
| `skills/rag/augur/tests/test_unified_indexer.py` | Verify reindexing preserves wiki compile metadata on entry rewrites |
| `skills/ingest/scripts/wiki_maintenance.py` | Mark matching RAG entries compiled after `apply_rewrite_proposals()` writes wiki pages |
| `skills/ingest/scripts/mcp/wiki_tools.py` | Add a read-only `wiki-compile-backlog` tool for backlog visibility |
| `skills/ingest/augur/tests/test_wiki_maintenance.py` | Verify rewrite application stamps consumed RAG entries with compile metadata |
| `skills/ingest/augur/tests/test_wiki_tools.py` | Verify the new backlog MCP tool returns ranked candidates and summary counts |
| `skills/ingest/SKILL.md` | Document the new backlog tool and compile-state-backed phase-1 behavior |

---

## Task 1: Preserve Wiki Compile Metadata During RAG Reindex

**Files:**
- Modify: `skills/rag/scripts/_indexer_helpers.py`
- Modify: `skills/rag/augur/tests/test_index_reader.py`
- Modify: `skills/rag/augur/tests/test_unified_indexer.py`

- [ ] **Step 1: Write the failing metadata-preservation tests**

Append to `skills/rag/augur/tests/test_index_reader.py`:

```python
def test_read_index_entry_keeps_wiki_compile_fields(tmp_path):
    from plugins.ai.skills.rag.scripts.index_reader import read_index_entry

    entry = tmp_path / "vault" / "brain" / "ideas.md"
    entry.parent.mkdir(parents=True)
    entry.write_text(
        "---\n"
        "type: vault\n"
        "hub: brain\n"
        "name: ideas\n"
        "source_path: /tmp/ideas.md\n"
        "checksum: abc123\n"
        "wiki_compile_status: compiled\n"
        "wiki_compiled_checksum: abc123\n"
        "wiki_compiled_at: 2026-04-14T09:00:00+00:00\n"
        "wiki_targets:\n"
        "  - startup-ideas\n"
        "---\n",
        encoding="utf-8",
    )

    result = read_index_entry(entry)

    assert result["wiki_compile_status"] == "compiled"
    assert result["wiki_compiled_checksum"] == "abc123"
    assert result["wiki_targets"] == ["startup-ideas"]
```

Append to `skills/rag/augur/tests/test_unified_indexer.py`:

```python
def test_write_entry_preserves_existing_wiki_compile_metadata(tmp_path):
    from plugins.ai.skills.rag.scripts._indexer_helpers import _write_entry
    from src.lib.frontmatter_utils import parse_frontmatter

    output = tmp_path / "rag" / "vault" / "brain" / "ideas.md"
    output.parent.mkdir(parents=True)
    output.write_text(
        "---\n"
        "type: vault\n"
        "source_path: /tmp/ideas.md\n"
        "checksum: old-checksum\n"
        "wiki_compile_status: compiled\n"
        "wiki_compiled_checksum: old-checksum\n"
        "wiki_compiled_at: 2026-04-14T09:00:00+00:00\n"
        "wiki_targets:\n"
        "  - startup-ideas\n"
        "---\n",
        encoding="utf-8",
    )

    _write_entry(
        output,
        {
            "type": "vault",
            "source_path": "/tmp/ideas.md",
            "checksum": "new-checksum",
        },
    )

    meta, _ = parse_frontmatter(output)
    assert meta["wiki_compile_status"] == "compiled"
    assert meta["wiki_compiled_checksum"] == "old-checksum"
    assert meta["wiki_targets"] == ["startup-ideas"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest skills/rag/augur/tests/test_index_reader.py::test_read_index_entry_keeps_wiki_compile_fields \
  skills/rag/augur/tests/test_unified_indexer.py::test_write_entry_preserves_existing_wiki_compile_metadata -q
```

Expected:

```text
FAILED ... KeyError: 'wiki_compile_status'
```

- [ ] **Step 3: Preserve compile metadata in `_write_entry()`**

Update `skills/rag/scripts/_indexer_helpers.py`:

```python
def _write_entry(output_path: Path, metadata: dict[str, Any], body: str = "") -> None:
    """Write a RAG index entry, preserving manual and wiki compile metadata."""
    if output_path.exists():
        existing_meta, _ = parse_frontmatter(output_path)
        if existing_meta.get("manual_related"):
            metadata.setdefault("manual_related", existing_meta["manual_related"])

        for key in (
            "wiki_compile_status",
            "wiki_compiled_at",
            "wiki_compiled_checksum",
            "wiki_targets",
        ):
            if existing_meta.get(key) and key not in metadata:
                metadata[key] = existing_meta[key]

    metadata["indexed_at"] = datetime.now(tz=timezone.utc).isoformat()
    write_frontmatter(output_path, metadata, body)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest skills/rag/augur/tests/test_index_reader.py::test_read_index_entry_keeps_wiki_compile_fields \
  skills/rag/augur/tests/test_unified_indexer.py::test_write_entry_preserves_existing_wiki_compile_metadata -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit**

```bash
git add skills/rag/scripts/_indexer_helpers.py \
  skills/rag/augur/tests/test_index_reader.py \
  skills/rag/augur/tests/test_unified_indexer.py
git commit -m "feat(wiki): preserve compile metadata on rag entries"
```

---

## Task 2: Build The Compile Backlog Helper Over Existing RAG Entries

**Files:**
- Create: `skills/ingest/scripts/wiki_compile_backlog.py`
- Create: `skills/ingest/augur/tests/test_wiki_compile_backlog.py`

- [ ] **Step 1: Write the failing backlog tests**

Create `skills/ingest/augur/tests/test_wiki_compile_backlog.py`:

```python
from pathlib import Path

from src.lib.frontmatter_utils import write_frontmatter

from skills.ingest.scripts.wiki_compile_backlog import (
    build_compile_backlog,
    classify_compile_status,
    mark_rag_entries_compiled,
)


def _write_rag_entry(path: Path, **meta) -> None:
    write_frontmatter(path, meta, "")


def test_classify_compile_status_pending_vs_needs_recompile():
    assert classify_compile_status({"checksum": "abc"}) == "pending"
    assert classify_compile_status(
        {
            "checksum": "abc",
            "wiki_compiled_checksum": "old",
            "wiki_compile_status": "compiled",
        }
    ) == "needs-recompile"
    assert classify_compile_status(
        {
            "checksum": "abc",
            "wiki_compiled_checksum": "abc",
            "wiki_compiled_at": "2026-04-14T09:00:00+00:00",
        }
    ) == "compiled"


def test_build_compile_backlog_prioritizes_ask_aligned_entries(tmp_path):
    rag_dir = tmp_path / "rag"

    _write_rag_entry(
        rag_dir / "vault" / "brain" / "startup-ideas.md",
        type="vault",
        name="startup-ideas",
        source_path="/tmp/startup-ideas.md",
        checksum="ideas-1",
        modified="2026-04-14T09:00:00+00:00",
    )
    _write_rag_entry(
        rag_dir / "documents" / "career" / "resume.md",
        type="document",
        name="resume",
        source_path="/tmp/resume.md",
        checksum="resume-1",
        modified="2026-04-14T09:00:00+00:00",
    )

    backlog = build_compile_backlog(
        rag_dir=rag_dir,
        ask_outcomes=[
            {
                "question": "What startup ideas keep recurring?",
                "summary": "Startup ideas are becoming a durable thread.",
                "tags": ["startup", "ideas"],
            }
        ],
        limit=5,
    )

    assert backlog["summary"]["pending"] == 2
    assert backlog["candidates"][0]["name"] == "startup-ideas"
    assert backlog["candidates"][0]["ask_alignment"] > 0


def test_mark_rag_entries_compiled_updates_matching_sources(tmp_path):
    rag_dir = tmp_path / "rag"
    entry = rag_dir / "vault" / "brain" / "ideas.md"
    _write_rag_entry(
        entry,
        type="vault",
        name="ideas",
        source_path="/tmp/ideas.md",
        checksum="ideas-1",
    )

    updated = mark_rag_entries_compiled(
        rag_dir=rag_dir,
        source_paths=["/tmp/ideas.md"],
        wiki_targets=["startup-ideas", "brain/overview"],
        compiled_at="2026-04-14T10:00:00+00:00",
    )

    assert str(entry) in updated
    from src.lib.frontmatter_utils import parse_frontmatter

    meta, _ = parse_frontmatter(entry)
    assert meta["wiki_compile_status"] == "compiled"
    assert meta["wiki_compiled_checksum"] == "ideas-1"
    assert meta["wiki_targets"] == ["brain/overview", "startup-ideas"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest skills/ingest/augur/tests/test_wiki_compile_backlog.py -q
```

Expected:

```text
FAILED ... ModuleNotFoundError: No module named 'skills.ingest.scripts.wiki_compile_backlog'
```

- [ ] **Step 3: Implement the backlog helper**

Create `skills/ingest/scripts/wiki_compile_backlog.py`:

```python
"""RAG-backed wiki compile backlog helpers."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter


_COMPILE_CATEGORIES = ("vault", "documents", "pages", "actions", "commands", "integrations", "skills", "adrs")
_CATEGORY_WEIGHTS = {
    "vault": 90,
    "documents": 85,
    "pages": 75,
    "actions": 65,
    "commands": 65,
    "integrations": 60,
    "skills": 55,
    "adrs": 40,
}


def classify_compile_status(entry: dict[str, Any]) -> str:
    explicit = str(entry.get("wiki_compile_status") or "").strip()
    checksum = str(entry.get("checksum") or "").strip()
    compiled_checksum = str(entry.get("wiki_compiled_checksum") or "").strip()

    if explicit in {"deferred", "failed"}:
        return explicit
    if checksum and compiled_checksum == checksum and entry.get("wiki_compiled_at"):
        return "compiled"
    if checksum and compiled_checksum and compiled_checksum != checksum:
        return "needs-recompile"
    return "pending"


def build_compile_backlog(
    *,
    rag_dir: Path,
    ask_outcomes: list[dict[str, Any]] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    ask_outcomes = ask_outcomes or []

    for entry_path in _iter_rag_entries(Path(rag_dir)):
        meta, _ = parse_frontmatter(entry_path)
        status = classify_compile_status(meta)
        status_counts[status] += 1
        if status == "compiled":
            continue

        ask_alignment = _ask_alignment_score(meta, ask_outcomes)
        category = str(entry_path.relative_to(rag_dir).parts[0])
        score = _CATEGORY_WEIGHTS.get(category, 0) + ask_alignment
        if status == "needs-recompile":
            score += 25

        candidates.append(
            {
                "entry_path": str(entry_path),
                "category": category,
                "name": str(meta.get("name") or entry_path.stem),
                "source_path": str(meta.get("source_path") or ""),
                "status": status,
                "checksum": str(meta.get("checksum") or ""),
                "modified": str(meta.get("modified") or ""),
                "ask_alignment": ask_alignment,
                "score": score,
            }
        )

    candidates.sort(key=lambda item: (item["score"], item["modified"], item["name"]), reverse=True)
    return {
        "summary": {
            "pending": status_counts["pending"],
            "needs_recompile": status_counts["needs-recompile"],
            "deferred": status_counts["deferred"],
            "failed": status_counts["failed"],
        },
        "candidates": candidates[: max(limit, 0)],
    }


def mark_rag_entries_compiled(
    *,
    rag_dir: Path,
    source_paths: list[str],
    wiki_targets: list[str],
    compiled_at: str | None = None,
) -> list[str]:
    source_set = {str(item).strip() for item in source_paths if str(item).strip()}
    target_list = sorted(dict.fromkeys(str(item).strip() for item in wiki_targets if str(item).strip()))
    if not source_set:
        return []

    compiled_stamp = compiled_at or datetime.now(tz=timezone.utc).isoformat()
    updated: list[str] = []

    for entry_path in _iter_rag_entries(Path(rag_dir)):
        meta, body = parse_frontmatter(entry_path)
        if str(meta.get("source_path") or "").strip() not in source_set:
            continue
        checksum = str(meta.get("checksum") or "").strip()
        meta["wiki_compile_status"] = "compiled"
        meta["wiki_compiled_at"] = compiled_stamp
        meta["wiki_compiled_checksum"] = checksum
        meta["wiki_targets"] = target_list
        write_frontmatter(entry_path, meta, body)
        updated.append(str(entry_path))

    return updated


def _iter_rag_entries(rag_dir: Path):
    for category in _COMPILE_CATEGORIES:
        category_dir = rag_dir / category
        if not category_dir.exists():
            continue
        yield from sorted(category_dir.rglob("*.md"))


def _ask_alignment_score(entry: dict[str, Any], ask_outcomes: list[dict[str, Any]]) -> int:
    haystack = " ".join(
        [
            str(entry.get("name") or ""),
            str(entry.get("description") or ""),
            str(entry.get("source_path") or ""),
        ]
    ).lower()
    score = 0
    for item in ask_outcomes:
        tokens = " ".join(
            [
                str(item.get("question") or ""),
                str(item.get("summary") or ""),
                " ".join(str(tag) for tag in item.get("tags", [])),
            ]
        ).lower().split()
        if any(token and token in haystack for token in tokens):
            score += 30
    return score
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest skills/ingest/augur/tests/test_wiki_compile_backlog.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/wiki_compile_backlog.py \
  skills/ingest/augur/tests/test_wiki_compile_backlog.py
git commit -m "feat(wiki): add rag-backed compile backlog helpers"
```

---

## Task 3: Expose The Compile Backlog Through Wiki MCP Tools

**Files:**
- Modify: `skills/ingest/scripts/mcp/wiki_tools.py`
- Modify: `skills/ingest/augur/tests/test_wiki_tools.py`
- Modify: `skills/ingest/SKILL.md`

- [ ] **Step 1: Write the failing MCP tool test**

Append to `skills/ingest/augur/tests/test_wiki_tools.py`:

```python
def test_registers_wiki_compile_backlog_tool(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts.mcp import wiki_tools

    fake_mcp = _FakeMCP()
    metrics = _FakeMetrics()

    monkeypatch.setattr(
        "skills.ingest.scripts.wiki_compile_backlog.build_compile_backlog",
        lambda **_: {
            "summary": {
                "pending": 2,
                "needs_recompile": 1,
                "deferred": 0,
                "failed": 0,
            },
            "candidates": [
                {
                    "name": "startup-ideas",
                    "status": "pending",
                    "category": "vault",
                    "score": 120,
                }
            ],
        },
    )

    wiki_tools.register_wiki_tools(fake_mcp, _identity, metrics)

    tool = fake_mcp.tools["wiki-compile-backlog"]
    payload = json.loads(asyncio.run(tool(limit=5)))

    assert payload["success"] is True
    assert payload["summary"]["pending"] == 2
    assert payload["candidates"][0]["name"] == "startup-ideas"
    assert ("wiki_compile_backlog", "ingest") in metrics.calls
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest skills/ingest/augur/tests/test_wiki_tools.py::test_registers_wiki_compile_backlog_tool -q
```

Expected:

```text
FAILED ... KeyError: 'wiki-compile-backlog'
```

- [ ] **Step 3: Register the new read-only backlog tool**

Append to `skills/ingest/scripts/mcp/wiki_tools.py`:

```python
    @mcp.tool(
        name="wiki-compile-backlog",
        annotations=tool_annotations(
            {
                "title": "Wiki Compile Backlog",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def wiki_compile_backlog(limit: int = 20) -> str:
        """Return pending and stale indexed sources that have not been compiled into the wiki."""
        metrics.track_tool("wiki_compile_backlog", skill="ingest")
        try:
            from ask_sync import load_recent_ask_outcomes
            from src.config.paths import get_rag_dir
            from wiki_compile_backlog import build_compile_backlog

            backlog = build_compile_backlog(
                rag_dir=get_rag_dir(),
                ask_outcomes=load_recent_ask_outcomes(limit=max(limit * 2, 10)),
                limit=limit,
            )
            return json.dumps({"success": True, **backlog}, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})
```

Update the tool inventory in `skills/ingest/SKILL.md`:

```markdown
- `wiki-compile-backlog` — inspect indexed sources that are pending compile or need wiki recompilation
```

- [ ] **Step 4: Run the tool test to verify it passes**

Run:

```bash
pytest skills/ingest/augur/tests/test_wiki_tools.py::test_registers_wiki_compile_backlog_tool -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/mcp/wiki_tools.py \
  skills/ingest/augur/tests/test_wiki_tools.py \
  skills/ingest/SKILL.md
git commit -m "feat(wiki): expose compile backlog tool"
```

---

## Task 4: Stamp RAG Entries As Compiled When Wiki Rewrites Consume Them

**Files:**
- Modify: `skills/ingest/scripts/wiki_maintenance.py`
- Modify: `skills/ingest/augur/tests/test_wiki_maintenance.py`

- [ ] **Step 1: Write the failing rewrite-stamping test**

Append to `skills/ingest/augur/tests/test_wiki_maintenance.py`:

```python
def test_apply_rewrite_proposals_marks_matching_rag_entries_compiled(tmp_path):
    vault_dir = tmp_path / "vault"
    wiki_dir = vault_dir / "wiki"
    runtime_wiki_dir = tmp_path / "runtime" / "wiki"
    rag_dir = tmp_path / "rag"
    documents_dir = tmp_path / "documents"

    source_path = str(vault_dir / "brain" / "startup-ideas.md")
    (vault_dir / "brain").mkdir(parents=True)
    (vault_dir / "brain" / "startup-ideas.md").write_text("# Startup Ideas\n\nNew angle.\n", encoding="utf-8")
    documents_dir.mkdir(parents=True)

    write_frontmatter(
        rag_dir / "vault" / "brain" / "startup-ideas.md",
        {
            "type": "vault",
            "name": "startup-ideas",
            "source_path": source_path,
            "checksum": "ideas-1",
        },
        "",
    )

    wp = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_wiki_dir)
    wp.write(
        page="brain/overview",
        title="Brain Overview",
        tags=["brain", "overview"],
        sources=[source_path],
        body="# Brain Overview\n\nThis hub contains 1 source.\n\n## Sources\n\n- startup ideas\n",
        hub="brain",
    )

    results = apply_rewrite_proposals(
        wiki_dir=wiki_dir,
        runtime_wiki_dir=runtime_wiki_dir,
        sources=[
            {
                "hub": "brain",
                "path": source_path,
                "title": "Startup Ideas",
                "source_surface": "vault",
            }
        ],
        ask_outcomes=[],
        limit=1,
        rag_dir=rag_dir,
    )

    assert results
    meta, _ = parse_frontmatter(rag_dir / "vault" / "brain" / "startup-ideas.md")
    assert meta["wiki_compile_status"] == "compiled"
    assert meta["wiki_compiled_checksum"] == "ideas-1"
    assert "brain/overview" in meta["wiki_targets"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest skills/ingest/augur/tests/test_wiki_maintenance.py::test_apply_rewrite_proposals_marks_matching_rag_entries_compiled -q
```

Expected:

```text
FAILED ... TypeError: apply_rewrite_proposals() got an unexpected keyword argument 'rag_dir'
```

- [ ] **Step 3: Mark compiled entries after successful rewrite application**

Update the signature and body of `apply_rewrite_proposals()` in `skills/ingest/scripts/wiki_maintenance.py`:

```python
def apply_rewrite_proposals(
    *,
    wiki_dir: Path,
    runtime_wiki_dir: Path,
    sources: list[dict[str, Any]] | None = None,
    ask_outcomes: list[dict[str, Any]] | None = None,
    limit: int = 1,
    rag_dir: Path | None = None,
) -> list[dict[str, Any]]:
```

Then, after each successful page write:

```python
        if rag_dir is not None:
            from .wiki_compile_backlog import mark_rag_entries_compiled

            mark_rag_entries_compiled(
                rag_dir=Path(rag_dir),
                source_paths=resolved_sources,
                wiki_targets=[proposal["page"]],
            )

        results.append(
            {
                **proposal,
                "path": str(path),
            }
        )
```

Also update `apply_top_rewrite_proposal()` to accept and forward `rag_dir`.

- [ ] **Step 4: Run the targeted maintenance tests**

Run:

```bash
pytest skills/ingest/augur/tests/test_wiki_maintenance.py::test_apply_rewrite_proposals_marks_matching_rag_entries_compiled -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/wiki_maintenance.py \
  skills/ingest/augur/tests/test_wiki_maintenance.py
git commit -m "feat(wiki): stamp rag entries after rewrite consumption"
```

---

## Task 5: Run The Full Proving Slice And Record The New Behavior

**Files:**
- Modify: `skills/ingest/augur/tests/test_wiki_tools.py`
- Modify: `skills/ingest/augur/tests/test_wiki_maintenance.py`

- [ ] **Step 1: Run the focused slice test suite**

Run:

```bash
pytest \
  skills/rag/augur/tests/test_index_reader.py \
  skills/rag/augur/tests/test_unified_indexer.py \
  skills/ingest/augur/tests/test_wiki_compile_backlog.py \
  skills/ingest/augur/tests/test_wiki_tools.py \
  skills/ingest/augur/tests/test_wiki_maintenance.py -q
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 2: Verify the new backlog tool locally**

Run:

```bash
python3 - <<'PY'
from src.config.paths import get_rag_dir
from skills.ingest.scripts.ask_sync import load_recent_ask_outcomes
from skills.ingest.scripts.wiki_compile_backlog import build_compile_backlog

backlog = build_compile_backlog(
    rag_dir=get_rag_dir(),
    ask_outcomes=load_recent_ask_outcomes(limit=25),
    limit=10,
)
print(backlog["summary"])
print(backlog["candidates"][:3])
PY
```

Expected:

```text
summary dict with pending / needs_recompile counts
top candidates printed in score order
```

- [ ] **Step 3: Verify a live rewrite stamps consumed entries**

Run:

```bash
python3 - <<'PY'
from src.config.paths import get_documents_dir, get_logs_dir, get_rag_dir, get_runtime_dir, get_vault_dir, get_wiki_dir
from skills.ingest.scripts.ask_sync import load_recent_ask_outcomes
from skills.ingest.scripts.wiki_scanner import WikiScanner
from skills.ingest.scripts.wiki_maintenance import apply_top_rewrite_proposal
from skills.rag.scripts.index_reader import list_category_entries

scanner = WikiScanner(
    vault_dir=get_vault_dir(),
    documents_dir=get_documents_dir(),
    project_root=__import__('src.config.paths', fromlist=['get_project_root']).get_project_root(),
    runtime_dir=get_runtime_dir(),
    logs_dir=get_logs_dir(),
    ask_outcomes_loader=load_recent_ask_outcomes,
)
sources = scanner.scan()
result = apply_top_rewrite_proposal(
    wiki_dir=get_wiki_dir(),
    runtime_wiki_dir=get_runtime_dir() / "wiki",
    sources=sources,
    ask_outcomes=load_recent_ask_outcomes(limit=20),
    rag_dir=get_rag_dir(),
)
print(result["page"] if result else "no proposal")
for item in list_category_entries(get_rag_dir() / "vault", limit=3):
    if item.get("wiki_compile_status"):
        print(item["name"], item["wiki_compile_status"], item.get("wiki_targets"))
PY
```

Expected:

```text
rewritten page name (or "no proposal" if queue empty)
at least one matching rag entry shows wiki_compile_status: compiled
```

- [ ] **Step 4: Commit**

```bash
git add skills/rag/augur/tests/test_index_reader.py \
  skills/rag/augur/tests/test_unified_indexer.py \
  skills/ingest/scripts/wiki_compile_backlog.py \
  skills/ingest/scripts/wiki_maintenance.py \
  skills/ingest/scripts/mcp/wiki_tools.py \
  skills/ingest/augur/tests/test_wiki_compile_backlog.py \
  skills/ingest/augur/tests/test_wiki_tools.py \
  skills/ingest/augur/tests/test_wiki_maintenance.py \
  skills/ingest/SKILL.md
git commit -m "feat(wiki): add rag-backed compile backlog phase one"
```

---

## Notes For The Next Plan

This slice intentionally stops short of the full architecture spec. After it lands, the next plan should cover:

- compiler-driven creation of non-overview pages from backlog clusters
- deeper `/ask`-driven page creation
- rate-limited compile batch execution policies
- optional document relocation policy
- lint rules for thin or uncompiled high-signal regions
