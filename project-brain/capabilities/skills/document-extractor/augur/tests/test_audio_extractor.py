"""Coverage for local audio extraction and transcription."""
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_audio_extractor_importable() -> None:
    mod = importlib.import_module("src.lib.extraction.audio_extractor")
    assert mod is not None


def test_transcribe_audio_degrades_when_backend_missing(tmp_path, monkeypatch) -> None:
    from src.lib.extraction import transcription

    audio_path = tmp_path / "sample.mp3"
    audio_path.write_bytes(b"fake mp3")
    monkeypatch.setattr(transcription.shutil, "which", lambda _name: None)
    monkeypatch.setattr(transcription, "_packaged_ffmpeg_binary", lambda: None)

    result = transcription.transcribe_audio(str(audio_path))

    assert result.success is False
    assert result.method == "unavailable"
    assert result.cloud_used is False
    assert result.needs_review is True


def test_extract_audio_uses_local_transcription_first(monkeypatch) -> None:
    from src.lib.extraction import audio_extractor
    from src.lib.extraction.transcription import TranscriptResult

    monkeypatch.setattr(
        audio_extractor,
        "transcribe_audio",
        lambda _path: TranscriptResult(
            success=True,
            transcript="Discussed roadmap and assigned Gur a follow-up.",
            method="test-local-whisper",
            backend="CPU",
            duration_s=12.0,
            language="en",
            confidence="medium",
        ),
    )

    markdown = audio_extractor.extract_audio("meeting.mp3")

    assert markdown is not None
    assert "Discussed roadmap" in markdown
    assert "Method: test-local-whisper" in markdown


def test_extract_audio_fails_closed_without_markitdown_fallback(monkeypatch) -> None:
    from src.lib.extraction import audio_extractor
    from src.lib.extraction.transcription import TranscriptResult

    class _CloudAudioMarkItDown:
        def convert(self, _path: str):
            return types.SimpleNamespace(markdown="cloud transcript", text_content="cloud transcript")

    monkeypatch.setattr(audio_extractor.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        audio_extractor,
        "transcribe_audio",
        lambda _path: TranscriptResult(
            success=False,
            transcript="",
            method="unavailable",
            cloud_used=False,
            needs_review=True,
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "markitdown",
        types.SimpleNamespace(MarkItDown=lambda: _CloudAudioMarkItDown()),
    )

    assert audio_extractor.extract_audio("meeting.mp3") is None


def test_transcribe_audio_downloads_default_faster_whisper_model_on_macos(tmp_path, monkeypatch) -> None:
    from src.lib.extraction import transcription

    audio_path = tmp_path / "sample.mp3"
    audio_path.write_bytes(b"fake mp3")
    cache_dir = tmp_path / "cache"
    downloaded: list[Path] = []

    class _WhisperModel:
        def __init__(self, model_name: str, **_kwargs):
            assert Path(model_name).name == "faster-whisper-small"

        def transcribe(self, _path: str):
            return [types.SimpleNamespace(text="hello from faster whisper")], types.SimpleNamespace(
                duration=1.0,
                language="en",
                language_probability=0.98,
            )

    def fake_download() -> Path:
        model_dir = cache_dir / "models" / "faster-whisper-small"
        model_dir.mkdir(parents=True)
        downloaded.append(model_dir)
        return model_dir

    monkeypatch.setattr(transcription.sys, "platform", "darwin")
    monkeypatch.delenv("AUGUR_LOCAL_WHISPER_MODEL_DIR", raising=False)
    monkeypatch.setattr(transcription, "_has_ffmpeg", lambda: True)
    monkeypatch.setattr(transcription, "_module_available", lambda name: name == "faster_whisper")
    monkeypatch.setattr(transcription, "get_cache_dir", lambda: cache_dir)
    monkeypatch.setattr(transcription, "_airplane_mode_enabled", lambda: False)
    monkeypatch.setattr(transcription, "_download_default_faster_whisper_model", fake_download, raising=False)
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=_WhisperModel))

    result = transcription.transcribe_audio(str(audio_path))

    assert result.success is True
    assert result.method == "faster-whisper"
    assert result.backend == "auto"
    assert result.transcript == "hello from faster whisper"
    assert downloaded == [cache_dir / "models" / "faster-whisper-small"]


