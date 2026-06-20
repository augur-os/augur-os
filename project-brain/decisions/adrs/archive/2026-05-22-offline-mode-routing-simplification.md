# Offline-Mode Routing Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the scattered offline-mode escalation/probing logic with one declarative `(mode × activity × OS) → engine` routing module, so OCR, transcript, and chat each resolve their engine in exactly one place.

**Architecture:** A new `src/lib/routing/` package holds the matrix as data (`matrix.py`), a resolver + orchestrators (`resolver.py`), and thin engine adapters over already-working internals (`engines.py`). `extractor.py` and `get-local-backend-status` are re-pointed at the resolver; the OCR escalation ladder, the Hebrew special-case, and the ~900-line probe layer in `local_backends.py` are deleted. One net-new engine (`gemini-transcribe`) provides regular-mode audio via a Gemini-CLI passive-agent.

**Tech Stack:** Python 3.11+, pytest, Pydantic-free dataclasses, Windows PowerShell. Spec: `docs/superpowers/specs/2026-05-22-offline-mode-routing-simplification-design.md`. Partial supersede of ADR-640.

**Branch:** `offline-routing-simplification` (already created).

---

## Conventions for every task

- Run a single test with the project venv:
  `& .\.venv\Scripts\python.exe -m pytest <path>::<test> -v`
- The tight TDD loop uses direct `pytest` on the one new test (allowed for inner-loop work). The **final** verification (Task 9) goes through the repo's `/auto-test-pytest`, `/auto-lint`, and `/dev-build` per CLAUDE.md rules 19/29.
- Param name for the operating system is always `os_name` (never shadow the `os` module).
- `os_name` values are `sys.platform` strings: `"win32"`, `"darwin"`, `"linux"`.

---

## File Structure

```
src/lib/routing/                        # NEW package — the single decision point
├── __init__.py                         # public exports
├── matrix.py                           # ROUTES table, Activity/Mode types, engine_id_for(), RoutingError
├── engines.py                          # result dataclasses, engine adapters, registries
└── resolver.py                         # detect_mode(), run_ocr(), transcribe(), resolve_chat(), engine_availability()

src/lib/extraction/extractor.py         # MODIFY — OCR path calls routing.run_ocr(); audio path calls routing.transcribe(); delete _request_llm_ocr ladder, Hebrew case, _run_ollama_ocr (moved)
src/mcp/augur_framework/tools/infrastructure/local_backends.py  # MODIFY — delete probe ladders; get_airplane_launch_overrides_impl + get_local_backend_status_impl re-pointed to routing
docs/adrs/ADR-765-offline-mode-routing-matrix.md  # NEW — record the matrix as canonical (number assigned at write time)

tests/lib/routing/test_matrix.py        # NEW
tests/lib/routing/test_resolver_mode.py # NEW
tests/lib/routing/test_ocr_engines.py   # NEW
tests/lib/routing/test_transcript_engines.py  # NEW
tests/lib/routing/test_chat_launcher.py # NEW
tests/test_extractor.py                 # MODIFY — drop Hebrew/ladder assertions; assert routing delegation
tests/packages/augur-mcp/tools/test_airplane_mode.py  # MODIFY — status reflects per-cell engines, no probe assertions
```

---

## Task 1: Routing matrix (the single source of truth)

**Files:**
- Create: `src/lib/routing/__init__.py`
- Create: `src/lib/routing/matrix.py`
- Test: `tests/lib/routing/test_matrix.py`

- [ ] **Step 1: Create the empty package marker**

Create `src/lib/routing/__init__.py`:

```python
"""Single decision point for (mode x activity x OS) -> engine routing.

See docs/superpowers/specs/2026-05-22-offline-mode-routing-simplification-design.md
"""
```

- [ ] **Step 2: Write the failing matrix test**

Create `tests/lib/routing/test_matrix.py`:

```python
import pytest

from src.lib.routing.matrix import ROUTES, RoutingError, engine_id_for


@pytest.mark.parametrize(
    "activity,mode,os_name,expected",
    [
        ("chat", "regular", "win32", "agent-chat"),
        ("chat", "regular", "darwin", "agent-chat"),
        ("chat", "offline", "win32", "ollama-llm"),
        ("chat", "offline", "darwin", "ollama-llm"),
        ("ocr", "regular", "win32", "agent-vision"),
        ("ocr", "regular", "darwin", "agent-vision"),
        ("ocr", "offline", "win32", "ollama-glm-ocr"),
        ("ocr", "offline", "darwin", "ollama-glm-ocr"),
        ("transcript", "regular", "win32", "gemini-transcribe"),
        ("transcript", "regular", "darwin", "gemini-transcribe"),
        ("transcript", "offline", "win32", "openvino-whisper"),
        ("transcript", "offline", "darwin", "faster-whisper"),
        ("transcript", "offline", "linux", "openvino-whisper"),
    ],
)
def test_every_cell_resolves(activity, mode, os_name, expected):
    assert engine_id_for(activity, mode, os_name) == expected


def test_unknown_activity_raises():
    with pytest.raises(RoutingError):
        engine_id_for("translate", "regular", "win32")


def test_unmapped_os_raises_for_os_specific_cell():
    # transcript/offline has no "*"; an unknown OS must raise, not silently default
    with pytest.raises(RoutingError):
        engine_id_for("transcript", "offline", "sunos5")


def test_routes_has_exactly_six_cells():
    assert set(ROUTES.keys()) == {
        ("chat", "regular"), ("chat", "offline"),
        ("ocr", "regular"), ("ocr", "offline"),
        ("transcript", "regular"), ("transcript", "offline"),
    }
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\lib\routing\test_matrix.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.lib.routing.matrix'`

- [ ] **Step 4: Implement `matrix.py`**

Create `src/lib/routing/matrix.py`:

```python
"""The offline-mode routing matrix as data. The only place a route is defined."""
from __future__ import annotations

import sys
from typing import Literal

Activity = Literal["chat", "ocr", "transcript"]
Mode = Literal["regular", "offline"]


class RoutingError(RuntimeError):
    """Raised when no engine is mapped for an (activity, mode, os) cell."""


# (activity, mode) -> {os_key: engine_id}. "*" matches any OS.
ROUTES: dict[tuple[str, str], dict[str, str]] = {
    ("chat", "regular"): {"*": "agent-chat"},
    ("chat", "offline"): {"*": "ollama-llm"},
    ("ocr", "regular"): {"*": "agent-vision"},
    ("ocr", "offline"): {"*": "ollama-glm-ocr"},
    ("transcript", "regular"): {"*": "gemini-transcribe"},
    ("transcript", "offline"): {"win32": "openvino-whisper", "linux": "openvino-whisper", "darwin": "faster-whisper"},
}


def engine_id_for(activity: str, mode: str, os_name: str | None = None) -> str:
    """Return the engine id for a matrix cell, or raise RoutingError."""
    resolved_os = os_name or sys.platform
    cell = ROUTES.get((activity, mode))
    if cell is None:
        raise RoutingError(f"no route for activity={activity!r} mode={mode!r}")
    engine_id = cell.get(resolved_os) or cell.get("*")
    if engine_id is None:
        raise RoutingError(
            f"no engine for activity={activity!r} mode={mode!r} os={resolved_os!r}"
        )
    return engine_id
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\lib\routing\test_matrix.py -v`
Expected: PASS (13 + 3 = all green)

