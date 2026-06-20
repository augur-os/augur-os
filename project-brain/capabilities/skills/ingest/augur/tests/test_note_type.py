"""Tests for note_type pure-logic helpers."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
NOTE_TYPE_PATH = (
    PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "ingest" / "scripts" / "note_type.py"
)


def _load_note_type():
    spec = importlib.util.spec_from_file_location("ingest_note_type", NOTE_TYPE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_note_type"] = module
    spec.loader.exec_module(module)
    return module


def test_detect_url():
    nt = _load_note_type()
    assert nt.detect_note_type_from_arg("https://hbr.org/leverage") == "url"
    assert nt.detect_note_type_from_arg("http://example.com/x") == "url"


def test_detect_file_pdf():
    nt = _load_note_type()
    assert nt.detect_note_type_from_arg("/tmp/report.pdf") == "file"


def test_detect_existing_file_pdf(tmp_path):
    nt = _load_note_type()
    report = tmp_path / "report.pdf"
    report.write_bytes(b"%PDF-1.7\n")
    assert nt.detect_note_type_from_arg(str(report)) == "file"


def test_detect_audio_m4a(tmp_path):
    nt = _load_note_type()
    voice = tmp_path / "voice.m4a"
    voice.write_bytes(b"audio")
    assert nt.detect_note_type_from_arg(str(voice)) == "audio"


def test_detect_image_png(tmp_path):
    nt = _load_note_type()
    image = tmp_path / "whiteboard.png"
    image.write_bytes(b"png")
    assert nt.detect_note_type_from_arg(str(image)) == "image"


def test_detect_thought_freetext():
    nt = _load_note_type()
    assert (
        nt.detect_note_type_from_arg(
            "I think RRF works because failures are orthogonal"
        )
        == "thought"
    )


def test_detect_folder(tmp_path):
    nt = _load_note_type()
    (tmp_path / "x").mkdir()
    assert nt.detect_note_type_from_arg(str(tmp_path / "x")) == "folder"


def test_valid_types_are_complete():
    nt = _load_note_type()
    assert set(nt.VALID_NOTE_TYPES) == {
        "url",
        "file",
        "thought",
        "voice-memo",
        "meeting",
        "image",
        "prompt",
        "folder",
        "audio",
    }
