"""whisper.cpp adapter.

Preferred backend is the ``pywhispercpp`` Python binding. When that binding is
not installed, this provider falls back to the ``whisper-cli`` binary (e.g. the
Homebrew ``whisper-cpp`` formula) driving the same ggml models. The binary path
is what actually works on macOS today, so the fallback is first-class, not a
degraded mode.
"""

from __future__ import annotations

from dataclasses import replace
from importlib.metadata import version
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from src.config.paths import get_cache_dir
from src.logging import get_entity_logger

from . import register_provider
from .types import Segment, Transcript

logger = get_entity_logger("lib.extraction.transcription.whisper_cpp")

_MODEL_CACHE: dict[str, Any] = {}

# whisper-cli backend (Homebrew whisper-cpp). pywhispercpp downloads ggml models
# into this directory, so it doubles as the binary backend's model store.
_DEFAULT_CLI_MODEL_DIR = Path.home() / "Library" / "Application Support" / "pywhispercpp" / "models"
_CLI_MODEL_DIR_ENV = "AUGUR_WHISPER_CPP_MODEL_DIR"
# Model used when an English-only (``.en``) model is requested for non-English
# speech. large-v3-turbo is multilingual and handles most languages.
_MULTILINGUAL_FALLBACK_MODEL = "large-v3-turbo"
_ENGLISH_LANGUAGES = {"", "en", "english", "auto"}

# Hebrew gets the ivrit.ai large-v3 finetune when its ggml model is present:
# empirically more accurate on Hebrew speech than large-v3-turbo (the reason
# island-io/mila ships it for Hebrew). Falls back to the multilingual model
# when the ivrit ``.bin`` is not installed, so this never regresses Hebrew.
_HEBREW_LANGUAGES = {"he", "heb", "hebrew", "iw"}
_HEBREW_MODEL = "ivrit-ai-whisper-large-v3"


def _get_model(name: str) -> Any:
    if name in _MODEL_CACHE:
        return _MODEL_CACHE[name]
    try:
        from pywhispercpp.model import Model  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "pywhispercpp is required for whisper-cpp transcription. " "Install with: uv sync --extra audio"
        ) from exc
    model = Model(name)
    _MODEL_CACHE[name] = model
    return model


def _provider_version() -> str:
    try:
        return version("pywhispercpp")
    except Exception:
        return "unknown"


def _segment_time_seconds(raw: Any, primary_attr: str, whisper_attr: str) -> float:
    value = getattr(raw, primary_attr, None)
    if value is not None:
        return float(value or 0.0)
    # pywhispercpp exposes whisper.cpp timestamps as centiseconds: t0/t1.
    whisper_value = getattr(raw, whisper_attr, None)
    if whisper_value is not None:
        return float(whisper_value or 0.0) / 100.0
    return 0.0


def _select_model(model_name: str, language: str) -> str:
    """Pick the best model for the requested language.

    ``medium.en``/``tiny.en`` etc. emit ``(speaking in foreign language)`` for
    non-English audio, so for a non-English language we transcribe with a
    multilingual model instead. Hebrew prefers the ivrit.ai large-v3 finetune
    when it is installed, otherwise large-v3-turbo.
    """
    lang = language.strip().lower()
    if lang in _HEBREW_LANGUAGES:
        # Use ivrit only when its ggml bin is actually present; otherwise keep a
        # working multilingual model rather than failing on a missing file.
        if _model_bin_path(_HEBREW_MODEL).is_file():
            return _HEBREW_MODEL
        return _MULTILINGUAL_FALLBACK_MODEL
    if model_name.endswith(".en") and lang not in _ENGLISH_LANGUAGES:
        return _MULTILINGUAL_FALLBACK_MODEL
    return model_name


def _model_bin_path(model_name: str) -> Path:
    """Resolve the ggml ``.bin`` file for a model name in the CLI model dir."""
    model_dir = Path(os.environ.get(_CLI_MODEL_DIR_ENV) or _DEFAULT_CLI_MODEL_DIR).expanduser()
    name = model_name if model_name.startswith("ggml-") else f"ggml-{model_name}"
    if not name.endswith(".bin"):
        name = f"{name}.bin"
    return model_dir / name


def _parse_cli_json(data: dict, *, requested_language: str, model_name: str) -> Transcript:
    """Parse whisper-cli ``-oj`` JSON into a provider-neutral Transcript.

    whisper-cli reports per-segment ``offsets`` in milliseconds and the detected
    language under ``result.language``.
    """
    segments: list[Segment] = []
    for raw in data.get("transcription", []) or []:
        offsets = raw.get("offsets", {}) or {}
        text = str(raw.get("text", "")).strip()
        segments.append(
            Segment(
                start=float(offsets.get("from", 0) or 0) / 1000.0,
                end=float(offsets.get("to", 0) or 0) / 1000.0,
                text=text,
            )
        )
    text = " ".join(segment.text for segment in segments if segment.text).strip()
    duration = max((segment.end for segment in segments), default=0.0)
    detected_language = str((data.get("result") or {}).get("language") or requested_language)
    return Transcript(
        text=text,
        segments=segments,
        duration_seconds=duration,
        language=detected_language,
        provider="whisper-cpp",
        provider_version=_provider_version(),
        extra={"model": model_name, "backend": "whisper-cli"},
    )