- [ ] **Step 6: Commit**

```powershell
git add src\lib\routing\__init__.py src\lib\routing\matrix.py tests\lib\routing\test_matrix.py
git commit -m "feat(routing): declarative offline-mode routing matrix"
```

---

## Task 2: Result types + engine protocols

**Files:**
- Create: `src/lib/routing/engines.py` (types only in this task)
- Test: covered indirectly; add a small dataclass test here.

- [ ] **Step 1: Write the failing types test**

Append to a new file `tests/lib/routing/test_engines_types.py`:

```python
from src.lib.routing.engines import ChatLaunchSpec, EngineAvailability, OcrResult


def test_ocr_result_defaults():
    r = OcrResult(success=True, results={"0": "hi"}, engine_id="ollama-glm-ocr")
    assert r.error is None
    assert r.needs_handoff is False
    assert r.handoff_requests is None


def test_engine_availability_defaults():
    a = EngineAvailability(available=False, engine_id="gemini-transcribe")
    assert a.detail == ""
    assert a.setup_hint is None


def test_chat_launch_spec_defaults():
    s = ChatLaunchSpec(engine_id="ollama-llm", use_local_ollama=True)
    assert s.ready is True
    assert s.launch_argv is None
    assert s.model is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\lib\routing\test_engines_types.py -v`
Expected: FAIL with `ModuleNotFoundError` / `ImportError`

- [ ] **Step 3: Implement the types at the top of `engines.py`**

Create `src/lib/routing/engines.py`:

```python
"""Thin engine adapters over already-working extraction internals + registries.

Wraps; never rewrites. The proven internals live in src/lib/extraction; this
module only adapts them to a uniform per-activity interface and registers them
under the engine ids used by the routing matrix.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.lib.extraction.transcription import TranscriptResult


@dataclass
class EngineAvailability:
    available: bool
    engine_id: str
    detail: str = ""
    setup_hint: str | None = None


@dataclass
class OcrResult:
    success: bool
    results: dict[str, str]          # request_id -> extracted text
    engine_id: str
    error: str | None = None
    needs_handoff: bool = False      # in-session AI client should run handoff_requests
    handoff_requests: list[dict] | None = None


@dataclass
class ChatLaunchSpec:
    engine_id: str
    use_local_ollama: bool
    launch_argv: list[str] | None = None
    model: str | None = None
    ready: bool = True
    setup_hint: str | None = None
    error: str | None = None


class OcrEngine(Protocol):
    engine_id: str
    def run(self, requests: list[dict]) -> OcrResult: ...
    def available(self) -> EngineAvailability: ...


class TranscriptEngine(Protocol):
    engine_id: str
    def run(self, audio_path: str, *, model_dir: str | None = None) -> TranscriptResult: ...
    def available(self) -> EngineAvailability: ...
```

- [ ] **Step 4: Run to verify it passes**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\lib\routing\test_engines_types.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src\lib\routing\engines.py tests\lib\routing\test_engines_types.py
git commit -m "feat(routing): engine result types and protocols"
```

---

## Task 3: Mode detection

**Files:**
- Create: `src/lib/routing/resolver.py` (detect_mode only in this task)
- Test: `tests/lib/routing/test_resolver_mode.py`

- [ ] **Step 1: Write the failing mode test**

Create `tests/lib/routing/test_resolver_mode.py`:

```python
from src.lib.routing import resolver


def test_forced_airplane_is_offline(monkeypatch):
    monkeypatch.setattr(resolver, "_load_airplane_prefs", lambda: {"enabled": True, "forced": True, "auto_detect": True})
    assert resolver.detect_mode() == "offline"


def test_disabled_airplane_is_regular(monkeypatch):
    monkeypatch.setattr(resolver, "_load_airplane_prefs", lambda: {"enabled": False, "forced": False, "auto_detect": True})
    assert resolver.detect_mode() == "regular"


def test_auto_detect_offline_when_no_connectivity(monkeypatch):
    monkeypatch.setattr(resolver, "_load_airplane_prefs", lambda: {"enabled": False, "forced": False, "auto_detect": True})
    monkeypatch.setattr(resolver, "_is_online", lambda: False)
    assert resolver.detect_mode() == "offline"


def test_auto_detect_regular_when_online(monkeypatch):
    monkeypatch.setattr(resolver, "_load_airplane_prefs", lambda: {"enabled": False, "forced": False, "auto_detect": True})
    monkeypatch.setattr(resolver, "_is_online", lambda: True)
    assert resolver.detect_mode() == "regular"


def test_explicit_mode_override_wins(monkeypatch):
    # Callers may pass mode explicitly; detection is skipped.
    assert resolver.resolve_mode("offline") == "offline"
    assert resolver.resolve_mode("regular") == "regular"
```

- [ ] **Step 2: Run to verify it fails**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\lib\routing\test_resolver_mode.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.lib.routing.resolver'`

- [ ] **Step 3: Implement `detect_mode` in `resolver.py`**

Create `src/lib/routing/resolver.py`:

```python
"""Resolver + orchestrators: the public entry points for routed work."""
from __future__ import annotations

from typing import Any

from src.lib.routing.matrix import Mode


def _load_airplane_prefs() -> dict[str, Any]:
    try:
        from src.config.preferences import load_preferences

        prefs = load_preferences()
    except Exception:
        return {}
    airplane = prefs.get("airplane_mode", {})
    return airplane if isinstance(airplane, dict) else {"enabled": bool(airplane)}


def _is_online() -> bool:
    try:
        from src.mcp.augur_framework.tools.infrastructure.connectivity import (
            check_connectivity,
        )

        return bool(check_connectivity().get("online"))
    except Exception:
        # If we cannot even probe connectivity, assume online (regular).
        return True


def detect_mode() -> Mode:
    """Return 'offline' or 'regular' from airplane prefs + connectivity."""
    airplane = _load_airplane_prefs()
    if airplane.get("forced"):
        return "offline" if airplane.get("enabled", True) else "regular"
    if airplane.get("enabled"):
        return "offline"
    if airplane.get("auto_detect", True) and not _is_online():
        return "offline"
    return "regular"


def resolve_mode(mode: str | None) -> Mode:
    """Return the caller-provided mode, or detect it."""
    if mode in ("regular", "offline"):
        return mode  # type: ignore[return-value]
    return detect_mode()
```

