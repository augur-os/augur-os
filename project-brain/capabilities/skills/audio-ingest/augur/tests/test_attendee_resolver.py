from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
RESOLVER_PATH = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "audio-ingest" / "scripts" / "attendee_resolver.py"


def _load_resolver():
    spec = importlib.util.spec_from_file_location("audio_ingest_resolver", RESOLVER_PATH)
    assert spec is not None and spec.loader is not None
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


def test_infers_attendee_count_from_segment_speakers():
    r = _load_resolver()
    count = r.infer_attendee_count(
        text="Flat transcript",
        segments=[
            {"speaker": "Sasha", "text": "Hi."},
            {"speaker": "Priya", "text": "Hello."},
            {"speaker": "Sasha", "text": "Next item."},
        ],
        attendee_slugs=[],
        duration_seconds=120.0,
    )
    assert count == 2


def test_infers_two_attendees_from_unlabeled_dialogue_questions():
    r = _load_resolver()
    count = r.infer_attendee_count(
        text=(
            "What should we work on next? We should finish the notes flow. "
            "How will you verify it? I will use the real vault. "
            "When do you need the branch? Today."
        ),
        segments=[],
        attendee_slugs=[],
        duration_seconds=162.0,
    )
    assert count == 2


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
