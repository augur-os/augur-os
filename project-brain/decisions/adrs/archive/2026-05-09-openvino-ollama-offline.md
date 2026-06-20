# OpenVINO + Ollama Offline Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current extraction ladder with a single-engine, OS-aware offline path: Ollama GLM-OCR for OCR (both OSes), OpenVINO Whisper-large-v3 INT8 for ASR on Win (with explicit NPU/GPU/CPU device probe) plus faster-whisper on macOS, Hebrew OCR short-circuits to passive-agent cloud, and Tesseract is removed.

**Architecture:** Modify the existing tier-based extractor in `src/lib/extraction/`. No new modules — only deletions, model swaps, a language-hint short-circuit, and a real device probe to replace the silent `device="AUTO"` that never reaches NPU on Intel hardware. Cloud escalation continues through the existing `run_cloud_vision_ocr` passive-agent CLI subprocess; no new SDKs.

**Tech Stack:** Python 3.11/3.12, FastMCP skill tools, pytest, OpenVINO 2026.0+ / OpenVINO GenAI, Ollama HTTP API (`localhost:11434`), `transformers==4.52.x` pin, `optimum-intel>=1.25.2`, `imageio-ffmpeg`, `pymupdf`, MarkItDown, faster-whisper (macOS-only).

---

## Scope Check

This plan is the extraction-layer slice of the May-09 spec. It does NOT touch:

- Brain Inbox dashboard, source cards, RAG indexing (May-07 plan owns those).
- Chat LLM swap to OpenVINO GenAI (next sub-project).
- EasyOCR Hebrew rung (tracked alternative; Hebrew goes to passive-agent cloud in this slice).
- PaddleOCR-VL OpenVINO module (tracked alternative).
- Cloud audio escalation (passive-agent doesn't currently handle audio; the slice leaves audio offline-only).

The plan preserves Augur's existing boundaries:

- Library code in `src/lib/extraction/`
- MCP tool surface in `shared-vault/skills/document-extractor/scripts/mcp/`
- Tests in `shared-vault/skills/document-extractor/augur/tests/`
- Runtime model cache under `get_cache_dir() / "models"`
- Mutable preferences in `config/preferences.yaml`

## File Structure

### Files to modify

- `src/lib/extraction/capabilities.py` — drop Tesseract / `markitdown-ocr` / `pytesseract` from inventory; add 2026 prereq checks (NPU driver, `transformers` pin, `openvino>=2026.0`); add GLM-OCR availability via Ollama tag list.
- `src/lib/extraction/extractor.py` — delete Tier 0.5 Tesseract branch; swap hardcoded Ollama `model="llava"` to `"glm-ocr"`; add `language_hint` parameter to `extract()` and short-circuit Tier 1a when hint is `"he"`.
- `src/lib/extraction/transcription.py` — replace `device="AUTO"` with explicit `["NPU","GPU","CPU"]` probe; default model becomes `whisper-large-v3-int8-ov`; remove `_transcribe_faster_whisper` Windows branch (keep macOS-only via `sys.platform == "darwin"` gate).
- `src/lib/extraction/audio_extractor.py` — adjust to the new transcription dispatch (already OS-aware via `platform.system()`).
- `src/lib/extraction/__init__.py` — no new exports needed; keep as-is unless cleanup required.
- `shared-vault/skills/document-extractor/scripts/mcp/tools_extract.py` — extend `get-extraction-status` JSON surface with new fields.
- `pyproject.toml` — add `openvino>=2026.0`, `openvino-genai>=2026.0`, `transformers==4.52.*`, `optimum-intel>=1.25.2`; remove `pytesseract`, `markitdown-ocr`.

### Files to delete

- `src/lib/extraction/tesseract_ocr.py`
- `shared-vault/skills/document-extractor/augur/tests/test_tesseract_ocr.py`

### Test files to modify

- `shared-vault/skills/document-extractor/augur/tests/test_capabilities.py` — assert pruned inventory; assert prereq fields populate; assert GLM-OCR detection.
- `shared-vault/skills/document-extractor/augur/tests/test_extractor.py` — assert Tier 0.5 is gone; assert `model="glm-ocr"`; assert Hebrew short-circuit.
- `shared-vault/skills/document-extractor/augur/tests/test_audio_extractor.py` — assert OS-aware transcription dispatch.
- `shared-vault/skills/document-extractor/augur/tests/test_tools_extract.py` — assert new `get-extraction-status` JSON fields.

---

### Task 1: Create execution worktree and verify baseline

**Files:**
- Read: `docs/superpowers/specs/2026-05-09-openvino-ollama-offline-design.md`
- No code changes in this task

- [ ] **Step 1: Create an isolated worktree**

Run from `C:\Users\intel\Projects\Augur` in PowerShell:

```powershell
git fetch origin
git worktree add C:\Users\intel\Projects\Augur\.worktrees\openvino-ollama-offline -b openvino-ollama-offline origin/main
Set-Location C:\Users\intel\Projects\Augur\.worktrees\openvino-ollama-offline
git status --short --branch
```

Expected output includes:

```text
## openvino-ollama-offline...origin/main
```

- [ ] **Step 2: Confirm spec is present in the worktree**

```powershell
Test-Path docs/superpowers/specs/2026-05-09-openvino-ollama-offline-design.md
```

Expected: `True`

- [ ] **Step 3: Run the existing extractor tests as a baseline**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/ -x -q
```

Expected: all green (or whatever existing baseline shows). Record any pre-existing failures for context — they are not this plan's responsibility.

- [ ] **Step 4: Confirm Ollama is running and pull GLM-OCR**

```powershell
ollama list
ollama pull glm-ocr
ollama list
```

Expected: `glm-ocr` appears in the second `ollama list`. If `ollama pull` fails because the model name is not yet available locally, document the model tag mismatch and stop — fixing the tag is a prerequisite for Task 5.

---

### Task 2: Drop Tesseract / markitdown-ocr / pytesseract from capability inventory

**Files:**
- Modify: `src/lib/extraction/capabilities.py`
- Modify: `shared-vault/skills/document-extractor/augur/tests/test_capabilities.py`

- [ ] **Step 1: Write the failing test**

Append to `test_capabilities.py`:

```python
def test_inventory_omits_tesseract_and_markitdown_ocr(monkeypatch) -> None:
    """Tesseract and markitdown-ocr are removed from the active capability surface."""
    from src.lib.extraction import capabilities

    inventory = capabilities.detect_extraction_capabilities(use_cache=False)
    packages = inventory.get("packages", {})

    assert "pytesseract" not in packages
    assert "markitdown-ocr" not in packages
    assert "tesseract" not in inventory.get("commands", {})
    assert "ocr_ready" not in inventory  # legacy Tesseract-derived flag
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_capabilities.py::test_inventory_omits_tesseract_and_markitdown_ocr -v
```

Expected: FAIL — current inventory includes those package names and the `ocr_ready` flag.

- [ ] **Step 3: Edit `capabilities.py`**

In `src/lib/extraction/capabilities.py`, locate `_PACKAGE_NAMES` (currently around line 21):

```python
_PACKAGE_NAMES = [
    "markitdown",
    "markitdown-ocr",
    "pymupdf",
    "openvino",
    "openvino-genai",
    "faster-whisper",
    "imageio-ffmpeg",
    "onnxruntime",
    "onnxruntime-directml",
    "pytesseract",
    "pdf2image",
]
```

Replace with:

```python
_PACKAGE_NAMES = [
    "markitdown",
    "pymupdf",
    "openvino",
    "openvino-genai",
    "faster-whisper",
    "imageio-ffmpeg",
    "onnxruntime",
    "onnxruntime-directml",
    "pdf2image",
]
```

Locate the `commands` dict in `_detect_extraction_capabilities_uncached` (around line 240):

```python
commands = {
    "tesseract": shutil.which("tesseract"),
    "ffmpeg": _resolve_ffmpeg_binary(),
    "ollama": _resolve_ollama_binary(),
}
```

Replace with:

```python
commands = {
    "ffmpeg": _resolve_ffmpeg_binary(),
    "ollama": _resolve_ollama_binary(),
}
```

Locate `ocr_ready` in the same function (around line 281):

```python
ocr_ready = bool(
    commands["tesseract"]
    or packages["pytesseract"]["installed"]
    or packages["markitdown-ocr"]["installed"]
)
```

Delete the `ocr_ready` calculation entirely. Then locate the return dict at the end of `_detect_extraction_capabilities_uncached` and remove the `"ocr_ready": ocr_ready,` line from it.

- [ ] **Step 4: Run test to verify it passes**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_capabilities.py::test_inventory_omits_tesseract_and_markitdown_ocr -v
```

Expected: PASS.

- [ ] **Step 5: Run the full capabilities test suite to catch regressions**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_capabilities.py -v
```

Expected: all green. If a previous test asserted `ocr_ready` or expected Tesseract in `commands`, update it to match the new inventory shape (delete the assertion or rewrite to test what now exists).

- [ ] **Step 6: Commit**

```powershell
git add src/lib/extraction/capabilities.py shared-vault/skills/document-extractor/augur/tests/test_capabilities.py
git commit -m "refactor(extraction): drop Tesseract/markitdown-ocr from capability inventory"
```

---

### Task 3: Add 2026 prereq checks to capability inventory

**Files:**
- Modify: `src/lib/extraction/capabilities.py`
- Modify: `shared-vault/skills/document-extractor/augur/tests/test_capabilities.py`

This task adds an `extraction_prereqs` block to the inventory: NPU driver floor on Windows, `transformers` pin compatibility, OpenVINO version floor.

- [ ] **Step 1: Write the failing test**

Append to `test_capabilities.py`:

```python
def test_inventory_reports_extraction_prereqs(monkeypatch) -> None:
    """The new prereqs block surfaces NPU driver, transformers pin, and OV version."""
    from src.lib.extraction import capabilities

    monkeypatch.setattr(capabilities, "_get_transformers_version", lambda: "4.52.4")
    monkeypatch.setattr(capabilities, "_get_optimum_intel_version", lambda: "1.25.3")
    monkeypatch.setattr(capabilities, "_get_openvino_version", lambda: "2026.0.0")
    monkeypatch.setattr(capabilities, "_get_npu_driver_version", lambda: "32.0.100.3104")

    inventory = capabilities.detect_extraction_capabilities(use_cache=False)
    prereqs = inventory.get("extraction_prereqs", {})

    assert prereqs["transformers_version"] == "4.52.4"
    assert prereqs["transformers_ok"] is True
    assert prereqs["optimum_intel_version"] == "1.25.3"
    assert prereqs["optimum_intel_ok"] is True
    assert prereqs["openvino_version"] == "2026.0.0"
    assert prereqs["openvino_ok"] is True
    assert prereqs["npu_driver_version"] == "32.0.100.3104"
    assert prereqs["npu_driver_ok"] is True


def test_inventory_flags_transformers_pin_violation(monkeypatch) -> None:
    """transformers 4.53+ silently breaks Whisper conversion — must surface as not_ok."""
    from src.lib.extraction import capabilities

    monkeypatch.setattr(capabilities, "_get_transformers_version", lambda: "4.53.0")
    monkeypatch.setattr(capabilities, "_get_optimum_intel_version", lambda: "1.25.3")
    monkeypatch.setattr(capabilities, "_get_openvino_version", lambda: "2026.0.0")
    monkeypatch.setattr(capabilities, "_get_npu_driver_version", lambda: "32.0.100.3104")

    inventory = capabilities.detect_extraction_capabilities(use_cache=False)
    prereqs = inventory["extraction_prereqs"]

    assert prereqs["transformers_ok"] is False
    assert "4.52" in prereqs["transformers_setup_hint"]
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_capabilities.py::test_inventory_reports_extraction_prereqs shared-vault/skills/document-extractor/augur/tests/test_capabilities.py::test_inventory_flags_transformers_pin_violation -v
```

Expected: FAIL — `extraction_prereqs` field doesn't exist; helper functions don't exist.

- [ ] **Step 3: Add prereq helpers to `capabilities.py`**

In `src/lib/extraction/capabilities.py`, add these helpers below the existing `_package_version` helper (around line 41):

```python
def _get_transformers_version() -> str | None:
    return _package_version("transformers")


def _get_optimum_intel_version() -> str | None:
    return _package_version("optimum-intel")


def _get_openvino_version() -> str | None:
    return _package_version("openvino")


def _get_npu_driver_version() -> str | None:
    """Return Intel NPU driver version on Windows, or None elsewhere or on failure."""
    if sys.platform != "win32":
        return None
    try:
        result = subprocess.run(
            [
                "pnputil",
                "/enum-drivers",
            ],
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    # Parse for "Intel(R) AI Boost" device driver version line
    lines = result.stdout.splitlines()
    in_block = False
    for line in lines:
        if "Intel(R) AI Boost" in line or "AI Boost" in line:
            in_block = True
            continue
        if in_block and "Driver Version" in line:
            # Format: "Driver Version: 32.0.100.3104"
            parts = line.split(":", 1)
            if len(parts) == 2:
                return parts[1].strip()
        if in_block and not line.strip():
            in_block = False
    return None


def _semver_at_least(actual: str | None, floor: str) -> bool:
    """Return True when actual >= floor under simple dotted-tuple comparison."""
    if not actual:
        return False
    def _tuple(v: str) -> tuple[int, ...]:
        out = []
        for part in v.split("."):
            digits = "".join(ch for ch in part if ch.isdigit())
            if digits:
                out.append(int(digits))
            else:
                out.append(0)
        return tuple(out)
    return _tuple(actual) >= _tuple(floor)


def _transformers_pin_ok(version: str | None) -> bool:
    """transformers must be 4.52.x — 4.53+ silently breaks Whisper conversion."""
    if not version:
        return False
    parts = version.split(".")
    if len(parts) < 2:
        return False
    try:
        return parts[0] == "4" and parts[1] == "52"
    except (ValueError, IndexError):
        return False


def _build_extraction_prereqs() -> dict[str, Any]:
    transformers_v = _get_transformers_version()
    optimum_v = _get_optimum_intel_version()
    openvino_v = _get_openvino_version()
    npu_v = _get_npu_driver_version()

    return {
        "transformers_version": transformers_v,
        "transformers_ok": _transformers_pin_ok(transformers_v),
        "transformers_setup_hint": (
            "Pin transformers==4.52.x; 4.53+ breaks Whisper conversion."
            if not _transformers_pin_ok(transformers_v)
            else None
        ),
        "optimum_intel_version": optimum_v,
        "optimum_intel_ok": _semver_at_least(optimum_v, "1.25.2"),
        "optimum_intel_setup_hint": (
            "Upgrade optimum-intel>=1.25.2."
            if not _semver_at_least(optimum_v, "1.25.2")
            else None
        ),
        "openvino_version": openvino_v,
        "openvino_ok": _semver_at_least(openvino_v, "2026.0.0"),
        "openvino_setup_hint": (
            "Upgrade openvino>=2026.0 for stateful Whisper + AOT NPU compile."
            if not _semver_at_least(openvino_v, "2026.0.0")
            else None
        ),
        "npu_driver_version": npu_v,
        "npu_driver_ok": _semver_at_least(npu_v, "32.0.100.3104"),
        "npu_driver_setup_hint": (
            "NPU driver below floor 32.0.100.3104 — install latest from intel.com."
            if (sys.platform == "win32" and not _semver_at_least(npu_v, "32.0.100.3104"))
            else None
        ),
    }
```

In `_detect_extraction_capabilities_uncached`, add the prereqs block to the returned dict (just before the closing `return`):

```python
    return {
        "platform": platform.system(),
        "packages": packages,
        "commands": commands,
        "ollama": {
            "installed": ollama_binary is not None,
            "binary": ollama_binary,
            "models": ollama_models,
            "vision_models": ollama_vision_models,
        },
        "openvino_ready": openvino_ready,
        "openvino_genai_ready": openvino_genai_ready,
        "transcription_ready": transcription_ready,
        "transcription_model": str(transcription_model) if transcription_model.exists() else None,
        "local_agent_ready": local_agent_ready,
        "extraction_prereqs": _build_extraction_prereqs(),
    }
```

(Note: `ocr_ready` was already removed in Task 2 — confirm this dict matches.)

- [ ] **Step 4: Run tests to verify they pass**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_capabilities.py::test_inventory_reports_extraction_prereqs shared-vault/skills/document-extractor/augur/tests/test_capabilities.py::test_inventory_flags_transformers_pin_violation -v
```

Expected: PASS.

- [ ] **Step 5: Run full capabilities suite**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_capabilities.py -v
```

Expected: all green.

- [ ] **Step 6: Commit**

```powershell
git add src/lib/extraction/capabilities.py shared-vault/skills/document-extractor/augur/tests/test_capabilities.py
git commit -m "feat(extraction): surface NPU driver / transformers / OV version prereqs"
```

---

### Task 4: GLM-OCR availability detection

**Files:**
- Modify: `src/lib/extraction/capabilities.py`
- Modify: `shared-vault/skills/document-extractor/augur/tests/test_capabilities.py`

- [ ] **Step 1: Write the failing test**

Append to `test_capabilities.py`:

```python
def test_inventory_reports_glm_ocr_availability(monkeypatch) -> None:
    """GLM-OCR availability is detected by name in Ollama tag list."""
    from src.lib.extraction import capabilities

    monkeypatch.setattr(capabilities.shutil, "which", lambda name: "ollama.exe" if name == "ollama" else None)
    monkeypatch.setattr(
        capabilities,
        "_run_json_command",
        lambda _cmd, timeout_s=10: {"models": [{"name": "glm-ocr:latest"}, {"name": "qwen3:8b"}]},
    )
    monkeypatch.setattr(capabilities, "_ollama_show_text", lambda *_args, **_kwargs: "")

    inventory = capabilities.detect_extraction_capabilities(use_cache=False)

    assert inventory["ollama"]["glm_ocr_available"] is True


def test_inventory_reports_glm_ocr_missing(monkeypatch) -> None:
    from src.lib.extraction import capabilities

    monkeypatch.setattr(capabilities.shutil, "which", lambda name: "ollama.exe" if name == "ollama" else None)
    monkeypatch.setattr(
        capabilities,
        "_run_json_command",
        lambda _cmd, timeout_s=10: {"models": [{"name": "qwen3:8b"}]},
    )
    monkeypatch.setattr(capabilities, "_ollama_show_text", lambda *_args, **_kwargs: "")

    inventory = capabilities.detect_extraction_capabilities(use_cache=False)

    assert inventory["ollama"]["glm_ocr_available"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_capabilities.py::test_inventory_reports_glm_ocr_availability shared-vault/skills/document-extractor/augur/tests/test_capabilities.py::test_inventory_reports_glm_ocr_missing -v
```

Expected: FAIL — `glm_ocr_available` field doesn't exist.

- [ ] **Step 3: Add GLM-OCR detection in `capabilities.py`**

In `_detect_extraction_capabilities_uncached`, after the existing `ollama_models` / `ollama_vision_models` collection loop completes, compute:

```python
    glm_ocr_available = any(
        name.startswith("glm-ocr") for name in ollama_models
    )
```

Update the `ollama` block in the returned dict to include the new field:

```python
        "ollama": {
            "installed": ollama_binary is not None,
            "binary": ollama_binary,
            "models": ollama_models,
            "vision_models": ollama_vision_models,
            "glm_ocr_available": glm_ocr_available,
        },
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_capabilities.py -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```powershell
git add src/lib/extraction/capabilities.py shared-vault/skills/document-extractor/augur/tests/test_capabilities.py
git commit -m "feat(extraction): detect GLM-OCR availability via Ollama tag list"
```

---

### Task 5: Swap hardcoded Ollama OCR model from `llava` to `glm-ocr`

**Files:**
- Modify: `src/lib/extraction/extractor.py:255-275` (the `_run_ollama_ocr` function)
- Modify: `shared-vault/skills/document-extractor/augur/tests/test_extractor.py`

- [ ] **Step 1: Write the failing test**

Add to `test_extractor.py` (locate or create a TestOllamaOcr class near the bottom):

```python
class TestOllamaOcrModel:
    def test_ollama_ocr_uses_glm_ocr_model(self, monkeypatch):
        """Tier 1a Ollama OCR calls glm-ocr, not llava."""
        from src.lib.extraction import extractor

        captured_payload = {}

        class FakeResponse:
            def __init__(self, body: bytes) -> None:
                self._body = body
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return self._body

        def fake_urlopen(req, timeout=None):
            captured_payload["data"] = req.data
            return FakeResponse(b'{"response": "extracted text"}')

        import urllib.request as urllib_request
        monkeypatch.setattr(urllib_request, "urlopen", fake_urlopen)

        result = extractor._run_ollama_ocr("aGVsbG8=", "Extract all text.")

        assert result == "extracted text"
        import json as _json
        body = _json.loads(captured_payload["data"])
        assert body["model"] == "glm-ocr"
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_extractor.py::TestOllamaOcrModel -v
```

Expected: FAIL — current model is `"llava"`.

- [ ] **Step 3: Edit `extractor.py`**

In `src/lib/extraction/extractor.py`, find `_run_ollama_ocr` (around line 255):

```python
def _run_ollama_ocr(image_b64: str, prompt: str) -> str:
    """Run a single OCR request through the local Ollama vision model."""
    import urllib.request

    payload = json.dumps({
        "model": "llava",
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
    }).encode()
```

Change `"model": "llava"` to `"model": "glm-ocr"`.

Also update the `hardware_backend` recorded when this path succeeds. Find (around line 536):

```python
            hardware_backend="ollama-vision",
```

Change to:

```python
            hardware_backend="ollama-glm-ocr",
```

- [ ] **Step 4: Run test to verify it passes**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_extractor.py::TestOllamaOcrModel -v
```

Expected: PASS.

- [ ] **Step 5: Run full extractor suite to catch regressions**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_extractor.py -v
```

Expected: green except for any test that asserted `model: "llava"` or `hardware_backend: "ollama-vision"` — update those tests to the new strings.

- [ ] **Step 6: Commit**

```powershell
git add src/lib/extraction/extractor.py shared-vault/skills/document-extractor/augur/tests/test_extractor.py
git commit -m "feat(extraction): swap Tier 1a Ollama model from llava to glm-ocr"
```

---

### Task 6: Delete Tier 0.5 Tesseract branch from extractor

**Files:**
- Modify: `src/lib/extraction/extractor.py:418-443` (the `if ext in IMAGE_EXTENSIONS or ext in PDF_EXTENSIONS:` Tesseract block)
- Modify: `src/lib/extraction/extractor.py:472-482` (the `_try_tesseract` helper)
- Modify: `shared-vault/skills/document-extractor/augur/tests/test_extractor.py`

- [ ] **Step 1: Write the failing test**

Add to `test_extractor.py`:

```python
class TestTesseractTierRemoved:
    def test_no_try_tesseract_helper(self):
        """The _try_tesseract helper is gone."""
        from src.lib.extraction import extractor
        assert not hasattr(extractor, "_try_tesseract")

    def test_image_with_no_tier0_text_skips_to_tier1(self, monkeypatch, tmp_path):
        """Empty Tier 0 result on an image flows directly to Tier 1, not through Tesseract."""
        from src.lib.extraction import extractor

        called = {"tesseract": False, "tier1": False}

        def fake_request_llm_ocr(file_path, fmt, size, elapsed, partial, *, allow_cloud):
            called["tier1"] = True
            return extractor.ExtractionResult(
                success=True,
                markdown="from tier1",
                title=file_path.stem,
                tier_used=1,
                format=fmt,
                size_bytes=size,
                extraction_time=elapsed,
                ocr_applied=True,
            )

        monkeypatch.setattr(extractor, "_request_llm_ocr", fake_request_llm_ocr)

        # Force tier 0 to return empty for an image
        img = tmp_path / "scan.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        result = extractor.extract(str(img), max_tier=1, allow_cloud=False)

        assert called["tier1"] is True
        assert result.markdown == "from tier1"
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_extractor.py::TestTesseractTierRemoved -v
```

Expected: FAIL — `_try_tesseract` still exists; the Tier 0.5 branch still runs.

- [ ] **Step 3: Edit `extractor.py`**

In `src/lib/extraction/extractor.py`, find this block (around line 418-443):

```python
    # Empty result for image/scanned PDF — try Tesseract first (tier 0.5)
    # Tesseract is local and free, so it runs even at max_tier=0
    if ext in IMAGE_EXTENSIONS or ext in PDF_EXTENSIONS:
        tesseract_text = _try_tesseract(file_path)
        if tesseract_text:
            if _should_escalate_to_llm(file_path, tesseract_text, max_tier):
                return _request_llm_ocr(
                    file_path,
                    fmt,
                    size_bytes,
                    elapsed,
                    tesseract_text,
                    allow_cloud=allow_cloud,
                )
            elapsed = time.monotonic() - start
            return ExtractionResult(
                success=True,
                markdown=tesseract_text,
                title=file_path.stem,
                tier_used=0,
                format=fmt,
                size_bytes=size_bytes,
                extraction_time=elapsed,
                ocr_applied=True,
            )
```

Delete the entire block.

Find `_try_tesseract` (around line 472-482):

```python
def _try_tesseract(file_path: Path) -> str | None:
    """Try Tesseract OCR on an image or scanned PDF."""
    try:
        from src.lib.extraction.tesseract_ocr import is_tesseract_available, ocr_image  # noqa: PLC0415
        if not is_tesseract_available():
            return None
        return ocr_image(str(file_path))
    except (ImportError, Exception) as e:
        logger.debug("Tesseract OCR not available: %s", e)
        return None
```

Delete the function.

Also remove the `# Tesseract OCR (tier 0.5)` section header comment block above it.

- [ ] **Step 4: Run tests to verify they pass**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_extractor.py::TestTesseractTierRemoved -v
```

Expected: PASS.

- [ ] **Step 5: Run full extractor suite**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_extractor.py -v
```

Expected: green except for any test that exercised the Tesseract tier specifically — delete those tests, do not rewrite them. The Tesseract tier is gone.

- [ ] **Step 6: Commit**

```powershell
git add src/lib/extraction/extractor.py shared-vault/skills/document-extractor/augur/tests/test_extractor.py
git commit -m "refactor(extraction): delete Tier 0.5 Tesseract branch"
```

---

### Task 7: Add language hint and Hebrew short-circuit to extractor

**Files:**
- Modify: `src/lib/extraction/extractor.py` (`extract()` signature; Tier 1 routing)
- Modify: `shared-vault/skills/document-extractor/augur/tests/test_extractor.py`

- [ ] **Step 1: Write the failing test**

Add to `test_extractor.py`:

```python
class TestHebrewShortCircuit:
    def test_hebrew_hint_skips_ollama_goes_straight_to_tier1bc(self, monkeypatch, tmp_path):
        from src.lib.extraction import extractor

        called = {"ollama": False, "tier1bc": False}

        def fake_run_ollama_ocr(image_b64, prompt):
            called["ollama"] = True
            return "should not be called"

        def fake_request_llm_ocr(file_path, fmt, size, elapsed, partial, *, allow_cloud):
            called["tier1bc"] = True
            return extractor.ExtractionResult(
                success=True,
                markdown="from cloud",
                title=file_path.stem,
                tier_used=1,
                format=fmt,
                size_bytes=size,
                extraction_time=elapsed,
                ocr_applied=True,
                cloud_used=True,
                hardware_backend="passive-agent-vision",
            )

        monkeypatch.setattr(extractor, "_run_ollama_ocr", fake_run_ollama_ocr)
        monkeypatch.setattr(extractor, "_request_llm_ocr", fake_request_llm_ocr)

        img = tmp_path / "hebrew.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        result = extractor.extract(
            str(img),
            max_tier=1,
            allow_cloud=True,
            language_hint="he",
        )

        assert called["ollama"] is False
        assert called["tier1bc"] is True
        assert result.cloud_used is True

    def test_hebrew_hint_with_airplane_returns_needs_review(self, monkeypatch, tmp_path):
        from src.lib.extraction import extractor

        img = tmp_path / "hebrew.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        result = extractor.extract(
            str(img),
            max_tier=1,
            allow_cloud=False,
            language_hint="he",
        )

        assert result.success is True   # the run continues, just no OCR available
        assert result.escalation_reason == "hebrew_offline_unavailable"
        assert result.ocr_applied is False
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_extractor.py::TestHebrewShortCircuit -v
```

Expected: FAIL — `extract()` doesn't accept `language_hint`.

- [ ] **Step 3: Edit `extractor.py`**

In `src/lib/extraction/extractor.py`, change the `extract()` signature (around line 277):

```python
def extract(
    path: str,
    max_tier: int = 1,
    *,
    audio_model_dir: str | None = None,
    allow_cloud: bool = False,
    language_hint: str | None = None,
) -> ExtractionResult:
```

Update the docstring to mention `language_hint`:

```python
    """Extract a document to Markdown.

    Args:
        path: Filesystem path to the document.
        max_tier: Maximum extraction tier to use (0=parse only, 1=LLM OCR).
        audio_model_dir: Optional existing local Whisper model directory for audio.
        allow_cloud: Whether policy permits cloud vision escalation after local OCR fails.
        language_hint: Optional ISO language code. When "he" (Hebrew), Tier 1a Ollama is
            skipped and OCR routes directly to passive-agent cloud — GLM-OCR has no Hebrew
            support. With airplane mode on (allow_cloud=False) Hebrew docs return
            needs_review with reason hebrew_offline_unavailable.
    """
```

Now route the Hebrew short-circuit. Find the Tier 1 entry point — in this codebase that is the call to `_request_llm_ocr` from `_run_extraction`. The simplest hook is in `_request_llm_ocr` itself: it currently tries Ollama first, then falls back to Tier 1b/1c. We add an `is_hebrew` parameter that skips the Ollama attempt entirely.

In `_request_llm_ocr` (around line 489):

```python
def _request_llm_ocr(
    file_path: Path,
    fmt: str,
    size: int,
    elapsed: float,
    partial: str,
    *,
    allow_cloud: bool,
    is_hebrew: bool = False,
) -> ExtractionResult:
```

Inside the function, currently lines 518-539 try Ollama first. Wrap that block:

```python
    if not is_hebrew:
        # Try Ollama first (English / Latin / CJK content)
        try:
            merged_results: dict[str, str] = {}
            for idx, request in enumerate(llm_requests):
                ocr_text = _run_ollama_ocr(request["image_b64"], request["prompt"])
                if not ocr_text:
                    raise RuntimeError(f"Ollama OCR returned no text for request {idx}")
                merged_results[str(idx)] = ocr_text
            return ExtractionResult(
                success=True,
                markdown=merge_llm_results(partial_markdown, merged_results),
                title=file_path.stem,
                tier_used=1,
                format=fmt,
                size_bytes=size,
                extraction_time=elapsed,
                ocr_applied=True,
                local_agent_used=True,
                hardware_backend="ollama-glm-ocr",
            )
        except Exception as exc:
            logger.debug("Ollama OCR unavailable for %s: %s", file_path.name, exc)
```

When `is_hebrew=True` AND `allow_cloud=False`, the function must short-circuit to a `needs_review`-style result before reaching the Tier 1b/1c paths. Add a guard at the top of the function (after the `if not llm_requests` early return):

```python
    if is_hebrew and not allow_cloud:
        return ExtractionResult(
            success=True,
            markdown=partial,
            title=file_path.stem,
            tier_used=0,
            format=fmt,
            size_bytes=size,
            extraction_time=elapsed,
            ocr_applied=False,
            escalation_reason="hebrew_offline_unavailable",
        )
```

Now thread `language_hint` through the existing call sites of `_request_llm_ocr` inside `_run_extraction` (the body of `extract()`). Search for `_request_llm_ocr(` in `extractor.py`. There are three call sites in the current code (around lines 400, 425, and 447). Update each to pass `is_hebrew=(language_hint == "he")`. Example for the first:

```python
        if _should_escalate_to_llm(file_path, markdown, max_tier):
            return _request_llm_ocr(
                file_path,
                fmt,
                size_bytes,
                elapsed,
                markdown,
                allow_cloud=allow_cloud,
                is_hebrew=(language_hint == "he"),
            )
```

Note: the second call site (around line 425) was inside the deleted Tesseract block — confirm it's already gone after Task 6. Only the first and third remain.

- [ ] **Step 4: Run tests to verify they pass**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_extractor.py::TestHebrewShortCircuit -v
```

Expected: PASS.

- [ ] **Step 5: Run full extractor suite**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_extractor.py -v
```

Expected: green.

- [ ] **Step 6: Commit**

```powershell
git add src/lib/extraction/extractor.py shared-vault/skills/document-extractor/augur/tests/test_extractor.py
git commit -m "feat(extraction): Hebrew language hint short-circuits past local OCR"
```

---

### Task 8: Replace Whisper `device="AUTO"` with explicit NPU/GPU/CPU probe

**Files:**
- Modify: `src/lib/extraction/transcription.py:67-91` (the `_transcribe_openvino` function)
- Modify: `shared-vault/skills/document-extractor/augur/tests/test_audio_extractor.py` (or new `test_transcription.py`)

- [ ] **Step 1: Write the failing test**

If `shared-vault/skills/document-extractor/augur/tests/test_transcription.py` does not exist, create it. Add:

```python
"""Tests for the OpenVINO Whisper device probe and large-v3 default."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def test_openvino_probe_walks_npu_gpu_cpu(monkeypatch, tmp_path: Path) -> None:
    """Device probe tries NPU first; on RuntimeError it falls through to GPU then CPU."""
    from src.lib.extraction import transcription

    audio = tmp_path / "sample.mp3"
    audio.write_bytes(b"\x00" * 32)

    model_dir = tmp_path / "model"
    model_dir.mkdir()

    attempts = []

    class FakePipeline:
        def __init__(self, model_path, device):
            attempts.append(device)
            if device != "CPU":
                raise RuntimeError(f"{device} probe failed")
        def generate(self, audio_path):
            mock = MagicMock()
            mock.text = "hello world"
            return mock

    fake_module = MagicMock()
    fake_module.WhisperPipeline = FakePipeline
    monkeypatch.setattr(transcription, "_module_available", lambda name: name == "openvino_genai")
    monkeypatch.setattr(transcription, "_has_ffmpeg", lambda: True)
    monkeypatch.setitem(__import__("sys").modules, "openvino_genai", fake_module)

    result = transcription._transcribe_openvino(audio, model_dir=str(model_dir))

    assert attempts == ["NPU", "GPU", "CPU"]
    assert result.success is True
    assert result.transcript == "hello world"
    assert result.backend == "CPU"


def test_openvino_probe_records_npu_on_first_success(monkeypatch, tmp_path: Path) -> None:
    from src.lib.extraction import transcription

    audio = tmp_path / "sample.mp3"
    audio.write_bytes(b"\x00" * 32)

    model_dir = tmp_path / "model"
    model_dir.mkdir()

    class FakePipeline:
        def __init__(self, model_path, device):
            self.device = device
        def generate(self, audio_path):
            mock = MagicMock()
            mock.text = "transcribed"
            return mock

    fake_module = MagicMock()
    fake_module.WhisperPipeline = FakePipeline
    monkeypatch.setattr(transcription, "_module_available", lambda name: name == "openvino_genai")
    monkeypatch.setattr(transcription, "_has_ffmpeg", lambda: True)
    monkeypatch.setitem(__import__("sys").modules, "openvino_genai", fake_module)

    result = transcription._transcribe_openvino(audio, model_dir=str(model_dir))

    assert result.backend == "NPU"
    assert result.success is True
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_transcription.py -v
```

Expected: FAIL — current `_transcribe_openvino` calls with a single `device` argument, no probe loop.

- [ ] **Step 3: Edit `transcription.py`**

In `src/lib/extraction/transcription.py`, find `_transcribe_openvino` (around line 67-91):

```python
def _transcribe_openvino(path: Path, *, model_dir: str, device: str = "AUTO") -> TranscriptResult:
    try:
        import openvino_genai

        pipeline = openvino_genai.WhisperPipeline(str(model_dir), device)
        result = pipeline.generate(str(path))
        transcript = _stringify_transcript(result)
        return TranscriptResult(
            success=bool(transcript.strip()),
            transcript=transcript,
            method="openvino-whisper",
            backend=device,
            confidence="medium",
            needs_review=not bool(transcript.strip()),
        )
    except Exception as exc:
        return TranscriptResult(
            success=False,
            transcript="",
            method="openvino-whisper",
            backend=device,
            cloud_used=False,
            needs_review=True,
            error=str(exc),
        )
```

Replace with:

```python
DEFAULT_OPENVINO_DEVICES: tuple[str, ...] = ("NPU", "GPU", "CPU")


def _transcribe_openvino(
    path: Path,
    *,
    model_dir: str,
    devices: tuple[str, ...] = DEFAULT_OPENVINO_DEVICES,
) -> TranscriptResult:
    try:
        import openvino_genai
    except Exception as exc:  # noqa: BLE001 — import failure is structural
        return TranscriptResult(
            success=False,
            transcript="",
            method="openvino-whisper",
            backend="unavailable",
            cloud_used=False,
            needs_review=True,
            error=str(exc),
        )

    last_err: Exception | None = None
    for device in devices:
        try:
            pipeline = openvino_genai.WhisperPipeline(str(model_dir), device)
            result = pipeline.generate(str(path))
            transcript = _stringify_transcript(result)
            return TranscriptResult(
                success=bool(transcript.strip()),
                transcript=transcript,
                method="openvino-whisper",
                backend=device,
                confidence="medium",
                needs_review=not bool(transcript.strip()),
            )
        except Exception as exc:  # noqa: BLE001 — device probe; record and continue
            last_err = exc
            continue

    return TranscriptResult(
        success=False,
        transcript="",
        method="openvino-whisper",
        backend="all_devices_failed",
        cloud_used=False,
        needs_review=True,
        error=str(last_err) if last_err else "no devices attempted",
    )
```

Also update the call site in `transcribe_audio` (around line 60). Currently:

```python
    if _module_available("openvino_genai"):
        return _transcribe_openvino(audio_path, model_dir=str(local_model_path), device=device)
```

Change to:

```python
    if _module_available("openvino_genai"):
        return _transcribe_openvino(audio_path, model_dir=str(local_model_path))
```

The `device` parameter at the `transcribe_audio` level is now unused for the OV path; either remove it from the public signature or leave it for the faster-whisper path. Inspect `transcribe_audio` and remove `device=` only if it's no longer referenced.

- [ ] **Step 4: Run tests to verify they pass**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_transcription.py -v
```

Expected: PASS.

- [ ] **Step 5: Run audio_extractor tests for regressions**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_audio_extractor.py -v
```

Expected: green. If any test asserted `device="AUTO"` or the old call shape, update it.

- [ ] **Step 6: Commit**

```powershell
git add src/lib/extraction/transcription.py shared-vault/skills/document-extractor/augur/tests/test_transcription.py shared-vault/skills/document-extractor/augur/tests/test_audio_extractor.py
git commit -m "fix(extraction): replace Whisper device=AUTO with explicit NPU/GPU/CPU probe"
```

---

### Task 9: Whisper-large-v3 default; drop Win faster-whisper branch

**Files:**
- Modify: `src/lib/extraction/transcription.py` (model defaults + Win faster-whisper removal)
- Modify: `shared-vault/skills/document-extractor/augur/tests/test_transcription.py`

- [ ] **Step 1: Write the failing test**

Append to `test_transcription.py`:

```python
def test_default_whisper_model_is_large_v3() -> None:
    from src.lib.extraction import transcription

    assert transcription.DEFAULT_LOCAL_WHISPER_MODEL_NAME == "whisper-large-v3-int8-ov"


def test_can_transcribe_returns_false_on_windows_without_openvino(monkeypatch, tmp_path) -> None:
    """faster-whisper alone is not sufficient on Windows — OpenVINO must be present."""
    from src.lib.extraction import transcription
    import sys

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(transcription, "_has_ffmpeg", lambda: True)
    monkeypatch.setattr(transcription, "_local_model_path", lambda model_dir=None: tmp_path)
    monkeypatch.setattr(
        transcription,
        "_module_available",
        lambda name: name == "faster_whisper",  # OV missing
    )

    assert transcription.can_transcribe_audio() is False


def test_can_transcribe_returns_true_on_macos_with_faster_whisper(monkeypatch, tmp_path) -> None:
    from src.lib.extraction import transcription
    import sys

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(transcription, "_has_ffmpeg", lambda: True)
    monkeypatch.setattr(transcription, "_local_model_path", lambda model_dir=None: tmp_path)
    monkeypatch.setattr(
        transcription,
        "_module_available",
        lambda name: name == "faster_whisper",
    )

    assert transcription.can_transcribe_audio() is True
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_transcription.py::test_default_whisper_model_is_large_v3 shared-vault/skills/document-extractor/augur/tests/test_transcription.py::test_can_transcribe_returns_false_on_windows_without_openvino -v
```

Expected: FAIL — default is `faster-whisper-tiny.en`; current `can_transcribe_audio` accepts faster-whisper on any platform.

- [ ] **Step 3: Edit `transcription.py`**

Locate (around line 14):

```python
DEFAULT_LOCAL_WHISPER_MODEL_NAME = "faster-whisper-tiny.en"
```

Replace with:

```python
DEFAULT_LOCAL_WHISPER_MODEL_NAME = "whisper-large-v3-int8-ov"
```

Locate `can_transcribe_audio` (around line 32):

```python
def can_transcribe_audio(model_dir: str | None = None) -> bool:
    """Return whether a local transcription backend is available."""
    return (
        _has_ffmpeg()
        and _local_model_path(model_dir) is not None
        and (_module_available("openvino_genai") or _module_available("faster_whisper"))
    )
```

Replace with:

```python
def can_transcribe_audio(model_dir: str | None = None) -> bool:
    """Return whether a local transcription backend is available on this OS.

    Win/Linux: OpenVINO Whisper is the only supported local path.
    macOS: faster-whisper is the supported local path (OV macOS arm64 is CPU-only;
           faster-whisper uses Metal/CoreML for real acceleration).
    """
    if not _has_ffmpeg():
        return False
    if _local_model_path(model_dir) is None:
        return False
    if sys.platform == "darwin":
        return _module_available("faster_whisper") or _module_available("openvino_genai")
    return _module_available("openvino_genai")
```

Make sure `import sys` is present at the top of the file (add if missing).

Locate `transcribe_audio` (around line 41):

```python
def transcribe_audio(path: str, *, model_dir: str | None = None, device: str = "AUTO") -> TranscriptResult:
    ...
    if _module_available("openvino_genai"):
        return _transcribe_openvino(audio_path, model_dir=str(local_model_path))
    if _module_available("faster_whisper"):
        return _transcribe_faster_whisper(audio_path, model_dir=str(local_model_path), device=device)
    return _unavailable("No local transcription backend is installed")
```

Replace the dispatch logic with OS-aware selection:

```python
def transcribe_audio(path: str, *, model_dir: str | None = None) -> TranscriptResult:
    """Transcribe audio with local backends only.

    Win/Linux: OpenVINO Whisper-large-v3 INT8 with NPU→GPU→CPU device probe.
    macOS: faster-whisper (Metal/CoreML).
    """
    audio_path = Path(path)
    if not audio_path.exists():
        return _unavailable(f"Audio file does not exist: {audio_path}")
    if audio_path.suffix.lower() not in AUDIO_EXTENSIONS:
        return _unavailable(f"Unsupported audio extension: {audio_path.suffix}")
    if not _has_ffmpeg():
        return _unavailable("ffmpeg or avconv is required for local audio transcription")

    local_model_path = _local_model_path(model_dir)
    if local_model_path is None:
        return _unavailable("A local transcription model directory is required")

    if sys.platform == "darwin":
        if _module_available("faster_whisper"):
            return _transcribe_faster_whisper(audio_path, model_dir=str(local_model_path))
        if _module_available("openvino_genai"):
            return _transcribe_openvino(audio_path, model_dir=str(local_model_path))
        return _unavailable("No local transcription backend installed (need faster-whisper or openvino-genai)")

    if _module_available("openvino_genai"):
        return _transcribe_openvino(audio_path, model_dir=str(local_model_path))
    return _unavailable("OpenVINO GenAI is required for local transcription on this OS")
```

Update `_transcribe_faster_whisper` signature to drop the unused `device` argument and let it pick its own device, OR keep the argument with a sensible default `"auto"`. Inspect the current `_transcribe_faster_whisper` body and choose. The simplest is to remove the parameter:

```python
def _transcribe_faster_whisper(
    path: Path,
    *,
    model_dir: str | None = None,
) -> TranscriptResult:
    local_model_path = _local_model_path(model_dir)
    if local_model_path is None:
        return _unavailable("A local faster-whisper model directory is required")

    try:
        from faster_whisper import WhisperModel

        model = WhisperModel(str(local_model_path), device="auto", compute_type="int8")
        segments, info = model.transcribe(str(path))
        transcript = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        language_probability = getattr(info, "language_probability", None)
        return TranscriptResult(
            success=bool(transcript),
            transcript=transcript,
            method="faster-whisper",
            backend="auto",
            duration_s=getattr(info, "duration", None),
            language=getattr(info, "language", None),
            confidence=_confidence_from_probability(language_probability),
            cloud_used=False,
            needs_review=not bool(transcript),
        )
    except Exception as exc:  # noqa: BLE001
        return TranscriptResult(
            success=False,
            transcript="",
            method="faster-whisper",
            backend="auto",
            cloud_used=False,
            needs_review=True,
            error=str(exc),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_transcription.py -v
```

Expected: PASS.

- [ ] **Step 5: Run audio_extractor tests for regressions**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_audio_extractor.py -v
```

Expected: green. Update any test that called `transcribe_audio(..., device="AUTO")` to drop the `device` kwarg.

- [ ] **Step 6: Commit**

```powershell
git add src/lib/extraction/transcription.py shared-vault/skills/document-extractor/augur/tests/test_transcription.py shared-vault/skills/document-extractor/augur/tests/test_audio_extractor.py
git commit -m "feat(extraction): default Whisper to large-v3 INT8 OV; OS-aware dispatch"
```

---

### Task 10: Surface new fields in `get-extraction-status`

**Files:**
- Modify: `shared-vault/skills/document-extractor/scripts/mcp/tools_extract.py` (the `get_extraction_status_impl` function)
- Modify: `shared-vault/skills/document-extractor/augur/tests/test_tools_extract.py`

- [ ] **Step 1: Locate the current `get-extraction-status` impl**

Read `shared-vault/skills/document-extractor/scripts/mcp/tools_extract.py` and find the implementation function (search for `get_extraction_status_impl` or `get-extraction-status`). Note the exact line range.

- [ ] **Step 2: Write the failing test**

Append to `test_tools_extract.py`:

```python
def test_get_extraction_status_surfaces_glm_ocr_and_prereqs(monkeypatch) -> None:
    """get-extraction-status reports the OCR engine, OS chain, and 2026 prereqs."""
    from shared_vault.skills.document_extractor.scripts.mcp import tools_extract  # adjust import to actual module path
    import json as _json

    fake_inventory = {
        "platform": "Windows",
        "ollama": {
            "installed": True,
            "binary": "C:/Users/test/AppData/Local/Programs/Ollama/ollama.exe",
            "models": ["glm-ocr:latest", "qwen3:8b"],
            "vision_models": [],
            "glm_ocr_available": True,
        },
        "openvino_ready": True,
        "openvino_genai_ready": True,
        "transcription_ready": True,
        "transcription_model": "/cache/whisper-large-v3-int8-ov",
        "local_agent_ready": True,
        "extraction_prereqs": {
            "transformers_version": "4.52.4",
            "transformers_ok": True,
            "transformers_setup_hint": None,
            "optimum_intel_version": "1.25.3",
            "optimum_intel_ok": True,
            "optimum_intel_setup_hint": None,
            "openvino_version": "2026.0.0",
            "openvino_ok": True,
            "openvino_setup_hint": None,
            "npu_driver_version": "32.0.100.3104",
            "npu_driver_ok": True,
            "npu_driver_setup_hint": None,
        },
        "packages": {},
        "commands": {},
        "policy": {
            "airplane_mode_enabled": False,
            "cloud_escalation_allowed": True,
            "local_agent_escalation_allowed": True,
        },
    }

    monkeypatch.setattr(
        tools_extract,
        "detect_extraction_capabilities",
        lambda **kwargs: fake_inventory,
    )

    payload = _json.loads(tools_extract._get_extraction_status_impl())  # adjust to real entry name
    assert payload["ocr_engine"] == "glm-ocr"
    assert payload["ocr_engine_available"] is True
    assert payload["os_default_chain"]["ocr"] == ["ollama-glm-ocr", "passive-agent-vision"]
    assert payload["os_default_chain"]["transcription"] == ["openvino-whisper"]
    assert payload["prereqs"]["transformers_ok"] is True
    assert payload["prereqs"]["npu_driver_ok"] is True
```

(Adjust the import path / entry name to match the actual module shape — read the module first and align the test to the real surface.)

- [ ] **Step 3: Run test to verify it fails**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_tools_extract.py::test_get_extraction_status_surfaces_glm_ocr_and_prereqs -v
```

Expected: FAIL.

- [ ] **Step 4: Edit `tools_extract.py` to populate the new fields**

In `get_extraction_status_impl` (or the equivalent function discovered in Step 1), construct a JSON-serializable payload that includes:

```python
import sys

def _build_os_default_chain() -> dict[str, list[str]]:
    if sys.platform == "darwin":
        ocr_chain = ["ollama-glm-ocr", "passive-agent-vision"]
        transcription_chain = ["faster-whisper", "openvino-whisper"]
    else:
        ocr_chain = ["ollama-glm-ocr", "passive-agent-vision"]
        transcription_chain = ["openvino-whisper"]
    return {"ocr": ocr_chain, "transcription": transcription_chain}
```

Then in the existing implementation function, locate where the inventory is fetched and the JSON payload is built. Add these fields to the payload dict before serialization:

```python
    inventory = detect_extraction_capabilities()
    prereqs = inventory.get("extraction_prereqs", {})
    ollama_block = inventory.get("ollama", {})

    payload = {
        # ... existing fields ...
        "ocr_engine": "glm-ocr",
        "ocr_engine_available": ollama_block.get("glm_ocr_available", False),
        "os_default_chain": _build_os_default_chain(),
        "prereqs": prereqs,
    }
```

If the existing payload already contains overlapping fields (e.g., `policy`, `airplane_mode`), keep them — only add the new ones. Drop any field that referenced Tesseract or `markitdown_ocr_ready`.

- [ ] **Step 5: Run test to verify it passes**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_tools_extract.py::test_get_extraction_status_surfaces_glm_ocr_and_prereqs -v
```

Expected: PASS.

- [ ] **Step 6: Run full tools_extract suite**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_tools_extract.py -v
```

Expected: green. Update or delete any test that asserted Tesseract-related fields in the status payload.

- [ ] **Step 7: Commit**

```powershell
git add shared-vault/skills/document-extractor/scripts/mcp/tools_extract.py shared-vault/skills/document-extractor/augur/tests/test_tools_extract.py
git commit -m "feat(extraction): surface GLM-OCR engine + OS chain + 2026 prereqs in get-extraction-status"
```

---

### Task 11: Delete Tesseract module and update dependencies

**Files:**
- Delete: `src/lib/extraction/tesseract_ocr.py`
- Delete: `shared-vault/skills/document-extractor/augur/tests/test_tesseract_ocr.py`
- Modify: `pyproject.toml`
- Modify: `src/lib/extraction/__init__.py` (only if it imports from `tesseract_ocr`)

- [ ] **Step 1: Confirm no remaining imports of `tesseract_ocr`**

```powershell
uv run python -c "import subprocess; subprocess.run(['rg', '-l', 'tesseract_ocr', 'src', 'shared-vault'], check=False)"
```

Or use the Grep tool. If any files other than `tesseract_ocr.py` and `test_tesseract_ocr.py` still import the module, fix those callers first — list each path and what it expected, then either remove the call or replace with the new ladder.

- [ ] **Step 2: Delete the Tesseract module and its tests**

```powershell
git rm src/lib/extraction/tesseract_ocr.py
git rm shared-vault/skills/document-extractor/augur/tests/test_tesseract_ocr.py
```

- [ ] **Step 3: Update `pyproject.toml` dependencies**

Open `pyproject.toml`. Locate the dependencies block (currently around line 25-60). Make the following edits:

Remove these lines:

```text
    "markitdown-ocr>=0.1.0",
    "pytesseract>=0.3.13",
```

Add these lines (preserving alphabetical order if the block is sorted; otherwise append):

```text
    "openvino>=2026.0",
    "openvino-genai>=2026.0",
    "optimum-intel>=1.25.2",
    "transformers==4.52.*",
```

If `transformers` is already in the block at a different version, replace the existing line with the pinned `transformers==4.52.*`.

If `openvino` and/or `openvino-genai` are already pinned to an older version, update them to `>=2026.0`.

- [ ] **Step 4: Resolve the lockfile**

```powershell
uv sync
```

Expected: lockfile updates without error. If `uv sync` fails because `transformers==4.52.*` conflicts with a transitive constraint, surface the conflict and stop — resolving conflicting deps is out of scope for this task.

- [ ] **Step 5: Run the full extraction test suite**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/ -x -q
```

Expected: all green.

- [ ] **Step 6: Run a wider smoke check**

```powershell
uv run pytest shared-vault/skills/document-extractor/augur/tests/ shared-vault/skills/ingest/augur/tests/ -x -q
```

Expected: green for the slice; ingest tests that depend on extraction may need follow-up updates if any referenced Tesseract directly. If a downstream test fails because it still expects Tesseract availability, fix it (drop the Tesseract assertion) within this task — do not skip.

- [ ] **Step 7: Manual verification on this Windows AI PC**

Run a quick end-to-end check before committing:

```powershell
uv run python -c "from src.lib.extraction import detect_extraction_capabilities; import json; print(json.dumps(detect_extraction_capabilities(use_cache=False), indent=2, default=str))"
```

Confirm: no `tesseract`, no `pytesseract`, no `markitdown-ocr`. `openvino_genai_ready` is True. `extraction_prereqs.npu_driver_ok` is True (or surfaces a hint).

```powershell
uv run python -c "from src.lib.extraction import transcribe_audio; print(transcribe_audio('test.mp3').backend)"
```

(Use a real small mp3 file or skip if none available — record the result.)

- [ ] **Step 8: Commit**

```powershell
git add pyproject.toml uv.lock src/lib/extraction/tesseract_ocr.py shared-vault/skills/document-extractor/augur/tests/test_tesseract_ocr.py
git commit -m "refactor(extraction): retire Tesseract module and update deps for OV 2026.0"
```

---

### Task 12: Final integration check and worktree merge readiness

**Files:**
- No code changes; verification only

- [ ] **Step 1: Run the slash-command-driven build/test/lint loop**

Per CLAUDE.md rules 19 and 29, verify through the canonical loops:

```powershell
# Inside the worktree:
/auto-test-pytest
/auto-lint
/auto-test-build
```

Each must report green. If `/auto-test-build` flags an MCP surface drift, that's a real downstream regression — surface it and fix in this slice.

- [ ] **Step 2: Verify the spec is fully implemented**

Walk the spec section-by-section and tick off each implementation phase against the commits in this branch:

```powershell
git log --oneline origin/main..HEAD
```

Expected commits (in order):

- refactor(extraction): drop Tesseract/markitdown-ocr from capability inventory
- feat(extraction): surface NPU driver / transformers / OV version prereqs
- feat(extraction): detect GLM-OCR availability via Ollama tag list
- feat(extraction): swap Tier 1a Ollama model from llava to glm-ocr
- refactor(extraction): delete Tier 0.5 Tesseract branch
- feat(extraction): Hebrew language hint short-circuits past local OCR
- fix(extraction): replace Whisper device=AUTO with explicit NPU/GPU/CPU probe
- feat(extraction): default Whisper to large-v3 INT8 OV; OS-aware dispatch
- feat(extraction): surface GLM-OCR engine + OS chain + 2026 prereqs in get-extraction-status
- refactor(extraction): retire Tesseract module and update deps for OV 2026.0

- [ ] **Step 3: Manual end-to-end verification (Windows AI PC)**

Run each of these and record the result in the task tracker:

1. **Whisper on NPU:**
   ```powershell
   uv run python -c "from src.lib.extraction import transcribe_audio; r = transcribe_audio('sample.mp3'); print(r.backend, r.success, r.transcript[:80])"
   ```
   Expected: `backend == "NPU"`, `success == True`. Use any small WAV/MP3 file.

2. **GLM-OCR on a scanned receipt:**
   ```powershell
   uv run python -c "from src.lib.extraction import extract; r = extract('scan.png', max_tier=1, allow_cloud=False); print(r.hardware_backend, r.success, len(r.markdown))"
   ```
   Expected: `hardware_backend == "ollama-glm-ocr"`, `success == True`, non-empty markdown.

3. **Hebrew document with airplane mode on:**
   ```powershell
   uv run python -c "from src.lib.extraction import extract; r = extract('hebrew.png', max_tier=1, allow_cloud=False, language_hint='he'); print(r.escalation_reason, r.ocr_applied)"
   ```
   Expected: `escalation_reason == "hebrew_offline_unavailable"`, `ocr_applied == False`.

4. **Hebrew document with airplane mode off (cloud allowed):**
   ```powershell
   uv run python -c "from src.lib.extraction import extract; r = extract('hebrew.png', max_tier=1, allow_cloud=True, language_hint='he'); print(r.cloud_used, r.hardware_backend)"
   ```
   Expected: passes through to Tier 1b/1c (the result depends on whether running inside an AI client context — both outcomes are acceptable, but `language_hint='he'` must NOT call Ollama on the way).

- [ ] **Step 4: Update the spec status**

Edit the spec frontmatter:

```yaml
---
title: OpenVINO + Ollama Offline Mode Design
date: 2026-05-09
status: implemented
scope: design
supersedes_partial: 2026-05-07-ai-pc-brain-inbox-design.md (extraction layer only)
---
```

Commit:

```powershell
git add docs/superpowers/specs/2026-05-09-openvino-ollama-offline-design.md
git commit -m "docs(extraction): mark OpenVINO + Ollama offline spec implemented"
```

- [ ] **Step 5: Worktree handoff to /dev-merge**

The branch is ready for the user to run `/dev-merge` per CLAUDE.md rule 24/26. Do not run `/dev-merge` yourself — it's a user-driven slash command. Report:

```text
Branch openvino-ollama-offline is ready for /dev-merge.

12 commits ahead of main. All loop checks green. Manual verification
recorded in task tracker. Spec status flipped to "implemented".

Worktree path: C:\Users\intel\Projects\Augur\.worktrees\openvino-ollama-offline
```

---

## Self-Review Notes

Spec coverage walked task-by-task:

- ✅ "Drop Tesseract / markitdown-ocr from capability inventory" → Task 2
- ✅ "Add 2026 prereq checks (NPU driver, transformers pin, openvino>=2026.0)" → Task 3
- ✅ "GLM-OCR availability via Ollama tag list" → Task 4
- ✅ "Swap Ollama OCR model from llava to glm-ocr" → Task 5
- ✅ "Delete Tier 0.5 Tesseract branch" → Task 6
- ✅ "Hebrew language hint short-circuit" → Task 7
- ✅ "Replace Whisper device=AUTO with explicit NPU/GPU/CPU probe" → Task 8
- ✅ "Whisper-large-v3 default; drop Win faster-whisper branch" → Task 9
- ✅ "get-extraction-status surface upgrade" → Task 10
- ✅ "Tesseract module deletion + pyproject cleanup" → Task 11
- ✅ Manual verification + worktree handoff → Task 12

Type consistency: `language_hint` (Task 7), `hardware_backend == "ollama-glm-ocr"` (Tasks 5 & 7), `os_default_chain` (Task 10), `extraction_prereqs` (Tasks 3 & 10) — all consistent across tasks.

No placeholders. Every step has the exact code or command needed.
