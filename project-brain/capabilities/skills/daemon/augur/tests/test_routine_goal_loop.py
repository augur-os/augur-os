"""Tests for the routine goal runner."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


TESTS_DIR = Path(__file__).resolve().parent
DAEMON_DIR = TESTS_DIR.parents[1]
SCRIPTS_DIR = DAEMON_DIR / "scripts"
ORCHESTRATOR_DIR = SCRIPTS_DIR / "routine_orchestrator"
MCP_INIT = SCRIPTS_DIR / "mcp" / "__init__.py"


def _load_module(module_name: str, path: Path):
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_goal_catalog():
    return _load_module(
        "routine_goal_catalog_tests",
        ORCHESTRATOR_DIR / "goal_catalog.py",
    )


def _load_goal_loop():
    return _load_module(
        "routine_goal_loop_tests",
        ORCHESTRATOR_DIR / "goal_loop.py",
    )


def _load_mcp_module():
    return _load_module("daemon_mcp_goal_cli_tests", MCP_INIT)


def _parser_for(module):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    module.register_subcommands(subparsers)
    return parser


def test_demo_readiness_goal_is_cataloged_with_compounding_steps() -> None:
    catalog = _load_goal_catalog()

    goal = catalog.get_goal("demo-readiness")

    assert goal.id == "demo-readiness"
    assert "prepare demo" in goal.aliases
    assert [step.id for step in goal.steps] == [
        "demo-readiness",
        "demo-smoke",
        "compound-review",
    ]


def test_goal_loop_writes_ready_report_when_all_checks_pass(tmp_path: Path) -> None:
    goal_loop = _load_goal_loop()
    calls: list[str] = []

    def runner(step, _context):
        calls.append(step.id)
        return goal_loop.StepExecution(
            step_id=step.id,
            command=["fixture", step.id],
            returncode=0,
            stdout=f"{step.id} ok",
            stderr="",
        )

    result = goal_loop.run_goal(
        "demo-readiness",
        project_root=tmp_path / "repo",
        runtime_dir=tmp_path / "state",
        max_iterations=1,
        command_runner=runner,
    )

    assert result.status == "ready"
    assert result.iterations == 1
    assert result.next_actions == []
    assert calls == ["demo-readiness", "demo-smoke", "compound-review"]
    assert result.report_json_path.is_file()
    assert result.report_markdown_path.is_file()
    payload = json.loads(result.report_json_path.read_text(encoding="utf-8"))
    assert payload["goal_id"] == "demo-readiness"
    assert payload["status"] == "ready"
    assert "Demo goal: ready" in result.report_markdown_path.read_text(encoding="utf-8")


def test_goal_loop_returns_agent_actions_for_failed_check(tmp_path: Path) -> None:
    goal_loop = _load_goal_loop()

    def runner(step, _context):
        return goal_loop.StepExecution(
            step_id=step.id,
            command=["fixture", step.id],
            returncode=2 if step.id == "compound-review" else 0,
            stdout="Blockers: compound review proposal was not supplied by the native agent",
            stderr="",
        )

    result = goal_loop.run_goal(
        "demo-readiness",
        project_root=tmp_path / "repo",
        runtime_dir=tmp_path / "state",
        max_iterations=1,
        command_runner=runner,
    )

    assert result.status == "needs_agent_action"
    assert result.next_actions
    assert "proposal JSON" in result.next_actions[0]
    assert "rerun" in result.next_actions[0]
    payload = json.loads(result.report_json_path.read_text(encoding="utf-8"))
    assert payload["iterations"][0]["checks"][-1]["success"] is False


def test_goal_loop_can_converge_after_agent_repair_callback(tmp_path: Path) -> None:
    goal_loop = _load_goal_loop()
    repaired = {"value": False}

    def runner(step, _context):
        if step.id == "demo-smoke" and not repaired["value"]:
            return goal_loop.StepExecution(
                step_id=step.id,
                command=["fixture", step.id],
                returncode=1,
                stdout="missing transcript artifact",
                stderr="",
            )
        return goal_loop.StepExecution(
            step_id=step.id,
            command=["fixture", step.id],
            returncode=0,
            stdout=f"{step.id} ok",
            stderr="",
        )

    def repair(_result):
        repaired["value"] = True

    result = goal_loop.run_goal(
        "demo-readiness",
        project_root=tmp_path / "repo",
        runtime_dir=tmp_path / "state",
        max_iterations=2,
        command_runner=runner,
        repair_callback=repair,
    )

    assert result.status == "ready"
    assert result.iterations == 2
    assert repaired["value"] is True


def test_aug_routine_goal_parses_and_invokes_goal_loop(monkeypatch, capsys) -> None:
    module = _load_mcp_module()
    calls: list[dict] = []

    def run_goal(goal_id: str, **kwargs):
        calls.append({"goal_id": goal_id, **kwargs})
        return SimpleNamespace(
            goal_id=goal_id,
            status="ready",
            iterations=1,
            next_actions=[],
            report_json_path=Path("/tmp/goal.json"),
            report_markdown_path=Path("/tmp/goal.md"),
            to_payload=lambda: {
                "success": True,
                "goal_id": goal_id,
                "status": "ready",
                "iterations": 1,
                "next_actions": [],
                "report_json_path": "/tmp/goal.json",
                "report_markdown_path": "/tmp/goal.md",
            },
        )

    monkeypatch.setattr(
        module,
        "_load_goal_loop",
        lambda: SimpleNamespace(run_goal=run_goal),
    )
    parser = _parser_for(module)

    args = parser.parse_args(
        [
            "a-loops",
            "goal",
            "demo-readiness",
            "--max-iterations",
            "2",
            "--compound-proposal-json",
            "/tmp/proposal.json",
        ]
    )
    assert args.func(args, []) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["goal_id"] == "demo-readiness"
    assert payload["status"] == "ready"
    assert calls == [
        {
            "goal_id": "demo-readiness",
            "project_root": None,
            "runtime_dir": None,
            "max_iterations": 2,
            "compound_proposal_json": Path("/tmp/proposal.json"),
            "skip_smoke": False,
        }
    ]
