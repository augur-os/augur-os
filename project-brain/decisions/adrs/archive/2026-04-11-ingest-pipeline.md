# Ingest Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a unified content ingest pipeline that accepts any content type (files, URLs, text, folders), processes it through extraction, classification, renaming, and routing, then indexes it in RAG.

**Architecture:** New `skills/ingest/` skill with Python backend (detector, renamer, job queue, pipeline orchestrator, MCP tools), CLI `/ingest` command, and dashboard UI (full-page drop zone + FAB + input modal). All execution happens inside AI client sessions per `docs/references/ai-client-execution-model.md` — MCP tools are stateless atomic operations, the agent orchestrates.

**Tech Stack:** Python 3.11+ (backend), TypeScript/React (dashboard), FastMCP (MCP tools), MarkItDown + opendataloader-pdf (extraction), YAML (job records/config)

**Spec:** `docs/superpowers/specs/2026-04-11-ingest-pipeline-design.md`

---

## File Structure

### Create

| File | Responsibility |
|------|---------------|
| `skills/ingest/SKILL.md` | Skill metadata, MCP tool list, hub config |
| `skills/ingest/commands/ingest.md` | `/ingest` CLI command definition |
| `skills/ingest/scripts/__init__.py` | Package init |
| `skills/ingest/scripts/detector.py` | Content type detection by extension, URL pattern, magic bytes |
| `skills/ingest/scripts/renamer.py` | Filename normalization to `YYYY-MM-DD-slug.ext` |
| `skills/ingest/scripts/job_queue.py` | Filesystem-based job record CRUD |
| `skills/ingest/scripts/pipeline.py` | Pipeline orchestrator: stage, detect, extract, rename, route, index |
| `skills/ingest/scripts/mcp/__init__.py` | MCP registration entry point |
| `skills/ingest/scripts/mcp/ingest_tools.py` | MCP tool definitions (ingest-process, ingest-extract, etc.) |
| `skills/ingest/augur/data/config-defaults.yaml` | Default ingest configuration |
| `skills/ingest/assets/seeds/classification-rules.yaml` | Heuristic classification keyword rules |
| `skills/ingest/augur/tests/test_detector.py` | Detector unit tests |
| `skills/ingest/augur/tests/test_renamer.py` | Renamer unit tests |
| `skills/ingest/augur/tests/test_job_queue.py` | Job queue unit tests |
| `skills/ingest/augur/tests/test_pipeline.py` | Pipeline integration tests |
| `skills/ingest/augur/dashboard/IngestDropZone.tsx` | Full-page drag overlay + drop handler |
| `skills/ingest/augur/dashboard/IngestFAB.tsx` | Floating action button + queue panel |
| `skills/ingest/augur/dashboard/IngestModal.tsx` | URL/text/file/folder input tabs |
| `skills/ingest/augur/dashboard/IngestQueueItem.tsx` | Single item in processing queue |
| `apps/dashboard/app/api/ingest/upload/route.ts` | File upload API endpoint |

### Modify

| File | Change |
|------|--------|
| None initially — skill auto-discovery handles registration |

---

## Task 1: Skill Scaffold

**Files:**
- Create: `skills/ingest/SKILL.md`
- Create: `skills/ingest/scripts/__init__.py`
- Create: `skills/ingest/augur/data/config-defaults.yaml`
- Create: `skills/ingest/assets/seeds/classification-rules.yaml`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p skills/ingest/{commands,scripts/mcp,augur/{dashboard,data,tests},assets/seeds}
```

- [ ] **Step 2: Write SKILL.md**

Create `skills/ingest/SKILL.md`:

```markdown
---
name: ingest
x-augur-type: domain
x-augur-category: augur-internal
x-augur-tags: [ingest, pipeline, extraction, classification, indexing]
description: Unified content ingest pipeline — accepts files, URLs, text, folders, skills and processes through extraction, classification, renaming, routing, and RAG indexing.
x-augur-hub: brain
x-augur-tab: knowledge
x-augur-license: MIT
x-augur-metadata:
  version: 0.1.0
  author: Augur
  mcp-server: augur
x-augur-mcp-tools:
- ingest-process
- ingest-extract
- ingest-rename
- ingest-route
- ingest-status
- ingest-history
- ingest-config
x-augur-dashboard-pages: []
x-augur-data-dir: ingest
x-augur-config:
  contributions:
    actions:
    - id: ingest-content
      label: Ingest Content
      dispatch: ide
      prompt: "Process the dropped content through the ingest pipeline"
---
# Ingest Skill

Unified content ingest pipeline for Augur's knowledge base. Accepts any content type, extracts text, classifies destination, normalizes filenames, routes to vault, and indexes in RAG.

## Architecture

All execution happens inside AI client sessions. MCP tools are stateless atomic operations. The agent orchestrates the pipeline — classification and summarization happen at the agent level using LLM capability.

See: `docs/references/ai-client-execution-model.md`

## MCP Tools

| Tool | Type | Purpose |
|------|------|---------|
| `ingest-process` | mutation | Process batch of items through extract/rename/route/index |
| `ingest-extract` | mutation | Extract single file to markdown |
| `ingest-rename` | mutation | Normalize a filename |
| `ingest-route` | mutation | Move file to destination and index |
| `ingest-status` | read | Get job queue state |
| `ingest-history` | read | Recent ingest history |
| `ingest-config` | read/write | Get/set ingest configuration |

## CLI

`/ingest <files|urls|text> [--to destination] [--text]`
```

- [ ] **Step 3: Write config defaults**

Create `skills/ingest/augur/data/config-defaults.yaml`:

```yaml
ingest:
  classification:
    method: "heuristic"
    model: "gemma2:2b"
    fallback: "heuristic"
  extraction:
    pdf: "opendataloader-pdf"
    ocr: "tesseract"
  naming:
    pattern: "{date}-{slug}"
    date_format: "%Y-%m-%d"
  summarize:
    enabled: true
    max_length: 2000
  tracked_folders: []
  auto_index: true
```

- [ ] **Step 4: Write classification rules seed**

Create `skills/ingest/assets/seeds/classification-rules.yaml`:

```yaml
# Heuristic classification rules: keyword patterns → vault destination
# The agent handles ambiguous cases; these cover obvious matches.
rules:
  - keywords: [recipe, cooking, ingredient, meal, food, diet, nutrition]
    destination: lifestyle/recipes
  - keywords: [invoice, receipt, tax, payment, budget, expense, salary, bank]
    destination: finance/documents
  - keywords: [resume, cv, job, career, interview, application, offer, hiring]
    destination: career/documents
  - keywords: [symptom, medication, doctor, diagnosis, health, medical, prescription]
    destination: health/records
  - keywords: [travel, flight, hotel, itinerary, booking, trip, vacation]
    destination: lifestyle/travel
  - keywords: [meeting, agenda, standup, sprint, retro, project, deadline]
    destination: notes/work
  - keywords: [paper, research, abstract, methodology, findings, arxiv, doi]
    destination: notes/research
  - keywords: [readme, api, endpoint, deployment, docker, kubernetes, config]
    destination: notes/technical
