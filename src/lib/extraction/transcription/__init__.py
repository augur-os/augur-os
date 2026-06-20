"""Transcription facade. Default provider: whisper-cpp."""

from __future__ import annotations

from collections.abc import Callable
import importlib.util
from pathlib import Path
import sys
from types import FunctionType

from .types import Segment, Transcript

Provider = Callable[[Path, dict], Transcript]
_PROVIDERS: dict[str, Provider] = {}


def _load_legacy_transcription_module() -> None:
    """Expose the pre-existing local transcription helpers from transcription.py."""
    legacy_path = Path(__file__).resolve().parents[1] / "transcription.py"
    if not legacy_path.exists():
        return
    module_name = "src.lib.extraction._legacy_transcription"
    module = sys.modules.get(module_name)
    if module is None:
        spec = importlib.util.spec_from_file_location(module_name, legacy_path)
        if spec is None or spec.loader is None:
            return
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    for name, value in vars(module).items():
        if name.startswith("__"):
            continue
        if isinstance(value, FunctionType) and getattr(value, "__module__", None) == module_name:
            rebound = FunctionType(
                value.__code__,
                globals(),
                name=value.__name__,
                argdefs=value.__defaults__,
                closure=value.__closure__,
            )
            rebound.__annotations__ = dict(getattr(value, "__annotations__", {}))
            rebound.__kwdefaults__ = getattr(value, "__kwdefaults__", None)
            globals().setdefault(name, rebound)
            continue
        globals().setdefault(name, value)


def register_provider(name: str, fn: Provider) -> None:
    """Register a transcription provider."""
    _PROVIDERS[name] = fn


def transcribe(
    audio_path: Path,
    *,
    provider: str = "whisper-cpp",
    options: dict | None = None,
) -> Transcript:
    """Dispatch transcription to the named provider."""
    if provider not in _PROVIDERS:
        if provider == "whisper-cpp":
            from . import whisper_cpp  # noqa: F401
        else:
            raise ValueError(f"Unknown transcription provider: {provider}")
    return _PROVIDERS[provider](audio_path, options or {})


_load_legacy_transcription_module()

__all__ = [
    "Segment",
    "Transcript",
    "register_provider",
    "transcribe",
    "AUDIO_EXTENSIONS",
    "AUGUR_LOCAL_WHISPER_MODEL_ENV",
    "TranscriptResult",
    "can_transcribe_audio",
    "transcribe_audio",
]
