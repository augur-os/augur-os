"""Tests for ADR-755 client-aware subagent dispatch."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from time import monotonic
from types import SimpleNamespace

import pytest

from src.lib.ops_protocol import FixResult


TESTS_DIR = Path(__file__).resolve().parent
DAEMON_DIR = TESTS_DIR.parents[1]
DAEMON_SCRIPTS_DIR = DAEMON_DIR / "scripts"
SUBAGENT_DISPATCH_PATH = DAEMON_SCRIPTS_DIR / "routine_orchestrator" / "subagent_dispatch.py"
BUDGET_PATH = DAEMON_SCRIPTS_DIR / "routine_orchestrator" / "budget.py"
BUCKET_PLANNER_PATH = DAEMON_SCRIPTS_DIR / "routine_orchestrator" / "bucket_planner.py"
SESSION_DETECT_PATH = DAEMON_SCRIPTS_DIR / "routine_orchestrator" / "session_detect.py"

if str(DAEMON_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(DAEMON_SCRIPTS_DIR))


def _load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_dispatch_module():
    return _load_module("routine_orchestrator_subagent_dispatch_under_test", SUBAGENT_DISPATCH_PATH)


def _load_budget_module():
    return _load_module("routine_orchestrator_budget_for_dispatch", BUDGET_PATH)


def _load_bucket_module():
    return _load_module("routine_orchestrator_bucket_for_dispatch", BUCKET_PLANNER_PATH)


def _load_session_module():
    return _load_module("routine_orchestrator_session_for_dispatch", SESSION_DETECT_PATH)


def _bucket():
    bucket_mod = _load_bucket_module()
    return bucket_mod.FindingBucket(
        auto_command="auto-semantic",
        primary_file="fixtures/toy_loop/auto_semantic.py",
        findings=[
            {
                "auto_command": "auto-semantic",
                "path": "fixtures/toy_loop/auto_semantic.py",
                "detail": "Choose wording from local context",
            }
        ],
    )


def _budget(max_turns: int = 20):
    budget_mod = _load_budget_module()
    return budget_mod.Budget(max_turns=max_turns, soft_timeout_s=600, start_time=monotonic())


def _session(surface: str | None):
    session_mod = _load_session_module()
    return session_mod.OrchestratorSessionContext(
        has_tool_access=surface is not None,
        has_llm=surface is not None,
        subagent_surface=surface,
    )


def _auto_command():
    module = SimpleNamespace(
        name="auto-semantic",
        description="Repair wording using nearby context.",
        ALLOWED_TOOLS=("Read", "Edit", "Bash"),
    )
    return SimpleNamespace(
        name="auto-semantic",
        module=module,
        loop_name="toy-loop",
        owner_skill="routine-codebase",
        config={},
    )


def test_dispatch_via_claude_code_task_tool_with_mocked_primitive() -> None:
    dispatch = _load_dispatch_module()
    calls: list[dict] = []

    def task_invoker(**kwargs):
        calls.append(kwargs)
        return {"status": "success", "commit_hash": "abc123", "diagnostic": "fixed"}

    result = dispatch.dispatch_bucket(
        _bucket(),
        _auto_command(),
        _session("claude-code"),
        _budget(),
        verify_command="uv run verify",
        task_invoker=task_invoker,
    )

    assert result.status == "success"
    assert result.commit_hash == "abc123"
    assert result.diagnostic == "fixed"
    assert result.budget_consumed == 1
    assert len(calls) == 1
    call = calls[0]
    assert call["subagent_type"] == "general-purpose"
    assert call["allowed_tools"] == ["Read", "Edit", "Bash"]
    assert "auto-semantic" in call["description"]
    prompt_payload = json.loads(call["prompt"].split("\n", 1)[1])
    assert prompt_payload["description"] == "Repair wording using nearby context."
    assert prompt_payload["findings"][0]["detail"] == "Choose wording from local context"
    assert prompt_payload["allowed_tools"] == ["Read", "Edit", "Bash"]
    assert prompt_payload["budget"]["max_turns"] == 20
    assert prompt_payload["verify_command"] == "uv run verify"


def test_subagent_result_parsing_from_json_string() -> None:
    dispatch = _load_dispatch_module()

    result = dispatch.dispatch_bucket(
        _bucket(),
        _auto_command(),
        _session("claude-code"),
        _budget(),
        task_invoker=lambda **_kwargs: '{"status":"success","commit_hash":"abc","diagnostic":"ok"}',
    )

    assert result.status == "success"
    assert result.commit_hash == "abc"
    assert result.diagnostic == "ok"


def test_subagent_failure_returned_as_structured_result() -> None:
    dispatch = _load_dispatch_module()

    result = dispatch.dispatch_bucket(
        _bucket(),
        _auto_command(),
        _session("claude-code"),
        _budget(),
        task_invoker=lambda **_kwargs: {"status": "failed", "diagnostic": "needs human"},
    )

    assert result.status == "failed"
    assert result.commit_hash is None
    assert result.diagnostic == "needs human"


def test_codex_surface_dispatches_via_headless_exec(monkeypatch, tmp_path: Path) -> None:
    dispatch = _load_dispatch_module()
    session_mod = _load_session_module()
    calls: list[dict] = []

    def fake_run(cmd, capture_output, text, timeout, cwd, env, stdin):  # noqa: ANN001
        calls.append(
            {
                "cmd": cmd,
                "capture_output": capture_output,
                "text": text,
                "timeout": timeout,
                "cwd": cwd,
                "env_has_path": "PATH" in env,
                "stdin": stdin,
            }
        )
        output_path = Path(cmd[cmd.index("-o") + 1])
        output_path.write_text(
            '{"status":"success","commit_hash":"abc123","diagnostic":"fixed"}',
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(dispatch.subprocess, "run", fake_run)

    session = session_mod.OrchestratorSessionContext(
        has_tool_access=True,
        has_llm=True,
        cli_name="codex",
        cli_path="/fake/bin/codex",
        subagent_surface="codex",
        timeout=321,
    )

    result = dispatch.dispatch_bucket(
        _bucket(),
        _auto_command(),
        session,
        _budget(),
        project_root=tmp_path,
        verify_command="uv run verify",
    )

    assert result.status == "success"
    assert result.commit_hash == "abc123"
    assert result.diagnostic == "fixed"
    assert result.budget_consumed == 1
    assert len(calls) == 1
    call = calls[0]
    assert call["cmd"][:2] == ["/fake/bin/codex", "exec"]
    assert "--ephemeral" in call["cmd"]
    assert "--dangerously-bypass-approvals-and-sandbox" in call["cmd"]
    assert "-o" in call["cmd"]
    assert call["cwd"] == str(tmp_path)
    assert call["timeout"] == 321
    assert call["stdin"] == dispatch.subprocess.DEVNULL


def test_degraded_inline_mode_for_cursor() -> None:
    dispatch = _load_dispatch_module()
    calls: list[list[dict]] = []

    def fix(ctx, issues):
        calls.append(issues)
        return FixResult(success=True, summary=f"inline fixed {len(issues)}")

    command = _auto_command()
    command.module.fix = fix

    result = dispatch.dispatch_bucket(
        _bucket(),
        command,
        _session("degraded-inline"),
        _budget(),
        project_root=Path.cwd(),
    )

    assert calls == [_bucket().findings]
    assert result.status == "success"
    assert result.diagnostic == "inline fixed 1"
    assert result.budget_consumed == 1


def test_no_session_raises_explicit_error() -> None:
    dispatch = _load_dispatch_module()

    with pytest.raises(dispatch.NoSessionAvailable):
        dispatch.dispatch_bucket(
            _bucket(),
            _auto_command(),
            _session(None),
            _budget(),
        )


def test_budget_exhaustion_raises_before_dispatch() -> None:
    dispatch = _load_dispatch_module()
    budget = _budget(max_turns=1)
    budget.consume()

    with pytest.raises(dispatch.BudgetExceeded):
        dispatch.dispatch_bucket(
            _bucket(),
            _auto_command(),
            _session("claude-code"),
            budget,
            task_invoker=lambda **_kwargs: {"status": "success"},
        )


# --- _allowed_tools default toolset tests (fix for toothless subagents) ---


def test_allowed_tools_defaults_when_command_declares_none() -> None:
    """When a command declares NO tools, _allowed_tools must return the DEFAULT_FIX_TOOLS."""
    dispatch = _load_dispatch_module()

    class _Cmd:  # no allowed_tools attr, no module ALLOWED_TOOLS
        pass

    tools = dispatch._allowed_tools(_Cmd())
    assert tools == list(dispatch.DEFAULT_FIX_TOOLS)
    assert tools  # non-empty


def test_allowed_tools_honors_declared_list() -> None:
    """When a command declares a list, _allowed_tools must return that list exactly."""
    dispatch = _load_dispatch_module()

    class _Cmd:
        allowed_tools = ["Read", "Grep"]

    assert dispatch._allowed_tools(_Cmd()) == ["Read", "Grep"]


def test_allowed_tools_honors_declared_csv() -> None:
    """When a command declares a CSV string, _allowed_tools must split and return it."""
    dispatch = _load_dispatch_module()

    class _Cmd:
        allowed_tools = "Read, Bash"

    assert dispatch._allowed_tools(_Cmd()) == ["Read", "Bash"]


def test_allowed_tools_empty_declared_falls_back_to_default() -> None:
    """An explicitly declared empty list is also toothless — fall back to DEFAULT_FIX_TOOLS."""
    dispatch = _load_dispatch_module()

    class _Cmd:
        allowed_tools = []

    assert dispatch._allowed_tools(_Cmd()) == list(dispatch.DEFAULT_FIX_TOOLS)