- [ ] **Step 4: Run to verify it passes**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\lib\routing\test_resolver_mode.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src\lib\routing\resolver.py tests\lib\routing\test_resolver_mode.py
git commit -m "feat(routing): mode detection (airplane prefs + connectivity)"
```

---

## Task 4: OCR engines + `run_ocr` orchestrator

**Files:**
- Modify: `src/lib/routing/engines.py` (add OCR engines + registry; move `_run_ollama_ocr` here)
- Modify: `src/lib/routing/resolver.py` (add `run_ocr`)
- Modify: `src/lib/extraction/extractor.py` (delete `_run_ollama_ocr`; it now lives in engines.py)
- Test: `tests/lib/routing/test_ocr_engines.py`

- [ ] **Step 1: Write the failing OCR engine test**

Create `tests/lib/routing/test_ocr_engines.py`:

```python
from src.lib.routing import engines, resolver

REQS = [{"type": "ocr", "request_id": "0", "image_b64": "QQ==", "prompt": "p"}]


def test_ollama_glm_ocr_returns_results(monkeypatch):
    monkeypatch.setattr(engines, "_run_ollama_ocr", lambda b64, prompt: "HELLO")
    eng = engines.OCR_ENGINES["ollama-glm-ocr"]
    out = eng.run(REQS)
    assert out.success is True
    assert out.results == {"0": "HELLO"}
    assert out.engine_id == "ollama-glm-ocr"


def test_ollama_glm_ocr_empty_text_is_failure(monkeypatch):
    monkeypatch.setattr(engines, "_run_ollama_ocr", lambda b64, prompt: "")
    out = engines.OCR_ENGINES["ollama-glm-ocr"].run(REQS)
    assert out.success is False
    assert out.error


def test_agent_vision_handoff_in_client_context(monkeypatch):
    monkeypatch.setattr(engines, "_is_ai_client_context", lambda: True)
    out = engines.OCR_ENGINES["agent-vision"].run(REQS)
    assert out.needs_handoff is True
    assert out.handoff_requests == REQS
    assert out.engine_id == "agent-vision"


def test_agent_vision_passive_agent_when_not_in_client(monkeypatch):
    from src.lib.extraction.cloud_vision import CloudVisionResult

    monkeypatch.setattr(engines, "_is_ai_client_context", lambda: False)
    monkeypatch.setattr(
        engines, "_run_cloud_vision_ocr",
        lambda reqs, reason: CloudVisionResult(True, {"0": "CLOUD"}, "passive-agent:claude", "claude"),
    )
    out = engines.OCR_ENGINES["agent-vision"].run(REQS)
    assert out.success is True
    assert out.results == {"0": "CLOUD"}


