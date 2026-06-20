# Demo-Ready Investor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the real, repeatable investor demo path defined in `docs/superpowers/specs/2026-05-07-demo-ready-investor-goal-design.md`.

**Architecture:** Keep Brain Inbox as the product orchestration layer. Add a demo reset/readiness module, extend extraction results with local/cloud evidence, wire consume to policy-controlled cloud vision escalation, persist extracted/transcribed artifacts, and expose evidence through MCP and the Brain dashboard. Verification must run against real files and real runtime state.

**Tech Stack:** Python 3.12 via `.venv\Scripts\python.exe`, pytest, FastMCP skill tools, MarkItDown, PyMuPDF/pdf2image/Tesseract when available, local Ollama vision, unified `src.lib.ai` cloud vision client, unified RAG indexer/search, Next.js/React/TypeScript/Jest, Playwright.

---

## Scope Check

This plan is one cohesive demo-readiness increment. It touches multiple layers, but each task produces a testable checkpoint toward the same user-facing workflow:

- reset and readiness
- real extraction/escalation evidence
- real consume artifacts
- real meeting memory output
- real RAG proof
- dashboard evidence
- end-to-end verification

Do not start by polishing UI. The priority is proving the real pipeline.

## File Structure Map

- `skills/ingest/scripts/demo_ready.py` — new demo fixture, reset, readiness, and smoke orchestration module.
- `skills/ingest/augur/tests/test_demo_ready.py` — new tests for reset/readiness and no-cheat smoke payloads.
- `src/lib/extraction/extractor.py` — extend `ExtractionResult` and `extract()` with backend, cloud, local-agent, and escalation metadata.
- `src/lib/extraction/cloud_vision.py` — new cloud vision helper using `src.lib.extraction.ollama_client.get_vision_client()`.
- `shared-vault/skills/document-extractor/augur/tests/test_cloud_escalation.py` — new extraction tests for airplane/cloud policy behavior.
- `skills/ingest/scripts/inbox_models.py` — extend run/file records with extracted artifact and escalation evidence fields.
- `skills/ingest/scripts/inbox_consume.py` — pass cloud policy into extraction, write extracted/transcribed artifacts, count cloud/local calls.
- `skills/ingest/scripts/source_cards.py` — enrich source cards with extracted artifact links, escalation evidence, and meeting action sections.
- `skills/ingest/scripts/meeting_memory.py` — new deterministic meeting summary/action extraction from transcript markdown.
- `skills/ingest/scripts/rag_demo_verify.py` — new RAG proof helper for demo readiness.
- `skills/ingest/scripts/mcp/inbox_tools.py` — expose reset/readiness/smoke tools through MCP.
- `skills/ingest/SKILL.md` — declare the new MCP tools.
- `apps/dashboard/features/pages/brain/inbox/types.ts` — add fields used by run evidence.
- `apps/dashboard/features/pages/brain/inbox/page.tsx` — show readiness and richer file evidence.
- `apps/dashboard/features/pages/brain/insights/types.ts` — add fields used by insights evidence.
- `apps/dashboard/features/pages/brain/insights/page.tsx` — show RAG proof and cloud/local evidence.
- `tests/dashboard/brain/inbox-page.test.tsx` — assert demo evidence renders.
- `tests/dashboard/brain/insights-page.test.tsx` — assert RAG proof and escalation evidence render.
- `scripts/verify_ai_pc_demo.py` — command-line pre-demo verification wrapper.

---

### Task 1: Demo Reset And Readiness Module

**Files:**
- Create: `skills/ingest/scripts/demo_ready.py`
- Create: `skills/ingest/augur/tests/test_demo_ready.py`
- Modify: `skills/ingest/SKILL.md`

- [ ] **Step 1: Write failing reset/readiness tests**

Create `skills/ingest/augur/tests/test_demo_ready.py`:

```python
from __future__ import annotations

import json
from pathlib import Path


def test_prepare_demo_state_creates_seeded_desktop_and_folder(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import demo_ready
    from skills.ingest.scripts.inbox_store import InboxStore

    desktop = tmp_path / "Desktop"
    store_root = tmp_path / "state"
    vault = tmp_path / "vault"
    preferences = tmp_path / "preferences.yaml"

    state = demo_ready.prepare_demo_state(
        desktop=desktop,
        store_root=store_root,
        vault_dir=vault,
        preferences_path=preferences,
        airplane_mode=True,
    )

    assert state["success"] is True
    assert state["desktop"] == str(desktop)
    assert sorted(Path(item).name for item in state["files"]) == [
        "demo-hard-photo.png",
        "demo-invoice.txt",
        "demo-meeting.mp3",
        "demo-medical-note.txt",
    ]
    assert "enabled: true" in preferences.read_text(encoding="utf-8")
    folders = InboxStore(store_root).list_folders()
    assert len(folders) == 1
    assert folders[0].name == "Demo Desktop"
    assert folders[0].path == str(desktop.resolve(strict=False))


def test_readiness_fails_when_cloud_profile_missing(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import demo_ready

    monkeypatch.setattr(
        demo_ready,
        "detect_extraction_capabilities",
        lambda use_cache=False, probe_timeout_s=5: {
            "packages": {"markitdown": {"installed": True}},
            "commands": {"ffmpeg": "ffmpeg.exe", "ollama": "ollama.exe"},
            "ocr_ready": True,
            "transcription_ready": True,
            "local_agent_ready": True,
            "ollama": {"vision_models": ["gemma4:latest"]},
            "policy": {"airplane_mode_enabled": False, "cloud_escalation_allowed": True},
        },
    )
    monkeypatch.setattr(demo_ready, "get_vision_client", lambda: None)

    result = demo_ready.check_demo_readiness(desktop=tmp_path, require_cloud=True)

    assert result["ready"] is False
    assert "cloud vision profile is not available" in result["failures"]


def test_main_prints_json(monkeypatch, tmp_path: Path, capsys) -> None:
    from skills.ingest.scripts import demo_ready

    monkeypatch.setattr(
        demo_ready,
        "prepare_demo_state",
        lambda **kwargs: {"success": True, "desktop": str(kwargs["desktop"]), "files": []},
    )

    code = demo_ready.main(["reset", "--desktop", str(tmp_path / "Desktop")])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_demo_ready.py -q
```

Expected: fail with `ImportError` or `ModuleNotFoundError` for `skills.ingest.scripts.demo_ready`.

- [ ] **Step 3: Implement demo reset/readiness module**

Create `skills/ingest/scripts/demo_ready.py`:

