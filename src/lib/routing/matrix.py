"""The offline-mode routing matrix as data. The only place a route is defined."""

from __future__ import annotations

import sys
from typing import Literal

Activity = Literal["chat", "ocr", "transcript"]
Mode = Literal["regular", "offline"]


class RoutingError(RuntimeError):
    """Raised when no engine is mapped for an (activity, mode, os) cell."""


# (activity, mode) -> {os_key: engine_id}. "*" matches any OS.
ROUTES: dict[tuple[str, str], dict[str, str]] = {
    ("chat", "regular"): {"*": "agent-chat"},
    ("chat", "offline"): {"*": "ollama-llm"},
    ("ocr", "regular"): {"*": "agent-vision"},
    ("ocr", "offline"): {"*": "ollama-glm-ocr"},
    ("transcript", "regular"): {"*": "gemini-transcribe"},
    ("transcript", "offline"): {"win32": "openvino-whisper", "linux": "openvino-whisper", "darwin": "faster-whisper"},
}


def engine_id_for(activity: str, mode: str, os_name: str | None = None) -> str:
    """Return the engine id for a matrix cell, or raise RoutingError."""
    resolved_os = os_name or sys.platform
    cell = ROUTES.get((activity, mode))
    if cell is None:
        raise RoutingError(f"no route for activity={activity!r} mode={mode!r}")
    engine_id = cell.get(resolved_os)
    if engine_id is None:
        engine_id = cell.get("*")
    if engine_id is None:
        raise RoutingError(f"no engine for activity={activity!r} mode={mode!r} os={resolved_os!r}")
    return engine_id
