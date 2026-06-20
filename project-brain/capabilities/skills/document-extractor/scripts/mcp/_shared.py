"""Shared helpers for document-extractor MCP tools."""
import logging
from pathlib import Path

import yaml

logger = logging.getLogger("document-extractor")

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


def load_skill_config() -> dict:
    """Load the document-extractor skill config."""
    if not _CONFIG_PATH.exists():
        return {}
    return yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}


def tool_annotations(hints: dict) -> dict:
    """Build MCP tool annotation hints."""
    return {"annotations": {"hints": hints}}
