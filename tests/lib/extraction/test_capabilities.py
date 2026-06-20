"""Regression tests for extraction capability inventory probes."""


def test_lightweight_capability_inventory_skips_per_model_ollama_show(
    tmp_path,
    monkeypatch,
):
    from src.lib.extraction import capabilities

    capabilities.clear_capability_cache()
    monkeypatch.setattr(
        capabilities,
        "_PACKAGE_NAMES",
        ["openvino", "openvino-genai", "faster-whisper"],
    )
    monkeypatch.setattr(capabilities, "_package_version", lambda _name: None)
    monkeypatch.setattr(capabilities, "_resolve_ffmpeg_binary", lambda: None)
    monkeypatch.setattr(capabilities, "_resolve_ollama_binary", lambda: "ollama")
    monkeypatch.setattr(
        capabilities,
        "_run_json_command",
        lambda _cmd, timeout_s: {
            "models": [
                {"name": "glm-ocr:latest", "details": {"families": []}},
                {"name": "llava:latest", "details": {"families": ["clip"]}},
            ]
        },
    )
    monkeypatch.setattr(
        capabilities,
        "_run_text_command",
        lambda *_args, **_kwargs: "",
    )
    monkeypatch.setattr(
        capabilities,
        "_ollama_show_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("lightweight inventory should not run ollama show")
        ),
    )
    monkeypatch.setattr(
        capabilities,
        "_default_transcription_model_dir",
        lambda: tmp_path / "missing-model",
    )
    monkeypatch.setattr(capabilities, "_read_openvino_live_device", lambda _path: None)
    monkeypatch.setattr(capabilities, "_build_extraction_prereqs", lambda: {})

    inventory = capabilities.detect_extraction_capabilities(
        use_cache=False,
        probe_vision_models=False,
    )

    assert inventory["ollama"]["models"] == ["glm-ocr:latest", "llava:latest"]
    assert inventory["ollama"]["glm_ocr_available"] is True
    assert inventory["ollama"]["vision_models"] == ["llava:latest"]
