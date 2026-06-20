"""Tests for ADR-755 pure-Python mechanical fix application."""
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
FIX_PHASE_PATH = DAEMON_SCRIPTS_DIR / "routine_orchestrator" / "fix_phase_mechanical.py"

if str(DAEMON_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(DAEMON_SCRIPTS_DIR))


def _load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_fix_phase():
    return _load_module("routine_orchestrator_fix_phase_under_test", FIX_PHASE_PATH)


def _load_fixture_helpers():
    return _load_module("orchestrator_fixtures_mechanical_fix", TESTS_DIR / "_fixtures.py")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _init_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Augur Tests")
    (repo / "toy.txt").write_text("before\n", encoding="utf-8")
    _git(repo, "add", "toy.txt")
    _git(repo, "commit", "-m", "initial")
    return repo


def _finding(*, band: str = "mechanical", path: str = "toy.txt", command: str = "auto-mech") -> dict:
    return {
        "auto_command": command,
        "loop": "toy-loop",
        "path": path,
        "detail": f"{band} finding",
        "finding_band": band,
    }


def _command(repo: Path, *, name: str = "auto-mech", verify_command: object | None = None):
    calls: list[list[dict]] = []

    def fix(ctx, issues: list[dict]) -> FixResult:
        calls.append(issues)
        (repo / "toy.txt").write_text("after\n", encoding="utf-8")
        return FixResult(
            success=True,
            changes=["toy.txt"],
            summary="updated toy file",
            fix_type="code-fix",
        )

    module = SimpleNamespace(name=name, fix=fix, verify_command=verify_command)
    return SimpleNamespace(name=name, module=module, loop_name="toy-loop", config={}), calls


def _raising_command(repo: Path, *, name: str = "auto-mech"):
    calls: list[list[dict]] = []

    def fix(ctx, issues: list[dict]) -> FixResult:
        calls.append(issues)
        (repo / "toy.txt").write_text("after exception\n", encoding="utf-8")
        raise RuntimeError("fixture boom")

    module = SimpleNamespace(name=name, fix=fix)
    return SimpleNamespace(name=name, module=module, loop_name="toy-loop", config={}), calls


def _unreported_command(repo: Path, *, name: str = "auto-mech"):
    calls: list[list[dict]] = []

    def fix(ctx, issues: list[dict]) -> FixResult:
        calls.append(issues)
        (repo / "toy.txt").write_text("reported\n", encoding="utf-8")
        (repo / "unreported.txt").write_text("unreported\n", encoding="utf-8")
        return FixResult(
            success=True,
            changes=["toy.txt"],
            summary="updated reported and unreported files",
            fix_type="code-fix",
        )

    module = SimpleNamespace(name=name, fix=fix)
    return SimpleNamespace(name=name, module=module, loop_name="toy-loop", config={}), calls


def _mutates_dirty_non_target_command(repo: Path, *, name: str = "auto-mech"):
    calls: list[list[dict]] = []

    def fix(ctx, issues: list[dict]) -> FixResult:
        calls.append(issues)
        (repo / "toy.txt").write_text("reported\n", encoding="utf-8")
        (repo / "note.txt").write_text("clobbered dirty note\n", encoding="utf-8")
        return FixResult(
            success=True,
            changes=["toy.txt"],
            summary="updated reported file but touched dirty note",
            fix_type="code-fix",
        )

    module = SimpleNamespace(name=name, fix=fix)
    return SimpleNamespace(name=name, module=module, loop_name="toy-loop", config={}), calls


def _trust_config() -> dict:
    return _load_fixture_helpers().build_toy_loop()["config"]


