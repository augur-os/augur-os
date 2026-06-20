"""MCP tools for the audio-ingest skill."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _ensure_project_paths(start: Path) -> Path:
    for candidate in (start.parent, *start.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "src" / "config" / "paths.py").is_file():
            for path in (candidate / "src" / "mcp", candidate, candidate / "project-brain"):
                text = str(path)
                if text not in sys.path:
                    sys.path.insert(0, text)
            return candidate
    raise RuntimeError(f"Unable to locate Augur project root from {start}")


_PROJECT_ROOT = _ensure_project_paths(Path(__file__).resolve())
_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from src.config.paths import get_vault_dir  # noqa: E402
from src.lib.brain_layout import brain_capture_dir  # noqa: E402
from src.lib.frontmatter_utils import parse_frontmatter  # noqa: E402
from attendee_resolver import extract_speaker_names_from_text, infer_attendee_count, resolve_speakers  # noqa: E402
from classifier import build_llm_dispatch_payload, classify_heuristic  # noqa: E402
from note_writer import write_audio_note  # noqa: E402
from voice_memo_source import latest_voice_memo  # noqa: E402
from src.lib.ingest.note_index_refresh import refresh_notes_browse_index  # noqa: E402


def _load_skill_config() -> dict:
    import yaml

    config_path = Path(__file__).resolve().parents[2] / "config.yaml"
    if not config_path.exists():
        return {}
    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


def register(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any] | None = None,
    metrics: Any = None,
) -> None:
    """Register the audio-ingest MCP tools."""
    interceptor = mcp_tool_interceptor or (lambda fn: fn)

    @mcp.tool(name="audio-classify")
    @interceptor
    def audio_classify(
        transcript_text: str,
        segments_json: str = "[]",
        duration_seconds: float = 0.0,
        speaker_count: int = 0,
    ) -> dict[str, Any]:
        if metrics:
            metrics.track_tool("audio_classify", skill="audio-ingest")
        config = _load_skill_config()
        classifier_config = config.get("classifier", {}) if isinstance(config, dict) else {}
        threshold = float(classifier_config.get("heuristic_threshold", 0.9))
        llm_assisted = bool(classifier_config.get("llm_assisted", True))
        segments = json.loads(segments_json) if segments_json else []
        result = classify_heuristic(
            text=transcript_text,
            segments=segments,
            duration_seconds=duration_seconds,
            speaker_count=speaker_count,
        )
        if result["confidence"] >= threshold or not llm_assisted:
            return {"success": True, **result}
        return build_llm_dispatch_payload(
            text=transcript_text,
            duration_seconds=duration_seconds,
            speaker_count=speaker_count,
        )

    @mcp.tool(name="submit-audio-classify-result")
    @interceptor
    def submit_audio_classify_result(type_: str, confidence: float, reasoning: str) -> dict[str, Any]:
        if metrics:
            metrics.track_tool("submit_audio_classify_result", skill="audio-ingest")
        if type_ not in ("voice-memo", "meeting"):
            return {"success": False, "error": f"unexpected type: {type_}"}
        return {
            "success": True,
            "type": type_,
            "confidence": float(confidence),
            "reasoning": reasoning,
            "source": "llm",
        }

    @mcp.tool(name="voice-memo-latest")
    @interceptor
    def voice_memo_latest(
        copy_to: str = "",
        since_seconds: int = 0,
    ) -> dict[str, Any]:
        if metrics:
            metrics.track_tool("voice_memo_latest", skill="audio-ingest")
        result = latest_voice_memo(
            since_seconds=since_seconds or None,
            copy_to=copy_to or None,
        )
        return result.to_dict()

    @mcp.tool(name="audio-ingest-write")
    @interceptor
    def audio_ingest_write(
        audio_path: str,
        note_type: str,
        title: str,
        transcript_text: str,
        segments_json: str = "[]",
        duration_seconds: float = 0.0,
        provider: str = "whisper-cpp",
        provider_version: str = "unknown",
        consume_source: bool = False,
    ) -> dict[str, Any]:
        if metrics:
            metrics.track_tool("audio_ingest_write", skill="audio-ingest")
        if note_type not in ("voice-memo", "meeting"):
            return {"success": False, "error": f"unexpected note_type: {note_type}"}

        segments = json.loads(segments_json) if segments_json else []
        attendee_slugs: list[str] = []
        config = _load_skill_config()
        attendee_config = config.get("attendee_resolution", {}) if isinstance(config, dict) else {}
        if note_type == "meeting" and attendee_config.get("enabled", True):
            attendee_slugs = resolve_speakers(extract_speaker_names_from_text(transcript_text))
        attendee_count = (
            infer_attendee_count(
                text=transcript_text,
                segments=segments,
                attendee_slugs=attendee_slugs,
                duration_seconds=duration_seconds,
            )
            if note_type == "meeting"
            else 0
        )

        # Captures land in the brain capture dir (knowledge/notes legacy;
        # inbox/ domains), matching the other capture writers.
        vault_dir = get_vault_dir()
        notes_dir = brain_capture_dir(vault_dir)
        path = write_audio_note(
            notes_dir=notes_dir,
            audio_path=Path(audio_path),
            note_type=note_type,
            title=title,
            transcript_text=transcript_text,
            segments=segments,
            duration_seconds=duration_seconds,
            provider=provider,
            provider_version=provider_version,
            attendee_slugs=attendee_slugs,
            attendee_count_hint=attendee_count,
            consume_source=consume_source,
            vault_dir=vault_dir,
        )
        metadata, _ = parse_frontmatter(path, include_sidecar_config=False)
        browse_index = refresh_notes_browse_index(vault_dir=vault_dir)
        return {
            "success": True,
            "path": str(path),
            "audio_path": str(metadata.get("audio_path") or audio_path),
            "note_type": note_type,
            "attendee_slugs": attendee_slugs,
            "attendee_count": attendee_count,
            "browse_index": browse_index.to_dict(),
        }
