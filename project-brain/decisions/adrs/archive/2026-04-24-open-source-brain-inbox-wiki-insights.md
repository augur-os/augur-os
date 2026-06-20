# Open-Source Brain Inbox and Wiki Insights Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the open-source first-use Brain Inbox journey: watched folders, one-click Consume, Purge to Trash, deep document understanding, wiki/RAG compounding signals, Brain Insights, and hardened Browse wiki cards.

**Architecture:** Add a first-class inbox workflow inside the `ingest` skill, exposed through MCP tools and consumed by dashboard Brain pages through MCP hooks. The backend stores folder config and run history in runtime state, reuses existing ingest/document/RAG/wiki primitives, and keeps compiled wiki pages concept-first. The dashboard adds flat Brain pages for Inbox and Insights and updates Browse wiki card behavior without bypassing MCP.

**Tech Stack:** Python 3.11, pytest, FastMCP tool registration, Augur path helpers, Next.js 16, React 19, TypeScript, Jest, MCP dashboard hooks, lucide-react.

---

## Scope Check

This plan is one product slice, not separate products. The backend, Brain UI, Browse wiki hardening, and verification are coupled by the same user journey: a local knowledge worker adds a folder, clicks Consume, and sees organized files plus new insights.

Implementation must happen in a dedicated worktree before code changes. Do not implement this directly in the root `main` checkout.

## File Structure

### Backend

- Create `skills/ingest/scripts/inbox_models.py` for dataclasses and normalization helpers.
- Create `skills/ingest/scripts/inbox_store.py` for runtime JSON persistence of folders and run records.
- Create `skills/ingest/scripts/inbox_trash.py` for OS-trash abstraction and purge planning.
- Create `skills/ingest/scripts/inbox_consume.py` for scan, consume, purge, run-history, and Brain Insights orchestration.
- Modify `skills/ingest/scripts/mcp/ingest_tools.py` to register inbox MCP tools.
- Modify `skills/ingest/SKILL.md` to list the new MCP tools.
- Modify `skills/rag/scripts/document_understanding.py` to expose richer confidence/action fields.
- Test with new `skills/ingest/augur/tests/test_inbox_store.py`, `test_inbox_consume.py`, `test_inbox_mcp_tools.py`, and expanded `skills/rag/augur/tests/test_binary_extractor.py`.

### Dashboard

- Create `apps/dashboard/features/pages/brain/inbox/page.tsx`.
- Create `apps/dashboard/features/pages/brain/inbox/hooks.ts`.
- Create `apps/dashboard/features/pages/brain/inbox/types.ts`.
- Create `apps/dashboard/features/pages/brain/insights/page.tsx`.
- Create `apps/dashboard/features/pages/brain/insights/hooks.ts`.
- Create `apps/dashboard/features/pages/brain/insights/types.ts`.
- Modify `apps/dashboard/features/pages/brain/overview/BrainOverviewHome.tsx`.
- Modify `apps/dashboard/lib/browse/transforms.ts`.
- Modify `apps/dashboard/components/shared/BrowseCard.tsx`.
- Modify `apps/dashboard/app/(views)/browse/page.tsx`.
- Add Jest tests under `apps/dashboard/features/pages/brain/inbox/page.test.tsx`, `apps/dashboard/features/pages/brain/insights/page.test.tsx`, and `apps/dashboard/components/shared/BrowseCard.test.tsx`.

### Generated/Registry

- Run `cd apps/dashboard && pnpm run mount-plugins` after adding Brain pages.
- Run dashboard tests and build before final merge.
- Browser-verify `/brain/inbox`, `/brain/insights`, `/brain`, and `/browse?category=wiki`.

---

### Task 1: Create Isolated Worktree And ADR Record

**Files:**
- Create: external ADR file from `get_adr_dir()`
- Read: `docs/superpowers/specs/2026-04-24-open-source-brain-inbox-wiki-insights-design.md`
- No code implementation files in this task

- [ ] **Step 1: Create a dedicated worktree**

Run:

```bash
git fetch origin
git worktree add ../augur-wt-brain-inbox-wiki-insights -b brain-inbox-wiki-insights origin/main
cd ../augur-wt-brain-inbox-wiki-insights
```

Expected: new worktree on branch `brain-inbox-wiki-insights`.

- [ ] **Step 2: Confirm clean isolated state**

Run:

```bash
git status --short --branch
```

Expected:

```text
## brain-inbox-wiki-insights...origin/main
```

- [ ] **Step 3: Find the ADR directory and next ADR number**

Run:

```bash
uv run python - <<'PY'
from pathlib import Path
from src.config.paths import get_adr_dir

adr_dir = get_adr_dir()
numbers = []
for path in adr_dir.glob("ADR-*.md"):
    stem = path.stem
    try:
        numbers.append(int(stem.split("-", 1)[1]))
    except (IndexError, ValueError):
        pass
next_number = max(numbers, default=0) + 1
print(adr_dir)
print(f"ADR-{next_number:03d}")
PY
```

Expected: first line is the external ADR directory, second line is the next ADR id.

- [ ] **Step 4: Write the ADR**

Run this command to create the ADR with the computed next number:

```bash
uv run python - <<'PY'
from pathlib import Path
from src.config.paths import get_adr_dir

adr_dir = get_adr_dir()
numbers = []
for path in adr_dir.glob("ADR-*.md"):
    stem = path.stem
    try:
        numbers.append(int(stem.split("-", 1)[1]))
    except (IndexError, ValueError):
        pass
number = max(numbers, default=0) + 1
path = adr_dir / f"ADR-{number:03d}-open-source-brain-inbox-wiki-insights.md"
path.write_text(
    f"""---
title: Open-Source Brain Inbox and Wiki Insights
status: Accepted
date: 2026-04-24
---

# ADR-{number:03d}: Open-Source Brain Inbox and Wiki Insights

## Context

Augur's open-source first-use journey needs a concrete local knowledge-worker outcome. Users should be able to add folders such as Desktop or Downloads, click Consume, and receive organized files, searchable context, cross-source insights, and next actions.

Existing ingest, document extraction, RAG indexing, wiki compounding, and Brain dashboard pieces are present, but folder consume is not a first-class product workflow.

## Decision

Add a Brain Inbox and Brain Insights journey:

- Store user-configured inbox folders in runtime state.
- Expose folder scan, consume, purge-to-trash, run history, run detail, and Brain insights through MCP tools owned by the ingest skill.
- Reuse existing ingest, document understanding, RAG, and wiki compounding primitives.
- Keep compiled wiki pages concept-first and agent-orchestrated.
- Add flat Brain pages `/brain/inbox` and `/brain/insights`.
- Harden Browse wiki cards with cleaned tags, contextual primary actions, and overflow actions.

## Consequences

The dashboard remains MCP-first and does not directly touch local files. Folder Consume can be automatic after a user click, while Purge only moves files to OS trash and never permanently deletes them.

This creates a clear open-source user journey and a durable implementation boundary for later background scheduling or richer folder policies.
""",
    encoding="utf-8",
)
print(path)
PY
```

Expected: the command prints the created ADR file path.

- [ ] **Step 5: Commit the ADR**

Run:

```bash
ADR_PATH="$(uv run python - <<'PY'
from src.config.paths import get_adr_dir
paths = sorted(get_adr_dir().glob("ADR-*-open-source-brain-inbox-wiki-insights.md"))
print(paths[-1])
PY
)"
git add "$ADR_PATH"
git commit -m "docs: record brain inbox wiki insights decision"
```

Expected: one ADR commit. If the external ADR directory is a separate git repo, commit it there and record the ADR path in the final task summary.

---

### Task 2: Backend Inbox Models And Runtime Store

**Files:**
- Create: `skills/ingest/scripts/inbox_models.py`
- Create: `skills/ingest/scripts/inbox_store.py`
- Create: `skills/ingest/augur/tests/test_inbox_store.py`

- [ ] **Step 1: Write failing store tests**

Create `skills/ingest/augur/tests/test_inbox_store.py`:

```python
from __future__ import annotations

from pathlib import Path


def test_store_adds_folder_and_persists_counts(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_store import InboxStore

    store = InboxStore(tmp_path / "inbox")

    folder = store.add_folder(name="Downloads", path=tmp_path / "Downloads")
    saved = store.update_folder_counts(
        folder.id,
        {
            "new_files": 3,
            "document_candidates": 2,
            "trash_candidates": 1,
            "failed": 0,
        },
    )

    reloaded = InboxStore(tmp_path / "inbox")
    folders = reloaded.list_folders()

    assert saved.counts.new_files == 3
    assert len(folders) == 1
    assert folders[0].id == "downloads"
    assert folders[0].name == "Downloads"
    assert folders[0].path == str((tmp_path / "Downloads").resolve(strict=False))
    assert folders[0].enabled is True


def test_store_records_run_history_and_detail(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_models import InboxInsight, InboxRunRecord
    from skills.ingest.scripts.inbox_store import InboxStore

    store = InboxStore(tmp_path / "inbox")
    folder = store.add_folder(name="Desktop", path=tmp_path / "Desktop")
    record = InboxRunRecord(
        id="run_123",
        folder_id=folder.id,
        started_at="2026-04-24T10:00:00+00:00",
        completed_at="2026-04-24T10:01:00+00:00",
        status="success",
        files_seen=1,
        files_moved=1,
        files_indexed=1,
        files_skipped=0,
        files_failed=0,
        wiki_update_marked=True,
        wiki_batch_created=False,
        insights=[
            InboxInsight(
                title="Health paperwork grouped",
                summary="Two files support the same reimbursement workflow.",
                sources=["a.pdf", "b.pdf"],
                next_actions=["Review claim receipt"],
            )
        ],
        file_results=[],
    )

    store.save_run(record)

    assert store.list_runs(folder_id=folder.id)[0].id == "run_123"
    assert store.get_run("run_123").insights[0].title == "Health paperwork grouped"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest skills/ingest/augur/tests/test_inbox_store.py -q
```

Expected: FAIL with missing `inbox_store` or `inbox_models`.

- [ ] **Step 3: Create model dataclasses**

Create `skills/ingest/scripts/inbox_models.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class InboxFolderCounts:
    new_files: int = 0
    document_candidates: int = 0
    trash_candidates: int = 0
    failed: int = 0


@dataclass(frozen=True)
class InboxFolder:
    id: str
    name: str
    path: str
    enabled: bool = True
    last_scan_at: str | None = None
    last_consume_run_id: str | None = None
    last_purge_run_id: str | None = None
    counts: InboxFolderCounts = field(default_factory=InboxFolderCounts)


@dataclass(frozen=True)
class InboxInsight:
    title: str
    summary: str
    sources: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class InboxFileResult:
    source_path: str
    final_path: str | None = None
    extracted_markdown_path: str | None = None
    content_type: str = "unknown"
    document_kind: str = "document"
    extraction_method: str = "unknown"
    extraction_confidence: str = "low"
    ocr_applied: bool = False
    llm_assisted: bool = False
    route: str | None = None
    renamed_to: str | None = None
    rag_indexed: bool = False
    wiki_relevant: bool = False
    status: str = "pending"
    stage: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class InboxRunRecord:
    id: str
    folder_id: str
    started_at: str
    completed_at: str | None
    status: str
    files_seen: int
    files_moved: int
    files_indexed: int
    files_skipped: int
    files_failed: int
    wiki_update_marked: bool
    wiki_batch_created: bool
    insights: list[InboxInsight] = field(default_factory=list)
    file_results: list[InboxFileResult] = field(default_factory=list)


def folder_id_from_name(name: str) -> str:
    text = name.strip().lower()
    slug = "".join(char if char.isalnum() else "-" for char in text)
    slug = "-".join(part for part in slug.split("-") if part)
    return slug or "folder"


def normalize_folder_path(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve(strict=False))


def dataclass_to_dict(value: Any) -> dict[str, Any]:
    return asdict(value)
```

- [ ] **Step 4: Create runtime store**

Create `skills/ingest/scripts/inbox_store.py`:

```python
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from skills.ingest.scripts.inbox_models import (
    InboxFileResult,
    InboxFolder,
    InboxFolderCounts,
    InboxInsight,
    InboxRunRecord,
    dataclass_to_dict,
    folder_id_from_name,
    normalize_folder_path,
)


class InboxStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._folders_path = self.root / "folders.json"
        self._runs_path = self.root / "runs.json"

    def list_folders(self) -> list[InboxFolder]:
        data = self._read_json(self._folders_path, default=[])
        return [self._folder_from_dict(item) for item in data]

    def add_folder(self, *, name: str, path: str | Path) -> InboxFolder:
        folders = self.list_folders()
        folder_id = self._unique_folder_id(folder_id_from_name(name), folders)
        folder = InboxFolder(
            id=folder_id,
            name=name.strip() or Path(path).name,
            path=normalize_folder_path(path),
        )
        folders.append(folder)
        self._write_json(self._folders_path, [dataclass_to_dict(item) for item in folders])
        return folder

    def update_folder_counts(self, folder_id: str, counts: dict[str, int]) -> InboxFolder:
        folders = self.list_folders()
        next_folders: list[InboxFolder] = []
        updated: InboxFolder | None = None
        for folder in folders:
            if folder.id == folder_id:
                updated = replace(
                    folder,
                    counts=InboxFolderCounts(
                        new_files=int(counts.get("new_files", 0)),
                        document_candidates=int(counts.get("document_candidates", 0)),
                        trash_candidates=int(counts.get("trash_candidates", 0)),
                        failed=int(counts.get("failed", 0)),
                    ),
                )
                next_folders.append(updated)
            else:
                next_folders.append(folder)
        if updated is None:
            raise KeyError(f"Unknown inbox folder: {folder_id}")
        self._write_json(self._folders_path, [dataclass_to_dict(item) for item in next_folders])
        return updated

    def save_run(self, record: InboxRunRecord) -> InboxRunRecord:
        runs = [run for run in self.list_runs() if run.id != record.id]
        runs.append(record)
        self._write_json(self._runs_path, [dataclass_to_dict(run) for run in runs])
        return record

    def list_runs(self, *, folder_id: str | None = None) -> list[InboxRunRecord]:
        data = self._read_json(self._runs_path, default=[])
        runs = [self._run_from_dict(item) for item in data]
        if folder_id:
            runs = [run for run in runs if run.folder_id == folder_id]
        return sorted(runs, key=lambda run: run.started_at, reverse=True)

    def get_run(self, run_id: str) -> InboxRunRecord:
        for run in self.list_runs():
            if run.id == run_id:
                return run
        raise KeyError(f"Unknown inbox run: {run_id}")

    def _unique_folder_id(self, base: str, folders: list[InboxFolder]) -> str:
        existing = {folder.id for folder in folders}
        if base not in existing:
            return base
        index = 2
        while f"{base}-{index}" in existing:
            index += 1
        return f"{base}-{index}"

    def _folder_from_dict(self, data: dict[str, Any]) -> InboxFolder:
        counts = data.get("counts") if isinstance(data.get("counts"), dict) else {}
        return InboxFolder(
            id=str(data["id"]),
            name=str(data["name"]),
            path=str(data["path"]),
            enabled=bool(data.get("enabled", True)),
            last_scan_at=data.get("last_scan_at"),
            last_consume_run_id=data.get("last_consume_run_id"),
            last_purge_run_id=data.get("last_purge_run_id"),
            counts=InboxFolderCounts(**counts),
        )

    def _run_from_dict(self, data: dict[str, Any]) -> InboxRunRecord:
        return InboxRunRecord(
            id=str(data["id"]),
            folder_id=str(data["folder_id"]),
            started_at=str(data["started_at"]),
            completed_at=data.get("completed_at"),
            status=str(data["status"]),
            files_seen=int(data.get("files_seen", 0)),
            files_moved=int(data.get("files_moved", 0)),
            files_indexed=int(data.get("files_indexed", 0)),
            files_skipped=int(data.get("files_skipped", 0)),
            files_failed=int(data.get("files_failed", 0)),
            wiki_update_marked=bool(data.get("wiki_update_marked", False)),
            wiki_batch_created=bool(data.get("wiki_batch_created", False)),
            insights=[InboxInsight(**item) for item in data.get("insights", [])],
            file_results=[InboxFileResult(**item) for item in data.get("file_results", [])],
        )

    def _read_json(self, path: Path, *, default: Any) -> Any:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
```

- [ ] **Step 5: Run store tests**