```python
from __future__ import annotations

import argparse
import base64
import json
import shutil
from pathlib import Path
from typing import Any

from src.config.paths import get_runtime_dir, get_vault_dir
from src.config.preferences import get_preferences_path
from src.lib.extraction import detect_extraction_capabilities
from src.lib.extraction.ollama_client import get_vision_client

from skills.ingest.scripts.inbox_store import InboxStore

_PNG_1X1 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_demo_mp3(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"ID3\x03\x00\x00\x00\x00\x00\x21"
        b"TIT2\x00\x00\x00\x17\x00\x00\x03Demo meeting audio\x00"
        b"\xff\xfb\x90d" + (b"\x00" * 2048)
    )


def _clear_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_file():
        path.unlink()
        return
    for child in sorted(path.iterdir(), reverse=True):
        _clear_path(child)
    path.rmdir()


def _write_preferences(path: Path, *, airplane_mode: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "airplane_mode:\n"
        f"  enabled: {'true' if airplane_mode else 'false'}\n",
        encoding="utf-8",
    )


def prepare_demo_state(
    *,
    desktop: Path,
    store_root: Path,
    vault_dir: Path,
    preferences_path: Path,
    airplane_mode: bool,
) -> dict[str, Any]:
    _clear_path(desktop)
    desktop.mkdir(parents=True, exist_ok=True)
    vault_dir.mkdir(parents=True, exist_ok=True)
    _write_preferences(preferences_path, airplane_mode=airplane_mode)

    invoice = desktop / "demo-invoice.txt"
    medical = desktop / "demo-medical-note.txt"
    hard_photo = desktop / "demo-hard-photo.png"
    meeting = desktop / "demo-meeting.mp3"

    _write_text(
        invoice,
        "Invoice\nVendor: Northwind Labs\nAmount: 1842.25\nDue: 2026-05-20\n",
    )
    _write_text(
        medical,
        "Clinic visit note\nProvider: City Health Clinic\nAction: submit insurance form\n",
    )
    hard_photo.write_bytes(base64.b64decode(_PNG_1X1))
    _write_demo_mp3(meeting)

    store = InboxStore(store_root)
    store.add_folder(name="Demo Desktop", path=desktop)

    return {
        "success": True,
        "desktop": str(desktop),
        "store_root": str(store_root),
        "vault_dir": str(vault_dir),
        "airplane_mode": airplane_mode,
        "files": [str(invoice), str(medical), str(hard_photo), str(meeting)],
    }


def check_demo_readiness(*, desktop: Path, require_cloud: bool) -> dict[str, Any]:
    inventory = detect_extraction_capabilities(use_cache=False, probe_timeout_s=5)
    failures: list[str] = []

    if not desktop.exists():
        failures.append(f"desktop inbox does not exist: {desktop}")
    if not inventory.get("packages", {}).get("markitdown", {}).get("installed"):
        failures.append("markitdown is not installed")
    if not inventory.get("transcription_ready"):
        failures.append("local transcription is not ready")
    if not inventory.get("local_agent_ready"):
        failures.append("local vision or local agent backend is not ready")
    if require_cloud and get_vision_client() is None:
        failures.append("cloud vision profile is not available")

    return {
        "ready": not failures,
        "failures": failures,
        "desktop": str(desktop),
        "capabilities": inventory,
    }


def _default_desktop() -> Path:
    return Path.home() / "Desktop" / "Augur Demo Inbox"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare or check the AI PC demo state.")
    sub = parser.add_subparsers(dest="command", required=True)

    reset = sub.add_parser("reset")
    reset.add_argument("--desktop", type=Path, default=_default_desktop())
    reset.add_argument("--airplane", choices=["on", "off"], default="on")

    ready = sub.add_parser("ready")
    ready.add_argument("--desktop", type=Path, default=_default_desktop())
    ready.add_argument("--require-cloud", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "reset":
        payload = prepare_demo_state(
            desktop=args.desktop,
            store_root=get_runtime_dir() / "brain" / "inbox",
            vault_dir=get_vault_dir(),
            preferences_path=get_preferences_path(),
            airplane_mode=args.airplane == "on",
        )
    else:
        payload = check_demo_readiness(
            desktop=args.desktop,
            require_cloud=bool(args.require_cloud),
        )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload.get("success", payload.get("ready", False)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Declare MCP tools in skill metadata**

Modify `skills/ingest/SKILL.md` and add these entries under `x-augur-mcp-tools`:

```yaml
  - demo-reset
  - demo-readiness
  - demo-smoke
```

- [ ] **Step 5: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_demo_ready.py -q
```

Expected: `3 passed`.

- [ ] **Step 6: Commit**

```powershell
git add skills\ingest\scripts\demo_ready.py skills\ingest\augur\tests\test_demo_ready.py skills\ingest\SKILL.md
git -c user.name='Gur Sannikov' -c user.email='gsannikov@users.noreply.github.com' commit -m "feat(ingest): add AI PC demo reset readiness"
```

---

### Task 2: Cloud Vision Escalation In Extraction

**Files:**
- Create: `src/lib/extraction/cloud_vision.py`
- Modify: `src/lib/extraction/extractor.py`
- Modify: `src/lib/extraction/__init__.py`
- Test: `shared-vault/skills/document-extractor/augur/tests/test_cloud_escalation.py`

- [ ] **Step 1: Write failing cloud escalation tests**

Create `shared-vault/skills/document-extractor/augur/tests/test_cloud_escalation.py`:

```python
from __future__ import annotations

from pathlib import Path


class FakeVisionClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate_with_vision(self, *, prompt: str, images: list[bytes | str], **kwargs) -> str:
        self.calls.append({"prompt": prompt, "images": images, "kwargs": kwargs})
        return "Cloud OCR text: Invoice total 1842.25 due 2026-05-20."


def test_extract_uses_cloud_vision_when_allowed(monkeypatch, tmp_path: Path) -> None:
    from src.lib.extraction import cloud_vision, extractor

    image = tmp_path / "scan.png"
    image.write_bytes(b"not-a-real-image-but-request-builder-reads-bytes")
    client = FakeVisionClient()

    monkeypatch.setattr(extractor, "_get_markitdown", lambda: (_ for _ in ()).throw(RuntimeError("no local text")))
    monkeypatch.setattr(extractor, "_try_tesseract", lambda _path: None)
    monkeypatch.setattr(extractor, "_run_ollama_ocr", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(cloud_vision, "get_vision_client", lambda: client)

    result = extractor.extract(str(image), max_tier=1, allow_cloud=True)

    assert result.success is True
    assert result.cloud_used is True
    assert result.local_agent_used is False
    assert result.escalation_reason == "local OCR and local vision did not produce usable text"
    assert "Invoice total" in result.markdown
    assert len(client.calls) == 1


def test_extract_blocks_cloud_when_not_allowed(monkeypatch, tmp_path: Path) -> None:
    from src.lib.extraction import cloud_vision, extractor

    image = tmp_path / "scan.png"
    image.write_bytes(b"scan")
    client = FakeVisionClient()

    monkeypatch.setattr(extractor, "_get_markitdown", lambda: (_ for _ in ()).throw(RuntimeError("no local text")))
    monkeypatch.setattr(extractor, "_try_tesseract", lambda _path: None)
    monkeypatch.setattr(extractor, "_run_ollama_ocr", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(cloud_vision, "get_vision_client", lambda: client)

    result = extractor.extract(str(image), max_tier=1, allow_cloud=False)

    assert result.cloud_used is False
    assert result.needs_llm is False
    assert result.markdown == ""
    assert client.calls == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest shared-vault\skills\document-extractor\augur\tests\test_cloud_escalation.py -q
```