```

- [ ] **Step 5: Write package init**

Create `skills/ingest/scripts/__init__.py`:

```python
"""Ingest pipeline skill — unified content ingestion for Augur."""
```

- [ ] **Step 6: Commit**

```bash
git add skills/ingest/
git commit -m "feat(ingest): scaffold skill structure with SKILL.md, config, and classification rules"
```

---

## Task 2: Content Type Detector

**Files:**
- Create: `skills/ingest/scripts/detector.py`
- Test: `skills/ingest/augur/tests/test_detector.py`

- [ ] **Step 1: Write the failing test**

Create `skills/ingest/augur/tests/test_detector.py`:

```python
"""Tests for content type detection."""
from pathlib import Path

from scripts.detector import detect_content_type, ContentType


def test_detect_pdf():
    assert detect_content_type("/tmp/report.pdf") == ContentType.PDF


def test_detect_docx():
    assert detect_content_type("/tmp/file.docx") == ContentType.DOCUMENT


def test_detect_pptx():
    assert detect_content_type("/tmp/slides.pptx") == ContentType.DOCUMENT


def test_detect_image_jpg():
    assert detect_content_type("/tmp/photo.jpg") == ContentType.IMAGE


def test_detect_image_png():
    assert detect_content_type("/tmp/screenshot.PNG") == ContentType.IMAGE


def test_detect_markdown():
    assert detect_content_type("/tmp/notes.md") == ContentType.MARKDOWN


def test_detect_url():
    assert detect_content_type("https://example.com/article") == ContentType.URL


def test_detect_youtube():
    assert detect_content_type("https://youtube.com/watch?v=abc123") == ContentType.YOUTUBE


def test_detect_youtube_short():
    assert detect_content_type("https://youtu.be/abc123") == ContentType.YOUTUBE


def test_detect_github():
    assert detect_content_type("https://github.com/user/repo") == ContentType.GITHUB


def test_detect_text():
    assert detect_content_type("This is raw text content") == ContentType.TEXT


def test_detect_folder(tmp_path):
    folder = tmp_path / "mydir"
    folder.mkdir()
    assert detect_content_type(str(folder)) == ContentType.FOLDER