Run:

```bash
pytest skills/ingest/augur/tests/test_inbox_store.py -q
```

Expected: `2 passed`.

- [ ] **Step 6: Commit**

Run:

```bash
git add skills/ingest/scripts/inbox_models.py skills/ingest/scripts/inbox_store.py skills/ingest/augur/tests/test_inbox_store.py
git commit -m "feat(inbox): add runtime folder store"
```

Expected: focused backend store commit.

---

### Task 3: Purge-To-Trash Planning And OS Trash Abstraction

**Files:**
- Create: `skills/ingest/scripts/inbox_trash.py`
- Create: `skills/ingest/augur/tests/test_inbox_trash.py`

- [ ] **Step 1: Write failing purge tests**

Create `skills/ingest/augur/tests/test_inbox_trash.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path


def test_plan_purge_skips_recent_files_and_directories(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_trash import plan_purge

    old_file = tmp_path / "old.tmp"
    old_file.write_text("cache", encoding="utf-8")
    recent_file = tmp_path / "recent.tmp"
    recent_file.write_text("download", encoding="utf-8")
    folder = tmp_path / "folder"
    folder.mkdir()

    old_time = datetime.now(tz=UTC) - timedelta(days=3)
    recent_time = datetime.now(tz=UTC)

    plan = plan_purge(
        [old_file, recent_file, folder],
        now=recent_time,
        modified_times={
            old_file: old_time,
            recent_file: recent_time,
            folder: old_time,
        },
    )

    assert [item.path for item in plan.to_trash] == [old_file]
    assert {item.reason for item in plan.skipped} == {"recently_modified", "directory"}


def test_move_to_trash_uses_injected_runner(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_trash import move_to_trash

    target = tmp_path / "old.tmp"
    target.write_text("cache", encoding="utf-8")
    calls: list[list[str]] = []

    result = move_to_trash(target, runner=lambda args: calls.append(args) or 0)

    assert result["success"] is True
    assert calls == [["osascript", "-e", f'tell application "Finder" to delete POSIX file "{target}"']]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest skills/ingest/augur/tests/test_inbox_trash.py -q
```

Expected: FAIL with missing `inbox_trash`.

- [ ] **Step 3: Implement trash planning**

Create `skills/ingest/scripts/inbox_trash.py`:

```python
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class PurgeCandidate:
    path: Path
    reason: str


@dataclass(frozen=True)
class PurgePlan:
    to_trash: list[PurgeCandidate]
    skipped: list[PurgeCandidate]


def plan_purge(
    paths: list[Path],
    *,
    now: datetime | None = None,
    modified_times: dict[Path, datetime] | None = None,
    recent_window: timedelta = timedelta(hours=2),
) -> PurgePlan:
    now = now or datetime.now(tz=UTC)
    modified_times = modified_times or {}
    to_trash: list[PurgeCandidate] = []
    skipped: list[PurgeCandidate] = []

    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            skipped.append(PurgeCandidate(path=path, reason="directory"))
            continue
        if not path.exists():
            skipped.append(PurgeCandidate(path=path, reason="missing"))
            continue
        modified = modified_times.get(path) or datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        if now - modified < recent_window:
            skipped.append(PurgeCandidate(path=path, reason="recently_modified"))
            continue
        if path.suffix.lower() in {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".md", ".txt"}:
            skipped.append(PurgeCandidate(path=path, reason="valuable_document"))
            continue
        to_trash.append(PurgeCandidate(path=path, reason="trash_candidate"))

    return PurgePlan(to_trash=to_trash, skipped=skipped)


def move_to_trash(path: Path, *, runner: Callable[[list[str]], int] | None = None) -> dict[str, object]:
    resolved = Path(path).resolve(strict=False)
    command = ["osascript", "-e", f'tell application "Finder" to delete POSIX file "{resolved}"']
    runner = runner or _default_runner
    code = runner(command)
    return {
        "success": code == 0,
        "path": str(resolved),
        "error": None if code == 0 else f"trash command exited with {code}",
    }


def _default_runner(args: list[str]) -> int:
    return subprocess.run(args, check=False).returncode
```

- [ ] **Step 4: Run purge tests**

Run:

```bash
pytest skills/ingest/augur/tests/test_inbox_trash.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add skills/ingest/scripts/inbox_trash.py skills/ingest/augur/tests/test_inbox_trash.py
git commit -m "feat(inbox): add purge to trash planning"
```

Expected: focused purge abstraction commit.

---

### Task 4: Deep Document Understanding Fields

**Files:**
- Modify: `skills/rag/scripts/document_understanding.py`
- Modify: `skills/rag/augur/tests/test_binary_extractor.py`

- [ ] **Step 1: Add failing document understanding test**

Append to `skills/rag/augur/tests/test_binary_extractor.py`:

```python
def test_extract_document_includes_deep_understanding_fields(tmp_path, monkeypatch):
    from skills.rag.scripts import document_understanding
    from skills.rag.scripts.unified_indexer import _extract_document

    doc = tmp_path / "invoice.txt"
    doc.write_text("Invoice\n\nTotal due 1200 NIS\nSubmit reimbursement by Friday.", encoding="utf-8")

    result = _extract_document(doc)

    assert result["document_extraction_confidence"] in {"low", "medium", "high"}
    assert result["document_action_candidates"] == ["Submit reimbursement by Friday."]
    assert result["document_low_signal_warnings"] == []
    assert result["document_llm_assisted"] is False
    assert document_understanding.UNDERSTANDING_VERSION >= "v2"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
pytest skills/rag/augur/tests/test_binary_extractor.py::test_extract_document_includes_deep_understanding_fields -q
```

Expected: FAIL because the fields are missing.

- [ ] **Step 3: Extend document understanding output**

Modify `skills/rag/scripts/document_understanding.py`:

```python
UNDERSTANDING_VERSION = "v2"
```

Add helper functions near `_section_hints`:

```python
def _extraction_confidence(body: str, *, method: str) -> str:
    words = body.split()
    if len(words) >= 80:
        return "high"
    if len(words) >= 12 or method != "failed":
        return "medium"
    return "low"


def _action_candidates(body: str) -> list[str]:
    candidates: list[str] = []
    markers = ("submit", "review", "send", "pay", "schedule", "call", "follow up")
    for line in body.splitlines():
        stripped = line.strip().strip("-* ")
        if not stripped:
            continue
        lowered = stripped.lower()
        if any(marker in lowered for marker in markers) and stripped not in candidates:
            candidates.append(stripped)
        if len(candidates) == 5:
            break
    return candidates


def _low_signal_warnings(body: str) -> list[str]:
    warnings: list[str] = []
    if not body.strip():
        warnings.append("empty_extraction")
    elif len(body.split()) < 12:
        warnings.append("short_extraction")
    return warnings
```

In `understand_document`, after `body` and `title` are computed, store method and return the new fields:

```python
    method = str(extracted.get("method") or "unknown")
    confidence = _extraction_confidence(body, method=method)

    return {
        "body": body,
        "title": title,
        "format": suffix.lstrip(".") or "unknown",
        "document_kind": "pdf" if suffix == ".pdf" else "document",
        "extraction_method": method,
        "ocr_applied": bool(extracted.get("ocr_applied")),
        "summary": _summarize(body=body, title=title),
        "key_insights": _key_insights(body),
        "section_hints": _section_hints(body),
        "action_candidates": _action_candidates(body),
        "extraction_confidence": confidence,
        "low_signal_warnings": _low_signal_warnings(body),
        "llm_assisted": method.endswith(":1"),
        "visual_structure_used": bool(extracted.get("ocr_applied")),
        "understanding_version": UNDERSTANDING_VERSION,
        "error": extracted.get("error"),
    }
```

Modify `_extract_document` in `skills/rag/scripts/unified_indexer.py` to include these fields:

```python
        "document_action_candidates": understanding["action_candidates"],
        "document_extraction_confidence": understanding["extraction_confidence"],
        "document_low_signal_warnings": understanding["low_signal_warnings"],
        "document_llm_assisted": understanding["llm_assisted"],
```

- [ ] **Step 4: Run binary extraction tests**

Run:

```bash
pytest skills/rag/augur/tests/test_binary_extractor.py -q
```