def test_transcribe_audio_does_not_download_faster_whisper_model_in_airplane_mode(tmp_path, monkeypatch) -> None:
    from src.lib.extraction import transcription

    audio_path = tmp_path / "sample.mp3"
    audio_path.write_bytes(b"fake mp3")
    constructed_models: list[str] = []

    class _WhisperModel:
        def __init__(self, model_name: str, **_kwargs):
            constructed_models.append(model_name)

    monkeypatch.setattr(transcription.sys, "platform", "darwin")
    monkeypatch.delenv("AUGUR_LOCAL_WHISPER_MODEL_DIR", raising=False)
    monkeypatch.setattr(transcription, "_has_ffmpeg", lambda: True)
    monkeypatch.setattr(transcription, "_module_available", lambda name: name == "faster_whisper")
    monkeypatch.setattr(transcription, "get_cache_dir", lambda: tmp_path / "empty-cache")
    monkeypatch.setattr(transcription, "_airplane_mode_enabled", lambda: True)
    monkeypatch.setattr(
        transcription,
        "_download_default_faster_whisper_model",
        lambda: (_ for _ in ()).throw(AssertionError("must not download in airplane mode")),
        raising=False,
    )
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=_WhisperModel))

    result = transcription.transcribe_audio(str(audio_path))

    assert result.success is False
    assert result.method == "unavailable"
    assert result.needs_review is True
    assert constructed_models == []


def test_default_whisper_model_is_large_v3() -> None:
    from src.lib.extraction import transcription

    assert transcription.DEFAULT_LOCAL_WHISPER_MODEL_NAME == "whisper-large-v3-int8-ov"


def test_openvino_transcription_probes_npu_gpu_cpu(tmp_path, monkeypatch) -> None:
    from src.lib.extraction import transcription

    audio_path = tmp_path / "sample.mp3"
    audio_path.write_bytes(b"fake mp3")
    model_dir = tmp_path / "whisper-large-v3-int8-ov"
    model_dir.mkdir()
    devices_seen: list[str] = []
    pipeline_kwargs: dict[str, dict] = {}

    class _WhisperPipeline:
        def __init__(self, _model_dir: str, device: str, **kwargs):
            devices_seen.append(device)
            pipeline_kwargs[device] = kwargs
            if device != "CPU":
                raise RuntimeError(f"{device} unavailable")

        def generate(self, raw_speech_input):
            assert raw_speech_input == [0.0, 0.25]
            return "hello from cpu"

    monkeypatch.setattr(transcription, "_has_ffmpeg", lambda: True)
    monkeypatch.setattr(transcription, "_load_audio_samples_16khz", lambda _path: [0.0, 0.25])
    monkeypatch.setattr(transcription, "_module_available", lambda name: name == "openvino_genai")
    monkeypatch.setattr(transcription, "_npu_driver_ready_for_openvino", lambda: True)
    monkeypatch.setitem(sys.modules, "openvino_genai", types.SimpleNamespace(WhisperPipeline=_WhisperPipeline))

    result = transcription.transcribe_audio(str(audio_path), model_dir=str(model_dir))

    assert result.success is True
    assert result.backend == "CPU"
    assert devices_seen == ["NPU", "GPU", "CPU"]
    assert pipeline_kwargs["NPU"] == {"STATIC_PIPELINE": True}
    assert pipeline_kwargs["GPU"] == {}
    assert pipeline_kwargs["CPU"] == {}


