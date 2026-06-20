"""Local-only audio transcription helpers."""

from __future__ import annotations

from array import array
from dataclasses import dataclass
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any

from src.config.paths import get_cache_dir
from src.lib.extraction.local_backend_config import (
    DEFAULT_ASR_MODEL,
    get_local_asr_model_name,
    get_local_fast_whisper_model_name,
    local_model_dir_name,
    openvino_repo_id_for_model,
)

AUDIO_EXTENSIONS = {
    ".aac",
    ".flac",
    ".m4a",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".ogg",
    ".wav",
    ".webm",
}
AUGUR_LOCAL_WHISPER_MODEL_ENV = "AUGUR_LOCAL_WHISPER_MODEL_DIR"
DEFAULT_LOCAL_WHISPER_MODEL_NAME = DEFAULT_ASR_MODEL
OPENVINO_WHISPER_DEVICES = ("NPU", "GPU", "CPU")
OPENVINO_DEVICE_STATUS_FILENAME = "openvino-whisper-status.json"
OPENVINO_NPU_FAILURE_COOLDOWN_S = 86_400


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
    note: str | None = None
    route_mode: str | None = None
    route_engine_id: str | None = None
    fallback_engine_id: str | None = None


def _has_whisper_cli_backend() -> bool:
    """True if the whisper-cli binary and at least one ggml model are present.

    This is the whisper.cpp binary backend used by the ``whisper-cpp`` provider
    when the pywhispercpp binding is not installed.
    """
    if not (shutil.which("whisper-cli") or shutil.which("whisper")):
        return False
    model_dir = Path(
        os.environ.get("AUGUR_WHISPER_CPP_MODEL_DIR")
        or (Path.home() / "Library" / "Application Support" / "pywhispercpp" / "models")
    ).expanduser()
    try:
        return any(model_dir.glob("ggml-*.bin"))
    except OSError:
        return False


def can_transcribe_audio(model_dir: str | None = None) -> bool:
    """Return whether a local transcription backend is available on this OS."""
    if not _has_ffmpeg():
        return False
    # whisper-cli (Homebrew whisper-cpp) is a valid backend on every OS.
    if _has_whisper_cli_backend():
        return True
    if sys.platform == "darwin":
        if _module_available("faster_whisper") and _existing_faster_whisper_model_path(model_dir) is not None:
            return True
        return _module_available("openvino_genai") and _local_model_path(model_dir) is not None
    return _module_available("openvino_genai") and _local_model_path(model_dir) is not None


def transcribe_audio(path: str, *, model_dir: str | None = None) -> TranscriptResult:
    """Transcribe audio with local backends only.

    Windows/Linux use OpenVINO Whisper with an explicit NPU -> GPU -> CPU probe.
    macOS uses faster-whisper first because OpenVINO arm64 is CPU-only.
    """
    audio_path = Path(path)
    if not audio_path.exists():
        return _unavailable(f"Audio file does not exist: {audio_path}")
    if audio_path.suffix.lower() not in AUDIO_EXTENSIONS:
        return _unavailable(f"Unsupported audio extension: {audio_path.suffix}")
    if not _has_ffmpeg():
        return _unavailable("ffmpeg or avconv is required for local audio transcription")

    if sys.platform == "darwin":
        if _module_available("faster_whisper"):
            local_model_path = _resolve_faster_whisper_model_path(model_dir)
            if local_model_path is None:
                return _unavailable("A local faster-whisper model directory is required")
            return _transcribe_faster_whisper(audio_path, model_dir=str(local_model_path))
        if _module_available("openvino_genai"):
            local_model_path = _resolve_transcription_model_path(model_dir)
            if local_model_path is None:
                return _unavailable("A local transcription model directory is required")
            return _transcribe_openvino(audio_path, model_dir=str(local_model_path))
        return _unavailable("No local transcription backend installed (need faster-whisper or openvino-genai)")

    local_model_path = _resolve_transcription_model_path(model_dir)
    if local_model_path is None:
        return _unavailable("A local transcription model directory is required")

    if _module_available("openvino_genai"):
        return _transcribe_openvino(audio_path, model_dir=str(local_model_path))
    return _unavailable("OpenVINO GenAI is required for local transcription on this OS")


