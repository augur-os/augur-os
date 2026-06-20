---
title: Offline-Mode Routing Simplification
date: 2026-05-22
status: design
supersedes_partial: ADR-640
topic: offline-mode
---

# Offline-Mode Routing Simplification — Design

## Problem

"Offline mode" today (ADR-640) is spread across several modules with overlapping
responsibilities: a 902-line `local_backends.py` doing Ollama detection plus
multi-step agent-launch smoke probing, a tiered OCR escalation ladder inside
`extractor.py` (Ollama → cloud-vision → in-session handoff) with Hebrew
special-casing, and per-OS branching scattered between extraction and
infrastructure code. The behavior is hard to reason about, fragile to set up,
and risky to demo.

The system actually has a simple conceptual model — **three activities, two
modes, two operating systems** — but that model is implicit and re-derived in
many places. This design makes the model explicit as a single declarative
routing table and deletes the scattered decision logic around it.

**Primary driver:** the Windows laptop offline path must be solid and
demonstrable for demo day.

## Goal

One module owns the decision "which engine runs this activity right now."
Everything else asks it and runs what it gets back. Proven engine internals
(OpenVINO Whisper, faster-whisper, GLM-OCR, cloud-vision) are preserved and
wrapped as thin adapters; the routing/escalation/probing tangle is removed.

## The routing matrix (single source of truth)

| Activity | Regular mode (Win + Mac) | Offline — Windows | Offline — Mac |
|---|---|---|---|
| **Chat / LLM** | Agent (active cloud AI client) | Agent launched on local **Ollama** LLM | Agent launched on local **Ollama** LLM |
| **OCR** (images, scanned PDF) | Agent vision (active client) | **Ollama GLM-OCR** | **Ollama GLM-OCR** |
| **Transcript** (audio ASR) | **Gemini** passive-agent (audio-native) | **OpenVINO Whisper** (NPU/GPU/CPU) | **faster-whisper** (CPU/Metal) |

Notes on the matrix:
- **OCR is symmetric across OSes** (GLM-OCR via Ollama on both Windows and Mac).
  Only the **transcript** row branches by OS, because OpenVINO on Mac arm64 is
  CPU-only.
- **Regular-mode transcript routes to Gemini specifically**, because Claude Code
  and Codex cannot ingest audio natively; only Gemini-family models accept audio.
  This is the one activity that is client-specific in regular mode.
- "Offline mode" is the existing `airplane_mode` toggle in `preferences.yaml`
  (forced toggle + `auto_detect` connectivity).

## Architecture

A new lean package `src/lib/routing/` is the only place that maps a cell of the
matrix to an engine.

```
src/lib/routing/
├── matrix.py     # the declarative ROUTES table + Activity/Mode/OS enums
├── resolver.py   # resolve_chat / resolve_ocr / resolve_transcript + detect_mode()
└── engines.py    # thin adapters over existing engine internals + engine registry
```

### The table as data

```python
# matrix.py
ROUTES = {
    # (activity,     mode)      : {os_key: engine_id}   ("*" = any OS)
    ("chat",       "regular")  : {"*": "agent-chat"},
    ("chat",       "offline")  : {"*": "ollama-llm"},
    ("ocr",        "regular")  : {"*": "agent-vision"},
    ("ocr",        "offline")  : {"*": "ollama-glm-ocr"},
    ("transcript", "regular")  : {"*": "gemini-transcribe"},
    ("transcript", "offline")  : {"win32": "openvino-whisper", "darwin": "faster-whisper"},
}
```

Changing a route = editing one entry. There is no second place where the
decision is made.

### Resolver

```python
# resolver.py
def detect_mode() -> Mode: ...        # reads airplane_mode pref + connectivity
def resolve_chat(*, mode=None, os=None) -> ChatLauncher: ...
def resolve_ocr(*, mode=None, os=None) -> OcrEngine: ...
def resolve_transcript(*, mode=None, os=None) -> TranscriptEngine: ...
```

- `mode` defaults to `detect_mode()`; `os` defaults to `sys.platform`.
- Each resolver looks up the cell, finds the `engine_id`, and returns the
  registered engine instance.
- A cell with no engine for the current OS raises a clear, actionable error
  naming the missing cell.

### Engine interface

Three small protocols, one per activity — not one forced universal signature,
because chat returns a *launch spec* while OCR/transcript return *extracted
text*:

- `ChatLauncher.launch_spec() -> LaunchSpec` (argv / model selection)
- `OcrEngine.run(images) -> OcrResult`
- `TranscriptEngine.run(audio_path) -> TranscriptResult`

Each engine also exposes `available() -> EngineAvailability` (installed +
ready + setup hint) so readiness can be reported without deep smoke probing.

## Components — wrap, don't rewrite