Expected: all tests in the file pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add skills/rag/scripts/document_understanding.py skills/rag/scripts/unified_indexer.py skills/rag/augur/tests/test_binary_extractor.py
git commit -m "feat(rag): expose deep document understanding fields"
```

Expected: focused document understanding commit.

---

### Task 5: Inbox Consume Pipeline

**Files:**
- Create: `skills/ingest/scripts/inbox_consume.py`
- Create: `skills/ingest/augur/tests/test_inbox_consume.py`

- [ ] **Step 1: Write failing consume tests**

Create `skills/ingest/augur/tests/test_inbox_consume.py`:

```python
from __future__ import annotations

from pathlib import Path


def test_scan_folder_counts_document_and_trash_candidates(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_consume import scan_folder

    folder = tmp_path / "Downloads"
    folder.mkdir()
    (folder / "claim.pdf").write_bytes(b"%PDF-1.4 fake")
    (folder / "notes.txt").write_text("Review insurance claim", encoding="utf-8")
    (folder / "cache.tmp").write_text("cache", encoding="utf-8")

    result = scan_folder(folder)

    assert result["counts"]["new_files"] == 3
    assert result["counts"]["document_candidates"] == 2
    assert result["counts"]["trash_candidates"] == 1


def test_consume_folder_records_partial_success_and_wiki_flag(tmp_path: Path, monkeypatch) -> None:
    from skills.ingest.scripts.inbox_consume import consume_folder
    from skills.ingest.scripts.inbox_store import InboxStore

    folder_path = tmp_path / "Downloads"
    folder_path.mkdir()
    source = folder_path / "claim.txt"
    source.write_text("Submit reimbursement by Friday.", encoding="utf-8")
    runtime = tmp_path / "runtime"
    vault = tmp_path / "vault"
    documents = tmp_path / "documents"
    store = InboxStore(runtime / "brain" / "inbox")
    folder = store.add_folder(name="Downloads", path=folder_path)

    def fake_route_file(path: Path, *, vault_dir: Path, documents_dir: Path):
        destination = documents_dir / "health" / path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        return destination

    monkeypatch.setattr("skills.ingest.scripts.inbox_consume._route_file", fake_route_file)
    monkeypatch.setattr("skills.ingest.scripts.inbox_consume._reindex_documents", lambda *_args, **_kwargs: True)

    record = consume_folder(
        folder,
        store=store,
        runtime_dir=runtime,
        vault_dir=vault,
        documents_dir=documents,
        rag_dir=tmp_path / "rag",
        wiki_dir=tmp_path / "wiki",
    )

    assert record.status == "success"
    assert record.files_seen == 1
    assert record.files_moved == 1
    assert record.files_indexed == 1
    assert record.wiki_update_marked is True
    assert (runtime / "wiki" / "needs-update.flag").exists()
    assert store.get_run(record.id).file_results[0].wiki_relevant is True
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest skills/ingest/augur/tests/test_inbox_consume.py -q
```

Expected: FAIL with missing `inbox_consume`.

- [ ] **Step 3: Implement consume orchestration**

Create `skills/ingest/scripts/inbox_consume.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from skills.ingest.scripts.inbox_models import InboxFileResult, InboxFolder, InboxInsight, InboxRunRecord
from skills.ingest.scripts.inbox_store import InboxStore
from skills.ingest.scripts.renamer import normalize_filename
from skills.rag.scripts.document_understanding import understand_document

DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".md", ".txt", ".csv"}
TRASH_EXTENSIONS = {".tmp", ".download", ".part", ".crdownload"}


def scan_folder(folder: Path) -> dict[str, object]:
    paths = [path for path in Path(folder).iterdir() if path.is_file() and not path.name.startswith(".")]
    document_candidates = [path for path in paths if path.suffix.lower() in DOCUMENT_EXTENSIONS]
    trash_candidates = [path for path in paths if path.suffix.lower() in TRASH_EXTENSIONS]
    return {
        "path": str(Path(folder).resolve(strict=False)),
        "counts": {
            "new_files": len(paths),
            "document_candidates": len(document_candidates),
            "trash_candidates": len(trash_candidates),
            "failed": 0,
        },
        "files": [str(path) for path in paths],
    }


def consume_folder(
    folder: InboxFolder,
    *,
    store: InboxStore,
    runtime_dir: Path,
    vault_dir: Path,
    documents_dir: Path,
    rag_dir: Path,
    wiki_dir: Path,
) -> InboxRunRecord:
    started = datetime.now(tz=UTC).isoformat()
    source_paths = [
        path for path in Path(folder.path).iterdir()
        if path.is_file() and not path.name.startswith(".") and path.suffix.lower() in DOCUMENT_EXTENSIONS
    ]
    file_results: list[InboxFileResult] = []
    files_moved = 0
    files_indexed = 0

    for source_path in source_paths:
        try:
            understanding = understand_document(source_path)
            final_path = _route_file(source_path, vault_dir=vault_dir, documents_dir=documents_dir)
            files_moved += 1
            rag_indexed = _reindex_documents(documents_dir, rag_dir=rag_dir)
            files_indexed += 1 if rag_indexed else 0
            file_results.append(
                InboxFileResult(
                    source_path=str(source_path),
                    final_path=str(final_path),
                    content_type=source_path.suffix.lower().lstrip(".") or "file",
                    document_kind=str(understanding.get("document_kind") or "document"),
                    extraction_method=str(understanding.get("extraction_method") or "unknown"),
                    extraction_confidence=str(understanding.get("extraction_confidence") or "low"),
                    ocr_applied=bool(understanding.get("ocr_applied")),
                    llm_assisted=bool(understanding.get("llm_assisted")),
                    route=final_path.parent.name,
                    renamed_to=final_path.name,
                    rag_indexed=rag_indexed,
                    wiki_relevant=bool(str(understanding.get("body") or "").strip()),
                    status="success",
                )
            )
        except Exception as exc:
            file_results.append(
                InboxFileResult(
                    source_path=str(source_path),
                    status="failed",
                    stage="consume",
                    error=str(exc),
                )
            )

    flag_path = _mark_wiki_update(runtime_dir)
    failed = sum(1 for result in file_results if result.status == "failed")
    moved_or_indexed = files_moved + files_indexed
    status = "success" if failed == 0 else "partial_success" if moved_or_indexed else "failed"
    record = InboxRunRecord(
        id=f"run_{uuid4().hex[:12]}",
        folder_id=folder.id,
        started_at=started,
        completed_at=datetime.now(tz=UTC).isoformat(),
        status=status,
        files_seen=len(source_paths),
        files_moved=files_moved,
        files_indexed=files_indexed,
        files_skipped=0,
        files_failed=failed,
        wiki_update_marked=flag_path.exists(),
        wiki_batch_created=False,
        insights=_build_run_insights(file_results),
        file_results=file_results,
    )
    return store.save_run(record)


def _route_file(path: Path, *, vault_dir: Path, documents_dir: Path) -> Path:
    destination_dir = documents_dir / "inbox"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / normalize_filename(path.name)
    destination.write_bytes(path.read_bytes())
    return destination


def _reindex_documents(documents_dir: Path, *, rag_dir: Path) -> bool:
    from skills.rag.scripts.unified_indexer import index_documents

    index_documents(documents_dir, rag_dir)
    return True


def _mark_wiki_update(runtime_dir: Path) -> Path:
    flag = Path(runtime_dir) / "wiki" / "needs-update.flag"
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text(datetime.now(tz=UTC).isoformat(), encoding="utf-8")
    return flag


def _build_run_insights(file_results: list[InboxFileResult]) -> list[InboxInsight]:
    wiki_sources = [Path(result.final_path).name for result in file_results if result.final_path and result.wiki_relevant]
    if not wiki_sources:
        return []
    return [
        InboxInsight(
            title="New files are ready for wiki compounding",
            summary=f"{len(wiki_sources)} routed files contain text that can strengthen the wiki.",
            sources=wiki_sources[:5],
            next_actions=["Run Wiki Update from Brain Insights"],
        )
    ]