Expected: fail because `extract()` does not accept `allow_cloud` and `ExtractionResult` has no cloud fields.

- [ ] **Step 3: Add cloud vision helper**

Create `src/lib/extraction/cloud_vision.py`:

```python
from __future__ import annotations

import base64
from dataclasses import dataclass

from src.lib.extraction.ollama_client import get_vision_client


@dataclass(frozen=True)
class CloudVisionResult:
    success: bool
    results: dict[str, str]
    provider: str
    model: str | None
    error: str | None = None


def run_cloud_vision_ocr(
    requests: list[dict[str, str]],
    *,
    reason: str,
) -> CloudVisionResult:
    client = get_vision_client()
    if client is None:
        return CloudVisionResult(
            success=False,
            results={},
            provider="",
            model=None,
            error="cloud vision client is not configured",
        )

    merged: dict[str, str] = {}
    for request in requests:
        raw_image = base64.b64decode(request["image_b64"])
        text = client.generate_with_vision(
            prompt=f"{request['prompt']}\n\nEscalation reason: {reason}",
            images=[raw_image],
            temperature=0,
            max_tokens=2000,
        ).strip()
        if not text:
            return CloudVisionResult(
                success=False,
                results=merged,
                provider=type(client).__name__,
                model=getattr(client, "default_model", None),
                error=f"cloud vision returned empty text for request {request.get('request_id', '')}",
            )
        merged[request["request_id"]] = text

    return CloudVisionResult(
        success=True,
        results=merged,
        provider=type(client).__name__,
        model=getattr(client, "default_model", None),
    )
```

- [ ] **Step 4: Extend `ExtractionResult` and `extract()`**

Modify `src/lib/extraction/extractor.py`:

```python
from src.lib.extraction.cloud_vision import run_cloud_vision_ocr
```

Change `ExtractionResult` to:

```python
@dataclass
class ExtractionResult:
    success: bool
    markdown: str
    title: str
    tier_used: int
    format: str
    size_bytes: int
    extraction_time: float
    ocr_applied: bool
    needs_llm: bool = False
    llm_requests: list[dict] | None = None
    partial_markdown: str | None = None
    error: str | None = None
    cloud_used: bool = False
    local_agent_used: bool = False
    escalation_reason: str | None = None
    cloud_provider: str | None = None
    cloud_model: str | None = None
    hardware_backend: str = "local"
```

Change `extract()` signature to:

```python
def extract(
    path: str,
    max_tier: int = 1,
    *,
    audio_model_dir: str | None = None,
    allow_cloud: bool = False,
) -> ExtractionResult:
```

Change every call to `_request_llm_ocr(...)` so it passes `allow_cloud=allow_cloud`.

In the image exception branch of `extract()`, call `_request_llm_ocr(...)` when tier 1 is allowed instead of returning a successful empty markdown result:

```python
        if fmt in IMAGE_FORMATS and max_tier >= 1:
            return _request_llm_ocr(
                file_path,
                fmt,
                size,
                elapsed,
                "",
                allow_cloud=allow_cloud,
            )
```

Change `_request_llm_ocr()` signature to:

```python
def _request_llm_ocr(
    file_path: Path,
    fmt: str,
    size: int,
    elapsed: float,
    partial: str,
    *,
    allow_cloud: bool,
) -> ExtractionResult:
```

Inside `_request_llm_ocr()`, after local Ollama fails and before the AI-client return, add:

```python
    escalation_reason = "local OCR and local vision did not produce usable text"
    if allow_cloud:
        cloud = run_cloud_vision_ocr(llm_requests, reason=escalation_reason)
        if cloud.success:
            return ExtractionResult(
                success=True,
                markdown=merge_llm_results(partial_markdown, cloud.results),
                title=file_path.stem,
                tier_used=1,
                format=fmt,
                size_bytes=size,
                extraction_time=elapsed,
                ocr_applied=True,
                cloud_used=True,
                local_agent_used=False,
                escalation_reason=escalation_reason,
                cloud_provider=cloud.provider,
                cloud_model=cloud.model,
                hardware_backend="cloud-vision",
            )
```

In the local Ollama success return, add:

```python
            local_agent_used=True,
            hardware_backend="ollama-vision",
```

In the AI-client `needs_llm=True` return, add:

```python
            local_agent_used=True,
            escalation_reason="local agent OCR required",
            hardware_backend="agent-vision",
```

- [ ] **Step 5: Export helper**

Modify `src/lib/extraction/__init__.py` and export `CloudVisionResult` and `run_cloud_vision_ocr`.

- [ ] **Step 6: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest shared-vault\skills\document-extractor\augur\tests\test_cloud_escalation.py shared-vault\skills\document-extractor\augur\tests\test_extractor.py shared-vault\skills\document-extractor\augur\tests\test_tools_extract.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```powershell
git add src\lib\extraction\cloud_vision.py src\lib\extraction\extractor.py src\lib\extraction\__init__.py shared-vault\skills\document-extractor\augur\tests\test_cloud_escalation.py
git -c user.name='Gur Sannikov' -c user.email='gsannikov@users.noreply.github.com' commit -m "feat(extraction): add policy-controlled cloud vision escalation"
```

---

### Task 3: Persist Extracted Artifacts And File-Level Evidence

**Files:**
- Modify: `skills/ingest/scripts/inbox_models.py`
- Modify: `skills/ingest/scripts/inbox_store.py`
- Modify: `skills/ingest/scripts/inbox_consume.py`
- Modify: `skills/ingest/scripts/source_cards.py`
- Test: `skills/ingest/augur/tests/test_inbox_consume.py`
- Test: `skills/ingest/augur/tests/test_inbox_store.py`

- [ ] **Step 1: Add failing consume evidence test**

Append to `skills/ingest/augur/tests/test_inbox_consume.py`:

```python
def test_consume_writes_extracted_artifact_and_cloud_evidence(monkeypatch, tmp_path):
    from src.lib.extraction import ExtractionResult
    from skills.ingest.scripts import inbox_consume
    from skills.ingest.scripts.inbox_store import InboxStore

    inbox = tmp_path / "Desktop"
    inbox.mkdir()
    source = inbox / "demo-hard-photo.png"
    source.write_bytes(b"image")
    _mark_stable(source)
    vault = tmp_path / "vault"
    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=inbox)

    monkeypatch.setattr(inbox_consume, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(inbox_consume, "get_rag_dir", lambda: tmp_path / "rag")
    monkeypatch.setattr(inbox_consume, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(inbox_consume, "reindex_category", lambda *args, **kwargs: 1)
    monkeypatch.setattr(
        inbox_consume,
        "get_extraction_policy",
        lambda: {
            "airplane_mode_enabled": False,
            "cloud_escalation_allowed": True,
            "local_agent_escalation_allowed": True,
        },
    )

    def fake_extract(path, max_tier=1, **kwargs):
        assert kwargs["allow_cloud"] is True
        return ExtractionResult(
            success=True,
            markdown="Cloud OCR text invoice amount 1842.25",
            title="Cloud invoice",
            tier_used=1,
            format="png",
            size_bytes=5,
            extraction_time=0.1,
            ocr_applied=True,
            cloud_used=True,
            escalation_reason="local OCR and local vision did not produce usable text",
            cloud_provider="FakeVisionClient",
            cloud_model="gpt-vision-demo",
            hardware_backend="cloud-vision",
        )

    monkeypatch.setattr(inbox_consume, "extract", fake_extract)

    record = inbox_consume.consume_folder(store=store, folder_id=folder.id)

    result = record.file_results[0]
    assert record.cloud_calls == 1
    assert result.cloud_used is True
    assert result.escalation_reason == "local OCR and local vision did not produce usable text"
    assert result.cloud_provider == "FakeVisionClient"
    assert Path(result.extracted_path).exists()
    assert "Cloud OCR text" in Path(result.extracted_path).read_text(encoding="utf-8")
    assert "Cloud OCR text" in Path(result.source_card_path).read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_inbox_consume.py::test_consume_writes_extracted_artifact_and_cloud_evidence -q
```

Expected: fail because `InboxFileResult` has no `extracted_path`, `escalation_reason`, `cloud_provider`, or `cloud_model`.

- [ ] **Step 3: Extend models**

Modify `InboxFileResult` in `skills/ingest/scripts/inbox_models.py`:

```python
@dataclass
class InboxFileResult:
    source_path: str
    final_path: str
    source_card_path: str
    content_type: str
    extraction_method: str
    hardware_backend: str
    confidence: str
    route: str
    renamed_to: str
    rag_indexed: bool
    status: str
    document_kind: str | None = None
    route_reason: str | None = None
    extracted_path: str | None = None
    local_agent_used: bool = False
    cloud_used: bool = False
    escalation_reason: str | None = None
    cloud_provider: str | None = None
    cloud_model: str | None = None
    content_hash: str | None = None
    review_reason: str | None = None
    error: str | None = None
```

Modify `_run_from_dict()` in `skills/ingest/scripts/inbox_store.py` so old run JSON remains readable:

```python
        file_results = []
        for item in data.get("file_results", []):
            if isinstance(item, InboxFileResult):
                file_results.append(item)
            else:
                item.setdefault("extracted_path", None)
                item.setdefault("escalation_reason", None)
                item.setdefault("cloud_provider", None)
                item.setdefault("cloud_model", None)
                item.setdefault("content_hash", None)
                file_results.append(InboxFileResult(**item))
```

- [ ] **Step 4: Add artifact writer in consume**

In `skills/ingest/scripts/inbox_consume.py`, add:

```python
def _write_extracted_artifact(
    *,
    vault_dir: Path,
    decision_filename: str,
    body: str,
    content_type: str,
) -> Path:
    suffix = ".transcript.md" if content_type == "audio" else ".extracted.md"
    target = _unique_destination_path(
        vault_dir / "sources" / "extracted" / f"{Path(decision_filename).stem}{suffix}"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target
```

Change the extraction call in `consume_folder()` to:

```python
            extracted = extract(
                str(source),
                max_tier=1,
                allow_cloud=bool(policy.get("cloud_escalation_allowed", False)),
            )
```

After `actual_decision = replace(...)`, before `shutil.move(...)`, add:

```python
            extracted_artifact = _write_extracted_artifact(
                vault_dir=vault_dir,
                decision_filename=actual_decision.filename,
                body=body,
                content_type=content_type,
            )
```

Pass `extracted_path=str(extracted_artifact)` into `write_source_card(...)`.

When creating the success `InboxFileResult`, set:

```python
                extracted_path=str(extracted_artifact),
                local_agent_used=bool(getattr(extracted, "local_agent_used", False) or extracted.needs_llm),
                cloud_used=bool(getattr(extracted, "cloud_used", False)),
                escalation_reason=getattr(extracted, "escalation_reason", None),
                cloud_provider=getattr(extracted, "cloud_provider", None),
                cloud_model=getattr(extracted, "cloud_model", None),
```

In `_save_record()`, change cloud count to:

```python
        cloud_calls=sum(1 for result in file_results if result.cloud_used),
```

- [ ] **Step 5: Enrich source-card signature and body**

Modify `write_source_card()` signature in `skills/ingest/scripts/source_cards.py`:

```python
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
    escalation_reason: str | None = None,
    cloud_used: bool = False,
    cloud_provider: str | None = None,
    cloud_model: str | None = None,
    content_hash: str | None = None,
) -> Path:
```

Add these metadata fields:

```python
        "cloud_used": cloud_used,
        "cloud_provider": cloud_provider,
        "cloud_model": cloud_model,
        "escalation_reason": escalation_reason,
```

Add this section to `card_body` after `## Routing`:

```markdown

## Processing Evidence

- Method: `{extraction_method}`
- Backend: `{hardware_backend}`
- Confidence: `{confidence}`
- Cloud used: `{str(cloud_used).lower()}`
- Cloud provider: `{cloud_provider or ''}`
- Cloud model: `{cloud_model or ''}`
- Escalation reason: {escalation_reason or ''}
```

- [ ] **Step 6: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_inbox_consume.py skills\ingest\augur\tests\test_inbox_store.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```powershell
git add skills\ingest\scripts\inbox_models.py skills\ingest\scripts\inbox_store.py skills\ingest\scripts\inbox_consume.py skills\ingest\scripts\source_cards.py skills\ingest\augur\tests\test_inbox_consume.py skills\ingest\augur\tests\test_inbox_store.py
git -c user.name='Gur Sannikov' -c user.email='gsannikov@users.noreply.github.com' commit -m "feat(ingest): persist demo extraction evidence"
```

---

### Task 4: Meeting Transcript Memory Output

**Files:**
- Create: `skills/ingest/scripts/meeting_memory.py`
- Modify: `skills/ingest/scripts/source_cards.py`
- Test: `skills/ingest/augur/tests/test_meeting_memory.py`
- Test: `skills/ingest/augur/tests/test_source_cards.py`

- [ ] **Step 1: Write failing meeting memory tests**

Create `skills/ingest/augur/tests/test_meeting_memory.py`:

```python
from __future__ import annotations


def test_build_meeting_memory_extracts_summary_and_actions() -> None:
    from skills.ingest.scripts.meeting_memory import build_meeting_memory

    memory = build_meeting_memory(
        "Discussed investor demo readiness. "
        "Decision: use airplane mode first. "
        "Action: Gur will prepare fixture pack. "
        "Follow-up: verify cloud escalation evidence."
    )

    assert memory["summary"].startswith("Discussed investor demo readiness")
    assert memory["decisions"] == ["use airplane mode first."]
    assert memory["next_actions"] == [
        "Gur will prepare fixture pack.",
        "verify cloud escalation evidence.",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_meeting_memory.py -q
```

Expected: fail because `meeting_memory.py` does not exist.

- [ ] **Step 3: Implement deterministic meeting memory helper**

Create `skills/ingest/scripts/meeting_memory.py`:

```python
from __future__ import annotations

import re


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]


def _strip_label(sentence: str, labels: tuple[str, ...]) -> str:
    pattern = "|".join(re.escape(label) for label in labels)
    return re.sub(rf"^({pattern})\s*:\s*", "", sentence, flags=re.IGNORECASE).strip()


def build_meeting_memory(transcript_markdown: str) -> dict[str, list[str] | str]:
    text = re.sub(r"^# .*$", "", transcript_markdown, flags=re.MULTILINE)
    text = re.sub(r"^(Method|Backend|Confidence|Language|Duration seconds):.*$", "", text, flags=re.MULTILINE)
    sentences = _sentences(re.sub(r"\s+", " ", text))
    summary = " ".join(sentences[:2]) if sentences else "No transcript summary was captured."
    decisions = [
        _strip_label(sentence, ("decision", "decided"))
        for sentence in sentences
        if sentence.lower().startswith(("decision:", "decided:"))
    ]
    next_actions = [
        _strip_label(sentence, ("action", "follow-up", "follow up"))
        for sentence in sentences
        if sentence.lower().startswith(("action:", "follow-up:", "follow up:"))
    ]
    return {
        "summary": summary,
        "decisions": decisions,
        "next_actions": next_actions,
    }
```

- [ ] **Step 4: Add meeting sections to source cards**

In `skills/ingest/scripts/source_cards.py`, import:

```python
from skills.ingest.scripts.meeting_memory import build_meeting_memory
```

Before `write_vault_frontmatter(...)`, add:

```python
    meeting_section = ""
    if content_type == "audio":
        meeting = build_meeting_memory(body)
        actions = "\n".join(f"- [ ] {item}" for item in meeting["next_actions"])
        decisions = "\n".join(f"- {item}" for item in meeting["decisions"])
        meeting_section = f"""

## Meeting Memory

{meeting["summary"]}

### Decisions

{decisions or "- None detected"}

### Action Items

{actions or "- [ ] Review transcript for actions"}
"""
```

Append `{meeting_section}` to the end of `card_body`.

- [ ] **Step 5: Add source-card test**

Append to `skills/ingest/augur/tests/test_source_cards.py`:

```python
def test_audio_source_card_contains_meeting_memory(tmp_path):
    from skills.ingest.scripts.inbox_routing import RouteDecision
    from skills.ingest.scripts.source_cards import write_source_card

    card = write_source_card(
        vault_dir=tmp_path,
        title="Investor demo meeting",
        body="Decision: use airplane mode first. Action: Gur will prepare fixture pack.",
        decision=RouteDecision(route="meetings", filename="2026-05-07-investor-demo.mp3", reason="Audio meeting or recording detected."),
        original_path="C:/Desktop/demo-meeting.mp3",
        final_path=str(tmp_path / "meetings" / "2026-05-07-investor-demo.mp3"),
        extracted_path=str(tmp_path / "sources" / "extracted" / "2026-05-07-investor-demo.transcript.md"),
        extraction_method="document-extractor:0",
        hardware_backend="local",
        confidence="high",
        content_type="audio",
    )

    text = card.read_text(encoding="utf-8")
    assert "## Meeting Memory" in text
    assert "- use airplane mode first." in text
    assert "- [ ] Gur will prepare fixture pack." in text
```

- [ ] **Step 6: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_meeting_memory.py skills\ingest\augur\tests\test_source_cards.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```powershell
git add skills\ingest\scripts\meeting_memory.py skills\ingest\scripts\source_cards.py skills\ingest\augur\tests\test_meeting_memory.py skills\ingest\augur\tests\test_source_cards.py
git -c user.name='Gur Sannikov' -c user.email='gsannikov@users.noreply.github.com' commit -m "feat(ingest): add meeting memory source cards"
```

---

### Task 5: RAG Proof For Demo Readiness

**Files:**
- Create: `skills/ingest/scripts/rag_demo_verify.py`
- Modify: `skills/ingest/scripts/brain_insights.py`
- Test: `skills/ingest/augur/tests/test_rag_demo_verify.py`
- Test: `skills/ingest/augur/tests/test_brain_insights.py`

- [ ] **Step 1: Write failing RAG proof test**

Create `skills/ingest/augur/tests/test_rag_demo_verify.py`:

```python
from __future__ import annotations


def test_verify_demo_rag_returns_hits(monkeypatch) -> None:
    from skills.ingest.scripts import rag_demo_verify

    class FakeSearcher:
        def search(self, query, scopes=None, top_k=5):
            assert query == "investor demo meeting"
            assert scopes == ["rag"]
            return [{"file": "vault/sources/files/demo.md", "content": "investor demo meeting"}]

    monkeypatch.setattr(rag_demo_verify, "UnifiedSearcher", lambda scopes=None: FakeSearcher())

    result = rag_demo_verify.verify_demo_rag("investor demo meeting")

    assert result["query"] == "investor demo meeting"
    assert result["hit_count"] == 1
    assert result["hits"][0]["file"] == "vault/sources/files/demo.md"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_rag_demo_verify.py -q
```

Expected: fail because `rag_demo_verify.py` does not exist.

- [ ] **Step 3: Implement RAG proof helper**

Create `skills/ingest/scripts/rag_demo_verify.py`:

```python
from __future__ import annotations

from typing import Any

from src.lib.knowledge.unified_search import UnifiedSearcher


def verify_demo_rag(query: str, *, top_k: int = 5) -> dict[str, Any]:
    hits = UnifiedSearcher(scopes=["rag"]).search(query, scopes=["rag"], top_k=top_k)
    compact = [
        {
            "file": str(hit.get("file", "")),
            "line": str(hit.get("line", "")),
            "content": str(hit.get("content", ""))[:240],
            "scope": str(hit.get("scope", "rag")),
        }
        for hit in hits
    ]
    return {
        "query": query,
        "hit_count": len(compact),
        "hits": compact,
        "ready": len(compact) > 0,
    }
```

- [ ] **Step 4: Add RAG proof to brain insights**

Modify `skills/ingest/scripts/brain_insights.py`:

```python
from skills.ingest.scripts.rag_demo_verify import verify_demo_rag
```

In `build_brain_insights()`, after `files_indexed = ...`, add:

```python
    rag_demo = verify_demo_rag("investor demo meeting") if latest_runs else {
        "query": "investor demo meeting",
        "hit_count": 0,
        "hits": [],
        "ready": False,
    }
```

Change the returned `wiki_status["index"]` block to:

```python
            "index": {
                "indexed": bool(latest_runs),
                "wiki_rag_entries": 0,
                "demo_query": rag_demo["query"],
                "demo_hit_count": rag_demo["hit_count"],
                "demo_ready": rag_demo["ready"],
                "demo_hits": rag_demo["hits"],
            },
```

- [ ] **Step 5: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_rag_demo_verify.py skills\ingest\augur\tests\test_brain_insights.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```powershell
git add skills\ingest\scripts\rag_demo_verify.py skills\ingest\scripts\brain_insights.py skills\ingest\augur\tests\test_rag_demo_verify.py skills\ingest\augur\tests\test_brain_insights.py
git -c user.name='Gur Sannikov' -c user.email='gsannikov@users.noreply.github.com' commit -m "feat(ingest): surface demo RAG proof"
```

---

### Task 6: MCP Tools For Reset, Readiness, And Smoke

**Files:**
- Modify: `skills/ingest/scripts/mcp/inbox_tools.py`
- Test: `skills/ingest/augur/tests/test_inbox_mcp_tools.py`

- [ ] **Step 1: Write failing MCP tests**

Append to `skills/ingest/augur/tests/test_inbox_mcp_tools.py`:

```python
def test_demo_readiness_tool_returns_status(monkeypatch, tmp_path):
    from skills.ingest.scripts.mcp import inbox_tools

    monkeypatch.setattr(
        inbox_tools,
        "check_demo_readiness",
        lambda **kwargs: {"ready": True, "failures": [], "desktop": str(kwargs["desktop"])},
    )

    payload = json.loads(asyncio.run(inbox_tools.demo_readiness_impl(desktop=str(tmp_path), require_cloud=True)))

    assert payload["success"] is True
    assert payload["ready"] is True


def test_demo_reset_tool_uses_real_reset(monkeypatch, tmp_path):
    from skills.ingest.scripts.mcp import inbox_tools

    monkeypatch.setattr(
        inbox_tools,
        "prepare_demo_state",
        lambda **kwargs: {"success": True, "desktop": str(kwargs["desktop"]), "files": []},
    )

    payload = json.loads(asyncio.run(inbox_tools.demo_reset_impl(desktop=str(tmp_path), airplane="off")))

    assert payload["success"] is True
    assert payload["airplane"] == "off"
```

At the top of `skills/ingest/augur/tests/test_inbox_mcp_tools.py`, the imports must include:

```python
import asyncio
import json
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_inbox_mcp_tools.py -q
```

Expected: fail because `demo_readiness_impl` and `demo_reset_impl` do not exist.

- [ ] **Step 3: Implement MCP helpers**

Modify `skills/ingest/scripts/mcp/inbox_tools.py` imports:

```python
from pathlib import Path

from src.config.paths import get_vault_dir
from src.config.preferences import get_preferences_path
from skills.ingest.scripts.demo_ready import check_demo_readiness, prepare_demo_state
```

Add:

```python
async def demo_readiness_impl(desktop: str = "", require_cloud: bool = True) -> str:
    target = Path(desktop).expanduser() if desktop else Path.home() / "Desktop" / "Augur Demo Inbox"
    result = check_demo_readiness(desktop=target, require_cloud=require_cloud)
    return json.dumps({"success": bool(result["ready"]), **result})


async def demo_reset_impl(desktop: str = "", airplane: str = "on") -> str:
    target = Path(desktop).expanduser() if desktop else Path.home() / "Desktop" / "Augur Demo Inbox"
    result = prepare_demo_state(
        desktop=target,
        store_root=_store_root(),
        vault_dir=get_vault_dir(),
        preferences_path=get_preferences_path(),
        airplane_mode=airplane == "on",
    )
    return json.dumps({"airplane": airplane, **result})
```

Register tools in `register_inbox_tools()`:

```python
    @mcp.tool(
        name="demo-readiness",
        annotations=tool_annotations(
            {
                "title": "Demo Readiness",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def demo_readiness_tool(desktop: str = "", require_cloud: bool = True) -> str:
        if metrics:
            metrics.track_tool("demo_readiness", skill="ingest")
        return await demo_readiness_impl(desktop=desktop, require_cloud=require_cloud)

    @mcp.tool(
        name="demo-reset",
        annotations=tool_annotations(
            {
                "title": "Demo Reset",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def demo_reset_tool(desktop: str = "", airplane: str = "on") -> str:
        if metrics:
            metrics.track_tool("demo_reset", skill="ingest")
        return await demo_reset_impl(desktop=desktop, airplane=airplane)
```

- [ ] **Step 4: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_inbox_mcp_tools.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add skills\ingest\scripts\mcp\inbox_tools.py skills\ingest\augur\tests\test_inbox_mcp_tools.py
git -c user.name='Gur Sannikov' -c user.email='gsannikov@users.noreply.github.com' commit -m "feat(ingest): expose demo readiness tools"
```

---

### Task 7: Dashboard Evidence For Investor Demo

**Files:**
- Modify: `apps/dashboard/features/pages/brain/inbox/types.ts`
- Modify: `apps/dashboard/features/pages/brain/inbox/page.tsx`
- Modify: `apps/dashboard/features/pages/brain/insights/types.ts`
- Modify: `apps/dashboard/features/pages/brain/insights/page.tsx`
- Test: `tests/dashboard/brain/inbox-page.test.tsx`
- Test: `tests/dashboard/brain/insights-page.test.tsx`

- [ ] **Step 1: Add failing dashboard tests**

In `tests/dashboard/brain/inbox-page.test.tsx`, extend the latest run fixture with:

```typescript
latest_runs: [
  {
    id: "run_cloud",
    status: "success",
    airplane_mode: false,
    files_seen: 4,
    files_moved: 3,
    files_indexed: 3,
    cloud_calls: 1,
    local_agent_calls: 2,
    files_needing_review: 1,
    file_results: [
      {
        source_path: "C:/Users/example/Desktop/demo-hard-photo.png",
        final_path: "C:/Users/example/Projects/Au-vault/finance/2026-05-07-cloud-invoice.png",
        source_card_path: "C:/Users/example/Projects/Au-vault/sources/files/2026-05-07-cloud-invoice.md",
        extracted_path: "C:/Users/example/Projects/Au-vault/sources/extracted/2026-05-07-cloud-invoice.extracted.md",
        content_type: "image",
        extraction_method: "document-extractor:1",
        hardware_backend: "cloud-vision",
        confidence: "high",
        route: "finance",
        renamed_to: "2026-05-07-cloud-invoice.png",
        rag_indexed: true,
        status: "success",
        cloud_used: true,
        escalation_reason: "local OCR and local vision did not produce usable text",
        cloud_provider: "OpenAICompatibleClient",
        cloud_model: "gpt-4o-mini",
      },
    ],
  },
],
```

Add assertions:

```typescript
expect(screen.getByText(/cloud: 1/i)).toBeInTheDocument();
expect(screen.getByText(/cloud-vision/i)).toBeInTheDocument();
expect(screen.getByText(/local OCR and local vision/i)).toBeInTheDocument();
expect(screen.getByText(/2026-05-07-cloud-invoice\.extracted\.md/i)).toBeInTheDocument();
```

In `tests/dashboard/brain/insights-page.test.tsx`, extend `wiki_status.index`:

```typescript
index: {
  indexed: true,
  wiki_rag_entries: 9,
  demo_query: "investor demo meeting",
  demo_hit_count: 1,
  demo_ready: true,
  demo_hits: [{ file: "vault/sources/files/demo-meeting.md", content: "investor demo meeting" }],
},
```

Add assertions:

```typescript
expect(screen.getByText(/investor demo meeting/i)).toBeInTheDocument();
expect(screen.getByText(/demo-meeting\.md/i)).toBeInTheDocument();
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd apps\dashboard
pnpm test -- --runTestsByPath ..\..\tests\dashboard\brain\inbox-page.test.tsx ..\..\tests\dashboard\brain\insights-page.test.tsx
```

Expected: fail because new evidence fields are not rendered.

- [ ] **Step 3: Extend TypeScript types**

Modify `InboxFileResult` in `apps/dashboard/features/pages/brain/inbox/types.ts`:

```typescript
  extracted_path?: string | null;
  escalation_reason?: string | null;
  cloud_provider?: string | null;
  cloud_model?: string | null;
  content_hash?: string | null;