def test_mechanical_fix_applies_pure_python_only(tmp_path: Path) -> None:
    fix_phase = _load_fix_phase()
    repo = _init_git_repo(tmp_path)
    command, calls = _command(repo)

    def no_subagent_dispatch(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("mechanical fix path must not dispatch subagents")

    result = fix_phase.apply_mechanical_fixes(
        [_finding()],
        commands=[command],
        project_root=repo,
        state_dir=tmp_path / "state",
        trust_config=_trust_config(),
        subagent_dispatch=no_subagent_dispatch,
    )

    assert calls == [[_finding()]]
    assert (repo / "toy.txt").read_text(encoding="utf-8") == "after\n"
    assert result.applied[0].changed_files == ["toy.txt"]
    assert result.deferred == []


def test_mechanical_fix_invokes_verify_command_and_reverts_on_failure(tmp_path: Path) -> None:
    fix_phase = _load_fix_phase()
    repo = _init_git_repo(tmp_path)
    command, _calls = _command(repo, verify_command=["verify-toy"])
    verify_calls: list[object] = []

    def failing_verify(*, verify_command, ctx, changed_files, finding, command_entry):
        verify_calls.append((verify_command, changed_files, finding["path"], command_entry.name))
        return False

    result = fix_phase.apply_mechanical_fixes(
        [_finding()],
        commands=[command],
        project_root=repo,
        state_dir=tmp_path / "state",
        trust_config=_trust_config(),
        verify_runner=failing_verify,
    )

    assert verify_calls == [(["verify-toy"], ["toy.txt"], "toy.txt", "auto-mech")]
    assert result.applied == []
    assert result.failed[0].reason == "verify failed"
    assert (repo / "toy.txt").read_text(encoding="utf-8") == "before\n"
    assert _git(repo, "rev-list", "--count", "HEAD") == "1"
    state = json.loads((tmp_path / "state" / "trust_state.json").read_text(encoding="utf-8"))
    category = state["loops"]["toy-loop"]["categories"]["auto-mech"]
    assert category["failure_count"] == 1
    assert category["consecutive_failures"] == 1


def test_mechanical_fix_uses_project_verify_command_when_command_has_none(tmp_path: Path) -> None:
    fix_phase = _load_fix_phase()
    repo = _init_git_repo(tmp_path)
    config_dir = repo / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "adaptive_loops.yaml").write_text(
        "engine:\n  verify_command: python -m compileall project-brain\n",
        encoding="utf-8",
    )
    command, _calls = _command(repo)
    verify_calls: list[object] = []

    result = fix_phase.apply_mechanical_fixes(
        [_finding()],
        commands=[command],
        project_root=repo,
        state_dir=tmp_path / "state",
        trust_config=_trust_config(),
        verify_runner=lambda **kwargs: verify_calls.append(kwargs["verify_command"]) or True,
    )

    assert len(result.applied) == 1
    assert verify_calls == ["python -m compileall project-brain"]


def test_mechanical_fix_preserves_preexisting_dirty_target_without_fixing(tmp_path: Path) -> None:
    fix_phase = _load_fix_phase()
    repo = _init_git_repo(tmp_path)
    (repo / "toy.txt").write_text("user dirty\n", encoding="utf-8")
    command, calls = _command(repo)

    result = fix_phase.apply_mechanical_fixes(
        [_finding()],
        commands=[command],
        project_root=repo,
        state_dir=tmp_path / "state",
        trust_config=_trust_config(),
    )

    assert calls == []
    assert result.applied == []
    assert result.failed[0].reason == "pre-existing changes in target path"
    assert (repo / "toy.txt").read_text(encoding="utf-8") == "user dirty\n"
    assert _git(repo, "rev-list", "--count", "HEAD") == "1"


def test_mechanical_fix_reverts_and_records_failure_when_fix_raises(tmp_path: Path) -> None:
    fix_phase = _load_fix_phase()
    repo = _init_git_repo(tmp_path)
    command, calls = _raising_command(repo)

    result = fix_phase.apply_mechanical_fixes(
        [_finding()],
        commands=[command],
        project_root=repo,
        state_dir=tmp_path / "state",
        trust_config=_trust_config(),
    )

    assert calls == [[_finding()]]
    assert result.applied == []
    assert result.failed[0].reason == "fix raised: fixture boom"
    assert result.failed[0].changed_files == ["toy.txt"]
    assert (repo / "toy.txt").read_text(encoding="utf-8") == "before\n"
    state = json.loads((tmp_path / "state" / "trust_state.json").read_text(encoding="utf-8"))
    category = state["loops"]["toy-loop"]["categories"]["auto-mech"]
    assert category["failure_count"] == 1


def test_mechanical_fix_rejects_unreported_file_mutations(tmp_path: Path) -> None:
    fix_phase = _load_fix_phase()
    repo = _init_git_repo(tmp_path)
    command, calls = _unreported_command(repo)

    result = fix_phase.apply_mechanical_fixes(
        [_finding()],
        commands=[command],
        project_root=repo,
        state_dir=tmp_path / "state",
        trust_config=_trust_config(),
    )

    assert calls == [[_finding()]]
    assert result.applied == []
    assert result.failed[0].reason == "fix changed unreported paths"
    assert result.failed[0].changed_files == ["toy.txt", "unreported.txt"]
    assert (repo / "toy.txt").read_text(encoding="utf-8") == "before\n"
    assert not (repo / "unreported.txt").exists()
    assert _git(repo, "status", "--porcelain") == ""


