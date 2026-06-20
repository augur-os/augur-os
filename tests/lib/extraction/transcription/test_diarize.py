"""Tests for the portable (torch-free) parts of the diarization module.

The pyannote pipeline itself needs torch + gated models and is not exercised
here; these cover the join logic, availability gating, config templating, and
the substring-naming invariant that the backend routing depends on.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from src.lib.extraction.transcription import diarize
from src.lib.extraction.transcription.diarize import (
    EMBEDDING_DIR,
    SpeakerTurn,
    assign_speakers,
    models_dir,
)
from src.lib.extraction.transcription.types import Segment


def test_embedding_dir_preserves_pyannote_substring():
    """pyannote routes to the torch backend only when the path says 'pyannote'.

    Dropping the prefix silently selects the ONNX backend and breaks
    diarization (mila PR #14). Guard the invariant in code.
    """
    assert "pyannote" in EMBEDDING_DIR
    assert EMBEDDING_DIR == "pyannote-wespeaker-voxceleb-resnet34-LM"


def test_assign_speakers_labels_by_max_overlap():
    segments = [
        Segment(start=0.0, end=2.0, text="Hi there"),
        Segment(start=2.0, end=5.0, text="How are you"),
        Segment(start=5.0, end=6.0, text="Good"),
    ]
    turns = [
        SpeakerTurn(start=0.0, end=2.1, speaker="SPEAKER_00"),
        SpeakerTurn(start=2.1, end=6.0, speaker="SPEAKER_01"),
    ]
    labeled = assign_speakers(segments, turns)

    assert [s.speaker for s in labeled] == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_01"]
    # original text is preserved, only speaker is added
    assert [s.text for s in labeled] == ["Hi there", "How are you", "Good"]


def test_assign_speakers_no_turns_returns_segments_unchanged():
    segments = [Segment(start=0.0, end=1.0, text="solo")]
    out = assign_speakers(segments, [])
    assert out[0].speaker is None
    assert out[0].text == "solo"


def test_assign_speakers_segment_with_no_overlap_keeps_speaker_none():
    segments = [Segment(start=10.0, end=11.0, text="late")]
    turns = [SpeakerTurn(start=0.0, end=2.0, speaker="SPEAKER_00")]
    out = assign_speakers(segments, turns)
    assert out[0].speaker is None


def test_is_available_false_without_models(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_DIARIZATION_MODEL_DIR", str(tmp_path))
    assert diarize.models_present() is False
    assert diarize.is_available() is False


def test_is_available_requires_both_libraries_and_models(tmp_path, monkeypatch):
    # Pretend both model files exist...
    monkeypatch.setenv("AUGUR_DIARIZATION_MODEL_DIR", str(tmp_path))
    (tmp_path / diarize.SEGMENTATION_DIR).mkdir()
    (tmp_path / diarize.SEGMENTATION_DIR / "pytorch_model.bin").write_bytes(b"x")
    (tmp_path / EMBEDDING_DIR).mkdir()
    (tmp_path / EMBEDDING_DIR / "pytorch_model.bin").write_bytes(b"x")
    assert diarize.models_present() is True

    # ...availability still depends on the libraries being importable.
    with patch.object(diarize, "libraries_installed", return_value=False):
        assert diarize.is_available() is False
    with patch.object(diarize, "libraries_installed", return_value=True):
        assert diarize.is_available() is True


def test_models_dir_honors_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_DIARIZATION_MODEL_DIR", str(tmp_path / "custom"))
    assert models_dir() == Path(tmp_path / "custom")


def test_diarize_raises_clear_error_when_models_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_DIARIZATION_MODEL_DIR", str(tmp_path))
    try:
        diarize.diarize(Path("nonexistent.wav"))
    except RuntimeError as exc:
        assert "Diarization models not found" in str(exc)
        assert "diarize_setup" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError for missing models")
