# ADR-752 Implementation Plan — audio-ingest skill (voice memos + meetings)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add audio as a first-class `/note` modality. Pipe `/note <audio-file>` through transcription (whisper.cpp by default, pluggable), agent-classify the transcript as `voice-memo` or `meeting`, and write a note in `<vault>/notes/` with type-correct frontmatter (duration, transcript status, attendee slugs for meetings).

**Architecture:** Transcription lives in `document-extractor` as a new "tier 0" capability — local whisper.cpp by default, pluggable adapters under `src/lib/extraction/transcription/`. A new `audio-ingest` skill owns the audio-specific routing on top: it consumes the transcript, dispatches the classifier through the **LLM-Assisted MCP Pattern** (`docs/references/llm-assisted-mcp-pattern.md`) so the active AI client decides memo vs meeting (no hardcoded provider per Rule 19), and writes the resulting note. Meeting transcripts additionally resolve attendees against the ADR-738 typed graph and surface a "Merge to timeline" action that targets the ADR-740 compiled-truth/timeline pattern. BrowseDetailPanel gets voice-memo and meeting sections.

**Tech Stack:** Python 3.11+, whisper.cpp (via `pywhispercpp` or direct binary call), pytest (skill tests use `importlib.util.spec_from_file_location` — see memory `feedback-skill-test-convention`), Next.js + TypeScript dashboard, vitest. AI-client dispatch follows `docs/references/llm-assisted-mcp-pattern.md` (no direct provider API calls per Rule 19 + memory `feedback-vendor-neutral-design`).

**Spec:** `docs/superpowers/specs/2026-05-15-gbrain-ingest-port-design.md` §"audio-ingest". **Depends on:** ADR-751 plan complete and merged (atomic ops write to `<vault>/notes/`, `/note` router exists, BrowseCard handles `voice-memo`/`meeting` badges). **Related ADRs:** ADR-738 (typed graph for attendee resolution), ADR-740 (compiled-truth/timeline merge target), ADR-742 (eval harness — used for classifier accuracy testing), ADR-748 (existing prompt-card pattern parallels note-writing here).

---

## File Structure

### Create

| Path | Responsibility |
|------|----------------|
| `docs/adrs/ADR-752-audio-ingest-skill.md` | Architecture decision record |
| `shared-vault/skills/audio-ingest/SKILL.md` | New skill manifest (hub: brain, type: domain, MCP tools, dashboard pages) |
| `shared-vault/skills/audio-ingest/config.yaml` | Skill-local config (default transcription provider, classifier prompt, attendee resolution toggles) |
| `shared-vault/skills/audio-ingest/scripts/__init__.py` | Empty marker |
| `shared-vault/skills/audio-ingest/scripts/classifier.py` | Pure-logic helpers for transcript → memo/meeting decision (heuristic features + LLM-assisted dispatch payload) |
| `shared-vault/skills/audio-ingest/scripts/note_writer.py` | Pure-logic helpers: build the markdown body + frontmatter for a voice-memo or meeting note |
| `shared-vault/skills/audio-ingest/scripts/attendee_resolver.py` | Pure-logic: given a transcript's speaker chunks, attempt to resolve speaker labels to known person-entity slugs via the ADR-738 graph |
| `shared-vault/skills/audio-ingest/scripts/mcp/__init__.py` | Empty marker |
| `shared-vault/skills/audio-ingest/scripts/mcp/tools_audio.py` | MCP tools: `audio-classify`, `submit-audio-classify-result`, `audio-ingest-write` |
| `shared-vault/skills/audio-ingest/augur/scripts/` | Skill-internal scripts dir (per Augur convention) |
| `shared-vault/skills/audio-ingest/augur/tests/test_classifier.py` | Unit tests for the classifier (heuristic baseline + dispatch payload shape) |
| `shared-vault/skills/audio-ingest/augur/tests/test_note_writer.py` | Unit tests for note frontmatter and slug generation |
| `shared-vault/skills/audio-ingest/augur/tests/test_attendee_resolver.py` | Unit tests for attendee resolution |
| `shared-vault/skills/audio-ingest/augur/tests/test_audio_mcp.py` | Integration tests for the MCP tools (mocked transcription) |
| `shared-vault/skills/audio-ingest/augur/tests/fixtures/voice_memo_sample.txt` | Canned transcript: single-speaker, first-person, short |
| `shared-vault/skills/audio-ingest/augur/tests/fixtures/meeting_sample.txt` | Canned transcript: multi-speaker, time-stamps, decisions |
| `src/lib/extraction/transcription/__init__.py` | Provider registry + `transcribe(audio_path, options) -> Transcript` facade |
| `src/lib/extraction/transcription/whisper_cpp.py` | Default whisper.cpp adapter |
| `src/lib/extraction/transcription/types.py` | `Transcript` dataclass — text, segments, speaker hints, duration_seconds, language, provider |
| `tests/lib/extraction/transcription/test_whisper_cpp.py` | Tests for the whisper.cpp adapter (mocked binary call + real-call smoke marked `@pytest.mark.slow`) |

### Modify

| Path | Change |
|------|--------|
| `src/mcp/augur_framework/.../document_extractor_tools.py` (or wherever MCP tools register) | Register the new `extract-audio` MCP tool that calls the transcription facade |
| `shared-vault/skills/document-extractor/SKILL.md` | Add `extract-audio` to `x-augur-mcp-tools` |
| `shared-vault/skills/document-extractor/config.yaml` | Add a `transcription:` section with provider/model/language defaults |
| `shared-vault/skills/document-extractor/scripts/mcp/tools_extract.py` | Wire the `extract-audio` MCP tool into the existing tool registration |
| `shared-vault/skills/ingest/commands/note.md` | Replace the "Audio (not yet implemented)" stub section with the live dispatch into `extract-audio` → `audio-classify` → `audio-ingest-write` |
| `apps/dashboard/components/shared/BrowseDetailPanel.tsx` | Add `voice-memo` and `meeting` sections (audio player, transcript pane, attendee chips for meetings, "Merge to timeline" action) |
| `tests/dashboard/browse/BrowseDetailPanel.test.tsx` | Tests for voice-memo and meeting sections |
| `config/system/capability_exposure.yaml` | Add `mcp-tool:audio-classify`, `mcp-tool:submit-audio-classify-result`, `mcp-tool:audio-ingest-write`, `mcp-tool:extract-audio` |
| `shared-vault/skills/ingest/scripts/note_type.py` | The "audio" routing label is already present (Plan 1 Task 2); no change needed |

---

## Task 1: Write ADR-752

**Files:**
- Create: `docs/adrs/ADR-752-audio-ingest-skill.md`

- [ ] **Step 1: Write the ADR using ADR-751's frontmatter shape**

Status: `Proposed`. Date: 2026-05-16. `plan_file: docs/superpowers/plans/2026-05-16-adr-752-audio-ingest-skill.md`. Sections:

- **Context:** Augur has no audio modality today; voice memos + meeting recordings are two distinct knowledge shapes blocked behind the same missing capability; gbrain ports inform the design.
- **Decision:** New `audio-ingest` skill owns voice/meeting routing; transcription lives in `document-extractor` as a tier-0 capability with a pluggable provider abstraction; classifier and speaker labeling use the LLM-Assisted MCP Pattern so the active AI client (not a hardcoded vendor) does the LLM reasoning.
- **Alternatives:** Put transcription in `audio-ingest` skill directly (rejected — duplicates `document-extractor`'s "binary in, clean text out" pattern); hardcode whisper-API cloud calls (rejected — violates Rule 19 + vendor-neutrality); always-LLM classifier (rejected at design time — heuristic preferred if it hits ≥90% accuracy).
- **Consequences:** Three new MCP tools, one new skill, one new provider abstraction module. Requires whisper.cpp model download on first use (~1.5 GB). Pluggable provider lets users swap to OpenAI Whisper API / AssemblyAI / Apple Speech later without skill changes.
- **Non-goals:** Real-time transcription (streaming); diarization of poorly-separated speakers; PII redaction (separate concern).
- **Open question (to be settled by this implementation):** Local heuristic classifier vs LLM-assisted classifier; benchmark both during implementation and pick whichever hits ≥90% accuracy on the held-out fixtures.

- [ ] **Step 2: Regenerate the ADR index**

```bash
python scripts/regenerate_adr_index.py
```
Expected: `docs/generated/adr-index.md` lists ADR-752 with status `Proposed`.

- [ ] **Step 3: Commit**

```bash
git add docs/adrs/ADR-752-audio-ingest-skill.md docs/generated/adr-index.md docs/adrs/adrs-index.json
git commit -m "$(cat <<'EOF'
docs(adr): ADR-752 audio-ingest skill for voice memos and meetings

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Transcription `Transcript` types

**Files:**
- Create: `src/lib/extraction/transcription/__init__.py`
- Create: `src/lib/extraction/transcription/types.py`
- Create: `tests/lib/extraction/transcription/test_types.py`

- [ ] **Step 1: Write the failing test for `Transcript`**

```python
# tests/lib/extraction/transcription/test_types.py
from __future__ import annotations
from src.lib.extraction.transcription.types import Transcript, Segment


def test_transcript_has_required_fields():
    t = Transcript(
        text="Hello world.",
        segments=[Segment(start=0.0, end=1.2, text="Hello world.", speaker="S1")],
        duration_seconds=1.2,
        language="en",
        provider="whisper-cpp",
        provider_version="1.5.4",
    )
    assert t.text == "Hello world."
    assert len(t.segments) == 1
    assert t.duration_seconds == 1.2
    assert t.speaker_count() == 1


def test_segment_with_no_speaker():
    s = Segment(start=0.0, end=1.0, text="hi", speaker=None)
    assert s.speaker is None


def test_speaker_count_zero_when_all_unlabeled():
    t = Transcript(
        text="x",
        segments=[Segment(start=0, end=1, text="x", speaker=None)],
        duration_seconds=1.0,
        language="en",
        provider="whisper-cpp",
        provider_version="x",
    )
    assert t.speaker_count() == 0


def test_speaker_count_unique():
    t = Transcript(
        text="x",
        segments=[
            Segment(start=0, end=1, text="a", speaker="S1"),
            Segment(start=1, end=2, text="b", speaker="S2"),
            Segment(start=2, end=3, text="c", speaker="S1"),
        ],
        duration_seconds=3.0,
        language="en",
        provider="whisper-cpp",
        provider_version="x",
    )
    assert t.speaker_count() == 2
```

- [ ] **Step 2: Run the test**

```bash
uv run pytest tests/lib/extraction/transcription/test_types.py -v
```
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `types.py`**

```python
# src/lib/extraction/transcription/types.py
"""Transcription data types — provider-neutral.

Adapters under this package return Transcript instances; everything
downstream (audio-ingest classifier, attendee resolver, note writer)
operates on Transcript.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Segment:
    """One contiguous speech segment within a transcript."""
    start: float            # seconds from audio start
    end: float              # seconds from audio start
    text: str               # spoken text in this segment
    speaker: Optional[str]  # provider-supplied speaker label, e.g. "S1"; None when diarization unavailable


@dataclass(frozen=True)
class Transcript:
    """Full transcript returned by a transcription provider."""
    text: str                       # concatenated full text
    segments: list[Segment]         # ordered by start time
    duration_seconds: float
    language: str                   # ISO 639-1, e.g. "en"
    provider: str                   # e.g. "whisper-cpp"
    provider_version: str           # provider-reported version string
    extra: dict = field(default_factory=dict)  # provider-specific extras (logprobs, model, etc.)

    def speaker_count(self) -> int:
        """Number of distinct labelled speakers in this transcript.

        Returns 0 when no segments carry a speaker label.
        """
        labels = {s.speaker for s in self.segments if s.speaker is not None}
        return len(labels)
```

- [ ] **Step 4: Implement `__init__.py` re-exporting public API**

```python
# src/lib/extraction/transcription/__init__.py
"""Transcription facade. Default provider: whisper-cpp.

Adapters implement transcribe(audio_path: Path, options: dict) -> Transcript.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from .types import Segment, Transcript

# Provider registry. Adapters call register_provider at import time.
_PROVIDERS: dict[str, Callable[[Path, dict], Transcript]] = {}


def register_provider(name: str, fn: Callable[[Path, dict], Transcript]) -> None:
    _PROVIDERS[name] = fn


def transcribe(
    audio_path: Path,
    *,
    provider: str = "whisper-cpp",
    options: Optional[dict] = None,
) -> Transcript:
    """Dispatch to the named provider. Raises if provider not registered."""
    if provider not in _PROVIDERS:
        # Lazy-import the default provider so the package imports cheaply.
        if provider == "whisper-cpp":
            from . import whisper_cpp  # noqa: F401  (registers itself)
        else:
            raise ValueError(f"Unknown transcription provider: {provider}")
    return _PROVIDERS[provider](audio_path, options or {})


__all__ = ["Transcript", "Segment", "transcribe", "register_provider"]
```

- [ ] **Step 5: Run the tests**

```bash
uv run pytest tests/lib/extraction/transcription/test_types.py -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/lib/extraction/transcription/__init__.py src/lib/extraction/transcription/types.py tests/lib/extraction/transcription/test_types.py
git commit -m "$(cat <<'EOF'
feat(extraction): transcription facade + Transcript types (ADR-752)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: whisper.cpp transcription adapter

**Files:**
- Create: `src/lib/extraction/transcription/whisper_cpp.py`
- Create: `tests/lib/extraction/transcription/test_whisper_cpp.py`

- [ ] **Step 1: Add `pywhispercpp` to the project's Python deps**

Modify the relevant `pyproject.toml` (or the equivalent dependency list). The Augur project uses `uv`; add `pywhispercpp` as an optional dep under an `audio` extra so users who don't want audio don't pull the model bindings:

```toml
[project.optional-dependencies]
audio = ["pywhispercpp>=1.2.0"]
```

```bash
uv sync --extra audio
```
Expected: `pywhispercpp` installed in the project venv.

- [ ] **Step 2: Write the failing adapter test**

```python
# tests/lib/extraction/transcription/test_whisper_cpp.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from src.lib.extraction.transcription import transcribe
from src.lib.extraction.transcription.types import Transcript


@pytest.fixture
def fake_audio(tmp_path):
    p = tmp_path / "voice.m4a"
    p.write_bytes(b"\x00\x00\x00\x00fake audio")
    return p


def test_whisper_cpp_returns_transcript(fake_audio):
    fake_segments = [
        MagicMock(start=0.0, end=2.0, text="Hello,"),
        MagicMock(start=2.0, end=4.0, text="world."),
    ]
    fake_model = MagicMock()
    fake_model.transcribe = MagicMock(return_value=fake_segments)
    fake_model.model_path = "medium.en"

    with patch("src.lib.extraction.transcription.whisper_cpp._get_model", return_value=fake_model):
        result = transcribe(fake_audio, provider="whisper-cpp", options={"model": "medium.en", "language": "en"})

    assert isinstance(result, Transcript)
    assert "Hello" in result.text
    assert "world" in result.text
    assert result.language == "en"
    assert result.provider == "whisper-cpp"
    assert result.duration_seconds == pytest.approx(4.0)
    assert len(result.segments) == 2


def test_whisper_cpp_handles_empty_audio(fake_audio):
    fake_model = MagicMock()
    fake_model.transcribe = MagicMock(return_value=[])
    fake_model.model_path = "medium.en"
    with patch("src.lib.extraction.transcription.whisper_cpp._get_model", return_value=fake_model):
        result = transcribe(fake_audio, provider="whisper-cpp", options={"model": "medium.en", "language": "en"})
    assert result.text == ""
    assert result.duration_seconds == 0.0
    assert len(result.segments) == 0


@pytest.mark.slow
def test_whisper_cpp_against_real_short_clip(tmp_path):
    """Smoke test against a real bundled short clip. Marked slow; opt-in only.

    Bundle a tiny 1-2 second 16kHz mono WAV at
    tests/lib/extraction/transcription/fixtures/hello.wav before enabling.
    """
    fixture = Path(__file__).parent / "fixtures" / "hello.wav"
    if not fixture.exists():
        pytest.skip("hello.wav fixture not bundled; opt-in for real-call validation")
    result = transcribe(fixture, provider="whisper-cpp", options={"model": "tiny.en", "language": "en"})
    assert isinstance(result, Transcript)
    assert len(result.text.strip()) > 0
```

- [ ] **Step 3: Run the failing test**

```bash
uv run pytest tests/lib/extraction/transcription/test_whisper_cpp.py::test_whisper_cpp_returns_transcript -v
```
Expected: FAIL — `whisper_cpp.py` module not yet present.

- [ ] **Step 4: Implement the adapter**

```python
# src/lib/extraction/transcription/whisper_cpp.py
"""whisper.cpp adapter via pywhispercpp.

Reads model name from options['model'] (default "medium.en"). The model
file lives under <cache>/whisper-cpp/<model>.bin and is auto-downloaded
by pywhispercpp on first use.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .types import Segment, Transcript
from . import register_provider

_MODEL_CACHE: dict[str, object] = {}


def _get_model(name: str):
    if name in _MODEL_CACHE:
        return _MODEL_CACHE[name]
    try:
        from pywhispercpp.model import Model  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "pywhispercpp is required for whisper-cpp transcription. "
            "Install with: uv sync --extra audio"
        ) from exc
    model = Model(name)
    _MODEL_CACHE[name] = model
    return model


def _provider_version() -> str:
    try:
        from importlib.metadata import version
        return version("pywhispercpp")
    except Exception:
        return "unknown"


def transcribe_whisper_cpp(audio_path: Path, options: dict) -> Transcript:
    model_name = str(options.get("model", "medium.en"))
    language = str(options.get("language", "en"))
    speaker_labels = bool(options.get("speaker_labels", False))

    model = _get_model(model_name)
    raw_segments = model.transcribe(str(audio_path), language=language)

    segments: list[Segment] = []
    for s in raw_segments:
        segments.append(Segment(
            start=float(getattr(s, "start", 0.0) or 0.0),
            end=float(getattr(s, "end", 0.0) or 0.0),
            text=str(getattr(s, "text", "")).strip(),
            speaker=str(getattr(s, "speaker", "")) if speaker_labels and getattr(s, "speaker", None) else None,
        ))

    text = " ".join(s.text for s in segments if s.text).strip()
    duration = max((s.end for s in segments), default=0.0)

    return Transcript(
        text=text,
        segments=segments,
        duration_seconds=duration,
        language=language,
        provider="whisper-cpp",
        provider_version=_provider_version(),
        extra={"model": model_name},
    )


register_provider("whisper-cpp", transcribe_whisper_cpp)
```

- [ ] **Step 5: Run the tests**

```bash
uv run pytest tests/lib/extraction/transcription/test_whisper_cpp.py -v -m "not slow"
```
Expected: both non-slow tests pass. The `slow` test is skipped (no fixture bundled).

- [ ] **Step 6: Commit**

```bash
git add src/lib/extraction/transcription/whisper_cpp.py tests/lib/extraction/transcription/test_whisper_cpp.py pyproject.toml uv.lock
git commit -m "$(cat <<'EOF'
feat(extraction): whisper.cpp transcription adapter (ADR-752)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `extract-audio` MCP tool

**Files:**
- Modify: `shared-vault/skills/document-extractor/scripts/mcp/tools_extract.py`
- Modify: `shared-vault/skills/document-extractor/SKILL.md` (add `extract-audio` to `x-augur-mcp-tools`)
- Modify: `shared-vault/skills/document-extractor/config.yaml` (add `transcription:` defaults)
- Modify: `config/system/capability_exposure.yaml` (add `mcp-tool:extract-audio`)
- Create: `shared-vault/skills/document-extractor/augur/tests/test_extract_audio_mcp.py`

- [ ] **Step 1: Add the transcription defaults to `document-extractor/config.yaml`**

```yaml
# shared-vault/skills/document-extractor/config.yaml
transcription:
  provider: whisper-cpp
  model: medium.en
  language: en
  speaker_labels: false
```

- [ ] **Step 2: Register the `extract-audio` tool in `tools_extract.py`**

At the bottom of the existing tool-registration block, add:

```python
def _register_extract_audio(mcp: "FastMCP") -> None:
    from src.lib.extraction.transcription import transcribe

    @mcp.tool(
        name="extract-audio",
        description="Transcribe an audio file to text. Default provider: whisper-cpp (local).",
        **tool_annotations({"side_effects": "read", "destructive": False}),
    )
    def extract_audio(
        audio_path: str,
        provider: str | None = None,
        model: str | None = None,
        language: str | None = None,
        speaker_labels: bool = False,
    ) -> dict[str, Any]:
        from pathlib import Path
        from shared_vault.skills.document_extractor.scripts.mcp._shared import load_skill_config
        cfg = load_skill_config()
        prov = provider or cfg["transcription"]["provider"]
        opts = {
            "model": model or cfg["transcription"]["model"],
            "language": language or cfg["transcription"]["language"],
            "speaker_labels": speaker_labels or cfg["transcription"]["speaker_labels"],
        }
        t = transcribe(Path(audio_path), provider=prov, options=opts)
        return {
            "success": True,
            "text": t.text,
            "segments": [
                {"start": s.start, "end": s.end, "text": s.text, "speaker": s.speaker}
                for s in t.segments
            ],
            "duration_seconds": t.duration_seconds,
            "language": t.language,
            "provider": t.provider,
            "provider_version": t.provider_version,
            "speaker_count": t.speaker_count(),
        }
```

Helper `load_skill_config()` should be added to `_shared.py` if it isn't there yet — it reads the skill's `config.yaml` next to the SKILL.md.

- [ ] **Step 3: Add `load_skill_config()` to `_shared.py`**

```python
# shared-vault/skills/document-extractor/scripts/mcp/_shared.py
from pathlib import Path
import yaml

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


def load_skill_config() -> dict:
    if not _CONFIG_PATH.exists():
        return {}
    with _CONFIG_PATH.open() as fh:
        return yaml.safe_load(fh) or {}
```

- [ ] **Step 4: Write the integration test**

```python
# shared-vault/skills/document-extractor/augur/tests/test_extract_audio_mcp.py
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[5]


def _load_tools_extract():
    spec = importlib.util.spec_from_file_location(
        "doc_extractor_tools_extract",
        PROJECT_ROOT / "shared-vault" / "skills" / "document-extractor" / "scripts" / "mcp" / "tools_extract.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["doc_extractor_tools_extract"] = module
    spec.loader.exec_module(module)
    return module


def test_extract_audio_returns_transcript_payload(tmp_path):
    """Calling the registered extract-audio function returns the documented shape."""
    from src.lib.extraction.transcription.types import Segment, Transcript

    fake_path = tmp_path / "x.m4a"
    fake_path.write_bytes(b"\x00\x00")
    fake_transcript = Transcript(
        text="Hello world.",
        segments=[Segment(start=0.0, end=2.0, text="Hello world.", speaker=None)],
        duration_seconds=2.0,
        language="en",
        provider="whisper-cpp",
        provider_version="1.x",
    )

    mod = _load_tools_extract()
    captured = {}
    def fake_tool(*a, **kw):
        def inner(fn):
            captured["fn"] = fn
            return fn
        return inner
    fake_mcp = MagicMock()
    fake_mcp.tool = fake_tool

    with patch("src.lib.extraction.transcription.transcribe", return_value=fake_transcript):
        mod._register_extract_audio(fake_mcp)
        result = captured["fn"](str(fake_path))

    assert result["success"] is True
    assert result["text"] == "Hello world."
    assert result["duration_seconds"] == 2.0
    assert result["provider"] == "whisper-cpp"
    assert result["speaker_count"] == 0
```

- [ ] **Step 5: Run the tests**

```bash
uv run pytest shared-vault/skills/document-extractor/augur/tests/test_extract_audio_mcp.py -v
```
Expected: PASS.

- [ ] **Step 6: Update SKILL.md and capability_exposure.yaml**

In `shared-vault/skills/document-extractor/SKILL.md`, replace `x-augur-mcp-tools: []` with:

```yaml
x-augur-mcp-tools:
  - extract-audio
```

In `config/system/capability_exposure.yaml`, add:

```yaml
  mcp-tool:extract-audio:
    classification_status: approved
    export_to:
    - shell
    management: generated
    owner_kind: augur
    preferred_client: shell
    primary_surface: mcp-tool
    scope: project
```

- [ ] **Step 7: Commit**

```bash
git add shared-vault/skills/document-extractor/ config/system/capability_exposure.yaml
git commit -m "$(cat <<'EOF'
feat(document-extractor): extract-audio MCP tool with pluggable provider (ADR-752)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `audio-ingest` skill scaffold

**Files:**
- Create: `shared-vault/skills/audio-ingest/SKILL.md`
- Create: `shared-vault/skills/audio-ingest/config.yaml`
- Create: empty marker dirs and `__init__.py` files

- [ ] **Step 1: Write `SKILL.md`**

```markdown
---
name: audio-ingest
x-augur-type: domain
x-augur-group: brain
x-augur-release: mvp
description: Audio modality for /note. Routes voice memos and meeting recordings into the brain via transcription + agent classification. Voice memos preserve first-person phrasing; meetings resolve attendees and surface a timeline-merge action.
x-augur-hub: brain
x-augur-tab: notes
x-augur-requires-platform: true
x-augur-mcp-tools:
  - audio-classify
  - submit-audio-classify-result
  - audio-ingest-write
x-augur-dashboard-pages: []
x-augur-config-file: config.yaml
x-augur-dependencies:
  python:
    - pywhispercpp
---

# audio-ingest

Owns the audio path of `/note`. The flow:

1. `/note <audio>` (in `shared-vault/skills/ingest/commands/note.md`) detects the audio extension via `note_type.py` and calls `extract-audio` (document-extractor).
2. `extract-audio` returns a transcript + duration + speaker_count.
3. `/note` calls `audio-classify` with the transcript. The classifier returns `{type: "voice-memo" | "meeting", confidence, reasoning}` either directly (heuristic short-circuit hit ≥ 0.9) or via the LLM-Assisted MCP Pattern (returns `{needs_llm: true, ...}` to the AI client, which calls back with `submit-audio-classify-result`).
4. `/note` calls `audio-ingest-write` with the transcript + classification + audio metadata. The atomic op writes a note under `<vault>/notes/` with the correct `x-augur-note-type` (`voice-memo` or `meeting`).
5. For meetings only, the writer additionally calls the ADR-738 graph entity-extraction to populate `attendee_slugs` in frontmatter and surface a "Merge to timeline" action (ADR-740).

## Layering

- **L2 policy**: `/note` command file in `ingest` skill — agent sees a single `/note` verb.
- **L3 agent**: dispatches the three calls in sequence (`extract-audio` → `audio-classify` → `audio-ingest-write`).
- **L4 atomic ops**: the three MCP tools above. Each does one thing, persists no state of its own.

## Configuration

See `config.yaml` for: classifier heuristic thresholds, fallback-to-LLM threshold, attendee-resolution toggle, default frontmatter fields.
```

- [ ] **Step 2: Write `config.yaml`**

```yaml
# shared-vault/skills/audio-ingest/config.yaml
classifier:
  heuristic_threshold: 0.9        # short-circuit to result if heuristic confidence >= this
  llm_assisted: true              # if heuristic is below threshold, escalate via LLM-Assisted MCP Pattern
  voice_memo_max_seconds: 360     # default upper bound for "memo" by duration alone
attendee_resolution:
  enabled: true                   # only meetings; uses ADR-738 graph
  min_speaker_count: 2            # below this, do not attempt attendee resolution
```

- [ ] **Step 3: Create marker `__init__.py` files and empty dirs**

```bash
mkdir -p shared-vault/skills/audio-ingest/scripts/mcp
mkdir -p shared-vault/skills/audio-ingest/augur/scripts
mkdir -p shared-vault/skills/audio-ingest/augur/tests/fixtures
touch shared-vault/skills/audio-ingest/scripts/__init__.py
touch shared-vault/skills/audio-ingest/scripts/mcp/__init__.py
touch shared-vault/skills/audio-ingest/augur/scripts/__init__.py
```

- [ ] **Step 4: Bundle the canned test transcripts**

```bash
cat > shared-vault/skills/audio-ingest/augur/tests/fixtures/voice_memo_sample.txt <<'EOF'
I keep coming back to this idea that RRF works because retrieval failure modes are roughly orthogonal across rankers. If BM25 misses something semantically, the dense ranker often catches it, and vice versa. So a sum-of-reciprocal-ranks ends up trusting whichever ranker had information for this query. I should write this up properly tomorrow.
EOF

cat > shared-vault/skills/audio-ingest/augur/tests/fixtures/meeting_sample.txt <<'EOF'
[Sasha] Let's start. The Q2 numbers are in.
[Priya] Revenue's up 23% quarter over quarter. We're tracking ahead of plan.
[Jay] What's the breakdown by segment?
[Priya] Enterprise is the driver. SMB is flat.
[Sasha] So action items: Jay, you'll lead the SMB strategy review. Priya, refresh the forecast by next Tuesday.
[Jay] Got it.
[Priya] On it.
EOF
```

- [ ] **Step 5: Commit the scaffold**

```bash
git add shared-vault/skills/audio-ingest/
git commit -m "$(cat <<'EOF'
feat(audio-ingest): skill scaffold + canned transcripts (ADR-752)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Classifier (heuristic + LLM-assisted dispatch payload)

**Files:**
- Create: `shared-vault/skills/audio-ingest/scripts/classifier.py`
- Create: `shared-vault/skills/audio-ingest/augur/tests/test_classifier.py`

- [ ] **Step 1: Write the failing test**

```python
# shared-vault/skills/audio-ingest/augur/tests/test_classifier.py
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
CLASSIFIER_PATH = PROJECT_ROOT / "shared-vault" / "skills" / "audio-ingest" / "scripts" / "classifier.py"
FIXTURES = PROJECT_ROOT / "shared-vault" / "skills" / "audio-ingest" / "augur" / "tests" / "fixtures"


def _load_classifier():
    spec = importlib.util.spec_from_file_location("audio_ingest_classifier", CLASSIFIER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["audio_ingest_classifier"] = module
    spec.loader.exec_module(module)
    return module


def _voice_transcript():
    text = (FIXTURES / "voice_memo_sample.txt").read_text()
    return {"text": text, "segments": [], "duration_seconds": 30.0, "speaker_count": 0}


def _meeting_transcript():
    text = (FIXTURES / "meeting_sample.txt").read_text()
    return {
        "text": text,
        "segments": [],
        "duration_seconds": 1800.0,
        "speaker_count": 3,
    }


def test_classify_voice_memo_heuristic():
    c = _load_classifier()
    result = c.classify_heuristic(**_voice_transcript())
    assert result["type"] == "voice-memo"
    assert result["confidence"] >= 0.9
    assert "reasoning" in result


def test_classify_meeting_heuristic():
    c = _load_classifier()
    result = c.classify_heuristic(**_meeting_transcript())
    assert result["type"] == "meeting"
    assert result["confidence"] >= 0.9


def test_low_confidence_short_circuits_to_llm_dispatch():
    """A transcript that fits neither shape returns low confidence — caller escalates to LLM."""
    c = _load_classifier()
    result = c.classify_heuristic(
        text="ok yes maybe sure ok ok",
        segments=[],
        duration_seconds=12.0,
        speaker_count=1,
    )
    assert result["confidence"] < 0.9


def test_build_llm_dispatch_payload_shape():
    c = _load_classifier()
    payload = c.build_llm_dispatch_payload(
        text="ambiguous content",
        duration_seconds=12.0,
        speaker_count=1,
    )
    assert payload["needs_llm"] is True
    assert payload["task"] == "audio-classify"
    assert "transcript_preview" in payload
    assert "instructions" in payload
    assert payload["expected_result_schema"] == {
        "type": "string (voice-memo | meeting)",
        "confidence": "number 0..1",
        "reasoning": "string",
    }
```

- [ ] **Step 2: Run the failing test**

```bash
uv run pytest shared-vault/skills/audio-ingest/augur/tests/test_classifier.py -v
```
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `classifier.py`**

```python
# shared-vault/skills/audio-ingest/scripts/classifier.py
"""Audio transcript classifier — heuristic first, LLM-assisted fallback.

Heuristic features:
  - speaker_count: >=2 strongly favors "meeting"
  - explicit speaker tags like "[Name]" in the text favor "meeting"
  - first-person markers ("I ", "my ", "I think") favor "voice-memo"
  - duration: very long (>20min) favors "meeting", very short (<2min) favors "voice-memo"

Returns confidence in [0, 1]. When confidence < heuristic_threshold (default 0.9),
the caller should escalate via the LLM-Assisted MCP Pattern using
build_llm_dispatch_payload(...).
"""
from __future__ import annotations

import re
from typing import Any

_SPEAKER_TAG_RE = re.compile(r"^\s*\[[A-Za-z][A-Za-z0-9 _\-]*\]", re.MULTILINE)
_FIRST_PERSON_RE = re.compile(r"\b(I|I'm|I'll|my|me|myself)\b")


def _first_person_density(text: str) -> float:
    if not text:
        return 0.0
    tokens = text.split()
    if not tokens:
        return 0.0
    hits = len(_FIRST_PERSON_RE.findall(text))
    return hits / len(tokens)


def classify_heuristic(
    text: str,
    segments: list[dict],  # not used by heuristic yet, accepted for forward compatibility
    duration_seconds: float,
    speaker_count: int,
) -> dict[str, Any]:
    """Score memo vs meeting purely from features available without LLM."""
    score_meeting = 0.0
    score_voice = 0.0
    reasons: list[str] = []

    if speaker_count >= 2:
        score_meeting += 0.6
        reasons.append(f"speaker_count={speaker_count} >= 2")
    elif speaker_count == 1:
        score_voice += 0.3
        reasons.append("single speaker labeled")

    speaker_tag_hits = len(_SPEAKER_TAG_RE.findall(text))
    if speaker_tag_hits >= 2:
        score_meeting += 0.4
        reasons.append(f"speaker_tags={speaker_tag_hits}")

    fp_density = _first_person_density(text)
    if fp_density > 0.04:
        score_voice += 0.4
        reasons.append(f"first_person_density={fp_density:.3f}")

    if duration_seconds <= 360:
        score_voice += 0.2
        reasons.append("duration <= 6min")
    elif duration_seconds >= 1200:
        score_meeting += 0.3
        reasons.append("duration >= 20min")

    if score_meeting > score_voice:
        decision = "meeting"
        confidence = min(1.0, score_meeting / max(0.01, score_meeting + score_voice))
    else:
        decision = "voice-memo"
        confidence = min(1.0, score_voice / max(0.01, score_meeting + score_voice))

    # No-signal case: force low confidence so caller escalates
    if score_meeting + score_voice < 0.4:
        confidence = min(confidence, 0.5)
        reasons.append("low total signal — escalate")

    return {
        "type": decision,
        "confidence": round(confidence, 3),
        "reasoning": "; ".join(reasons) or "no_features",
    }


def build_llm_dispatch_payload(text: str, duration_seconds: float, speaker_count: int) -> dict[str, Any]:
    """Build the payload for the LLM-Assisted MCP Pattern callback.

    The MCP tool returns this when heuristic confidence is below threshold.
    The AI client reads `instructions`, runs the classification, and calls
    submit-audio-classify-result with the answer.
    """
    preview = text[:2000]
    return {
        "needs_llm": True,
        "task": "audio-classify",
        "transcript_preview": preview,
        "transcript_full_length_chars": len(text),
        "duration_seconds": duration_seconds,
        "speaker_count": speaker_count,
        "instructions": (
            "Read the transcript preview. Decide whether this is a personal voice memo "
            "(the user talking to themselves) or a meeting recording (multi-person conversation). "
            "Return JSON with keys 'type' (one of voice-memo | meeting), 'confidence' (0..1), "
            "'reasoning' (short string explaining the call)."
        ),
        "expected_result_schema": {
            "type": "string (voice-memo | meeting)",
            "confidence": "number 0..1",
            "reasoning": "string",
        },
    }
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest shared-vault/skills/audio-ingest/augur/tests/test_classifier.py -v
```
Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/audio-ingest/scripts/classifier.py shared-vault/skills/audio-ingest/augur/tests/test_classifier.py
git commit -m "$(cat <<'EOF'
feat(audio-ingest): heuristic classifier + LLM-assisted dispatch payload (ADR-752)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Attendee resolver (graph-backed)

**Files:**
- Create: `shared-vault/skills/audio-ingest/scripts/attendee_resolver.py`
- Create: `shared-vault/skills/audio-ingest/augur/tests/test_attendee_resolver.py`

- [ ] **Step 1: Inspect the ADR-738 graph reader**

```bash
grep -rln "graph\|entity" shared-vault/skills/graph/scripts/ 2>/dev/null | head -10
```
Find the public function for "given a candidate name, return matching person-entity slug + confidence". Likely under `shared-vault/skills/graph/scripts/` with a name like `resolve_entity_by_name`.

If the graph skill is not yet built or no such reader exists, this task degrades gracefully — the resolver returns an empty list and we log the gap. The note write still happens.

- [ ] **Step 2: Write the failing test**

```python
# shared-vault/skills/audio-ingest/augur/tests/test_attendee_resolver.py
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[5]
RESOLVER_PATH = PROJECT_ROOT / "shared-vault" / "skills" / "audio-ingest" / "scripts" / "attendee_resolver.py"


def _load_resolver():
    spec = importlib.util.spec_from_file_location("audio_ingest_resolver", RESOLVER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["audio_ingest_resolver"] = module
    spec.loader.exec_module(module)
    return module


def test_extracts_speaker_names_from_bracket_tags():
    r = _load_resolver()
    names = r.extract_speaker_names_from_text("[Sasha] hi.\n[Priya] hello.\n[Jay] yo.")
    assert set(names) == {"Sasha", "Priya", "Jay"}


def test_extracts_no_names_from_plain_transcript():
    r = _load_resolver()
    assert r.extract_speaker_names_from_text("just some flat text") == []


def test_resolve_against_graph_returns_slugs_when_known():
    r = _load_resolver()

    def fake_lookup(name: str):
        return {"sasha": ("sasha-chen", 0.95), "priya": ("priya-rao", 0.93)}.get(name.lower())

    with patch.object(r, "_lookup_entity", side_effect=fake_lookup):
        slugs = r.resolve_speakers(["Sasha", "Priya", "Unknown"])
    assert slugs == ["sasha-chen", "priya-rao"]


def test_resolve_degrades_when_graph_unavailable():
    r = _load_resolver()
    with patch.object(r, "_lookup_entity", side_effect=RuntimeError("graph not available")):
        slugs = r.resolve_speakers(["Sasha", "Priya"])
    assert slugs == []
```

- [ ] **Step 3: Implement `attendee_resolver.py`**

```python
# shared-vault/skills/audio-ingest/scripts/attendee_resolver.py
"""Resolve meeting speakers to person-entity slugs via ADR-738 graph.

Degrades gracefully: if the graph reader is unavailable or raises, the resolver
returns an empty list and the note still gets written without attendee_slugs.
"""
from __future__ import annotations

import re
from typing import Optional

_BRACKET_NAME_RE = re.compile(r"^\s*\[([A-Z][A-Za-z0-9 _\-]*)\]", re.MULTILINE)


def extract_speaker_names_from_text(text: str) -> list[str]:
    """Return distinct bracket-tagged speaker names in first-seen order."""
    seen: list[str] = []
    for m in _BRACKET_NAME_RE.findall(text or ""):
        n = m.strip()
        if n and n not in seen:
            seen.append(n)
    return seen


def _lookup_entity(name: str) -> Optional[tuple[str, float]]:
    """Wrapper for the graph reader. Returns (slug, confidence) or None.

    Imported lazily so absence of the graph skill is a soft failure.
    """
    try:
        # Adjust this import to match the actual public surface in the graph skill.
        from shared_vault.skills.graph.scripts.entity_lookup import resolve_entity_by_name  # type: ignore
    except Exception:
        raise RuntimeError("graph skill entity_lookup not available")
    return resolve_entity_by_name(name, entity_type="person")


def resolve_speakers(speaker_names: list[str], min_confidence: float = 0.8) -> list[str]:
    """Return the slugs for resolved speakers; skip unresolved or low-confidence."""
    resolved: list[str] = []
    for name in speaker_names:
        try:
            hit = _lookup_entity(name)
        except Exception:
            return []  # graph unavailable — degrade silently
        if hit and hit[1] >= min_confidence:
            slug = hit[0]
            if slug not in resolved:
                resolved.append(slug)
    return resolved
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest shared-vault/skills/audio-ingest/augur/tests/test_attendee_resolver.py -v
```
Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/audio-ingest/scripts/attendee_resolver.py shared-vault/skills/audio-ingest/augur/tests/test_attendee_resolver.py
git commit -m "$(cat <<'EOF'
feat(audio-ingest): attendee resolver against ADR-738 graph (ADR-752)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Note writer for voice-memo and meeting

**Files:**
- Create: `shared-vault/skills/audio-ingest/scripts/note_writer.py`
- Create: `shared-vault/skills/audio-ingest/augur/tests/test_note_writer.py`

- [ ] **Step 1: Write the failing test**

```python
# shared-vault/skills/audio-ingest/augur/tests/test_note_writer.py
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
WRITER_PATH = PROJECT_ROOT / "shared-vault" / "skills" / "audio-ingest" / "scripts" / "note_writer.py"


def _load_writer():
    spec = importlib.util.spec_from_file_location("audio_ingest_writer", WRITER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["audio_ingest_writer"] = module
    spec.loader.exec_module(module)
    return module


def test_writes_voice_memo_with_correct_frontmatter(tmp_path):
    w = _load_writer()
    out = w.write_audio_note(
        notes_dir=tmp_path,
        audio_path=Path("/tmp/voice-monday.m4a"),
        note_type="voice-memo",
        title="Monday Recap",
        transcript_text="I keep coming back to this idea about RRF.",
        segments=[],
        duration_seconds=72.0,
        provider="whisper-cpp",
        provider_version="1.5.4",
        attendee_slugs=[],
    )
    assert out.exists()
    body = out.read_text()
    assert "x-augur-note-type: voice-memo" in body
    assert "duration_seconds: 72.0" in body
    assert "provider: whisper-cpp" in body
    assert "transcript_status: complete" in body
    assert "monday-recap" in out.name.lower()


def test_writes_meeting_with_attendee_slugs(tmp_path):
    w = _load_writer()
    out = w.write_audio_note(
        notes_dir=tmp_path,
        audio_path=Path("/tmp/q2-planning.mp4"),
        note_type="meeting",
        title="Q2 Planning",
        transcript_text="[Sasha] start ... [Priya] revenue up.",
        segments=[],
        duration_seconds=2280.0,
        provider="whisper-cpp",
        provider_version="1.5.4",
        attendee_slugs=["sasha-chen", "priya-rao"],
    )
    body = out.read_text()
    assert "x-augur-note-type: meeting" in body
    assert "attendee_count: 2" in body
    assert "sasha-chen" in body
    assert "priya-rao" in body


def test_slug_derivation_handles_unicode_and_punctuation(tmp_path):
    w = _load_writer()
    out = w.write_audio_note(
        notes_dir=tmp_path,
        audio_path=Path("/tmp/x.m4a"),
        note_type="voice-memo",
        title="Café — Tuesday's *plan*",
        transcript_text="hi",
        segments=[],
        duration_seconds=10.0,
        provider="whisper-cpp",
        provider_version="x",
        attendee_slugs=[],
    )
    assert "cafe" in out.name.lower()
    assert "tuesday" in out.name.lower()
```

- [ ] **Step 2: Implement `note_writer.py`**

```python
# shared-vault/skills/audio-ingest/scripts/note_writer.py
"""Write a voice-memo or meeting note to <vault>/notes/.

Single entry point: write_audio_note(...). Returns the path that was written.
Idempotency: if a note with the same content hash already exists in notes_dir,
the function returns that path without rewriting.
"""
from __future__ import annotations

import hashlib
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

# Bootstrap project paths so we can import write_vault_frontmatter
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.lib.frontmatter_utils import write_vault_frontmatter  # noqa: E402


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(s: str, max_len: int = 80) -> str:
    # Strip accents via NFKD where possible; fall back to ASCII drop.
    import unicodedata
    norm = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    slug = _SLUG_RE.sub("-", norm.strip().lower()).strip("-")
    return slug[:max_len].rstrip("-") or "audio"


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def write_audio_note(
    *,
    notes_dir: Path,
    audio_path: Path,
    note_type: str,            # "voice-memo" or "meeting"
    title: str,
    transcript_text: str,
    segments: list[dict],
    duration_seconds: float,
    provider: str,
    provider_version: str,
    attendee_slugs: list[str],
) -> Path:
    notes_dir.mkdir(parents=True, exist_ok=True)
    date_prefix = date.today().isoformat()
    slug = _slugify(title or audio_path.stem)
    filename = f"{date_prefix}-{'voice' if note_type == 'voice-memo' else 'meeting'}-{slug}.md"
    target = notes_dir / filename

    if target.exists():
        return target  # idempotent on filename collision

    fm: dict[str, Any] = {
        "title": title,
        "x-augur-note-type": note_type,
        "audio_path": str(audio_path),
        "duration_seconds": duration_seconds,
        "transcript_status": "complete",
        "provider": provider,
        "provider_version": provider_version,
        "content_hash": _content_hash(transcript_text),
    }
    if note_type == "meeting":
        fm["attendee_count"] = len(attendee_slugs)
        if attendee_slugs:
            fm["attendee_slugs"] = attendee_slugs

    body_lines: list[str] = []
    if note_type == "meeting" and attendee_slugs:
        body_lines.append("## Attendees")
        for slug in attendee_slugs:
            body_lines.append(f"- [[wiki/people/{slug}]]")
        body_lines.append("")
    body_lines.append("## Transcript")
    body_lines.append("")
    body_lines.append(transcript_text)
    body_lines.append("")
    body = "\n".join(body_lines)

    write_vault_frontmatter(target, fm, body)
    return target
```

- [ ] **Step 3: Run the tests**

```bash
uv run pytest shared-vault/skills/audio-ingest/augur/tests/test_note_writer.py -v
```
Expected: all 3 tests pass.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/audio-ingest/scripts/note_writer.py shared-vault/skills/audio-ingest/augur/tests/test_note_writer.py
git commit -m "$(cat <<'EOF'
feat(audio-ingest): note_writer for voice-memo and meeting notes (ADR-752)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: MCP tools — `audio-classify`, `submit-audio-classify-result`, `audio-ingest-write`

**Files:**
- Create: `shared-vault/skills/audio-ingest/scripts/mcp/tools_audio.py`
- Create: `shared-vault/skills/audio-ingest/augur/tests/test_audio_mcp.py`
- Modify: `config/system/capability_exposure.yaml`

- [ ] **Step 1: Implement the three MCP tools**

```python
# shared-vault/skills/audio-ingest/scripts/mcp/tools_audio.py
"""MCP tools for audio-ingest skill.

Three tools:
  - audio-classify: heuristic-first; returns {needs_llm: true, ...} on low confidence
  - submit-audio-classify-result: companion for the LLM-Assisted MCP Pattern callback
  - audio-ingest-write: persist a voice-memo or meeting note to <vault>/notes/
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# Path bootstrap (same pattern as document-extractor tools_extract.py)
def _ensure_project_paths(start: Path) -> Path:
    for candidate in (start.parent, *start.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "src" / "config" / "paths.py").is_file():
            for path in (candidate / "src" / "mcp", candidate, candidate / "shared-vault"):
                text = str(path)
                if text not in sys.path:
                    sys.path.insert(0, text)
            return candidate
    raise RuntimeError(f"Unable to locate Augur project root from {start}")


_PROJECT_ROOT = _ensure_project_paths(Path(__file__).resolve())

from src.config.paths import get_vault_notes_dir  # noqa: E402
from skills.audio_ingest.scripts.classifier import classify_heuristic, build_llm_dispatch_payload  # noqa: E402
from skills.audio_ingest.scripts.attendee_resolver import (  # noqa: E402
    extract_speaker_names_from_text,
    resolve_speakers,
)
from skills.audio_ingest.scripts.note_writer import write_audio_note  # noqa: E402


def _load_skill_config() -> dict:
    import yaml
    cfg_path = Path(__file__).resolve().parents[2] / "config.yaml"
    if not cfg_path.exists():
        return {}
    with cfg_path.open() as fh:
        return yaml.safe_load(fh) or {}


def register(mcp: "FastMCP") -> None:
    @mcp.tool(name="audio-classify")
    def audio_classify(
        transcript_text: str,
        segments_json: str = "[]",
        duration_seconds: float = 0.0,
        speaker_count: int = 0,
    ) -> dict[str, Any]:
        cfg = _load_skill_config()
        threshold = float(cfg.get("classifier", {}).get("heuristic_threshold", 0.9))
        llm_assisted = bool(cfg.get("classifier", {}).get("llm_assisted", True))

        segments = json.loads(segments_json) if segments_json else []
        result = classify_heuristic(
            text=transcript_text,
            segments=segments,
            duration_seconds=duration_seconds,
            speaker_count=speaker_count,
        )
        if result["confidence"] >= threshold or not llm_assisted:
            return {"success": True, **result}
        # Escalate via LLM-Assisted MCP Pattern
        return build_llm_dispatch_payload(
            text=transcript_text,
            duration_seconds=duration_seconds,
            speaker_count=speaker_count,
        )

    @mcp.tool(name="submit-audio-classify-result")
    def submit_audio_classify_result(
        type_: str,         # passed as 'type_' to avoid shadowing the builtin in the tool client
        confidence: float,
        reasoning: str,
    ) -> dict[str, Any]:
        if type_ not in ("voice-memo", "meeting"):
            return {"success": False, "error": f"unexpected type: {type_}"}
        return {
            "success": True,
            "type": type_,
            "confidence": float(confidence),
            "reasoning": reasoning,
            "source": "llm",
        }

    @mcp.tool(name="audio-ingest-write")
    def audio_ingest_write(
        audio_path: str,
        note_type: str,                  # "voice-memo" or "meeting"
        title: str,
        transcript_text: str,
        segments_json: str = "[]",
        duration_seconds: float = 0.0,
        provider: str = "whisper-cpp",
        provider_version: str = "unknown",
    ) -> dict[str, Any]:
        if note_type not in ("voice-memo", "meeting"):
            return {"success": False, "error": f"unexpected note_type: {note_type}"}

        attendee_slugs: list[str] = []
        cfg = _load_skill_config()
        attendee_cfg = cfg.get("attendee_resolution", {})
        if note_type == "meeting" and attendee_cfg.get("enabled", True):
            names = extract_speaker_names_from_text(transcript_text)
            attendee_slugs = resolve_speakers(names)

        segments = json.loads(segments_json) if segments_json else []
        path = write_audio_note(
            notes_dir=get_vault_notes_dir(),
            audio_path=Path(audio_path),
            note_type=note_type,
            title=title,
            transcript_text=transcript_text,
            segments=segments,
            duration_seconds=duration_seconds,
            provider=provider,
            provider_version=provider_version,
            attendee_slugs=attendee_slugs,
        )
        return {
            "success": True,
            "path": str(path),
            "note_type": note_type,
            "attendee_slugs": attendee_slugs,
        }
```

- [ ] **Step 2: Wire the registration into the MCP runtime**

Find the MCP server registration sweep (somewhere under `src/mcp/`). It typically scans `shared-vault/skills/*/scripts/mcp/` for a `register` callable. If the runtime does NOT auto-discover, add an explicit registration entry. (Grep `_register_audio_ingest\|skills.audio_ingest` in `src/mcp/`.)

If a manual hook is needed, add to the relevant registration file:

```python
from skills.audio_ingest.scripts.mcp.tools_audio import register as register_audio_ingest
register_audio_ingest(mcp)
```

- [ ] **Step 3: Write integration tests**

```python
# shared-vault/skills/audio-ingest/augur/tests/test_audio_mcp.py
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[5]
TOOLS_PATH = PROJECT_ROOT / "shared-vault" / "skills" / "audio-ingest" / "scripts" / "mcp" / "tools_audio.py"


def _load_tools():
    spec = importlib.util.spec_from_file_location("audio_ingest_tools_audio", TOOLS_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["audio_ingest_tools_audio"] = module
    spec.loader.exec_module(module)
    return module


def _capture_tools(mod):
    """Register on a MagicMock and capture the registered callables by name."""
    captured = {}
    fake_mcp = MagicMock()
    def fake_tool(*, name):
        def wrap(fn):
            captured[name] = fn
            return fn
        return wrap
    fake_mcp.tool = fake_tool
    mod.register(fake_mcp)
    return captured


def test_audio_classify_heuristic_short_circuits_voice(tmp_path):
    mod = _load_tools()
    tools = _capture_tools(mod)
    r = tools["audio-classify"](
        transcript_text="I think about RRF. I keep coming back to it. I might write it up.",
        duration_seconds=42.0,
        speaker_count=0,
    )
    assert r["success"] is True
    assert r["type"] == "voice-memo"


def test_audio_classify_heuristic_short_circuits_meeting(tmp_path):
    mod = _load_tools()
    tools = _capture_tools(mod)
    r = tools["audio-classify"](
        transcript_text="[Sasha] hi.\n[Priya] hello.\n[Jay] yo.",
        duration_seconds=1800.0,
        speaker_count=3,
    )
    assert r["success"] is True
    assert r["type"] == "meeting"


def test_audio_classify_low_confidence_returns_needs_llm():
    mod = _load_tools()
    tools = _capture_tools(mod)
    r = tools["audio-classify"](
        transcript_text="ok yes",
        duration_seconds=10.0,
        speaker_count=1,
    )
    assert r.get("needs_llm") is True
    assert r["task"] == "audio-classify"


def test_audio_ingest_write_creates_voice_memo(monkeypatch, tmp_path):
    mod = _load_tools()
    tools = _capture_tools(mod)
    monkeypatch.setattr(mod, "get_vault_notes_dir", lambda: tmp_path)
    r = tools["audio-ingest-write"](
        audio_path="/tmp/voice.m4a",
        note_type="voice-memo",
        title="Hello",
        transcript_text="Hello world.",
        duration_seconds=2.0,
    )
    assert r["success"] is True
    p = Path(r["path"])
    assert p.exists()
    assert "x-augur-note-type: voice-memo" in p.read_text()
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest shared-vault/skills/audio-ingest/augur/tests/test_audio_mcp.py -v
```
Expected: all 4 tests pass.

- [ ] **Step 5: Update `capability_exposure.yaml`**

```yaml
  mcp-tool:audio-classify:
    classification_status: approved
    export_to:
    - shell
    management: generated
    owner_kind: augur
    preferred_client: shell
    primary_surface: mcp-tool
    scope: project
  mcp-tool:submit-audio-classify-result:
    classification_status: approved
    export_to:
    - shell
    management: generated
    owner_kind: augur
    preferred_client: shell
    primary_surface: mcp-tool
    scope: project
  mcp-tool:audio-ingest-write:
    classification_status: approved
    export_to:
    - shell
    management: generated
    owner_kind: augur
    preferred_client: shell
    primary_surface: mcp-tool
    scope: project
```

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/audio-ingest/scripts/mcp/ shared-vault/skills/audio-ingest/augur/tests/test_audio_mcp.py config/system/capability_exposure.yaml src/mcp/
git commit -m "$(cat <<'EOF'
feat(audio-ingest): audio-classify, submit-audio-classify-result, audio-ingest-write MCP tools (ADR-752)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Wire the Audio path into `/note` command policy

**Files:**
- Modify: `shared-vault/skills/ingest/commands/note.md`

- [ ] **Step 1: Replace the "Audio not yet implemented" stub with the live dispatch**

In `shared-vault/skills/ingest/commands/note.md`, find the `## Audio` section (added in Plan 1 Task 8 with a "not yet implemented" stub). Replace its body with:

```markdown
## Audio

Live in ADR-752.

1. Call atomic MCP tool `extract-audio` with the audio file path. Read the result: `text`, `segments`, `duration_seconds`, `speaker_count`, `provider`, `provider_version`.
2. **Resolve the audio sub-type.** If the user passed `--memo`, force `note_type = "voice-memo"`. If `--meeting`, force `note_type = "meeting"`. Otherwise:
   - Call atomic MCP tool `audio-classify` with `transcript_text`, `duration_seconds`, `speaker_count`.
   - If the response includes `needs_llm: true`, that is the LLM-Assisted MCP Pattern callback (see `docs/references/llm-assisted-mcp-pattern.md`). Read `instructions` and `transcript_preview`, decide `type` ∈ {`voice-memo`, `meeting`}, then call `submit-audio-classify-result` with `{type_, confidence, reasoning}`. Use that result.
   - Otherwise the response is the heuristic result directly. Use it.
3. **Derive a short human title.** Use the audio filename stem if no other context is available; for meetings, prefer the first speaker turn or an explicit "the meeting is about X" sentence in the transcript if present. The agent picks; no atomic op for this step.
4. **Persist via the atomic op.** Call `audio-ingest-write` with `audio_path`, `note_type`, `title`, `transcript_text`, `segments_json`, `duration_seconds`, `provider`, `provider_version`. The tool writes under `<vault>/notes/`, resolves attendees for meetings, returns the resolved path.
5. **Report.** Print the resolved card path. If the note type is `meeting` and attendee_slugs is non-empty, surface them. Suggest the "Merge to timeline" action if the meeting transcript shows decisions or action items.

Errors: if `extract-audio` fails (corrupt audio, provider not installed), surface the error to the user. Do not write a stub note (CLAUDE.md rule 1).
```

- [ ] **Step 2: Commit**

```bash
git add shared-vault/skills/ingest/commands/note.md
git commit -m "$(cat <<'EOF'
feat(ingest): /note dispatches audio path through extract-audio + audio-classify + audio-ingest-write (ADR-752)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: BrowseDetailPanel — voice-memo and meeting sections

**Files:**
- Modify: `apps/dashboard/components/shared/BrowseDetailPanel.tsx`
- Modify: `tests/dashboard/browse/BrowseDetailPanel.test.tsx`

- [ ] **Step 1: Add the voice-memo section**

In `BrowseDetailPanel.tsx`, after the existing `thought` and `image` branches added in Plan 1, add:

```tsx
{item.typeBadge === "voice-memo" && (
  <section className="space-y-3">
    {item.metadata?.audio_path && (
      // eslint-disable-next-line jsx-a11y/media-has-caption
      <audio controls src={`/api/vault-asset?path=${encodeURIComponent(item.metadata.audio_path)}`} className="w-full" />
    )}
    {item.metadata?.duration_seconds && (
      <div className="text-xs text-[var(--text-muted)]">
        Duration: {Math.round(Number(item.metadata.duration_seconds) / 60)} min · provider: {item.metadata.provider ?? "?"}
      </div>
    )}
    <details>
      <summary className="cursor-pointer text-sm text-[var(--text-secondary)]">Transcript</summary>
      <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap rounded bg-[var(--bg-secondary)] p-2 text-xs">
        {item.metadata?.transcript ?? "(transcript not available in metadata; open the source file)"}
      </pre>
    </details>
  </section>
)}
```

- [ ] **Step 2: Add the meeting section**

```tsx
{item.typeBadge === "meeting" && (
  <section className="space-y-3">
    {item.metadata?.audio_path && (
      // eslint-disable-next-line jsx-a11y/media-has-caption
      <audio controls src={`/api/vault-asset?path=${encodeURIComponent(item.metadata.audio_path)}`} className="w-full" />
    )}
    <div className="text-xs text-[var(--text-muted)]">
      Duration: {Math.round(Number(item.metadata.duration_seconds ?? 0) / 60)} min ·
      attendees: {item.metadata?.attendee_count ?? "?"} ·
      provider: {item.metadata?.provider ?? "?"}
    </div>
    {item.metadata?.attendee_slugs && (
      <div>
        <div className="text-[11px] uppercase tracking-wide text-[var(--text-muted)]">Attendees</div>
        <div className="mt-1 flex flex-wrap gap-1">
          {item.metadata.attendee_slugs.split(",").map((slug) => (
            <a key={slug} href={`/brain/wiki/people/${slug.trim()}`} className="rounded bg-[var(--bg-secondary)] px-2 py-0.5 text-xs">
              {slug.trim()}
            </a>
          ))}
        </div>
      </div>
    )}
    <details>
      <summary className="cursor-pointer text-sm text-[var(--text-secondary)]">Transcript (with speakers)</summary>
      <pre className="mt-2 max-h-[60vh] overflow-auto whitespace-pre-wrap rounded bg-[var(--bg-secondary)] p-2 text-xs">
        {item.metadata?.transcript ?? "(transcript not available in metadata; open the source file)"}
      </pre>
    </details>
    <button
      className="rounded border border-[var(--border-color)] px-3 py-1 text-sm hover:bg-[var(--bg-hover)]"
      onClick={() => { /* TODO_HOOK: ADR-740 timeline-merge call wired in a follow-up */ }}
    >
      Merge to timeline
    </button>
  </section>
)}
```

(The "Merge to timeline" button stays inert in this plan; wiring it is a follow-up in either ADR-740's plan or a tiny follow-up plan. Adding the button now puts the affordance in the UI so users know it's coming.)

- [ ] **Step 3: Tests**

```tsx
it("renders voice-memo audio player and transcript pane", () => {
  const { container, getByText } = render(
    <BrowseDetailPanel item={{
      ...baseItem,
      typeBadge: "voice-memo",
      metadata: { audio_path: "/tmp/voice.m4a", duration_seconds: "72", provider: "whisper-cpp", transcript: "Hello there." },
    }} />
  );
  expect(container.querySelector("audio")).toBeTruthy();
  expect(getByText(/1 min/)).toBeTruthy();
  expect(getByText(/Hello there/)).toBeTruthy();
});

it("renders meeting attendees and transcript", () => {
  const { getByText } = render(
    <BrowseDetailPanel item={{
      ...baseItem,
      typeBadge: "meeting",
      metadata: {
        audio_path: "/tmp/q2.mp4",
        duration_seconds: "2280",
        attendee_count: "2",
        attendee_slugs: "sasha-chen,priya-rao",
        provider: "whisper-cpp",
        transcript: "[Sasha] hi.",
      },
    }} />
  );
  expect(getByText("sasha-chen")).toBeTruthy();
  expect(getByText("priya-rao")).toBeTruthy();
  expect(getByText(/Merge to timeline/)).toBeTruthy();
});
```

- [ ] **Step 4: Run the tests**

```bash
cd apps/dashboard && pnpm test BrowseDetailPanel -- --run
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/components/shared/BrowseDetailPanel.tsx tests/dashboard/browse/BrowseDetailPanel.test.tsx
git commit -m "$(cat <<'EOF'
feat(dashboard): BrowseDetailPanel voice-memo + meeting sections (ADR-752)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Sync agents + rebuild dashboard

**Files:** none modified directly. Regenerates client-surface artifacts.

- [ ] **Step 1: Sync commands and MCP tool surfaces to clients**

Per memory `feedback-sync-agents-artifact-scope`:

```bash
augur sync commands all
augur sync mcp all
```
Expected: the new MCP tools appear in each client's generated surface; `/note` command body is unchanged (it was updated in Task 10).

- [ ] **Step 2: Rebuild dashboard via `/dev-build`**

```bash
/dev-build
```
Expected: rebuild succeeds; dev server up.

- [ ] **Step 3: Commit any generated-surface changes**

```bash
git add .claude .codex .gemini src/mcp/
git status
# Commit if anything was generated:
git commit -m "$(cat <<'EOF'
chore(sync): regenerate client surfaces for audio-ingest (ADR-752)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)" 2>/dev/null || echo "Nothing to commit; already in sync."
```

---

## Task 13: Real-data verification per Rule 34

**Files:** none modified. Real-vault value validation.

- [ ] **Step 1: Record a short voice memo**

On macOS: open Voice Memos app, record a 30–60 second monologue, then drag the resulting `.m4a` to `~/Downloads/voice-memo-verify.m4a`.

- [ ] **Step 2: Run `/note` against the real voice memo**

In an active AI client session:

```
/note ~/Downloads/voice-memo-verify.m4a
```

Expected (concrete behavior):
- Agent dispatches the Audio path
- `extract-audio` transcribes (~10–30 seconds depending on duration + model)
- `audio-classify` heuristic returns `voice-memo` with high confidence (single speaker, short, first-person)
- `audio-ingest-write` produces a note under `<vault>/notes/`

Verify:

```bash
ls -t "$(uv run python -c 'from src.config.paths import get_vault_notes_dir; print(get_vault_notes_dir())')" | head -1
head -25 "$(uv run python -c 'from src.config.paths import get_vault_notes_dir; print(get_vault_notes_dir())')/$(ls -t $(uv run python -c 'from src.config.paths import get_vault_notes_dir; print(get_vault_notes_dir())') | head -1)"
```

Expected: latest file is the voice-memo note. Frontmatter contains:
- `x-augur-note-type: voice-memo`
- `duration_seconds: <real duration>`
- `provider: whisper-cpp`
- `transcript_status: complete`

Body contains the transcribed text (read it; does it correspond to what you actually said?).

- [ ] **Step 3: Get a real meeting recording**

Find a meeting recording you have permission to use (Zoom export, internal recording, podcast episode for testing, etc.). Drop to `~/Downloads/meeting-verify.m4a` (or `.mp4`).

If you do not have a real meeting recording handy: use a podcast episode (any 2+ speaker podcast on disk). Mark the verification as "synthetic-but-real" in the notes.

- [ ] **Step 4: Run `/note` against the meeting**

```
/note ~/Downloads/meeting-verify.m4a
```

Expected: agent dispatches Audio path; classification returns `meeting` (multi-speaker); note written with `x-augur-note-type: meeting`, `attendee_count >= 2`.

- [ ] **Step 5: Verify in the dashboard browser**

Open `http://localhost:3000/browse?view=notes&type=voice-memo,meeting`. Confirm:
- Voice-memo card appears with the Mic badge and minute-count
- Meeting card appears with the Users badge and attendee-count
- Click into each card: detail panel renders the audio player + transcript pane
- For the meeting: attendee chips render (even if attendee_slugs is empty — section degrades gracefully)

- [ ] **Step 6: Test the `--memo` and `--meeting` overrides**

```
/note --memo ~/Downloads/meeting-verify.m4a
```

Expected: classifier-override path. Note is written with `x-augur-note-type: voice-memo` regardless of speaker count. Inspect frontmatter to confirm.

```
/note --meeting ~/Downloads/voice-memo-verify.m4a
```

Expected: written as meeting. Inspect frontmatter.

- [ ] **Step 7: Document the verification**

Append to `docs/migrations/2026-05-15-notes-zone-migration.md` (or create a new audio-verification log):

```bash
cat >> docs/migrations/2026-05-15-notes-zone-migration.md <<'EOF'

## Audio ingest verification (2026-05-16, ADR-752)

- Voice memo: <real audio path>, duration <s>s, transcript word-count <N>
- Meeting: <real audio path>, duration <s>s, speakers detected <N>, attendees resolved <N>
- Override tests: --memo and --meeting both observed to force the type as expected
- Provider: whisper-cpp (medium.en), version <pywhispercpp version>
- Issues: <list any divergence from expected behavior>
EOF
git add docs/migrations/2026-05-15-notes-zone-migration.md
git commit -m "$(cat <<'EOF2'
chore(verify): record ADR-752 audio-ingest real-data verification

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF2
)"
```

This step satisfies CLAUDE.md Rule 34: the capability was exercised against real audio (not tmp fixtures) and the user-facing outputs (real notes with real transcripts, real attendee chips, real audio players) are inspectable.

---

## Self-Review

**1. Spec coverage**

| Spec section | Task |
|--------------|------|
| audio-ingest skill (new skill) | Task 5 |
| Voice + meeting modalities | Tasks 6, 8, 11 |
| document-extractor transcription op | Tasks 2, 3, 4 |
| Pluggable provider via SKILL.md frontmatter | Task 2 (facade) + Task 3 (default provider) + Task 4 (config wiring) |
| whisper.cpp default | Task 3 |
| Agent classifier (memo vs meeting) | Tasks 6, 9 (LLM-Assisted MCP Pattern) |
| `--memo` / `--meeting` overrides | Task 10 (note.md dispatch) + Task 13 step 6 (verification) |
| Speaker labeling | Task 3 (`speaker_labels` option) — provider-supplied when available |
| Attendee resolution from graph (ADR-738) | Task 7 |
| Timeline merge target (ADR-740) | Task 11 (UI affordance — actual wiring follow-up) |
| BrowseDetailPanel voice-memo + meeting sections | Task 11 |
| ADR-752 document | Task 1 |
| Capability exposure for new MCP tools | Tasks 4, 9 |
| Real-data verification per Rule 34 | Task 13 |
| Browser verification per Rule 28 | Task 13 step 5 |
| Open question (heuristic vs LLM accuracy) | Resolved during Task 6 by the heuristic's 0.9-threshold short-circuit; LLM dispatched only when heuristic is uncertain |

Gaps: timeline-merge button is inert (Task 11 step 2 — flagged as a follow-up; not a spec gap since ADR-740 governs the merge mechanics, not this plan).

**2. Placeholder scan**

```bash
grep -nE "TODO|TBD|FIXME|XXX|appropriate error|similar to Task" docs/superpowers/plans/2026-05-16-adr-752-audio-ingest-skill.md
```
Expected matches: only the self-review section's `grep` command itself and the one explicit `TODO_HOOK:` comment in Task 11 step 2 (intentional — marks the follow-up wire-up of timeline-merge). The `TODO_HOOK:` follows CLAUDE.md Rule 7 (TODO_ markers for discovered debt).

**3. Type consistency**

- `Transcript` / `Segment` defined in Task 2 — used by Tasks 3, 4, 9 (`audio-ingest-write` reads transcript JSON from the same shape).
- `extract-audio` MCP tool — returns dict in Task 4 step 2; consumed by `/note` Audio dispatch in Task 10.
- `audio-classify` payload shape — defined in Task 6 (`build_llm_dispatch_payload`); consumed by `/note` in Task 10; companion tool `submit-audio-classify-result` matches in Task 9.
- `audio-ingest-write` parameters — declared in Task 9; called from `/note` Task 10 with matching args.
- BrowseItem metadata keys — `attendee_slugs`, `audio_path`, `transcript`, `duration_seconds`, `provider` — written by Task 9 (`write_audio_note`), read by Task 11 (BrowseDetailPanel sections).
- `note_type` values — `voice-memo` and `meeting` consistent across classifier, writer, MCP tools, command policy, and BrowseDetailPanel.

No inconsistencies.

---

## Execution handoff

Plan 2 complete and saved to `docs/superpowers/plans/2026-05-16-adr-752-audio-ingest-skill.md`. Plan 3 (article enrichment) still to write before any execution.
