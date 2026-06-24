"""End-to-end fixture tests for ADR-755 routine orchestration."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from src.lib.ops_protocol import FixResult


TESTS_DIR = Path(__file__).resolve().parent
DAEMON_DIR = TESTS_DIR.parents[1]
DAEMON_SCRIPTS_DIR = DAEMON_DIR / "scripts"
ROUTINE_DIR = DAEMON_SCRIPTS_DIR / "routine_orchestrator"

if str(DAEMON_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(DAEMON_SCRIPTS_DIR))


def _load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_orchestrator():
    package_name = "routine_orchestrator"
    if package_name not in sys.modules:
        package_spec = importlib.util.spec_from_file_location(
            package_name,
            ROUTINE_DIR / "__init__.py",
            submodule_search_locations=[str(ROUTINE_DIR)],
        )
        assert package_spec is not None and package_spec.loader is not None
        package = importlib.util.module_from_spec(package_spec)
        sys.modules[package_name] = package
        package_spec.loader.exec_module(package)
    return _load_module("routine_orchestrator.orchestrator", ROUTINE_DIR / "orchestrator.py")


def _load_fixture_helpers():
    return _load_module("orchestrator_fixtures_e2e", TESTS_DIR / "_fixtures.py")


def _load_toy_module(module_name: str):
    fixtures = _load_fixture_helpers()
    return _load_module(module_name, fixtures.TOY_LOOP_FIXTURE_DIR / f"{module_name}.py")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Augur Tests")
    tool_file = repo / "fixtures" / "toy_loop" / "tool-name.txt"
    tool_file.parent.mkdir(parents=True)
    tool_file.write_text("toy-toool\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    return repo


def _commands(repo: Path, scanned: list[str]):
    auto_mech = _load_toy_module("auto_mech")
    auto_semantic = _load_toy_module("auto_semantic")
    auto_struct = _load_toy_module("auto_struct")

    def mech_scan(ctx):
        scanned.append("auto-mech")
        return auto_mech.scan(ctx)

    def mech_fix(ctx, issues):
        (repo / "fixtures" / "toy_loop" / "tool-name.txt").write_text(
            "toy-tool\n",
            encoding="utf-8",
        )
        return FixResult(
            success=True,
            changes=["fixtures/toy_loop/tool-name.txt"],
            summary=f"fixed {len(issues)} mechanical issue(s)",
            fix_type="code-fix",
        )

    def semantic_scan(ctx):
        scanned.append("auto-semantic")
        return auto_semantic.scan(ctx)

    def struct_scan(ctx):
        scanned.append("auto-struct")
        return auto_struct.scan(ctx)

    return [
        SimpleNamespace(
            name="auto-mech",
            module=SimpleNamespace(name="auto-mech", scan=mech_scan, fix=mech_fix),
            loop_name="toy-loop",
            config={},
            tier=0,
            owner_skill="routine-codebase",
        ),
        SimpleNamespace(
            name="auto-semantic",
            module=SimpleNamespace(
                name="auto-semantic",
                description="Repair semantic toy issue.",
                scan=semantic_scan,
                fix=auto_semantic.fix,
                ALLOWED_TOOLS=("Read", "Edit"),
            ),
            loop_name="toy-loop",
            config={},
            tier=1,
            owner_skill="routine-codebase",
        ),
        SimpleNamespace(
            name="auto-struct",
            module=SimpleNamespace(name="auto-struct", scan=struct_scan, fix=auto_struct.fix),
            loop_name="toy-loop",
            config={},
            tier=2,
            owner_skill="routine-codebase",
        ),
    ]


def _ledger_phase_events(runtime_dir: Path) -> list[str]:
    job_dirs = sorted((runtime_dir / "jobs").glob("*routine-toy-loop*"))
    assert job_dirs
    events_path = job_dirs[-1] / "events.jsonl"
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [event["phase"] for event in events if "phase" in event]


def test_orchestrator_end_to_end_fixture_round_trip(tmp_path: Path) -> None:
    orchestrator = _load_orchestrator()
    fixtures = _load_fixture_helpers()
    repo = _init_repo(tmp_path)
    state_file = fixtures.build_trust_state_file(tmp_path)
    runtime_dir = state_file.parents[1]
    scanned: list[str] = []
    events: list[dict] = []
    task_calls: list[dict] = []

    def task_invoker(**kwargs):
        task_calls.append(kwargs)
        return {
            "status": "success",
            "commit_hash": "semantic123",
            "diagnostic": "semantic toy fixed",
        }

    session = orchestrator.session_detect.OrchestratorSessionContext(
        has_tool_access=True,
        has_llm=True,
        subagent_surface="claude-code",
    )

    result = orchestrator.orchestrate_run(
        "toy-loop",
        project_root=repo,
        runtime_dir=runtime_dir,
        state_dir=runtime_dir / "adaptive",
        commands=_commands(repo, scanned),
        trust_config=fixtures.build_toy_loop()["config"],
        session=session,
        task_invoker=task_invoker,
        verify_runner=lambda **_kwargs: True,
        event_sink=events,
        verify_command="fixture verify",
    )

    assert scanned == ["auto-mech", "auto-semantic", "auto-struct"]
    assert result.counts == {
        "findings": 3,
        "mechanical_applied": 1,
        "mechanical_failed": 0,
        "deferred": 2,
        "design_gate_findings": 1,
        "dispatched": 1,
        "enqueued": 0,
    }
    assert result.mechanical_applied[0].command == "auto-mech"
    assert _git(repo, "log", "-1", "--pretty=%s").startswith(
        "ADR-755 mechanical fix: auto-mech"
    )
    assert task_calls
    assert task_calls[0]["subagent_type"] == "general-purpose"
    assert result.dispatched[0].commit_hash == "semantic123"
    assert result.design_gate_findings[0]["auto_command"] == "auto-struct"
    assert [event["phase"] for event in events] == [
        "scan",
        "mechanical",
        "bucket",
        "dispatch",
        "complete",
    ]
    assert _ledger_phase_events(runtime_dir) == [
        "scan",
        "mechanical",
        "bucket",
        "dispatch",
        "complete",
    ]

    state = json.loads(state_file.read_text(encoding="utf-8"))
    categories = state["loops"]["toy-loop"]["categories"]
    assert categories["auto-mech"]["success_count"] == 1
    assert categories["auto-semantic"]["success_count"] == 1
    assert categories["auto-struct"].get("success_count", 0) == 0


def test_orchestrator_enqueues_semantic_findings_without_session(tmp_path: Path) -> None:
    orchestrator = _load_orchestrator()
    fixtures = _load_fixture_helpers()
    repo = _init_repo(tmp_path)
    state_file = fixtures.build_trust_state_file(tmp_path)
    runtime_dir = state_file.parents[1]
    session = orchestrator.session_detect.OrchestratorSessionContext(
        has_llm=False,
        subagent_surface=None,
    )

    result = orchestrator.orchestrate_run(
        "toy-loop",
        project_root=repo,
        runtime_dir=runtime_dir,
        state_dir=runtime_dir / "adaptive",
        commands=_commands(repo, []),
        trust_config=fixtures.build_toy_loop()["config"],
        session=session,
        verify_runner=lambda **_kwargs: True,
    )

    assert result.counts["dispatched"] == 0
    assert result.counts["enqueued"] == 1
    pending = runtime_dir / "jobs" / "_escalations" / "pending.jsonl"
    payload = json.loads(pending.read_text(encoding="utf-8").splitlines()[0])
    assert payload["finding"]["auto_command"] == "auto-semantic"


def test_orchestrator_escalates_when_claude_surface_has_no_invoker(
    tmp_path: Path,
) -> None:
    """A headless run inherits CLAUDECODE env (surface detects as claude-code)
    but has no in-process Task invoker. The orchestrator must escalate, not raise
    NoSessionAvailable and record a hard failure. Regression for the
    skill-standards `aug a-loops run` crash."""
    orchestrator = _load_orchestrator()
    fixtures = _load_fixture_helpers()
    repo = _init_repo(tmp_path)
    state_file = fixtures.build_trust_state_file(tmp_path)
    runtime_dir = state_file.parents[1]
    session = orchestrator.session_detect.OrchestratorSessionContext(
        has_tool_access=True,
        has_llm=True,
        subagent_surface="claude-code",
    )

    # No task_invoker passed and _TASK_INVOKER is unset (headless subprocess).
    result = orchestrator.orchestrate_run(
        "toy-loop",
        project_root=repo,
        runtime_dir=runtime_dir,
        state_dir=runtime_dir / "adaptive",
        commands=_commands(repo, []),
        trust_config=fixtures.build_toy_loop()["config"],
        session=session,
        verify_runner=lambda **_kwargs: True,
    )

    assert result.counts["dispatched"] == 0
    assert result.counts["enqueued"] == 1
    assert "escalate" in [event["phase"] for event in result.events]
    pending = runtime_dir / "jobs" / "_escalations" / "pending.jsonl"
    payload = json.loads(pending.read_text(encoding="utf-8").splitlines()[0])
    assert payload["finding"]["auto_command"] == "auto-semantic"


def test_fix_one_command_builds_dynamic_trust_config(tmp_path: Path) -> None:
    orchestrator = _load_orchestrator()
    repo = _init_repo(tmp_path)
    state_file = _load_fixture_helpers().build_trust_state_file(tmp_path)
    runtime_dir = state_file.parents[1]
    command = _commands(repo, [])[0]

    result = orchestrator.fix_one_command(
        "toy-loop",
        project_root=repo,
        runtime_dir=runtime_dir,
        state_dir=runtime_dir / "adaptive",
        command=command,
        findings=[
            {
                "auto_command": "auto-mech",
                "loop": "toy-loop",
                "path": "fixtures/toy_loop/tool-name.txt",
                "detail": "mechanical typo",
                "finding_band": "mechanical",
            }
        ],
        trust_config={
            "engine": {"enabled": True},
            "loops": {"toy-loop": {"enabled": True, "categories": {}}},
        },
        verify_runner=lambda **_kwargs: True,
    )

    assert result.counts["mechanical_applied"] == 1
    state = json.loads(state_file.read_text(encoding="utf-8"))
    category = state["loops"]["toy-loop"]["categories"]["auto-mech"]
    assert category["success_count"] == 1


def test_orchestrator_dedupes_pending_and_completes_on_dispatch(tmp_path: Path) -> None:
    orchestrator = _load_orchestrator()
    fixtures = _load_fixture_helpers()
    repo = _init_repo(tmp_path)
    state_file = fixtures.build_trust_state_file(tmp_path)
    runtime_dir = state_file.parents[1]
    semantic_finding = {
        "auto_command": "auto-semantic",
        "loop": "toy-loop",
        "path": "fixtures/toy_loop/auto_semantic.py",
        "detail": "Choose the right summary wording from nearby context.",
        "requires_llm": True,
        "fixability": "llm-assisted",
    }
    orchestrator.escalation_queue.enqueue(semantic_finding, runtime_dir=runtime_dir)
    session = orchestrator.session_detect.OrchestratorSessionContext(
        has_tool_access=True,
        has_llm=True,
        subagent_surface="claude-code",
    )
    task_calls: list[dict] = []

    result = orchestrator.orchestrate_run(
        "toy-loop",
        project_root=repo,
        runtime_dir=runtime_dir,
        state_dir=runtime_dir / "adaptive",
        commands=_commands(repo, []),
        trust_config=fixtures.build_toy_loop()["config"],
        session=session,
        verify_runner=lambda **_kwargs: True,
        task_invoker=lambda **kwargs: task_calls.append(kwargs)
        or {"status": "success", "commit_hash": "semantic456", "diagnostic": "ok"},
    )

    assert result.counts["findings"] == 3
    assert result.counts["dispatched"] == 1
    assert len(task_calls) == 1
    pending_path = runtime_dir / "jobs" / "_escalations" / "pending.jsonl"
    assert pending_path.read_text(encoding="utf-8") == ""


def test_orchestrator_ignores_foreign_pending_escalations(tmp_path: Path) -> None:
    orchestrator = _load_orchestrator()
    fixtures = _load_fixture_helpers()
    repo = _init_repo(tmp_path)
    state_file = fixtures.build_trust_state_file(tmp_path)
    runtime_dir = state_file.parents[1]
    pending_path = runtime_dir / "jobs" / "_escalations" / "pending.jsonl"
    foreign_finding = {
        "auto_command": "auto-test-dashboard",
        "loop": "testing",
        "path": "tests/dashboard/example.test.ts",
        "detail": "Foreign testing backlog should stay queued for testing.",
        "requires_llm": True,
        "fixability": "llm-assisted",
    }
    orchestrator.escalation_queue.enqueue(foreign_finding, runtime_dir=runtime_dir)
    session = orchestrator.session_detect.OrchestratorSessionContext(
        has_tool_access=True,
        has_llm=True,
        subagent_surface="claude-code",
    )
    task_calls: list[dict] = []

    result = orchestrator.orchestrate_run(
        "toy-loop",
        project_root=repo,
        runtime_dir=runtime_dir,
        state_dir=runtime_dir / "adaptive",
        commands=_commands(repo, []),
        trust_config=fixtures.build_toy_loop()["config"],
        session=session,
        verify_runner=lambda **_kwargs: True,
        task_invoker=lambda **kwargs: task_calls.append(kwargs)
        or {"status": "success", "commit_hash": "semantic789", "diagnostic": "ok"},
    )

    assert result.counts["findings"] == 3
    assert result.counts["dispatched"] == 1
    assert len(task_calls) == 1
    pending_rows = [
        json.loads(line)
        for line in pending_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(pending_rows) == 1
    assert pending_rows[0]["finding"]["loop"] == "testing"
    assert pending_rows[0]["finding"]["auto_command"] == "auto-test-dashboard"


def test_orchestrator_ignores_stale_same_loop_pending_from_deleted_worktree(tmp_path: Path) -> None:
    orchestrator = _load_orchestrator()
    fixtures = _load_fixture_helpers()
    repo = _init_repo(tmp_path)
    state_file = fixtures.build_trust_state_file(tmp_path)
    runtime_dir = state_file.parents[1]
    pending_path = runtime_dir / "jobs" / "_escalations" / "pending.jsonl"
    stale_finding = {
        "auto_command": "auto-semantic",
        "loop": "toy-loop",
        "detail": "Deleted worktree backlog should not dispatch into the current run.",
        "error": (
            "Cannot import fixture from "
            f"{repo / '.worktrees' / 'goal' / 'missing-run' / 'fixtures' / 'toy_loop' / 'auto_semantic.py'}"
        ),
        "requires_llm": True,
        "fixability": "llm-assisted",
    }
    orchestrator.escalation_queue.enqueue(stale_finding, runtime_dir=runtime_dir)
    session = orchestrator.session_detect.OrchestratorSessionContext(
        has_tool_access=True,
        has_llm=True,
        subagent_surface="claude-code",
    )
    task_calls: list[dict] = []

    result = orchestrator.orchestrate_run(
        "toy-loop",
        project_root=repo,
        runtime_dir=runtime_dir,
        state_dir=runtime_dir / "adaptive",
        commands=_commands(repo, []),
        trust_config=fixtures.build_toy_loop()["config"],
        session=session,
        verify_runner=lambda **_kwargs: True,
        task_invoker=lambda **kwargs: task_calls.append(kwargs)
        or {"status": "success", "commit_hash": "semantic999", "diagnostic": "ok"},
    )

    assert result.counts["findings"] == 3
    assert result.counts["dispatched"] == 1
    assert len(task_calls) == 1
    assert pending_path.read_text(encoding="utf-8") == ""
