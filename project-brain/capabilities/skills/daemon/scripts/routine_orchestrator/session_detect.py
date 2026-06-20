"""Session detection for the ADR-755 routine orchestrator."""
from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Mapping
from typing import Any

from src.lib.ops_protocol import SessionContext


Which = Callable[[str], str | None]


class OrchestratorSessionContext(SessionContext):
    """Session context extended with the native subagent surface."""

    def __init__(
        self,
        *args: Any,
        subagent_surface: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.subagent_surface = subagent_surface

_SESSION_ENV_VARS = {
    "claude": ("CLAUDE_CODE_ENTRY_POINT", "CLAUDECODE", "CLAUDE_CODE_SESSION"),
    # Codex Desktop shells expose thread/shell markers even when CODEX_SESSION is absent.
    "codex": ("CODEX_SESSION", "CODEX_THREAD_ID", "CODEX_SHELL", "CODEX_INTERNAL_ORIGINATOR_OVERRIDE"),
    "gemini": ("GEMINI_SESSION",),
    "cursor": ("CURSOR_SESSION",),
    "copilot": ("COPILOT_SESSION", "GITHUB_COPILOT_SESSION"),
}

_CLI_CANDIDATES: tuple[tuple[str, tuple[str, ...], str | None], ...] = (
    ("claude", ("claude", "claude-code"), "claude-code"),
    ("codex", ("codex",), "codex"),
    ("gemini", ("gemini",), "gemini"),
    ("cursor", ("cursor",), "degraded-inline"),
    ("copilot", ("copilot",), "degraded-inline"),
)


def detect(
    config: dict[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
    which: Which | None = None,
) -> OrchestratorSessionContext:
    """Return a SessionContext-compatible object for orchestrator dispatch.

    The legacy adaptive engine detects broad LLM availability. The orchestrator
    also needs the native subagent surface so semantic fixes can fan out through
    the active client when one is present.
    """
    env_map = os.environ if env is None else env
    resolve = shutil.which if which is None else which
    ctx = OrchestratorSessionContext()

    detected = _first_detected_surface(env_map, resolve)
    if detected is not None:
        cli_name, cli_path, subagent_surface = detected
        ctx.cli_name = cli_name
        ctx.cli_path = cli_path
        ctx.has_llm = True
        ctx.subagent_surface = subagent_surface
    else:
        ctx.subagent_surface = None

    ctx.has_tool_access = any(
        env_map.get(var)
        for env_vars in _SESSION_ENV_VARS.values()
        for var in env_vars
    )

    if ctx.has_tool_access and ctx.subagent_surface in {"claude-code", "codex", "gemini"}:
        ctx.has_llm = True

    llm_cfg = (config or {}).get("engine", {}).get("llm_escalation", {})
    ctx.max_turns = llm_cfg.get("max_turns", ctx.max_turns)
    ctx.timeout = llm_cfg.get("timeout_s", ctx.timeout)
    return ctx


def get_subagent_surface(ctx: SessionContext) -> str | None:
    """Return the subagent surface for orchestrator-aware contexts."""
    value = getattr(ctx, "subagent_surface", None)
    return value if isinstance(value, str) else None


def _first_detected_surface(
    env: Mapping[str, str],
    which: Which,
) -> tuple[str, str, str | None] | None:
    for cli_name, binary_names, subagent_surface in _CLI_CANDIDATES:
        if not _env_or_cli_present(cli_name, binary_names, env, which):
            continue
        cli_path = _first_cli_path(binary_names, which)
        return (cli_name, cli_path, subagent_surface)
    return None


def _env_or_cli_present(
    cli_name: str,
    binary_names: tuple[str, ...],
    env: Mapping[str, str],
    which: Which,
) -> bool:
    return any(env.get(var) for var in _SESSION_ENV_VARS[cli_name]) and bool(
        _first_cli_path(binary_names, which)
    )


def _first_cli_path(binary_names: tuple[str, ...], which: Which) -> str:
    for binary_name in binary_names:
        path = which(binary_name)
        if path:
            return path
    return ""
