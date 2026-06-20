from __future__ import annotations


def test_gemini_transcribe_timeout_default_allows_agent_audio_startup(monkeypatch):
    from src.lib.routing import engines

    monkeypatch.delenv("AUGUR_GEMINI_TRANSCRIBE_TIMEOUT_SECONDS", raising=False)

    assert engines._gemini_transcribe_timeout_seconds() == 120


def test_gemini_transcribe_timeout_uses_valid_env_override(monkeypatch):
    from src.lib.routing import engines

    monkeypatch.setenv("AUGUR_GEMINI_TRANSCRIBE_TIMEOUT_SECONDS", "45")

    assert engines._gemini_transcribe_timeout_seconds() == 45


def test_gemini_transcribe_timeout_ignores_too_small_env_override(monkeypatch):
    from src.lib.routing import engines

    monkeypatch.setenv("AUGUR_GEMINI_TRANSCRIBE_TIMEOUT_SECONDS", "5")

    assert engines._gemini_transcribe_timeout_seconds() == 120


def test_regular_transcribe_forwards_explicit_gemini_timeout(monkeypatch):
    from src.lib.extraction.transcription import TranscriptResult
    from src.lib.routing import resolver

    captured = {}

    class FakeGeminiEngine:
        engine_id = "gemini-transcribe"

        def run(self, audio_path, *, model_dir=None, timeout_s=None):
            captured["audio_path"] = audio_path
            captured["model_dir"] = model_dir
            captured["timeout_s"] = timeout_s
            return TranscriptResult(
                success=True,
                transcript="regular route transcript",
                method="gemini-transcribe",
                backend="gemini",
            )

    monkeypatch.setattr(
        resolver,
        "engine_id_for",
        lambda activity, mode, os_name=None: "gemini-transcribe",
    )
    monkeypatch.setitem(
        resolver.TRANSCRIPT_ENGINES,
        "gemini-transcribe",
        FakeGeminiEngine(),
    )

    result = resolver.transcribe(
        "offload-demo.m4a",
        model_dir="unused",
        mode="regular",
        gemini_timeout_s=10,
    )

    assert result.success is True
    assert result.route_engine_id == "gemini-transcribe"
    assert captured == {
        "audio_path": "offload-demo.m4a",
        "model_dir": "unused",
        "timeout_s": 10,
    }


def test_gemini_capture_timeout_kills_posix_process_group(monkeypatch):
    from src.lib.routing import engines

    popen_kwargs = {}
    killpg_calls = []

    class FakeProc:
        pid = 43210

        def __init__(self):
            self._communicate_count = 0

        def poll(self):
            return None

        def communicate(self, timeout=None):
            self._communicate_count += 1
            if self._communicate_count == 1:
                raise engines.subprocess.TimeoutExpired(
                    cmd=["gemini"],
                    timeout=timeout,
                )
            return "", ""

        def wait(self, timeout=None):
            return -15

        def kill(self):
            raise AssertionError("POSIX timeout should kill the process group")

    def fake_popen(*args, **kwargs):
        del args
        popen_kwargs.update(kwargs)
        return FakeProc()

    def fake_killpg(pid, sig):
        killpg_calls.append((pid, sig))

    monkeypatch.setattr(engines.sys, "platform", "darwin")
    monkeypatch.setattr(engines.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(engines._os, "killpg", fake_killpg)

    stdout, timed_out = engines._run_gemini_capture(
        ["gemini"],
        cwd=".",
        env={},
        timeout_s=0.01,
    )

    assert stdout == ""
    assert timed_out is True
    assert popen_kwargs["start_new_session"] is True
    assert killpg_calls
    assert killpg_calls[0][0] == 43210