def test_detect_skill(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: test\n---\n")
    assert detect_content_type(str(skill_dir)) == ContentType.SKILL


def test_detect_notion_zip(tmp_path):
    # A .zip file is treated as NOTION if it looks like a Notion export
    zip_file = tmp_path / "export.zip"
    zip_file.write_bytes(b"PK\x03\x04")  # ZIP magic bytes
    assert detect_content_type(str(zip_file)) == ContentType.ARCHIVE


def test_detect_unknown_extension():
    assert detect_content_type("/tmp/file.xyz") == ContentType.UNKNOWN
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/ingest && python -m pytest augur/tests/test_detector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.detector'`

- [ ] **Step 3: Write detector implementation**

Create `skills/ingest/scripts/detector.py`:

```python
"""Content type detection by extension, URL pattern, and filesystem inspection."""
from __future__ import annotations

import re
from enum import Enum
from pathlib import Path


class ContentType(Enum):
    PDF = "pdf"
    DOCUMENT = "document"      # docx, pptx, xlsx
    IMAGE = "image"
    MARKDOWN = "markdown"
    URL = "url"
    YOUTUBE = "youtube"
    GITHUB = "github"
    NOTION = "notion"
    ARCHIVE = "archive"        # zip files
    FOLDER = "folder"
    SKILL = "skill"
    TEXT = "text"
    UNKNOWN = "unknown"


EXTENSION_MAP: dict[str, ContentType] = {
    ".pdf": ContentType.PDF,
    ".docx": ContentType.DOCUMENT,
    ".doc": ContentType.DOCUMENT,
    ".pptx": ContentType.DOCUMENT,
    ".ppt": ContentType.DOCUMENT,
    ".xlsx": ContentType.DOCUMENT,
    ".xls": ContentType.DOCUMENT,
    ".csv": ContentType.DOCUMENT,
    ".md": ContentType.MARKDOWN,
    ".markdown": ContentType.MARKDOWN,
    ".png": ContentType.IMAGE,
    ".jpg": ContentType.IMAGE,
    ".jpeg": ContentType.IMAGE,
    ".gif": ContentType.IMAGE,
    ".bmp": ContentType.IMAGE,
    ".tiff": ContentType.IMAGE,
    ".webp": ContentType.IMAGE,
    ".heic": ContentType.IMAGE,
    ".heif": ContentType.IMAGE,
    ".svg": ContentType.IMAGE,
    ".zip": ContentType.ARCHIVE,
}

_URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)
_YOUTUBE_PATTERN = re.compile(
    r"^https?://(www\.)?(youtube\.com|youtu\.be)/", re.IGNORECASE
)
_GITHUB_PATTERN = re.compile(
    r"^https?://(www\.)?github\.com/[^/]+/[^/]+", re.IGNORECASE
)


def detect_content_type(source: str) -> ContentType:
    """Detect the content type of a source string.

    Args:
        source: A filesystem path, URL, or raw text.

    Returns:
        ContentType enum value.
    """
    # URL detection first (before filesystem checks)
    if _YOUTUBE_PATTERN.match(source):
        return ContentType.YOUTUBE
    if _GITHUB_PATTERN.match(source):
        return ContentType.GITHUB
    if _URL_PATTERN.match(source):
        return ContentType.URL

    # Filesystem path checks
    path = Path(source)

    if path.is_dir():
        # Check if it's a skill package
        if (path / "SKILL.md").exists():
            return ContentType.SKILL
        return ContentType.FOLDER

    # Extension-based detection (case-insensitive)
    ext = path.suffix.lower()
    if ext in EXTENSION_MAP:
        return EXTENSION_MAP[ext]

    # If it looks like a path but has no recognized extension
    if path.suffix or "/" in source or "\\" in source:
        return ContentType.UNKNOWN

    # Default: raw text
    return ContentType.TEXT
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd skills/ingest && PYTHONPATH=. python -m pytest augur/tests/test_detector.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/detector.py skills/ingest/augur/tests/test_detector.py
git commit -m "feat(ingest): content type detector with extension, URL, and filesystem detection"
```

---

## Task 3: File Renamer

**Files:**
- Create: `skills/ingest/scripts/renamer.py`
- Test: `skills/ingest/augur/tests/test_renamer.py`

- [ ] **Step 1: Write the failing test**

Create `skills/ingest/augur/tests/test_renamer.py`:

```python
"""Tests for filename normalization."""
from datetime import date

from scripts.renamer import normalize_filename


def test_basic_rename():
    result = normalize_filename("Invoice_2024.PDF", title="Invoice 2024")
    assert result == f"{date.today().isoformat()}-invoice-2024.pdf"


def test_special_characters():
    result = normalize_filename("résumé final v3 (2).docx", title="Resume Final")
    assert result == f"{date.today().isoformat()}-resume-final.docx"


def test_image_keeps_extension():
    result = normalize_filename("IMG_20240101_123456.jpg", title="Photo January")
    assert result == f"{date.today().isoformat()}-photo-january.jpg"


def test_url_becomes_markdown():
    result = normalize_filename(None, title="Machine Learning Transformers", ext=".md")
    assert result == f"{date.today().isoformat()}-machine-learning-transformers.md"


def test_text_becomes_markdown():
    result = normalize_filename(None, title="Meeting Notes Q3 Roadmap", ext=".md")
    assert result == f"{date.today().isoformat()}-meeting-notes-q3-roadmap.md"


def test_slug_strips_non_alphanumeric():
    result = normalize_filename("file!!!@#$.pdf", title="Test & Report #1")
    assert result == f"{date.today().isoformat()}-test-report-1.pdf"


def test_slug_collapses_hyphens():
    result = normalize_filename("a---b---c.pdf", title="A - B - C")
    assert result == f"{date.today().isoformat()}-a-b-c.pdf"


def test_slug_strips_leading_trailing_hyphens():
    result = normalize_filename("--test--.pdf", title="--Test--")
    assert result == f"{date.today().isoformat()}-test.pdf"


def test_custom_date():
    result = normalize_filename(
        "file.pdf", title="Test", ingest_date=date(2026, 1, 15)
    )
    assert result == "2026-01-15-test.pdf"


def test_collision_suffix():
    result = normalize_filename("file.pdf", title="Test", collision_index=2)
    assert result == f"{date.today().isoformat()}-test-2.pdf"


def test_fallback_to_filename_when_no_title():
    result = normalize_filename("My Document (copy).pdf")
    assert result == f"{date.today().isoformat()}-my-document-copy.pdf"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/ingest && PYTHONPATH=. python -m pytest augur/tests/test_renamer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write renamer implementation**

Create `skills/ingest/scripts/renamer.py`:

```python
"""Filename normalization to YYYY-MM-DD-slug.ext pattern."""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path


def _slugify(text: str) -> str:
    """Convert text to a URL-safe slug: lowercase, hyphens, no special chars."""
    # Normalize unicode (e.g., résumé → resume)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    # Lowercase
    text = text.lower()
    # Replace non-alphanumeric with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Collapse multiple hyphens
    text = re.sub(r"-+", "-", text)
    # Strip leading/trailing hyphens
    text = text.strip("-")
    return text


def normalize_filename(
    original: str | None,
    *,
    title: str | None = None,
    ext: str | None = None,
    ingest_date: date | None = None,
    collision_index: int = 0,
) -> str:
    """Normalize a filename to the YYYY-MM-DD-slug.ext pattern.

    Args:
        original: Original filename (can be None for URLs/text).
        title: Extracted content title. Falls back to original filename stem.
        ext: Override extension (e.g., '.md' for URLs/text).
        ingest_date: Date to use. Defaults to today.
        collision_index: Append -N suffix for collisions (0 = no suffix).

    Returns:
        Normalized filename string.
    """
    d = ingest_date or date.today()
    date_str = d.isoformat()

    # Determine slug from title or filename
    if title:
        slug = _slugify(title)
    elif original:
        stem = Path(original).stem
        slug = _slugify(stem)
    else:
        slug = "untitled"

    # Determine extension
    if ext:
        extension = ext if ext.startswith(".") else f".{ext}"
    elif original:
        extension = Path(original).suffix.lower()
    else:
        extension = ".md"

    # Build filename
    suffix = f"-{collision_index}" if collision_index > 0 else ""
    return f"{date_str}-{slug}{suffix}{extension}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd skills/ingest && PYTHONPATH=. python -m pytest augur/tests/test_renamer.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/renamer.py skills/ingest/augur/tests/test_renamer.py
git commit -m "feat(ingest): filename normalizer with slugification and collision handling"
```

---

## Task 4: Job Queue

**Files:**
- Create: `skills/ingest/scripts/job_queue.py`
- Test: `skills/ingest/augur/tests/test_job_queue.py`

- [ ] **Step 1: Write the failing test**

Create `skills/ingest/augur/tests/test_job_queue.py`:

```python
"""Tests for filesystem-based job queue."""
from pathlib import Path

from scripts.job_queue import JobQueue, JobStatus


def test_create_job(tmp_path):
    q = JobQueue(tmp_path)
    job = q.create("pdf", "/tmp/invoice.pdf", "Invoice_2024.PDF")
    assert job["status"] == JobStatus.PENDING.value
    assert job["type"] == "pdf"
    assert job["original_name"] == "Invoice_2024.PDF"
    assert (tmp_path / "jobs" / f"{job['id']}.yaml").exists()


def test_get_job(tmp_path):
    q = JobQueue(tmp_path)
    created = q.create("url", "https://example.com", "example.com")
    fetched = q.get(created["id"])
    assert fetched["id"] == created["id"]
    assert fetched["type"] == "url"


def test_update_status(tmp_path):
    q = JobQueue(tmp_path)
    job = q.create("pdf", "/tmp/file.pdf", "file.pdf")
    q.update(job["id"], status=JobStatus.PROCESSING, stage="extract")
    updated = q.get(job["id"])
    assert updated["status"] == "processing"
    assert updated["stage"] == "extract"


def test_complete_job(tmp_path):
    q = JobQueue(tmp_path)
    job = q.create("pdf", "/tmp/file.pdf", "file.pdf")
    q.complete(job["id"], destination="/vault/notes/file.md", renamed_to="2026-04-11-file.pdf")
    done = q.get(job["id"])
    assert done["status"] == "completed"
    assert done["classified_to"] == "/vault/notes/file.md"
    assert done["completed_at"] is not None


def test_fail_job(tmp_path):
    q = JobQueue(tmp_path)
    job = q.create("pdf", "/tmp/bad.pdf", "bad.pdf")
    q.fail(job["id"], error="Extraction failed: corrupt PDF")
    failed = q.get(job["id"])
    assert failed["status"] == "failed"
    assert "corrupt PDF" in failed["error"]


def test_list_jobs(tmp_path):
    q = JobQueue(tmp_path)
    q.create("pdf", "/tmp/a.pdf", "a.pdf")
    q.create("url", "https://b.com", "b.com")
    q.create("text", "hello", "text-input")
    jobs = q.list_jobs()
    assert len(jobs) == 3


def test_list_jobs_by_status(tmp_path):
    q = JobQueue(tmp_path)
    j1 = q.create("pdf", "/tmp/a.pdf", "a.pdf")
    q.create("url", "https://b.com", "b.com")
    q.update(j1["id"], status=JobStatus.PROCESSING)
    pending = q.list_jobs(status=JobStatus.PENDING)
    assert len(pending) == 1


def test_get_nonexistent_job(tmp_path):
    q = JobQueue(tmp_path)
    assert q.get("nonexistent") is None


def test_staging_dir(tmp_path):
    q = JobQueue(tmp_path)
    job = q.create("pdf", "/tmp/file.pdf", "file.pdf")
    staging = q.staging_dir(job["id"])
    assert staging == tmp_path / "staging" / job["id"]
    assert staging.is_dir()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/ingest && PYTHONPATH=. python -m pytest augur/tests/test_job_queue.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write job queue implementation**

Create `skills/ingest/scripts/job_queue.py`:

```python
"""Filesystem-based job queue for ingest pipeline."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobQueue:
    """Manages ingest job records as YAML files on disk."""

    def __init__(self, base_dir: Path) -> None:
        self._base = Path(base_dir)
        self._jobs_dir = self._base / "jobs"
        self._staging_dir = self._base / "staging"
        self._jobs_dir.mkdir(parents=True, exist_ok=True)
        self._staging_dir.mkdir(parents=True, exist_ok=True)

    def create(
        self, content_type: str, source: str, original_name: str
    ) -> dict[str, Any]:
        """Create a new pending job and return its record."""
        job_id = uuid.uuid4().hex[:8]
        now = datetime.now(tz=timezone.utc).isoformat()
        record: dict[str, Any] = {
            "id": job_id,
            "status": JobStatus.PENDING.value,
            "type": content_type,
            "source": source,
            "original_name": original_name,
            "stage": None,
            "classified_to": None,
            "renamed_to": None,
            "summary_path": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }
        self._write(job_id, record)
        # Ensure staging directory exists for this job
        (self._staging_dir / job_id).mkdir(parents=True, exist_ok=True)
        return record

    def get(self, job_id: str) -> dict[str, Any] | None:
        """Read a job record by ID. Returns None if not found."""
        path = self._jobs_dir / f"{job_id}.yaml"
        if not path.exists():
            return None
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def update(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        stage: str | None = None,
        classified_to: str | None = None,
        renamed_to: str | None = None,
        summary_path: str | None = None,
    ) -> dict[str, Any] | None:
        """Update specific fields on a job record."""
        record = self.get(job_id)
        if record is None:
            return None
        if status is not None:
            record["status"] = status.value
        if stage is not None:
            record["stage"] = stage
        if classified_to is not None:
            record["classified_to"] = classified_to
        if renamed_to is not None:
            record["renamed_to"] = renamed_to
        if summary_path is not None:
            record["summary_path"] = summary_path
        record["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        self._write(job_id, record)
        return record

    def complete(
        self, job_id: str, *, destination: str, renamed_to: str
    ) -> dict[str, Any] | None:
        """Mark a job as completed."""
        record = self.get(job_id)
        if record is None:
            return None
        record["status"] = JobStatus.COMPLETED.value
        record["classified_to"] = destination
        record["renamed_to"] = renamed_to
        record["completed_at"] = datetime.now(tz=timezone.utc).isoformat()
        record["updated_at"] = record["completed_at"]
        self._write(job_id, record)
        return record

    def fail(self, job_id: str, *, error: str) -> dict[str, Any] | None:
        """Mark a job as failed with an error message."""
        record = self.get(job_id)
        if record is None:
            return None
        record["status"] = JobStatus.FAILED.value
        record["error"] = error
        record["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        self._write(job_id, record)
        return record

    def list_jobs(
        self, *, status: JobStatus | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """List job records, optionally filtered by status."""
        jobs = []
        for path in sorted(self._jobs_dir.glob("*.yaml"), reverse=True):
            record = yaml.safe_load(path.read_text(encoding="utf-8"))
            if status is not None and record.get("status") != status.value:
                continue
            jobs.append(record)
            if len(jobs) >= limit:
                break
        return jobs

    def staging_dir(self, job_id: str) -> Path:
        """Return the staging directory for a job, creating it if needed."""
        d = self._staging_dir / job_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def cleanup_staging(self, job_id: str) -> None:
        """Remove staging directory for a completed job."""
        d = self._staging_dir / job_id
        if d.exists():
            import shutil
            shutil.rmtree(d)

    def _write(self, job_id: str, record: dict[str, Any]) -> None:
        path = self._jobs_dir / f"{job_id}.yaml"
        path.write_text(
            yaml.dump(record, allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd skills/ingest && PYTHONPATH=. python -m pytest augur/tests/test_job_queue.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/job_queue.py skills/ingest/augur/tests/test_job_queue.py
git commit -m "feat(ingest): filesystem-based job queue with YAML records"
```

---

## Task 5: Pipeline Orchestrator

**Files:**
- Create: `skills/ingest/scripts/pipeline.py`
- Test: `skills/ingest/augur/tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

Create `skills/ingest/augur/tests/test_pipeline.py`:

```python
"""Tests for the ingest pipeline orchestrator."""
import shutil
from pathlib import Path

from scripts.pipeline import IngestPipeline, IngestResult
from scripts.detector import ContentType


def test_process_markdown_file(tmp_path):
    """Markdown files go through detect → rename → route → index."""
    ingest_dir = tmp_path / "ingest"
    vault_dir = tmp_path / "vault"
    rag_dir = tmp_path / "rag"
    vault_dir.mkdir()

    # Create a markdown file to ingest
    src = tmp_path / "notes.md"
    src.write_text("# Meeting Notes\n\nDiscussed Q3 roadmap.")

    pipeline = IngestPipeline(
        ingest_dir=ingest_dir,
        vault_dir=vault_dir,
        rag_dir=rag_dir,
    )
    result = pipeline.process_item(str(src), destination="notes/work")

    assert result.success is True
    assert result.content_type == ContentType.MARKDOWN
    assert result.renamed_to is not None
    assert "meeting-notes" in result.renamed_to
    assert (vault_dir / "notes" / "work" / result.renamed_to).exists()


def test_process_detects_type(tmp_path):
    """Pipeline correctly detects content type."""
    ingest_dir = tmp_path / "ingest"
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    src = tmp_path / "photo.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\n")  # PNG magic bytes

    pipeline = IngestPipeline(
        ingest_dir=ingest_dir,
        vault_dir=vault_dir,
        rag_dir=tmp_path / "rag",
    )
    result = pipeline.process_item(str(src), destination="notes/images")
    assert result.content_type == ContentType.IMAGE


