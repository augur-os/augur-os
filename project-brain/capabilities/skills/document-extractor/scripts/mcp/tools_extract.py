"""Document extraction MCP tools.

Provides extract-document, submit-extract-document-result,
extract-document-batch, and get-extraction-status tools.
"""
from __future__ import annotations

import json
import platform
import sys
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
def _ensure_project_paths(start: Path) -> Path:
    for candidate in (start.parent, *start.parents):
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "src" / "config" / "paths.py").is_file()
        ):
            for path in (candidate / "src" / "mcp", candidate, candidate / "project-brain"):
                text = str(path)
                if text not in sys.path:
                    sys.path.insert(0, text)
            return candidate
    raise RuntimeError(f"Unable to locate Augur project root from {start}")


_project_root = _ensure_project_paths(Path(__file__).resolve())

from src.lib.extraction import (
    ExtractionResult,
    detect_available_tier,
    detect_extraction_capabilities,
    extract,
    get_extraction_policy,
    merge_llm_results,
)
from src.lib.extraction.ollama_client import get_vision_client
from src.logging import get_entity_logger

from ._shared import load_skill_config, tool_annotations

logger = get_entity_logger("document-extractor")

# ---------------------------------------------------------------------------
# In-memory store for pending LLM results
# ---------------------------------------------------------------------------
_pending_results: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Pure implementation functions (_impl suffix)
# ---------------------------------------------------------------------------

def _result_to_dict(result: ExtractionResult, include_metadata: bool = True) -> dict:
    """Convert ExtractionResult to a JSON-serializable dict, stripping None fields."""
    d: dict[str, Any] = {
        "success": result.success,
        "markdown": result.markdown,
        "title": result.title,
        "tier_used": result.tier_used,
        "format": result.format,
        "ocr_applied": result.ocr_applied,
    }

    if include_metadata:
        d["size_bytes"] = result.size_bytes
        d["extraction_time"] = result.extraction_time

    if result.needs_llm:
        d["needs_llm"] = result.needs_llm
    if result.llm_requests is not None:
        d["llm_requests"] = result.llm_requests
    if result.partial_markdown is not None:
        d["partial_markdown"] = result.partial_markdown
    if result.error is not None:
        d["error"] = result.error

    return d


def extract_document_impl(
    path: str,
    max_tier: int = 1,
    include_metadata: bool = True,
) -> dict:
    """Extract a document to Markdown.

    Args:
        path: Filesystem path to the document.
        max_tier: Maximum extraction tier (0=parse, 1=LLM OCR).
        include_metadata: Include size_bytes and extraction_time in response.

    Returns:
        Dict with extraction result.
    """
    policy = get_extraction_policy()
    result = extract(
        path,
        max_tier=max_tier,
        allow_cloud=bool(policy.get("cloud_escalation_allowed", False)),
    )

    # Store partial result for possible LLM follow-up
    if result.needs_llm and result.partial_markdown:
        _pending_results[path] = {
            "partial_markdown": result.partial_markdown,
            "llm_requests": result.llm_requests,
        }

    return _result_to_dict(result, include_metadata=include_metadata)


def submit_result_impl(
    request_id: str,
    result_text: str,
    source_path: str,
) -> dict:
    """Submit LLM-processed result and merge with partial extraction.

    Args:
        request_id: The request ID from the original extraction.
        result_text: The LLM-generated text to merge.
        source_path: Original file path for lookup.

    Returns:
        Dict with merged markdown.
    """
    pending = _pending_results.get(source_path)
    partial = pending["partial_markdown"] if pending else "[Image: page requires OCR]"

    merged = merge_llm_results(partial, {"0": result_text})

    # Clean up pending entry
    _pending_results.pop(source_path, None)

    return {
        "success": True,
        "merged_markdown": merged,
        "request_id": request_id,
        "source_path": source_path,
    }


def extract_batch_impl(
    paths_json: str,
    max_tier: int = 1,
) -> dict:
    """Extract multiple documents in batch.

    Args:
        paths_json: JSON array of file paths.
        max_tier: Maximum extraction tier.

    Returns:
        Dict with results array and summary.
    """
    try:
        paths = json.loads(paths_json)
    except (json.JSONDecodeError, TypeError) as exc:
        return {
            "success": False,
            "results": [],
            "llm_requests": [],
            "summary": {"total": 0, "completed": 0, "needs_llm": 0, "failed": 0},
            "error": f"Invalid paths_json: {exc}",
        }

    results = []
    all_llm_requests = []
    completed = 0
    needs_llm = 0
    failed = 0

    for idx, path in enumerate(paths):
        result = extract(path, max_tier=max_tier)
        result_dict = _result_to_dict(result)
        result_dict["path"] = path
        results.append(result_dict)

        if result.success:
            if result.needs_llm:
                needs_llm += 1
                # Prefix request IDs for batch disambiguation
                if result.llm_requests:
                    for req in result.llm_requests:
                        req["request_id"] = f"batch-{idx}-{req.get('request_id', '0')}"
                    all_llm_requests.extend(result.llm_requests)
                # Store partial for later submission
                if result.partial_markdown:
                    _pending_results[path] = {
                        "partial_markdown": result.partial_markdown,
                        "llm_requests": result.llm_requests,
                    }
            else:
                completed += 1
        else:
            failed += 1

    return {
        "success": failed < len(paths),  # True if at least one succeeded
        "results": results,
        "llm_requests": all_llm_requests,
        "summary": {
            "total": len(paths),
            "completed": completed,
            "needs_llm": needs_llm,
            "failed": failed,
        },
    }