def test_openvino_transcription_skips_npu_when_driver_below_floor(tmp_path, monkeypatch) -> None:
    from src.lib.extraction import transcription

    audio_path = tmp_path / "sample.mp3"
    audio_path.write_bytes(b"fake mp3")
    model_dir = tmp_path / "whisper-large-v3-int8-ov"
    model_dir.mkdir()
    devices_seen: list[str] = []

    class _WhisperPipeline:
        def __init__(self, _model_dir: str, device: str, **_kwargs):
            devices_seen.append(device)
            if device == "NPU":
                raise AssertionError("stale NPU driver should not be probed")

        def generate(self, raw_speech_input):
            assert raw_speech_input == [0.0, 0.25]
            return "hello from gpu"

    monkeypatch.setattr(transcription, "_has_ffmpeg", lambda: True)
    monkeypatch.setattr(transcription, "_load_audio_samples_16khz", lambda _path: [0.0, 0.25])
    monkeypatch.setattr(transcription, "_module_available", lambda name: name == "openvino_genai")
    monkeypatch.setattr(transcription, "_npu_driver_ready_for_openvino", lambda: False, raising=False)
    monkeypatch.setitem(sys.modules, "openvino_genai", types.SimpleNamespace(WhisperPipeline=_WhisperPipeline))

    result = transcription.transcribe_audio(str(audio_path), model_dir=str(model_dir))

    assert result.success is True
    assert result.backend == "GPU"
    assert devices_seen == ["GPU"]


def test_openvino_transcription_skips_npu_after_same_boot_failure(tmp_path, monkeypatch) -> None:
    from src.lib.extraction import transcription

    audio_path = tmp_path / "sample.mp3"
    audio_path.write_bytes(b"fake mp3")
    model_dir = tmp_path / "whisper-large-v3-int8-ov"
    model_dir.mkdir()
    cache_dir = tmp_path / "cache"
    status_dir = cache_dir / "extraction"
    status_dir.mkdir(parents=True)
    (status_dir / transcription.OPENVINO_DEVICE_STATUS_FILENAME).write_text(
        (
            '{"success": false, "device": "NPU", "model_dir": "'
            + str(model_dir).replace("\\", "\\\\")
            + '", "timestamp": 1000.0, "error": "ZE_RESULT_ERROR_UNKNOWN"}'
        ),
        encoding="utf-8",
    )
    devices_seen: list[str] = []

    class _WhisperPipeline:
        def __init__(self, _model_dir: str, device: str, **_kwargs):
            devices_seen.append(device)
            if device == "NPU":
                raise AssertionError("recent same-boot NPU failure should not be retried")

        def generate(self, raw_speech_input):
            assert raw_speech_input == [0.0, 0.25]
            return "hello from gpu"

    monkeypatch.setattr(transcription, "get_cache_dir", lambda: cache_dir)
    monkeypatch.setattr(transcription.time, "time", lambda: 1100.0)
    monkeypatch.setattr(transcription, "_current_boot_time", lambda: 900.0, raising=False)
    monkeypatch.setattr(transcription, "_has_ffmpeg", lambda: True)
    monkeypatch.setattr(transcription, "_load_audio_samples_16khz", lambda _path: [0.0, 0.25])
    monkeypatch.setattr(transcription, "_module_available", lambda name: name == "openvino_genai")
    monkeypatch.setattr(transcription, "_npu_driver_ready_for_openvino", lambda: True)
    monkeypatch.setitem(sys.modules, "openvino_genai", types.SimpleNamespace(WhisperPipeline=_WhisperPipeline))

    result = transcription.transcribe_audio(str(audio_path), model_dir=str(model_dir))

    status = transcription.get_last_openvino_device_status()
    assert result.success is True
    assert result.backend == "GPU"
    assert devices_seen == ["GPU"]
    assert status["device_failures"]["NPU"]["error"] == "ZE_RESULT_ERROR_UNKNOWN"