| engine_id | Wraps (existing code) | New? |
|---|---|---|
| `agent-chat` | active AI-client default dispatch | no |
| `ollama-llm` | trimmed `get_airplane_launch_overrides` launch spec | no |
| `agent-vision` | `cloud_vision.run_cloud_vision_ocr` + in-session `needs_llm` handoff | no |
| `ollama-glm-ocr` | `extractor._run_ollama_ocr` + `local_backend_config.get_local_ocr_settings` | no |
| `openvino-whisper` | `transcription._transcribe_openvino` (in `src/lib/extraction/transcription.py`) | no |
| `faster-whisper` | `transcription._transcribe_faster_whisper` (in `src/lib/extraction/transcription.py`) | no |
| `gemini-transcribe` | **new** Gemini-CLI passive-agent (subprocess, no SDK) | **yes** |

Only `gemini-transcribe` is net-new. It is a subprocess passive-agent (consistent
with the "passive-agent canonical, no new SDKs" rule), not a provider SDK.

## Mode detection

`detect_mode()` is the only logic that survives from `local_backends.py`'s
decision code. It reads the `airplane_mode` preference (forced toggle +
`auto_detect` connectivity check via the existing `check_connectivity`). The
~900 lines of agent-launch smoke probing and model-turn probes are deleted and
replaced by lightweight `engine.available()` checks.

## What gets deleted vs. kept

**Deleted:**
- The tiered OCR escalation ladder in `extractor._request_llm_ocr`
  (Ollama → cloud-vision → `needs_llm`).
- The deep agent-launch / model-turn probe ladders in `local_backends.py`.
- Per-OS / per-engine branching scattered across extraction and infrastructure.
- The Hebrew offline→cloud special-case (see Decision D2).

**Kept and re-pointed:**
- `get-local-backend-status` MCP tool — the dashboard depends on it. Reimplemented
  to iterate the `ROUTES` table and report per-cell `engine_id` + `available()`
  state. Output shape stays compatible with the consuming pages.
- The proven extraction internals (OpenVINO/faster-whisper, GLM-OCR call,
  cloud-vision), now reached only through their engine adapters.
- The `airplane_mode` preference and toggle.

## Confirmed decisions

### D1 — Gemini absent (regular-mode transcript): FALLBACK

If the Gemini CLI is not installed/configured when regular-mode transcript is
requested, fall back to the local offline transcript engine (OpenVINO on
Windows, faster-whisper on Mac) and surface a "used local fallback" notice in
the result. The activity still succeeds; the notice makes the degraded path
honest (rules 1, 34).

### D2 — Hebrew: DROP the special-case

Remove the offline Hebrew→cloud special-case entirely. Regular-mode OCR
(agent vision) handles Hebrew natively; offline OCR uses GLM-OCR (a multilingual
VLM) directly with no language-based diversion. If offline GLM-OCR produces weak
Hebrew output, that is reported honestly rather than silently rerouted.

## Verification (demo-day priority = Windows offline)

Real-data proof per rule 34, not just green tests:

- **Windows offline OCR**: run a real image through `ollama-glm-ocr` and show the
  extracted text.
- **Windows offline transcript**: run a real audio clip through
  `openvino-whisper` and show the transcript + the device actually used.
- **Windows offline chat**: run a real chat turn via the `ollama-llm` launch spec
  and show the response.
- **Regular-mode transcript**: run a real audio clip through `gemini-transcribe`;
  separately, with Gemini disabled, confirm the D1 fallback produces a transcript
  and emits the fallback notice.

Automated:
- Unit tests assert **every matrix cell resolves** for every (mode, OS)
  permutation, and that an unmapped OS raises the actionable error.
- The existing live-backend integration plan
  (`2026-05-12-offline-backends-integration-tests.md`) is re-pointed at the
  resolver and engine adapters.
- Dashboard pages `/settings/security` and `/brain/agents` verified to interactive
  state in a real browser (rules 28, 31), since `get-local-backend-status` changes.

## ADR

This partially supersedes **ADR-640 (OpenVINO and Ollama Offline Mode)**. A short
ADR will record the routing matrix as the canonical model and the deletion of the
escalation/probing layer (rule 12).

## File structure summary

```
src/lib/routing/                      # NEW — single decision point
├── __init__.py
├── matrix.py                         # ROUTES table + enums
├── resolver.py                       # resolve_* + detect_mode
└── engines.py                        # adapters + registry (incl. new gemini-transcribe)

src/lib/extraction/extractor.py       # OCR path calls resolve_ocr(); escalation ladder removed
src/lib/extraction/transcription.py   # _transcribe_openvino / _transcribe_faster_whisper wrapped by adapters
src/lib/extraction/cloud_vision.py    # run_cloud_vision_ocr wrapped by the agent-vision adapter
src/mcp/.../infrastructure/local_backends.py  # gutted to detect_mode reuse; status tool re-pointed
```

## Out of scope

- Re-benchmarking OCR/ASR engine quality (engine choices are settled: GLM-OCR for
  OCR, OpenVINO/faster-whisper for transcript).
- Adding any provider SDK.
- Changing the dashboard's MCP dispatch architecture (Critical Rule 11 unchanged).
