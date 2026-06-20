from src.lib.extraction.transcription import TranscriptResult
from src.lib.routing import engines, resolver


def _ok(method):
    return TranscriptResult(success=True, transcript="hello world", method=method, backend="NPU")


def test_local_whisper_engine_delegates(monkeypatch):
    monkeypatch.setattr(engines, "_transcribe_audio", lambda path, model_dir=None: _ok("openvino-whisper"))
    out = engines.TRANSCRIPT_ENGINES["openvino-whisper"].run("a.wav")
    assert out.success is True
    assert out.method == "openvino-whisper"


def test_gemini_unavailable_reports_not_ready(monkeypatch):
    monkeypatch.setattr(engines, "_gemini_cli_path", lambda: None)
    avail = engines.TRANSCRIPT_ENGINES["gemini-transcribe"].available()
    assert avail.available is False
    assert avail.setup_hint


def test_transcribe_offline_uses_local_whisper(monkeypatch):
    monkeypatch.setattr(engines, "_transcribe_audio", lambda path, model_dir=None: _ok("openvino-whisper"))
    out = resolver.transcribe("a.wav", mode="offline", os_name="win32")
    assert out.method == "openvino-whisper"


def test_transcribe_offline_attaches_route_metadata(monkeypatch):
    monkeypatch.setattr(engines, "_transcribe_audio", lambda path, model_dir=None: _ok("openvino-whisper"))
    out = resolver.transcribe("a.wav", mode="offline", os_name="win32")
    assert out.route_mode == "offline"
    assert out.route_engine_id == "openvino-whisper"
    assert out.fallback_engine_id is None


def test_transcribe_regular_uses_gemini(monkeypatch):
    monkeypatch.setattr(engines, "_gemini_cli_path", lambda: "C:/g/gemini.cmd")
    monkeypatch.setattr(
        engines.GeminiTranscribeEngine,
        "run",
        lambda self, path, *, model_dir=None, timeout_s=None: _ok("gemini-transcribe"),
    )
    out = resolver.transcribe("a.wav", mode="regular", os_name="win32")
    assert out.method == "gemini-transcribe"


def test_transcribe_regular_attaches_route_metadata(monkeypatch):
    monkeypatch.setattr(engines, "_gemini_cli_path", lambda: "C:/g/gemini.cmd")
    monkeypatch.setattr(
        engines.GeminiTranscribeEngine,
        "run",
        lambda self, path, *, model_dir=None, timeout_s=None: _ok("gemini-transcribe"),
    )
    out = resolver.transcribe("a.wav", mode="regular", os_name="win32")
    assert out.route_mode == "regular"
    assert out.route_engine_id == "gemini-transcribe"
    assert out.fallback_engine_id is None


def test_d1_fallback_to_local_when_gemini_absent(monkeypatch):
    # Regular mode, but Gemini missing -> fall back to local whisper + notice.
    monkeypatch.setattr(engines, "_gemini_cli_path", lambda: None)
    monkeypatch.setattr(engines, "_transcribe_audio", lambda path, model_dir=None: _ok("faster-whisper"))
    out = resolver.transcribe("a.wav", mode="regular", os_name="darwin")
    assert out.success is True
    assert out.method == "faster-whisper"
    assert out.needs_review is True
    assert "fallback" in (out.note or "").lower()


def test_d1_fallback_records_selected_and_fallback_engines(monkeypatch):
    monkeypatch.setattr(engines, "_gemini_cli_path", lambda: None)
    monkeypatch.setattr(engines, "_transcribe_audio", lambda path, model_dir=None: _ok("faster-whisper"))
    out = resolver.transcribe("a.wav", mode="regular", os_name="darwin")
    assert out.route_mode == "regular"
    assert out.route_engine_id == "gemini-transcribe"
    assert out.fallback_engine_id == "faster-whisper"
    assert out.needs_review is True
    assert "fallback" in (out.note or "").lower()


def test_gemini_run_happy_path(monkeypatch, tmp_path):
    # Engine must pass --yolo + an @<path> audio attachment and parse the transcript
    # off stdout (Gemini's file tools are workspace-sandboxed, so no result file).
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFFfake")
    monkeypatch.setattr(engines, "_gemini_cli_path", lambda: "gemini")

    noisy_stdout = (
        "Warning: 256-color support not detected.\n"
        "YOLO mode is enabled. All tool calls will be automatically approved.\n"
        "the quick brown fox\n"
    )

    def fake_capture(cmd, *, cwd, env, timeout_s):
        assert "--yolo" in cmd
        assert any(str(part).startswith("Transcribe the audio file @") for part in cmd)
        return noisy_stdout, False

    monkeypatch.setattr(engines, "_run_gemini_capture", fake_capture)

    out = engines.TRANSCRIPT_ENGINES["gemini-transcribe"].run(str(audio))
    assert out.success is True
    assert out.transcript == "the quick brown fox"
    assert out.method == "gemini-transcribe"
    assert out.cloud_used is True


def test_gemini_run_uses_bounded_demo_safe_timeout(monkeypatch, tmp_path):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFFfake")
    monkeypatch.setattr(engines, "_gemini_cli_path", lambda: "gemini")

    def fake_capture(cmd, *, cwd, env, timeout_s):
        assert timeout_s == 120
        return "", True

    monkeypatch.setattr(engines, "_run_gemini_capture", fake_capture)
    out = engines.TRANSCRIPT_ENGINES["gemini-transcribe"].run(str(audio))
    assert out.success is False
    assert "timed out" in (out.error or "")


def test_gemini_run_timeout_is_reported(monkeypatch, tmp_path):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFFfake")
    monkeypatch.setattr(engines, "_gemini_cli_path", lambda: "gemini")
    monkeypatch.setattr(engines, "_run_gemini_capture", lambda *a, **k: ("", True))
    out = engines.TRANSCRIPT_ENGINES["gemini-transcribe"].run(str(audio))
    assert out.success is False
    assert "timed out" in (out.error or "")


def test_clean_gemini_transcript_strips_noise():
    raw = (
        "Warning: 256-color support not detected.\n"
        "Ripgrep is not available.\n"
        "MCP issues detected.\n"
        "Skill conflict detected.\n"
        "YOLO mode is enabled.\n"
        "Error: AttachConsole failed\n"
        "    at Object.<anonymous> (conpty_console_list_agent.js:11:26)\n"
        "Node.js v24.15.0\n"
        "Augur offline routing verification, the quick brown fox.\n"
    )
    assert engines._clean_gemini_transcript(raw) == "Augur offline routing verification, the quick brown fox."