def _to_wav_16k(audio_path: Path) -> Path:
    """Decode any audio to the 16kHz mono PCM WAV whisper.cpp requires."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to transcribe audio with whisper-cli.")
    cache_dir = get_cache_dir() / "transcription"
    cache_dir.mkdir(parents=True, exist_ok=True)
    fd, wav_str = tempfile.mkstemp(suffix=".wav", dir=str(cache_dir))
    os.close(fd)
    wav = Path(wav_str)
    subprocess.run(
        [ffmpeg, "-nostdin", "-y", "-i", str(audio_path), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)],
        check=True,
        capture_output=True,
    )
    return wav


def _run_cli(binary: str, model_bin: Path, audio_path: Path, language: str) -> dict:
    """Run whisper-cli on the audio and return its parsed ``-oj`` JSON."""
    wav = _to_wav_16k(audio_path)
    out_prefix = wav.with_suffix("")
    json_out = Path(f"{out_prefix}.json")
    try:
        subprocess.run(
            [
                binary,
                "-m",
                str(model_bin),
                "-f",
                str(wav),
                "-l",
                language or "auto",
                "-np",
                "-oj",
                "-of",
                str(out_prefix),
            ],
            check=True,
            capture_output=True,
        )
        return json.loads(json_out.read_text(encoding="utf-8"))
    finally:
        for leftover in (wav, json_out):
            try:
                leftover.unlink()
            except OSError:
                pass


def _transcribe_via_cli(audio_path: Path, options: dict) -> Transcript:
    """Fallback path: transcribe through the whisper-cli binary."""
    binary = shutil.which("whisper-cli") or shutil.which("whisper")
    if not binary:
        raise RuntimeError(
            "Neither pywhispercpp nor a whisper-cli binary is available. "
            "Install with 'uv sync --extra audio' or 'brew install whisper-cpp'."
        )
    model_name = _select_model(str(options.get("model", "medium.en")), str(options.get("language", "en")))
    language = str(options.get("language", "en"))
    model_bin = _model_bin_path(model_name)
    if not model_bin.is_file():
        raise RuntimeError(
            f"whisper model not found: {model_bin}. Download it into {model_bin.parent} "
            f"(e.g. ggml-{model_name}.bin from huggingface ggerganov/whisper.cpp)."
        )
    data = _run_cli(binary, model_bin, audio_path, language)
    return _parse_cli_json(data, requested_language=language, model_name=model_name)


def transcribe_whisper_cpp(audio_path: Path, options: dict) -> Transcript:
    """Transcribe an audio file through pywhispercpp, falling back to whisper-cli."""
    model_name = _select_model(str(options.get("model", "medium.en")), str(options.get("language", "en")))
    language = str(options.get("language", "en"))
    speaker_labels = bool(options.get("speaker_labels", False))

    try:
        model = _get_model(model_name)
    except RuntimeError:
        # pywhispercpp binding missing — use the whisper-cli binary backend.
        transcript = _transcribe_via_cli(Path(audio_path), options)
        return _maybe_diarize(Path(audio_path), transcript, speaker_labels)

    raw_segments = model.transcribe(str(audio_path), language=language)

    segments: list[Segment] = []
    for raw in raw_segments:
        speaker = getattr(raw, "speaker", None) if speaker_labels else None
        segments.append(
            Segment(
                start=_segment_time_seconds(raw, "start", "t0"),
                end=_segment_time_seconds(raw, "end", "t1"),
                text=str(getattr(raw, "text", "")).strip(),
                speaker=str(speaker) if speaker else None,
            )
        )

    text = " ".join(segment.text for segment in segments if segment.text).strip()
    duration = max((segment.end for segment in segments), default=0.0)
    transcript = Transcript(
        text=text,
        segments=segments,
        duration_seconds=duration,
        language=language,
        provider="whisper-cpp",
        provider_version=_provider_version(),
        extra={"model": model_name},
    )
    return _maybe_diarize(Path(audio_path), transcript, speaker_labels)


def _maybe_diarize(audio_path: Path, transcript: Transcript, speaker_labels: bool) -> Transcript:
    """Overlay pyannote speaker turns onto the transcript when requested.

    Best-effort: when ``speaker_labels`` is off, or the optional diarization
    extra / models are absent, the transcript is returned unchanged. A real
    diarization failure is recorded in ``extra['diarization_error']`` rather
    than aborting transcription — the user still gets their text.
    """
    if not speaker_labels:
        return transcript

    try:
        from .diarize import assign_speakers, diarize, is_available
    except Exception:  # pragma: no cover - import guard
        return transcript

    if not is_available():
        return transcript

    wav: Path | None = None
    try:
        wav = _to_wav_16k(audio_path)
        turns = diarize(wav)
        labeled = assign_speakers(transcript.segments, turns)
        extra = dict(transcript.extra)
        extra["diarized"] = True
        extra["diarization_turns"] = len(turns)
        return replace(transcript, segments=labeled, extra=extra)
    except Exception as exc:
        logger.warning("diarization failed; returning unlabeled transcript: %s", exc)
        extra = dict(transcript.extra)
        extra["diarization_error"] = str(exc)
        return replace(transcript, extra=extra)
    finally:
        if wav is not None:
            try:
                wav.unlink()
            except OSError:
                pass


register_provider("whisper-cpp", transcribe_whisper_cpp)
