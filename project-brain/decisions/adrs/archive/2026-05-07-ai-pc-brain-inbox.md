# AI PC Brain Inbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the local-first AI PC Brain Inbox demo: Desktop files and MP3 recordings are consumed, understood locally first, routed into the brain, indexed in RAG, and shown in Brain Inbox/Insights with airplane-mode policy enforced.

**Architecture:** Add a focused `ingest` skill backend for inbox state, scan, consume, source cards, and Brain Insights. Extend the existing document-extractor capability surface so OCR/transcription/local-agent/cloud policy decisions are visible and testable. Keep dashboard code MCP-first by wiring existing Brain pages to real tool data and richer run/file status.

**Tech Stack:** Python 3.11/3.12, FastMCP skill tools, pytest, MarkItDown, PyMuPDF, optional OpenVINO/OpenVINO GenAI, optional Tesseract/pdf2image/ffmpeg, Ollama local models, YAML frontmatter helpers, unified RAG indexer, Next.js/React/TypeScript/Jest, Playwright/browser verification.

---

## Scope Check

This plan is one product slice with coupled backend and dashboard work. The first usable checkpoint is a manual Desktop **Consume** workflow, not a daemon watcher. Background watching and broad format perfection stay out of the first pass.

The plan preserves Augur's existing boundaries:

- runtime state under `get_runtime_dir()`
- user-facing source cards under `get_vault_dir()`
- central indexes under `get_rag_dir()`
- backend workflow in a skill MCP surface
- dashboard calls through `mcpCall` / `useMcpQuery`

## File Structure

### New Backend Files

- Create `skills/ingest/SKILL.md`: skill metadata and MCP tool declarations for the Brain Inbox backend.
- Create `skills/ingest/scripts/__init__.py`: package marker.
- Create `skills/ingest/scripts/inbox_models.py`: dataclasses, serialization, status constants, confidence values.
- Create `skills/ingest/scripts/inbox_store.py`: runtime JSON persistence for folders and runs.
- Create `skills/ingest/scripts/inbox_scan.py`: file stability, candidate detection, scan counts.
- Create `skills/ingest/scripts/inbox_routing.py`: route and rename decisions from extracted content.
- Create `skills/ingest/scripts/source_cards.py`: user-facing Markdown source cards with frontmatter.
- Create `skills/ingest/scripts/inbox_consume.py`: consume orchestration and RAG indexing handoff.
- Create `skills/ingest/scripts/brain_insights.py`: read run history and wiki/RAG state for dashboard.
- Create `skills/ingest/scripts/mcp/__init__.py`: MCP tool registration.
- Create `skills/ingest/scripts/mcp/_shared.py`: local `tool_annotations` helper.
- Create `skills/ingest/scripts/mcp/inbox_tools.py`: pure tool implementations plus registered MCP tools.

### Backend Files To Modify

- Modify `src/lib/extraction/audio_extractor.py`: delegate to a real local transcription wrapper before MarkItDown fallback.
- Create `src/lib/extraction/transcription.py`: local audio capability and transcript result model.
- Create `src/lib/extraction/capabilities.py`: capability inventory for OCR, transcription, Ollama, OpenVINO, NPU/GPU/CPU, airplane policy.
- Modify `src/lib/extraction/__init__.py`: export new transcription/capability helpers.
- Modify `skills/document-extractor/scripts/mcp/tools_extract.py`: enrich `get-extraction-status`.
- Modify `pyproject.toml`: add optional `ai-pc-demo` dependencies for local OCR/transcription acceleration.

### Backend Tests

- Create `skills/ingest/augur/tests/test_inbox_store.py`
- Create `skills/ingest/augur/tests/test_inbox_scan.py`
- Create `skills/ingest/augur/tests/test_source_cards.py`
- Create `skills/ingest/augur/tests/test_inbox_consume.py`
- Create `skills/ingest/augur/tests/test_inbox_mcp_tools.py`
- Create `skills/ingest/augur/tests/test_brain_insights.py`
- Create `skills/document-extractor/augur/tests/test_capabilities.py`
- Expand `skills/document-extractor/augur/tests/test_audio_extractor.py`
- Expand `skills/document-extractor/augur/tests/test_tools_extract.py`

### Dashboard Files To Modify

- Modify `apps/dashboard/features/pages/brain/inbox/types.ts`
- Modify `apps/dashboard/features/pages/brain/inbox/hooks.ts`
- Modify `apps/dashboard/features/pages/brain/inbox/page.tsx`
- Modify `apps/dashboard/features/pages/brain/insights/types.ts`
- Modify `apps/dashboard/features/pages/brain/insights/page.tsx`
- Expand `tests/dashboard/brain/inbox-page.test.tsx`
- Expand `tests/dashboard/brain/insights-page.test.tsx`
- Expand `tests/dashboard/visual/wiki-llm-surface.spec.ts`

---

### Task 1: Create Execution Worktree And Verify Baseline

**Files:**
- Read: `docs/superpowers/specs/2026-05-07-ai-pc-brain-inbox-design.md`
- No code files changed in this task

- [ ] **Step 1: Create an isolated worktree**

Run from `C:\Users\intel\Projects\Augur` in native PowerShell:

```powershell
git fetch origin
git worktree add C:\Users\intel\Projects\Augur\.worktrees\ai-pc-brain-inbox -b ai-pc-brain-inbox origin/main
Set-Location C:\Users\intel\Projects\Augur\.worktrees\ai-pc-brain-inbox
git status --short --branch
```

Expected output includes:

```text
## ai-pc-brain-inbox...origin/main
```

- [ ] **Step 2: Confirm the approved spec is present**

Run:

```powershell
Test-Path docs\superpowers\specs\2026-05-07-ai-pc-brain-inbox-design.md
Get-Content docs\superpowers\specs\2026-05-07-ai-pc-brain-inbox-design.md -TotalCount 20
```

Expected: first command prints `True`; second command shows the `AI PC Brain Inbox Design` heading.

- [ ] **Step 3: Run targeted baseline tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\document-extractor\augur\tests\test_tools_extract.py -q
```

Expected: Python tests pass.

- [ ] **Step 4: Commit checkpoint only if setup files changed**

If no files changed, do not commit. If a repo-local generated file changed during verification, inspect it before committing:

```powershell
git status --short
git diff --stat
```

Expected: clean worktree or only intentional generated changes.

---

### Task 2: Add Capability Inventory And Airplane Policy

**Files:**
- Create: `src/lib/extraction/capabilities.py`
- Modify: `src/lib/extraction/__init__.py`
- Modify: `skills/document-extractor/scripts/mcp/tools_extract.py`
- Create: `skills/document-extractor/augur/tests/test_capabilities.py`
- Modify: `skills/document-extractor/augur/tests/test_tools_extract.py`

- [ ] **Step 1: Write failing capability tests**

Create `skills/document-extractor/augur/tests/test_capabilities.py`:

```python
from __future__ import annotations

from pathlib import Path


def test_airplane_policy_disables_cloud(monkeypatch, tmp_path: Path) -> None:
    from src.lib.extraction import capabilities

    prefs = tmp_path / "preferences.yaml"
    prefs.write_text("airplane_mode:\n  enabled: true\n", encoding="utf-8")
    monkeypatch.setattr(capabilities, "get_preferences_path", lambda: prefs)

    policy = capabilities.get_extraction_policy()

    assert policy["airplane_mode_enabled"] is True
    assert policy["cloud_escalation_allowed"] is False
    assert policy["local_agent_escalation_allowed"] is True


def test_inventory_reports_ollama_vision_models(monkeypatch) -> None:
    from src.lib.extraction import capabilities

    monkeypatch.setattr(capabilities.shutil, "which", lambda name: "ollama.exe" if name == "ollama" else None)
    monkeypatch.setattr(
        capabilities,
        "_run_json_command",
        lambda _cmd, timeout_s=10: {
            "models": [
                {"name": "gemma4:latest", "details": {"families": ["gemma4"]}},
                {"name": "llama3.2:3b", "details": {"families": ["llama"]}},
            ]
        },
    )
    monkeypatch.setattr(
        capabilities,
        "_ollama_show_text",
        lambda model: "Capabilities\n  completion\n  vision\n" if model == "gemma4:latest" else "Capabilities\n  completion\n",
    )

    inventory = capabilities.detect_extraction_capabilities()

    assert inventory["ollama"]["installed"] is True
    assert inventory["ollama"]["vision_models"] == ["gemma4:latest"]
    assert inventory["local_agent_ready"] is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\document-extractor\augur\tests\test_capabilities.py -q
```

Expected: fail with `ImportError` or `AttributeError` for missing `src.lib.extraction.capabilities`.

- [ ] **Step 3: Add capability implementation**

Create `src/lib/extraction/capabilities.py`:

```python
from __future__ import annotations

