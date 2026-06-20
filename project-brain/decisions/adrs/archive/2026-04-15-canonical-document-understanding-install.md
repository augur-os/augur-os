# Canonical Document Understanding And Install Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ambient import and RAG use one canonical document-understanding path, guarantee the baseline extraction stack on fresh macOS and Windows installs, and persist enough structured document metadata for the wiki compiler to write better imported-document pages.

**Architecture:** Add a single `document_understanding` router in the RAG skill and make `unified_indexer` delegate to it. Move `pymupdf` into the guaranteed install path, align the Windows installer with the same dependency source of truth as Unix, extend document-extractor capability reporting, and then teach the wiki compiler to prefer structured document metadata over thin raw excerpts.

**Tech Stack:** Python 3.11+, `uv`, `markitdown[all]`, `markitdown-ocr`, `pymupdf`, existing `skills/document-extractor`, `skills/rag`, `skills/ingest`, pytest

**Spec:** `~/Projects/Augur/docs/superpowers/specs/2026-04-15-canonical-document-understanding-install-design.md`

---

## File Structure

### Create

| File | Responsibility |
|------|----------------|
| `skills/rag/scripts/document_understanding.py` | Canonical router for document extraction + first-slice structured understanding |
| `skills/rag/augur/tests/test_document_understanding.py` | Cross-format routing and metadata regression tests |
| `tests/unit/test_install_document_contract.py` | Installer/onboarding contract tests that assert baseline document dependencies and Windows parity |

### Modify

| File | Change |
|------|--------|
| `pyproject.toml` | Move `pymupdf` into baseline dependencies and leave `mlx-vlm` optional |
| `uv.lock` | Refresh lockfile after dependency contract changes |
| `skills/rag/scripts/unified_indexer.py` | Delegate `_extract_document()` to `document_understanding.py` and persist structured metadata on RAG entries |
| `skills/rag/augur/tests/test_unified_indexer.py` | Assert new document metadata is written into RAG entries |
| `skills/document-extractor/scripts/mcp/tools_extract.py` | Extend `get_extraction_status_impl()` to report the baseline contract clearly, including `pymupdf` and OCR capability |
| `skills/document-extractor/augur/tests/test_tools_extract.py` | Verify richer status output |
| `skills/ingest/scripts/wiki_compiler.py` | Use RAG document metadata when rendering source-summary/topic pages for imported docs |
| `skills/ingest/scripts/wiki_page_writer.py` | Prefer structured document summary/insights over thin raw excerpts |
| `skills/ingest/augur/tests/test_wiki_compiler.py` | Cover imported-document page writing from structured metadata |
| `scripts/install.sh` | Verify baseline document capability after `uv sync` |
| `scripts/install.ps1` | Stop using the non-existent `requirements.txt` path and align Windows Python install with `uv` + baseline capability verification |
| `docs/guides/installation-windows.md` | Document the new baseline vs optional document capability contract |
| `~/.agents/skills/augur/onboard/references/mode-default.md` | Add document-capability verification to onboarding |
| `~/.agents/skills/augur/onboard/references/mode-full.md` | Ensure full onboarding includes the same verification |

---

### Task 1: Add The Canonical Document Understanding Router

**Files:**
- Create: `skills/rag/scripts/document_understanding.py`
- Test: `skills/rag/augur/tests/test_document_understanding.py`

- [ ] **Step 1: Write the failing test**

Create `skills/rag/augur/tests/test_document_understanding.py`:

```python
from pathlib import Path


def test_understand_document_prefers_pymupdf_for_text_pdf(monkeypatch, tmp_path):
    pdf = tmp_path / "guide.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    from skills.rag.scripts import document_understanding

    monkeypatch.setattr(
        document_understanding,
        "_extract_text_pdf",
        lambda path: {
            "body": "The Complete Guide to Building Skills for Claude",
            "title": "The Complete Guide to Building Skills for Claude",
            "method": "pymupdf",
            "ocr_applied": False,
        },
    )
    monkeypatch.setattr(document_understanding, "_extract_via_document_extractor", lambda path: None)

    result = document_understanding.understand_document(pdf)

    assert result["title"] == "The Complete Guide to Building Skills for Claude"
    assert result["extraction_method"] == "pymupdf"
    assert result["document_kind"] == "pdf"
    assert result["body"].startswith("The Complete Guide")


def test_understand_document_returns_summary_and_key_insights_for_pdf(monkeypatch, tmp_path):
    pdf = tmp_path / "guide.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    from skills.rag.scripts import document_understanding

    monkeypatch.setattr(
        document_understanding,
        "_extract_text_pdf",
        lambda path: {
            "body": (
                "The Complete Guide to Building Skills for Claude\\n\\n"
                "A skill is a set of instructions packaged as a folder.\\n"
                "Skills are the knowledge layer on top of MCP.\\n"
                "Progressive disclosure minimizes token usage.\\n"
            ),
            "title": "The Complete Guide to Building Skills for Claude",
            "method": "pymupdf",
            "ocr_applied": False,
        },
    )

    result = document_understanding.understand_document(pdf)

    assert "knowledge layer on top of MCP" in result["summary"]
    assert any("Progressive disclosure" in item for item in result["key_insights"])
    assert result["understanding_version"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest skills/rag/augur/tests/test_document_understanding.py -q`

