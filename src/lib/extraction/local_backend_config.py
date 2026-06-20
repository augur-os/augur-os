"""Configuration helpers for local OCR and ASR extraction backends."""

from __future__ import annotations

from dataclasses import dataclass
import os

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_OCR_MODEL = "glm-ocr"
DEFAULT_ASR_MODEL = "whisper-large-v3-int8-ov"
DEFAULT_FAST_WHISPER_MODEL = "Systran/faster-whisper-small"
FAST_WHISPER_MODEL_ENV = "AUGUR_FAST_WHISPER_MODEL"


@dataclass(frozen=True)
class LocalOcrSettings:
    model: str = DEFAULT_OCR_MODEL
    generate_url: str = "http://localhost:11434/api/generate"
    timeout_s: int = 60


def _profile_for_task(task: str):
    try:
        import src.lib.ai as ai_api

        config = ai_api.load_llm_config()
    except Exception:
        return None

    task_profile = config.tasks.get(task) if config.tasks else None
    if isinstance(task_profile, str):
        profile = config.profiles.get(task_profile)
        if profile is not None:
            return profile

    try:
        return ai_api.resolve_llm_profile(config, task=task)
    except Exception:
        return None


def _ollama_generate_url(base_url: str | None) -> str:
    base = (base_url or DEFAULT_OLLAMA_BASE_URL).strip().rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3].rstrip("/")
    return f"{base}/api/generate"


def get_local_ocr_settings() -> LocalOcrSettings:
    profile = _profile_for_task("document_ocr")
    if profile is None:
        return LocalOcrSettings()

    model = (getattr(profile, "model", None) or DEFAULT_OCR_MODEL).strip() or DEFAULT_OCR_MODEL
    timeout_s = int(getattr(profile, "timeout_s", None) or 60)
    return LocalOcrSettings(
        model=model,
        generate_url=_ollama_generate_url(getattr(profile, "base_url", None)),
        timeout_s=timeout_s,
    )


def get_local_asr_model_name() -> str:
    profile = _profile_for_task("document_asr")
    if profile is None:
        return DEFAULT_ASR_MODEL
    model = (getattr(profile, "model", None) or DEFAULT_ASR_MODEL).strip()
    return model or DEFAULT_ASR_MODEL


def get_local_fast_whisper_model_name() -> str:
    model = (os.environ.get(FAST_WHISPER_MODEL_ENV) or DEFAULT_FAST_WHISPER_MODEL).strip()
    return model or DEFAULT_FAST_WHISPER_MODEL


def local_model_dir_name(model_name: str) -> str:
    normalized = model_name.replace("\\", "/").strip("/")
    return normalized.rsplit("/", 1)[-1] or DEFAULT_ASR_MODEL


def openvino_repo_id_for_model(model_name: str) -> str:
    model = model_name.strip() or DEFAULT_ASR_MODEL
    return model if "/" in model else f"OpenVINO/{model}"