def test_mechanical_fix_restores_preexisting_dirty_non_target_mutations(tmp_path: Path) -> None:
    fix_phase = _load_fix_phase()
    repo = _init_git_repo(tmp_path)
    (repo / "note.txt").write_text("clean note\n", encoding="utf-8")
    _git(repo, "add", "note.txt")
    _git(repo, "commit", "-m", "add note")
    (repo / "note.txt").write_text("user dirty note\n", encoding="utf-8")
    command, calls = _mutates_dirty_non_target_command(repo)

    result = fix_phase.apply_mechanical_fixes(
        [_finding()],
        commands=[command],
        project_root=repo,
        state_dir=tmp_path / "state",
        trust_config=_trust_config(),
    )

    assert calls == [[_finding()]]
    assert result.applied == []
    assert result.failed[0].reason == "fix changed pre-existing dirty paths"
    assert sorted(result.failed[0].changed_files) == ["note.txt", "toy.txt"]
    assert (repo / "note.txt").read_text(encoding="utf-8") == "user dirty note\n"
    assert (repo / "toy.txt").read_text(encoding="utf-8") == "before\n"
    assert _git(repo, "status", "--porcelain") == "M note.txt"


def test_mechanical_fix_skips_non_mechanical_findings(tmp_path: Path) -> None:
    fix_phase = _load_fix_phase()
    repo = _init_git_repo(tmp_path)
    command, calls = _command(repo)
    fixtures = _load_fixture_helpers()
    semantic_module = _load_module(
        "toy_auto_semantic_for_mechanical_fix",
        fixtures.TOY_LOOP_FIXTURE_DIR / "auto_semantic.py",
    )
    semantic_finding = semantic_module.scan(None).issues[0]
    semantic_finding["auto_command"] = "auto-semantic"
    semantic_finding["loop"] = "toy-loop"

    result = fix_phase.apply_mechanical_fixes(
        [
            semantic_finding,
            _finding(band="structural"),
            _finding(),
        ],
        commands=[command],
        project_root=repo,
        state_dir=tmp_path / "state",
        trust_config=_trust_config(),
    )

    assert calls == [[_finding()]]
    assert result.deferred == [semantic_finding, _finding(band="structural")]
    assert len(result.applied) == 1


def test_mechanical_fix_records_trust_success_on_verified_commit(tmp_path: Path) -> None:
    fix_phase = _load_fix_phase()
    repo = _init_git_repo(tmp_path)
    command, _calls = _command(repo, verify_command=["verify-toy"])

    result = fix_phase.apply_mechanical_fixes(
        [_finding()],
        commands=[command],
        project_root=repo,
        state_dir=tmp_path / "state",
        trust_config=_trust_config(),
        verify_runner=lambda **_kwargs: True,
        difficulty=2,
    )

    assert len(result.applied) == 1
    assert result.applied[0].commit
    assert "ADR-755 mechanical fix: auto-mech" in _git(repo, "log", "-1", "--pretty=%s")

    state = json.loads((tmp_path / "state" / "trust_state.json").read_text(encoding="utf-8"))
    category = state["loops"]["toy-loop"]["categories"]["auto-mech"]
    assert category["success_count"] == 1
    assert category["consecutive_successes"] == 1
    assert category["trust"] > 0.8
    assert category["total_fixes"] == 1
    assert category["total_commits"] == 1
    assert category["commit_trust"] > 0
    assert category["last_commit_trust_credit"] > 0
    assert category["max_committed_difficulty"] == 2
    assert category["pending_commit_verification"] is True


def test_default_verify_runner_string_command_uses_shlex_not_shell(tmp_path: Path) -> None:
    """_default_verify_runner must split a string verify_command via shlex, NOT shell=True.

    Regression guard for the security fix: previously `subprocess.run(..., shell=True)` was
    used for the string fallback path.  This test confirms the string is split into a list and
    the subprocess is launched without a shell (a mock replaces subprocess.run to inspect args).
    """
    import unittest.mock as mock
    from types import SimpleNamespace

    fix_phase = _load_fix_phase()

    ctx = SimpleNamespace(project_root=tmp_path)
    captured: list[dict] = []

    def fake_subprocess_run(cmd, **kwargs):
        captured.append({"cmd": cmd, "kwargs": kwargs})
        return SimpleNamespace(returncode=0)

    with mock.patch.object(fix_phase.subprocess, "run", side_effect=fake_subprocess_run):
        result = fix_phase._default_verify_runner(
            verify_command="python -c 'print(1)'",
            ctx=ctx,
            changed_files=[],
            finding={},
            command_entry=SimpleNamespace(name="test"),
        )

    assert result is True
    assert len(captured) == 1
    call = captured[0]
    # Must be a list (shlex-split), never a plain string (which triggers shell=True path)
    assert isinstance(call["cmd"], list), f"expected list, got {type(call['cmd'])}: {call['cmd']}"
    assert call["cmd"] == ["python", "-c", "print(1)"]
    # Must NOT pass shell=True
    assert not call["kwargs"].get("shell"), "shell=True must NOT be passed for string verify_command"
