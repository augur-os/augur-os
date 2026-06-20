from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
CLASSIFIER_PATH = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "audio-ingest" / "scripts" / "classifier.py"
FIXTURES = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "audio-ingest" / "augur" / "tests" / "fixtures"


def _load_classifier():
    spec = importlib.util.spec_from_file_location("audio_ingest_classifier", CLASSIFIER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["audio_ingest_classifier"] = module
    spec.loader.exec_module(module)
    return module


def test_classify_voice_memo_heuristic():
    c = _load_classifier()
    result = c.classify_heuristic(
        text=(FIXTURES / "voice_memo_sample.txt").read_text(encoding="utf-8"),
        segments=[],
        duration_seconds=30.0,
        speaker_count=0,
    )
    assert result["type"] == "voice-memo"
    assert result["confidence"] >= 0.9
    assert "reasoning" in result


def test_classify_meeting_heuristic():
    c = _load_classifier()
    result = c.classify_heuristic(
        text=(FIXTURES / "meeting_sample.txt").read_text(encoding="utf-8"),
        segments=[],
        duration_seconds=1800.0,
        speaker_count=3,
    )
    assert result["type"] == "meeting"
    assert result["confidence"] >= 0.9


def test_short_dialogue_questions_classify_as_meeting_without_diarization():
    c = _load_classifier()
    result = c.classify_heuristic(
        text=(
            "I got a new laptop yesterday. You got a new laptop? "
            "Why didn't you get a desktop? Isn't the keyboard too small to use? "
            "I think big keyboards are easier. Aren't laptops more expensive? "
            "That's true, but I can use my laptop anywhere."
        ),
        segments=[],
        duration_seconds=162.0,
        speaker_count=0,
    )
    assert result["type"] == "meeting"
    assert result["confidence"] >= 0.9
    assert "dialogue_questions" in result["reasoning"]


def test_low_confidence_short_circuits_to_llm_dispatch():
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
