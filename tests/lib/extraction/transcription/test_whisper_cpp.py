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

    with patch(
        "src.lib.extraction.transcription.whisper_cpp._get_model",
        return_value=fake_model,
    ):
        result = transcribe(
            fake_audio,
            provider="whisper-cpp",
            options={"model": "medium.en", "language": "en"},
        )

    assert isinstance(result, Transcript)
    assert "Hello" in result.text
    assert "world" in result.text
    assert result.language == "en"
    assert result.provider == "whisper-cpp"
    assert result.duration_seconds == pytest.approx(4.0)
    assert len(result.segments) == 2


def test_whisper_cpp_uses_pywhispercpp_centisecond_timestamps(fake_audio):
    class RawSegment:
        def __init__(self, t0, t1, text):
            self.t0 = t0
            self.t1 = t1
            self.text = text

    fake_segments = [
        RawSegment(0, 196, "Hello,"),
        RawSegment(196, 508, "world."),
    ]
    fake_model = MagicMock()
    fake_model.transcribe = MagicMock(return_value=fake_segments)

    with patch(
        "src.lib.extraction.transcription.whisper_cpp._get_model",
        return_value=fake_model,
    ):
        result = transcribe(
            fake_audio,
            provider="whisper-cpp",
            options={"model": "medium.en", "language": "en"},
        )

    assert result.segments[0].start == pytest.approx(0.0)
    assert result.segments[0].end == pytest.approx(1.96)
    assert result.duration_seconds == pytest.approx(5.08)


def test_whisper_cpp_handles_empty_audio(fake_audio):
    fake_model = MagicMock()
    fake_model.transcribe = MagicMock(return_value=[])
    fake_model.model_path = "medium.en"
    with patch(
        "src.lib.extraction.transcription.whisper_cpp._get_model",
        return_value=fake_model,
    ):
        result = transcribe(
            fake_audio,
            provider="whisper-cpp",
            options={"model": "medium.en", "language": "en"},
        )
    assert result.text == ""
    assert result.duration_seconds == 0.0
    assert len(result.segments) == 0


def test_select_model_upgrades_english_only_for_non_english_language():
    from src.lib.extraction.transcription import whisper_cpp
    from src.lib.extraction.transcription.whisper_cpp import _select_model

    # English-only model + non-English language -> upgrade to multilingual.
    assert _select_model("tiny.en", "es") == "large-v3-turbo"
    # Hebrew with no ivrit bin installed falls back to the multilingual model.
    # Mock the bin-presence check so this test is hermetic regardless of whether
    # the ivrit ggml bin happens to be installed on the host machine.
    with patch.object(whisper_cpp, "_model_bin_path") as bin_path:
        bin_path.return_value = MagicMock(is_file=lambda: False)
        assert _select_model("medium.en", "he") == "large-v3-turbo"
    # English (or unset/auto) keeps the requested model.
    assert _select_model("medium.en", "en") == "medium.en"
    assert _select_model("medium.en", "") == "medium.en"
    assert _select_model("medium.en", "auto") == "medium.en"
    # An already-multilingual model is never downgraded.
    assert _select_model("large-v3-turbo", "es") == "large-v3-turbo"


def test_select_model_prefers_ivrit_for_hebrew_when_installed():
    """Hebrew picks the ivrit.ai large-v3 finetune when its ggml bin exists."""
    from src.lib.extraction.transcription import whisper_cpp

    with patch.object(whisper_cpp, "_model_bin_path") as bin_path:
        bin_path.return_value = MagicMock(is_file=lambda: True)
        for lang in ("he", "hebrew", "iw"):
            assert whisper_cpp._select_model("medium.en", lang) == "ivrit-ai-whisper-large-v3"


def test_parse_cli_json_maps_offsets_and_language():
    from src.lib.extraction.transcription.whisper_cpp import _parse_cli_json

    data = {
        "result": {"language": "he"},
        "transcription": [
            {"offsets": {"from": 0, "to": 5840}, "text": " Okay,"},
            {"offsets": {"from": 5840, "to": 9000}, "text": " world."},
        ],
    }
    transcript = _parse_cli_json(data, requested_language="he", model_name="large-v3-turbo")

    assert transcript.provider == "whisper-cpp"
    assert transcript.language == "he"  # detected language from result wins
    assert transcript.text == "Okay, world."
    assert transcript.segments[0].start == pytest.approx(0.0)
    assert transcript.segments[0].end == pytest.approx(5.84)
    assert transcript.duration_seconds == pytest.approx(9.0)
    assert transcript.extra["backend"] == "whisper-cli"
    assert transcript.extra["model"] == "large-v3-turbo"


