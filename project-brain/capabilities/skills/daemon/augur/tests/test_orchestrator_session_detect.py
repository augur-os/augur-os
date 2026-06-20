"""Tests for ADR-755 routine orchestrator session detection."""
from __future__ import annotations

import importlib.util
from pathlib import Path


TESTS_DIR = Path(__file__).resolve().parent
DAEMON_DIR = TESTS_DIR.parents[1]
SESSION_DETECT_PATH = DAEMON_DIR / "scripts" / "routine_orchestrator" / "session_detect.py"


def _load_session_detect_module():
    spec = importlib.util.spec_from_file_location(
        "routine_orchestrator_session_detect",
        SESSION_DETECT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _which_with(*available: str):
    paths = {name: f"/fake/bin/{name}" for name in available}

    def which(name: str) -> str | None:
        return paths.get(name)

    return which


def test_in_session_with_claude_code_detects_subagent_capability() -> None:
    session_detect = _load_session_detect_module()

    ctx = session_detect.detect(
        env={"CLAUDE_CODE_ENTRY_POINT": "cli"},
        which=_which_with("claude"),
    )

    assert ctx.has_llm is True
    assert ctx.has_tool_access is True
    assert ctx.cli_name == "claude"
    assert ctx.cli_path == "/fake/bin/claude"
    assert ctx.subagent_surface == "claude-code"


def test_headless_environment_returns_no_session_context() -> None:
    session_detect = _load_session_detect_module()

    ctx = session_detect.detect(env={}, which=_which_with())

    assert ctx.has_llm is False
    assert ctx.has_tool_access is False
    assert ctx.cli_name == ""
    assert ctx.cli_path == ""
    assert ctx.subagent_surface is None


def test_cli_binary_without_session_does_not_claim_subagent_surface() -> None:
    session_detect = _load_session_detect_module()

    ctx = session_detect.detect(env={}, which=_which_with("claude"))

    assert ctx.has_llm is False
    assert ctx.has_tool_access is False
    assert ctx.cli_name == ""
    assert ctx.cli_path == ""
    assert ctx.subagent_surface is None


def test_session_env_without_cli_bridge_does_not_claim_subagent_surface() -> None:
    session_detect = _load_session_detect_module()

    ctx = session_detect.detect(env={"CODEX_SESSION": "1"}, which=_which_with())

    assert ctx.has_llm is False
    assert ctx.has_tool_access is True
    assert ctx.cli_name == ""
    assert ctx.cli_path == ""
    assert ctx.subagent_surface is None


def test_codex_desktop_shell_env_detects_subagent_capability() -> None:
    session_detect = _load_session_detect_module()

    ctx = session_detect.detect(
        env={
            "CODEX_THREAD_ID": "019e7108-1d79-7713-b7ea-5ca4a1aea7c9",
            "CODEX_SHELL": "1",
        },
        which=_which_with("codex"),
    )

    assert ctx.has_llm is True
    assert ctx.has_tool_access is True
    assert ctx.cli_name == "codex"
    assert ctx.cli_path == "/fake/bin/codex"
    assert ctx.subagent_surface == "codex"


def test_plain_session_context_surface_helper_is_safe() -> None:
    session_detect = _load_session_detect_module()

    plain_ctx = session_detect.SessionContext()

    assert session_detect.get_subagent_surface(plain_ctx) is None


def test_cursor_returns_degraded_mode_marker() -> None:
    session_detect = _load_session_detect_module()

    ctx = session_detect.detect(env={"CURSOR_SESSION": "1"}, which=_which_with("cursor"))

    assert ctx.has_llm is True
    assert ctx.has_tool_access is True
    assert ctx.cli_name == "cursor"
    assert ctx.cli_path == "/fake/bin/cursor"
    assert ctx.subagent_surface == "degraded-inline"
