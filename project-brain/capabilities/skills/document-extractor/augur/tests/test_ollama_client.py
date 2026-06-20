"""Tests for document extractor LLM vision client."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from src.lib.extraction.ollama_client import get_vision_client


class TestGetVisionClient:
    def test_returns_client_from_config(self):
        mock_client = MagicMock()

        with patch("src.lib.extraction.ollama_client.get_llm_client", return_value=mock_client) as mock_get:
            result = get_vision_client()

        assert result is mock_client
        mock_get.assert_called_once_with("document_ocr")

    def test_returns_none_on_config_failure(self):
        with patch("src.lib.extraction.ollama_client.get_llm_client", side_effect=RuntimeError("no config")):
            result = get_vision_client()

        assert result is None