def _transcribe_openvino(
    path: Path,
    *,
    model_dir: str,
    devices: tuple[str, ...] = OPENVINO_WHISPER_DEVICES,
) -> TranscriptResult:
    import openvino_genai

    try:
        raw_speech_input = _load_audio_samples_16khz(path)
    except RuntimeError as exc:
        return TranscriptResult(
            success=False,
            transcript="",
            method="openvino-whisper",
            backend="audio-decode",
            cloud_used=False,
            needs_review=True,
            error=str(exc),
        )
    if not raw_speech_input:
        return TranscriptResult(
            success=False,
            transcript="",
            method="openvino-whisper",
            backend="audio-decode",
            cloud_used=False,
            needs_review=True,
            error="Audio decode produced no samples",
        )

    last_error: Exception | None = None
    runtime_devices, device_failures = _openvino_runtime_device_plan(devices, model_dir)
    if not runtime_devices:
        return TranscriptResult(
            success=False,
            transcript="",
            method="openvino-whisper",
            backend=devices[0] if devices else "unknown",
            cloud_used=False,
            needs_review=True,
            error="No OpenVINO devices available after runtime compatibility checks",
        )

    last_device = runtime_devices[-1]
    for device in runtime_devices:
        last_device = device
        try:
            pipeline = openvino_genai.WhisperPipeline(
                str(model_dir),
                device,
                **_openvino_whisper_pipeline_kwargs(device),
            )
            result = pipeline.generate(raw_speech_input)
            transcript = _stringify_transcript(result)
            _record_openvino_device_status(
                device=device,
                model_dir=model_dir,
                success=bool(transcript.strip()),
                device_failures=device_failures,
            )
            return TranscriptResult(
                success=bool(transcript.strip()),
                transcript=transcript,
                method="openvino-whisper",
                backend=device,
                confidence="medium",
                needs_review=not bool(transcript.strip()),
            )
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            device_failures[device] = {
                "error": str(exc),
                "timestamp": time.time(),
            }
            continue

    _record_openvino_device_status(
        device=last_device,
        model_dir=model_dir,
        success=False,
        error=str(last_error) if last_error else None,
        device_failures=device_failures,
    )
    return TranscriptResult(
        success=False,
        transcript="",
        method="openvino-whisper",
        backend=last_device,
        cloud_used=False,
        needs_review=True,
        error=f"All OpenVINO devices failed; last error: {last_error}",
    )


def _openvino_whisper_pipeline_kwargs(device: str) -> dict[str, Any]:
    """Return device-specific OpenVINO GenAI Whisper pipeline options."""
    if device == "NPU":
        return {"STATIC_PIPELINE": True}
    return {}


def _openvino_runtime_device_plan(
    devices: tuple[str, ...],
    model_dir: str,
) -> tuple[tuple[str, ...], dict[str, dict[str, Any]]]:
    """Return usable devices plus failures that should be preserved in status."""
    device_failures: dict[str, dict[str, Any]] = {}
    if "NPU" not in devices:
        return devices, device_failures

    if not _npu_driver_ready_for_openvino():
        device_failures["NPU"] = {
            "error": "NPU driver below OpenVINO runtime floor",
            "timestamp": time.time(),
        }
        return tuple(device for device in devices if device != "NPU"), device_failures

    recent_failure = _recent_openvino_device_failure("NPU", model_dir)
    if recent_failure is not None:
        device_failures["NPU"] = recent_failure
        return tuple(device for device in devices if device != "NPU"), device_failures

    return devices, device_failures


def _npu_driver_ready_for_openvino() -> bool:
    from src.lib.extraction.capabilities import npu_driver_ready_for_openvino

    return npu_driver_ready_for_openvino()


def _recent_openvino_device_failure(device: str, model_dir: str) -> dict[str, Any] | None:
    status = get_last_openvino_device_status()
    if not status or not _openvino_status_matches_model(status, model_dir):
        return None

    candidates: list[dict[str, Any]] = []
    if status.get("success") is False and status.get("device") == device:
        candidates.append(status)
    failures = status.get("device_failures")
    if isinstance(failures, dict):
        failure = failures.get(device)
        if isinstance(failure, dict):
            candidates.append(failure)

    for candidate in candidates:
        timestamp = candidate.get("timestamp")
        if not isinstance(timestamp, (int, float)):
            continue
        now = time.time()
        if now - float(timestamp) > OPENVINO_NPU_FAILURE_COOLDOWN_S:
            continue
        boot_time = _current_boot_time()
        if boot_time is not None and float(timestamp) < boot_time:
            continue
        return {
            "error": str(candidate.get("error") or "OpenVINO device failed"),
            "timestamp": float(timestamp),
        }
    return None


def _openvino_status_matches_model(status: dict[str, Any], model_dir: str) -> bool:
    status_model = status.get("model_dir")
    return not isinstance(status_model, str) or Path(status_model) == Path(model_dir)


def _current_boot_time() -> float | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes

        uptime_ms = ctypes.windll.kernel32.GetTickCount64()
    except Exception:
        return None
    return time.time() - (float(uptime_ms) / 1000.0)


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
    except Exception as exc:
        return TranscriptResult(
            success=False,
            transcript="",
            method="faster-whisper",
            backend="auto",
            cloud_used=False,
            needs_review=True,
            error=str(exc),
        )


def _has_ffmpeg() -> bool:
    return _resolve_ffmpeg_binary() is not None


def _resolve_ffmpeg_binary() -> str | None:
    return shutil.which("ffmpeg") or shutil.which("avconv") or _packaged_ffmpeg_binary()


