"""Audio transcription — local Whisper first, then local macOS fallback."""

from __future__ import annotations

import platform
from pathlib import Path

from src.lib.extraction.transcription import (
    AUDIO_EXTENSIONS as _AUDIO_EXTENSIONS,
    AUGUR_LOCAL_WHISPER_MODEL_ENV,
    can_transcribe_audio,
    transcribe_audio,
)

AUDIO_EXTENSIONS = _AUDIO_EXTENSIONS


def can_extract_audio(model_dir: str | None = None) -> bool:
    if can_transcribe_audio(model_dir=_resolve_model_dir(model_dir)):
        return True
    if platform.system() == "Darwin":
        return True
    return False


def extract_audio(path: str, *, model_dir: str | None = None) -> str | None:
    resolved_model_dir = _resolve_model_dir(model_dir)
    if resolved_model_dir:
        transcript = transcribe_audio(path, model_dir=resolved_model_dir)
    else:
        transcript = transcribe_audio(path)
    if transcript.success:
        return _format_transcript_markdown(transcript)

    if platform.system() == "Darwin":
        result = _extract_audio_macos(path)
        if result:
            return result
    return None


def _extract_audio_macos(path: str) -> str | None:
    # Stub for a future local SFSpeechRecognizer helper.
    # Future: Swift helper for SFSpeechRecognizer offline transcription.
    return None


def _format_transcript_markdown(transcript) -> str:
    lines = [
        "# Audio Transcript",
        "",
        f"Method: {transcript.method}",
        f"Backend: {transcript.backend}",
        f"Confidence: {transcript.confidence}",
    ]
    if transcript.language:
        lines.append(f"Language: {transcript.language}")
    if transcript.duration_s is not None:
        lines.append(f"Duration seconds: {transcript.duration_s:.2f}")
    lines.extend(["", transcript.transcript.strip()])
    return "\n".join(lines)


format_transcript_markdown = _format_transcript_markdown


def _resolve_model_dir(model_dir: str | None = None) -> str | None:
    candidate = model_dir or _env_model_dir()
    if not candidate:
        return None
    path = Path(candidate).expanduser()
    if not path.exists():
        return None
    return str(path)


def _env_model_dir() -> str | None:
    import os

    return os.environ.get(AUGUR_LOCAL_WHISPER_MODEL_ENV)
