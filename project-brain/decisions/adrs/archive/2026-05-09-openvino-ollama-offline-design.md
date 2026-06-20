---
title: OpenVINO + Ollama Offline Mode Design
date: 2026-05-09
status: implemented
scope: design
supersedes_partial: 2026-05-07-ai-pc-brain-inbox-design.md (extraction layer only)
---

# OpenVINO + Ollama Offline Mode Design

## Purpose

Make Augur's offline mode (airplane mode) work cleanly with **one OCR engine
and one ASR engine** per OS, using the existing passive-agent pattern for
all cloud escalation. No new cloud SDKs are added.

The active local backends are Ollama (cross-OS) and OpenVINO
(transcription-only on Win; transcription on Mac via faster-whisper for
Metal/CoreML acceleration since OV macOS arm64 is CPU-only). Cloud
escalation goes through `run_cloud_vision_ocr` and a future symmetric
audio variant — no Mistral/ElevenLabs/etc. SDKs are introduced.

Hebrew OCR routes directly to cloud (passive agent) because no local OCR
engine in the active ladder supports Hebrew well. Bringing in EasyOCR for
offline Hebrew is tracked as a deferred option.

## Current State

Implemented today:

- `src/lib/extraction/extractor.py` runs a tiered ladder:
  Tier 0 (MarkItDown / PyMuPDF) → Tier 0.5 (Tesseract) → Tier 1a (Ollama
  `llava` hardcoded at `extractor.py:260`) → Tier 1b (`needs_llm=True`
  hand-off when `is_ai_client_context()`) → Tier 1c
  (`run_cloud_vision_ocr` passive-agent CLI subprocess via
  `cloud_vision.py`).
- `src/lib/extraction/transcription.py` has an OpenVINO Whisper path with
  `device="AUTO"` (which silently never reaches NPU on Intel — OpenVINO
  excludes NPU from AUTO) and a faster-whisper path. No cloud audio
  escalation today.
- `src/lib/extraction/capabilities.py` reports a wide inventory including
  Tesseract, `pytesseract`, `markitdown-ocr`, `pdf2image`,
  `faster-whisper`, OpenVINO, Ollama models.
- `src/mcp/augur_framework/tools/infrastructure/local_backends.py` owns
  airplane-mode toggling and the Ollama detection / launch readiness probe.
- `capabilities.get_extraction_policy()` returns
  `cloud_escalation_allowed = not airplane_mode_enabled`. Callers pass
  `allow_cloud=...` into `extract()`.

Stale or out of date:

- Tier 0.5 Tesseract path. Tesseract is a 2010-era OCR; dominated by
  modern OCR-VLMs.