```

- [ ] **Step 4: Run consume tests**

Run:

```bash
pytest skills/ingest/augur/tests/test_inbox_consume.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add skills/ingest/scripts/inbox_consume.py skills/ingest/augur/tests/test_inbox_consume.py
git commit -m "feat(inbox): add consume run pipeline"
```

Expected: focused consume pipeline commit.

---

### Task 6: Inbox MCP Tools And Skill Contract

**Files:**
- Modify: `skills/ingest/scripts/mcp/ingest_tools.py`
- Modify: `skills/ingest/SKILL.md`
- Create: `skills/ingest/augur/tests/test_inbox_mcp_tools.py`

- [ ] **Step 1: Write failing MCP registration tests**

Create `skills/ingest/augur/tests/test_inbox_mcp_tools.py`:

```python
from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, *, name: str, annotations: dict | None = None):  # noqa: ARG002
        def decorator(fn):
            self.tools[name] = fn
            return fn
        return decorator


class _FakeMetrics:
    def track_tool(self, *_args, **_kwargs) -> None:
        pass


def test_register_ingest_tools_exposes_inbox_tools() -> None:
    from skills.ingest.scripts.mcp.ingest_tools import register_ingest_tools

    fake_mcp = _FakeMCP()
    register_ingest_tools(fake_mcp, lambda fn: fn, _FakeMetrics())

    for name in (
        "inbox-folders",
        "inbox-scan-folder",
        "inbox-consume-folder",
        "inbox-purge-folder",
        "inbox-run-history",
        "inbox-run-detail",
        "brain-insights",
    ):
        assert name in fake_mcp.tools

    assert "action" in inspect.signature(fake_mcp.tools["inbox-folders"]).parameters
    assert "folder_id" in inspect.signature(fake_mcp.tools["inbox-consume-folder"]).parameters


def test_inbox_folders_add_and_list(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts.mcp import ingest_tools

    monkeypatch.setattr(ingest_tools, "get_runtime_dir", lambda: tmp_path / "runtime", raising=False)

    fake_mcp = _FakeMCP()
    ingest_tools.register_ingest_tools(fake_mcp, lambda fn: fn, _FakeMetrics())
    target = tmp_path / "Downloads"
    target.mkdir()

    added = json.loads(asyncio.run(fake_mcp.tools"inbox-folders")))
    listed = json.loads(asyncio.run(fake_mcp.tools"inbox-folders"))

    assert added["success"] is True
    assert added["folder"]["id"] == "downloads"
    assert listed["success"] is True
    assert listed["folders"][0]["name"] == "Downloads"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest skills/ingest/augur/tests/test_inbox_mcp_tools.py -q
```

Expected: FAIL because tools are not registered.

- [ ] **Step 3: Add store helper in MCP module**

Modify `skills/ingest/scripts/mcp/ingest_tools.py` near `_get_config_path`:

```python
def _get_inbox_store():
    from skills.ingest.scripts.inbox_store import InboxStore

    return InboxStore(get_runtime_dir() / "brain" / "inbox")