def test_whisper_cpp_falls_back_to_cli_when_binding_missing(fake_audio, tmp_path):
    """When pywhispercpp is unavailable, transcription routes through whisper-cli."""
    model_bin = tmp_path / "ggml-medium.en.bin"
    model_bin.write_bytes(b"model")
    sample = {
        "result": {"language": "en"},
        "transcription": [
            {"offsets": {"from": 0, "to": 2000}, "text": " Hello,"},
            {"offsets": {"from": 2000, "to": 4000}, "text": " world."},
        ],
    }

    with (
        patch(
            "src.lib.extraction.transcription.whisper_cpp._get_model",
            side_effect=RuntimeError("pywhispercpp is required"),
        ),
        patch(
            "src.lib.extraction.transcription.whisper_cpp.shutil.which",
            return_value="/usr/local/bin/whisper-cli",
        ),
        patch(
            "src.lib.extraction.transcription.whisper_cpp._model_bin_path",
            return_value=model_bin,
        ),
        patch(
            "src.lib.extraction.transcription.whisper_cpp._run_cli",
            return_value=sample,
        ),
    ):
        result = transcribe(
            fake_audio,
            provider="whisper-cpp",
            options={"model": "medium.en", "language": "en"},
        )

    assert isinstance(result, Transcript)
    assert result.text == "Hello, world."
    assert result.provider == "whisper-cpp"
    assert result.extra["backend"] == "whisper-cli"
    assert result.duration_seconds == pytest.approx(4.0)


def test_speaker_labels_overlay_diarization_when_available(fake_audio):
    """speaker_labels=True overlays pyannote turns onto the whisper segments."""
    from src.lib.extraction.transcription import whisper_cpp
    from src.lib.extraction.transcription.diarize import SpeakerTurn

    fake_segments = [
        MagicMock(start=0.0, end=2.0, text="Hi"),
        MagicMock(start=2.0, end=4.0, text="Bye"),
    ]
    fake_model = MagicMock()
    fake_model.transcribe = MagicMock(return_value=fake_segments)

    turns = [
        SpeakerTurn(0.0, 2.0, "SPEAKER_00"),
        SpeakerTurn(2.0, 4.0, "SPEAKER_01"),
    ]

    with (
        patch.object(whisper_cpp, "_get_model", return_value=fake_model),
        patch("src.lib.extraction.transcription.diarize.is_available", return_value=True),
        patch("src.lib.extraction.transcription.diarize.diarize", return_value=turns),
        patch.object(whisper_cpp, "_to_wav_16k", return_value=fake_audio),
    ):
        result = transcribe(
            fake_audio,
            provider="whisper-cpp",
            options={"model": "medium.en", "language": "en", "speaker_labels": True},
        )

    assert [s.speaker for s in result.segments] == ["SPEAKER_00", "SPEAKER_01"]
    assert result.extra.get("diarized") is True
    assert result.extra.get("diarization_turns") == 2
    assert result.speaker_count() == 2


def test_speaker_labels_noop_when_diarization_unavailable(fake_audio):
    """Without the diarization extra/models, transcription is unchanged."""
    from src.lib.extraction.transcription import whisper_cpp

    # Realistic raw segment: no diarization-bearing ``speaker`` attribute.
    raw = MagicMock(spec=["start", "end", "text"])
    raw.start, raw.end, raw.text = 0.0, 1.0, "solo"
    fake_model = MagicMock()
    fake_model.transcribe = MagicMock(return_value=[raw])

    with (
        patch.object(whisper_cpp, "_get_model", return_value=fake_model),
        patch("src.lib.extraction.transcription.diarize.is_available", return_value=False),
    ):
        result = transcribe(
            fake_audio,
            provider="whisper-cpp",
            options={"model": "medium.en", "language": "en", "speaker_labels": True},
        )

    assert result.segments[0].speaker is None
    assert "diarized" not in result.extra


@pytest.mark.slow
def test_whisper_cpp_against_real_short_clip():
    fixture = Path(__file__).parent / "fixtures" / "hello.wav"
    if not fixture.exists():
        pytest.skip("hello.wav fixture not bundled; opt-in for real-call validation")
    result = transcribe(fixture, provider="whisper-cpp", options={"model": "tiny.en", "language": "en"})
    assert isinstance(result, Transcript)
    assert len(result.text.strip()) > 0