def test_process_renames_file(tmp_path):
    """Pipeline normalizes filename."""
    ingest_dir = tmp_path / "ingest"
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    src = tmp_path / "Invoice_2024 (copy).PDF"
    src.write_text("fake pdf content")

    pipeline = IngestPipeline(
        ingest_dir=ingest_dir,
        vault_dir=vault_dir,
        rag_dir=tmp_path / "rag",
    )
    result = pipeline.process_item(
        str(src), destination="finance/documents", title="Invoice 2024"
    )
    assert result.success is True
    assert "invoice-2024" in result.renamed_to
    assert result.renamed_to.endswith(".pdf")


def test_process_creates_job_record(tmp_path):
    """Pipeline creates and updates job records."""
    ingest_dir = tmp_path / "ingest"
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    src = tmp_path / "test.md"
    src.write_text("# Test\n\nContent here.")

    pipeline = IngestPipeline(
        ingest_dir=ingest_dir,
        vault_dir=vault_dir,
        rag_dir=tmp_path / "rag",
    )
    result = pipeline.process_item(str(src), destination="notes")
    assert result.job_id is not None

    job = pipeline.queue.get(result.job_id)
    assert job["status"] == "completed"


def test_process_batch(tmp_path):
    """Pipeline handles multiple items."""
    ingest_dir = tmp_path / "ingest"
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    files = []
    for i in range(3):
        f = tmp_path / f"file{i}.md"
        f.write_text(f"# File {i}\n\nContent {i}.")
        files.append(str(f))

    pipeline = IngestPipeline(
        ingest_dir=ingest_dir,
        vault_dir=vault_dir,
        rag_dir=tmp_path / "rag",
    )
    results = pipeline.process_batch(
        [{"source": f, "destination": "notes"} for f in files]
    )
    assert len(results) == 3
    assert all(r.success for r in results)


def test_process_item_failure(tmp_path):
    """Pipeline handles missing source gracefully."""
    ingest_dir = tmp_path / "ingest"
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    pipeline = IngestPipeline(
        ingest_dir=ingest_dir,
        vault_dir=vault_dir,
        rag_dir=tmp_path / "rag",
    )
    result = pipeline.process_item("/nonexistent/file.pdf", destination="notes")
    assert result.success is False
    assert result.error is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/ingest && PYTHONPATH=. python -m pytest augur/tests/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write pipeline implementation**

Create `skills/ingest/scripts/pipeline.py`:

```python
"""Ingest pipeline orchestrator.

Coordinates: detect → extract → rename → route → index.
Classification and summarization are handled by the agent (LLM),
not by this pipeline. The agent calls process_item with a destination.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .detector import ContentType, detect_content_type
from .job_queue import JobQueue, JobStatus
from .renamer import normalize_filename


@dataclass
class IngestResult:
    """Result of processing a single item through the pipeline."""
    success: bool
    job_id: str | None = None
    content_type: ContentType = ContentType.UNKNOWN
    source: str = ""
    destination: str = ""
    renamed_to: str = ""
    extracted_markdown: str = ""
    error: str | None = None


class IngestPipeline:
    """Orchestrates the ingest pipeline for a single item or batch.

    The pipeline handles mechanical work: detect type, extract content,
    rename files, route to destination, and index in RAG.

    Classification and summarization are NOT done here — those are
    agent-level responsibilities that happen before calling process_item.
    """

    def __init__(
        self,
        *,
        ingest_dir: Path,
        vault_dir: Path,
        rag_dir: Path,
    ) -> None:
        self._ingest_dir = Path(ingest_dir)
        self._vault_dir = Path(vault_dir)
        self._rag_dir = Path(rag_dir)
        self.queue = JobQueue(self._ingest_dir)

    def process_item(
        self,
        source: str,
        *,
        destination: str,
        title: str | None = None,
        content_type_override: str | None = None,
    ) -> IngestResult:
        """Process a single item through the pipeline.

        Args:
            source: Filesystem path, URL, or raw text.
            destination: Vault-relative destination path (e.g., 'notes/work').
            title: Extracted title for renaming. If None, derived from filename.
            content_type_override: Override auto-detection.

        Returns:
            IngestResult with processing outcome.
        """
        # Detect content type
        if content_type_override:
            try:
                ct = ContentType(content_type_override)
            except ValueError:
                ct = detect_content_type(source)
        else:
            ct = detect_content_type(source)

        # Create job record
        original_name = Path(source).name if "/" in source or "\\" in source else source[:50]
        job = self.queue.create(ct.value, source, original_name)
        job_id = job["id"]

        try:
            # Stage: update status
            self.queue.update(job_id, status=JobStatus.PROCESSING, stage="detect")

            # Validate source exists for file-based types
            source_path = Path(source)
            if ct not in (ContentType.URL, ContentType.YOUTUBE, ContentType.GITHUB, ContentType.TEXT):
                if not source_path.exists():
                    raise FileNotFoundError(f"Source not found: {source}")

            # Extract: get markdown content
            self.queue.update(job_id, stage="extract")
            markdown = self._extract(source_path, ct)

            # Rename: normalize filename
            self.queue.update(job_id, stage="rename")
            ext = None
            if ct in (ContentType.URL, ContentType.TEXT, ContentType.YOUTUBE):
                ext = ".md"
            renamed = normalize_filename(
                source_path.name if source_path.suffix else None,
                title=title,
                ext=ext,
            )
            self.queue.update(job_id, renamed_to=renamed)

            # Route: copy/move to destination
            self.queue.update(job_id, stage="route")
            dest_dir = self._vault_dir / destination
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / renamed

            # Handle collision
            collision = 0
            while dest_path.exists():
                collision += 1
                renamed = normalize_filename(
                    source_path.name if source_path.suffix else None,
                    title=title,
                    ext=ext,
                    collision_index=collision,
                )
                dest_path = dest_dir / renamed

            if ct in (ContentType.URL, ContentType.TEXT, ContentType.YOUTUBE):
                # Write extracted markdown directly
                dest_path.write_text(markdown, encoding="utf-8")
            elif ct == ContentType.MARKDOWN:
                # Copy markdown file
                shutil.copy2(str(source_path), str(dest_path))
            else:
                # Copy binary file
                shutil.copy2(str(source_path), str(dest_path))
                # Also write extracted markdown alongside if we have it
                if markdown:
                    md_path = dest_path.with_suffix(".extracted.md")
                    md_path.write_text(markdown, encoding="utf-8")

            # Index: the agent triggers RAG reindexing after routing
            # by calling the existing reindex-browse-category or rag-reindex MCP tools.
            # The pipeline marks this stage complete — actual indexing is agent-orchestrated.
            self.queue.update(job_id, stage="index")

            # Complete
            self.queue.complete(
                job_id,
                destination=str(dest_path),
                renamed_to=renamed,
            )
            self.queue.cleanup_staging(job_id)

            return IngestResult(
                success=True,
                job_id=job_id,
                content_type=ct,
                source=source,
                destination=str(dest_path),
                renamed_to=renamed,
                extracted_markdown=markdown,
            )

        except Exception as exc:
            self.queue.fail(job_id, error=str(exc))
            return IngestResult(
                success=False,
                job_id=job_id,
                content_type=ct,
                source=source,
                error=str(exc),
            )

    def process_batch(
        self, items: list[dict[str, Any]]
    ) -> list[IngestResult]:
        """Process multiple items sequentially.

        Args:
            items: List of dicts with keys: source, destination, title?, type?

        Returns:
            List of IngestResult, one per item.
        """
        results = []
        for item in items:
            result = self.process_item(
                item["source"],
                destination=item.get("destination", "inbox"),
                title=item.get("title"),
                content_type_override=item.get("type"),
            )
            results.append(result)
        return results

    def _extract(self, source: Path, ct: ContentType) -> str:
        """Extract content to markdown based on type.

        For complex extraction (PDF via opendataloader-pdf, OCR images),
        the agent should call ingest-extract directly and pass the result.
        This method handles simple cases.
        """
        if ct == ContentType.MARKDOWN:
            return source.read_text(encoding="utf-8")

        if ct == ContentType.TEXT:
            return str(source)

        # For files with known extractors, try MarkItDown
        if ct in (ContentType.PDF, ContentType.DOCUMENT, ContentType.IMAGE):
            try:
                from markitdown import MarkItDown
                mid = MarkItDown()
                result = mid.convert(str(source))
                return result.text_content or ""
            except Exception:
                return ""

        # URLs, YouTube, GitHub — extraction handled by existing skills
        # The agent calls the appropriate MCP tool and passes results
        return ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd skills/ingest && PYTHONPATH=. python -m pytest augur/tests/test_pipeline.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/pipeline.py skills/ingest/augur/tests/test_pipeline.py
git commit -m "feat(ingest): pipeline orchestrator with detect, extract, rename, route stages"
```

---

## Task 6: MCP Tool Registration

**Files:**
- Create: `skills/ingest/scripts/mcp/__init__.py`
- Create: `skills/ingest/scripts/mcp/ingest_tools.py`

- [ ] **Step 1: Write MCP tool registration entry point**

Create `skills/ingest/scripts/mcp/__init__.py`:

```python
"""MCP tool registration for ingest skill."""
```

- [ ] **Step 2: Write MCP tools**

Create `skills/ingest/scripts/mcp/ingest_tools.py`:

```python
"""MCP tool definitions for the ingest pipeline.

All tools are stateless atomic operations. The agent orchestrates
the pipeline — classification and summarization happen at the agent
level using LLM capability.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# Path bootstrap
_skill_root = Path(__file__).resolve().parents[2]
_scripts_dir = _skill_root / "scripts"
if str(_skill_root) not in sys.path:
    sys.path.insert(0, str(_skill_root))
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

try:
    from augur_mcp.logging import get_entity_logger
    from augur_mcp.annotations import tool_annotations
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        return importlib.import_module("logging").getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations


logger = get_entity_logger("ingest")


def _get_pipeline():
    """Lazy-init the pipeline with proper paths."""
    from pipeline import IngestPipeline

    try:
        from src.config.paths import get_runtime_dir, get_vault_dir, get_rag_dir
        ingest_dir = get_runtime_dir() / "ingest"
        vault_dir = get_vault_dir()
        rag_dir = get_rag_dir()
    except ImportError:
        # Fallback for testing
        ingest_dir = Path.home() / "Library" / "Application Support" / "Augur" / "state" / "ingest"
        vault_dir = Path.home() / "Au-vault"
        rag_dir = Path.home() / "Library" / "Application Support" / "Augur" / "rag"

    return IngestPipeline(ingest_dir=ingest_dir, vault_dir=vault_dir, rag_dir=rag_dir)


def register_ingest_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register all ingest MCP tools."""

    @mcp.tool(
        name="ingest-process",
        annotations=tool_annotations({
            "title": "Ingest Process",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def ingest_process(
        items: str = "[]",
    ) -> str:
        """Process a batch of items through the ingest pipeline.

        Args:
            items: JSON array of objects with keys:
                   source (required), destination (required),
                   title (optional), type (optional).

        Each item goes through: detect → extract → rename → route.
        Classification and summarization should be done by the agent
        before calling this tool.
        """
        metrics.track_tool("ingest_process", skill="ingest")
        try:
            parsed = json.loads(items) if isinstance(items, str) else items
            pipeline = _get_pipeline()
            results = pipeline.process_batch(parsed)
            return json.dumps({
                "success": True,
                "results": [
                    {
                        "source": r.source,
                        "status": "completed" if r.success else "failed",
                        "destination": r.destination,
                        "renamed_to": r.renamed_to,
                        "content_type": r.content_type.value,
                        "error": r.error,
                    }
                    for r in results
                ],
                "processed": sum(1 for r in results if r.success),
                "failed": sum(1 for r in results if not r.success),
            }, indent=2)
        except Exception as exc:
            logger.error("ingest-process failed: %s", exc, exc_info=True)
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="ingest-extract",
        annotations=tool_annotations({
            "title": "Ingest Extract",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def ingest_extract(source: str = "", type: str = "") -> str:
        """Extract a single file to markdown without routing.

        Useful when the agent wants to read content before classifying.
        """
        metrics.track_tool("ingest_extract", skill="ingest")
        try:
            from detector import detect_content_type, ContentType
            ct = ContentType(type) if type else detect_content_type(source)
            pipeline = _get_pipeline()
            markdown = pipeline._extract(Path(source), ct)
            title = Path(source).stem if Path(source).suffix else source[:50]
            return json.dumps({
                "success": True,
                "markdown": markdown[:10000],  # cap for context
                "title": title,
                "format": ct.value,
                "size_bytes": Path(source).stat().st_size if Path(source).exists() else 0,
            }, indent=2)
        except Exception as exc:
            logger.error("ingest-extract failed: %s", exc, exc_info=True)
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="ingest-rename",
        annotations=tool_annotations({
            "title": "Ingest Rename",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def ingest_rename(path: str = "", title: str = "") -> str:
        """Preview what a file would be renamed to without moving it."""
        metrics.track_tool("ingest_rename", skill="ingest")
        try:
            from renamer import normalize_filename
            renamed = normalize_filename(Path(path).name if path else None, title=title or None)
            return json.dumps({
                "success": True,
                "original": Path(path).name if path else None,
                "renamed_to": renamed,
            }, indent=2)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="ingest-route",
        annotations=tool_annotations({
            "title": "Ingest Route",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def ingest_route(source: str = "", destination: str = "") -> str:
        """Move a file to a vault destination and index it."""
        metrics.track_tool("ingest_route", skill="ingest")
        try:
            pipeline = _get_pipeline()
            result = pipeline.process_item(source, destination=destination)
            return json.dumps({
                "success": result.success,
                "routed_to": result.destination,
                "renamed_to": result.renamed_to,
                "indexed": True,
                "error": result.error,
            }, indent=2)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="ingest-status",
        annotations=tool_annotations({
            "title": "Ingest Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def ingest_status(job_id: str = "") -> str:
        """Get ingest job queue status."""
        metrics.track_tool("ingest_status", skill="ingest")
        try:
            pipeline = _get_pipeline()
            if job_id:
                job = pipeline.queue.get(job_id)
                return json.dumps({"success": True, "job": job}, indent=2, default=str)
            jobs = pipeline.queue.list_jobs()
            return json.dumps({
                "success": True,
                "jobs": jobs,
                "queue_size": len(jobs),
            }, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="ingest-history",
        annotations=tool_annotations({
            "title": "Ingest History",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def ingest_history(limit: int = 20) -> str:
        """Get recent ingest history (completed jobs)."""
        metrics.track_tool("ingest_history", skill="ingest")
        try:
            from job_queue import JobStatus
            pipeline = _get_pipeline()
            completed = pipeline.queue.list_jobs(status=JobStatus.COMPLETED, limit=limit)
            return json.dumps({
                "success": True,
                "items": [
                    {
                        "source": j["source"],
                        "destination": j["classified_to"],
                        "type": j["type"],
                        "renamed_to": j["renamed_to"],
                        "created_at": j["created_at"],
                        "completed_at": j["completed_at"],
                    }
                    for j in completed
                ],
                "count": len(completed),
            }, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="ingest-config",
        annotations=tool_annotations({
            "title": "Ingest Config",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def ingest_config(key: str = "", value: str = "") -> str:
        """Read or write ingest configuration."""
        metrics.track_tool("ingest_config", skill="ingest")
        try:
            import yaml as _yaml
            config_path = _skill_root / "augur" / "data" / "config-defaults.yaml"
            config = _yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
            if key and value:
                # Write mode: set a config value
                keys = key.split(".")
                target = config
                for k in keys[:-1]:
                    target = target.setdefault(k, {})
                target[keys[-1]] = value
                config_path.write_text(
                    _yaml.dump(config, allow_unicode=True, sort_keys=False, default_flow_style=False),
                    encoding="utf-8",
                )
                return json.dumps({"success": True, "updated": {key: value}}, indent=2)
            # Read mode
            if key:
                keys = key.split(".")
                val = config
                for k in keys:
                    val = val.get(k, {}) if isinstance(val, dict) else None
                return json.dumps({"success": True, "key": key, "value": val}, indent=2, default=str)
            return json.dumps({"success": True, "config": config}, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})
```

- [ ] **Step 3: Commit**

```bash
git add skills/ingest/scripts/mcp/
git commit -m "feat(ingest): MCP tools — ingest-process, ingest-extract, ingest-rename, ingest-route, ingest-status, ingest-history, ingest-config"
```

---

## Task 7: CLI Command

**Files:**
- Create: `skills/ingest/commands/ingest.md`

- [ ] **Step 1: Write the /ingest command definition**

Create `skills/ingest/commands/ingest.md`:

```markdown
---
id: ingest
description: Ingest files, URLs, folders, or text into the Augur knowledge base
skill: ingest
tags: [ingest, pipeline, knowledge]
---

Ingest content into the Augur knowledge base. Accepts files, URLs, folders, or raw text.

## Usage

```
/ingest <sources...> [--to <destination>] [--text]
```

## Arguments

- `<sources>`: One or more file paths, URLs, or folder paths to ingest
- `--to <destination>`: Override auto-classification with an explicit vault-relative path (e.g., `finance/documents`)
- `--text`: Treat all arguments as raw text to save as a markdown note

## Examples

```bash
/ingest document.pdf                          # Single file
/ingest file1.pdf file2.docx                  # Multiple files
/ingest path/to/folder/                       # Entire folder
/ingest https://arxiv.org/abs/2401.12345      # URL (scraped + summarized)
/ingest https://youtube.com/watch?v=abc       # YouTube (transcribed)
/ingest document.pdf --to finance/reports     # Explicit destination
```

## Processing Steps

For each item:

1. **Detect** content type (file, URL, YouTube, GitHub, etc.)
2. **Extract** text content to markdown using the appropriate extractor
3. **Classify** destination — you (the agent) decide where it goes based on the content
4. **Rename** to normalized `YYYY-MM-DD-slug.ext` pattern
5. **Summarize** URLs/articles to markdown (if configured)
6. **Route** to the vault destination
7. **Index** in RAG for searchability

For batch processing, use parallel tool calls or batch command to process multiple items concurrently.

## MCP Tools

- `ingest-process` — process batch through the full pipeline (extract + rename + route)
- `ingest-extract` — extract a single file to markdown (for pre-classification review)
- `ingest-rename` — preview filename normalization
- `ingest-route` — move a file to destination and index
- `ingest-status` — check processing status
- `ingest-config` — read/write ingest settings
```

- [ ] **Step 2: Commit**

```bash
git add skills/ingest/commands/ingest.md
git commit -m "feat(ingest): /ingest CLI command definition"
```

---

## Task 8: Upload API Route

**Files:**
- Create: `apps/dashboard/app/api/ingest/upload/route.ts`

- [ ] **Step 1: Write the upload API route**

Create `apps/dashboard/app/api/ingest/upload/route.ts`:

```typescript
import { NextRequest, NextResponse } from "next/server";
import { writeFile, mkdir } from "fs/promises";
import { join } from "path";
import { randomBytes } from "crypto";

/**
 * POST /api/ingest/upload
 *
 * Receives file uploads from the dashboard drop zone / FAB modal.
 * Stages files to the ingest staging directory and returns job metadata.
 *
 * Note: This is a thin staging endpoint — it does NOT process files.
 * Processing happens when the agent calls ingest-process MCP tool.
 */
export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const files = formData.getAll("files") as File[];

    if (files.length === 0) {
      return NextResponse.json(
        { success: false, error: "No files provided" },
        { status: 400 }
      );
    }

    // Resolve staging directory
    const stateDir =
      process.env.AUGUR_STATE ||
      join(
        process.env.HOME || "",
        "Library",
        "Application Support",
        "Augur",
        "state"
      );
    const stagingBase = join(stateDir, "ingest", "staging");

    const staged: Array<{ jobId: string; name: string; path: string; size: number }> = [];

    for (const file of files) {
      const jobId = randomBytes(4).toString("hex");
      const jobDir = join(stagingBase, jobId);
      await mkdir(jobDir, { recursive: true });

      const buffer = Buffer.from(await file.arrayBuffer());
      const filePath = join(jobDir, file.name);
      await writeFile(filePath, buffer);

      staged.push({
        jobId,
        name: file.name,
        path: filePath,
        size: buffer.length,
      });
    }

    return NextResponse.json({
      success: true,
      staged,
      count: staged.length,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Upload failed";
    return NextResponse.json(
      { success: false, error: message },
      { status: 500 }
    );
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/dashboard/app/api/ingest/upload/route.ts
git commit -m "feat(ingest): upload API route for staging files from dashboard"
```

---

## Task 9: Dashboard Drop Zone & FAB

**Files:**
- Create: `skills/ingest/augur/dashboard/IngestDropZone.tsx`
- Create: `skills/ingest/augur/dashboard/IngestFAB.tsx`
- Create: `skills/ingest/augur/dashboard/IngestQueueItem.tsx`

- [ ] **Step 1: Write IngestQueueItem component**

Create `skills/ingest/augur/dashboard/IngestQueueItem.tsx`:

```tsx
"use client";

import { Circle, CheckCircle2, XCircle, Loader2 } from "lucide-react";

interface QueueItem {
  jobId: string;
  name: string;
  status: "pending" | "processing" | "completed" | "failed";
  stage?: string;
  destination?: string;
  error?: string;
}

const STATUS_ICONS = {
  pending: <Circle className="h-4 w-4 text-muted-foreground" />,
  processing: <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />,
  completed: <CheckCircle2 className="h-4 w-4 text-green-500" />,
  failed: <XCircle className="h-4 w-4 text-red-500" />,
} as const;

export function IngestQueueItem({ item }: { item: QueueItem }) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 text-sm border-b border-border last:border-0">
      {STATUS_ICONS[item.status]}
      <div className="flex-1 min-w-0">
        <div className="truncate font-medium">{item.name}</div>
        {item.stage && item.status === "processing" && (
          <div className="text-xs text-muted-foreground">{item.stage}...</div>
        )}
        {item.destination && item.status === "completed" && (
          <div className="text-xs text-muted-foreground truncate">
            &rarr; {item.destination}
          </div>
        )}
        {item.error && (
          <div className="text-xs text-red-400 truncate">{item.error}</div>
        )}
      </div>
    </div>
  );
}

export type { QueueItem };
```

- [ ] **Step 2: Write IngestFAB component**

Create `skills/ingest/augur/dashboard/IngestFAB.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Plus, X } from "lucide-react";
import { IngestQueueItem, type QueueItem } from "./IngestQueueItem";

interface IngestFABProps {
  queue: QueueItem[];
  onAddClick: () => void;
}

export function IngestFAB({ queue, onAddClick }: IngestFABProps) {
  const [expanded, setExpanded] = useState(false);
  const activeCount = queue.filter(
    (q) => q.status === "pending" || q.status === "processing"
  ).length;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-2">
      {/* Queue panel */}
      {expanded && queue.length > 0 && (
        <div className="w-80 max-h-64 overflow-y-auto rounded-lg border border-border bg-card shadow-lg">
          <div className="flex items-center justify-between px-3 py-2 border-b border-border">
            <span className="text-sm font-medium">
              Processing ({activeCount})
            </span>
            <button
              onClick={() => setExpanded(false)}
              className="text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          {queue.map((item) => (
            <IngestQueueItem key={item.jobId} item={item} />
          ))}
        </div>
      )}

      {/* FAB button */}
      <button
        onClick={() => {
          if (activeCount > 0) {
            setExpanded(!expanded);
          } else {
            onAddClick();
          }
        }}
        className="relative flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg hover:bg-primary/90 transition-colors"
      >
        <Plus className="h-5 w-5" />
        {activeCount > 0 && (
          <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-blue-500 text-[10px] font-bold text-white">
            {activeCount}
          </span>
        )}
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Write IngestDropZone component**

Create `skills/ingest/augur/dashboard/IngestDropZone.tsx`:

```tsx
"use client";

import { useState, useCallback, type DragEvent, type ReactNode } from "react";
import { Upload } from "lucide-react";

interface IngestDropZoneProps {
  onDrop: (files: File[]) => void;
  children: ReactNode;
}

