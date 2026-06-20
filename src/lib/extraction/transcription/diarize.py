"""Speaker diarization via pyannote.audio (optional ``diarization`` extra).

Ported from `island-io/mila <https://github.com/island-io/mila>`_ (Apache-2.0):
the offline pyannote pipeline configuration, the two monkey-patches required to
run pyannote 3.x on recent torch/speechbrain, and the path-substring model
naming that routes the embedding to the torch backend. See NOTICE for
attribution.

This module is import-safe without torch/pyannote installed — every heavy
import is deferred. ``is_available()`` gates callers; the whisper provider only
runs diarization when both the libraries and the bundled models are present.

Models are not redistributed. They are gated on Hugging Face and downloaded
once via :mod:`src.lib.extraction.transcription.diarize_setup`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import os
import tempfile
import types
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from src.config.paths import get_cache_dir
from src.logging import get_entity_logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .types import Segment

logger = get_entity_logger("lib.extraction.transcription.diarize")

# Local directory names for the bundled models. The embedding directory MUST
# contain the substring ``pyannote`` — pyannote routes the embedding to the
# torch backend when the path contains ``pyannote`` and to the ONNX backend
# otherwise. Dropping the prefix silently selects the wrong backend and breaks
# diarization (mila PR #14 / .claude/rules/python-subprocess.md).
SEGMENTATION_DIR = "segmentation-3.0"
EMBEDDING_DIR = "pyannote-wespeaker-voxceleb-resnet34-LM"

_MODEL_DIR_ENV = "AUGUR_DIARIZATION_MODEL_DIR"

# Mirrors mila's bundled DiarizationModels/config.yaml. ``__MODELS_DIR__`` is
# substituted with the absolute model directory at load time.
_CONFIG_TEMPLATE = """version: 3.1.0

pipeline:
  name: pyannote.audio.pipelines.SpeakerDiarization
  params:
    clustering: AgglomerativeClustering
    embedding: __MODELS_DIR__/pyannote-wespeaker-voxceleb-resnet34-LM/pytorch_model.bin
    embedding_batch_size: 32
    embedding_exclude_overlap: true
    segmentation: __MODELS_DIR__/segmentation-3.0/pytorch_model.bin
    segmentation_batch_size: 32

params:
  clustering:
    method: centroid
    min_cluster_size: 12
    threshold: 0.7045654963945799
  segmentation:
    min_duration_off: 0.0
"""


@dataclass(frozen=True)
class SpeakerTurn:
    """One diarized speaker turn: ``speaker`` is active in ``[start, end)``."""

    start: float
    end: float
    speaker: str


def models_dir() -> Path:
    """Directory holding the bundled segmentation + embedding models."""
    override = os.environ.get(_MODEL_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return get_cache_dir() / "diarization"


def models_present() -> bool:
    """True when both required model weight files exist on disk."""
    base = models_dir()
    return (base / SEGMENTATION_DIR / "pytorch_model.bin").is_file() and (
        base / EMBEDDING_DIR / "pytorch_model.bin"
    ).is_file()


def libraries_installed() -> bool:
    """True when the optional ``diarization`` extra is importable."""
    import importlib.util

    return importlib.util.find_spec("torch") is not None and importlib.util.find_spec("pyannote.audio") is not None


def is_available() -> bool:
    """True when diarization can actually run (libraries + models present)."""
    return libraries_installed() and models_present()


def _apply_compat_patches() -> None:
    """Apply the pyannote 3.x compatibility patches (ported from mila).

    Required as of pyannote.audio 3.x + torch >= 2.6 + recent speechbrain:
    1. ``torch.load`` defaults to ``weights_only=True`` since torch 2.6, which
       rejects the pickled pyannote checkpoints.
    2. speechbrain's ``LazyModule`` raises ``ImportError`` when the lightning
       stack inspects optional modules; swallow it with a stub module.
    Remove if a future pyannote/speechbrain release fixes these.
    """
    try:
        import speechbrain.utils.importutils as _sbiu  # type: ignore

        _orig_ensure = _sbiu.LazyModule.ensure_module

        def _safe_ensure(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            try:
                return _orig_ensure(self, *args, **kwargs)
            except ImportError:
                self.lazy_module = types.ModuleType(self.target)
                return self.lazy_module

        _sbiu.LazyModule.ensure_module = _safe_ensure
    except Exception:  # speechbrain optional / API drift — non-fatal
        logger.debug("speechbrain LazyModule patch skipped", exc_info=True)

    import torch  # type: ignore

    _orig_torch_load = torch.load

    def _patched_torch_load(*args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs["weights_only"] = False
        return _orig_torch_load(*args, **kwargs)

    torch.load = _patched_torch_load


_PIPELINE = None  # cached pyannote Pipeline (lazy, process-lifetime)


def _get_pipeline():  # type: ignore[no-untyped-def]
    """Build (once) and return the pyannote SpeakerDiarization pipeline."""
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE

    _apply_compat_patches()

    import torch  # type: ignore
    from pyannote.audio import Pipeline  # type: ignore

    base = models_dir()
    config_text = _CONFIG_TEMPLATE.replace("__MODELS_DIR__", str(base))
    tmp = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
    try:
        tmp.write(config_text)
        tmp.close()
        pipeline = Pipeline.from_pretrained(tmp.name)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    if pipeline is None:
        raise RuntimeError(
            "pyannote returned no pipeline — the bundled diarization models " f"under {base} are missing or corrupt."
        )

    # Prefer Metal (MPS) on Apple Silicon; CPU everywhere else.
    try:
        if torch.backends.mps.is_available():
            pipeline.to(torch.device("mps"))
            logger.debug("diarization pipeline on MPS")
    except Exception:  # MPS probe can throw on odd torch builds — stay on CPU
        logger.debug("MPS unavailable, diarization on CPU", exc_info=True)

    _PIPELINE = pipeline
    return pipeline


def diarize(audio_path: Path) -> list[SpeakerTurn]:
    """Diarize a 16 kHz mono WAV into time-ordered speaker turns.

    Raises ``RuntimeError`` when the models are not installed — callers that
    want best-effort behaviour should gate on :func:`is_available` first.
    """
    if not models_present():
        raise RuntimeError(
            f"Diarization models not found under {models_dir()}. Run "
            "`uv run python -m src.lib.extraction.transcription.diarize_setup` "
            "with a Hugging Face token that has accepted the pyannote model "
            "licenses (pyannote/segmentation-3.0 and "
            "pyannote/wespeaker-voxceleb-resnet34-LM)."
        )

    pipeline = _get_pipeline()
    annotation = pipeline(str(audio_path))
    turns = [
        SpeakerTurn(float(segment.start), float(segment.end), str(speaker))
        for segment, _, speaker in annotation.itertracks(yield_label=True)
    ]
    turns.sort(key=lambda turn: turn.start)
    return turns


def assign_speakers(segments: Sequence["Segment"], turns: Sequence[SpeakerTurn]) -> list["Segment"]:
    """Label each transcript segment with its max-overlap diarization speaker.

    Pure function — no torch. A segment with no overlapping turn keeps its
    existing ``speaker`` (usually ``None``). This is the join between the
    whisper segment timeline and the pyannote speaker timeline.
    """
    if not turns:
        return list(segments)

    labeled: list["Segment"] = []
    for seg in segments:
        best_speaker: str | None = None
        best_overlap = 0.0
        for turn in turns:
            overlap = min(seg.end, turn.end) - max(seg.start, turn.start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = turn.speaker
        labeled.append(replace(seg, speaker=best_speaker) if best_speaker else seg)
    return labeled
