from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
MCP_DIR = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "audio-ingest" / "scripts" / "mcp"
SHARED_VAULT_DIR = PROJECT_ROOT / "project-brain"
if str(SHARED_VAULT_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_VAULT_DIR))

from src.lib.ingest.note_index_refresh import NoteBrowseIndexRefresh


def _load_tools():
    package_name = "audio_ingest_test_mcp"
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
    return importlib.import_module(f"{package_name}.tools_audio")


def _capture_tools(mod):
    captured = {}
    fake_mcp = MagicMock()

    def fake_tool(*, name):
        def wrap(fn):
            captured[name] = fn
            return fn

        return wrap

    fake_mcp.tool = fake_tool
    mod.register(fake_mcp)
    return captured


def _stub_browse_refresh(monkeypatch, mod, expected_vault_dir):
    refresh_calls = []

    def fake_refresh(*, vault_dir):
        refresh_calls.append(vault_dir)
        assert vault_dir == expected_vault_dir
        return NoteBrowseIndexRefresh(success=True, count=1)

    monkeypatch.setattr(mod, "refresh_notes_browse_index", fake_refresh)
    return refresh_calls


def test_audio_classify_heuristic_short_circuits_voice():
    mod = _load_tools()
    tools = _capture_tools(mod)
    result = tools["audio-classify"](
        transcript_text="I think about RRF. I keep coming back to it. I might write it up.",
        duration_seconds=42.0,
        speaker_count=0,
    )
    assert result["success"] is True
    assert result["type"] == "voice-memo"


def test_audio_classify_heuristic_short_circuits_meeting():
    mod = _load_tools()
    tools = _capture_tools(mod)
    result = tools["audio-classify"](
        transcript_text="[Sasha] hi.\n[Priya] hello.\n[Jay] yo.",
        duration_seconds=1800.0,
        speaker_count=3,
    )
    assert result["success"] is True
    assert result["type"] == "meeting"


def test_audio_classify_low_confidence_returns_needs_llm():
    mod = _load_tools()
    tools = _capture_tools(mod)
    result = tools["audio-classify"](
        transcript_text="ok yes",
        duration_seconds=10.0,
        speaker_count=1,
    )
    assert result.get("needs_llm") is True
    assert result["task"] == "audio-classify"


def test_audio_ingest_write_creates_voice_memo(monkeypatch, tmp_path):
    mod = _load_tools()
    tools = _capture_tools(mod)
    vault = tmp_path / "vault"
    vault.mkdir()
    refresh_calls = _stub_browse_refresh(monkeypatch, mod, vault)
    monkeypatch.setattr(mod, "get_vault_dir", lambda: vault)
    result = tools["audio-ingest-write"](
        audio_path="/tmp/voice.m4a",
        note_type="voice-memo",
        title="Hello",
        transcript_text="Hello world.",
        duration_seconds=2.0,
    )
    assert result["success"] is True
    path = Path(result["path"])
    assert path.exists()
    # Legacy layout: captures land in the vault capture dir (knowledge/notes).
    assert path.is_relative_to(vault / "knowledge" / "notes")
    assert "x-augur-note-type: voice-memo" in path.read_text(encoding="utf-8")
    assert refresh_calls == [vault]


def test_audio_ingest_write_returns_stored_audio_path(monkeypatch, tmp_path):
    mod = _load_tools()
    tools = _capture_tools(mod)
    vault = tmp_path / "vault"
    vault.mkdir()
    source_dir = tmp_path / "Downloads"
    source_dir.mkdir()
    source = source_dir / "voice.m4a"
    source.write_bytes(b"audio")
    _stub_browse_refresh(monkeypatch, mod, vault)
    monkeypatch.setattr(mod, "get_vault_dir", lambda: vault)

    result = tools["audio-ingest-write"](
        audio_path=str(source),
        note_type="voice-memo",
        title="Hello",
        transcript_text="Hello world.",
        duration_seconds=2.0,
        consume_source=True,
    )

    stored = Path(result["audio_path"])
    assert result["success"] is True
    # Audio sits next to the capture dir (notes_dir.parent / voice-memos).
    assert stored.is_relative_to(vault / "knowledge" / "voice-memos")
    assert stored.exists()
    assert not source.exists()
    assert f"audio_path: {stored}" in Path(result["path"]).read_text(encoding="utf-8")


def test_audio_ingest_write_refreshes_browse_index(monkeypatch, tmp_path):
    mod = _load_tools()
    tools = _capture_tools(mod)
    vault = tmp_path / "vault"
    vault.mkdir()
    refresh_calls = []

    def fake_refresh(*, vault_dir):
        refresh_calls.append(vault_dir)
        return NoteBrowseIndexRefresh(success=True, count=4)

    monkeypatch.setattr(mod, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(mod, "refresh_notes_browse_index", fake_refresh)

    result = tools["audio-ingest-write"](
        audio_path="/tmp/voice.m4a",
        note_type="voice-memo",
        title="Hello",
        transcript_text="Hello world.",
        duration_seconds=2.0,
    )

    assert result["success"] is True
    assert result["browse_index"] == {"success": True, "count": 4}
    assert refresh_calls == [vault]
    assert Path(result["path"]).is_relative_to(vault / "knowledge" / "notes")


def test_audio_ingest_write_returns_inferred_meeting_attendee_count(monkeypatch, tmp_path):
    mod = _load_tools()
    tools = _capture_tools(mod)
    vault = tmp_path / "vault"
    vault.mkdir()
    refresh_calls = _stub_browse_refresh(monkeypatch, mod, vault)
    monkeypatch.setattr(mod, "get_vault_dir", lambda: vault)

    result = tools["audio-ingest-write"](
        audio_path="/tmp/meeting.mp3",
        note_type="meeting",
        title="Interview",
        transcript_text=(
            "What should we work on next? We should finish the notes flow. "
            "How will you verify it? I will use the real vault. "
            "When do you need the branch? Today."
        ),
        duration_seconds=162.0,
    )

    assert result["success"] is True
    assert result["attendee_count"] == 2
    path = Path(result["path"])
    assert "attendee_count: 2" in path.read_text(encoding="utf-8")
    assert refresh_calls == [vault]