Expected: FAIL with `ModuleNotFoundError` because `document_understanding.py` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create `skills/rag/scripts/document_understanding.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any


UNDERSTANDING_VERSION = "v1"


def understand_document(path: Path) -> dict[str, Any]:
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        extracted = _extract_text_pdf(path) or _extract_via_document_extractor(path) or _empty_result(path)
    else:
        extracted = _extract_via_document_extractor(path) or _empty_result(path)

    body = str(extracted.get("body") or "").strip()
    title = str(extracted.get("title") or path.stem).strip()

    return {
        "body": body,
        "title": title,
        "format": suffix.lstrip(".") or "unknown",
        "document_kind": "pdf" if suffix == ".pdf" else "document",
        "extraction_method": str(extracted.get("method") or "unknown"),
        "ocr_applied": bool(extracted.get("ocr_applied")),
        "summary": _summarize(body=body, title=title),
        "key_insights": _key_insights(body),
        "section_hints": _section_hints(body),
        "visual_structure_used": False,
        "understanding_version": UNDERSTANDING_VERSION,
        "error": extracted.get("error"),
    }


def _extract_text_pdf(path: Path) -> dict[str, Any] | None:
    from skills.rag.scripts.ocr_extractor import extract_text

    result = extract_text(path)
    text = str(result.get("text") or "").strip()
    if not text:
        return None
    return {
        "body": text,
        "title": _infer_title(text, fallback=path.stem),
        "method": result.get("method", "unknown"),
        "ocr_applied": result.get("method") not in {"pymupdf", "plaintext"},
    }


def _extract_via_document_extractor(path: Path) -> dict[str, Any] | None:
    import sys
    from src.config.paths import get_skills_dir

    scripts_dir = get_skills_dir() / "document-extractor" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from extractor import extract  # type: ignore[import-not-found]

    result = extract(str(path), max_tier=1)
    if not result.success:
        return None
    return {
        "body": result.markdown,
        "title": result.title or path.stem,
        "method": f"document-extractor:{result.tier_used}",
        "ocr_applied": result.ocr_applied,
    }


def _empty_result(path: Path) -> dict[str, Any]:
    return {"body": "", "title": path.stem, "method": "failed", "ocr_applied": False, "error": "No extractor result"}


def _infer_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if len(line) >= 8:
            return line[:140]
    return fallback


def _summarize(*, body: str, title: str) -> str:
    sentences = [line.strip() for line in body.splitlines() if line.strip()]
    if not sentences:
        return f"{title} was imported, but no readable text was captured."
    summary = " ".join(sentences[:3])
    return summary[:320]


def _key_insights(body: str) -> list[str]:
    insights = []
    for line in body.splitlines():
        stripped = line.strip()
        if len(stripped) >= 30 and stripped not in insights:
            insights.append(stripped)
        if len(insights) == 5:
            break
    return insights


def _section_hints(body: str) -> list[str]:
    hints = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and stripped == stripped.title() and len(stripped.split()) <= 6:
            hints.append(stripped)
        if len(hints) == 8:
            break
    return hints
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest skills/rag/augur/tests/test_document_understanding.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/rag/scripts/document_understanding.py skills/rag/augur/tests/test_document_understanding.py
git commit -m "feat(rag): add canonical document understanding router"
```

---

### Task 2: Wire RAG Indexing To The Canonical Router And Persist Metadata

**Files:**
- Modify: `skills/rag/scripts/unified_indexer.py`
- Test: `skills/rag/augur/tests/test_unified_indexer.py`

- [ ] **Step 1: Write the failing test**

Append to `skills/rag/augur/tests/test_unified_indexer.py`:

```python
def test_index_documents_persists_structured_document_metadata(monkeypatch, tmp_path):
    documents_dir = tmp_path / "documents"
    rag_dir = tmp_path / "rag"
    pdf = documents_dir / "sources" / "guide.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4 fake")

    import skills.rag.scripts.unified_indexer as unified_indexer

    monkeypatch.setattr(
        unified_indexer,
        "_extract_document",
        lambda path: {
            "format": "pdf",
            "size_bytes": 123,
            "created": "2026-04-15T00:00:00+00:00",
            "body": "Skills are the knowledge layer on top of MCP.",
            "extraction_error": None,
            "document_title": "The Complete Guide to Building Skills for Claude",
            "document_kind": "pdf",
            "document_summary": "Skills are the knowledge layer on top of MCP.",
            "document_key_insights": [
                "Skills are the knowledge layer on top of MCP.",
                "Progressive disclosure minimizes token usage.",
            ],
            "document_sections": ["Introduction", "Fundamentals"],
            "document_extraction_method": "pymupdf",
            "document_visual_structure_used": False,
            "document_understanding_version": "v1",
        },
    )

    count = unified_indexer.index_documents(documents_dir, rag_dir)

    assert count == 1
    entry = rag_dir / "documents" / "sources" / "guide.md"
    text = entry.read_text(encoding="utf-8")
    assert "document_title: The Complete Guide to Building Skills for Claude" in text
    assert "document_kind: pdf" in text
    assert "document_extraction_method: pymupdf" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest skills/rag/augur/tests/test_unified_indexer.py -q`

Expected: FAIL because `index_documents()` does not yet write the structured document metadata fields.

- [ ] **Step 3: Write minimal implementation**

Modify `skills/rag/scripts/unified_indexer.py` inside `_extract_document()` and `index_documents()` so it delegates to the new router and writes the returned fields:

```python
def _extract_document(path: Path) -> dict[str, Any]:
    from skills.rag.scripts.document_understanding import understand_document

    if path.suffix.lower() in _DIRECT_TEXT_EXTENSIONS:
        body = _best_effort_document_body(path)
        return {
            "format": path.suffix.lstrip(".") or "txt",
            "size_bytes": path.stat().st_size,
            "created": _dt.now(_tz.utc).isoformat(),
            "body": body,
            "extraction_error": None,
            "document_title": path.stem,
            "document_kind": "document",
            "document_summary": body[:320],
            "document_key_insights": [],
            "document_sections": [],
            "document_extraction_method": "plaintext",
            "document_visual_structure_used": False,
            "document_understanding_version": "v1",
        }

    understanding = understand_document(path)
    return {
        "format": path.suffix.lstrip(".") or "bin",
        "size_bytes": path.stat().st_size,
        "created": _dt.now(_tz.utc).isoformat(),
        "body": understanding["body"],
        "extraction_error": understanding.get("error"),
        "document_title": understanding["title"],
        "document_kind": understanding["document_kind"],
        "document_summary": understanding["summary"],
        "document_key_insights": understanding["key_insights"],
        "document_sections": understanding["section_hints"],
        "document_extraction_method": understanding["extraction_method"],
        "document_visual_structure_used": understanding["visual_structure_used"],
        "document_understanding_version": understanding["understanding_version"],
    }
```

And when building `entry_meta`:

```python
entry_meta.update({
    "document_title": extraction["document_title"],
    "document_kind": extraction["document_kind"],
    "document_summary": extraction["document_summary"],
    "document_key_insights": extraction["document_key_insights"],
    "document_sections": extraction["document_sections"],
    "document_extraction_method": extraction["document_extraction_method"],
    "document_visual_structure_used": extraction["document_visual_structure_used"],
    "document_understanding_version": extraction["document_understanding_version"],
})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest skills/rag/augur/tests/test_document_understanding.py skills/rag/augur/tests/test_unified_indexer.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/rag/scripts/document_understanding.py skills/rag/scripts/unified_indexer.py skills/rag/augur/tests/test_document_understanding.py skills/rag/augur/tests/test_unified_indexer.py
git commit -m "feat(rag): persist structured document metadata in rag entries"
```

---

### Task 3: Use Structured Document Metadata In Wiki Compilation

**Files:**
- Modify: `skills/ingest/scripts/wiki_compiler.py`
- Modify: `skills/ingest/scripts/wiki_page_writer.py`
- Test: `skills/ingest/augur/tests/test_wiki_compiler.py`

- [ ] **Step 1: Write the failing test**

Append to `skills/ingest/augur/tests/test_wiki_compiler.py`:

```python
def test_compile_batch_prefers_structured_document_metadata_for_source_summary(tmp_path, monkeypatch):
    wiki_dir = tmp_path / "wiki"
    runtime_wiki_dir = tmp_path / "runtime"
    rag_dir = tmp_path / "rag"
    documents_dir = tmp_path / "documents"

    source = documents_dir / "sources" / "guide.pdf"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"%PDF-1.4 fake")

    entry = rag_dir / "documents" / "sources" / "guide.md"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(
        \"\"\"---
type: document
source_path: {source}
document_title: The Complete Guide to Building Skills for Claude
document_kind: pdf
document_summary: Skills are a reusable knowledge layer on top of MCP.
document_key_insights:
  - Progressive disclosure minimizes token usage.
  - Skills encode workflow knowledge once and reuse it.
document_sections:
  - Introduction
  - Fundamentals
wiki_compile_status: pending
checksum: abc
---

Raw body that should not be the only thing the writer sees.
\"\"\".format(source=source),
        encoding="utf-8",
    )

    from skills.ingest.scripts.wiki_compiler import compile_batch

    result = compile_batch(
        wiki_dir=wiki_dir,
        runtime_wiki_dir=runtime_wiki_dir,
        rag_dir=rag_dir,
        ask_outcomes=[],
        limit=2,
    )

    assert "sources/guide" in result["compiled_pages"]
    page = (wiki_dir / "sources" / "guide.md").read_text(encoding="utf-8")
    assert "Skills are a reusable knowledge layer on top of MCP." in page
    assert "Progressive disclosure minimizes token usage." in page
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest skills/ingest/augur/tests/test_wiki_compiler.py -q`

Expected: FAIL because the current writer only uses raw source bodies/excerpts.

- [ ] **Step 3: Write minimal implementation**

In `skills/ingest/scripts/wiki_compiler.py`, add a helper that loads document metadata from matching RAG entries:

```python
def _load_source_contexts(candidates: list[dict[str, Any]], rag_dir: Path) -> dict[str, dict[str, Any]]:
    contexts: dict[str, dict[str, Any]] = {}
    for entry in sorted(Path(rag_dir).rglob("*.md")):
        meta, body = parse_frontmatter(entry)
        source_path = str(meta.get("source_path") or "").strip()
        if not source_path:
            continue
        contexts[source_path] = {
            "body": body,
            "document_title": meta.get("document_title"),
            "document_summary": meta.get("document_summary"),
            "document_key_insights": meta.get("document_key_insights", []),
            "document_sections": meta.get("document_sections", []),
        }
    return contexts
```

Pass that context into page rendering, and in `skills/ingest/scripts/wiki_page_writer.py` prefer structured metadata:

```python
def _render_source_summary(candidate, *, source_contexts):
    source_path = str(candidate["source_paths"][0])
    context = source_contexts.get(source_path, {})
    summary = str(context.get("document_summary") or "").strip()
    insights = [str(item).strip() for item in context.get("document_key_insights", []) if str(item).strip()]

    lines = [
        f"# {build_page_title(candidate)} Source Summary",
        "",
        "## Summary",
        "",
        summary or f"This page captures the currently compiled value of `{source_path}`.",
        "",
        "## Key Insights",
        "",
    ]
    if insights:
        lines.extend(f"- {item}" for item in insights)
    else:
        lines.append("- No structured document insights captured yet.")
    lines.extend(["", "## Source Basis", "", f"- `{source_path}`"])
    return "\\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest skills/ingest/augur/tests/test_wiki_compiler.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/wiki_compiler.py skills/ingest/scripts/wiki_page_writer.py skills/ingest/augur/tests/test_wiki_compiler.py
git commit -m "feat(ingest): write wiki pages from structured document metadata"
```

---

### Task 4: Align Installers And Onboarding With The Baseline Document Contract

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `skills/document-extractor/scripts/mcp/tools_extract.py`
- Modify: `skills/document-extractor/augur/tests/test_tools_extract.py`
- Modify: `scripts/install.sh`
- Modify: `scripts/install.ps1`
- Modify: `docs/guides/installation-windows.md`
- Modify: `~/.agents/skills/augur/onboard/references/mode-default.md`
- Modify: `~/.agents/skills/augur/onboard/references/mode-full.md`
- Create: `tests/unit/test_install_document_contract.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_install_document_contract.py`:

```python
from pathlib import Path


def test_pyproject_makes_pymupdf_a_baseline_dependency():
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert '\"pymupdf>=1.24.0\",' in text
    assert 'ocr = [' in text


def test_windows_installer_uses_uv_sync_not_missing_requirements_file():
    text = Path("scripts/install.ps1").read_text(encoding="utf-8")
    assert "uv sync" in text
    assert "requirements.txt" not in text


def test_onboarding_mentions_document_capability_verification():
    text = Path("~/.agents/skills/augur/onboard/references/mode-default.md").read_text(encoding="utf-8")
    assert "get-extraction-status" in text
    assert "text PDF extraction" in text
```

