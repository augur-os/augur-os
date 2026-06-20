from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def clear_capability_cache():
    from src.lib.extraction import capabilities

    capabilities.clear_capability_cache()
    yield
    capabilities.clear_capability_cache()


def test_airplane_policy_disables_cloud(monkeypatch, tmp_path: Path) -> None:
    from src.lib.extraction import capabilities

    prefs = tmp_path / "preferences.yaml"
    prefs.write_text("airplane_mode:\n  enabled: true\n", encoding="utf-8")
    monkeypatch.setattr(capabilities, "get_preferences_path", lambda: prefs)

    policy = capabilities.get_extraction_policy()

    assert policy["airplane_mode_enabled"] is True
    assert policy["cloud_escalation_allowed"] is False
    assert policy["local_agent_escalation_allowed"] is True


def test_inventory_reports_ollama_vision_models(monkeypatch) -> None:
    from src.lib.extraction import capabilities

    monkeypatch.setattr(capabilities.shutil, "which", lambda name: "ollama.exe" if name == "ollama" else None)
    monkeypatch.setattr(
        capabilities,
        "_run_json_command",
        lambda _cmd, timeout_s=10: {
            "models": [
                {"name": "gemma4:latest", "details": {"families": ["gemma4"]}},
                {"name": "llama3.2:3b", "details": {"families": ["llama"]}},
            ]
        },
    )
    monkeypatch.setattr(
        capabilities,
        "_ollama_show_text",
        lambda model, **_kwargs: "Capabilities\n  completion\n  vision\n" if model == "gemma4:latest" else "Capabilities\n  completion\n",
    )

    inventory = capabilities.detect_extraction_capabilities(use_cache=False)

    assert inventory["ollama"]["installed"] is True
    assert inventory["ollama"]["vision_models"] == ["gemma4:latest"]
    assert inventory["local_agent_ready"] is True


def test_inventory_omits_tesseract_and_markitdown_ocr(monkeypatch) -> None:
    """Tesseract and markitdown-ocr are removed from the active capability surface."""
    from src.lib.extraction import capabilities

    inventory = capabilities.detect_extraction_capabilities(use_cache=False)
    packages = inventory.get("packages", {})

    assert "pytesseract" not in packages
    assert "markitdown-ocr" not in packages
    assert "tesseract" not in inventory.get("commands", {})
    assert "ocr_ready" not in inventory


def test_inventory_falls_back_to_plain_ollama_list(monkeypatch) -> None:
    from src.lib.extraction import capabilities

    monkeypatch.setattr(capabilities.shutil, "which", lambda name: "ollama.exe" if name == "ollama" else None)
    monkeypatch.setattr(capabilities, "_run_json_command", lambda _cmd, timeout_s=10: {})
    monkeypatch.setattr(
        capabilities,
        "_run_text_command",
        lambda _cmd, timeout_s=10: (
            "NAME                 ID              SIZE      MODIFIED\n"
            "gemma4:latest        1a2b3c4d5e6f    4.9 GB    2 hours ago\n"
            "llama3.2:3b          7g8h9i0j1k2l    2.0 GB    1 day ago\n"
        ),
    )
    monkeypatch.setattr(
        capabilities,
        "_ollama_show_text",
        lambda model, **_kwargs: "Capabilities\n  completion\n  vision\n" if model == "gemma4:latest" else "Capabilities\n  completion\n",
    )

    inventory = capabilities.detect_extraction_capabilities(use_cache=False)

    assert inventory["ollama"]["models"] == ["gemma4:latest", "llama3.2:3b"]
    assert inventory["ollama"]["vision_models"] == ["gemma4:latest"]
    assert inventory["local_agent_ready"] is True