def get_extraction_status_impl() -> dict:
    """Get extraction capability status.

    Returns:
        Dict with format support, LLM integrations, tier info.
    """
    def _installed_version(package_name: str) -> str | None:
        try:
            return package_version(package_name)
        except PackageNotFoundError:
            return None

    ai_pc = detect_extraction_capabilities()
    md_version = _installed_version("markitdown")
    pymupdf_version = _installed_version("pymupdf")
    mlx_vlm_version = _installed_version("mlx-vlm")
    markitdown_available = md_version is not None
    ollama = ai_pc.get("ollama", {})
    prereqs = ai_pc.get("extraction_prereqs", {})
    ocr_available = bool(ollama.get("glm_ocr_available"))

    # Format support — MarkItDown handles these
    formats = {
        "pdf_text": markitdown_available and pymupdf_version is not None,
        "docx": markitdown_available,
        "pptx": markitdown_available,
        "xlsx": markitdown_available,
        "html": markitdown_available,
        "csv": markitdown_available,
        "json": markitdown_available,
        "text": True,  # Always supported via plain read
        "images": markitdown_available or ocr_available,
        "audio": bool(ai_pc.get("transcription_ready")),
        "pdf_scanned": ocr_available,
    }

    # LLM integrations
    vision_client = get_vision_client()
    vision_available = vision_client is not None

    llm_integrations = {
        "vision_available": vision_available,
        "vision_model": None,  # model is configured in llm.yaml, not auto-detected
        "ollama_glm_ocr": {
            "installed": bool(ollama.get("installed")),
            "available": ocr_available,
            "model": "glm-ocr",
        },
    }

    tier = detect_available_tier()
    dependencies = {
        "markitdown": {"installed": markitdown_available, "version": md_version},
        "pymupdf": {"installed": pymupdf_version is not None, "version": pymupdf_version},
        "mlx_vlm": {"installed": mlx_vlm_version is not None, "version": mlx_vlm_version},
    }
    capabilities = {
        "document_parsing_ready": markitdown_available,
        "text_pdf_extraction_ready": markitdown_available and pymupdf_version is not None,
        "ocr_engine_ready": ocr_available,
        "advanced_vision_ready": vision_available,
        "baseline_document_stack_ready": markitdown_available and pymupdf_version is not None,
    }

    return {
        "formats": formats,
        "dependencies": dependencies,
        "capabilities": capabilities,
        "llm_integrations": llm_integrations,
        "ai_pc": ai_pc,
        "airplane_mode": ai_pc["policy"],
        "local_agent_ready": ai_pc["local_agent_ready"],
        "transcription_ready": ai_pc["transcription_ready"],
        "ocr_engine": "glm-ocr",
        "ocr_engine_available": ocr_available,
        "asr_engine": "openvino-whisper" if sys.platform != "darwin" else "faster-whisper",
        "os_default_chain": _build_os_default_chain(),
        "prereqs": prereqs,
        "openvino": ai_pc.get("openvino", {"devices": ["NPU", "GPU", "CPU"], "live_device": None}),
        "cloud": {
            "passive_agent_cli": "document-ocr-cloud",
            "available": bool(ai_pc["policy"].get("cloud_escalation_allowed")),
        },
        "tier_available": tier,
        "markitdown_version": md_version or "builtin-fallback",
        "platform": platform.system(),
    }


def _build_os_default_chain() -> dict[str, list[str]]:
    ocr_chain = ["ollama-glm-ocr", "passive-agent-vision"]
    if sys.platform == "darwin":
        transcription_chain = ["faster-whisper", "openvino-whisper"]
    else:
        transcription_chain = ["openvino-whisper"]
    return {"ocr": ocr_chain, "transcription": transcription_chain}