```

Modify `WikiIndexStatus` in `apps/dashboard/features/pages/brain/insights/types.ts`:

```typescript
  demo_query?: string | null;
  demo_hit_count?: number;
  demo_ready?: boolean;
  demo_hits?: Array<{ file?: string | null; content?: string | null; line?: string | null; scope?: string | null }>;
```

- [ ] **Step 4: Render file-level evidence in Brain Inbox**

In `apps/dashboard/features/pages/brain/inbox/page.tsx`, inside each file result card, add:

```tsx
{file.extracted_path && (
  <span title={file.extracted_path}>{fileNameFromPath(file.extracted_path)}</span>
)}
{file.escalation_reason && (
  <span title={file.escalation_reason}>{file.escalation_reason}</span>
)}
{file.cloud_provider && (
  <span>{file.cloud_provider}{file.cloud_model ? ` / ${file.cloud_model}` : ""}</span>
)}
```

Use the existing compact status row styling used for `cloud`, `rag`, and `confidence`.

- [ ] **Step 5: Render RAG proof in Brain Insights**

In `apps/dashboard/features/pages/brain/insights/page.tsx`, after the RAG index stat card section, add:

```tsx
{wikiIndex?.demo_query && (
  <section className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
    <div className="flex items-center justify-between gap-3">
      <h2 className="text-base font-semibold text-[var(--text-primary)]">Demo RAG proof</h2>
      <span className="rounded-full border border-[var(--border-color)] px-3 py-1 text-xs text-[var(--text-secondary)]">
        {wikiIndex.demo_hit_count ?? 0} hits
      </span>
    </div>
    <p className="mt-2 text-sm text-[var(--text-secondary)]">{wikiIndex.demo_query}</p>
    <div className="mt-3 space-y-2">
      {(wikiIndex.demo_hits ?? []).slice(0, 3).map((hit, index) => (
        <div key={`${hit.file ?? "hit"}-${index}`} className="rounded-md bg-[var(--bg-secondary)] p-3 text-xs text-[var(--text-secondary)]">
          <div className="truncate font-medium text-[var(--text-primary)]" title={hit.file ?? ""}>{hit.file}</div>
          <div className="mt-1 line-clamp-2">{hit.content}</div>
        </div>
      ))}
    </div>
  </section>
)}
```

- [ ] **Step 6: Run dashboard tests**

Run:

```powershell
cd apps\dashboard
pnpm test -- --runTestsByPath ..\..\tests\dashboard\brain\inbox-page.test.tsx ..\..\tests\dashboard\brain\insights-page.test.tsx
```

Expected: `2 passed`, `26+` tests passed.

- [ ] **Step 7: Commit**

```powershell
git add apps\dashboard\features\pages\brain\inbox\types.ts apps\dashboard\features\pages\brain\inbox\page.tsx apps\dashboard\features\pages\brain\insights\types.ts apps\dashboard\features\pages\brain\insights\page.tsx tests\dashboard\brain\inbox-page.test.tsx tests\dashboard\brain\insights-page.test.tsx
git -c user.name='Gur Sannikov' -c user.email='gsannikov@users.noreply.github.com' commit -m "feat(dashboard): show demo run evidence"
```

---

### Task 8: End-To-End Demo Verification Command

**Files:**
- Create: `scripts/verify_ai_pc_demo.py`
- Modify: `skills/ingest/scripts/demo_ready.py`
- Test: `skills/ingest/augur/tests/test_demo_ready.py`

- [ ] **Step 1: Add failing smoke test**

Append to `skills/ingest/augur/tests/test_demo_ready.py`:

```python
def test_demo_smoke_requires_cloud_run_when_airplane_off(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import demo_ready

    calls: list[str] = []

    monkeypatch.setattr(demo_ready, "prepare_demo_state", lambda **kwargs: {"success": True, "files": []})
    monkeypatch.setattr(demo_ready, "check_demo_readiness", lambda **kwargs: {"ready": True, "failures": []})

    class FakeRecord:
        cloud_calls = 1
        files_indexed = 3
        files_needing_review = 1
        file_results = []

    monkeypatch.setattr(demo_ready, "consume_folder", lambda **kwargs: calls.append(kwargs["folder_id"]) or FakeRecord())

    result = demo_ready.run_demo_smoke(desktop=tmp_path / "Desktop", airplane="off", require_cloud=True)

    assert result["success"] is True
    assert result["cloud_calls"] == 1
    assert calls == ["demo-desktop"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_demo_ready.py::test_demo_smoke_requires_cloud_run_when_airplane_off -q
```

Expected: fail because `run_demo_smoke` does not exist.

- [ ] **Step 3: Implement smoke runner**

Modify `skills/ingest/scripts/demo_ready.py` imports:

```python
from skills.ingest.scripts.inbox_consume import consume_folder
```

Add:

```python
def run_demo_smoke(
    *,
    desktop: Path,
    airplane: str,
    require_cloud: bool,
) -> dict[str, Any]:
    reset = prepare_demo_state(
        desktop=desktop,
        store_root=get_runtime_dir() / "brain" / "inbox",
        vault_dir=get_vault_dir(),
        preferences_path=get_preferences_path(),
        airplane_mode=airplane == "on",
    )
    readiness = check_demo_readiness(
        desktop=desktop,
        require_cloud=require_cloud,
    )
    if not readiness["ready"]:
        return {"success": False, "stage": "readiness", **readiness}

    store = InboxStore(get_runtime_dir() / "brain" / "inbox")
    folders = store.list_folders()
    folder_id = folders[0].id if folders else "demo-desktop"
    record = consume_folder(store=store, folder_id=folder_id)
    cloud_calls = int(getattr(record, "cloud_calls", 0))
    success = bool(getattr(record, "files_indexed", 0) >= 1)
    if require_cloud and airplane == "off":
        success = success and cloud_calls == 1
    if airplane == "on":
        success = success and cloud_calls == 0

    return {
        "success": success,
        "stage": "consume",
        "reset": reset,
        "run_id": record.id,
        "status": record.status,
        "cloud_calls": cloud_calls,
        "files_indexed": record.files_indexed,
        "files_needing_review": record.files_needing_review,
    }
```

Add `smoke` subcommand in `main()`:

```python
    smoke = sub.add_parser("smoke")
    smoke.add_argument("--desktop", type=Path, default=_default_desktop())
    smoke.add_argument("--airplane", choices=["on", "off"], default="on")
    smoke.add_argument("--require-cloud", action="store_true")
```

Handle it:

```python
    elif args.command == "smoke":
        payload = run_demo_smoke(
            desktop=args.desktop,
            airplane=args.airplane,
            require_cloud=bool(args.require_cloud),
        )
```

- [ ] **Step 4: Create wrapper script**

Create `scripts/verify_ai_pc_demo.py`:

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from skills.ingest.scripts.demo_ready import run_demo_smoke


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the AI PC investor demo.")
    parser.add_argument("--desktop", type=Path, default=Path.home() / "Desktop" / "Augur Demo Inbox")
    parser.add_argument("--airplane", choices=["on", "off"], default="on")
    parser.add_argument("--require-cloud", action="store_true")
    args = parser.parse_args(argv)
    result = run_demo_smoke(
        desktop=args.desktop,
        airplane=args.airplane,
        require_cloud=bool(args.require_cloud),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run tests and smoke help**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests\test_demo_ready.py -q
.\.venv\Scripts\python.exe scripts\verify_ai_pc_demo.py --help
```

Expected: tests pass and help prints usage for `--desktop`, `--airplane`, and `--require-cloud`.

- [ ] **Step 6: Commit**

```powershell
git add skills\ingest\scripts\demo_ready.py skills\ingest\augur\tests\test_demo_ready.py scripts\verify_ai_pc_demo.py
git -c user.name='Gur Sannikov' -c user.email='gsannikov@users.noreply.github.com' commit -m "test(demo): add AI PC demo smoke verifier"
```

---

### Task 9: Final Verification And Browser Review

**Files:**
- No planned source edits in this task.

- [ ] **Step 1: Run backend verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\ingest\augur\tests shared-vault\skills\document-extractor\augur\tests\test_cloud_escalation.py shared-vault\skills\document-extractor\augur\tests\test_capabilities.py shared-vault\skills\document-extractor\augur\tests\test_audio_extractor.py shared-vault\skills\document-extractor\augur\tests\test_tools_extract.py -q
```

Expected: all selected tests pass. A known ffmpeg warning is acceptable only if tests still pass.

- [ ] **Step 2: Run dashboard tests**

Run:

```powershell
cd apps\dashboard
pnpm test -- --runTestsByPath ..\..\tests\dashboard\brain\inbox-page.test.tsx ..\..\tests\dashboard\brain\insights-page.test.tsx
```

Expected: both suites pass.

- [ ] **Step 3: Run demo smoke in airplane mode**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\verify_ai_pc_demo.py --airplane on
```

Expected JSON:

```json
{
  "success": true,
  "cloud_calls": 0
}
```

The actual output may include more keys, but `success` must be `true` and `cloud_calls` must be `0`.

- [ ] **Step 4: Run demo smoke with cloud escalation**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\verify_ai_pc_demo.py --airplane off --require-cloud
```

Expected JSON:

```json
{
  "success": true,
  "cloud_calls": 1
}
```

The actual output may include more keys, but `success` must be `true` and `cloud_calls` must be `1`.

- [ ] **Step 5: Run dashboard build**

Run from `apps/dashboard`, not the repo root:

```powershell
cd apps\dashboard
pnpm run build:safe
```

Expected: Next.js build completes successfully.

- [ ] **Step 6: Browser verification**

Use the repo dashboard lifecycle path to start or rebuild the dashboard, then verify:

- `http://localhost:3000/brain/inbox`
- `http://localhost:3000/brain/insights`

Required browser evidence:

- page loads to interactive state
- no `Failed to load chunk`
- no app error boundary
- Brain Inbox shows run evidence from the smoke run
- Brain Insights shows demo RAG proof
- screenshots are saved under `C:\Users\intel\AppData\Local\Augur\state\browser-verification\demo-ready-investor`

- [ ] **Step 7: Stop on verification blockers**

If verification exposes a blocker, do not declare demo ready. Create a narrow follow-up fix task for the blocker, implement it with tests, rerun this verification section, and include the browser evidence trailer in that fix commit.

Expected: no source changes are committed from Task 9 unless a blocker was fixed in a separate explicit task.

- [ ] **Step 8: Final status**

Run:

```powershell
git status --short --branch
```

Expected: branch is clean except for intentional unpushed commits.

---

## Plan Self-Review

Spec coverage:

- Real seeded reset: Task 1 and Task 8.
- No fake output: Task 2, Task 3, Task 8, Task 9.
- Airplane mode blocks cloud: Task 2, Task 3, Task 8, Task 9.
- Real cloud escalation when airplane mode is off: Task 2, Task 3, Task 8, Task 9.
- MP3 meeting becomes memory/actions: Task 4.
- Source cards and extracted/transcribed artifacts: Task 3 and Task 4.
- RAG visibility: Task 5 and Task 7.
- Brain Inbox/Insights payoff: Task 7 and Task 9.
- Repeatable pre-demo check: Task 1 and Task 8.

Type consistency:

- Python `InboxFileResult.extracted_path`, `escalation_reason`, `cloud_provider`, and `cloud_model` match TypeScript `InboxFileResult`.
- `ExtractionResult.cloud_used`, `local_agent_used`, `escalation_reason`, `cloud_provider`, `cloud_model`, and `hardware_backend` are consumed by `inbox_consume.py`.
- `wiki_status.index.demo_query`, `demo_hit_count`, `demo_ready`, and `demo_hits` match dashboard `WikiIndexStatus`.

Verification coverage:

- Unit tests cover policy and serialization behavior.
- Runtime smoke verifies real reset and consume.
- Browser verification is required after dashboard changes.
