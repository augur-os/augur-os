"""LLM vision client for document extraction — uses unified LLM provider."""

from __future__ import annotations

from src.logging import get_entity_logger

logger = get_entity_logger("lib.extraction.ollama_client")

try:
    from src.lib.ai import get_llm_client
except ImportError:
    get_llm_client = None  # type: ignore[assignment]


def get_vision_client():
    """Resolve an LLMClient for document OCR via the unified config.

    Returns an LLMClient instance or None if config resolution fails.
    The caller should use client.generate_with_vision() for image inputs.
    """
    if get_llm_client is None:
        logger.warning("LLM config module not available for document extraction")
        return None

    try:
        return get_llm_client("document_ocr")
    except Exception as exc:
        logger.warning("Failed to resolve vision LLM client: %s", exc)
        return None
