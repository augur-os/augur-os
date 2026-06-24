"""Runner abstraction: daemon vs native AI-client adapters for standard loops."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


class LoopRunner:
    """Drives one standard loop. Subclasses bind to a runtime."""

    def run(self, loop: Any, **kwargs: Any) -> Any:  # pragma: no cover - interface
        raise NotImplementedError


def _resolve_orchestrate(injected: Callable[..., Any] | None = None) -> Callable[..., Any]:
    if injected is not None:
        return injected
    try:
        from . import orchestrator
    except ImportError:  # pragma: no cover - direct-path load
        import orchestrator  # type: ignore[no-redef]
    return orchestrator.orchestrate_run


class DaemonRunner(LoopRunner):
    """Deterministic, no-LLM runner: delegates to the orchestrator."""

    def __init__(self, orchestrate: Callable[..., Any] | None = None) -> None:
        self._orchestrate = orchestrate

    def run(self, loop: Any, **kwargs: Any) -> Any:
        return _resolve_orchestrate(self._orchestrate)(loop.loop_name or loop.id, **kwargs)


class _ClientRunner(LoopRunner):
    """Runs the loop natively in the active AI client: render a prompt-backed
    loop's prompt, or run an orchestrator-backed loop's scan-fix cycle in-session."""

    surface_name = "client"

    def __init__(self, orchestrate: Callable[..., Any] | None = None) -> None:
        self._orchestrate = orchestrate

    def run(self, loop: Any, **kwargs: Any) -> dict[str, Any]:
        discover_path = getattr(loop, "discover_path", None)
        if discover_path:
            path = Path(discover_path)
            if path.is_file() and path.suffix == ".md":
                return {
                    "success": True,
                    "loop_id": loop.id,
                    "runner": self.surface_name,
                    "discover": loop.automation.discover,
                    "render_prompt": path.read_text(encoding="utf-8"),
                }
        # orchestrator-backed loop: run the scan-fix cycle (adapts to session)
        return _resolve_orchestrate(self._orchestrate)(loop.loop_name or loop.id, **kwargs)


class ClaudeRunner(_ClientRunner):
    surface_name = "claude"


class CodexRunner(_ClientRunner):
    surface_name = "codex"


_SURFACE_TO_RUNNER = {"claude-code": ClaudeRunner, "codex": CodexRunner, "gemini": ClaudeRunner}


def _detect_surface() -> str | None:
    try:
        from . import session_detect
    except ImportError:  # pragma: no cover - direct-path load
        import sys
        from pathlib import Path
        _dir = Path(__file__).parent
        sys.path.insert(0, str(_dir))
        import session_detect  # type: ignore[no-redef]
    return session_detect.get_subagent_surface(session_detect.detect())


def resolve_runner(
    loop: Any,
    *,
    surface: str | None = None,
    orchestrate: Callable[..., Any] | None = None,
) -> LoopRunner:
    runner = loop.automation.runner
    if runner == "daemon":
        return DaemonRunner(orchestrate=orchestrate)
    if runner == "claude":
        return ClaudeRunner(orchestrate=orchestrate)
    if runner == "codex":
        return CodexRunner(orchestrate=orchestrate)
    if runner == "auto":
        resolved = surface if surface is not None else _detect_surface()
        cls = _SURFACE_TO_RUNNER.get(resolved or "", ClaudeRunner)
        return cls(orchestrate=orchestrate)
    raise ValueError(f"loop {loop.id!r} has unsupported runner {runner!r}")


__all__ = [
    "ClaudeRunner",
    "CodexRunner",
    "DaemonRunner",
    "LoopRunner",
    "resolve_runner",
]