import json
import platform
import shutil
import subprocess
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from src.config.preferences import get_preferences_path, load_preferences


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _run_json_command(cmd: list[str], timeout_s: int = 10) -> dict[str, Any]:
    completed = subprocess.run(
        cmd,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    if completed.returncode != 0:
        return {}
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _ollama_show_text(model: str) -> str:
    binary = shutil.which("ollama")
    if not binary:
        return ""
    completed = subprocess.run(
        [binary, "show", model],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        timeout=15,
        check=False,
    )
    return completed.stdout if completed.returncode == 0 else ""


def _airplane_enabled_from_preferences() -> bool:
    prefs = load_preferences(path=get_preferences_path(), migrate_legacy=True)
    airplane = prefs.get("airplane_mode", {})
    return isinstance(airplane, dict) and bool(airplane.get("enabled"))


def get_extraction_policy() -> dict[str, bool]:
    airplane = _airplane_enabled_from_preferences()
    return {
        "airplane_mode_enabled": airplane,
        "cloud_escalation_allowed": not airplane,
        "local_agent_escalation_allowed": True,
    }


def _detect_ollama() -> dict[str, Any]:
    binary = shutil.which("ollama")
    if not binary:
        return {"installed": False, "binary": None, "models": [], "vision_models": []}

    raw = _run_json_command([binary, "list", "--json"], timeout_s=10)
    models: list[str] = []
    for item in raw.get("models", []):
        if isinstance(item, dict) and item.get("name"):
            models.append(str(item["name"]))

    if not models:
        completed = subprocess.run(
            [binary, "list"],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=10,
            check=False,
        )
        if completed.returncode == 0:
            for line in completed.stdout.splitlines()[1:]:
                parts = line.split()
                if parts:
                    models.append(parts[0])

    vision_models = [
        model
        for model in models
        if "vision" in _ollama_show_text(model).lower()
    ]
    return {
        "installed": True,
        "binary": binary,
        "models": models,
        "vision_models": vision_models,
    }


def detect_extraction_capabilities() -> dict[str, Any]:
    ollama = _detect_ollama()
    policy = get_extraction_policy()
    packages = {
        name: _package_version(name)
        for name in [
            "markitdown",
            "markitdown-ocr",
            "pymupdf",
            "openvino",
            "openvino-genai",
            "faster-whisper",
            "onnxruntime",
            "onnxruntime-directml",
            "pytesseract",
            "pdf2image",
        ]
    }
    return {
        "platform": platform.system(),
        "policy": policy,
        "packages": packages,
        "commands": {
            "tesseract": shutil.which("tesseract"),
            "ffmpeg": shutil.which("ffmpeg"),
            "ollama": shutil.which("ollama"),
        },
        "ollama": ollama,
        "openvino_ready": packages["openvino"] is not None,
        "openvino_genai_ready": packages["openvino-genai"] is not None,
        "ocr_ready": bool(shutil.which("tesseract")) or packages["openvino"] is not None,
        "transcription_ready": bool(shutil.which("ffmpeg")) and (
            packages["openvino-genai"] is not None or packages["faster-whisper"] is not None
        ),
        "local_agent_ready": bool(ollama["vision_models"]),
    }
```

- [ ] **Step 4: Export capability helpers**

Modify `src/lib/extraction/__init__.py` so it includes:

```python
from src.lib.extraction.capabilities import (
    detect_extraction_capabilities,
    get_extraction_policy,
)
```

and extend `__all__` with:

```python
    "detect_extraction_capabilities",
    "get_extraction_policy",
```

- [ ] **Step 5: Enrich `get-extraction-status`**

Modify `skills/document-extractor/scripts/mcp/tools_extract.py` inside `get_extraction_status_impl()`:

```python
    from src.lib.extraction.capabilities import detect_extraction_capabilities  # noqa: PLC0415

    ai_pc = detect_extraction_capabilities()
```

Add these keys to the returned dict:

```python
        "ai_pc": ai_pc,
        "airplane_mode": ai_pc["policy"],
        "local_agent_ready": ai_pc["local_agent_ready"],
        "transcription_ready": ai_pc["transcription_ready"],
```

- [ ] **Step 6: Expand status MCP tests**

Append to `skills/document-extractor/augur/tests/test_tools_extract.py`:

```python
    def test_reports_ai_pc_policy_fields(self):
        result = get_extraction_status_impl()

        assert "ai_pc" in result
        assert "airplane_mode" in result
        assert "cloud_escalation_allowed" in result["airplane_mode"]
        assert "local_agent_ready" in result
        assert "transcription_ready" in result
```

- [ ] **Step 7: Run capability tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\document-extractor\augur\tests\test_capabilities.py skills\document-extractor\augur\tests\test_tools_extract.py -q
```

Expected: all selected tests pass.

- [ ] **Step 8: Commit**

Run:

```powershell
git add src\lib\extraction\capabilities.py src\lib\extraction\__init__.py skills\document-extractor\scripts\mcp\tools_extract.py skills\document-extractor\augur\tests\test_capabilities.py skills\document-extractor\augur\tests\test_tools_extract.py
git -c user.name='Gur Sannikov' -c user.email='gsannikov@users.noreply.github.com' commit -m "feat(extraction): report AI PC local capability policy"
```

Expected: commit succeeds and pre-commit passes.

---

### Task 3: Add Local Transcription Wrapper

**Files:**
- Create: `src/lib/extraction/transcription.py`
- Modify: `src/lib/extraction/audio_extractor.py`
- Modify: `src/lib/extraction/__init__.py`
- Modify: `pyproject.toml`
- Modify: `skills/document-extractor/augur/tests/test_audio_extractor.py`

- [ ] **Step 1: Write failing transcription tests**

Replace `skills/document-extractor/augur/tests/test_audio_extractor.py` with:

```python
from __future__ import annotations

from pathlib import Path


def test_audio_extractor_importable():
    import importlib

    mod = importlib.import_module("src.lib.extraction.audio_extractor")
    assert mod is not None


def test_local_transcription_result_degrades_when_backend_missing(monkeypatch, tmp_path: Path) -> None:
    from src.lib.extraction import transcription

    audio = tmp_path / "meeting.mp3"
    audio.write_bytes(b"not real audio")

    monkeypatch.setattr(transcription.shutil, "which", lambda _name: None)

    result = transcription.transcribe_audio(str(audio))

    assert result.success is False
    assert result.method == "unavailable"
    assert result.cloud_used is False
    assert result.needs_review is True


def test_audio_extractor_uses_local_transcription(monkeypatch, tmp_path: Path) -> None:
    from src.lib.extraction import audio_extractor
    from src.lib.extraction.transcription import TranscriptResult

    audio = tmp_path / "meeting.mp3"
    audio.write_bytes(b"fake")

    monkeypatch.setattr(
        audio_extractor,
        "transcribe_audio",
        lambda path: TranscriptResult(
            success=True,
            transcript="Discussed roadmap and assigned Gur a follow-up.",
            method="test-local-whisper",
            backend="CPU",
            duration_s=12.0,
            language="en",
            confidence="medium",
        ),
    )

    text = audio_extractor.extract_audio(str(audio))

    assert text is not None
    assert "Discussed roadmap" in text
    assert "Method: test-local-whisper" in text
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\document-extractor\augur\tests\test_audio_extractor.py -q
```

Expected: fail because `src.lib.extraction.transcription` is missing.

- [ ] **Step 3: Add optional local transcription dependencies**

Modify `pyproject.toml` under `[project.optional-dependencies]`:

```toml
ai-pc-demo = [
    "openvino>=2025.0.0",
    "openvino-genai>=2025.0.0",
    "faster-whisper>=1.1.0",
    "ctranslate2>=4.6.0",
    "pytesseract>=0.3.13",
    "pdf2image>=1.17.0",
    "opencv-python>=4.10.0.84",
]
```

- [ ] **Step 4: Add transcription wrapper**

Create `src/lib/extraction/transcription.py`:

```python
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"}


@dataclass
class TranscriptResult:
    success: bool
    transcript: str
    method: str
    backend: str = "unknown"
    duration_s: float | None = None
    language: str | None = None
    confidence: str = "low"
    cloud_used: bool = False
    needs_review: bool = False
    error: str | None = None


def can_transcribe_audio() -> bool:
    return shutil.which("ffmpeg") is not None and (
        _has_openvino_genai() or _has_faster_whisper()
    )


def _has_openvino_genai() -> bool:
    try:
        import openvino_genai  # type: ignore[import]  # noqa: F401
        return True
    except Exception:
        return False


def _has_faster_whisper() -> bool:
    try:
        import faster_whisper  # type: ignore[import]  # noqa: F401
        return True
    except Exception:
        return False


def transcribe_audio(path: str, *, model_dir: str | None = None, device: str = "AUTO") -> TranscriptResult:
    audio = Path(path)
    if not audio.exists():
        return TranscriptResult(
            success=False,
            transcript="",
            method="failed",
            needs_review=True,
            error=f"File not found: {path}",
        )
    if audio.suffix.lower() not in AUDIO_EXTENSIONS:
        return TranscriptResult(
            success=False,
            transcript="",
            method="unsupported",
            needs_review=True,
            error=f"Unsupported audio extension: {audio.suffix}",
        )
    if shutil.which("ffmpeg") is None:
        return TranscriptResult(
            success=False,
            transcript="",
            method="unavailable",
            needs_review=True,
            error="ffmpeg is not installed",
        )
    if _has_openvino_genai() and model_dir:
        return _transcribe_openvino(audio, model_dir=model_dir, device=device)
    if _has_faster_whisper():
        return _transcribe_faster_whisper(audio)
    return TranscriptResult(
        success=False,
        transcript="",
        method="unavailable",
        needs_review=True,
        error="No local Whisper backend is installed",
    )


def _transcribe_openvino(audio: Path, *, model_dir: str, device: str) -> TranscriptResult:
    try:
        import openvino_genai as ov_genai  # type: ignore[import]

        pipe = ov_genai.WhisperPipeline(model_dir, device)
        result = pipe.generate(str(audio))
        transcript = str(getattr(result, "text", result)).strip()
        return TranscriptResult(
            success=bool(transcript),
            transcript=transcript,
            method="openvino-whisper",
            backend=device,
            confidence="medium" if transcript else "low",
            needs_review=not bool(transcript),
        )
    except Exception as exc:
        return TranscriptResult(
            success=False,
            transcript="",
            method="openvino-whisper",
            backend=device,
            needs_review=True,
            error=str(exc),
        )


def _transcribe_faster_whisper(audio: Path) -> TranscriptResult:
    try:
        from faster_whisper import WhisperModel  # type: ignore[import]

        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(audio), vad_filter=True)
        parts = [segment.text.strip() for segment in segments if segment.text.strip()]
        transcript = "\n".join(parts).strip()
        return TranscriptResult(
            success=bool(transcript),
            transcript=transcript,
            method="faster-whisper",
            backend="CPU",
            duration_s=float(getattr(info, "duration", 0.0) or 0.0),
            language=str(getattr(info, "language", "") or "") or None,
            confidence="medium" if transcript else "low",
            needs_review=not bool(transcript),
        )
    except Exception as exc:
        return TranscriptResult(
            success=False,
            transcript="",
            method="faster-whisper",
            backend="CPU",
            needs_review=True,
            error=str(exc),
        )
```

- [ ] **Step 5: Wire audio extractor to local transcription first**

Modify `src/lib/extraction/audio_extractor.py`:

```python
"""Audio transcription with local-first backends and MarkItDown fallback."""
from __future__ import annotations

import platform

from src.lib.extraction.transcription import AUDIO_EXTENSIONS, can_transcribe_audio, transcribe_audio


def can_extract_audio() -> bool:
    if can_transcribe_audio():
        return True
    if platform.system() == "Darwin":
        return True
    try:
        import speech_recognition  # noqa: F401

        return True
    except ImportError:
        return False


def extract_audio(path: str) -> str | None:
    local = transcribe_audio(path)
    if local.success and local.transcript.strip():
        header = [
            "# Audio Transcript",
            "",
            f"Method: {local.method}",
            f"Backend: {local.backend}",
            f"Confidence: {local.confidence}",
        ]
        if local.language:
            header.append(f"Language: {local.language}")
        if local.duration_s is not None:
            header.append(f"Duration seconds: {local.duration_s:.2f}")
        return "\n".join(header) + "\n\n" + local.transcript.strip()

    if platform.system() == "Darwin":
        result = _extract_audio_macos(path)
        if result:
            return result
    try:
        from markitdown import MarkItDown

        md = MarkItDown()
        result = md.convert(path)
        markdown = getattr(result, "markdown", None) or getattr(result, "text_content", "")
        if markdown and markdown.strip():
            return markdown
    except Exception:
        pass
    return None


def _extract_audio_macos(path: str) -> str | None:
    return None
```

- [ ] **Step 6: Export transcription helpers**

Modify `src/lib/extraction/__init__.py`:

```python
from src.lib.extraction.transcription import (
    TranscriptResult,
    can_transcribe_audio,
    transcribe_audio,
)
```

and extend `__all__` with:

```python
    "TranscriptResult",
    "can_transcribe_audio",
    "transcribe_audio",
```

- [ ] **Step 7: Run transcription tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\document-extractor\augur\tests\test_audio_extractor.py -q
```

Expected: all selected tests pass.

- [ ] **Step 8: Commit**

Run:

```powershell
git add pyproject.toml src\lib\extraction\transcription.py src\lib\extraction\audio_extractor.py src\lib\extraction\__init__.py skills\document-extractor\augur\tests\test_audio_extractor.py
git -c user.name='Gur Sannikov' -c user.email='gsannikov@users.noreply.github.com' commit -m "feat(extraction): add local audio transcription wrapper"
```

Expected: commit succeeds and pre-commit passes.

---

### Task 4: Scaffold Ingest Skill Models And Store

**Files:**
- Create: `skills/ingest/SKILL.md`
- Create: `skills/ingest/scripts/__init__.py`
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

    folder_path = tmp_path / "Desktop"
    folder_path.mkdir()
    store = InboxStore(tmp_path / "state")

    folder = store.add_folder(name="Desktop", path=folder_path)
    saved = store.update_folder_counts(
        folder.id,
        {
            "new_files": 3,
            "document_candidates": 2,
            "trash_candidates": 1,
            "failed": 0,
        },
    )

    reloaded = InboxStore(tmp_path / "state")
    folders = reloaded.list_folders()

    assert saved.counts.new_files == 3
    assert len(folders) == 1
    assert folders[0].id == "desktop"
    assert folders[0].path == str(folder_path.resolve())


def test_store_records_run_history_and_detail(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_models import InboxFileResult, InboxRunRecord
    from skills.ingest.scripts.inbox_store import InboxStore

    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=tmp_path / "Desktop")
    record = InboxRunRecord(
        id="run_1",
        folder_id=folder.id,
        started_at="2026-05-07T12:00:00+00:00",
        completed_at="2026-05-07T12:01:00+00:00",
        status="partial_success",
        airplane_mode=True,
        files_seen=1,
        files_moved=1,
        files_indexed=1,
        files_skipped=0,
        files_failed=0,
        files_needing_review=0,
        cloud_calls=0,
        local_agent_calls=1,
        wiki_update_marked=True,
        file_results=[
            InboxFileResult(
                source_path="C:/Users/example/Desktop/meeting.mp3",
                final_path="C:/Users/example/Projects/Au-vault/meetings/2026-05-07-meeting.mp3",
                source_card_path="C:/Users/example/Projects/Au-vault/sources/files/2026-05-07-meeting.md",
                content_type="audio",
                extraction_method="faster-whisper",
                hardware_backend="CPU",
                confidence="medium",
                route="meetings",
                renamed_to="2026-05-07-meeting.mp3",
                rag_indexed=True,
                status="success",
            )
        ],
    )

    store.save_run(record)

    assert store.list_runs()[0].id == "run_1"
    assert store.get_run("run_1").file_results[0].content_type == "audio"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_inbox_store.py -q
```

Expected: fail because `skills/ingest` does not exist.

- [ ] **Step 3: Create ingest skill metadata**

Create `skills/ingest/SKILL.md`:

```markdown
---
name: ingest
x-augur-type: domain
x-augur-group: brain
x-augur-release: mvp
description: Local-first file inbox ingestion for Brain. Scans watched folders, consumes documents and recordings, writes source cards, and updates RAG.
x-augur-hub: brain
x-augur-tab: inbox
x-augur-requires-platform: true
x-augur-mcp-tools:
  - inbox-folders
  - inbox-scan-folder
  - inbox-consume-folder
  - inbox-run-history
  - inbox-run-detail
  - brain-insights
x-augur-dashboard-pages:
  - /brain/inbox
  - /brain/insights
---

# Ingest

Local-first Brain Inbox workflow for consuming files and recordings into Augur knowledge.
```

Create `skills/ingest/scripts/__init__.py`:

```python
"""Brain Inbox ingest backend."""
```

- [ ] **Step 4: Add models**

Create `skills/ingest/scripts/inbox_models.py`:

```python
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any


@dataclass
class InboxFolderCounts:
    new_files: int = 0
    document_candidates: int = 0
    trash_candidates: int = 0
    failed: int = 0


@dataclass
class InboxFolder:
    id: str
    name: str
    path: str
    enabled: bool = True
    counts: InboxFolderCounts = field(default_factory=InboxFolderCounts)
    last_scan_at: str | None = None
    last_run_status: str | None = None


@dataclass
class InboxFileResult:
    source_path: str
    final_path: str | None
    source_card_path: str | None
    content_type: str
    extraction_method: str
    hardware_backend: str
    confidence: str
    route: str | None
    renamed_to: str | None
    rag_indexed: bool
    status: str
    document_kind: str | None = None
    route_reason: str | None = None
    local_agent_used: bool = False
    cloud_used: bool = False
    review_reason: str | None = None
    error: str | None = None


@dataclass
class InboxInsight:
    title: str
    summary: str
    sources: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    impact_score: float = 0.5


@dataclass
class InboxRunRecord:
    id: str
    folder_id: str
    started_at: str
    completed_at: str | None
    status: str
    airplane_mode: bool
    files_seen: int = 0
    files_moved: int = 0
    files_indexed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    files_needing_review: int = 0
    cloud_calls: int = 0
    local_agent_calls: int = 0
    wiki_update_marked: bool = False
    file_results: list[InboxFileResult] = field(default_factory=list)
    insights: list[InboxInsight] = field(default_factory=list)


def to_dict(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {key: to_dict(item) for key, item in dataclasses.asdict(value).items()}
    if isinstance(value, list):
        return [to_dict(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_dict(item) for key, item in value.items()}
    return value
```

- [ ] **Step 5: Add runtime store**

Create `skills/ingest/scripts/inbox_store.py`:

```python
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from skills.ingest.scripts.inbox_models import (
    InboxFileResult,
    InboxFolder,
    InboxFolderCounts,
    InboxInsight,
    InboxRunRecord,
    to_dict,
)


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return text or "folder"


class InboxStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.folders_path = root / "folders.json"
        self.runs_dir = root / "runs"

    def list_folders(self) -> list[InboxFolder]:
        data = self._read_json(self.folders_path, {"folders": []})
        return [self._folder_from_dict(item) for item in data.get("folders", [])]

    def add_folder(self, *, name: str, path: str | Path) -> InboxFolder:
        folders = self.list_folders()
        folder = InboxFolder(
            id=_slug(name),
            name=name,
            path=str(Path(path).expanduser().resolve(strict=False)),
        )
        folders = [existing for existing in folders if existing.id != folder.id]
        folders.append(folder)
        self._write_json(self.folders_path, {"folders": [to_dict(item) for item in folders]})
        return folder

    def get_folder(self, folder_id: str) -> InboxFolder:
        for folder in self.list_folders():
            if folder.id == folder_id:
                return folder
        raise KeyError(f"Unknown inbox folder: {folder_id}")

    def update_folder_counts(self, folder_id: str, counts: dict[str, int]) -> InboxFolder:
        folders = self.list_folders()
        updated: InboxFolder | None = None
        for folder in folders:
            if folder.id == folder_id:
                folder.counts = InboxFolderCounts(**{**to_dict(folder.counts), **counts})
                updated = folder
        if updated is None:
            raise KeyError(f"Unknown inbox folder: {folder_id}")
        self._write_json(self.folders_path, {"folders": [to_dict(item) for item in folders]})
        return updated

    def save_run(self, record: InboxRunRecord) -> InboxRunRecord:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(self.runs_dir / f"{record.id}.json", to_dict(record))
        return record

    def list_runs(self, *, folder_id: str | None = None) -> list[InboxRunRecord]:
        if not self.runs_dir.exists():
            return []
        runs = [self._run_from_dict(self._read_json(path, {})) for path in sorted(self.runs_dir.glob("*.json"))]
        if folder_id:
            runs = [run for run in runs if run.folder_id == folder_id]
        return sorted(runs, key=lambda run: run.started_at, reverse=True)

    def get_run(self, run_id: str) -> InboxRunRecord:
        path = self.runs_dir / f"{run_id}.json"
        if not path.exists():
            raise KeyError(f"Unknown inbox run: {run_id}")
        return self._run_from_dict(self._read_json(path, {}))

    def _read_json(self, path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return dict(fallback)

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _folder_from_dict(self, data: dict[str, Any]) -> InboxFolder:
        counts_raw = data.get("counts") if isinstance(data.get("counts"), dict) else {}
        return InboxFolder(
            id=str(data.get("id") or ""),
            name=str(data.get("name") or ""),
            path=str(data.get("path") or ""),
            enabled=bool(data.get("enabled", True)),
            counts=InboxFolderCounts(**{**to_dict(InboxFolderCounts()), **counts_raw}),
            last_scan_at=data.get("last_scan_at"),
            last_run_status=data.get("last_run_status"),
        )

    def _run_from_dict(self, data: dict[str, Any]) -> InboxRunRecord:
        return InboxRunRecord(
            id=str(data.get("id") or ""),
            folder_id=str(data.get("folder_id") or ""),
            started_at=str(data.get("started_at") or ""),
            completed_at=data.get("completed_at"),
            status=str(data.get("status") or "failed"),
            airplane_mode=bool(data.get("airplane_mode", False)),
            files_seen=int(data.get("files_seen", 0)),
            files_moved=int(data.get("files_moved", 0)),
            files_indexed=int(data.get("files_indexed", 0)),
            files_skipped=int(data.get("files_skipped", 0)),
            files_failed=int(data.get("files_failed", 0)),
            files_needing_review=int(data.get("files_needing_review", 0)),
            cloud_calls=int(data.get("cloud_calls", 0)),
            local_agent_calls=int(data.get("local_agent_calls", 0)),
            wiki_update_marked=bool(data.get("wiki_update_marked", False)),
            file_results=[InboxFileResult(**item) for item in data.get("file_results", [])],
            insights=[InboxInsight(**item) for item in data.get("insights", [])],
        )
```

- [ ] **Step 6: Run store tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_inbox_store.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add skills\ingest\SKILL.md skills\ingest\scripts\__init__.py skills\ingest\scripts\inbox_models.py skills\ingest\scripts\inbox_store.py skills\ingest\augur\tests\test_inbox_store.py
git -c user.name='Gur Sannikov' -c user.email='gsannikov@users.noreply.github.com' commit -m "feat(ingest): add inbox runtime store"
```

Expected: commit succeeds and pre-commit passes.

---

### Task 5: Add Folder Scan And MCP Folder Tools

**Files:**
- Create: `skills/ingest/scripts/inbox_scan.py`
- Create: `skills/ingest/scripts/mcp/__init__.py`
- Create: `skills/ingest/scripts/mcp/_shared.py`
- Create: `skills/ingest/scripts/mcp/inbox_tools.py`
- Create: `skills/ingest/augur/tests/test_inbox_scan.py`
- Create: `skills/ingest/augur/tests/test_inbox_mcp_tools.py`

- [ ] **Step 1: Write failing scan and MCP tests**

Create `skills/ingest/augur/tests/test_inbox_scan.py`:

```python
from __future__ import annotations

from pathlib import Path


def test_scan_counts_documents_and_trash(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_scan import scan_folder

    (tmp_path / "invoice.pdf").write_bytes(b"%PDF-1.7\n")
    (tmp_path / "meeting.mp3").write_bytes(b"audio")
    (tmp_path / "download.tmp").write_text("partial", encoding="utf-8")

    result = scan_folder(tmp_path)

    assert result.counts.new_files == 3
    assert result.counts.document_candidates == 2
    assert result.counts.trash_candidates == 1
    assert [item.name for item in result.items] == ["download.tmp", "invoice.pdf", "meeting.mp3"]
```

Create `skills/ingest/augur/tests/test_inbox_mcp_tools.py`:

```python
from __future__ import annotations

import asyncio
import json
from pathlib import Path


def test_inbox_folders_add_and_list(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts.mcp import inbox_tools

    monkeypatch.setattr(inbox_tools, "_store_root", lambda: tmp_path / "state")
    folder_path = tmp_path / "Desktop"
    folder_path.mkdir()

    added = json.loads(asyncio.run(inbox_tools.inbox_folders_impl(action="add", name="Desktop", path=str(folder_path))))
    listed = json.loads(asyncio.run(inbox_tools.inbox_folders_impl(action="list")))

    assert added["success"] is True
    assert listed["folders"][0]["id"] == "desktop"


def test_register_tools_exposes_required_names() -> None:
    from skills.ingest.scripts.mcp import register_tools

    class FakeMcp:
        def __init__(self) -> None:
            self.tools = {}

        def tool(self, name, annotations=None):
            def decorator(func):
                self.tools[name] = func
                return func
            return decorator

    fake = FakeMcp()
    register_tools(fake, lambda func: func, None)

    assert "inbox-folders" in fake.tools
    assert "inbox-scan-folder" in fake.tools
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_inbox_scan.py skills\ingest\augur\tests\test_inbox_mcp_tools.py -q
```

Expected: fail because scanner and MCP files are missing.

- [ ] **Step 3: Add folder scanner**

Create `skills/ingest/scripts/inbox_scan.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from skills.ingest.scripts.inbox_models import InboxFolderCounts

DOCUMENT_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".png", ".jpg", ".jpeg", ".tiff", ".webp", ".txt", ".md",
    ".mp3", ".wav", ".m4a", ".flac",
}
TRASH_EXTENSIONS = {".tmp", ".download", ".crdownload", ".part"}


@dataclass
class ScanItem:
    path: str
    name: str
    suffix: str
    candidate_type: str
    stable: bool = True


@dataclass
class ScanResult:
    path: str
    counts: InboxFolderCounts
    items: list[ScanItem]


def scan_folder(path: str | Path) -> ScanResult:
    folder = Path(path).expanduser().resolve(strict=False)
    items: list[ScanItem] = []
    counts = InboxFolderCounts()
    if not folder.is_dir():
        counts.failed = 1
        return ScanResult(path=str(folder), counts=counts, items=items)

    for file_path in sorted(folder.iterdir(), key=lambda item: item.name.lower()):
        if not file_path.is_file():
            continue
        suffix = file_path.suffix.lower()
        counts.new_files += 1
        if suffix in TRASH_EXTENSIONS:
            candidate_type = "trash"
            counts.trash_candidates += 1
        elif suffix in DOCUMENT_EXTENSIONS:
            candidate_type = "document"
            counts.document_candidates += 1
        else:
            candidate_type = "unknown"
        items.append(
            ScanItem(
                path=str(file_path),
                name=file_path.name,
                suffix=suffix,
                candidate_type=candidate_type,
                stable=True,
            )
        )
    return ScanResult(path=str(folder), counts=counts, items=items)
```

- [ ] **Step 4: Add MCP registration**

Create `skills/ingest/scripts/mcp/_shared.py`:

```python
from __future__ import annotations


def tool_annotations(hints: dict) -> dict:
    return {"annotations": {"hints": hints}}
```

Create `skills/ingest/scripts/mcp/inbox_tools.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

from src.config.paths import get_runtime_dir
from skills.ingest.scripts.inbox_scan import scan_folder
from skills.ingest.scripts.inbox_store import InboxStore
from skills.ingest.scripts.inbox_models import to_dict
from ._shared import tool_annotations

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _store_root() -> Path:
    return get_runtime_dir() / "brain" / "inbox"


def _store() -> InboxStore:
    return InboxStore(_store_root())


async def inbox_folders_impl(action: str = "list", folder_id: str = "", name: str = "", path: str = "") -> str:
    store = _store()
    if action == "add":
        if not path:
            return json.dumps({"success": False, "error": "path is required"})
        folder = store.add_folder(name=name or Path(path).name or "Folder", path=path)
        return json.dumps({"success": True, "folder": to_dict(folder), "message": "Folder added."})
    if action == "list":
        return json.dumps({"success": True, "folders": [to_dict(folder) for folder in store.list_folders()]})
    return json.dumps({"success": False, "error": f"Unsupported action: {action}"})


async def inbox_scan_folder_impl(folder_id: str = "") -> str:
    store = _store()
    folder = store.get_folder(folder_id)
    result = scan_folder(folder.path)
    saved = store.update_folder_counts(folder.id, to_dict(result.counts))
    return json.dumps({"success": True, "folder": to_dict(saved), "items": [to_dict(item) for item in result.items]})


def register_inbox_tools(mcp: "FastMCP", mcp_tool_interceptor: Callable[..., Any], metrics: Any = None) -> None:
    @mcp.tool(name="inbox-folders", annotations=tool_annotations({"title": "Inbox Folders", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True}))
    @mcp_tool_interceptor
    async def inbox_folders(action: str = "list", folder_id: str = "", name: str = "", path: str = "") -> str:
        return await inbox_folders_impl(action=action, folder_id=folder_id, name=name, path=path)

    @mcp.tool(name="inbox-scan-folder", annotations=tool_annotations({"title": "Inbox Scan Folder", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True}))
    @mcp_tool_interceptor
    async def inbox_scan_folder(folder_id: str = "") -> str:
        return await inbox_scan_folder_impl(folder_id=folder_id)
```

Create `skills/ingest/scripts/mcp/__init__.py`:

```python
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from .inbox_tools import register_inbox_tools

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_tools(mcp: "FastMCP", mcp_tool_interceptor: Callable[..., Any], metrics: Any = None) -> None:
    register_inbox_tools(mcp, mcp_tool_interceptor, metrics)


__all__ = ["register_tools"]
```

- [ ] **Step 5: Run scan and MCP tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_inbox_scan.py skills\ingest\augur\tests\test_inbox_mcp_tools.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add skills\ingest\scripts\inbox_scan.py skills\ingest\scripts\mcp skills\ingest\augur\tests\test_inbox_scan.py skills\ingest\augur\tests\test_inbox_mcp_tools.py
git -c user.name='Gur Sannikov' -c user.email='gsannikov@users.noreply.github.com' commit -m "feat(ingest): add inbox scan MCP tools"
```

Expected: commit succeeds and pre-commit passes.

---

### Task 6: Add Routing, Renaming, And Source Cards

**Files:**
- Create: `skills/ingest/scripts/inbox_routing.py`
- Create: `skills/ingest/scripts/source_cards.py`
- Create: `skills/ingest/augur/tests/test_source_cards.py`

- [ ] **Step 1: Write failing source card tests**

Create `skills/ingest/augur/tests/test_source_cards.py`:

```python
from __future__ import annotations

from pathlib import Path


def test_route_decision_uses_meeting_audio_summary() -> None:
    from skills.ingest.scripts.inbox_routing import decide_route

    decision = decide_route(
        source_name="meeting.mp3",
        title="Product roadmap meeting",
        body="Discussed roadmap decisions and follow-up actions.",
        content_type="audio",
    )

    assert decision.route == "meetings"
    assert decision.filename.endswith("product-roadmap-meeting.mp3")


def test_source_card_starts_with_frontmatter(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_routing import RouteDecision
    from skills.ingest.scripts.source_cards import write_source_card

    card = write_source_card(
        vault_dir=tmp_path,
        title="Product roadmap meeting",
        body="Summary text.",
        decision=RouteDecision(route="meetings", filename="2026-05-07-product-roadmap-meeting.mp3", reason="Audio meeting detected."),
        original_path="C:/Users/example/Desktop/meeting.mp3",
        final_path=str(tmp_path / "meetings" / "2026-05-07-product-roadmap-meeting.mp3"),
        extracted_path=str(tmp_path / "sources" / "files" / "2026-05-07-product-roadmap-meeting.transcript.md"),
        extraction_method="faster-whisper",
        hardware_backend="CPU",
        confidence="medium",
        content_type="audio",
    )

    text = card.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "Product roadmap meeting" in text
    assert "Audio meeting detected." in text
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_source_cards.py -q
```

Expected: fail because routing/source card files are missing.

- [ ] **Step 3: Add routing**

Create `skills/ingest/scripts/inbox_routing.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass
class RouteDecision:
    route: str
    filename: str
    reason: str


def _slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return value[:80].strip("-") or "imported-file"


def decide_route(*, source_name: str, title: str, body: str, content_type: str) -> RouteDecision:
    lowered = f"{source_name}\n{title}\n{body}".lower()
    suffix = Path(source_name).suffix.lower()
    if content_type == "audio" or suffix in {".mp3", ".wav", ".m4a", ".flac"}:
        route = "meetings"
        reason = "Audio meeting or recording detected."
    elif any(token in lowered for token in ["invoice", "receipt", "bank", "statement", "payment"]):
        route = "finance"
        reason = "Finance terms detected in extracted content."
    elif any(token in lowered for token in ["doctor", "medical", "health", "clinic", "insurance"]):
        route = "health"
        reason = "Health or insurance terms detected in extracted content."
    else:
        route = "inbox/review"
        reason = "No confident route matched."
    stem_source = title.strip() or Path(source_name).stem
    filename = f"{date.today().isoformat()}-{_slug(stem_source)}{suffix or '.md'}"
    return RouteDecision(route=route, filename=filename, reason=reason)
```

- [ ] **Step 4: Add source card writer**

Create `skills/ingest/scripts/source_cards.py`:

```python
from __future__ import annotations

from pathlib import Path

from src.lib.frontmatter_utils import write_vault_frontmatter
from skills.ingest.scripts.inbox_routing import RouteDecision


def _card_name(filename: str) -> str:
    return f"{Path(filename).stem}.md"


def write_source_card(
    *,
    vault_dir: Path,
    title: str,
    body: str,
    decision: RouteDecision,
    original_path: str,
    final_path: str | None,
    extracted_path: str | None,
    extraction_method: str,
    hardware_backend: str,
    confidence: str,
    content_type: str,
) -> Path:
    target = vault_dir / "sources" / "files" / _card_name(decision.filename)
    metadata = {
        "title": title,
        "source_type": "file",
        "content_type": content_type,
        "original_path": original_path,
        "final_path": final_path,
        "extracted_path": extracted_path,
        "extraction_method": extraction_method,
        "hardware_backend": hardware_backend,
        "confidence": confidence,
        "route": decision.route,
        "tags": ["inbox", decision.route.replace("/", "-")],
        "_source_type": "inbox-file",
    }
    card_body = (
        f"# {title}\n\n"
        f"> [!summary]\n> {body.strip()[:800] or 'No readable summary was captured.'}\n\n"
        f"## Routing\n\n"
        f"- Destination: `{decision.route}`\n"
        f"- Reason: {decision.reason}\n"
        f"- Original: `{original_path}`\n"
        f"- Final: `{final_path or ''}`\n"
        f"- Extracted: `{extracted_path or ''}`\n"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    write_vault_frontmatter(target, metadata, card_body)
    return target
```

- [ ] **Step 5: Run source card tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_source_cards.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add skills\ingest\scripts\inbox_routing.py skills\ingest\scripts\source_cards.py skills\ingest\augur\tests\test_source_cards.py
git -c user.name='Gur Sannikov' -c user.email='gsannikov@users.noreply.github.com' commit -m "feat(ingest): write routed inbox source cards"
```

Expected: commit succeeds and pre-commit passes.

---

### Task 7: Add Consume Workflow And RAG Indexing

**Files:**
- Create: `skills/ingest/scripts/inbox_consume.py`
- Modify: `skills/ingest/scripts/mcp/inbox_tools.py`
- Create: `skills/ingest/augur/tests/test_inbox_consume.py`
- Modify: `skills/ingest/augur/tests/test_inbox_mcp_tools.py`

- [ ] **Step 1: Write failing consume tests**

Create `skills/ingest/augur/tests/test_inbox_consume.py`:

```python
from __future__ import annotations

from pathlib import Path


def test_consume_text_file_writes_card_and_run(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import inbox_consume
    from skills.ingest.scripts.inbox_store import InboxStore

    inbox = tmp_path / "Desktop"
    inbox.mkdir()
    (inbox / "invoice.txt").write_text("Invoice 1042\nAmount due 1200\n", encoding="utf-8")
    vault = tmp_path / "vault"
    rag = tmp_path / "rag"
    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=inbox)

    monkeypatch.setattr(inbox_consume, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(inbox_consume, "get_rag_dir", lambda: rag)
    monkeypatch.setattr(inbox_consume, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(inbox_consume, "reindex_category", lambda category, root, rag_dir, vault_dir=None: 1)
    monkeypatch.setattr(inbox_consume, "get_extraction_policy", lambda: {"airplane_mode_enabled": True, "cloud_escalation_allowed": False, "local_agent_escalation_allowed": True})

    record = inbox_consume.consume_folder(store=store, folder_id=folder.id)

    assert record.status == "success"
    assert record.cloud_calls == 0
    assert record.files_indexed == 1
    assert Path(record.file_results[0].source_card_path).exists()
    assert "invoice" in record.file_results[0].renamed_to
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_inbox_consume.py -q
```

Expected: fail because consume workflow is missing.

- [ ] **Step 3: Add consume workflow**

Create `skills/ingest/scripts/inbox_consume.py`:

```python
from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.config.paths import get_project_root, get_rag_dir, get_vault_dir
from src.lib.extraction import extract, get_extraction_policy
from src.lib.index.unified_indexer import reindex_category
from skills.ingest.scripts.inbox_models import InboxFileResult, InboxRunRecord
from skills.ingest.scripts.inbox_routing import decide_route
from skills.ingest.scripts.inbox_scan import scan_folder
from skills.ingest.scripts.inbox_store import InboxStore
from skills.ingest.scripts.source_cards import write_source_card


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _content_type(path: Path) -> str:
    if path.suffix.lower() in {".mp3", ".wav", ".m4a", ".flac"}:
        return "audio"
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tiff", ".webp"}:
        return "image"
    return "document"


def consume_folder(*, store: InboxStore, folder_id: str) -> InboxRunRecord:
    folder = store.get_folder(folder_id)
    started = _now()
    policy = get_extraction_policy()
    scan = scan_folder(folder.path)
    file_results: list[InboxFileResult] = []
    vault_dir = get_vault_dir()

    for item in scan.items:
        source = Path(item.path)
        if item.candidate_type == "trash":
            file_results.append(
                InboxFileResult(
                    source_path=str(source),
                    final_path=None,
                    source_card_path=None,
                    content_type="trash",
                    extraction_method="skipped",
                    hardware_backend="none",
                    confidence="low",
                    route=None,
                    renamed_to=None,
                    rag_indexed=False,
                    status="skipped",
                    review_reason="Temporary or partial download file.",
                )
            )
            continue

        extracted = extract(str(source), max_tier=1)
        body = extracted.markdown.strip()
        if not extracted.success or not body:
            file_results.append(
                InboxFileResult(
                    source_path=str(source),
                    final_path=None,
                    source_card_path=None,
                    content_type=_content_type(source),
                    extraction_method=f"document-extractor:{extracted.tier_used}",
                    hardware_backend="unknown",
                    confidence="low",
                    route=None,
                    renamed_to=None,
                    rag_indexed=False,
                    status="needs_review",
                    review_reason=extracted.error or "No readable text captured.",
                )
            )
            continue

        decision = decide_route(
            source_name=source.name,
            title=extracted.title or source.stem,
            body=body,
            content_type=_content_type(source),
        )
        final_path = vault_dir / decision.route / decision.filename
        final_path.parent.mkdir(parents=True, exist_ok=True)
        if source.exists():
            shutil.move(str(source), str(final_path))

        card = write_source_card(
            vault_dir=vault_dir,
            title=extracted.title or source.stem,
            body=body,
            decision=decision,
            original_path=str(source),
            final_path=str(final_path),
            extracted_path=None,
            extraction_method=f"document-extractor:{extracted.tier_used}",
            hardware_backend="local",
            confidence="medium" if extracted.ocr_applied else "high",
            content_type=_content_type(final_path),
        )
        file_results.append(
            InboxFileResult(
                source_path=str(source),
                final_path=str(final_path),
                source_card_path=str(card),
                content_type=_content_type(final_path),
                extraction_method=f"document-extractor:{extracted.tier_used}",
                hardware_backend="local",
                confidence="medium" if extracted.ocr_applied else "high",
                route=decision.route,
                renamed_to=decision.filename,
                rag_indexed=True,
                status="success",
                route_reason=decision.reason,
                cloud_used=False,
                local_agent_used=bool(getattr(extracted, "needs_llm", False)),
            )
        )

    indexed = sum(1 for item in file_results if item.rag_indexed)
    if indexed:
        reindex_category("vault", get_project_root(), get_rag_dir(), vault_dir=vault_dir)

    failed = sum(1 for item in file_results if item.status == "failed")
    review = sum(1 for item in file_results if item.status == "needs_review")
    moved = sum(1 for item in file_results if item.final_path)
    skipped = sum(1 for item in file_results if item.status == "skipped")
    status = "success" if failed == 0 and review == 0 else "partial_success"
    record = InboxRunRecord(
        id=f"run_{uuid.uuid4().hex[:12]}",
        folder_id=folder_id,
        started_at=started,
        completed_at=_now(),
        status=status,
        airplane_mode=bool(policy["airplane_mode_enabled"]),
        files_seen=len(scan.items),
        files_moved=moved,
        files_indexed=indexed,
        files_skipped=skipped,
        files_failed=failed,
        files_needing_review=review,
        cloud_calls=0,
        local_agent_calls=sum(1 for item in file_results if item.local_agent_used),
        wiki_update_marked=indexed > 0,
        file_results=file_results,
    )
    return store.save_run(record)
```

- [ ] **Step 4: Add consume MCP tools**

Modify `skills/ingest/scripts/mcp/inbox_tools.py` imports:

```python
from skills.ingest.scripts.inbox_consume import consume_folder
```

Add pure implementation:

```python
async def inbox_consume_folder_impl(folder_id: str = "") -> str:
    record = consume_folder(store=_store(), folder_id=folder_id)
    return json.dumps({"success": True, **to_dict(record), "message": "Consume completed."})
```

Inside `register_inbox_tools`, add:

```python
    @mcp.tool(name="inbox-consume-folder", annotations=tool_annotations({"title": "Inbox Consume Folder", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True}))
    @mcp_tool_interceptor
    async def inbox_consume_folder(folder_id: str = "") -> str:
        return await inbox_consume_folder_impl(folder_id=folder_id)
```

- [ ] **Step 5: Expand MCP registration test**

Modify `skills/ingest/augur/tests/test_inbox_mcp_tools.py`:

```python
    assert "inbox-consume-folder" in fake.tools
```

- [ ] **Step 6: Run consume tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_inbox_consume.py skills\ingest\augur\tests\test_inbox_mcp_tools.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add skills\ingest\scripts\inbox_consume.py skills\ingest\scripts\mcp\inbox_tools.py skills\ingest\augur\tests\test_inbox_consume.py skills\ingest\augur\tests\test_inbox_mcp_tools.py
git -c user.name='Gur Sannikov' -c user.email='gsannikov@users.noreply.github.com' commit -m "feat(ingest): consume inbox files into source cards"
```

Expected: commit succeeds and pre-commit passes.

---

### Task 8: Add Run History, Run Detail, And Brain Insights MCP

**Files:**
- Create: `skills/ingest/scripts/brain_insights.py`
- Modify: `skills/ingest/scripts/mcp/inbox_tools.py`
- Create: `skills/ingest/augur/tests/test_brain_insights.py`
- Modify: `skills/ingest/augur/tests/test_inbox_mcp_tools.py`

- [ ] **Step 1: Write failing Brain Insights tests**

Create `skills/ingest/augur/tests/test_brain_insights.py`:

```python
from __future__ import annotations

from pathlib import Path


def test_brain_insights_returns_latest_runs(tmp_path: Path) -> None:
    from skills.ingest.scripts.brain_insights import build_brain_insights
    from skills.ingest.scripts.inbox_models import InboxRunRecord
    from skills.ingest.scripts.inbox_store import InboxStore

    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=tmp_path / "Desktop")
    store.save_run(
        InboxRunRecord(
            id="run_1",
            folder_id=folder.id,
            started_at="2026-05-07T12:00:00+00:00",
            completed_at="2026-05-07T12:01:00+00:00",
            status="success",
            airplane_mode=True,
            files_seen=1,
            files_moved=1,
            files_indexed=1,
        )
    )

    payload = build_brain_insights(store=store)

    assert payload["success"] is True
    assert payload["latest_runs"][0]["id"] == "run_1"
    assert payload["wiki_status"]["actions"][0]["tool"] == "wiki-update"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_brain_insights.py -q
```

Expected: fail because `brain_insights.py` is missing.

- [ ] **Step 3: Add Brain Insights builder**

Create `skills/ingest/scripts/brain_insights.py`:

```python
from __future__ import annotations

from skills.ingest.scripts.inbox_store import InboxStore
from skills.ingest.scripts.inbox_models import to_dict


def build_brain_insights(*, store: InboxStore, limit: int = 10) -> dict:
    runs = store.list_runs()[:limit]
    latest_runs = [to_dict(run) for run in runs]
    return {
        "success": True,
        "latest_runs": latest_runs,
        "wiki_status": {
            "verdict": "inbox_sources_ready" if latest_runs else "no_recent_inbox_runs",
            "healthy": True,
            "structure": {"pages": 0, "missing_links": [], "orphan_pages": []},
            "compiler": {
                "sources_total": sum(run.files_indexed for run in runs),
                "sources_pending_or_changed": sum(run.files_indexed for run in runs),
                "current": False if latest_runs else True,
            },
            "coverage": {"concept_coverage_ratio": 0.0, "top_uncovered_source_families": []},
            "index": {"indexed": bool(latest_runs), "wiki_rag_entries": 0},
            "batches": {"batch_count": 0, "needs_update": bool(latest_runs)},
            "compounding_health": {
                "concept_page_count": 0,
                "average_sources_per_concept_page": 0,
                "thin_page_count": 0,
                "target_sources_per_page": "10-15",
            },
            "actions": [
                {
                    "id": "prepare-incremental-batch",
                    "tool": "wiki-update",
                    "inputs": {"limit": 20},
                    "reason": "Recent inbox source cards are ready for concept compounding.",
                }
            ] if latest_runs else [],
        },
        "retained_ask_outcomes": [],
        "retained_ask_clusters": [],
        "errors": [],
    }
```

- [ ] **Step 4: Add MCP implementations**

Modify `skills/ingest/scripts/mcp/inbox_tools.py` imports:

```python
from skills.ingest.scripts.brain_insights import build_brain_insights
```

Add pure implementations:

```python
async def inbox_run_history_impl(folder_id: str = "") -> str:
    runs = _store().list_runs(folder_id=folder_id or None)
    return json.dumps({"success": True, "runs": [to_dict(run) for run in runs]})


async def inbox_run_detail_impl(run_id: str = "") -> str:
    run = _store().get_run(run_id)
    return json.dumps({"success": True, "run": to_dict(run)})


async def brain_insights_impl() -> str:
    return json.dumps(build_brain_insights(store=_store()))
```

Inside `register_inbox_tools`, add:

```python
    @mcp.tool(name="inbox-run-history", annotations=tool_annotations({"title": "Inbox Run History", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def inbox_run_history(folder_id: str = "") -> str:
        return await inbox_run_history_impl(folder_id=folder_id)

    @mcp.tool(name="inbox-run-detail", annotations=tool_annotations({"title": "Inbox Run Detail", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def inbox_run_detail(run_id: str = "") -> str:
        return await inbox_run_detail_impl(run_id=run_id)

    @mcp.tool(name="brain-insights", annotations=tool_annotations({"title": "Brain Insights", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def brain_insights() -> str:
        return await brain_insights_impl()
```

- [ ] **Step 5: Expand MCP registration test**

Modify `skills/ingest/augur/tests/test_inbox_mcp_tools.py`:

```python
    assert "inbox-run-history" in fake.tools
    assert "inbox-run-detail" in fake.tools
    assert "brain-insights" in fake.tools
```

- [ ] **Step 6: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_brain_insights.py skills\ingest\augur\tests\test_inbox_mcp_tools.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add skills\ingest\scripts\brain_insights.py skills\ingest\scripts\mcp\inbox_tools.py skills\ingest\augur\tests\test_brain_insights.py skills\ingest\augur\tests\test_inbox_mcp_tools.py
git -c user.name='Gur Sannikov' -c user.email='gsannikov@users.noreply.github.com' commit -m "feat(ingest): expose brain inbox insights"
```

Expected: commit succeeds and pre-commit passes.

---

### Task 9: Wire Dashboard To Richer File Results

**Files:**
- Modify: `apps/dashboard/features/pages/brain/inbox/types.ts`
- Modify: `apps/dashboard/features/pages/brain/inbox/page.tsx`
- Modify: `apps/dashboard/features/pages/brain/insights/types.ts`
- Modify: `apps/dashboard/features/pages/brain/insights/page.tsx`
- Modify: `tests/dashboard/brain/inbox-page.test.tsx`
- Modify: `tests/dashboard/brain/insights-page.test.tsx`

- [ ] **Step 1: Add failing dashboard tests for backend evidence**

Append to `tests/dashboard/brain/inbox-page.test.tsx`:

```tsx
it("renders latest run file results with local backend evidence", () => {
  setInboxQuery({
    latest_runs: [
      {
        id: "run_ai_pc",
        status: "partial_success",
        files_seen: 2,
        files_moved: 1,
        files_indexed: 1,
        files_needing_review: 1,
        cloud_calls: 0,
        local_agent_calls: 1,
        file_results: [
          {
            source_path: "C:/Users/example/Desktop/scan.pdf",
            final_path: "C:/Users/example/Projects/Au-vault/finance/2026-05-07-scan.pdf",
            source_card_path: "C:/Users/example/Projects/Au-vault/sources/files/2026-05-07-scan.md",
            content_type: "pdf",
            extraction_method: "openvino-ocr",
            hardware_backend: "NPU",
            confidence: "medium",
            route: "finance",
            renamed_to: "2026-05-07-scan.pdf",
            rag_indexed: true,
            status: "success",
            local_agent_used: true,
            cloud_used: false,
          },
        ],
      },
    ],
  });

  render(<InboxPage />);

  expect(screen.getByText("run_ai_pc")).toBeInTheDocument();
  expect(screen.getByText("openvino-ocr")).toBeInTheDocument();
  expect(screen.getByText("NPU")).toBeInTheDocument();
  expect(screen.getByText("cloud: no")).toBeInTheDocument();
});
```

Append to `tests/dashboard/brain/insights-page.test.tsx`:

```tsx
it("shows airplane/local agent counters from latest inbox run", () => {
  setInsightsQuery({
    latest_runs: [
      {
        id: "run_airplane",
        status: "partial_success",
        airplane_mode: true,
        cloud_calls: 0,
        local_agent_calls: 1,
        files_seen: 2,
        files_moved: 1,
        files_indexed: 1,
        files_needing_review: 1,
        insights: [],
      },
    ],
  });

  render(<InsightsPage />);

  expect(screen.getByText("run_airplane")).toBeInTheDocument();
  expect(screen.getByText(/Airplane mode/i)).toBeInTheDocument();
  expect(screen.getByText(/Cloud calls: 0/i)).toBeInTheDocument();
  expect(screen.getByText(/Local agent calls: 1/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run dashboard tests to verify failure**

Run:

```powershell
Set-Location apps\dashboard
pnpm test -- --runTestsByPath ..\..\tests\dashboard\brain\inbox-page.test.tsx ..\..\tests\dashboard\brain\insights-page.test.tsx
Set-Location ..\..
```

Expected: fail because types/pages do not render the new fields.

- [ ] **Step 3: Extend inbox TypeScript types**

Modify `apps/dashboard/features/pages/brain/inbox/types.ts`:

```ts
export type InboxFileResult = {
  source_path: string;
  final_path?: string | null;
  source_card_path?: string | null;
  content_type: string;
  extraction_method: string;
  hardware_backend: string;
  confidence: string;
  route?: string | null;
  renamed_to?: string | null;
  rag_indexed: boolean;
  status: string;
  local_agent_used?: boolean;
  cloud_used?: boolean;
  review_reason?: string | null;
  error?: string | null;
};

export type InboxRun = {
  id: string;
  status: string;
  airplane_mode?: boolean;
  files_seen?: number;
  files_moved?: number;
  files_indexed?: number;
  files_skipped?: number;
  files_failed?: number;
  files_needing_review?: number;
  cloud_calls?: number;
  local_agent_calls?: number;
  file_results?: InboxFileResult[];
};
```

Add to `BrainInboxResponse`:

```ts
  latest_runs?: InboxRun[];
```

- [ ] **Step 4: Render file results on Inbox page**

Modify `apps/dashboard/features/pages/brain/inbox/page.tsx` by adding a compact run section below folder rows:

```tsx
function LatestRunList({ runs }: { runs: InboxRun[] }) {
  if (runs.length === 0) return null;
  return (
    <section className="space-y-3" aria-label="Recent inbox runs">
      <h2 className="text-base font-semibold text-[var(--text-primary)]">Recent runs</h2>
      {runs.slice(0, 3).map((run) => (
        <article key={run.id} className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
          <div className="flex flex-wrap items-center gap-2 text-sm text-[var(--text-secondary)]">
            <span className="font-medium text-[var(--text-primary)]">{run.id}</span>
            <span>{run.status}</span>
            <span>Cloud calls: {run.cloud_calls ?? 0}</span>
            <span>Local agent calls: {run.local_agent_calls ?? 0}</span>
          </div>
          <div className="mt-3 grid gap-2">
            {(run.file_results ?? []).map((file) => (
              <div key={`${run.id}-${file.source_path}`} className="rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] p-3 text-xs text-[var(--text-muted)]">
                <div className="font-medium text-[var(--text-primary)]">{file.renamed_to || file.source_path}</div>
                <div className="mt-1 flex flex-wrap gap-2">
                  <span>{file.extraction_method}</span>
                  <span>{file.hardware_backend}</span>
                  <span>{file.confidence}</span>
                  <span>cloud: {file.cloud_used ? "yes" : "no"}</span>
                  <span>{file.status}</span>
                </div>
              </div>
            ))}
          </div>
        </article>
      ))}
    </section>
  );
}
```

Use it inside the page render:

```tsx
<LatestRunList runs={data.latest_runs ?? []} />
```

- [ ] **Step 5: Extend insights TypeScript types**

Modify `apps/dashboard/features/pages/brain/insights/types.ts` in `BrainInsightsRun`:

```ts
  airplane_mode?: boolean;
  files_needing_review?: number;
  cloud_calls?: number;
  local_agent_calls?: number;
```

- [ ] **Step 6: Render local/cloud evidence on Insights page**

Modify `apps/dashboard/features/pages/brain/insights/page.tsx` in the latest run card:

```tsx
<div className="mt-2 flex flex-wrap gap-2 text-xs text-[var(--text-muted)]">
  {run.airplane_mode && <span>Airplane mode</span>}
  <span>Cloud calls: {run.cloud_calls ?? 0}</span>
  <span>Local agent calls: {run.local_agent_calls ?? 0}</span>
  <span>Needs review: {run.files_needing_review ?? 0}</span>
</div>
```

- [ ] **Step 7: Run dashboard tests**

Run:

```powershell
Set-Location apps\dashboard
pnpm test -- --runTestsByPath ..\..\tests\dashboard\brain\inbox-page.test.tsx ..\..\tests\dashboard\brain\insights-page.test.tsx
Set-Location ..\..
```

Expected: selected Jest tests pass.

- [ ] **Step 8: Commit**

Run:

```powershell
git add apps\dashboard\features\pages\brain\inbox\types.ts apps\dashboard\features\pages\brain\inbox\page.tsx apps\dashboard\features\pages\brain\insights\types.ts apps\dashboard\features\pages\brain\insights\page.tsx tests\dashboard\brain\inbox-page.test.tsx tests\dashboard\brain\insights-page.test.tsx
git -c user.name='Gur Sannikov' -c user.email='gsannikov@users.noreply.github.com' commit -m "feat(dashboard): show AI PC inbox run evidence"
```

Expected: commit succeeds and pre-commit passes.

---

### Task 10: Add Demo Calibration Command

**Files:**
- Create: `skills/ingest/scripts/ai_pc_demo_calibration.py`
- Create: `skills/ingest/augur/tests/test_ai_pc_demo_calibration.py`

- [ ] **Step 1: Write failing calibration tests**

Create `skills/ingest/augur/tests/test_ai_pc_demo_calibration.py`:

```python
from __future__ import annotations

from pathlib import Path


def test_calibration_scores_text_file_without_cloud(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import ai_pc_demo_calibration

    sample = tmp_path / "invoice.txt"
    sample.write_text("Invoice 100\nAmount 20\n", encoding="utf-8")
    monkeypatch.setattr(ai_pc_demo_calibration, "get_extraction_policy", lambda: {"airplane_mode_enabled": True, "cloud_escalation_allowed": False, "local_agent_escalation_allowed": True})

    result = ai_pc_demo_calibration.score_file(sample)

    assert result["path"] == str(sample)
    assert result["cloud_allowed"] is False
    assert result["text_present"] is True
    assert result["score"] >= 1
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_ai_pc_demo_calibration.py -q
```

Expected: fail because calibration module is missing.

- [ ] **Step 3: Add calibration module**

Create `skills/ingest/scripts/ai_pc_demo_calibration.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.lib.extraction import extract, get_extraction_policy


def score_file(path: Path) -> dict[str, Any]:
    policy = get_extraction_policy()
    result = extract(str(path), max_tier=1)
    text = result.markdown.strip() if result.success else ""
    score = 0
    if text:
        score += 1
    if any(char.isdigit() for char in text):
        score += 1
    if len(text.split()) >= 4:
        score += 1
    return {
        "path": str(path),
        "success": result.success,
        "method": f"document-extractor:{result.tier_used}",
        "ocr_applied": result.ocr_applied,
        "needs_llm": result.needs_llm,
        "cloud_allowed": bool(policy["cloud_escalation_allowed"]),
        "text_present": bool(text),
        "score": score,
    }


def score_folder(path: Path) -> dict[str, Any]:
    files = [item for item in sorted(path.iterdir()) if item.is_file()]
    results = [score_file(item) for item in files]
    return {
        "folder": str(path),
        "files": results,
        "average_score": sum(item["score"] for item in results) / len(results) if results else 0.0,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    args = parser.parse_args(argv)
    target = Path(args.path)
    payload = score_folder(target) if target.is_dir() else score_file(target)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run calibration tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_ai_pc_demo_calibration.py -q
```

Expected: selected tests pass.

- [ ] **Step 5: Run calibration smoke on a temp file**

Run:

```powershell
$tmp = New-Item -ItemType Directory -Force "$env:TEMP\augur-ai-pc-demo"
Set-Content -Path "$tmp\invoice.txt" -Value "Invoice 100`nAmount 20"
.\.venv\Scripts\python.exe skills\ingest\scripts\ai_pc_demo_calibration.py "$tmp"
```

Expected: JSON output with one file and `average_score` greater than `0`.

- [ ] **Step 6: Commit**

Run:

```powershell
git add skills\ingest\scripts\ai_pc_demo_calibration.py skills\ingest\augur\tests\test_ai_pc_demo_calibration.py
git -c user.name='Gur Sannikov' -c user.email='gsannikov@users.noreply.github.com' commit -m "feat(ingest): add AI PC demo calibration probe"
```

Expected: commit succeeds and pre-commit passes.

---

### Task 11: End-To-End Verification

**Files:**
- Modify only if verification exposes a real bug

- [ ] **Step 1: Run backend test slice**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\document-extractor\augur\tests\test_capabilities.py skills\document-extractor\augur\tests\test_audio_extractor.py skills\document-extractor\augur\tests\test_tools_extract.py skills\ingest\augur\tests -q
```

Expected: all selected backend tests pass.

- [ ] **Step 2: Run dashboard test slice**

Run:

```powershell
Set-Location apps\dashboard
pnpm test -- --runTestsByPath ..\..\tests\dashboard\brain\inbox-page.test.tsx ..\..\tests\dashboard\brain\insights-page.test.tsx
Set-Location ..\..
```

Expected: selected Jest tests pass.

- [ ] **Step 3: Run lint/build through repository workflows**

Run the canonical slash commands from an Augur-capable client:

```text
/auto-lint
/dev-build
```

Expected: lint and build pass. If `/dev-build` reports a browser/client error, fix the cause and rerun `/dev-build`.

- [ ] **Step 4: Browser-verify dashboard pages**

Use the browser tool against the dashboard after `/dev-build` or the running dev server:

```text
Open /brain/inbox
Open /brain/insights
```

Expected:

- both pages load to interactive state
- no chunk-load error boundary appears
- Inbox shows folders, recent runs, and backend evidence when MCP returns it
- Insights shows local/cloud counters and wiki action state
- no visible text overflow or incoherent overlap at desktop and mobile widths

- [ ] **Step 5: Run local Desktop-style smoke test in a temp folder**

Run:

```powershell
$root = New-Item -ItemType Directory -Force "$env:TEMP\augur-inbox-smoke"
Set-Content -Path "$root\invoice.txt" -Value "Invoice 1042`nAmount due 1200`nPayment due 2026-05-30"
@'
from pathlib import Path
from skills.ingest.scripts.inbox_store import InboxStore
from skills.ingest.scripts.inbox_consume import consume_folder

root = Path.home() / "AppData" / "Local" / "Temp" / "augur-inbox-smoke"
store = InboxStore(root / "state")
folder = store.add_folder(name="Smoke", path=root)
record = consume_folder(store=store, folder_id=folder.id)
print(record.status)
print(record.files_indexed)
print(record.cloud_calls)
'@ | .\.venv\Scripts\python.exe -
```

Expected:

```text
success
1
0
```

- [ ] **Step 6: Inspect git status**

Run:

```powershell
git status --short --branch
```

Expected: branch is ahead of `origin/main` with only committed work, or clean after a final verification-fix commit.

- [ ] **Step 7: Final commit for verification fixes**

If verification required fixes, commit them:

```powershell
git add pyproject.toml src\lib\extraction skills\document-extractor skills\ingest apps\dashboard\features\pages\brain tests\dashboard\brain tests\dashboard\visual
git -c user.name='Gur Sannikov' -c user.email='gsannikov@users.noreply.github.com' commit -m "fix(ingest): stabilize AI PC brain inbox verification"
```

Expected: commit succeeds and pre-commit passes.

---

## Plan Self-Review

Spec coverage:

- Local-first Desktop consume workflow: Tasks 4, 5, 6, 7, 8, 9, 11.
- OCR/transcription capability ladder: Tasks 2, 3, 10.
- Airplane mode cloud gate with local Ollama allowed: Tasks 2, 7, 9, 11.
- Source cards and RAG descriptions: Tasks 6, 7, 11.
- Brain Inbox/Insights dashboard payoff: Tasks 8, 9, 11.
- Calibration instead of assuming local vision quality: Task 10.
- Browser/client verification for dashboard work: Task 11.

Type consistency:

- Python run/file fields match the TypeScript additions: `cloud_calls`, `local_agent_calls`, `files_needing_review`, `airplane_mode`, `file_results`.
- MCP names match existing dashboard hooks: `inbox-folders`, `inbox-scan-folder`, `inbox-consume-folder`, `brain-insights`.
- Runtime state and vault writes use path helpers rather than hardcoded machine paths in production code.
