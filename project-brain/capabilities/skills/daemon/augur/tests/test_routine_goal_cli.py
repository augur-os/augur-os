"""Tests for the `aug routine goal` CLI verb (ADR-758)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

TESTS_DIR = Path(__file__).resolve().parent
DAEMON_DIR = TESTS_DIR.parents[1]
SCRIPTS_DIR = DAEMON_DIR / "scripts"
MCP_INIT = SCRIPTS_DIR / "mcp" / "__init__.py"


def _load_mcp_module():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    module_name = "daemon_mcp_routines_goal_cli_tests"
    spec = importlib.util.spec_from_file_location(module_name, MCP_INIT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_goal_in_routine_verbs() -> None:
    module = _load_mcp_module()
    assert "goal" in module._ROUTINE_VERBS


def test_goal_no_id_returns_suggestions(monkeypatch) -> None:
    module = _load_mcp_module()
    from routine_orchestrator import goal_suggest
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _FakeSuggestion:
        id: str = "harden"
        title: str = "Harden"
        loops: tuple[str, ...] = ("testing",)
        finding_count: int = 2
        top_findings: tuple[str, ...] = ("x", "y")
        est_iterations: int = 1

    monkeypatch.setattr(goal_suggest, "suggest", lambda **k: [_FakeSuggestion()])

    payload = module._routine_goal_payload(
        SimpleNamespace(
            goal_id=None,
            suggest=True,
            catalog_loop=False,
            stamp="x",
            max_iterations=1,
            loop_cap=6,
        )
    )
    assert payload["mode"] == "suggest"
    assert payload["success"] is True
    assert len(payload["suggestions"]) == 1
    assert payload["suggestions"][0]["id"] == "harden"
    assert payload["suggestions"][0]["title"] == "Harden"
    assert payload["suggestions"][0]["finding_count"] == 2


def test_goal_run_without_session_fails(monkeypatch) -> None:
    module = _load_mcp_module()
    monkeypatch.setattr(module, "_routine_session_surface", lambda s: None)

    payload = module._routine_goal_payload(
        SimpleNamespace(
            goal_id="harden",
            suggest=False,
            catalog_loop=True,
            stamp="x",
            max_iterations=1,
            loop_cap=6,
        )
    )
    assert payload["mode"] == "run"
    assert payload["success"] is False
    assert "error" in payload


def test_goal_run_success_payload_shape(monkeypatch) -> None:
    """Catalog-loop with a session now renders the goal-loop inline-session routine.

    The old test monkeypatched goal_loop.run_goal_loops; after the inline-session
    refactor the run branch calls registry.dispatch("goal-loop") instead.
    We monkeypatch _load_routine_registry to return a fake registry so this test
    is hermetic and does not depend on the goal-loop routine being declared yet
    (Task 7 adds that declaration).
    """
    module = _load_mcp_module()

    # Force a session to be present.
    monkeypatch.setattr(module, "_detect_routine_session", lambda: object())
    monkeypatch.setattr(module, "_routine_session_surface", lambda s: "claude-code")

    class _FakeRegistry:
        def dispatch(self, routine_id: str, **_kw):
            assert routine_id == "goal-loop"
            return {"success": True, "render_prompt": "PROMPT", "routine_id": "goal-loop", "execution": "inline-session", "policy": "adaptive"}

    monkeypatch.setattr(module, "_load_routine_registry", lambda: _FakeRegistry())

    payload = module._routine_goal_payload(
        SimpleNamespace(
            goal_id="harden",
            suggest=False,
            catalog_loop=True,
            stamp="x",
            max_iterations=1,
            loop_cap=6,
        )
    )
    # The run branch now renders the inline-session routine.
    assert payload["mode"] == "render"
    assert payload["success"] is True
    assert payload.get("render_prompt") == "PROMPT"
    assert payload["goal_id"] == "harden"
    assert payload["stamp"] == "x"


# ---------------------------------------------------------------------------
# New tests for ADR-793 goal-op CLI verbs and inline-session render path
# ---------------------------------------------------------------------------


def test_all_goal_op_verbs_registered() -> None:
    """All atomic op verbs must be registered in _ROUTINE_VERBS."""
    mcp = _load_mcp_module()
    for v in (
        "goal-worktree",
        "goal-scan-loop",
        "goal-record-bucket",
        "goal-loop-status",
        "goal-escalate",
        "goal-drain-backlog",
        "goal-consume-finding",
        "goal-run-maintenance",
    ):
        assert v in mcp._ROUTINE_VERBS, f"{v!r} missing from _ROUTINE_VERBS"


def test_goal_run_maintenance_verb_dispatches_through_cli(monkeypatch, capsys) -> None:
    """goal-run-maintenance routes through _run_routine_cli, json-parses findings,
    and calls op_run_maintenance with the parsed args."""
    import json
    import types

    mcp = _load_mcp_module()
    from routine_orchestrator import goal_ops

    called: dict = {}

    def fake_op_run_maintenance(**kw):
        called.update(kw)
        return {
            "success": True,
            "auto_command": "ln",
            "applied": 1,
            "changed_files": [],
            "summary": "rebuilt",
        }

    monkeypatch.setattr(goal_ops, "op_run_maintenance", fake_op_run_maintenance)

    ns = types.SimpleNamespace(
        routine_verb="goal-run-maintenance",
        loop="knowledge-enrichment",
        worktree="/tmp/wt",
        auto_command="ln",
        findings_json='[{"auto_command": "ln", "kind": "maintenance"}]',
    )
    rc = mcp._run_routine_cli(ns, [])

    out = json.loads(capsys.readouterr().out)
    assert out["success"] is True, f"unexpected payload: {out}"
    assert out["auto_command"] == "ln"
    assert called.get("loop") == "knowledge-enrichment"
    assert called.get("worktree_path") == "/tmp/wt"
    assert called.get("auto_command") == "ln"
    assert called.get("findings") == [{"auto_command": "ln", "kind": "maintenance"}]
    assert rc == 0


def test_catalog_loop_run_renders_inline_session(monkeypatch) -> None:
    """catalog_loop=True with a live session renders the goal-loop routine.

    Monkeypatches _load_routine_registry so this test is hermetic — the
    goal-loop routine declaration is added in Task 7; this task only wires
    the render path.
    """
    mcp = _load_mcp_module()
    monkeypatch.setattr(mcp, "_detect_routine_session", lambda: object())
    monkeypatch.setattr(mcp, "_routine_session_surface", lambda s: "claude-code")

    class _FakeRegistry:
        def dispatch(self, routine_id: str, **_kw):
            assert routine_id == "goal-loop"
            return {"success": True, "render_prompt": "PROMPT", "routine_id": "goal-loop", "execution": "inline-session"}

    monkeypatch.setattr(mcp, "_load_routine_registry", lambda: _FakeRegistry())

    payload = mcp._routine_catalog_goal_payload(goal_id="clean", stamp="x", catalog_loop=True)
    assert payload["mode"] == "render"
    assert payload.get("render_prompt") == "PROMPT"


def test_catalog_loop_bare_cli_fails_fast(monkeypatch) -> None:
    """catalog_loop=True with no session must fail fast with an in-session message."""
    mcp = _load_mcp_module()
    monkeypatch.setattr(mcp, "_detect_routine_session", lambda: None)
    monkeypatch.setattr(mcp, "_routine_session_surface", lambda s: None)

    payload = mcp._routine_catalog_goal_payload(goal_id="clean", stamp="x", catalog_loop=True)
    assert payload["success"] is False
    assert "in-session" in payload["detail"].lower()


def test_catalog_loop_non_registry_error_propagates(monkeypatch) -> None:
    """A non-registry error from dispatch must propagate, not be swallowed as 'not declared yet'.

    After narrowing the except clause to RoutineNotFound/RoutineValidationError,
    any other exception (ImportError, TypeError, etc.) must bubble up so the outer
    handler in _run_routine_cli reports it with its true type.
    """
    import pytest

    mcp = _load_mcp_module()
    monkeypatch.setattr(mcp, "_detect_routine_session", lambda: object())
    monkeypatch.setattr(mcp, "_routine_session_surface", lambda s: "claude-code")

    class _BrokenRegistry:
        RoutineNotFound = type("RoutineNotFound", (Exception,), {})
        RoutineValidationError = type("RoutineValidationError", (Exception,), {})

        def dispatch(self, routine_id: str, **_kw):
            raise TypeError("unexpected internal failure")

    monkeypatch.setattr(mcp, "_load_routine_registry", lambda: _BrokenRegistry())

    with pytest.raises(TypeError, match="unexpected internal failure"):
        mcp._routine_catalog_goal_payload(goal_id="clean", stamp="x", catalog_loop=True)


def test_goal_worktree_verb_dispatches_through_cli(monkeypatch, capsys) -> None:
    """goal-worktree verb routes through the real _run_routine_cli dispatcher.

    The Namespace must carry exactly the attributes the branch reads:
      - args.goal_id  (str)
      - args.stamp    (str — non-empty so _derive_goal_stamp() is not called)
    project_root is obtained via get_project_root() at the module level,
    not from the args namespace.
    """
    import json
    import types

    mcp = _load_mcp_module()
    from routine_orchestrator import goal_ops

    called: dict = {}

    def fake_op_worktree(**kw):
        called.update(kw)
        return {
            "success": True,
            "branch": "goal/clean-x",
            "worktree_path": "/tmp/wt",
            "goal_id": "clean",
            "loops": ["x"],
        }

    monkeypatch.setattr(goal_ops, "op_worktree", fake_op_worktree)

    ns = types.SimpleNamespace(
        routine_verb="goal-worktree",
        goal_id="clean",
        stamp="x",
    )
    rc = mcp._run_routine_cli(ns, [])

    out = json.loads(capsys.readouterr().out)
    assert out["success"] is True, f"unexpected payload: {out}"
    assert out["branch"] == "goal/clean-x"
    assert called.get("goal_id") == "clean", f"op was not called with goal_id=clean; called={called}"
    assert called.get("stamp") == "x", f"op was not called with stamp=x; called={called}"
    assert rc == 0
