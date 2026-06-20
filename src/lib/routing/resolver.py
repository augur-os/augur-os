"""Resolver + orchestrators: the public entry points for routed work."""

from __future__ import annotations

import sys
from typing import Any, cast

from src.lib.extraction.transcription import TranscriptResult
import src.lib.routing.engines as _engines_mod
from src.lib.routing.engines import (
    ChatLaunchSpec,
    OCR_ENGINES,
    OcrResult,
    TRANSCRIPT_ENGINES,
)
from src.lib.routing.matrix import Mode, engine_id_for


def _load_airplane_prefs() -> dict[str, Any]:
    try:
        from src.config.preferences import load_preferences

        prefs = load_preferences()
    except Exception:
        return {}
    airplane = prefs.get("airplane_mode", {})
    return airplane if isinstance(airplane, dict) else {"enabled": bool(airplane)}


def _is_online() -> bool:
    try:
        from src.mcp.augur_framework.tools.infrastructure.connectivity import (
            check_connectivity,
        )

        return bool(check_connectivity().get("online"))
    except Exception:
        # If we cannot even probe connectivity, assume online (regular).
        return True


def detect_mode() -> Mode:
    """Return 'offline' or 'regular' from airplane prefs + connectivity."""
    airplane = _load_airplane_prefs()
    # forced = user explicitly set the mode; trust `enabled` and skip auto-detect.
    if airplane.get("forced"):
        return "offline" if airplane.get("enabled", True) else "regular"
    if airplane.get("enabled"):
        return "offline"
    if airplane.get("auto_detect", True) and not _is_online():
        return "offline"
    return "regular"


def resolve_mode(mode: str | None) -> Mode:
    """Return the caller-provided mode, or detect it."""
    if mode in ("regular", "offline"):
        return cast(Mode, mode)
    return detect_mode()


def _attach_transcript_route(
    result: TranscriptResult,
    *,
    route_mode: Mode,
    route_engine_id: str,
    fallback_engine_id: str | None = None,
) -> TranscriptResult:
    result.route_mode = route_mode
    result.route_engine_id = route_engine_id
    result.fallback_engine_id = fallback_engine_id
    return result


def run_ocr(
    requests: list[dict],
    *,
    mode: str | None = None,
    os_name: str | None = None,
) -> OcrResult:
    """Run OCR requests through the engine the matrix selects for the cell."""
    if not requests:
        return OcrResult(success=True, results={}, engine_id="none")
    resolved_mode = resolve_mode(mode)
    engine_id = engine_id_for("ocr", resolved_mode, os_name)
    return OCR_ENGINES[engine_id].run(requests)


def transcribe(
    audio_path: str,
    *,
    model_dir: str | None = None,
    mode: str | None = None,
    os_name: str | None = None,
    gemini_timeout_s: float | None = None,
) -> TranscriptResult:
    """Transcribe audio via the matrix engine, with D1 fallback for regular mode.

    D1: if regular-mode transcript (gemini-transcribe) is unavailable or fails,
    fall back to the local offline whisper engine and flag needs_review with a
    'used local fallback' note.
    """
    resolved_mode = resolve_mode(mode)
    resolved_os = os_name or sys.platform
    engine_id = engine_id_for("transcript", resolved_mode, resolved_os)
    engine = TRANSCRIPT_ENGINES[engine_id]

    result = engine.run(audio_path, model_dir=model_dir, timeout_s=gemini_timeout_s)
    if engine_id == "gemini-transcribe" and not result.success:
        local_id = engine_id_for("transcript", "offline", resolved_os)
        fallback = TRANSCRIPT_ENGINES[local_id].run(audio_path, model_dir=model_dir)
        note = f"used local fallback ({local_id}); gemini unavailable: {result.error}"
        fallback.needs_review = True
        fallback.note = note
        if not fallback.success:
            fallback.error = fallback.error or note
        return _attach_transcript_route(
            fallback,
            route_mode=resolved_mode,
            route_engine_id=engine_id,
            fallback_engine_id=local_id,
        )
    return _attach_transcript_route(
        result,
        route_mode=resolved_mode,
        route_engine_id=engine_id,
    )


def resolve_chat(agent_id: str = "claude", *, mode: str | None = None) -> ChatLaunchSpec:
    """Resolve how chat should run for the current mode."""
    resolved_mode = resolve_mode(mode)
    engine_id = engine_id_for("chat", resolved_mode)
    if engine_id == "ollama-llm":
        return _engines_mod.build_ollama_launch_spec(agent_id)
    # regular mode: native/cloud AI client, no local launch needed, always ready.
    return ChatLaunchSpec(engine_id="agent-chat", use_local_ollama=False)