def test_transcribe_audio_downloads_default_openvino_model_when_missing(tmp_path, monkeypatch) -> None:
    from src.lib.extraction import transcription

    audio_path = tmp_path / "sample.mp3"
    audio_path.write_bytes(b"fake mp3")
    cache_dir = tmp_path / "cache"
    downloaded: list[Path] = []

    class _WhisperPipeline:
        def __init__(self, model_dir: str, device: str, **kwargs):
            assert Path(model_dir).name == "whisper-large-v3-int8-ov"
            assert device == "NPU"
            assert kwargs == {"STATIC_PIPELINE": True}

        def generate(self, raw_speech_input):
            assert raw_speech_input == [0.0, 0.25]
            return "downloaded model transcript"

    def fake_download() -> Path:
        model_dir = cache_dir / "models" / "whisper-large-v3-int8-ov"
        model_dir.mkdir(parents=True)
        downloaded.append(model_dir)
        return model_dir

    monkeypatch.delenv("AUGUR_LOCAL_WHISPER_MODEL_DIR", raising=False)
    monkeypatch.setattr(transcription, "get_cache_dir", lambda: cache_dir)
    monkeypatch.setattr(transcription, "_has_ffmpeg", lambda: True)
    monkeypatch.setattr(transcription, "_load_audio_samples_16khz", lambda _path: [0.0, 0.25])
    monkeypatch.setattr(transcription, "_module_available", lambda name: name == "openvino_genai")
    monkeypatch.setattr(transcription, "_airplane_mode_enabled", lambda: False)
    monkeypatch.setattr(transcription, "_npu_driver_ready_for_openvino", lambda: True)
    monkeypatch.setattr(transcription, "_download_default_openvino_model", fake_download)
    monkeypatch.setitem(sys.modules, "openvino_genai", types.SimpleNamespace(WhisperPipeline=_WhisperPipeline))

    result = transcription.transcribe_audio(str(audio_path))

    assert result.success is True
    assert result.backend == "NPU"
    assert downloaded == [cache_dir / "models" / "whisper-large-v3-int8-ov"]


def test_transcribe_audio_does_not_download_model_in_airplane_mode(tmp_path, monkeypatch) -> None:
    from src.lib.extraction import transcription

    audio_path = tmp_path / "sample.mp3"
    audio_path.write_bytes(b"fake mp3")
    monkeypatch.delenv("AUGUR_LOCAL_WHISPER_MODEL_DIR", raising=False)
    monkeypatch.setattr(transcription, "get_cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(transcription, "_has_ffmpeg", lambda: True)
    monkeypatch.setattr(transcription, "_module_available", lambda name: name == "openvino_genai")
    monkeypatch.setattr(transcription, "_airplane_mode_enabled", lambda: True)
    monkeypatch.setattr(
        transcription,
        "_download_default_openvino_model",
        lambda: (_ for _ in ()).throw(AssertionError("must not download in airplane mode")),
    )

    result = transcription.transcribe_audio(str(audio_path))

    assert result.success is False
    assert result.method == "unavailable"
    assert "model" in (result.error or "").lower()


def test_can_transcribe_returns_false_on_windows_without_openvino(monkeypatch, tmp_path) -> None:
    from src.lib.extraction import transcription

    model_dir = tmp_path / "whisper-large-v3-int8-ov"
    model_dir.mkdir()
    monkeypatch.setattr(transcription.sys, "platform", "win32")
    monkeypatch.setattr(transcription, "_has_ffmpeg", lambda: True)
    monkeypatch.setattr(transcription, "_module_available", lambda name: name == "faster_whisper")

    assert transcription.can_transcribe_audio(model_dir=str(model_dir)) is False


def test_can_transcribe_returns_true_on_macos_with_faster_whisper(monkeypatch, tmp_path) -> None:
    from src.lib.extraction import transcription

    model_dir = tmp_path / "whisper-large-v3-int8-ov"
    model_dir.mkdir()
    monkeypatch.setattr(transcription.sys, "platform", "darwin")
    monkeypatch.setattr(transcription, "_has_ffmpeg", lambda: True)
    monkeypatch.setattr(transcription, "_module_available", lambda name: name == "faster_whisper")

    assert transcription.can_transcribe_audio(model_dir=str(model_dir)) is True


def test_transcribe_audio_accepts_video_recordings(tmp_path, monkeypatch) -> None:
    from src.lib.extraction import transcription

    video_path = tmp_path / "meeting-recording.mp4"
    video_path.write_bytes(b"fake mp4")
    model_dir = tmp_path / "faster-whisper-small"
    model_dir.mkdir()

    class _WhisperModel:
        def __init__(self, model_name: str, **_kwargs):
            assert Path(model_name) == model_dir

        def transcribe(self, _path: str):
            return [types.SimpleNamespace(text="video meeting transcript")], types.SimpleNamespace(
                duration=3.0,
                language="en",
                language_probability=0.97,
            )

    monkeypatch.setattr(transcription.sys, "platform", "darwin")
    monkeypatch.setattr(transcription, "_has_ffmpeg", lambda: True)
    monkeypatch.setattr(transcription, "_module_available", lambda name: name == "faster_whisper")
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=_WhisperModel))

    result = transcription.transcribe_audio(str(video_path), model_dir=str(model_dir))

    assert result.success is True
    assert result.transcript == "video meeting transcript"