def test_inventory_finds_windows_default_ollama_path(monkeypatch, tmp_path: Path) -> None:
    from src.lib.extraction import capabilities

    fallback = tmp_path / "Programs" / "Ollama" / "ollama.exe"
    seen_commands: list[list[str]] = []

    monkeypatch.setattr(capabilities.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("PROGRAMFILES", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.setattr(capabilities.shutil, "which", lambda _name: None)
    monkeypatch.setattr(capabilities, "_candidate_exists", lambda path: path == str(fallback))

    def fake_json_command(cmd: list[str], timeout_s: int = 10):
        seen_commands.append(cmd)
        return {"models": [{"name": "gemma4:latest", "details": {"families": ["gemma4"]}}]}

    monkeypatch.setattr(capabilities, "_run_json_command", fake_json_command)
    monkeypatch.setattr(capabilities, "_ollama_show_text", lambda model, **_kwargs: "Capabilities\n  vision\n")

    inventory = capabilities.detect_extraction_capabilities(use_cache=False)

    assert inventory["commands"]["ollama"] == str(fallback)
    assert seen_commands == [[str(fallback), "list", "--json"]]
    assert inventory["ollama"]["vision_models"] == ["gemma4:latest"]


def test_inventory_uses_packaged_ffmpeg_and_default_transcription_model(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.extraction import capabilities

    model_dir = tmp_path / "cache" / "models" / "whisper-large-v3-int8-ov"
    faster_model_dir = tmp_path / "cache" / "models" / "faster-whisper-small"
    model_dir.mkdir(parents=True)

    def fake_version(name: str) -> str | None:
        if name == "markitdown":
            return "0.1.5"
        if name == "faster-whisper":
            return "1.1.1"
        if name == "imageio-ffmpeg":
            return "0.5.1"
        if name == "openvino-genai":
            return "2026.0.0"
        return None

    monkeypatch.setattr(capabilities, "_package_version", fake_version)
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: None)
    monkeypatch.setattr(capabilities, "_packaged_ffmpeg_binary", lambda: "packaged-ffmpeg.exe")
    monkeypatch.setattr(capabilities, "_default_transcription_model_dir", lambda: model_dir)
    monkeypatch.setattr(capabilities, "_default_faster_whisper_model_dir", lambda: faster_model_dir)
    monkeypatch.setattr(capabilities, "_resolve_ollama_binary", lambda: None)

    inventory = capabilities.detect_extraction_capabilities(use_cache=False)

    assert inventory["commands"]["ffmpeg"] == "packaged-ffmpeg.exe"
    assert inventory["transcription_ready"] is True
    assert inventory["transcription_model"] == str(model_dir)


def test_inventory_uses_macos_faster_whisper_model_dir(monkeypatch, tmp_path: Path) -> None:
    from src.lib.extraction import capabilities

    model_dir = tmp_path / "cache" / "models" / "faster-whisper-small"
    model_dir.mkdir(parents=True)
    openvino_model_dir = tmp_path / "cache" / "models" / "whisper-large-v3-int8-ov"

    def fake_version(name: str) -> str | None:
        if name == "faster-whisper":
            return "1.2.1"
        if name == "imageio-ffmpeg":
            return "0.6.0"
        return None

    monkeypatch.setattr(capabilities.sys, "platform", "darwin")
    monkeypatch.setattr(capabilities, "_package_version", fake_version)
    monkeypatch.setattr(capabilities, "_resolve_ffmpeg_binary", lambda: "ffmpeg")
    monkeypatch.setattr(capabilities, "_default_faster_whisper_model_dir", lambda: model_dir)
    monkeypatch.setattr(capabilities, "_default_transcription_model_dir", lambda: openvino_model_dir)
    monkeypatch.setattr(capabilities, "_resolve_ollama_binary", lambda: None)

    inventory = capabilities.detect_extraction_capabilities(use_cache=False)

    assert inventory["transcription_ready"] is True
    assert inventory["transcription_model"] == str(model_dir)


def test_inventory_surfaces_recorded_openvino_live_device(monkeypatch, tmp_path: Path) -> None:
    from src.lib.extraction import capabilities

    cache_dir = tmp_path / "cache"
    model_dir = cache_dir / "models" / "whisper-large-v3-int8-ov"
    model_dir.mkdir(parents=True)
    status_dir = cache_dir / "extraction"
    status_dir.mkdir()
    (status_dir / "openvino-whisper-status.json").write_text(
        '{"success": true, "device": "GPU", "model_dir": "'
        + str(model_dir).replace("\\", "\\\\")
        + '"}',
        encoding="utf-8",
    )

    def fake_version(name: str) -> str | None:
        if name == "openvino":
            return "2026.1.0"
        if name == "openvino-genai":
            return "2026.1.0"
        if name == "imageio-ffmpeg":
            return "0.6.0"
        return None

    monkeypatch.setattr(capabilities, "_package_version", fake_version)
    monkeypatch.setattr(capabilities, "get_cache_dir", lambda: cache_dir)
    monkeypatch.setattr(capabilities, "_resolve_ffmpeg_binary", lambda: "ffmpeg.exe")
    monkeypatch.setattr(capabilities, "_resolve_ollama_binary", lambda: None)

    inventory = capabilities.detect_extraction_capabilities(use_cache=False)

    assert inventory["openvino"]["live_device"] == "GPU"


def test_inventory_reports_extraction_prereqs(monkeypatch) -> None:
    """The prereqs block surfaces NPU driver and OpenVINO runtime status."""
    from src.lib.extraction import capabilities

    monkeypatch.setattr(capabilities, "_get_transformers_version", lambda: None)
    monkeypatch.setattr(capabilities, "_get_optimum_intel_version", lambda: None)
    monkeypatch.setattr(capabilities, "_get_openvino_version", lambda: "2026.0.0")
    monkeypatch.setattr(capabilities, "_get_npu_driver_version", lambda: "32.0.100.4724")

    inventory = capabilities.detect_extraction_capabilities(use_cache=False)
    prereqs = inventory["extraction_prereqs"]

    assert prereqs["transformers_version"] is None
    assert prereqs["transformers_required"] is False
    assert prereqs["transformers_ok"] is True
    assert prereqs["transformers_setup_hint"] is None
    assert prereqs["optimum_intel_version"] is None
    assert prereqs["optimum_intel_required"] is False
    assert prereqs["optimum_intel_ok"] is True
    assert prereqs["openvino_version"] == "2026.0.0"
    assert prereqs["openvino_ok"] is True
    assert prereqs["npu_driver_version"] == "32.0.100.4724"
    assert prereqs["npu_driver_ok"] is True


def test_inventory_flags_npu_driver_below_openvino_floor(monkeypatch) -> None:
    """OpenVINO 2026.1 NPU runtime requires the matching Intel NPU driver floor."""
    from src.lib.extraction import capabilities

    monkeypatch.setattr(capabilities.sys, "platform", "win32")
    monkeypatch.setattr(capabilities, "_get_transformers_version", lambda: None)
    monkeypatch.setattr(capabilities, "_get_optimum_intel_version", lambda: None)
    monkeypatch.setattr(capabilities, "_get_openvino_version", lambda: "2026.1.0")
    monkeypatch.setattr(capabilities, "_get_npu_driver_version", lambda: "32.0.100.4404")
    monkeypatch.setattr(capabilities, "_resolve_ffmpeg_binary", lambda: None)
    monkeypatch.setattr(capabilities, "_resolve_ollama_binary", lambda: None)

    inventory = capabilities.detect_extraction_capabilities(use_cache=False)
    prereqs = inventory["extraction_prereqs"]

    assert prereqs["npu_driver_version"] == "32.0.100.4404"
    assert prereqs["npu_driver_ok"] is False
    assert "32.0.100.4724" in prereqs["npu_driver_setup_hint"]


def test_inventory_flags_vulnerable_transformers_runtime(monkeypatch) -> None:
    """transformers 4.x remains optional but must be flagged when installed."""
    from src.lib.extraction import capabilities

    monkeypatch.setattr(capabilities, "_get_transformers_version", lambda: "4.57.6")
    monkeypatch.setattr(capabilities, "_get_optimum_intel_version", lambda: "1.27.0")
    monkeypatch.setattr(capabilities, "_get_openvino_version", lambda: "2026.0.0")
    monkeypatch.setattr(capabilities, "_get_npu_driver_version", lambda: "32.0.100.4724")

    inventory = capabilities.detect_extraction_capabilities(use_cache=False)
    prereqs = inventory["extraction_prereqs"]

    assert prereqs["transformers_ok"] is False
    assert "transformers>=5.0.0" in prereqs["transformers_setup_hint"]


def test_npu_driver_version_parses_compute_accelerator_block(monkeypatch) -> None:
    from src.lib.extraction import capabilities

    class _Result:
        returncode = 0
        stdout = """
Published Name:     oem318.inf
Original Name:      npu.inf
Provider Name:      Intel Corporation
Class Name:         ComputeAccelerator
Driver Version:     10/29/2025 32.0.100.4404
Signer Name:        Microsoft Windows Hardware Compatibility Publisher
"""

    monkeypatch.setattr(capabilities.sys, "platform", "win32")
    monkeypatch.setattr(capabilities.subprocess, "run", lambda *_args, **_kwargs: _Result())

    assert capabilities._get_npu_driver_version() == "32.0.100.4404"


def test_npu_driver_version_uses_newest_matching_driver_store_package(monkeypatch) -> None:
    from src.lib.extraction import capabilities

    class _Result:
        returncode = 0
        stdout = """
Published Name:     oem318.inf
Original Name:      npu.inf
Provider Name:      Intel Corporation
Class Name:         ComputeAccelerator
Driver Version:     10/29/2025 32.0.100.4404

Published Name:     oem29.inf
Original Name:      npu.inf
Provider Name:      Intel Corporation
Class Name:         ComputeAccelerator
Driver Version:     03/19/2026 32.0.100.4724
"""

    monkeypatch.setattr(capabilities.sys, "platform", "win32")
    monkeypatch.setattr(capabilities.subprocess, "run", lambda *_args, **_kwargs: _Result())

    assert capabilities._get_npu_driver_version() == "32.0.100.4724"


def test_inventory_reports_glm_ocr_availability(monkeypatch) -> None:
    """GLM-OCR availability is detected by name in Ollama's tag list."""
    from src.lib.extraction import capabilities

    monkeypatch.setattr(capabilities.shutil, "which", lambda name: "ollama.exe" if name == "ollama" else None)
    monkeypatch.setattr(
        capabilities,
        "_run_json_command",
        lambda _cmd, timeout_s=10: {"models": [{"name": "glm-ocr:latest"}, {"name": "qwen3:8b"}]},
    )
    monkeypatch.setattr(capabilities, "_ollama_show_text", lambda *_args, **_kwargs: "")

    inventory = capabilities.detect_extraction_capabilities(use_cache=False)

    assert inventory["ollama"]["glm_ocr_available"] is True


def test_inventory_reports_glm_ocr_missing(monkeypatch) -> None:
    from src.lib.extraction import capabilities

    monkeypatch.setattr(capabilities.shutil, "which", lambda name: "ollama.exe" if name == "ollama" else None)
    monkeypatch.setattr(
        capabilities,
        "_run_json_command",
        lambda _cmd, timeout_s=10: {"models": [{"name": "qwen3:8b"}]},
    )
    monkeypatch.setattr(capabilities, "_ollama_show_text", lambda *_args, **_kwargs: "")

    inventory = capabilities.detect_extraction_capabilities(use_cache=False)

    assert inventory["ollama"]["glm_ocr_available"] is False


def test_detection_cache_reuses_expensive_probe_but_refreshes_policy(monkeypatch, tmp_path: Path) -> None:
    from src.lib.extraction import capabilities

    prefs = tmp_path / "preferences.yaml"
    prefs.write_text("airplane_mode:\n  enabled: false\n", encoding="utf-8")
    calls = {"list": 0, "show": 0}

    monkeypatch.setattr(capabilities, "get_preferences_path", lambda: prefs)
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: "ollama.exe" if name == "ollama" else None)

    def fake_json_command(_cmd: list[str], timeout_s: int = 10):
        calls["list"] += 1
        assert timeout_s == 1
        return {"models": [{"name": "gemma4:latest", "details": {"families": ["gemma4"]}}]}

    def fake_show_text(_model: str, **kwargs):
        calls["show"] += 1
        assert kwargs["timeout_s"] == 1
        return "Capabilities\n  vision\n"

    monkeypatch.setattr(capabilities, "_run_json_command", fake_json_command)
    monkeypatch.setattr(capabilities, "_ollama_show_text", fake_show_text)

    first = capabilities.detect_extraction_capabilities(probe_timeout_s=1)
    prefs.write_text("airplane_mode:\n  enabled: true\n", encoding="utf-8")
    second = capabilities.detect_extraction_capabilities(probe_timeout_s=1)

    assert first["policy"]["airplane_mode_enabled"] is False
    assert second["policy"]["airplane_mode_enabled"] is True
    assert calls == {"list": 1, "show": 1}