- Tier 1a Ollama model is hardcoded `llava` — beaten on every benchmark by
  GLM-OCR (current OmniDocBench v1.5 #1).
- `device="AUTO"` for Whisper silently never reaches NPU 4 on this AI PC.
- `whisper-base` is not the right default in 2026 — Whisper-large-v3 INT8
  is small enough and far better, including Hebrew support.

## Goals

- One local OCR engine: **Ollama GLM-OCR** on both Windows and macOS.
- One ASR engine per OS:
  - Windows: **OpenVINO Whisper-large-v3 INT8** with explicit
    `["NPU", "GPU", "CPU"]` device probe.
  - macOS: **faster-whisper** (Metal/CoreML) — forced exception because
    OpenVINO macOS arm64 is CPU-only.
- Hebrew OCR (any OS): skip local, route directly to passive-agent cloud
  via the existing `run_cloud_vision_ocr` path.
- All cloud escalation (OCR + audio) reuses the passive-agent pattern. No
  new SDK dependencies.
- Drop Tesseract, `markitdown-ocr`, faster-whisper-on-Windows from the
  active ladder.
- `get-extraction-status` accurately reports the new ladder, the active
  OCR/ASR models, and any 2026 prerequisite gaps (NPU driver,
  optional vulnerable conversion packages, OpenVINO version).

## Non-Goals

- Replacing the chat LLM backend with OpenVINO GenAI (next sub-project).
- Brain Inbox dashboard wiring, source-card writing, RAG indexing
  (May-07 plan).
- EasyOCR + OpenVINO Hebrew rung. Tracked alternative if cloud-Hebrew
  proves expensive or quality-poor; not in this slice.
- PaddleOCR-VL OpenVINO module for AI-PC NPU OCR. Tracked alternative if
  GLM-OCR speed on Vulkan iGPU proves unacceptable.
- Parakeet-TDT or other English-only ASR engines. Whisper-large-v3 covers
  English + Hebrew with one model.
- Direct cloud OCR / ASR provider SDKs (Mistral, ElevenLabs, AssemblyAI,
  Deepgram). Cloud routes through the passive-agent CLI today and stays
  that way.
- A cloud audio escalation path. Audio is offline-only in this slice; if
  both local backends fail we return `needs_review`. Adding cloud audio
  later requires extending `cloud_vision.py` to handle audio inputs in the
  passive-agent flow — separate decision.

## Architecture

### Modules

| Module | Status | Responsibility |
|---|---|---|
| `src/lib/extraction/capabilities.py` | modify | Drop Tesseract / `markitdown-ocr` / `pytesseract` from inventory. Add GLM-OCR availability check (Ollama tag list). Add 2026 prereq checks: NPU driver `>= 32.0.100.3104`, absence of vulnerable `transformers` 4.x conversion packages, `openvino >= 2026.0`. |
| `src/lib/extraction/extractor.py` | modify | Drop the Tesseract tier. Swap hardcoded `model: "llava"` to `"glm-ocr"`. Add Hebrew language-hint short-circuit — when hint is `"he"`, skip the local LLM rung and go straight to passive-agent cloud. |
| `src/lib/extraction/transcription.py` | modify | Replace `device="AUTO"` with explicit probe `["NPU", "GPU", "CPU"]`. Default model becomes `whisper-large-v3-int8-ov`. Drop `_transcribe_faster_whisper` on Windows; keep it macOS-only behind a `sys.platform == "darwin"` gate. |
| `src/lib/extraction/cloud_vision.py` | unchanged | Already correct shape. Used by both default-cloud and Hebrew-direct-cloud. |
| `src/lib/extraction/audio_extractor.py` | modify | Route through new transcription dispatch, OS-aware. |
| `src/lib/extraction/tesseract_ocr.py` | delete | Module retired. |

`pyproject.toml`:
- **add**: `openvino>=2026.0`, `openvino-genai>=2026.0`,
  `huggingface-hub>=0.36.0`.
- **remove**: `pytesseract`, `markitdown-ocr` extra. Keep `pymupdf` (PDF
  text + page rasterization). Keep `imageio-ffmpeg` (audio decoding).
  Drop `pdf2image` if no remaining caller; the LLM-OCR PDF path uses it
  today (`extractor.py:_pdf_page_images_for_llm`) so it stays for now.
- **exclude**: `transformers==4.52.*` and `optimum-intel` conversion
  tooling from the runtime extra. The active Windows ASR path uses the
  preconverted `OpenVINO/whisper-large-v3-int8-ov` model with
  `openvino-genai`; retaining the conversion stack reintroduces known
  `transformers` 4.x advisories.
- **scoped retain**: `faster-whisper` — used only on macOS via the
  `sys.platform == "darwin"` gate in `transcription.py`.

### Tiered ladder (after this change)

```
extract(path, max_tier, *, allow_cloud, language_hint=None)
            │
            ▼
  ┌──────────────────────────────────┐
  │ Tier 0: MarkItDown / PyMuPDF     │   text PDFs, Office docs
  └──────────────────────────────────┘
            │
            ▼   _is_low_signal_text() AND image/PDF AND max_tier >= 1
            ▼
  ┌──────────────────────────────────┐
  │ Hebrew gate                      │   if language_hint == "he":
  │                                  │     skip Tier 1a, go to Tier 1b/c
  └──────────────────────────────────┘
            │ not Hebrew
            ▼
  ┌──────────────────────────────────┐
  │ Tier 1a: Ollama GLM-OCR          │   model="glm-ocr"
  │ - localhost:11434/api/generate   │   (was "llava")
  │ - both OSes                      │
  └──────────────────────────────────┘
            │   if Ollama unavailable / produced no text
            ▼
  ┌──────────────────────────────────┐
  │ Tier 1b: AI-client hand-off      │   if allow_cloud and is_ai_client_context()
  │ - return needs_llm=True          │
  └──────────────────────────────────┘
            │   else
            ▼
  ┌──────────────────────────────────┐
  │ Tier 1c: passive CLI subprocess  │   run_cloud_vision_ocr()
  │ - claude/codex CLI handles       │
  │   the cloud vision call          │
  └──────────────────────────────────┘
```

The Tesseract tier (formerly between Tier 0 and Tier 1a) is gone. The
Hebrew gate is the only new branch.

### Transcription flow (after this change)

```
transcribe_audio(path)
            │
            ▼
  ┌──────────────────────────────────┐
  │ sys.platform check               │
  └──────────────────────────────────┘
        │ "darwin"            │ otherwise
        ▼                     ▼
  ┌─────────────────┐   ┌────────────────────────────────┐
  │ faster-whisper  │   │ OpenVINO Whisper-large-v3 INT8 │
  │ Metal/CoreML    │   │ device probe: NPU → GPU → CPU  │
  └─────────────────┘   └────────────────────────────────┘
        │                     │
        ▼                     ▼
   on success: TranscriptResult with backend = "metal" | "NPU" | "GPU" | "CPU"
   on all-fail: needs_review
```

No cloud audio escalation in this slice. If transcription fails offline,
the caller surfaces a needs_review file result.

### OpenVINO device probe

```python
# transcription.py — pseudocode
def _try_openvino_devices(model_dir, audio_path, devices=("NPU", "GPU", "CPU")):
    last_err = None
    for device in devices:
        try:
            pipeline = openvino_genai.WhisperPipeline(model_dir, device)
            return pipeline.generate(audio_path), device
        except RuntimeError as exc:
            last_err = exc
            continue
    raise RuntimeError(f"All OpenVINO devices failed; last={last_err}")
```

Replaces the silent `device="AUTO"` call. Result records the device that
actually ran.

### Hebrew detection / language hint

`extract()` already accepts a `max_tier` and `allow_cloud`. We add an
optional `language_hint: str | None = None` parameter, threaded through
from the inbox consume call. When the hint is `"he"` (or auto-detection
returns Hebrew via a fast pre-pass — file metadata or first 500 chars of
embedded text), the Tier 1 stage skips Tier 1a (Ollama GLM-OCR) and goes
directly to Tier 1b/1c.

If `allow_cloud` is False (airplane mode on) and Hebrew is detected, the
file gets `needs_review` with reason `hebrew_offline_unavailable`. We
do not fall back to GLM-OCR for Hebrew because GLM-OCR is not trained
on Hebrew and the result would be unreliable.

## Hardware & Dependency Requirements

### Windows AI PC (Intel Core Ultra, NPU 4 — Arrow Lake / Lunar Lake)

Hard requirements for the OpenVINO Whisper NPU path:

- NPU driver `>= 32.0.100.3104` (older drivers fail silently or with
  errors).
- `openvino >= 2026.0` and `openvino-genai >= 2026.0` for stateful
  Whisper, word timestamps across CPU/GPU/NPU, and AOT NPU compilation
  independent of OEM driver.
- No `transformers` 4.x runtime dependency. Model conversion tooling is
  not part of the shipped Windows ASR runtime; the runtime consumes the
  preconverted `OpenVINO/whisper-large-v3-int8-ov` model.

The capability layer checks these at startup and surfaces a single
`extraction_prereqs` block in `get-extraction-status` with concrete
remediation hints.

### macOS

- `faster-whisper` (Metal/CoreML inference) for transcription.
- Ollama with `glm-ocr` pulled.

### Both OSes

- Ollama installed and running with `glm-ocr` model pulled.
- For cloud: a passive-agent CLI configured at `document-ocr-cloud`
  (existing `agent_cli_config` mechanism — already supports `claude`,
  `codex`).

## Model Acquisition

| Model | Source | Cache key |
|---|---|---|
| GLM-OCR | `ollama pull glm-ocr` (user runs once; onboarding may prompt) | Ollama-managed |
| whisper-large-v3 INT8 OV | `OpenVINO/whisper-large-v3-int8-ov` HF, lazy on first use | `whisper-large-v3-int8-ov/` |
| whisper-large-v3 (faster-whisper) | HF transformers weights, lazy on first use | faster-whisper managed |

If airplane mode is on AND the cache is empty, the backend reports
`needs_review` with reason `model_missing`. Cached models run offline
indefinitely.

## Failure Modes

| Failure | Detection | Result |
|---|---|---|
| Ollama not running | tag-list query fails | OCR Tier 1a unavailable; `extract()` falls through to Tier 1b/c if `allow_cloud`, else returns Tier 0 result |
| GLM-OCR not pulled | tag list missing `glm-ocr` | same as above; setup hint `ollama pull glm-ocr` |
| OpenVINO not installed | package check | Whisper backend unavailable; setup hint surfaced |
| NPU driver below floor | driver query | NPU excluded from device probe; warning surfaced; GPU/CPU continue |
| `transformers` 4.x installed | version check | Status reports the optional package as unsafe and recommends removal or `transformers>=5.0.0`; the OpenVINO runtime does not require it |
| OV Whisper NPU compile failure | exception in NPU probe | Falls through to GPU/CPU automatically; result records fallback |
| Hebrew + airplane mode on | language hint + policy | `needs_review` with reason `hebrew_offline_unavailable` |
| Audio transcription fails on both Win OV and Mac faster-whisper | both branches fail | `needs_review`; no cloud audio path in this slice |
| Cloud passive agent unavailable | `agent_cli_config` resolution fails | Tier 1b/c returns the same error today does — caller sees `error` field |

A failed file does not fail the consume run; the file result records the
backend tried and the reason it failed.

## Preferences

`config/preferences.yaml` additions:

```yaml
local_backends:
  whisper:
    model: whisper-large-v3-int8-ov
    devices: ["NPU", "GPU", "CPU"]
  ollama_ocr:
    model_tag: "glm-ocr"   # override only if user pulled a different tag
```

All fields optional. `null`/missing means default. The migration writes
no values — existing prefs keep working.

## MCP Surface

Hardened:

- `get-extraction-status` adds:
  - `os_default_chain.{ocr,transcription}` — the resolved order
  - `ocr_engine: "glm-ocr"` (and Ollama availability)
  - `prereqs.{npu_driver, transformers_version, optimum_intel_version, openvino_version}`
  - `openvino.devices` list (which devices were probed and which is live)
  - `cloud.{passive_agent_cli, available}`
  Drops Tesseract / `markitdown-ocr` from the report.
- `get-local-backend-status` — unchanged shape; adds a small `extraction`
  block alongside the existing Ollama block.

No new MCP tools.

## Testing

### Unit

- `test_capabilities.py` — assert pruned inventory (no Tesseract, no
  `markitdown-ocr`); assert prereq checks populate the new fields; assert
  GLM-OCR detection through Ollama tag list.
- `test_extractor.py` — assert Tier 0.5 (Tesseract) is gone; assert Tier
  1a calls Ollama with `model="glm-ocr"`; assert Hebrew language hint
  short-circuits past Tier 1a; assert `is_ai_client_context()` and
  passive-agent paths still fire correctly.
- `test_transcription.py` — assert `["NPU", "GPU", "CPU"]` probe order;
  assert `device="AUTO"` is removed from the call path; assert macOS
  branch picks faster-whisper.
- `test_cloud_vision.py` — unchanged test surface; verify Hebrew docs
  reach this path.

### Manual verification on this Windows box

- `whisper-large-v3-int8-ov` runs end-to-end on NPU on a sample MP3 with
  airplane mode on; result reports `backend: "NPU"`.
- GLM-OCR runs on a scanned English receipt with airplane mode on;
  result reports backend `ollama-glm-ocr` and a confidence-equivalent
  signal.
- Hebrew document with airplane mode OFF reaches Tier 1b/c and returns
  cloud-OCR text.
- Hebrew document with airplane mode ON returns `needs_review` with
  reason `hebrew_offline_unavailable`.

### macOS verification (deferred)

- faster-whisper Metal path runs end-to-end on a sample MP3.
- Ollama GLM-OCR runs on the same English sample.
- Hebrew sample escalates to passive-agent cloud.

## Decision Notes

- **GLM-OCR everywhere over OpenVINO PaddleOCR-VL.** Both score similarly
  on OmniDocBench v1.5 (94.62 vs 94.50). GLM-OCR ships through Ollama
  which is already in the stack; PaddleOCR-VL would add a second runtime.
  Single-engine simplicity wins.
- **Whisper-large-v3 over Whisper-base.** Disk delta (~1.5 GB vs ~140 MB)
  is acceptable; quality difference is large (2.01% / 3.91% vs 5% / 11%
  WER on LibriSpeech), and large-v3 covers Hebrew where base does not.
- **No Parakeet split.** Parakeet-TDT-0.6B-v3 wins on English speed but
  drops Hebrew. One multilingual model > per-language split.
- **Hebrew → cloud directly.** No local Hebrew OCR engine in the active
  ladder. EasyOCR + OpenVINO INT8 is the only OV-ecosystem Hebrew option;
  it stays as a tracked alternative and lands later only if cloud-Hebrew
  is unsatisfactory in practice.
- **`device="AUTO"` excludes NPU.** OpenVINO docs make this explicit.
  Current `transcription.py` silently runs CPU/GPU on the AI PC's NPU 4.
- **No new cloud SDKs.** Mistral OCR 3, ElevenLabs Scribe v2, etc. are
  better than the passive-agent for cost and quality, but introducing
  them breaks the established escalation pattern (rule 19) and the
  user has explicitly chosen the simpler path.
- **No cloud audio path in this slice.** Audio is offline-only. The
  passive-agent shape would need to grow audio-handling support before
  cloud audio is worth adding; that's a separate decision.
- **Tesseract retirement.** Tesseract has been dominated for years; with
  GLM-OCR as Tier 1a there is no scenario where Tesseract is the right
  choice. Removing the tier removes a dep, a system binary requirement,
  and a code path.

## Out of Scope

- Chat LLM backend swap to OpenVINO GenAI (next sub-project).
- Brain Inbox dashboard wiring, source-card writing, RAG indexing
  (May-07 plan).
- EasyOCR + OpenVINO Hebrew rung. Tracked alternative.
- PaddleOCR-VL OpenVINO module. Tracked alternative.
- Parakeet-TDT-0.6B-v3 ASR. Tracked alternative for English-only
  workloads.
- Direct cloud OCR / ASR provider SDKs.
- Cloud audio escalation path.
- Background daemon watching of inbox folders.
- Migration of existing Tesseract / faster-whisper-on-Windows model
  caches.
- Linux as a primary platform.
- A `setup-extraction-models` MCP tool.

## Implementation Phases

1. **Capability inventory cleanup**
   - Drop Tesseract / `markitdown-ocr` / `pytesseract` from
     `capabilities.py`.
   - Add 2026 prereq checks (NPU driver, unsafe optional transformers 4.x,
     `openvino >= 2026.0`, GLM-OCR availability).
   - Tests.
2. **Extractor Tier swap**
   - Delete the Tier 0.5 Tesseract branch.
   - Change the hardcoded Ollama model from `"llava"` to `"glm-ocr"`.
   - Add the Hebrew language hint short-circuit.
   - Tests + manual scan verification.
3. **OpenVINO Whisper hardening**
   - Replace `device="AUTO"` with explicit `["NPU", "GPU", "CPU"]` probe.
   - Default model becomes `whisper-large-v3-int8-ov`.
   - Remove faster-whisper Windows branch; keep macOS-only branch.
   - Tests + manual NPU verification.
4. **`get-extraction-status` upgrade**
   - Surface OS default chains, current OCR/ASR engines, NPU device,
     prereq state.
   - Tests.
5. **Tesseract module deletion**
   - Delete `src/lib/extraction/tesseract_ocr.py` and remove imports.
   - Remove Tesseract install instructions from onboarding docs.

## References

### 2026 picks
- [GLM-OCR on Ollama](https://ollama.com/library/glm-ocr)
- [GLM-OCR HF model card](https://huggingface.co/zai-org/GLM-OCR)
- [OmniDocBench leaderboard (CodeSOTA)](https://www.codesota.com/browse/computer-vision/document-parsing/omnidocbench)
- [OpenVINO 2026.0 release blog](https://medium.com/openvino-toolkit/openvino-2026-0-new-models-enhanced-genai-and-smarter-compression-bf846a59cda8)
- [OpenVINO 2026 release notes](https://docs.openvino.ai/2026/about-openvino/release-notes-openvino.html)

### Hardware + ecosystem
- [OpenVINO Automatic Device Selection][auto-device] — NPU exclusion
- [Speech Recognition Using Whisper — OpenVINO GenAI](https://openvinotoolkit.github.io/openvino.genai/docs/use-cases/speech-recognition/)
- [openvino.genai #1965 — turbo INT8 NPU hang (legacy reference)](https://github.com/openvinotoolkit/openvino.genai/issues/1965)
- [Anandtech — Lunar Lake NPU 4 deep-dive](https://www.anandtech.com/show/21425/intel-lunar-lake-architecture-deep-dive-lion-cove-xe2-and-npu4/4)

### Internal
- [May-07 AI-PC Brain Inbox Design](2026-05-07-ai-pc-brain-inbox-design.md)
- `src/lib/extraction/extractor.py` — current escalation ladder
- `src/lib/extraction/cloud_vision.py` — passive-agent cloud OCR

[auto-device]: https://docs.openvino.ai/2025/openvino-workflow/running-inference/inference-devices-and-modes/auto-device-selection.html
