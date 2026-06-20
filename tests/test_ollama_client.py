"""Auto-generated importability test for ollama_client."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_ollama_client_importable():
    """Verify that ollama_client can be imported without errors."""
    import src.lib.extraction.ollama_client

    assert src.lib.extraction.ollama_client is not None
