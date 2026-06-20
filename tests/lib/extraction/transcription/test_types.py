from __future__ import annotations

from src.lib.extraction.transcription.types import Segment, Transcript


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