def _packaged_ffmpeg_binary() -> str | None:
    try:
        import imageio_ffmpeg

        path = Path(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        return None
    return str(path) if path.exists() else None


def _load_audio_samples_16khz(path: Path) -> list[float]:
    ffmpeg = _resolve_ffmpeg_binary()
    if not ffmpeg:
        raise RuntimeError("ffmpeg or avconv is required to decode audio for OpenVINO Whisper")

    try:
        result = subprocess.run(
            [
                ffmpeg,
                "-v",
                "error",
                "-i",
                str(path),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "s16le",
                "-",
            ],
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Audio decode failed: {exc}") from exc

    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(stderr or "Audio decode failed")

    samples = array("h")
    samples.frombytes(result.stdout)
    if sys.byteorder != "little":
        samples.byteswap()
    return [max(-1.0, min(1.0, sample / 32768.0)) for sample in samples]


def _local_model_path(model_dir: str | None) -> Path | None:
    candidates: list[Path] = []
    configured_model_dir = model_dir or os.environ.get(AUGUR_LOCAL_WHISPER_MODEL_ENV)
    if configured_model_dir:
        candidates.append(Path(configured_model_dir).expanduser())
    candidates.append(_default_local_model_dir())
    for path in candidates:
        if path.exists():
            return path
    return None


def _existing_faster_whisper_model_path(model_dir: str | None) -> Path | None:
    candidates: list[Path] = []
    configured_model_dir = model_dir or os.environ.get(AUGUR_LOCAL_WHISPER_MODEL_ENV)
    if configured_model_dir:
        candidates.append(Path(configured_model_dir).expanduser())
    candidates.append(_default_faster_whisper_model_dir())
    for path in candidates:
        if path.exists():
            return path
    return None


def _resolve_faster_whisper_model_path(model_dir: str | None) -> Path | None:
    existing = _existing_faster_whisper_model_path(model_dir)
    if existing is not None:
        return existing
    if model_dir or os.environ.get(AUGUR_LOCAL_WHISPER_MODEL_ENV) or _airplane_mode_enabled():
        return None
    return _download_default_faster_whisper_model()


def _resolve_transcription_model_path(model_dir: str | None) -> Path | None:
    existing = _local_model_path(model_dir)
    if existing is not None:
        return existing
    if model_dir or _airplane_mode_enabled():
        return None
    return _download_default_openvino_model()


def _download_default_openvino_model() -> Path | None:
    model_name = get_local_asr_model_name()
    model_dir = _default_local_model_dir()
    model_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import snapshot_download

        downloaded = snapshot_download(
            repo_id=openvino_repo_id_for_model(model_name),
            local_dir=str(model_dir),
        )
    except Exception:
        return None
    path = Path(downloaded)
    return path if path.exists() else model_dir if model_dir.exists() else None


def _download_default_faster_whisper_model() -> Path | None:
    model_name = get_local_fast_whisper_model_name()
    model_dir = _default_faster_whisper_model_dir()
    model_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import snapshot_download

        downloaded = snapshot_download(
            repo_id=model_name,
            local_dir=str(model_dir),
        )
    except Exception:
        return None
    path = Path(downloaded)
    return path if path.exists() else model_dir if model_dir.exists() else None


def _airplane_mode_enabled() -> bool:
    try:
        from src.config.preferences import load_preferences

        prefs = load_preferences()
    except Exception:
        return False
    airplane = prefs.get("airplane_mode", {})
    return bool(airplane.get("enabled")) if isinstance(airplane, dict) else bool(airplane)


def _default_local_model_dir() -> Path:
    return get_cache_dir() / "models" / local_model_dir_name(get_local_asr_model_name())


def _default_faster_whisper_model_dir() -> Path:
    return get_cache_dir() / "models" / local_model_dir_name(get_local_fast_whisper_model_name())


def _openvino_device_status_path() -> Path:
    return get_cache_dir() / "extraction" / OPENVINO_DEVICE_STATUS_FILENAME


def _record_openvino_device_status(
    *,
    device: str,
    model_dir: str,
    success: bool,
    error: str | None = None,
    device_failures: dict[str, dict[str, Any]] | None = None,
) -> None:
    payload = {
        "success": success,
        "device": device,
        "model_dir": str(model_dir),
        "timestamp": time.time(),
    }
    if error:
        payload["error"] = error
    if device_failures:
        payload["device_failures"] = device_failures
    try:
        path = _openvino_device_status_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass


def get_last_openvino_device_status() -> dict[str, Any] | None:
    try:
        raw = json.loads(_openvino_device_status_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _unavailable(error: str) -> TranscriptResult:
    return TranscriptResult(
        success=False,
        transcript="",
        method="unavailable",
        cloud_used=False,
        needs_review=True,
        error=error,
    )


def _stringify_transcript(result: Any) -> str:
    if isinstance(result, str):
        return result.strip()
    text = getattr(result, "text", None)
    if isinstance(text, str):
        return text.strip()
    return str(result).strip()


def _confidence_from_probability(probability: float | None) -> str:
    if probability is None:
        return "low"
    if probability >= 0.85:
        return "high"
    if probability >= 0.6:
        return "medium"
    return "low"
