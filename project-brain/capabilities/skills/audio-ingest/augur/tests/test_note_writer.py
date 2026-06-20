from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
WRITER_PATH = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "audio-ingest" / "scripts" / "note_writer.py"


def _load_writer():
    spec = importlib.util.spec_from_file_location("audio_ingest_writer", WRITER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["audio_ingest_writer"] = module
    spec.loader.exec_module(module)
    return module


def test_writes_voice_memo_with_correct_frontmatter(tmp_path):
    w = _load_writer()
    out = w.write_audio_note(
        notes_dir=tmp_path,
        audio_path=Path("/tmp/voice-monday.m4a"),
        note_type="voice-memo",
        title="Monday Recap",
        transcript_text="I keep coming back to this idea about RRF.",
        segments=[],
        duration_seconds=72.0,
        provider="whisper-cpp",
        provider_version="1.5.4",
        attendee_slugs=[],
    )
    body = out.read_text(encoding="utf-8")
    assert "x-augur-note-type: voice-memo" in body
    assert "duration_seconds: 72.0" in body
    assert "provider: whisper-cpp" in body
    assert "transcript_status: complete" in body
    assert "monday-recap" in out.name.lower()


def test_copies_existing_audio_source_into_vault(tmp_path):
    w = _load_writer()
    notes_dir = tmp_path / "vault" / "notes"
    source_dir = tmp_path / "Downloads"
    source_dir.mkdir()
    source = source_dir / "voice-monday.m4a"
    source.write_bytes(b"audio")

    out = w.write_audio_note(
        notes_dir=notes_dir,
        audio_path=source,
        note_type="voice-memo",
        title="Monday Recap",
        transcript_text="I keep coming back to this idea about RRF.",
        segments=[],
        duration_seconds=72.0,
        provider="whisper-cpp",
        provider_version="1.5.4",
        attendee_slugs=[],
    )

    body = out.read_text(encoding="utf-8")
    stored = tmp_path / "vault" / "voice-memos" / f"{date.today().isoformat()}-monday-recap.m4a"
    assert stored.exists()
    assert source.exists()
    assert f"audio_path: {stored}" in body


def test_consumes_existing_audio_source_when_requested(tmp_path):
    w = _load_writer()
    notes_dir = tmp_path / "vault" / "notes"
    source_dir = tmp_path / "Downloads"
    source_dir.mkdir()
    source = source_dir / "planning.mp3"
    source.write_bytes(b"audio")

    out = w.write_audio_note(
        notes_dir=notes_dir,
        audio_path=source,
        note_type="meeting",
        title="Planning",
        transcript_text="What should we do? We should write the test.",
        segments=[],
        duration_seconds=120.0,
        provider="whisper-cpp",
        provider_version="1.5.4",
        attendee_slugs=[],
        consume_source=True,
    )

    body = out.read_text(encoding="utf-8")
    stored = tmp_path / "vault" / "meetings" / f"{date.today().isoformat()}-planning.mp3"
    assert stored.exists()
    assert not source.exists()
    assert f"audio_path: {stored}" in body


def test_writes_meeting_with_attendee_slugs(tmp_path):
    w = _load_writer()
    out = w.write_audio_note(
        notes_dir=tmp_path,
        audio_path=Path("/tmp/q2-planning.mp4"),
        note_type="meeting",
        title="Q2 Planning",
        transcript_text="[Sasha] start ... [Priya] revenue up.",
        segments=[],
        duration_seconds=2280.0,
        provider="whisper-cpp",
        provider_version="1.5.4",
        attendee_slugs=["sasha-chen", "priya-rao"],
    )
    body = out.read_text(encoding="utf-8")
    assert "x-augur-note-type: meeting" in body
    assert "attendee_count: 2" in body
    assert "sasha-chen" in body
    assert "priya-rao" in body


def test_writes_meeting_with_unresolved_attendee_count_hint(tmp_path):
    w = _load_writer()
    out = w.write_audio_note(
        notes_dir=tmp_path,
        audio_path=Path("/tmp/interview.mp3"),
        note_type="meeting",
        title="Interview",
        transcript_text="What should we do? We should write the test. How do we know it worked?",
        segments=[],
        duration_seconds=162.0,
        provider="whisper-cpp",
        provider_version="1.5.4",
        attendee_slugs=[],
        attendee_count_hint=2,
    )
    body = out.read_text(encoding="utf-8")
    assert "x-augur-note-type: meeting" in body
    assert "attendee_count: 2" in body
    assert "attendee_slugs:" not in body
    assert "## Attendees" not in body


def test_idempotency_keeps_note_type_overrides_distinct(tmp_path):
    w = _load_writer()
    meeting = w.write_audio_note(
        notes_dir=tmp_path,
        audio_path=Path("/tmp/shared-audio.mp3"),
        note_type="meeting",
        title="Shared Audio",
        transcript_text="Bill asks a question. Robert answers it.",
        segments=[],
        duration_seconds=162.0,
        provider="whisper-cpp",
        provider_version="1.5.4",
        attendee_slugs=[],
    )
    memo = w.write_audio_note(
        notes_dir=tmp_path,
        audio_path=Path("/tmp/shared-audio.mp3"),
        note_type="voice-memo",
        title="Shared Audio",
        transcript_text="Bill asks a question. Robert answers it.",
        segments=[],
        duration_seconds=162.0,
        provider="whisper-cpp",
        provider_version="1.5.4",
        attendee_slugs=[],
    )
    assert memo != meeting
    assert "x-augur-note-type: voice-memo" in memo.read_text(encoding="utf-8")
    assert "x-augur-note-type: meeting" in meeting.read_text(encoding="utf-8")


def test_idempotent_meeting_write_repairs_attendee_count(tmp_path):
    w = _load_writer()
    first = w.write_audio_note(
        notes_dir=tmp_path,
        audio_path=Path("/tmp/interview.mp3"),
        note_type="meeting",
        title="Interview",
        transcript_text="What should we do? We should write the test. How do we know it worked?",
        segments=[],
        duration_seconds=162.0,
        provider="whisper-cpp",
        provider_version="1.5.4",
        attendee_slugs=[],
    )
    assert "attendee_count: 0" in first.read_text(encoding="utf-8")

    second = w.write_audio_note(
        notes_dir=tmp_path,
        audio_path=Path("/tmp/interview.mp3"),
        note_type="meeting",
        title="Interview",
        transcript_text="What should we do? We should write the test. How do we know it worked?",
        segments=[],
        duration_seconds=162.0,
        provider="whisper-cpp",
        provider_version="1.5.4",
        attendee_slugs=[],
        attendee_count_hint=2,
    )

    assert second == first
    assert "attendee_count: 2" in second.read_text(encoding="utf-8")


def test_domains_layout_stores_audio_under_machine_dir(tmp_path):
    """Domains vault: audio binaries land in _augur/voice-memos, not a rogue
    top-level dir; the note itself lands in inbox/ (the capture dir)."""
    w = _load_writer()
    from src.lib.brain_layout import brain_layout

    brain_layout.cache_clear()
    try:
        vault = tmp_path / "vault"
        (vault / "inbox").mkdir(parents=True)
        (vault / "BRAIN.yaml").write_text(
            "schema_version: 1\nid: t\ntype: personal\nlayout: domains\n",
            encoding="utf-8",
        )
        source_dir = tmp_path / "Downloads"
        source_dir.mkdir()
        source = source_dir / "voice-monday.m4a"
        source.write_bytes(b"audio")

        out = w.write_audio_note(
            notes_dir=vault / "inbox",
            audio_path=source,
            note_type="voice-memo",
            title="Monday Recap",
            transcript_text="I keep coming back to this idea about RRF.",
            segments=[],
            duration_seconds=72.0,
            provider="whisper-cpp",
            provider_version="1.5.4",
            attendee_slugs=[],
            vault_dir=vault,
        )

        stored = vault / "_augur" / "voice-memos" / f"{date.today().isoformat()}-monday-recap.m4a"
        assert stored.exists()
        assert not (vault / "voice-memos").exists(), "no rogue top-level voice-memos dir"
        assert f"audio_path: {stored}" in out.read_text(encoding="utf-8")
        assert out.parent == vault / "inbox"

        # Fallback (no vault_dir): notes_dir.parent IS the vault root in
        # domains layout, so the probe resolves the same machine dir.
        assert (
            w._audio_storage_dir(vault / "inbox", "voice-memo")
            == vault / "_augur" / "voice-memos"
        )
    finally:
        brain_layout.cache_clear()


def test_slug_derivation_handles_unicode_and_punctuation(tmp_path):
    w = _load_writer()
    out = w.write_audio_note(
        notes_dir=tmp_path,
        audio_path=Path("/tmp/x.m4a"),
        note_type="voice-memo",
        title="Cafe Tuesday's *plan*",
        transcript_text="hi",
        segments=[],
        duration_seconds=10.0,
        provider="whisper-cpp",
        provider_version="x",
        attendee_slugs=[],
    )
    assert "cafe" in out.name.lower()
    assert "tuesday" in out.name.lower()


def test_meeting_body_renders_diarization_speaker_labels(tmp_path):
    """Diarized meeting segments surface as [SPEAKER_XX] lines in the body."""
    w = _load_writer()
    out = w.write_audio_note(
        notes_dir=tmp_path,
        audio_path=Path("/tmp/standup.m4a"),
        note_type="meeting",
        title="Standup",
        transcript_text="Morning all Lets begin",
        segments=[
            {"start": 0.0, "end": 2.0, "text": "Morning all", "speaker": "SPEAKER_00"},
            {"start": 2.0, "end": 4.0, "text": "Lets begin", "speaker": "SPEAKER_01"},
        ],
        duration_seconds=4.0,
        provider="whisper-cpp",
        provider_version="1.5.4",
        attendee_slugs=[],
    )
    body = out.read_text(encoding="utf-8")
    assert "[SPEAKER_00] Morning all" in body
    assert "[SPEAKER_01] Lets begin" in body


def test_non_diarized_body_stays_flat_transcript(tmp_path):
    """Without speaker labels the body keeps the flat transcript text."""
    w = _load_writer()
    out = w.write_audio_note(
        notes_dir=tmp_path,
        audio_path=Path("/tmp/memo.m4a"),
        note_type="voice-memo",
        title="Memo",
        transcript_text="just one speaker talking",
        segments=[{"start": 0.0, "end": 2.0, "text": "just one speaker talking", "speaker": None}],
        duration_seconds=2.0,
        provider="whisper-cpp",
        provider_version="1.5.4",
        attendee_slugs=[],
    )
    body = out.read_text(encoding="utf-8")
    assert "just one speaker talking" in body
    assert "[SPEAKER" not in body