Append to `skills/document-extractor/augur/tests/test_tools_extract.py`:

```python
def test_get_extraction_status_reports_pymupdf_and_baseline_contract():
    from scripts.mcp.tools_extract import get_extraction_status_impl

    result = get_extraction_status_impl()

    assert "baseline_document_contract" in result
    assert "pymupdf" in result["baseline_document_contract"]
    assert "text_pdf" in result["formats"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_install_document_contract.py skills/document-extractor/augur/tests/test_tools_extract.py -q`

Expected: FAIL because `pymupdf` is optional, the Windows installer still references `requirements.txt`, and onboarding docs do not yet verify document capability.

- [ ] **Step 3: Write minimal implementation**

Update `pyproject.toml` so baseline dependencies include `pymupdf`:

```toml
dependencies = [
    "pyyaml>=6.0",
    "mcp>=1.22.0",
    ...
    "markitdown[all]>=0.1.0",
    "markitdown-ocr>=0.1.0",
    "pymupdf>=1.24.0",
    ...
]

[project.optional-dependencies]
ocr = [
    "mlx-vlm>=0.1.0",
]
```

In `skills/document-extractor/scripts/mcp/tools_extract.py`, extend the status payload:

```python
try:
    import fitz  # noqa: F401
    pymupdf_available = True
except ImportError:
    pymupdf_available = False

return {
    "formats": formats,
    "llm_integrations": llm_integrations,
    "tier_available": tier,
    "markitdown_version": md_version,
    "platform": platform.system(),
    "baseline_document_contract": {
        "markitdown": md_version is not None,
        "pymupdf": pymupdf_available,
        "text_pdf_extraction": pymupdf_available or formats["pdf_text"],
        "ocr_enhancement": tesseract_installed,
    },
}
```

In `scripts/install.sh`, add a post-`uv sync` capability check:

```bash
print_step "Verifying document extraction baseline..."
uv run python - <<'PY'
import sys
sys.path.insert(0, "skills/document-extractor/scripts")
sys.path.insert(0, "skills/document-extractor/scripts/mcp")
from tools_extract import get_extraction_status_impl
status = get_extraction_status_impl()
contract = status["baseline_document_contract"]
print(contract)
if not contract["markitdown"] or not contract["text_pdf_extraction"]:
    raise SystemExit("Document extraction baseline is incomplete")
PY
```

In `scripts/install.ps1`, replace the `requirements.txt` path with `uv sync` from the repo root and add the same baseline verification via Python.

Update onboarding docs so Step 6 verification includes:

```markdown
### Step 6b: Verify document capability

```bash
python - <<'PY'
import sys
sys.path.insert(0, "skills/document-extractor/scripts")
sys.path.insert(0, "skills/document-extractor/scripts/mcp")
from tools_extract import get_extraction_status_impl
print(get_extraction_status_impl())
PY
```

Confirm at least:
- `text PDF extraction`
- `document parsing`
- `OCR enhancement` (may be optional/unavailable)
```

- [ ] **Step 4: Refresh lockfile and run tests**

Run:

```bash
uv lock
pytest tests/unit/test_install_document_contract.py skills/document-extractor/augur/tests/test_tools_extract.py skills/rag/augur/tests/test_document_understanding.py skills/rag/augur/tests/test_unified_indexer.py skills/ingest/augur/tests/test_wiki_compiler.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock skills/document-extractor/scripts/mcp/tools_extract.py skills/document-extractor/augur/tests/test_tools_extract.py scripts/install.sh scripts/install.ps1 docs/guides/installation-windows.md ~/.agents/skills/augur/onboard/references/mode-default.md ~/.agents/skills/augur/onboard/references/mode-full.md tests/unit/test_install_document_contract.py
git commit -m "feat(onboard): guarantee baseline document extraction contract"
```

---

## Self-Review

- The spec requirements are covered:
  - canonical extraction path: Task 1 + Task 2
  - structured RAG metadata: Task 2
  - wiki writing from document understanding: Task 3
  - install/onboarding guarantees: Task 4
- No placeholders remain; all tasks name concrete files, tests, commands, and code.
- The type and field names are consistent across the tasks:
  - `document_title`
  - `document_kind`
  - `document_summary`
  - `document_key_insights`
  - `document_sections`
  - `document_extraction_method`
  - `document_visual_structure_used`
  - `document_understanding_version`