def extract_audio_impl(
    audio_path: str,
    provider: str | None = None,
    model: str | None = None,
    language: str | None = None,
    speaker_labels: bool = False,
) -> dict[str, Any]:
    """Transcribe an audio file and return the provider-neutral payload."""
    from src.lib.extraction.transcription import transcribe, transcribe_audio

    config = load_skill_config()
    transcription = config.get("transcription", {}) if isinstance(config, dict) else {}
    selected_provider = provider or transcription.get("provider") or "whisper-cpp"
    options = {
        "model": model or transcription.get("model") or "medium.en",
        "language": language or transcription.get("language") or "en",
        "speaker_labels": speaker_labels or bool(transcription.get("speaker_labels", False)),
    }
    try:
        transcript = transcribe(Path(audio_path), provider=selected_provider, options=options)
    except (RuntimeError, ValueError):
        fallback = transcribe_audio(audio_path)
        if not fallback.success:
            raise
        return {
            "success": True,
            "text": fallback.transcript,
            "segments": [],
            "duration_seconds": fallback.duration_s or 0.0,
            "language": fallback.language,
            "provider": fallback.method,
            "provider_version": fallback.backend,
            "speaker_count": 0,
        }
    return {
        "success": True,
        "text": transcript.text,
        "segments": [
            {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "speaker": segment.speaker,
            }
            for segment in transcript.segments
        ],
        "duration_seconds": transcript.duration_seconds,
        "language": transcript.language,
        "provider": transcript.provider,
        "provider_version": transcript.provider_version,
        "speaker_count": transcript.speaker_count(),
    }


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------

def register_extract_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any = None,
) -> None:
    """Register document extraction MCP tools."""

    @mcp.tool(
        name="extract-document",
        annotations=tool_annotations(
            {
                "title": "Extract Document",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def extract_document_tool(
        path: str,
        max_tier: int = 1,
        include_metadata: bool = True,
    ) -> str:
        """Extract a document to Markdown using MarkItDown with optional LLM OCR.

        Args:
            path: Filesystem path to the document.
            max_tier: Maximum extraction tier (0=parse only, 1=LLM OCR).
            include_metadata: Include size_bytes and extraction_time.

        Returns:
            JSON with {success, markdown, title, tier_used, format, ...}
        """
        if metrics:
            metrics.track_tool("extract_document", skill="document-extractor")
        return json.dumps(extract_document_impl(path, max_tier, include_metadata))

    @mcp.tool(
        name="submit-extract-document-result",
        annotations=tool_annotations(
            {
                "title": "Submit Extraction Result",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def submit_extract_result_tool(
        request_id: str,
        result_text: str,
        source_path: str,
    ) -> str:
        """Submit LLM-processed OCR result for a previous extraction.

        Args:
            request_id: Request ID from the original extraction's llm_requests.
            result_text: The LLM-generated text (OCR output).
            source_path: Original file path.

        Returns:
            JSON with {success, merged_markdown, request_id, source_path}
        """
        if metrics:
            metrics.track_tool("submit_extract_result", skill="document-extractor")
        return json.dumps(submit_result_impl(request_id, result_text, source_path))

    @mcp.tool(
        name="extract-document-batch",
        annotations=tool_annotations(
            {
                "title": "Batch Extract Documents",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def extract_batch_tool(
        paths_json: str,
        max_tier: int = 1,
    ) -> str:
        """Extract multiple documents to Markdown in batch.

        Args:
            paths_json: JSON array of filesystem paths.
            max_tier: Maximum extraction tier (0=parse, 1=LLM OCR).

        Returns:
            JSON with {success, results[], llm_requests[], summary}
        """
        if metrics:
            metrics.track_tool("extract_document_batch", skill="document-extractor")
        return json.dumps(extract_batch_impl(paths_json, max_tier))

    @mcp.tool(
        name="get-extraction-status",
        annotations=tool_annotations(
            {
                "title": "Get Extraction Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_extraction_status_tool() -> str:
        """Get extraction capability status — supported formats, LLM availability, tier info.

        Returns:
            JSON with {formats, llm_integrations, tier_available, markitdown_version, platform}
        """
        if metrics:
            metrics.track_tool("get_extraction_status", skill="document-extractor")
        return json.dumps(get_extraction_status_impl())

    _register_extract_audio(mcp, mcp_tool_interceptor, metrics)


def _register_extract_audio(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any] | None = None,
    metrics: Any = None,
) -> None:
    interceptor = mcp_tool_interceptor or (lambda fn: fn)

    @mcp.tool(
        name="extract-audio",
        annotations=tool_annotations(
            {
                "title": "Extract Audio",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    @interceptor
    def extract_audio_tool(
        audio_path: str,
        provider: str | None = None,
        model: str | None = None,
        language: str | None = None,
        speaker_labels: bool = False,
    ) -> str:
        """Transcribe an audio file to text using the configured provider."""
        if metrics:
            metrics.track_tool("extract_audio", skill="document-extractor")
        return json.dumps(
            extract_audio_impl(
                audio_path=audio_path,
                provider=provider,
                model=model,
                language=language,
                speaker_labels=speaker_labels,
            )
        )