def test_faster_whisper_helper_requires_local_model_path(monkeypatch) -> None:
    from src.lib.extraction import transcription

    constructed_models: list[str] = []

    class _WhisperModel:
        def __init__(self, model_name: str, **_kwargs):
            constructed_models.append(model_name)

    monkeypatch.setattr(transcription, "get_cache_dir", lambda: Path("empty-cache"))
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=_WhisperModel))

    result = transcription._transcribe_faster_whisper(Path("sample.mp3"))

    assert result.success is False
    assert result.method == "unavailable"
    assert result.needs_review is True
    assert constructed_models == []


def test_can_transcribe_audio_does_not_report_openvino_without_model_dir(monkeypatch) -> None:
    from src.lib.extraction import transcription

    monkeypatch.setattr(transcription, "_has_ffmpeg", lambda: True)
    monkeypatch.setattr(transcription, "_module_available", lambda name: name == "openvino_genai")
    monkeypatch.setattr(transcription, "get_cache_dir", lambda: Path("empty-cache"))

    assert transcription.can_transcribe_audio() is False


def test_local_model_path_defaults_to_augur_cache(tmp_path, monkeypatch) -> None:
    from src.lib.extraction import transcription

    cache_dir = tmp_path / "cache"
    model_dir = cache_dir / "models" / "whisper-large-v3-int8-ov"
    model_dir.mkdir(parents=True)
    monkeypatch.delenv("AUGUR_LOCAL_WHISPER_MODEL_DIR", raising=False)
    monkeypatch.setattr(transcription, "get_cache_dir", lambda: cache_dir)

    assert transcription._local_model_path(None) == model_dir


def test_default_model_path_uses_document_asr_profile(tmp_path, monkeypatch) -> None:
    import src.lib.ai as ai_api
    from src.lib.ai.config import LLMConfig, LLMProfile
    from src.lib.extraction import transcription

    cache_dir = tmp_path / "cache"
    cfg = LLMConfig(
        active_profile="local",
        profiles={
            "local": LLMProfile(
                name="local",
                provider="openai_compatible",
                base_url="http://localhost:11434/v1",
                model="qwen3.5:latest",
            ),
            "asr_gpu": LLMProfile(
                name="asr_gpu",
                provider="command",
                base_url="local://openvino",
                model="custom-whisper-int8-ov",
                command="openvino-whisper",
            ),
        },
        tasks={"document_asr": "asr_gpu"},
    )

    monkeypatch.setattr(ai_api, "load_llm_config", lambda: cfg)
    monkeypatch.setattr(transcription, "get_cache_dir", lambda: cache_dir)

    assert transcription._default_local_model_dir() == cache_dir / "models" / "custom-whisper-int8-ov"