export function IngestDropZone({ onDrop, children }: IngestDropZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDragEnter = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    // Only hide overlay when leaving the container (not children)
    if (e.currentTarget === e.target) {
      setIsDragOver(false);
    }
  }, []);

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);

      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) {
        onDrop(files);
      }
    },
    [onDrop]
  );

  return (
    <div
      className="relative"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {children}

      {/* Overlay — visible only during drag */}
      {isDragOver && (
        <div className="absolute inset-0 z-40 flex flex-col items-center justify-center bg-background/80 backdrop-blur-sm border-2 border-dashed border-primary rounded-lg">
          <Upload className="h-12 w-12 text-primary mb-3" />
          <p className="text-lg font-medium text-foreground">
            Drop to ingest
          </p>
          <p className="text-sm text-muted-foreground mt-1">
            PDF, DOCX, images, markdown, folders
          </p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add skills/ingest/augur/dashboard/IngestDropZone.tsx skills/ingest/augur/dashboard/IngestFAB.tsx skills/ingest/augur/dashboard/IngestQueueItem.tsx
git commit -m "feat(ingest): dashboard drop zone, FAB, and queue item components"
```

---

## Task 10: Ingest Modal

**Files:**
- Create: `skills/ingest/augur/dashboard/IngestModal.tsx`

- [ ] **Step 1: Write the IngestModal component**

Create `skills/ingest/augur/dashboard/IngestModal.tsx`:

```tsx
"use client";

import { useState, useRef } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { FileText, Link, Type, Folder } from "lucide-react";

interface IngestModalProps {
  open: boolean;
  onClose: () => void;
  onSubmitFiles: (files: File[]) => void;
  onSubmitUrl: (url: string) => void;
  onSubmitText: (text: string) => void;
}

export function IngestModal({
  open,
  onClose,
  onSubmitFiles,
  onSubmitUrl,
  onSubmitText,
}: IngestModalProps) {
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  const handleFileSubmit = () => {
    const files = fileInputRef.current?.files;
    if (files && files.length > 0) {
      onSubmitFiles(Array.from(files));
      onClose();
    }
  };

  const handleFolderSubmit = () => {
    const files = folderInputRef.current?.files;
    if (files && files.length > 0) {
      onSubmitFiles(Array.from(files));
      onClose();
    }
  };

  const handleUrlSubmit = () => {
    if (url.trim()) {
      onSubmitUrl(url.trim());
      setUrl("");
      onClose();
    }
  };

  const handleTextSubmit = () => {
    if (text.trim()) {
      onSubmitText(text.trim());
      setText("");
      onClose();
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Content</DialogTitle>
        </DialogHeader>

        <Tabs defaultValue="files" className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="files" className="gap-1">
              <FileText className="h-3 w-3" />
              Files
            </TabsTrigger>
            <TabsTrigger value="url" className="gap-1">
              <Link className="h-3 w-3" />
              URL
            </TabsTrigger>
            <TabsTrigger value="text" className="gap-1">
              <Type className="h-3 w-3" />
              Text
            </TabsTrigger>
            <TabsTrigger value="folder" className="gap-1">
              <Folder className="h-3 w-3" />
              Folder
            </TabsTrigger>
          </TabsList>

          <TabsContent value="files" className="space-y-3 pt-3">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="block w-full text-sm file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-primary file:text-primary-foreground hover:file:bg-primary/90"
            />
            <Button onClick={handleFileSubmit} className="w-full">
              Upload Files
            </Button>
          </TabsContent>

          <TabsContent value="url" className="space-y-3 pt-3">
            <Input
              placeholder="https://example.com/article"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleUrlSubmit()}
            />
            <p className="text-xs text-muted-foreground">
              Paste a URL to scrape, summarize, and save as markdown
            </p>
            <Button onClick={handleUrlSubmit} className="w-full">
              Ingest URL
            </Button>
          </TabsContent>

          <TabsContent value="text" className="space-y-3 pt-3">
            <Textarea
              placeholder="Paste notes, snippets, or raw text..."
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={5}
            />
            <Button onClick={handleTextSubmit} className="w-full">
              Save as Note
            </Button>
          </TabsContent>

          <TabsContent value="folder" className="space-y-3 pt-3">
            <input
              ref={folderInputRef}
              type="file"
              {...({ webkitdirectory: "", directory: "" } as any)}
              className="block w-full text-sm file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-primary file:text-primary-foreground hover:file:bg-primary/90"
            />
            <p className="text-xs text-muted-foreground">
              Select a folder to ingest all files recursively
            </p>
            <Button onClick={handleFolderSubmit} className="w-full">
              Upload Folder
            </Button>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add skills/ingest/augur/dashboard/IngestModal.tsx
git commit -m "feat(ingest): input modal with Files, URL, Text, and Folder tabs"
```

---

## Task 11: Integration — Wire into Browse Page

**Files:**
- This task documents how the skill owner (or agent) wires the components into the browse page. The IngestDropZone wraps the browse page content, the IngestFAB is positioned absolutely, and the IngestModal opens from the FAB.

- [ ] **Step 1: Verify skill discovery**

Run: `ls skills/ingest/SKILL.md` — confirm skill exists and is discoverable.

Run: `python -c "from src.config.paths import get_runtime_dir; print(get_runtime_dir() / 'ingest')"` — confirm runtime path resolves.

- [ ] **Step 2: Test MCP tools via CLI**

Start a CLI session and test:

```
/ingest /tmp/test-file.md
```

Verify the command loads, the agent calls `ingest-process`, and the file is routed.

- [ ] **Step 3: Test upload API route**

```bash
# Create a test file
echo "# Test Document" > /tmp/ingest-test.md

# Test the upload endpoint
curl -X POST http://localhost:3000/api/ingest/upload \
  -F "files=@/tmp/ingest-test.md" \
  | python3 -m json.tool
```

Expected: `{"success": true, "staged": [...], "count": 1}`

- [ ] **Step 4: Verify dashboard components mount**

Run `/dev-build` and check that:
- No build errors related to ingest components
- The browse page renders without errors
- Drop zone, FAB, and modal components are accessible

- [ ] **Step 5: Browser verification**

Open the browse page in Chrome:
1. Drag a file onto the page — overlay should appear
2. Drop the file — it should enter the processing queue
3. Click the FAB — the modal should open with 4 tabs
4. Paste a URL in the URL tab and submit

- [ ] **Step 6: Commit integration**

```bash
git add -A
git commit -m "feat(ingest): wire drop zone, FAB, and modal into browse page"
```

---

## Dependencies Between Tasks

```
Task 1 (Scaffold)
  ↓
Task 2 (Detector) ──→ Task 5 (Pipeline) ──→ Task 6 (MCP Tools) ──→ Task 7 (CLI Command)
Task 3 (Renamer)  ──↗                                              ↓
Task 4 (Job Queue) ─↗                                     Task 11 (Integration)
                                                                    ↑
Task 8 (Upload API) ──→ Task 9 (Drop Zone + FAB) ──→ Task 10 (Modal) ─↗
```

Tasks 2, 3, 4, 8 can run in parallel after Task 1.
Tasks 9 and 10 can run in parallel after Task 8.
Task 11 requires all other tasks.

## Note: Nightly Tracked Folder Scan

The spec describes a nightly daemon scan of tracked folders. This does NOT require new code — the daemon triggers an AI client session that calls the same `/ingest` command on tracked folder paths. Configuration is via `ingest-config` (`ingest.tracked_folders`). The daemon integration is a daemon config task, not an ingest skill task.
