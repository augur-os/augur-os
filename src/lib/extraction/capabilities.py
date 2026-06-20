"""AI PC extraction capability inventory and policy detection."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from typing import Any

from src.config.paths import get_cache_dir
from src.config.preferences import get_preferences_path, load_preferences
from src.lib.extraction.local_backend_config import (
    get_local_asr_model_name,
    get_local_fast_whisper_model_name,
    local_model_dir_name,
)

_CAPABILITY_CACHE_TTL_S = 5.0
_DEFAULT_PROBE_TIMEOUT_S = 2
OPENVINO_2026_1_NPU_DRIVER_FLOOR = "32.0.100.4724"
_PACKAGE_NAMES = [
    "markitdown",
    "pymupdf",
    "openvino",
    "openvino-genai",
    "faster-whisper",
    "imageio-ffmpeg",
    "onnxruntime",
    "onnxruntime-directml",
    "pdf2image",
]
_CAPABILITY_CACHE: dict[str, Any] = {
    "fetched_at": 0.0,
    "probe_timeout_s": None,
    "probe_vision_models": None,
    "value": None,
}


def _package_version(name: str) -> str | None:
    """Return an installed Python package version, or None when unavailable."""
    try:
        return package_version(name)
    except PackageNotFoundError:
        return None


def _get_transformers_version() -> str | None:
    return _package_version("transformers")


def _get_optimum_intel_version() -> str | None:
    return _package_version("optimum-intel")


def _get_openvino_version() -> str | None:
    return _package_version("openvino")


def _get_npu_driver_version() -> str | None:
    """Return the Intel NPU driver version on Windows, or None when unavailable."""
    if sys.platform != "win32":
        return None
    try:
        result = subprocess.run(
            ["pnputil", "/enum-drivers"],
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout:
        return None

    versions: list[str] = []
    blocks = re.split(r"\r?\n\s*\r?\n", result.stdout)
    for block in blocks:
        lowered = block.lower()
        if "provider name" in lowered and "intel" not in lowered:
            continue
        if not ("npu" in lowered or "computeaccelerator" in lowered or "ai boost" in lowered):
            continue
        driver_line = next(
            (line for line in block.splitlines() if "driver version" in line.lower()),
            "",
        )
        matches = re.findall(r"\d+(?:\.\d+){2,}", driver_line)
        if matches:
            versions.append(matches[-1])
    if not versions:
        return None
    return max(versions, key=_version_parts)


def _version_parts(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", value))


def _semver_at_least(actual: str | None, floor: str) -> bool:
    if not actual:
        return False

    actual_parts = _version_parts(actual)
    floor_parts = _version_parts(floor)
    if len(actual_parts) < len(floor_parts):
        actual_parts = (*actual_parts, *([0] * (len(floor_parts) - len(actual_parts))))
    return actual_parts >= floor_parts


def npu_driver_ready_for_openvino() -> bool:
    """Return whether the installed Intel NPU driver satisfies OpenVINO 2026.1."""
    if sys.platform != "win32":
        return True
    return _semver_at_least(_get_npu_driver_version(), OPENVINO_2026_1_NPU_DRIVER_FLOOR)


def _transformers_runtime_safe(version: str | None) -> bool:
    return version is None or _semver_at_least(version, "5.0.0")


def _optional_optimum_intel_safe(version: str | None) -> bool:
    return version is None or _semver_at_least(version, "1.25.2")


def _build_extraction_prereqs() -> dict[str, Any]:
    transformers_v = _get_transformers_version()
    optimum_v = _get_optimum_intel_version()
    openvino_v = _get_openvino_version()
    npu_v = _get_npu_driver_version()
    npu_ok = npu_driver_ready_for_openvino()

    return {
        "transformers_version": transformers_v,
        "transformers_required": False,
        "transformers_ok": _transformers_runtime_safe(transformers_v),
        "transformers_setup_hint": (
            "Remove transformers 4.x from this environment or install transformers>=5.0.0; "
            "Augur's OpenVINO Whisper runtime uses preconverted openvino-genai models."
            if not _transformers_runtime_safe(transformers_v)
            else None
        ),
        "optimum_intel_version": optimum_v,
        "optimum_intel_required": False,
        "optimum_intel_ok": _optional_optimum_intel_safe(optimum_v),
        "optimum_intel_setup_hint": (
            "Remove outdated optimum-intel or upgrade it before using conversion tooling; "
            "it is not required for the preconverted OpenVINO Whisper runtime."
            if not _optional_optimum_intel_safe(optimum_v)
            else None
        ),
        "openvino_version": openvino_v,
        "openvino_ok": _semver_at_least(openvino_v, "2026.0.0"),
        "openvino_setup_hint": (
            "Upgrade openvino>=2026.0 for stateful Whisper and NPU compilation."
            if not _semver_at_least(openvino_v, "2026.0.0")
            else None
        ),
        "npu_driver_version": npu_v,
        "npu_driver_ok": npu_ok,
        "npu_driver_setup_hint": (
            f"NPU driver below floor {OPENVINO_2026_1_NPU_DRIVER_FLOOR}; install the latest Intel NPU driver."
            if sys.platform == "win32" and not npu_ok
            else None
        ),
    }


def _run_json_command(cmd: list[str], timeout_s: int = _DEFAULT_PROBE_TIMEOUT_S) -> dict[str, Any]:
    """Run a command and parse JSON stdout, returning an empty dict on failure."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=timeout_s,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}

    if result.returncode != 0:
        return {}

    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return {}

    return data if isinstance(data, dict) else {}