def test_run_ocr_uses_offline_engine_when_mode_offline(monkeypatch):
    monkeypatch.setattr(engines, "_run_ollama_ocr", lambda b64, prompt: "OFFLINE")
    out = resolver.run_ocr(REQS, mode="offline", os_name="win32")
    assert out.engine_id == "ollama-glm-ocr"
    assert out.results == {"0": "OFFLINE"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\lib\routing\test_ocr_engines.py -v`
Expected: FAIL with `AttributeError` (no `OCR_ENGINES` / `_run_ollama_ocr` / `run_ocr`)

- [ ] **Step 3: Add OCR engines + `_run_ollama_ocr` to `engines.py`**

Append to `src/lib/routing/engines.py`:

```python
import json
import sys

from src.lib.extraction.cloud_vision import (
    CloudVisionResult,
    run_cloud_vision_ocr as _run_cloud_vision_ocr,
)
from src.lib.extraction.local_backend_config import get_local_ocr_settings


def _is_ai_client_context() -> bool:
    from src.lib.extraction.extractor import is_ai_client_context

    return is_ai_client_context()


def _run_ollama_ocr(image_b64: str, prompt: str) -> str:
    """Run a single OCR request through the local Ollama vision model.

    Moved verbatim from extractor.py so the routing layer owns the offline OCR
    engine and extractor no longer imports back into routing.
    """
    import urllib.error
    import urllib.request

    settings = get_local_ocr_settings()
    options: dict[str, int | float] = {"temperature": 0}
    if sys.platform == "win32":
        options["num_gpu"] = 1

    payload = json.dumps({
        "model": settings.model,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
        "options": options,
    }).encode()

    req = urllib.request.Request(
        settings.generate_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=settings.timeout_s) as resp:
            body = json.loads(resp.read())
            return str(body.get("response", "")).strip()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace").strip()
        raise RuntimeError(
            f"Ollama GLM-OCR request failed with HTTP {exc.code}: {detail or exc.reason}"
        ) from exc


class OllamaGlmOcrEngine:
    engine_id = "ollama-glm-ocr"

    def run(self, requests: list[dict]) -> OcrResult:
        results: dict[str, str] = {}
        try:
            for idx, request in enumerate(requests):
                request_id = str(request.get("request_id", idx))
                text = _run_ollama_ocr(request["image_b64"], request["prompt"])
                if not text:
                    return OcrResult(
                        success=False, results=results, engine_id=self.engine_id,
                        error=f"Ollama GLM-OCR returned no text for request {request_id}",
                    )
                results[request_id] = text
        except Exception as exc:  # noqa: BLE001
            return OcrResult(success=False, results=results, engine_id=self.engine_id, error=str(exc))
        return OcrResult(success=bool(results), results=results, engine_id=self.engine_id)

    def available(self) -> EngineAvailability:
        try:
            import urllib.request

            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                ok = resp.status == 200
        except Exception:
            ok = False
        if ok:
            return EngineAvailability(True, self.engine_id, "Ollama reachable")
        return EngineAvailability(
            False, self.engine_id, "Ollama not reachable",
            "Start Ollama and run: ollama pull glm-ocr",
        )


class AgentVisionEngine:
    engine_id = "agent-vision"

    def run(self, requests: list[dict]) -> OcrResult:
        if _is_ai_client_context():
            return OcrResult(
                success=True, results={}, engine_id=self.engine_id,
                needs_handoff=True, handoff_requests=requests,
            )
        cloud: CloudVisionResult = _run_cloud_vision_ocr(requests, reason="regular-mode OCR")
        if cloud.success:
            return OcrResult(success=True, results=cloud.results, engine_id=self.engine_id)
        return OcrResult(success=False, results=cloud.results or {}, engine_id=self.engine_id, error=cloud.error)

    def available(self) -> EngineAvailability:
        from src.lib.extraction.cloud_vision import get_passive_agent_status

        if _is_ai_client_context():
            return EngineAvailability(True, self.engine_id, "in AI client session")
        status = get_passive_agent_status()
        if status.get("available"):
            return EngineAvailability(True, self.engine_id, f"passive agent {status.get('cli')}")
        return EngineAvailability(False, self.engine_id, str(status.get("error") or "no passive agent"))


OCR_ENGINES: dict[str, OcrEngine] = {
    "ollama-glm-ocr": OllamaGlmOcrEngine(),
    "agent-vision": AgentVisionEngine(),
}
```

- [ ] **Step 4: Add `run_ocr` to `resolver.py`**

Append to `src/lib/routing/resolver.py`:

```python
from src.lib.routing.engines import OCR_ENGINES, OcrResult
from src.lib.routing.matrix import engine_id_for


def run_ocr(
    requests: list[dict],
    *,
    mode: str | None = None,
    os_name: str | None = None,
) -> OcrResult:
    """Run OCR requests through the engine the matrix selects for the cell."""
    if not requests:
        return OcrResult(success=True, results={}, engine_id="none")
    resolved_mode = resolve_mode(mode)
    engine_id = engine_id_for("ocr", resolved_mode, os_name)
    return OCR_ENGINES[engine_id].run(requests)
```

- [ ] **Step 5: Delete `_run_ollama_ocr` from `extractor.py`**

In `src/lib/extraction/extractor.py`, delete the entire `_run_ollama_ocr` function (the `def _run_ollama_ocr(image_b64, prompt)` block, ~lines 282-314). It now lives in `routing/engines.py`. Do not change other functions in this step.

- [ ] **Step 6: Run to verify it passes**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\lib\routing\test_ocr_engines.py -v`
Expected: PASS (5 tests)

- [ ] **Step 7: Commit**

```powershell
git add src\lib\routing\engines.py src\lib\routing\resolver.py src\lib\extraction\extractor.py tests\lib\routing\test_ocr_engines.py
git commit -m "feat(routing): OCR engines (ollama-glm-ocr, agent-vision) + run_ocr"
```

---

## Task 5: Transcript engines + `transcribe` orchestrator with D1 fallback

**Files:**
- Modify: `src/lib/routing/engines.py` (transcript engines + registry; new `gemini-transcribe`)
- Modify: `src/lib/routing/resolver.py` (add `transcribe` with D1 fallback)
- Test: `tests/lib/routing/test_transcript_engines.py`

- [ ] **Step 1: Write the failing transcript test**

Create `tests/lib/routing/test_transcript_engines.py`:

```python
from src.lib.extraction.transcription import TranscriptResult
from src.lib.routing import engines, resolver


def _ok(method):
    return TranscriptResult(success=True, transcript="hello world", method=method, backend="NPU")


def test_local_whisper_engine_delegates(monkeypatch):
    monkeypatch.setattr(engines, "_transcribe_audio", lambda path, model_dir=None: _ok("openvino-whisper"))
    out = engines.TRANSCRIPT_ENGINES["openvino-whisper"].run("a.wav")
    assert out.success is True
    assert out.method == "openvino-whisper"


def test_gemini_unavailable_reports_not_ready(monkeypatch):
    monkeypatch.setattr(engines, "_gemini_cli_path", lambda: None)
    avail = engines.TRANSCRIPT_ENGINES["gemini-transcribe"].available()
    assert avail.available is False
    assert avail.setup_hint


def test_transcribe_offline_uses_local_whisper(monkeypatch):
    monkeypatch.setattr(engines, "_transcribe_audio", lambda path, model_dir=None: _ok("openvino-whisper"))
    out = resolver.transcribe("a.wav", mode="offline", os_name="win32")
    assert out.method == "openvino-whisper"


def test_transcribe_regular_uses_gemini(monkeypatch):
    monkeypatch.setattr(engines, "_gemini_cli_path", lambda: "C:/g/gemini.cmd")
    monkeypatch.setattr(
        engines.GeminiTranscribeEngine, "run",
        lambda self, path, *, model_dir=None: _ok("gemini-transcribe"),
    )
    out = resolver.transcribe("a.wav", mode="regular", os_name="win32")
    assert out.method == "gemini-transcribe"


def test_d1_fallback_to_local_when_gemini_absent(monkeypatch):
    # Regular mode, but Gemini missing -> fall back to local whisper + notice.
    monkeypatch.setattr(engines, "_gemini_cli_path", lambda: None)
    monkeypatch.setattr(engines, "_transcribe_audio", lambda path, model_dir=None: _ok("faster-whisper"))
    out = resolver.transcribe("a.wav", mode="regular", os_name="darwin")
    assert out.success is True
    assert out.method == "faster-whisper"
    assert out.needs_review is True  # fallback notice signalled via needs_review
    assert "fallback" in (out.error or "").lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\lib\routing\test_transcript_engines.py -v`
Expected: FAIL with `AttributeError` (no `TRANSCRIPT_ENGINES` / `transcribe`)

- [ ] **Step 3: Add transcript engines to `engines.py`**

Append to `src/lib/routing/engines.py`:

```python
import os as _os
import subprocess
import uuid

from src.lib.extraction.transcription import transcribe_audio as _transcribe_audio


class LocalWhisperEngine:
    """Wraps transcribe_audio, which already selects OpenVINO/faster-whisper by OS."""

    def __init__(self, engine_id: str) -> None:
        self.engine_id = engine_id

    def run(self, audio_path: str, *, model_dir: str | None = None) -> TranscriptResult:
        return _transcribe_audio(audio_path, model_dir=model_dir)

    def available(self) -> EngineAvailability:
        from src.lib.extraction.transcription import can_transcribe_audio

        if can_transcribe_audio():
            return EngineAvailability(True, self.engine_id, "local whisper model present")
        return EngineAvailability(
            False, self.engine_id, "local whisper model/backend missing",
            "Install the OpenVINO/faster-whisper model per docs/guides/offline-backends-verification.md",
        )


def _gemini_cli_path() -> str | None:
    from src.lib.agent_cli_config import resolve_cli_path

    return resolve_cli_path("gemini")


class GeminiTranscribeEngine:
    """Regular-mode transcription via a Gemini-CLI passive-agent (no SDK)."""

    engine_id = "gemini-transcribe"

    def run(self, audio_path: str, *, model_dir: str | None = None) -> TranscriptResult:
        from src.config.paths import get_project_root, get_runtime_dir
        from src.lib.agent_cli_config import build_agent_command

        cli_path = _gemini_cli_path()
        if not cli_path:
            return TranscriptResult(
                success=False, transcript="", method="gemini-transcribe",
                backend="gemini", needs_review=True, error="Gemini CLI not found",
            )

        audio = Path(audio_path)
        if not audio.exists():
            return TranscriptResult(
                success=False, transcript="", method="gemini-transcribe",
                backend="gemini", needs_review=True, error=f"audio not found: {audio_path}",
            )

        job_dir = get_runtime_dir() / "document-extractor" / "gemini-transcribe" / uuid.uuid4().hex
        job_dir.mkdir(parents=True, exist_ok=True)
        result_path = job_dir / "result.json"
        prompt = (
            "You are completing an Augur audio transcription job. "
            f"Transcribe the audio file at this absolute path: {audio.as_posix()}\n"
            f"Write exactly this JSON to {result_path.as_posix()}:\n"
            '{"success": true, "transcript": "<verbatim transcript>", "error": ""}\n'
            "If transcription is impossible, write success false with a short error. "
            "After writing the file, print a brief completion message only."
        )
        cmd = build_agent_command(cli_path, "gemini", prompt, job_dir=job_dir)
        env = _os.environ.copy()
        env["AUGUR_AGENT_SESSION"] = "1"
        env.setdefault("PYTHONIOENCODING", "utf-8")
        try:
            subprocess.run(  # nosec B603
                cmd, cwd=str(get_project_root()), capture_output=True, check=False,
                encoding="utf-8", env=env, stdin=subprocess.DEVNULL, text=True, timeout=300,
            )
        except subprocess.TimeoutExpired:
            return TranscriptResult(
                success=False, transcript="", method="gemini-transcribe",
                backend="gemini", needs_review=True, error="gemini transcription timed out",
            )

        if not result_path.exists():
            return TranscriptResult(
                success=False, transcript="", method="gemini-transcribe",
                backend="gemini", needs_review=True, error="gemini produced no result JSON",
            )
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            return TranscriptResult(
                success=False, transcript="", method="gemini-transcribe",
                backend="gemini", needs_review=True, error=f"unreadable gemini result: {exc}",
            )
        transcript = str(payload.get("transcript") or "").strip()
        if payload.get("success") is True and transcript:
            return TranscriptResult(
                success=True, transcript=transcript, method="gemini-transcribe",
                backend="gemini", confidence="medium", cloud_used=True,
            )
        return TranscriptResult(
            success=False, transcript="", method="gemini-transcribe", backend="gemini",
            needs_review=True, error=str(payload.get("error") or "gemini returned no transcript"),
        )

    def available(self) -> EngineAvailability:
        if _gemini_cli_path():
            return EngineAvailability(True, self.engine_id, "gemini CLI present")
        return EngineAvailability(
            False, self.engine_id, "gemini CLI not found",
            "Install the Gemini CLI to enable agent-based transcription (regular mode).",
        )


TRANSCRIPT_ENGINES: dict[str, TranscriptEngine] = {
    "openvino-whisper": LocalWhisperEngine("openvino-whisper"),
    "faster-whisper": LocalWhisperEngine("faster-whisper"),
    "gemini-transcribe": GeminiTranscribeEngine(),
}
```

Add `from pathlib import Path` to the imports at the top of `engines.py` if not already present (Task 2 did not import it).

- [ ] **Step 4: Add `transcribe` (with D1 fallback) to `resolver.py`**

Append to `src/lib/routing/resolver.py`:

```python
from src.lib.extraction.transcription import TranscriptResult
from src.lib.routing.engines import TRANSCRIPT_ENGINES


def transcribe(
    audio_path: str,
    *,
    model_dir: str | None = None,
    mode: str | None = None,
    os_name: str | None = None,
) -> TranscriptResult:
    """Transcribe audio via the matrix engine, with D1 fallback for regular mode.

    D1: if regular-mode transcript (gemini-transcribe) is unavailable or fails,
    fall back to the local offline whisper engine and flag needs_review with a
    'used local fallback' note.
    """
    import sys as _sys

    resolved_mode = resolve_mode(mode)
    resolved_os = os_name or _sys.platform
    engine_id = engine_id_for("transcript", resolved_mode, resolved_os)
    engine = TRANSCRIPT_ENGINES[engine_id]

    result = engine.run(audio_path, model_dir=model_dir)
    if engine_id == "gemini-transcribe" and not result.success:
        local_id = engine_id_for("transcript", "offline", resolved_os)
        fallback = TRANSCRIPT_ENGINES[local_id].run(audio_path, model_dir=model_dir)
        note = f"used local fallback ({local_id}); gemini unavailable: {result.error}"
        fallback.needs_review = True
        fallback.error = note if fallback.success else (fallback.error or note)
        return fallback
    return result
```

- [ ] **Step 5: Run to verify it passes**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\lib\routing\test_transcript_engines.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```powershell
git add src\lib\routing\engines.py src\lib\routing\resolver.py tests\lib\routing\test_transcript_engines.py
git commit -m "feat(routing): transcript engines + gemini passive-agent + D1 fallback"
```

---

## Task 6: Chat launcher

**Files:**
- Modify: `src/lib/routing/resolver.py` (add `resolve_chat`)
- Modify: `src/lib/routing/engines.py` (add `build_ollama_launch_spec`)
- Test: `tests/lib/routing/test_chat_launcher.py`

- [ ] **Step 1: Write the failing chat test**

Create `tests/lib/routing/test_chat_launcher.py`:

```python
from src.lib.routing import engines, resolver


def test_regular_chat_uses_active_client(monkeypatch):
    spec = resolver.resolve_chat("claude", mode="regular")
    assert spec.engine_id == "agent-chat"
    assert spec.use_local_ollama is False
    assert spec.launch_argv is None


def test_offline_chat_builds_ollama_launch(monkeypatch):
    monkeypatch.setattr(
        engines, "build_ollama_launch_spec",
        lambda agent_id: engines.ChatLaunchSpec(
            engine_id="ollama-llm", use_local_ollama=True,
            launch_argv=["ollama", "launch", "claude", "--model", "m", "--"],
            model="m", ready=True,
        ),
    )
    spec = resolver.resolve_chat("claude", mode="offline")
    assert spec.engine_id == "ollama-llm"
    assert spec.use_local_ollama is True
    assert spec.launch_argv[:2] == ["ollama", "launch"]


def test_offline_chat_not_ready_when_ollama_missing(monkeypatch):
    monkeypatch.setattr(
        engines, "build_ollama_launch_spec",
        lambda agent_id: engines.ChatLaunchSpec(
            engine_id="ollama-llm", use_local_ollama=True, ready=False,
            setup_hint="Install Ollama from https://ollama.com/download/windows",
        ),
    )
    spec = resolver.resolve_chat("claude", mode="offline")
    assert spec.ready is False
    assert spec.setup_hint
```

- [ ] **Step 2: Run to verify it fails**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\lib\routing\test_chat_launcher.py -v`
Expected: FAIL with `AttributeError` (no `resolve_chat` / `build_ollama_launch_spec`)

- [ ] **Step 3: Add `build_ollama_launch_spec` to `engines.py`**

Append to `src/lib/routing/engines.py`:

```python
def build_ollama_launch_spec(agent_id: str = "claude") -> ChatLaunchSpec:
    """Offline chat launch argv from Ollama detection — NO smoke probing.

    Reuses the lightweight detection helpers in local_backends but drops the
    deleted probe ladders.
    """
    from src.mcp.augur_framework.tools.infrastructure.local_backends import (
        _detect_ollama, _integration_launch_args, _load_local_prefs,
        _load_ollama_config, _model_for_agent, _setup_hint,
    )

    detection = _detect_ollama()
    if not detection["installed"]:
        return ChatLaunchSpec("ollama-llm", True, ready=False, setup_hint=_setup_hint("binary_missing"))
    if not detection["server_running"]:
        return ChatLaunchSpec("ollama-llm", True, ready=False, setup_hint=_setup_hint("ollama_not_running"))

    config = _load_ollama_config(_load_local_prefs())
    model = _model_for_agent(config, agent_id)
    model_names = {m.get("name") for m in detection["models"] if isinstance(m, dict)}
    if model not in model_names:
        return ChatLaunchSpec(
            "ollama-llm", True, model=model, ready=False,
            setup_hint=_setup_hint("model_missing", model=model),
        )

    argv = [detection["binary"], "launch", agent_id, "--model", model, "--", *_integration_launch_args(agent_id)]
    return ChatLaunchSpec("ollama-llm", True, launch_argv=argv, model=model, ready=True)
```

- [ ] **Step 4: Add `resolve_chat` to `resolver.py`**

Append to `src/lib/routing/resolver.py`:

```python
from src.lib.routing.engines import ChatLaunchSpec, build_ollama_launch_spec


def resolve_chat(agent_id: str = "claude", *, mode: str | None = None) -> ChatLaunchSpec:
    """Resolve how chat should run for the current mode."""
    resolved_mode = resolve_mode(mode)
    engine_id = engine_id_for("chat", resolved_mode)
    if engine_id == "ollama-llm":
        return build_ollama_launch_spec(agent_id)
    return ChatLaunchSpec(engine_id="agent-chat", use_local_ollama=False)
```

- [ ] **Step 5: Run to verify it passes**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\lib\routing\test_chat_launcher.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Add public exports to `src/lib/routing/__init__.py`**

Replace `src/lib/routing/__init__.py` with:

```python
"""Single decision point for (mode x activity x OS) -> engine routing.

See docs/superpowers/specs/2026-05-22-offline-mode-routing-simplification-design.md
"""
from src.lib.routing.engines import (
    ChatLaunchSpec,
    EngineAvailability,
    OcrResult,
)
from src.lib.routing.matrix import ROUTES, RoutingError, engine_id_for
from src.lib.routing.resolver import (
    detect_mode,
    resolve_chat,
    resolve_mode,
    run_ocr,
    transcribe,
)

__all__ = [
    "ROUTES",
    "RoutingError",
    "engine_id_for",
    "detect_mode",
    "resolve_mode",
    "resolve_chat",
    "run_ocr",
    "transcribe",
    "ChatLaunchSpec",
    "EngineAvailability",
    "OcrResult",
]
```

- [ ] **Step 7: Run the whole routing suite + commit**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\lib\routing -v`
Expected: PASS (all routing tests green)

```powershell
git add src\lib\routing\engines.py src\lib\routing\resolver.py src\lib\routing\__init__.py tests\lib\routing\test_chat_launcher.py
git commit -m "feat(routing): chat launcher + package exports"
```

---

## Task 7: Re-point `extractor.py` (OCR + audio) and delete the ladder + Hebrew case (D2)

**Files:**
- Modify: `src/lib/extraction/extractor.py`
- Test: `tests/test_extractor.py`

- [ ] **Step 1: Write the failing delegation test**

Add to `tests/test_extractor.py`:

```python
def test_extract_image_delegates_ocr_to_routing(monkeypatch, tmp_path):
    import src.lib.extraction.extractor as extractor
    from src.lib.routing.engines import OcrResult

    captured = {}

    def fake_run_ocr(requests, *, mode=None, os_name=None):
        captured["requests"] = requests
        return OcrResult(success=True, results={"0": "ROUTED TEXT"}, engine_id="ollama-glm-ocr")

    monkeypatch.setattr(extractor, "_routing_run_ocr", fake_run_ocr)

    img = tmp_path / "scan.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)  # minimal bytes; markitdown yields no text
    result = extractor.extract(str(img), max_tier=1, allow_cloud=True)

    assert "ROUTED TEXT" in result.markdown
    assert result.ocr_applied is True
    assert captured["requests"]  # routing was actually called


def test_extract_no_longer_special_cases_hebrew(monkeypatch, tmp_path):
    # D2: language_hint="he" must NOT short-circuit to a hebrew-cloud-required error.
    import src.lib.extraction.extractor as extractor
    from src.lib.routing.engines import OcrResult

    monkeypatch.setattr(
        extractor, "_routing_run_ocr",
        lambda requests, *, mode=None, os_name=None: OcrResult(True, {"0": "shalom"}, "ollama-glm-ocr"),
    )
    img = tmp_path / "he.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    result = extractor.extract(str(img), max_tier=1, allow_cloud=False, language_hint="he")
    assert result.hardware_backend != "hebrew-cloud-required"
```

- [ ] **Step 2: Run to verify it fails**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\test_extractor.py::test_extract_image_delegates_ocr_to_routing tests\test_extractor.py::test_extract_no_longer_special_cases_hebrew -v`
Expected: FAIL (no `_routing_run_ocr`; Hebrew case still present)

- [ ] **Step 3: Replace `_request_llm_ocr` with a routing-backed version**

In `src/lib/extraction/extractor.py`:

1. Add near the other imports (after `from src.lib.extraction.local_backend_config import get_local_ocr_settings`):

```python
from src.lib.routing import run_ocr as _routing_run_ocr
```

2. Delete the entire `_is_hebrew_language_hint` function and the entire body of `_request_llm_ocr` (the long tiered ladder, ~lines 502-700), and replace `_request_llm_ocr` with this version (keep the same signature so callers are unchanged):

```python
def _request_llm_ocr(
    file_path: Path,
    fmt: str,
    size: int,
    elapsed: float,
    partial: str,
    *,
    allow_cloud: bool,
    language_hint: str | None = None,
) -> ExtractionResult:
    """Request OCR via the routing matrix. No tiered ladder, no Hebrew special-case (D2)."""
    partial_markdown, llm_requests = _build_llm_ocr_requests(file_path, partial)
    if not llm_requests:
        return ExtractionResult(
            success=True, markdown=partial, title=file_path.stem, tier_used=0,
            format=fmt, size_bytes=size, extraction_time=elapsed, ocr_applied=False,
        )

    outcome = _routing_run_ocr(llm_requests)

    if outcome.needs_handoff:
        return ExtractionResult(
            success=True, markdown=partial_markdown, title=file_path.stem, tier_used=1,
            format=fmt, size_bytes=size, extraction_time=elapsed, ocr_applied=False,
            needs_llm=True, llm_requests=outcome.handoff_requests, partial_markdown=partial_markdown,
            local_agent_used=True, escalation_reason="agent vision handoff", hardware_backend="agent-vision",
        )

    if outcome.success:
        return ExtractionResult(
            success=True, markdown=merge_llm_results(partial_markdown, outcome.results),
            title=file_path.stem, tier_used=1, format=fmt, size_bytes=size,
            extraction_time=elapsed, ocr_applied=True, hardware_backend=outcome.engine_id,
        )

    return ExtractionResult(
        success=False, markdown=partial, title=file_path.stem, tier_used=1, format=fmt,
        size_bytes=size, extraction_time=elapsed, ocr_applied=False,
        error=outcome.error or "OCR failed", escalation_reason="ocr failed",
        hardware_backend=outcome.engine_id,
    )
```

Note: the `language_hint` parameter is now accepted but unused (D2 removes the special-case). Leave it in the signature so callers in `extract()` are unchanged; add `# noqa: ARG001` if the linter flags it, or prefix with `_ = language_hint`.

- [ ] **Step 4: Re-point the audio path to `routing.transcribe`**

In `extract()`, replace the audio block (the `if ext in audio_extractor.AUDIO_EXTENSIONS:` branch, ~lines 358-385) so it uses the router and renders markdown:

```python
    if ext in audio_extractor.AUDIO_EXTENSIONS:
        from src.lib.routing import transcribe as _routing_transcribe

        transcript = _routing_transcribe(str(file_path), model_dir=audio_model_dir)
        elapsed = time.monotonic() - start
        if transcript.success:
            from src.lib.extraction.audio_extractor import _format_transcript_markdown
            return ExtractionResult(
                success=True, markdown=_format_transcript_markdown(transcript),
                title=file_path.stem, tier_used=0, format=fmt, size_bytes=size_bytes,
                extraction_time=elapsed, ocr_applied=False,
                cloud_used=transcript.cloud_used, hardware_backend=transcript.method,
            )
        return ExtractionResult(
            success=False, markdown="", title=file_path.name, tier_used=0, format=fmt,
            size_bytes=size_bytes, extraction_time=elapsed, ocr_applied=False,
            error=transcript.error or "transcription unavailable", hardware_backend=transcript.method,
        )
```

- [ ] **Step 5: Remove the now-dead `_is_hebrew_language_hint` reference check**

Run `& .\.venv\Scripts\python.exe -m pytest tests\test_extractor.py -v` and fix any test that asserted the old Hebrew `hardware_backend="hebrew-cloud-required"` / `escalation_reason="hebrew_offline_unavailable"` behavior — update those tests to the D2 behavior (no special-case) or delete them if they only existed to assert the removed branch. Document each change in the commit body.

- [ ] **Step 6: Run the targeted + full extractor suite**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\test_extractor.py -v`
Expected: PASS (new delegation tests green; Hebrew-special-case tests removed/updated)

- [ ] **Step 7: Commit**

```powershell
git add src\lib\extraction\extractor.py tests\test_extractor.py
git commit -m "refactor(extraction): route OCR/audio through routing matrix; drop ladder + Hebrew case (D2)"
```

---

## Task 8: Re-point `get-local-backend-status` and gut the probe layer

**Files:**
- Modify: `src/mcp/augur_framework/tools/infrastructure/local_backends.py`
- Test: `tests/packages/augur-mcp/tools/test_airplane_mode.py`

- [ ] **Step 1: Write the failing status test**

Add to `tests/packages/augur-mcp/tools/test_airplane_mode.py`:

```python
import asyncio
import json


def test_status_reports_routing_matrix(monkeypatch):
    from src.mcp.augur_framework.tools.infrastructure import local_backends as lb

    out = json.loads(asyncio.run(lb.get_local_backend_status_impl(lb.GetLocalBackendStatusInput())))
    routing = out["routing"]
    # Every activity present with both modes mapped to an engine id.
    assert routing["ocr"]["offline"]["engine"] == "ollama-glm-ocr"
    assert routing["transcript"]["regular"]["engine"] == "gemini-transcribe"
    assert routing["chat"]["offline"]["engine"] == "ollama-llm"
    assert "available" in routing["ocr"]["offline"]


def test_airplane_overrides_have_no_smoke_probe(monkeypatch):
    # The probe functions are deleted; overrides come from build_ollama_launch_spec.
    from src.mcp.augur_framework.tools.infrastructure import local_backends as lb

    assert not hasattr(lb, "_probe_agent_local_turn")
    assert not hasattr(lb, "_run_codex_local_turn_probe")
```

- [ ] **Step 2: Run to verify it fails**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\packages\augur-mcp\tools\test_airplane_mode.py::test_status_reports_routing_matrix tests\packages\augur-mcp\tools\test_airplane_mode.py::test_airplane_overrides_have_no_smoke_probe -v`
Expected: FAIL (no `routing` key; probe functions still present)

- [ ] **Step 3: Delete the probe ladder from `local_backends.py`**

Delete these functions and their module-level caches/constants entirely:
`_agent_turn_probe_timeout_s`, `_model_turn_probe_timeout_s`, `_model_turn_probe_attempts`,
`_model_turn_failure_hint`, `_agent_turn_failure_hint`, `_trim_probe_detail`,
`_run_ollama_model_turn_probe`, `_probe_ollama_model_turn`, `_terminate_process_tree`,
`_build_codex_local_turn_command`, `_run_codex_local_turn_probe`, `_run_claude_local_turn_probe`,
`_probe_agent_local_turn`, and the caches `_AGENT_TURN_CACHE`, `_MODEL_TURN_CACHE` plus their `*_TTL_S` / `*_TIMEOUT_S` / `*_ATTEMPTS` / `_AGENT_TURN_PROBE_MARKER` constants.
Keep: `_detect_ollama`, `_resolve_ollama_binary`, `_platform_candidates`, `_candidate_exists`, `_load_local_prefs`, `_load_ollama_config`, `_model_for_agent`, `_setup_hint`, `_integration_launch_args`, `list_ollama_integrations_impl`, `toggle_airplane_mode_impl`, `resolve_client_impl`, `set_client_override_impl`, `list_available_clients_impl`.
Update `_reset_integrations_cache` to drop the `_AGENT_TURN_CACHE.clear()` / `_MODEL_TURN_CACHE.clear()` lines.

- [ ] **Step 4: Rewrite `get_airplane_launch_overrides_impl` to use the routing spec**

Replace the body of `get_airplane_launch_overrides_impl` with:

```python
async def get_airplane_launch_overrides_impl(
    params: GetAirplaneLaunchOverridesInput,
) -> str:
    """Return Ollama launch argv for an airplane-mode agent (no smoke probing)."""
    from src.lib.routing.engines import build_ollama_launch_spec

    spec = build_ollama_launch_spec(params.agent_id)
    if not spec.ready:
        return json.dumps(
            {"ready": False, "reason": "ollama_not_ready", "setup_hint": spec.setup_hint},
            indent=2,
        )
    return json.dumps(
        {
            "ready": True,
            "integration_id": params.agent_id,
            "model": spec.model,
            "launch_argv": spec.launch_argv,
        },
        indent=2,
    )
```

- [ ] **Step 5: Add the `routing` section to `get_local_backend_status_impl`**

In `get_local_backend_status_impl`, build a routing report and add it to `result` before `return`:

```python
    from src.lib.routing.engines import OCR_ENGINES, TRANSCRIPT_ENGINES
    from src.lib.routing.matrix import engine_id_for

    def _avail(activity: str, engine_id: str) -> bool:
        registry = OCR_ENGINES if activity == "ocr" else TRANSCRIPT_ENGINES if activity == "transcript" else {}
        engine = registry.get(engine_id)
        if engine is None:
            return engine_id in ("agent-chat", "ollama-llm")  # chat reported via launch_command
        try:
            return bool(engine.available().available)
        except Exception:
            return False

    routing: dict[str, Any] = {}
    for activity in ("chat", "ocr", "transcript"):
        routing[activity] = {}
        for mode in ("regular", "offline"):
            try:
                eid = engine_id_for(activity, mode)
            except Exception:
                eid = None
            routing[activity][mode] = {"engine": eid, "available": _avail(activity, eid) if eid else False}
    result["routing"] = routing
```

(Leave the existing `extraction` block in place; `routing` is additive so the dashboard keeps its current fields and gains the matrix view.)

- [ ] **Step 6: Run to verify it passes**

Run: `& .\.venv\Scripts\python.exe -m pytest tests\packages\augur-mcp\tools\test_airplane_mode.py -v`
Expected: PASS (status reports routing; probe functions gone)

- [ ] **Step 7: Commit**

```powershell
git add src\mcp\augur_framework\tools\infrastructure\local_backends.py tests\packages\augur-mcp\tools\test_airplane_mode.py
git commit -m "refactor(infra): re-point local-backend status/overrides to routing matrix; delete probe ladder"
```

---

## Task 9: ADR, full verification, and real-data demo-day proof

**Files:**
- Create: `docs/adrs/ADR-<next>-offline-mode-routing-matrix.md`

- [ ] **Step 1: Write the ADR**

Run `& .\.venv\Scripts\python.exe -m pytest tests\config\test_runtime_preferences.py -q` first to confirm nothing broke in config, then create the ADR via the project ADR helper if one exists, else create `docs/adrs/ADR-<next>-offline-mode-routing-matrix.md` with frontmatter and these sections: Context (ADR-640 complexity), Decision (the 3×3 matrix as the single decision point in `src/lib/routing/`; D1 fallback; D2 drop Hebrew case; probe layer deleted), Consequences (simpler surface; Gemini dependency for regular-mode audio; NPU left for OpenVINO transcript only). Mark ADR-640 as partially superseded.

- [ ] **Step 2: Run the full Python suite through the repo loop**

Run the slash command (NOT raw pytest), per CLAUDE.md rules 19/29:

```text
/auto-test-pytest
```

Expected: green, or honest evolution-gap report. Fix any breakage from the refactor before continuing.

- [ ] **Step 3: Lint touched surfaces through the loop**

```text
/auto-lint
```

Expected: `All checks passed!` for `src/lib/routing`, `src/lib/extraction/extractor.py`, and `src/mcp/augur_framework/tools/infrastructure/local_backends.py`.

- [ ] **Step 4: Rebuild + browser-verify the dashboard surfaces**

The status payload changed (added `routing`), so verify the consuming pages load to interactive state (rules 28, 31):

```text
/dev-build --pages /settings/security,/brain/agents
```

Then confirm in a real browser (or screenshot-capable tool) that `/settings/security` shows the Local Backend section and `/brain/agents` shows client readiness with no chunk-load/application errors. If no browser tool is available, say so explicitly — do not claim verification.

- [ ] **Step 5: Real-data Windows offline proof (rule 34)**

On the Windows laptop, with airplane mode ON, run and capture **actual output** for each activity:

```powershell
# OCR (offline -> ollama-glm-ocr): make a real text image, extract, show the text
& .\.venv\Scripts\python.exe -c "from src.lib.extraction import extract; r=extract(r'<path-to-real-image.png>', max_tier=1, allow_cloud=False); print(r.hardware_backend); print(r.markdown[:500])"

# Transcript (offline -> openvino-whisper): real audio clip, show transcript + device
& .\.venv\Scripts\python.exe -c "from src.lib.routing import transcribe; t=transcribe(r'<path-to-real-audio.wav>', mode='offline'); print(t.method, t.backend); print(t.transcript[:500])"

# Chat (offline -> ollama-llm): show the launch spec resolves ready
& .\.venv\Scripts\python.exe -c "from src.lib.routing import resolve_chat; s=resolve_chat('claude', mode='offline'); print(s.ready, s.model, s.launch_argv)"
```

Expected: OCR prints `ollama-glm-ocr` + real extracted text; transcript prints `openvino-whisper` + a device in {NPU,GPU,CPU} + real words; chat prints `True` + a model + a launch argv. Record the real inputs and outputs in the final commit/PR body. A zero/empty result is a finding to fix, not a pass.

- [ ] **Step 6: Real-data regular-mode + D1 fallback proof**

```powershell
# Regular-mode transcript -> gemini-transcribe (requires gemini CLI + connectivity)
& .\.venv\Scripts\python.exe -c "from src.lib.routing import transcribe; t=transcribe(r'<path-to-real-audio.wav>', mode='regular'); print(t.method); print(t.transcript[:300])"
```

Then temporarily make Gemini unresolvable (e.g. rename the gemini shim on PATH for the test, or monkeypatch in a throwaway script) and re-run to confirm the D1 fallback returns a local transcript with `needs_review=True` and a "used local fallback" note. Restore Gemini afterward.

- [ ] **Step 7: Commit the ADR + verification metadata**

```powershell
git add docs\adrs\ADR-*-offline-mode-routing-matrix.md
git commit -m "docs(adr): offline-mode routing matrix supersedes part of ADR-640" -m "Verified-RealData: Windows offline OCR/transcript/chat + regular gemini + D1 fallback. Verified-Browser: /settings/security, /brain/agents (or Skip-Verify with reason if no browser tool)."
```

---

## Self-Review

**Spec coverage:**
- Matrix as single source of truth → Task 1.
- Engine adapters wrapping existing internals → Tasks 4 (OCR), 5 (transcript), 6 (chat).
- New `gemini-transcribe` passive-agent → Task 5.
- D1 fallback (Gemini absent → local whisper + notice) → Task 5 (`transcribe`) + Task 9 Step 6 proof.
- D2 drop Hebrew special-case → Task 7.
- Delete escalation ladder + probe layer → Task 7 (`_request_llm_ocr`) + Task 8 (`local_backends` probes).
- Re-point `get-local-backend-status` (dashboard dependency) → Task 8.
- Mode = airplane_mode toggle + connectivity → Task 3.
- ADR amends ADR-640 → Task 9 Step 1.
- Real-data verification (rule 34) + browser verification (rules 28/31) → Task 9 Steps 4–6.

**Placeholder scan:** ADR file name carries `<next>` (the ADR number is assigned at creation time from `docs/generated/adr-index.md`); real-data commands carry `<path-to-real-*>` placeholders the operator fills with actual demo files — these are inputs, not unfinished plan content. All code blocks are complete.

**Type consistency:** `OcrResult`, `ChatLaunchSpec`, `EngineAvailability` defined in Task 2 and used unchanged in Tasks 4/6/8. `engine_id_for(activity, mode, os_name)` signature stable across Tasks 1/4/5/6/8. `transcribe(...)`, `run_ocr(...)`, `resolve_chat(...)`, `resolve_mode(...)`, `detect_mode()` defined once and exported in Task 6 Step 6. `_transcribe_audio` / `_run_ollama_ocr` / `_run_cloud_vision_ocr` are the monkeypatch seams named consistently in engines.py and the tests.
