from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
MCP_DIR = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "document-extractor" / "scripts" / "mcp"


def _load_tools_extract():
    package_name = "document_extractor_audio_test_mcp"
    if package_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            package_name,
            MCP_DIR / "__init__.py",
            submodule_search_locations=[str(MCP_DIR)],
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[package_name] = module
        spec.loader.exec_module(module)
    return importlib.import_module(f"{package_name}.tools_extract")


def test_extract_audio_impl_returns_transcript_payload(tmp_path):
    from src.lib.extraction.transcription.types import Segment, Transcript

    fake_path = tmp_path / "x.m4a"
    fake_path.write_bytes(b"\x00\x00")
    fake_transcript = Transcript(
        text="Hello world.",
        segments=[Segment(start=0.0, end=2.0, text="Hello world.", speaker=None)],
        duration_seconds=2.0,
        language="en",
        provider="whisper-cpp",
        provider_version="1.x",
    )

    mod = _load_tools_extract()
    with patch("src.lib.extraction.transcription.transcribe", return_value=fake_transcript):
        result = mod.extract_audio_impl(str(fake_path))

    assert result["success"] is True
    assert result["text"] == "Hello world."
    assert result["duration_seconds"] == 2.0
    assert result["provider"] == "whisper-cpp"
    assert result["speaker_count"] == 0


def test_extract_audio_impl_falls_back_to_local_transcription(tmp_path):
    from src.lib.extraction.transcription import TranscriptResult

    fake_path = tmp_path / "x.m4a"
    fake_path.write_bytes(b"\x00\x00")
    fake_result = TranscriptResult(
        success=True,
        transcript="Hello from faster whisper.",
        method="faster-whisper",
        backend="auto",
        duration_s=3.5,
        language="en",
        confidence="medium",
    )

    mod = _load_tools_extract()
    with (
        patch("src.lib.extraction.transcription.transcribe", side_effect=RuntimeError("missing pywhispercpp")),
        patch("src.lib.extraction.transcription.transcribe_audio", return_value=fake_result),
    ):
        result = mod.extract_audio_impl(str(fake_path))

    assert result["success"] is True
    assert result["text"] == "Hello from faster whisper."
    assert result["provider"] == "faster-whisper"
    assert result["provider_version"] == "auto"
    assert result["duration_seconds"] == 3.5


def test_register_extract_audio_returns_json_payload(tmp_path):
    from src.lib.extraction.transcription.types import Segment, Transcript

    fake_path = tmp_path / "x.m4a"
    fake_path.write_bytes(b"\x00\x00")
    fake_transcript = Transcript(
        text="Hello world.",
        segments=[Segment(start=0.0, end=2.0, text="Hello world.", speaker=None)],
        duration_seconds=2.0,
        language="en",
        provider="whisper-cpp",
        provider_version="1.x",
    )
    mod = _load_tools_extract()
    captured = {}

    def fake_tool(*_args, **_kwargs):
        def inner(fn):
            captured["fn"] = fn
            return fn

        return inner

    fake_mcp = MagicMock()
    fake_mcp.tool = fake_tool

    with patch("src.lib.extraction.transcription.transcribe", return_value=fake_transcript):
        mod._register_extract_audio(fake_mcp)
        result = json.loads(captured["fn"](str(fake_path)))

    assert result["success"] is True
    assert result["text"] == "Hello world."
