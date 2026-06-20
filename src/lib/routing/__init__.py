"""Single decision point for (mode x activity x OS) -> engine routing.

See docs/superpowers/specs/2026-05-22-offline-mode-routing-simplification-design.md
"""

from src.lib.routing.engines import (
    ChatLaunchSpec,
    EngineAvailability,
    OcrResult,
)
from src.lib.routing.matrix import ROUTES, RoutingError, engine_id_for
from src.lib.routing.resolver import (
    detect_mode,
    resolve_chat,
    resolve_mode,
    run_ocr,
    transcribe,
)

__all__ = [
    "ROUTES",
    "RoutingError",
    "engine_id_for",
    "detect_mode",
    "resolve_mode",
    "resolve_chat",
    "run_ocr",
    "transcribe",
    "ChatLaunchSpec",
    "EngineAvailability",
    "OcrResult",
]