```

- [ ] **Step 4: Register inbox tools**

Add these tool handlers inside `register_ingest_tools` after `ingest-config` and before ambient import tools:

```python
    @mcp.tool(name="inbox-folders", annotations=tool_annotations({"title": "Inbox Folders", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True}))
    @mcp_tool_interceptor
    async def inbox_folders(action: str = "list", folder_id: str = "", name: str = "", path: str = "") -> str:
        metrics.track_tool("inbox_folders", skill="ingest")
        try:
            store = _get_inbox_store()
            if action == "add":
                if not path:
                    return json.dumps({"success": False, "error": "path is required"})
                folder = store.add_folder(name=name or Path(path).name, path=path)
                return json.dumps({"success": True, "folder": folder}, default=lambda value: value.__dict__, indent=2)
            folders = store.list_folders()
            return json.dumps({"success": True, "folders": folders}, default=lambda value: value.__dict__, indent=2)
        except Exception as exc:
            logger.error("inbox-folders failed: %s", exc, exc_info=True)
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(name="inbox-scan-folder", annotations=tool_annotations({"title": "Inbox Scan Folder", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}))
    @mcp_tool_interceptor
    async def inbox_scan_folder(folder_id: str = "") -> str:
        metrics.track_tool("inbox_scan_folder", skill="ingest")
        try:
            from skills.ingest.scripts.inbox_consume import scan_folder

            store = _get_inbox_store()
            folder = next(item for item in store.list_folders() if item.id == folder_id)
            result = scan_folder(Path(folder.path))
            store.update_folder_counts(folder.id, result["counts"])
            return json.dumps({"success": True, **result}, indent=2, default=str)
        except Exception as exc:
            logger.error("inbox-scan-folder failed: %s", exc, exc_info=True)
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(name="inbox-consume-folder", annotations=tool_annotations({"title": "Inbox Consume Folder", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True}))
    @mcp_tool_interceptor
    async def inbox_consume_folder(folder_id: str = "") -> str:
        metrics.track_tool("inbox_consume_folder", skill="ingest")
        try:
            from skills.ingest.scripts.inbox_consume import consume_folder

            paths = _get_ambient_import_paths()
            store = _get_inbox_store()
            folder = next(item for item in store.list_folders() if item.id == folder_id)
            record = consume_folder(
                folder,
                store=store,
                runtime_dir=paths["runtime_dir"],
                vault_dir=paths["vault_dir"],
                documents_dir=paths["documents_dir"],
                rag_dir=paths["rag_dir"],
                wiki_dir=paths["wiki_dir"],
            )
            return json.dumps({"success": True, "run": record}, default=lambda value: value.__dict__, indent=2)
        except Exception as exc:
            logger.error("inbox-consume-folder failed: %s", exc, exc_info=True)
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(name="inbox-run-history", annotations=tool_annotations({"title": "Inbox Run History", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def inbox_run_history(folder_id: str = "") -> str:
        metrics.track_tool("inbox_run_history", skill="ingest")
        try:
            runs = _get_inbox_store().list_runs(folder_id=folder_id or None)
            return json.dumps({"success": True, "runs": runs}, default=lambda value: value.__dict__, indent=2)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(name="inbox-run-detail", annotations=tool_annotations({"title": "Inbox Run Detail", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def inbox_run_detail(run_id: str = "") -> str:
        metrics.track_tool("inbox_run_detail", skill="ingest")
        try:
            return json.dumps({"success": True, "run": _get_inbox_store().get_run(run_id)}, default=lambda value: value.__dict__, indent=2)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(name="brain-insights", annotations=tool_annotations({"title": "Brain Insights", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def brain_insights() -> str:
        metrics.track_tool("brain_insights", skill="ingest")
        try:
            from skills.ingest.scripts.ask_sync import load_recent_ask_outcomes
            from skills.ingest.scripts.ask_sync_clusters import cluster_ask_outcomes
            from skills.ingest.scripts.wiki_status import build_wiki_status

            store = _get_inbox_store()
            runs = store.list_runs()
            ask_outcomes = load_recent_ask_outcomes(days_back=14, limit=10)
            return json.dumps({
                "success": True,
                "latest_runs": runs[:5],
                "wiki_status": build_wiki_status(),
                "retained_ask_outcomes": ask_outcomes,
                "retained_ask_clusters": cluster_ask_outcomes(ask_outcomes),
            }, default=lambda value: value.__dict__, indent=2)
        except Exception as exc:
            logger.error("brain-insights failed: %s", exc, exc_info=True)
            return json.dumps({"success": False, "error": str(exc)})
```

Add `inbox-purge-folder` in the same block:

```python
    @mcp.tool(name="inbox-purge-folder", annotations=tool_annotations({"title": "Inbox Purge Folder", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True}))
    @mcp_tool_interceptor
    async def inbox_purge_folder(folder_id: str = "") -> str:
        metrics.track_tool("inbox_purge_folder", skill="ingest")
        try:
            from skills.ingest.scripts.inbox_trash import move_to_trash, plan_purge

            store = _get_inbox_store()
            folder = next(item for item in store.list_folders() if item.id == folder_id)
            paths = [path for path in Path(folder.path).iterdir() if path.is_file()]
            plan = plan_purge(paths)
            results = [move_to_trash(item.path) for item in plan.to_trash]
            return json.dumps({
                "success": all(bool(item.get("success")) for item in results),
                "trashed": results,
                "skipped": [{"path": str(item.path), "reason": item.reason} for item in plan.skipped],
            }, indent=2)
        except Exception as exc:
            logger.error("inbox-purge-folder failed: %s", exc, exc_info=True)
            return json.dumps({"success": False, "error": str(exc)})
```

- [ ] **Step 5: Update skill MCP tool list**

Modify `skills/ingest/SKILL.md` frontmatter and add:

```yaml
- inbox-folders
- inbox-scan-folder
- inbox-consume-folder
- inbox-purge-folder
- inbox-run-history
- inbox-run-detail
- brain-insights
```

Add rows to the MCP Tools table for the same tools with concise descriptions.

- [ ] **Step 6: Run inbox MCP tests**

Run:

```bash
pytest skills/ingest/augur/tests/test_inbox_mcp_tools.py skills/ingest/augur/tests/test_ingest_tools.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add skills/ingest/scripts/mcp/ingest_tools.py skills/ingest/SKILL.md skills/ingest/augur/tests/test_inbox_mcp_tools.py
git commit -m "feat(inbox): expose folder workflow mcp tools"
```

Expected: focused MCP contract commit.

---

### Task 7: Brain Inbox Dashboard Page

**Files:**
- Create: `apps/dashboard/features/pages/brain/inbox/types.ts`
- Create: `apps/dashboard/features/pages/brain/inbox/hooks.ts`
- Create: `apps/dashboard/features/pages/brain/inbox/page.tsx`
- Create: `apps/dashboard/features/pages/brain/inbox/page.test.tsx`

- [ ] **Step 1: Write page test**

Create `apps/dashboard/features/pages/brain/inbox/page.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import InboxPage from "./page";

jest.mock("@/lib/mcp/useMcpQuery", () => ({
  useMcpQuery: () => ({
    data: {
      success: true,
      folders: [
        {
          id: "downloads",
          name: "Downloads",
          path: "/Users/example/Downloads",
          enabled: true,
          counts: { new_files: 3, document_candidates: 2, trash_candidates: 1, failed: 0 },
        },
      ],
    },
    loading: false,
    error: null,
    refetch: jest.fn(),
  }),
}));

const mcpCall = jest.fn(async () => ({ success: true }));
jest.mock("@/lib/mcp/client", () => ({ mcpCall: (...args: unknown[]) => mcpCall(...args) }));

describe("Brain Inbox page", () => {
  it("renders watched folders and consume action", async () => {
    render(<InboxPage />);

    expect(screen.getByText("Brain Inbox")).toBeInTheDocument();
    expect(screen.getByText("Downloads")).toBeInTheDocument();
    expect(screen.getByText("3 new")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /consume downloads/i }));
    expect(mcpCall).toHaveBeenCalledWith("inbox-consume-folder", { folder_id: "downloads" });
  });
});
```

- [ ] **Step 2: Run page test to verify failure**

Run:

```bash
cd apps/dashboard && pnpm test -- features/pages/brain/inbox/page.test.tsx
```

Expected: FAIL because page files do not exist.

- [ ] **Step 3: Create types**

Create `apps/dashboard/features/pages/brain/inbox/types.ts`:

```ts
export interface InboxFolderCounts {
  new_files: number;
  document_candidates: number;
  trash_candidates: number;
  failed: number;
}

export interface InboxFolder {
  id: string;
  name: string;
  path: string;
  enabled: boolean;
  counts?: InboxFolderCounts;
  last_scan_at?: string | null;
  last_consume_run_id?: string | null;
  last_purge_run_id?: string | null;
}

export interface InboxFoldersPayload {
  success: boolean;
  folders: InboxFolder[];
  error?: string;
}
```

- [ ] **Step 4: Create hook**

Create `apps/dashboard/features/pages/brain/inbox/hooks.ts`:

```ts
"use client";

import { useMcpQuery } from "@/lib/mcp/useMcpQuery";
import type { InboxFoldersPayload } from "./types";

export function useInboxFolders() {
  return useMcpQuery<InboxFoldersPayload>("brain-inbox-folders", "inbox-folders", "user-data", {
    args: { action: "list" },
    fallback: { success: true, folders: [] },
  });
}
```

- [ ] **Step 5: Create Inbox page**

Create `apps/dashboard/features/pages/brain/inbox/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { FolderOpen, RefreshCw, Trash2, UploadCloud } from "lucide-react";
import { mcpCall } from "@/lib/mcp/client";
import { useInboxFolders } from "./hooks";

export default function InboxPage() {
  const { data, loading, error, refetch } = useInboxFolders();
  const [runningFolderId, setRunningFolderId] = useState<string | null>(null);

  const runConsume = async (folderId: string) => {
    setRunningFolderId(folderId);
    try {
      await mcpCall("inbox-consume-folder", { folder_id: folderId });
      refetch();
    } finally {
      setRunningFolderId(null);
    }
  };

  const runPurge = async (folderId: string) => {
    setRunningFolderId(folderId);
    try {
      await mcpCall("inbox-purge-folder", { folder_id: folderId });
      refetch();
    } finally {
      setRunningFolderId(null);
    }
  };

  const folders = data?.folders ?? [];

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Brain Inbox</h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Add local folders, consume documents into Augur, and keep the wiki/search layer current.
          </p>
        </div>
        <button className="inline-flex min-h-[44px] items-center gap-2 rounded-lg border border-[var(--accent-primary)]/30 bg-[var(--accent-primary)]/10 px-3 text-sm font-medium text-[var(--accent-primary)]">
          <UploadCloud className="h-4 w-4" aria-hidden="true" />
          Add Folder
        </button>
      </header>

      {error && <div role="alert" className="rounded-lg border border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 p-4 text-sm">{error}</div>}

      <section className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-[var(--text-primary)]">Watched Folders</h2>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">Consume moves useful files into Augur; Purge sends disposable files to Trash.</p>
          </div>
          <button onClick={() => refetch()} className="inline-flex min-h-[44px] items-center gap-2 rounded-lg border border-[var(--border-color)] px-3 text-sm text-[var(--text-secondary)]">
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </button>
        </div>

        <div className="mt-5 space-y-3">
          {loading ? (
            <div className="rounded-lg border border-[var(--border-color)] p-4 text-sm text-[var(--text-secondary)]">Loading folders...</div>
          ) : folders.length === 0 ? (
            <div className="rounded-lg border border-dashed border-[var(--border-color)] p-6 text-sm text-[var(--text-secondary)]">No folders added yet.</div>
          ) : folders.map((folder) => {
            const counts = folder.counts ?? { new_files: 0, document_candidates: 0, trash_candidates: 0, failed: 0 };
            const running = runningFolderId === folder.id;
            return (
              <article key={folder.id} className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <FolderOpen className="h-4 w-4 text-[var(--accent-primary)]" aria-hidden="true" />
                      <h3 className="text-sm font-semibold text-[var(--text-primary)]">{folder.name}</h3>
                    </div>
                    <p className="mt-1 truncate text-xs text-[var(--text-muted)]">{folder.path}</p>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs">
                      <span className="rounded-full bg-[var(--accent-primary)]/10 px-2 py-1 text-[var(--accent-primary)]">{counts.new_files} new</span>
                      <span className="rounded-full bg-emerald-500/10 px-2 py-1 text-emerald-300">{counts.document_candidates} documents</span>
                      <span className="rounded-full bg-amber-500/10 px-2 py-1 text-amber-300">{counts.trash_candidates} trash candidates</span>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      aria-label={`Consume ${folder.name}`}
                      disabled={running}
                      onClick={() => void runConsume(folder.id)}
                      className="inline-flex min-h-[44px] items-center gap-2 rounded-lg border border-cyan-500/25 bg-cyan-500/10 px-3 text-sm font-medium text-cyan-300 disabled:opacity-50"
                    >
                      <RefreshCw className={`h-4 w-4 ${running ? "animate-spin" : ""}`} aria-hidden="true" />
                      Consume
                    </button>
                    <button
                      aria-label={`Purge ${folder.name} to Trash`}
                      disabled={running}
                      onClick={() => void runPurge(folder.id)}
                      className="inline-flex min-h-[44px] items-center gap-2 rounded-lg border border-rose-500/25 bg-rose-500/10 px-3 text-sm font-medium text-rose-300 disabled:opacity-50"
                    >
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                      Purge to Trash
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 6: Run page test**

Run:

```bash
cd apps/dashboard && pnpm test -- features/pages/brain/inbox/page.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add apps/dashboard/features/pages/brain/inbox
git commit -m "feat(dashboard): add brain inbox page"
```

Expected: focused page commit.

---

### Task 8: Brain Insights Dashboard Page And Overview Routing

**Files:**
- Create: `apps/dashboard/features/pages/brain/insights/types.ts`
- Create: `apps/dashboard/features/pages/brain/insights/hooks.ts`
- Create: `apps/dashboard/features/pages/brain/insights/page.tsx`
- Create: `apps/dashboard/features/pages/brain/insights/page.test.tsx`
- Modify: `apps/dashboard/features/pages/brain/overview/BrainOverviewHome.tsx`

- [ ] **Step 1: Write Insights page test**

Create `apps/dashboard/features/pages/brain/insights/page.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import InsightsPage from "./page";

jest.mock("@/lib/mcp/useMcpQuery", () => ({
  useMcpQuery: () => ({
    data: {
      success: true,
      latest_runs: [{ id: "run_1", status: "success", insights: [{ title: "Health paperwork grouped", summary: "Two files support one claim.", sources: [], next_actions: ["Review receipt"] }] }],
      wiki_status: { verdict: "structure_ok_compile_backlog", actions: [{ id: "prepare-incremental-batch", reason: "needs update" }] },
      retained_ask_outcomes: [{ question: "What did I learn?", summary: "Keep reimbursements together." }],
      retained_ask_clusters: [],
    },
    loading: false,
    error: null,
    refetch: jest.fn(),
  }),
}));

describe("Brain Insights page", () => {
  it("renders wiki status, insights, and next actions", () => {
    render(<InsightsPage />);

    expect(screen.getByText("Brain Insights")).toBeInTheDocument();
    expect(screen.getByText("Health paperwork grouped")).toBeInTheDocument();
    expect(screen.getByText("Review receipt")).toBeInTheDocument();
    expect(screen.getByText("structure_ok_compile_backlog")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd apps/dashboard && pnpm test -- features/pages/brain/insights/page.test.tsx
```

Expected: FAIL because files do not exist.

- [ ] **Step 3: Create Insights types and hook**

Create `apps/dashboard/features/pages/brain/insights/types.ts`:

```ts
export interface BrainInsight {
  title: string;
  summary: string;
  sources?: string[];
  next_actions?: string[];
}

export interface BrainInsightRun {
  id: string;
  status: string;
  insights?: BrainInsight[];
}

export interface BrainInsightsPayload {
  success: boolean;
  latest_runs: BrainInsightRun[];
  wiki_status: {
    verdict?: string;
    healthy?: boolean;
    actions?: { id: string; reason: string }[];
  };
  retained_ask_outcomes: { question?: string; summary?: string }[];
  retained_ask_clusters: unknown[];
  error?: string;
}
```

Create `apps/dashboard/features/pages/brain/insights/hooks.ts`:

```ts
"use client";

import { useMcpQuery } from "@/lib/mcp/useMcpQuery";
import type { BrainInsightsPayload } from "./types";

export function useBrainInsights() {
  return useMcpQuery<BrainInsightsPayload>("brain-insights", "brain-insights", "user-data", {
    fallback: {
      success: true,
      latest_runs: [],
      wiki_status: {},
      retained_ask_outcomes: [],
      retained_ask_clusters: [],
    },
  });
}
```

- [ ] **Step 4: Create Insights page**

Create `apps/dashboard/features/pages/brain/insights/page.tsx`:

```tsx
"use client";

import { BookOpenText, CheckCircle2, Lightbulb, RefreshCw } from "lucide-react";
import { mcpCall } from "@/lib/mcp/client";
import { useBrainInsights } from "./hooks";

export default function InsightsPage() {
  const { data, loading, error, refetch } = useBrainInsights();
  const latestInsights = (data?.latest_runs ?? []).flatMap((run) => run.insights ?? []);
  const nextActions = latestInsights.flatMap((insight) => insight.next_actions ?? []);
  const wikiActions = data?.wiki_status?.actions ?? [];

  const runWikiUpdate = async () => {
    await mcpCall("wiki-update", { limit: 20 });
    refetch();
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Brain Insights</h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Cross-source learning, pending wiki compounding, and practical next actions.
          </p>
        </div>
        <button onClick={runWikiUpdate} className="inline-flex min-h-[44px] items-center gap-2 rounded-lg border border-cyan-500/25 bg-cyan-500/10 px-3 text-sm font-medium text-cyan-300">
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Run Wiki Update
        </button>
      </header>

      {error && <div role="alert" className="rounded-lg border border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 p-4 text-sm">{error}</div>}

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-5">
          <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
            <BookOpenText className="h-4 w-4 text-cyan-300" aria-hidden="true" />
            Wiki Status
          </div>
          <div className="mt-2 text-xl font-semibold text-[var(--text-primary)]">{data?.wiki_status?.verdict ?? "unknown"}</div>
          <p className="mt-2 text-xs text-[var(--text-muted)]">{wikiActions[0]?.reason ?? "No wiki action currently recommended."}</p>
        </div>
        <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-5">
          <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
            <Lightbulb className="h-4 w-4 text-amber-300" aria-hidden="true" />
            Insights
          </div>
          <div className="mt-2 text-xl font-semibold text-[var(--text-primary)]">{latestInsights.length}</div>
          <p className="mt-2 text-xs text-[var(--text-muted)]">New or recent cross-source observations.</p>
        </div>
        <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-5">
          <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
            <CheckCircle2 className="h-4 w-4 text-emerald-300" aria-hidden="true" />
            Next Actions
          </div>
          <div className="mt-2 text-xl font-semibold text-[var(--text-primary)]">{nextActions.length}</div>
          <p className="mt-2 text-xs text-[var(--text-muted)]">Actions extracted from consumed files and retained chats.</p>
        </div>
      </section>

      <section className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-5">
        <h2 className="text-base font-semibold text-[var(--text-primary)]">Latest Insights</h2>
        <div className="mt-4 space-y-3">
          {loading ? <p className="text-sm text-[var(--text-secondary)]">Loading insights...</p> : latestInsights.length === 0 ? (
            <p className="text-sm text-[var(--text-secondary)]">No insights yet. Consume a folder or run wiki update.</p>
          ) : latestInsights.map((insight) => (
            <article key={insight.title} className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">{insight.title}</h3>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">{insight.summary}</p>
              {(insight.next_actions ?? []).length > 0 && (
                <ul className="mt-3 space-y-1 text-sm text-[var(--text-primary)]">
                  {insight.next_actions?.map((action) => <li key={action}>{action}</li>)}
                </ul>
              )}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 5: Update Brain overview routing**

Modify `apps/dashboard/features/pages/brain/overview/BrainOverviewHome.tsx`:

- Import `Inbox` from `lucide-react`.
- Add an action card with `href: "/brain/inbox"` when folder signals exist or always as the first open-source starting point.
- Change wiki quality `href` from `/brain/memory` to `/brain/insights`.

Use this card object inside `needsAttention`:

```ts
    {
      key: 'brain-inbox',
      visible: true,
      title: 'Brain Inbox',
      summary: 'Consume local folders into Augur',
      detail: 'Add Desktop, Downloads, or another folder and turn files into organized knowledge.',
      href: '/brain/inbox',
      icon: Inbox,
      accentClass: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-400',
    },
```

- [ ] **Step 6: Run Insights test**

Run:

```bash
cd apps/dashboard && pnpm test -- features/pages/brain/insights/page.test.tsx features/pages/brain/inbox/page.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add apps/dashboard/features/pages/brain/insights apps/dashboard/features/pages/brain/overview/BrainOverviewHome.tsx
git commit -m "feat(dashboard): add brain insights page"
```

Expected: focused Brain Insights commit.

---

### Task 9: Browse Wiki Card Hardening

**Files:**
- Modify: `apps/dashboard/lib/browse/transforms.ts`
- Modify: `apps/dashboard/components/shared/BrowseCard.tsx`
- Modify: `apps/dashboard/app/(views)/browse/page.tsx`
- Create or modify: `apps/dashboard/components/shared/BrowseCard.test.tsx`

- [ ] **Step 1: Add transform/card tests**

Create `apps/dashboard/components/shared/BrowseCard.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { BrowseCard } from "./BrowseCard";

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}));

describe("BrowseCard wiki rendering", () => {
  it("shows cleaned wiki tags and overflow actions", () => {
    render(
      <BrowseCard
        item={{
          id: "concepts/reimbursements",
          title: "Health Reimbursements",
          description: "Compiled concept page",
          hub: "brain",
          icon: "NotebookTabs",
          typeBadge: "concept",
          path: "/wiki/concepts/reimbursements.md",
          metadata: {
            pageType: "concept",
            pageTags: "health,finance",
            sourceCount: "4",
            qualityScore: "82",
          },
          primaryAction: { label: "Open", type: "open-file", target: "/wiki/concepts/reimbursements.md" },
          actions: [{ id: "rewrite", label: "Run Rewrite", icon: "Sparkles", type: "run-mcp", target: "wiki-rewrite:concepts/reimbursements" }],
        }}
      />
    );

    expect(screen.getByText("health")).toBeInTheDocument();
    expect(screen.getByText("finance")).toBeInTheDocument();
    expect(screen.getByText("4 sources")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd apps/dashboard && pnpm test -- components/shared/BrowseCard.test.tsx
```

Expected: FAIL because source count badge is not rendered.

- [ ] **Step 3: Add wiki metadata in transforms**

Modify wiki branch in `apps/dashboard/lib/browse/transforms.ts` so wiki metadata includes source count and quality score when present:

```ts
    case "wiki": {
      const pageKind = wikiPageKind(entry, itemId);
      const pageTags = displayWikiTags(entry, itemId);
      enrichedMeta.pageType = pageKind;
      copyMeta(enrichedMeta, "sourceCount", entry.source_count ?? entry.metadata?.source_count);
      copyMeta(enrichedMeta, "qualityScore", entry.quality_score ?? entry.metadata?.quality_score);
      if (pageTags.length > 0) {
        enrichedMeta.pageTags = pageTags.join(",");
      }
      break;
    }
```

In the primary action selection for wiki items, set:

```ts
      primaryAction = {
        label: entry.metadata?.quality_score && Number(entry.metadata.quality_score) < 75 ? "Review" : "Open",
        type: "open-file",
        target: entry.source_path || "",
      };
      actions = [
        { id: `copy-${entryId}`, label: "Copy Path", icon: "Copy", type: "copy", target: entry.source_path || itemId },
        { id: `rewrite-${entryId}`, label: "Run Rewrite", icon: "Sparkles", type: "run-mcp", target: `wiki-rewrite:${itemId}` },
        { id: `reindex-${entryId}`, label: "Reindex Wiki", icon: "RefreshCw", type: "run-mcp", target: "wiki-reindex" },
      ];
      break;
```

- [ ] **Step 4: Render source count badge**

Modify `collectBadges` in `apps/dashboard/components/shared/BrowseCard.tsx`:

```tsx
  if (isWikiPageItem(item) && m?.sourceCount) {
    badges.push({ key: "wiki-source-count", node: (
      <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--bg-secondary)] text-[var(--text-muted)] border border-[var(--border-color)]">
        {m.sourceCount} {m.sourceCount === "1" ? "source" : "sources"}
      </span>
    )});
  }
```

- [ ] **Step 5: Update Browse wiki description**

Modify `CATEGORY_DESCRIPTIONS` in `apps/dashboard/app/(views)/browse/page.tsx`:

```ts
wiki: "Compiled concept pages and reusable answers from Augur knowledge sources",
```

- [ ] **Step 6: Run Browse card test**

Run:

```bash
cd apps/dashboard && pnpm test -- components/shared/BrowseCard.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add apps/dashboard/lib/browse/transforms.ts apps/dashboard/components/shared/BrowseCard.tsx apps/dashboard/app/'(views)'/browse/page.tsx apps/dashboard/components/shared/BrowseCard.test.tsx
git commit -m "feat(browse): harden wiki cards"
```

Expected: focused Browse hardening commit.

---

### Task 10: Mount Brain Pages And Full Verification

**Files:**
- Generated files as produced by dashboard scripts
- No manual edits to generated app copies

- [ ] **Step 1: Mount plugins and tabs**

Run:

```bash
cd apps/dashboard
pnpm run build:scripts
pnpm run mount-plugins
```

Expected: mount output completes without orphan routes. Do not edit files under `apps/dashboard/app/brain/...` manually if they are generated copies.

- [ ] **Step 2: Run backend tests**

Run:

```bash
pytest \
  skills/ingest/augur/tests/test_inbox_store.py \
  skills/ingest/augur/tests/test_inbox_trash.py \
  skills/ingest/augur/tests/test_inbox_consume.py \
  skills/ingest/augur/tests/test_inbox_mcp_tools.py \
  skills/ingest/augur/tests/test_ingest_tools.py \
  skills/rag/augur/tests/test_binary_extractor.py \
  -q
```

Expected: all selected backend tests pass.

- [ ] **Step 3: Run dashboard tests and typecheck**

Run:

```bash
cd apps/dashboard
pnpm test -- features/pages/brain/inbox/page.test.tsx features/pages/brain/insights/page.test.tsx components/shared/BrowseCard.test.tsx
pnpm run typecheck
```

Expected: Jest tests pass and `tsc --noEmit` exits 0.

- [ ] **Step 4: Build dashboard**

Run:

```bash
cd apps/dashboard
pnpm run build
```

Expected: production build succeeds.

- [ ] **Step 5: Start dashboard for browser verification**

Run:

```bash
cd apps/dashboard
pnpm run dev
```

Expected: dev server URL is printed. Use that port for the browser checks.

- [ ] **Step 6: Browser verify desktop routes**

Open the dashboard in a real browser and verify:

```text
/brain/inbox
/brain/insights
/brain
/browse?category=wiki
```

Expected:

- `/brain/inbox` shows real folder state or a useful empty state.
- `/brain/insights` shows wiki status and retained/file signal sections.
- `/brain` links to Inbox and Insights.
- `/browse?category=wiki` uses the corrected category description and hardened wiki cards.
- no visible console errors.
- every visible button either produces useful work or a clear error.

- [ ] **Step 7: Browser verify mobile width**

Set viewport to mobile width and re-check:

```text
/brain/inbox
/brain/insights
```

Expected: no text overlap, no clipped buttons, folder cards and insight cards stack cleanly.

- [ ] **Step 8: Final git status**

Run:

```bash
git status --short --branch
git log --oneline origin/main..HEAD
```

Expected: only intentional changes are present and commits are listed in task order.

- [ ] **Step 9: Commit generated registry changes if any**

If `pnpm run mount-plugins` changed tracked generated registry files, inspect them and commit only relevant generated files. The expected generated paths for this feature are:

```text
apps/dashboard/lib/tabs/generated-registry.ts
apps/dashboard/lib/plugin-runtime/assembled-hubs.json
apps/dashboard/app/brain/[[...slug]]/registry.ts
config/dashboard/page_manifest.lock
```

Run:

```bash
git diff -- apps/dashboard/app apps/dashboard/lib config/dashboard
git add \
  apps/dashboard/lib/tabs/generated-registry.ts \
  apps/dashboard/lib/plugin-runtime/assembled-hubs.json \
  'apps/dashboard/app/brain/[[...slug]]/registry.ts' \
  config/dashboard/page_manifest.lock
git commit -m "chore(dashboard): refresh brain inbox registries"
```

Expected: no unrelated generated churn is included.

---

## Plan Self-Review

### Spec Coverage

- Folder registry: Task 2 and Task 6.
- Consume pipeline: Task 5 and Task 6.
- Purge to Trash: Task 3 and Task 6.
- Deep file understanding: Task 4.
- Wiki and interaction compounding signals: Task 5, Task 6, Task 8.
- Brain Inbox UI: Task 7.
- Brain Insights UI: Task 8.
- Brain Overview routing: Task 8.
- Browse wiki hardening: Task 9.
- MCP-first dashboard rule: Task 6, Task 7, Task 8, Task 10.
- Verification: Task 10.

### Known Implementation Notes

- The code snippets in Tasks 2-9 are intentionally minimal first passes. Workers should keep them aligned with existing project style while preserving the tested behavior.
- If a helper already exists with equivalent behavior, reuse it and adjust the test import path only when the resulting boundary remains as explicit as the plan states.
- If the external ADR repository is separate from the Augur repo, keep its commit separate and report both commit hashes.