def _run_text_command(cmd: list[str], timeout_s: int = _DEFAULT_PROBE_TIMEOUT_S) -> str:
    """Run a command and return stdout, or an empty string on failure."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=timeout_s,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""

    return result.stdout if result.returncode == 0 else ""


def _candidate_exists(path: str) -> bool:
    """Wrapped for monkey-patching in tests."""
    return Path(path).exists()


def _ollama_candidate_paths() -> list[str]:
    """Return platform-specific Ollama binary candidates after PATH lookup."""
    if sys.platform == "win32":
        localappdata = os.environ.get("LOCALAPPDATA", "")
        programfiles = os.environ.get("PROGRAMFILES", "")
        userprofile = os.environ.get("USERPROFILE", "")
        out: list[str] = []
        if localappdata:
            out.append(str(Path(localappdata) / "Programs" / "Ollama" / "ollama.exe"))
        if programfiles:
            out.append(str(Path(programfiles) / "Ollama" / "ollama.exe"))
        if userprofile:
            out.append(str(Path(userprofile) / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe"))
        return out

    home = Path.home()
    return [
        "/opt/homebrew/bin/ollama",
        "/usr/local/bin/ollama",
        str(home / ".local" / "bin" / "ollama"),
    ]


def _resolve_ollama_binary() -> str | None:
    """Find Ollama via PATH first, then conservative platform defaults."""
    found = shutil.which("ollama")
    if found:
        return found
    for candidate in _ollama_candidate_paths():
        if _candidate_exists(candidate):
            return candidate
    return None


def _resolve_ffmpeg_binary() -> str | None:
    return shutil.which("ffmpeg") or shutil.which("avconv") or _packaged_ffmpeg_binary()


def _packaged_ffmpeg_binary() -> str | None:
    try:
        import imageio_ffmpeg

        path = Path(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        return None
    return str(path) if path.exists() else None


def _default_transcription_model_dir() -> Path:
    return get_cache_dir() / "models" / local_model_dir_name(get_local_asr_model_name())


def _default_faster_whisper_model_dir() -> Path:
    return get_cache_dir() / "models" / local_model_dir_name(get_local_fast_whisper_model_name())


def _transcription_model_candidates() -> list[Path]:
    if sys.platform == "darwin":
        return [_default_faster_whisper_model_dir(), _default_transcription_model_dir()]
    return [_default_transcription_model_dir()]


def _read_openvino_live_device(model_dir: Path) -> str | None:
    status_path = get_cache_dir() / "extraction" / "openvino-whisper-status.json"
    try:
        raw = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict) or raw.get("success") is not True:
        return None

    status_model = raw.get("model_dir")
    if isinstance(status_model, str) and Path(status_model) != model_dir:
        return None

    timestamp = raw.get("timestamp")
    if isinstance(timestamp, (int, float)) and time.time() - float(timestamp) > 86_400:
        return None

    device = raw.get("device")
    return device if isinstance(device, str) and device.strip() else None


def _ollama_show_text(
    model: str,
    *,
    binary: str | None = None,
    timeout_s: int = _DEFAULT_PROBE_TIMEOUT_S,
) -> str:
    """Return `ollama show <model>` stdout when Ollama is available."""
    binary = binary or _resolve_ollama_binary()
    if binary is None:
        return ""

    try:
        result = subprocess.run(
            [binary, "show", model],
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=timeout_s,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""

    return result.stdout if result.returncode == 0 else ""


def get_extraction_policy() -> dict[str, bool]:
    """Return extraction escalation policy derived from mutable preferences."""
    prefs = load_preferences(path=get_preferences_path())
    airplane_config = prefs.get("airplane_mode", {})
    airplane = bool(airplane_config.get("enabled") if isinstance(airplane_config, dict) else airplane_config)

    return {
        "airplane_mode_enabled": airplane,
        "cloud_escalation_allowed": not airplane,
        "local_agent_escalation_allowed": True,
    }


def _model_name(model: Any) -> str | None:
    if isinstance(model, str):
        return model
    if isinstance(model, dict):
        name = model.get("name") or model.get("model")
        return name if isinstance(name, str) else None
    return None


def _model_has_vision(model: dict[str, Any], show_text: str) -> bool:
    details = model.get("details", {})
    families = details.get("families", []) if isinstance(details, dict) else []
    family_text = " ".join(str(family).lower() for family in families)
    if any(token in family_text for token in ("vision", "llava", "clip")):
        return True
    return "vision" in show_text.lower()


def _is_glm_ocr_model(name: str) -> bool:
    return name.split(":", 1)[0].strip().lower() == "glm-ocr"


def _parse_ollama_list_text(text: str) -> list[str]:
    models: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        first_field = stripped.split(maxsplit=1)[0]
        if first_field.upper() == "NAME":
            continue
        models.append(first_field)
    return models


def _detect_extraction_capabilities_uncached(
    probe_timeout_s: int,
    *,
    probe_vision_models: bool,
) -> dict[str, Any]:
    """Detect local extraction packages, commands, and accelerators."""
    packages = {
        name: {
            "installed": (version := _package_version(name)) is not None,
            "version": version,
        }
        for name in _PACKAGE_NAMES
    }
    commands = {
        "ffmpeg": _resolve_ffmpeg_binary(),
        "ollama": _resolve_ollama_binary(),
    }

    ollama_models: list[str] = []
    ollama_vision_models: list[str] = []
    ollama_binary = commands["ollama"]
    if ollama_binary is not None:
        data = _run_json_command([ollama_binary, "list", "--json"], timeout_s=probe_timeout_s)
        raw_models = data.get("models", [])
        if isinstance(raw_models, list) and raw_models:
            for raw_model in raw_models:
                name = _model_name(raw_model)
                if name is None:
                    continue
                ollama_models.append(name)
                show_text = (
                    _ollama_show_text(
                        name,
                        binary=ollama_binary,
                        timeout_s=probe_timeout_s,
                    )
                    if probe_vision_models
                    else ""
                )
                if isinstance(raw_model, dict) and _model_has_vision(raw_model, show_text):
                    ollama_vision_models.append(name)
                elif probe_vision_models and not isinstance(raw_model, dict) and "vision" in show_text.lower():
                    ollama_vision_models.append(name)
        else:
            text = _run_text_command([ollama_binary, "list"], timeout_s=probe_timeout_s)
            for name in _parse_ollama_list_text(text):
                ollama_models.append(name)
                if not probe_vision_models:
                    continue
                show_text = _ollama_show_text(
                    name,
                    binary=ollama_binary,
                    timeout_s=probe_timeout_s,
                )
                if "vision" in show_text.lower():
                    ollama_vision_models.append(name)

    openvino_ready = packages["openvino"]["installed"]
    openvino_genai_ready = packages["openvino-genai"]["installed"]
    transcription_model_candidates = _transcription_model_candidates()
    transcription_model = next(
        (path for path in transcription_model_candidates if path.exists()),
        transcription_model_candidates[0],
    )
    if sys.platform == "darwin":
        transcription_backend_ready = packages["faster-whisper"]["installed"] or openvino_genai_ready
    else:
        transcription_backend_ready = openvino_genai_ready
    # whisper-cli (Homebrew whisper-cpp) is a first-class backend that bundles
    # its own ggml model store, so it satisfies readiness on its own.
    from src.lib.extraction.transcription import _has_whisper_cli_backend

    whisper_cli_ready = _has_whisper_cli_backend()
    transcription_ready = bool(
        commands["ffmpeg"] and (whisper_cli_ready or (transcription_backend_ready and transcription_model.exists()))
    )
    live_device = _read_openvino_live_device(_default_transcription_model_dir())
    glm_ocr_available = any(_is_glm_ocr_model(name) for name in ollama_models)
    local_agent_ready = bool(glm_ocr_available or ollama_vision_models or openvino_genai_ready)

    return {
        "platform": platform.system(),
        "packages": packages,
        "commands": commands,
        "ollama": {
            "installed": ollama_binary is not None,
            "binary": ollama_binary,
            "models": ollama_models,
            "vision_models": ollama_vision_models,
            "glm_ocr_available": glm_ocr_available,
        },
        "openvino_ready": openvino_ready,
        "openvino_genai_ready": openvino_genai_ready,
        "openvino": {
            "devices": ["NPU", "GPU", "CPU"],
            "live_device": live_device,
        },
        "transcription_ready": transcription_ready,
        "transcription_model": str(transcription_model) if transcription_model.exists() else None,
        "local_agent_ready": local_agent_ready,
        "extraction_prereqs": _build_extraction_prereqs(),
    }


def _with_fresh_policy(inventory: dict[str, Any]) -> dict[str, Any]:
    current = dict(inventory)
    current["policy"] = get_extraction_policy()
    return current


def clear_capability_cache() -> None:
    """Clear the in-process capability cache for tests and explicit refreshes."""
    _CAPABILITY_CACHE["fetched_at"] = 0.0
    _CAPABILITY_CACHE["probe_timeout_s"] = None
    _CAPABILITY_CACHE["probe_vision_models"] = None
    _CAPABILITY_CACHE["value"] = None


def detect_extraction_capabilities(
    *,
    use_cache: bool = True,
    probe_timeout_s: int = _DEFAULT_PROBE_TIMEOUT_S,
    probe_vision_models: bool = True,
) -> dict[str, Any]:
    """Detect local extraction capabilities with a short cache for status calls."""
    now = time.monotonic()
    cached = _CAPABILITY_CACHE["value"]
    if (
        use_cache
        and isinstance(cached, dict)
        and _CAPABILITY_CACHE["probe_timeout_s"] == probe_timeout_s
        and _CAPABILITY_CACHE["probe_vision_models"] == probe_vision_models
        and now - float(_CAPABILITY_CACHE["fetched_at"]) < _CAPABILITY_CACHE_TTL_S
    ):
        return _with_fresh_policy(cached)

    inventory = _detect_extraction_capabilities_uncached(
        probe_timeout_s,
        probe_vision_models=probe_vision_models,
    )
    if use_cache:
        _CAPABILITY_CACHE["fetched_at"] = now
        _CAPABILITY_CACHE["probe_timeout_s"] = probe_timeout_s
        _CAPABILITY_CACHE["probe_vision_models"] = probe_vision_models
        _CAPABILITY_CACHE["value"] = dict(inventory)

    return _with_fresh_policy(inventory)


__all__ = [
    "clear_capability_cache",
    "detect_extraction_capabilities",
    "get_extraction_policy",
]