def test_openvino_transcription_records_selected_device(tmp_path, monkeypatch) -> None:
    from src.lib.extraction import transcription

    audio_path = tmp_path / "sample.mp3"
    audio_path.write_bytes(b"fake mp3")
    model_dir = tmp_path / "whisper-large-v3-int8-ov"
    model_dir.mkdir()

    class _WhisperPipeline:
        def __init__(self, _model_dir: str, device: str, **_kwargs):
            if device == "NPU":
                raise RuntimeError("NPU unavailable")
            self.device = device

        def generate(self, raw_speech_input):
            assert raw_speech_input == [0.0, 0.25]
            return "hello from gpu"

    monkeypatch.setattr(transcription, "get_cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(transcription, "_has_ffmpeg", lambda: True)
    monkeypatch.setattr(transcription, "_load_audio_samples_16khz", lambda _path: [0.0, 0.25])
    monkeypatch.setattr(transcription, "_module_available", lambda name: name == "openvino_genai")
    monkeypatch.setattr(transcription, "_npu_driver_ready_for_openvino", lambda: True)
    monkeypatch.setitem(sys.modules, "openvino_genai", types.SimpleNamespace(WhisperPipeline=_WhisperPipeline))

    result = transcription.transcribe_audio(str(audio_path), model_dir=str(model_dir))

    status = transcription.get_last_openvino_device_status()
    assert result.success is True
    assert result.backend == "GPU"
    assert status["device"] == "GPU"
    assert status["device_failures"]["NPU"]["error"] == "NPU unavailable"


def test_extract_audio_uses_env_model_dir(tmp_path, monkeypatch) -> None:
    from src.lib.extraction import audio_extractor
    from src.lib.extraction.transcription import TranscriptResult

    model_dir = tmp_path / "whisper-model"
    model_dir.mkdir()
    seen_model_dirs: list[str | None] = []

    def _transcribe(_path: str, *, model_dir: str | None = None):
        seen_model_dirs.append(model_dir)
        return TranscriptResult(
            success=True,
            transcript="Local env model transcript.",
            method="test-local-whisper",
            backend="CPU",
        )

    monkeypatch.setenv("AUGUR_LOCAL_WHISPER_MODEL_DIR", str(model_dir))
    monkeypatch.setattr(audio_extractor, "transcribe_audio", _transcribe)

    markdown = audio_extractor.extract_audio("meeting.mp3")

    assert markdown is not None
    assert seen_model_dirs == [str(model_dir)]


def test_extract_accepts_audio_model_dir_and_passes_through(tmp_path, monkeypatch) -> None:
    from src.lib.extraction import extractor
    from src.lib.extraction.transcription import TranscriptResult

    audio_path = tmp_path / "meeting.mp3"
    audio_path.write_bytes(b"fake mp3")
    model_dir = tmp_path / "whisper-model"
    model_dir.mkdir()
    seen_model_dirs: list[str | None] = []

    def _routing_transcribe(_path: str, *, model_dir: str | None = None):
        seen_model_dirs.append(model_dir)
        return TranscriptResult(
            success=True,
            transcript="forwarded transcript",
            method="openvino-whisper",
            backend="NPU",
        )

    monkeypatch.setattr(extractor, "_routing_transcribe", _routing_transcribe)

    result = extractor.extract(str(audio_path), audio_model_dir=str(model_dir))

    assert result.success is True
    assert seen_model_dirs == [str(model_dir)]


def test_extract_routes_audio_through_local_audio_extractor(tmp_path, monkeypatch) -> None:
    from src.lib.extraction import extractor
    from src.lib.extraction.transcription import TranscriptResult

    audio_path = tmp_path / "meeting.mp3"
    audio_path.write_bytes(b"fake mp3")

    monkeypatch.setattr(
        extractor,
        "_routing_transcribe",
        lambda _path, **_kwargs: TranscriptResult(
            success=True,
            transcript="hello world",
            method="openvino-whisper",
            backend="NPU",
        ),
    )

    result = extractor.extract(str(audio_path))

    assert result.success is True
    assert "hello world" in result.markdown
