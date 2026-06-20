# TODO_CLEANUP: This file is 1092 lines — consider splitting into smaller modules
"""Integration-style tests for the adaptive fix phase."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from skills.daemon.scripts.adaptive.engine import AdaptiveLoopEngine
from skills.daemon.scripts.adaptive.engine_fix_phase import (
    _dispatch_llm_fix,
    _parse_porcelain_paths,
    _revert_structural_commit,
    _rollback_llm_owned_changes,
    _status_paths,
    run_fix_phase,
)
from src.lib.ops_protocol import (
    FixClassification,
    FixResult,
    OpsContext,
    SessionContext,
)


class _MechanicalModule:
    def __init__(self) -> None:
        self.fix_calls = 0

    def fix(self, ctx, issues):
        self.fix_calls += 1
        return FixResult(
            success=True, changes=["src/safe.py"], summary="fixed", fix_type="code-fix"
        )


class _StructuralModule:
    def __init__(self) -> None:
        self.fix_calls = 0

    def fix(self, ctx, issues):
        self.fix_calls += 1
        return FixResult(
            success=True,
            changes=["src/ownership.py"],
            summary="fixed",
            fix_type="code-fix",
        )

    def scan(self, ctx):
        return SimpleNamespace(issues=[], summary="clean")


class _ReportOnlyModule:
    def __init__(self) -> None:
        self.fix_calls = 0

    def fix(self, ctx, issues):
        self.fix_calls += 1
        return FixResult(
            success=True,
            changes=["src/should-not-change.py"],
            summary="fixed",
            fix_type="code-fix",
        )


class _StructuralLlmModule:
    def fix(self, ctx, issues):
        return FixResult(
            success=True, changes=[], summary="needs llm", fix_type="report"
        )

    def llm_fix(self, ctx, issues):
        return "fix structurally"


def _build_engine(tmp_path: Path, runtime_dir: Path | None = None):
    config = {
        "engine": {"enabled": True, "verify_command": ""},
        "loops": {
            "observability": {
                "enabled": True,
                "trigger": "nightly",
                "budget": 3,
                "budget_growth_rate": 1,
                "categories": {
                    "demo-category": {"enabled": True, "trust": 0.6, "tier": 0},
                },
            }
        },
    }
    engine = AdaptiveLoopEngine(
        config, runtime_dir=runtime_dir or tmp_path, project_root=tmp_path
    )
    loop_state = engine.ledger.get_loop_state("observability")
    ctx = OpsContext(
        project_root=tmp_path,
        difficulty=2,
        session=SessionContext(),
    )
    entry = SimpleNamespace(
        name="demo-category",
        loop_name="observability",
        module=None,
        config={},
    )
    return engine, loop_state, ctx, entry


def _git(repo: Path, *args: str) -> str:
    import subprocess

    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(repo: Path) -> str:
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    return ""


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def test_parse_porcelain_paths_handles_rename_and_untracked_entries():
    output = "\n".join(
        [
            " M src/app.py",
            "R  old-name.md -> new-name.md",
            "?? generated/report.md",
        ]
    )

    assert _parse_porcelain_paths(output) == {
        "src/app.py": "M",
        "new-name.md": "R",
        "generated/report.md": "??",
    }


def test_rollback_blocks_committed_path_dirty_before_dispatch(tmp_path):
    _init_repo(tmp_path)
    protected = tmp_path / "protected.txt"
    protected.write_text("base\n", encoding="utf-8")
    head_before = _commit_all(tmp_path, "base")
    protected.write_text("user dirty\n", encoding="utf-8")
    status_before = {"protected.txt": "M"}
    _git(tmp_path, "add", "protected.txt")
    _git(tmp_path, "commit", "-m", "llm touched protected")

    try:
        _rollback_llm_owned_changes(tmp_path, head_before, status_before)
    except RuntimeError as exc:
        assert "already dirty before LLM dispatch" in str(exc)
    else:
        raise AssertionError("rollback should block instead of touching pre-dirty path")

    assert protected.read_text(encoding="utf-8") == "user dirty\n"


def test_rollback_blocks_committed_child_under_preexisting_untracked_dir(tmp_path):
    _init_repo(tmp_path)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("base\n", encoding="utf-8")
    head_before = _commit_all(tmp_path, "base")
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "user.md").write_text("keep user note\n", encoding="utf-8")
    status_before = {"notes": "??"}
    (notes / "draft.md").write_text("llm draft\n", encoding="utf-8")
    _git(tmp_path, "add", "notes/draft.md")
    _git(tmp_path, "commit", "-m", "llm draft")

    try:
        _rollback_llm_owned_changes(tmp_path, head_before, status_before)
    except RuntimeError as exc:
        assert "already dirty before LLM dispatch" in str(exc)
        assert "notes/draft.md" in str(exc)
    else:
        raise AssertionError(
            "rollback should block nested pre-existing untracked ownership"
        )

    assert (notes / "user.md").read_text(encoding="utf-8") == "keep user note\n"


def test_rollback_removes_top_level_untracked_file_with_unrelated_owner_dir(tmp_path):
    _init_repo(tmp_path)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("base\n", encoding="utf-8")
    head_before = _commit_all(tmp_path, "base")
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "user.txt").write_text("keep user note\n", encoding="utf-8")
    status_before = _status_paths(tmp_path)
    (tmp_path / "llm.txt").write_text("remove me\n", encoding="utf-8")

    reverted = _rollback_llm_owned_changes(tmp_path, head_before, status_before)

    assert reverted == ["llm.txt"]
    assert not (tmp_path / "llm.txt").exists()
    assert (notes / "user.txt").read_text(encoding="utf-8") == "keep user note\n"


def test_rollback_removes_untracked_file_inside_existing_clean_tracked_dir(tmp_path):
    _init_repo(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    tracked = src / "tracked.py"
    tracked.write_text("base\n", encoding="utf-8")
    head_before = _commit_all(tmp_path, "base")
    status_before = _status_paths(tmp_path)
    llm_tmp = src / "llm.tmp"
    llm_tmp.write_text("remove me\n", encoding="utf-8")

    reverted = _rollback_llm_owned_changes(tmp_path, head_before, status_before)

    assert reverted == ["src/llm.tmp"]
    assert not llm_tmp.exists()
    assert tracked.read_text(encoding="utf-8") == "base\n"
    assert _git(tmp_path, "status", "--porcelain") == ""


def test_rollback_restores_only_llm_owned_committed_paths(tmp_path):
    _init_repo(tmp_path)
    owned = tmp_path / "owned.txt"
    dirty = tmp_path / "dirty.txt"
    owned.write_text("base owned\n", encoding="utf-8")
    dirty.write_text("base dirty\n", encoding="utf-8")
    head_before = _commit_all(tmp_path, "base")
    dirty.write_text("user dirty\n", encoding="utf-8")
    status_before = {"dirty.txt": "M"}
    owned.write_text("llm edit\n", encoding="utf-8")
    _git(tmp_path, "add", "owned.txt")
    _git(tmp_path, "commit", "-m", "llm owned edit")

    reverted = _rollback_llm_owned_changes(tmp_path, head_before, status_before)

    assert reverted == ["owned.txt"]
    assert owned.read_text(encoding="utf-8") == "base owned\n"
    assert dirty.read_text(encoding="utf-8") == "user dirty\n"


def test_rollback_reverts_committed_llm_change_with_clean_worktree(tmp_path):
    _init_repo(tmp_path)
    owned = tmp_path / "owned.txt"
    owned.write_text("base owned\n", encoding="utf-8")
    head_before = _commit_all(tmp_path, "base")
    owned.write_text("llm edit\n", encoding="utf-8")
    _commit_all(tmp_path, "llm owned edit")

    reverted = _rollback_llm_owned_changes(tmp_path, head_before, {})

    assert reverted == ["owned.txt"]
    assert owned.read_text(encoding="utf-8") == "base owned\n"
    assert _git(tmp_path, "status", "--porcelain") == ""
    assert " revert " in f" {_git(tmp_path, 'log', '--oneline', '-1').lower()} "


def test_rollback_reverts_committed_rename_with_clean_worktree(tmp_path):
    _init_repo(tmp_path)
    old_path = tmp_path / "old.txt"
    old_path.write_text("base\n", encoding="utf-8")
    head_before = _commit_all(tmp_path, "base")
    _git(tmp_path, "mv", "old.txt", "new.txt")
    _git(tmp_path, "commit", "-m", "llm rename")

    reverted = _rollback_llm_owned_changes(tmp_path, head_before, {})

    assert reverted == ["new.txt", "old.txt"]
    assert old_path.read_text(encoding="utf-8") == "base\n"
    assert not (tmp_path / "new.txt").exists()
    assert _git(tmp_path, "status", "--porcelain") == ""


def test_rollback_removes_new_untracked_files_and_preserves_existing_untracked(
    tmp_path,
):
    _init_repo(tmp_path)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("base\n", encoding="utf-8")
    head_before = _commit_all(tmp_path, "base")
    existing_untracked = tmp_path / "existing.txt"
    existing_untracked.write_text("keep\n", encoding="utf-8")
    status_before = {"existing.txt": "??"}
    new_file = tmp_path / "new.txt"
    new_dir = tmp_path / "new-dir"
    new_dir.mkdir()
    (new_dir / "nested.txt").write_text("remove\n", encoding="utf-8")
    new_file.write_text("remove\n", encoding="utf-8")

    reverted = _rollback_llm_owned_changes(tmp_path, head_before, status_before)

    assert sorted(reverted) == ["new-dir", "new.txt"]
    assert existing_untracked.exists()
    assert not new_file.exists()
    assert not new_dir.exists()


def test_rollback_reports_git_failure_clearly(tmp_path):
    _init_repo(tmp_path)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("base\n", encoding="utf-8")
    _commit_all(tmp_path, "base")

    try:
        _rollback_llm_owned_changes(tmp_path, "missing-ref", {})
    except RuntimeError as exc:
        assert "Unable to inspect LLM commits" in str(exc)
    else:
        raise AssertionError("rollback should fail clearly for an invalid base ref")


def _dispatch_ctx(tmp_path: Path, *, timeout: float | None = 5) -> SimpleNamespace:
    return SimpleNamespace(
        project_root=tmp_path,
        session=SessionContext(
            has_llm=True,
            cli_path="fake-cli",
            max_turns=1,
            timeout=timeout,
        ),
    )


def _dispatch_engine(tmp_path: Path, verify_command: str = "") -> SimpleNamespace:
    return SimpleNamespace(_verify_command=verify_command, _llm_budget_multiplier=100)


def test_dispatch_rolls_back_successful_dirty_no_commit(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / "tracked.txt").write_text("base\n", encoding="utf-8")
    _commit_all(tmp_path, "base")
    monkeypatch.setattr(
        "src.lib.llm_retry.build_headless_cmd",
        lambda **_kwargs: [
            sys.executable,
            "-c",
            "from pathlib import Path; Path('llm.txt').write_text('dirty\\n')",
        ],
    )

    result = _dispatch_llm_fix(
        _dispatch_engine(tmp_path), _dispatch_ctx(tmp_path), "prompt", "dirty-no-commit"
    )

    assert result["success"] is False
    assert "rollback_paths" in result
    assert result["rollback_paths"] == ["llm.txt"]
    assert not (tmp_path / "llm.txt").exists()


def test_dispatch_blocks_no_commit_write_under_preexisting_untracked_dir(
    tmp_path, monkeypatch
):
    _init_repo(tmp_path)
    (tmp_path / "tracked.txt").write_text("base\n", encoding="utf-8")
    _commit_all(tmp_path, "base")
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "user.md").write_text("keep\n", encoding="utf-8")
    monkeypatch.setattr(
        "src.lib.llm_retry.build_headless_cmd",
        lambda **_kwargs: [
            sys.executable,
            "-c",
            "from pathlib import Path; Path('notes/draft.md').write_text('llm\\n')",
        ],
    )

    result = _dispatch_llm_fix(
        _dispatch_engine(tmp_path), _dispatch_ctx(tmp_path), "prompt", "dirty-owner-dir"
    )

    assert result["success"] is False
    assert (
        "introduced path(s) under pre-existing untracked owner directory"
        in result["error"]
    )
    assert "notes/draft.md" in result["error"]
    assert "rollback_paths" not in result
    assert (notes / "user.md").read_text(encoding="utf-8") == "keep\n"
    assert (notes / "draft.md").read_text(encoding="utf-8") == "llm\n"


def test_dispatch_rolls_back_nonzero_exit_dirty_change(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / "tracked.txt").write_text("base\n", encoding="utf-8")
    _commit_all(tmp_path, "base")
    monkeypatch.setattr(
        "src.lib.llm_retry.build_headless_cmd",
        lambda **_kwargs: [
            sys.executable,
            "-c",
            "from pathlib import Path; Path('failed.txt').write_text('dirty\\n'); raise SystemExit(7)",
        ],
    )

    result = _dispatch_llm_fix(
        _dispatch_engine(tmp_path), _dispatch_ctx(tmp_path), "prompt", "nonzero"
    )

    assert result["success"] is False
    assert result["rollback_paths"] == ["failed.txt"]
    assert not (tmp_path / "failed.txt").exists()


def test_dispatch_rolls_back_timeout_dirty_change(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / "tracked.txt").write_text("base\n", encoding="utf-8")
    _commit_all(tmp_path, "base")
    monkeypatch.setattr(
        "src.lib.llm_retry.build_headless_cmd",
        lambda **_kwargs: [
            sys.executable,
            "-c",
            "from pathlib import Path; import time; Path('timeout.txt').write_text('dirty\\n'); time.sleep(2)",
        ],
    )

    result = _dispatch_llm_fix(
        _dispatch_engine(tmp_path),
        _dispatch_ctx(tmp_path, timeout=0.1),
        "prompt",
        "timeout",
    )

    assert result["success"] is False
    assert "timed out" in result["error"]
    assert result["rollback_paths"] == ["timeout.txt"]
    assert not (tmp_path / "timeout.txt").exists()


def test_dispatch_rolls_back_build_verify_failure_with_revert_commit(
    tmp_path, monkeypatch
):
    _init_repo(tmp_path)
    (tmp_path / "tracked.ts").write_text("const value = 1;\n", encoding="utf-8")
    _commit_all(tmp_path, "base")
    monkeypatch.setattr(
        "src.lib.llm_retry.build_headless_cmd",
        lambda **_kwargs: [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; import subprocess; "
                "Path('tracked.ts').write_text('const value = 2;\\n'); "
                "subprocess.run(['git','add','tracked.ts'], check=True); "
                "subprocess.run(['git','commit','-m','llm ts edit'], check=True)"
            ),
        ],
    )

    result = _dispatch_llm_fix(
        _dispatch_engine(tmp_path, "false"), _dispatch_ctx(tmp_path), "prompt", "build"
    )

    assert result["success"] is False
    assert result["rollback_paths"] == ["tracked.ts"]
    assert (tmp_path / "tracked.ts").read_text(encoding="utf-8") == "const value = 1;\n"
    assert _git(tmp_path, "status", "--porcelain") == ""
    assert " revert " in f" {_git(tmp_path, 'log', '--oneline', '-1').lower()} "


def test_dispatch_rolls_back_committed_fix_with_leftover_untracked_file(
    tmp_path, monkeypatch
):
    _init_repo(tmp_path)
    owned = tmp_path / "owned.py"
    owned.write_text("base\n", encoding="utf-8")
    _commit_all(tmp_path, "base")
    monkeypatch.setattr(
        "src.lib.llm_retry.build_headless_cmd",
        lambda **_kwargs: [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; import subprocess; "
                "Path('owned.py').write_text('llm\\n'); "
                "subprocess.run(['git','add','owned.py'], check=True); "
                "subprocess.run(['git','commit','-m','llm edit'], check=True); "
                "Path('leftover.txt').write_text('dirty\\n')"
            ),
        ],
    )

    result = _dispatch_llm_fix(
        _dispatch_engine(tmp_path), _dispatch_ctx(tmp_path), "prompt", "commit-leftover"
    )

    assert result["success"] is False
    assert "left dirty state" in result["error"]
    assert owned.read_text(encoding="utf-8") == "base\n"
    assert not (tmp_path / "leftover.txt").exists()
    assert _git(tmp_path, "status", "--porcelain") == ""


def test_dispatch_fails_closed_when_successful_commit_includes_preexisting_dirty_file(
    tmp_path, monkeypatch
):
    _init_repo(tmp_path)
    dirty = tmp_path / "dirty.py"
    owned = tmp_path / "owned.py"
    dirty.write_text("base dirty\n", encoding="utf-8")
    owned.write_text("base owned\n", encoding="utf-8")
    _commit_all(tmp_path, "base")
    dirty.write_text("user dirty\n", encoding="utf-8")
    monkeypatch.setattr(
        "src.lib.llm_retry.build_headless_cmd",
        lambda **_kwargs: [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; import subprocess; "
                "Path('owned.py').write_text('llm owned\\n'); "
                "subprocess.run(['git','add','dirty.py','owned.py'], check=True); "
                "subprocess.run(['git','commit','-m','llm committed dirty and owned'], check=True)"
            ),
        ],
    )

    result = _dispatch_llm_fix(
        _dispatch_engine(tmp_path),
        _dispatch_ctx(tmp_path),
        "prompt",
        "dirty-commit-overlap",
    )

    assert result["success"] is False
    assert "pre-existing dirty path" in result["error"]
    assert "dirty.py" in result["error"]
    assert result["preexisting_dirty_paths"] == ["dirty.py"]
    assert result["changes"] == ["dirty.py", "owned.py"]
    assert "rollback_paths" not in result
    assert dirty.read_text(encoding="utf-8") == "user dirty\n"
    assert "llm committed dirty and owned" in _git(tmp_path, "log", "--oneline", "-1")


def test_dispatch_restores_preexisting_dirty_path_mutated_outside_llm_commit(
    tmp_path, monkeypatch
):
    _init_repo(tmp_path)
    dirty = tmp_path / "dirty.py"
    owned = tmp_path / "owned.py"
    dirty.write_text("base dirty\n", encoding="utf-8")
    owned.write_text("base owned\n", encoding="utf-8")
    _commit_all(tmp_path, "base")
    dirty.write_text("user dirty\n", encoding="utf-8")
    monkeypatch.setattr(
        "src.lib.llm_retry.build_headless_cmd",
        lambda **_kwargs: [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; import subprocess; "
                "Path('owned.py').write_text('llm owned\\n'); "
                "subprocess.run(['git','add','owned.py'], check=True); "
                "subprocess.run(['git','commit','-m','llm owned edit'], check=True); "
                "Path('dirty.py').write_text('llm corrupted dirty\\n')"
            ),
        ],
    )

    result = _dispatch_llm_fix(
        _dispatch_engine(tmp_path), _dispatch_ctx(tmp_path), "prompt", "dirty-mutated"
    )

    assert result["success"] is False
    assert "pre-existing dirty path" in result["error"]
    assert "dirty.py" in result["error"]
    assert result["preexisting_dirty_paths"] == ["dirty.py"]
    assert result["changes"] == ["owned.py"]
    assert result["rollback_paths"] == ["owned.py"]
    assert dirty.read_text(encoding="utf-8") == "user dirty\n"
    assert owned.read_text(encoding="utf-8") == "base owned\n"
    assert _git(tmp_path, "status", "--porcelain") == "M dirty.py"


def test_rollback_aborts_and_reports_partial_risk_when_revert_fails(
    tmp_path, monkeypatch
):
    _init_repo(tmp_path)
    (tmp_path / "owned.txt").write_text("base\n", encoding="utf-8")
    _commit_all(tmp_path, "base")
    calls: list[list[str]] = []

    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase._changed_paths_since",
        lambda *_args, **_kwargs: {"owned.txt"},
    )
    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase._commits_since",
        lambda *_args, **_kwargs: ["old-commit", "new-commit"],
    )

    def _fake_run_git(_project_root: Path, args: list[str], failure: str):
        calls.append(args)
        if args[:2] == ["revert", "--abort"]:
            return SimpleNamespace(stdout="")
        if args[:2] == ["revert", "--no-edit"] and args[-1] == "new-commit":
            return SimpleNamespace(stdout="")
        if args[:2] == ["revert", "--no-edit"] and args[-1] == "old-commit":
            raise RuntimeError(f"{failure}: conflict")
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase._run_git_checked",
        _fake_run_git,
    )

    try:
        _rollback_llm_owned_changes(tmp_path, "base", {})
    except RuntimeError as exc:
        assert "LLM rollback failed before completion" in str(exc)
        assert "partial rollback risk" in str(exc)
    else:
        raise AssertionError("rollback should fail clearly on revert conflict")

    assert ["revert", "--abort"] in calls


def test_engine_fix_phase_does_not_use_broad_destructive_git_rollback():
    daemon_root = Path(__file__).resolve().parents[2]
    source = (daemon_root / "scripts" / "adaptive" / "engine_fix_phase.py").read_text(
        encoding="utf-8"
    )

    assert "git reset --hard" not in source
    assert '"reset", "--hard"' not in source
    assert '"checkout", "--", "."' not in source


def test_structural_llm_verification_failure_rolls_back_llm_commit(
    tmp_path, monkeypatch
):
    project = tmp_path / "repo"
    project.mkdir()
    _init_repo(project)
    engine, loop_state, ctx, entry = _build_engine(
        project, runtime_dir=tmp_path / "runtime"
    )
    owned = project / "owned.py"
    owned.write_text("base\n", encoding="utf-8")
    head_before = _commit_all(project, "base")
    engine._llm_escalation_enabled = True
    engine._llm_min_trust = 0.1
    ctx.session = SessionContext(has_llm=True, cli_path="fake-cli")
    entry.module = _StructuralLlmModule()

    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.check_intentional_skip",
        lambda _path: "",
    )
    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.classify_fix",
        lambda *_args, **_kwargs: (FixClassification.STRUCTURAL, None),
    )
    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.collect_context",
        lambda **_kwargs: {
            "finding_band": "structural",
            "sources": [{"kind": "adr", "path": "project-brain/decisions/adrs/ADR-999.md"}],
        },
    )
    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.write_design_gate",
        lambda **_kwargs: {"written": True, "path": str(tmp_path / "gate.md")},
    )
    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase._verify_fix_reduced_issues",
        lambda *_args, **_kwargs: (False, 1),
    )

    def _fake_dispatch(_engine, _ctx, _prompt, _loop_name):
        owned.write_text("llm\n", encoding="utf-8")
        _commit_all(project, "llm structural edit")
        return {
            "success": True,
            "summary": "committed",
            "changes": ["owned.py"],
            "_head_before": head_before,
            "_status_before": {},
        }

    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase._dispatch_llm_fix",
        _fake_dispatch,
    )

    issues = [
        {"path": "owned.py", "detail": "needs structural llm", "ownership_change": True}
    ]
    issue_counts = engine._count_issue_kinds(issues)
    results: list = []
    cat_reports: list = []

    run_fix_phase(
        engine=engine,
        loop_name="observability",
        loop_state=loop_state,
        entry=entry,
        ctx=ctx,
        issues=issues,
        issue_counts=issue_counts,
        scan_duration_ms=1,
        trust_before=0.6,
        diff_before=ctx.difficulty,
        strategy_before="scan",
        deepening_reason="",
        execution_mode="deep",
        should_short_circuit=False,
        snap_fp="snap",
        yc="normal",
        new_count=0,
        repeated_count=0,
        resolved_count=0,
        results=results,
        cat_reports=cat_reports,
        invalidated_categories=set(),
        dep_invalidations={},
        allow_invalidations=False,
        t0=time.monotonic(),
    )

    assert results[-1].success is False
    assert "rolled back" in results[-1].error
    assert owned.read_text(encoding="utf-8") == "base\n"
    assert _git(project, "status", "--porcelain") == ""


def test_revert_structural_commit_targets_supplied_commit_without_reverting_later_work(
    tmp_path,
):
    _init_repo(tmp_path)
    owned = tmp_path / "owned.py"
    owned.write_text("base\n", encoding="utf-8")
    _commit_all(tmp_path, "base")

    owned.write_text("llm structural edit\n", encoding="utf-8")
    structural_commit = _commit_all(tmp_path, "llm structural edit")

    notes = tmp_path / "notes.md"
    notes.write_text("user work\n", encoding="utf-8")
    later_commit = _commit_all(tmp_path, "later user work")

    assert _revert_structural_commit(tmp_path, structural_commit) is True
    assert owned.read_text(encoding="utf-8") == "base\n"
    assert notes.read_text(encoding="utf-8") == "user work\n"
    assert _git(tmp_path, "rev-parse", "HEAD") != later_commit
    assert "llm structural edit" in _git(tmp_path, "log", "--oneline", "-1")
    assert _git(tmp_path, "status", "--porcelain") == ""


def test_generic_llm_scanner_exception_fails_closed_and_rolls_back(
    tmp_path, monkeypatch
):
    project = tmp_path / "repo"
    project.mkdir()
    _init_repo(project)
    engine, loop_state, ctx, entry = _build_engine(
        project, runtime_dir=tmp_path / "runtime"
    )
    owned = project / "owned.py"
    owned.write_text("base\n", encoding="utf-8")
    head_before = _commit_all(project, "base")
    engine._llm_escalation_enabled = True
    engine._llm_min_trust = 0.1
    ctx.session = SessionContext(has_llm=True, cli_path="fake-cli")

    class _GenericReportModule:
        def fix(self, _ctx, _issues):
            return FixResult(
                success=True, changes=[], summary="needs llm", fix_type="report"
            )

        def scan(self, _ctx):
            raise RuntimeError("scanner exploded")

    entry.module = _GenericReportModule()

    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.check_intentional_skip",
        lambda _path: "",
    )
    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.classify_fix",
        lambda *_args, **_kwargs: (FixClassification.SAFE, None),
    )

    def _fake_dispatch(_engine, _ctx, _prompt, _loop_name):
        owned.write_text("llm\n", encoding="utf-8")
        _commit_all(project, "llm generic edit")
        return {
            "success": True,
            "summary": "committed",
            "changes": ["owned.py"],
            "_head_before": head_before,
            "_status_before": {},
        }

    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase._dispatch_llm_fix",
        _fake_dispatch,
    )

    issues = [
        {
            "path": "owned.py",
            "detail": "generic actionable finding",
            "kind": "actionable",
        }
    ]
    issue_counts = engine._count_issue_kinds(issues)
    results: list = []
    cat_reports: list = []

    run_fix_phase(
        engine=engine,
        loop_name="observability",
        loop_state=loop_state,
        entry=entry,
        ctx=ctx,
        issues=issues,
        issue_counts=issue_counts,
        scan_duration_ms=1,
        trust_before=0.6,
        diff_before=ctx.difficulty,
        strategy_before="scan",
        deepening_reason="",
        execution_mode="deep",
        should_short_circuit=False,
        snap_fp="snap",
        yc="normal",
        new_count=0,
        repeated_count=0,
        resolved_count=0,
        results=results,
        cat_reports=cat_reports,
        invalidated_categories=set(),
        dep_invalidations={},
        allow_invalidations=False,
        t0=time.monotonic(),
    )

    assert results[-1].success is False
    assert "rolled back" in results[-1].error
    assert owned.read_text(encoding="utf-8") == "base\n"
    assert _git(project, "status", "--porcelain") == ""


def test_run_fix_phase_keeps_safe_issue_local_when_structural_issue_is_blocked(
    tmp_path, monkeypatch
):
    engine, loop_state, ctx, entry = _build_engine(tmp_path)
    module = _MechanicalModule()
    entry.module = module

    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.check_intentional_skip",
        lambda path: "user-owned" if path == "src/unsafe.py" else "",
    )
    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.classify_fix",
        lambda *_args, **_kwargs: (FixClassification.SAFE, None),
    )
    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.collect_context",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("mechanical issue should stay local")
        ),
    )

    issues = [
        {
            "path": "src/unsafe.py",
            "detail": "Move ownership to codex",
            "ownership_change": True,
        },
        {
            "path": "src/safe.py",
            "detail": "Fix a local typo",
            "tool_name_mismatch": True,
        },
    ]
    issue_counts = engine._count_issue_kinds(issues)
    results: list = []
    cat_reports: list = []

    run_fix_phase(
        engine=engine,
        loop_name="observability",
        loop_state=loop_state,
        entry=entry,
        ctx=ctx,
        issues=issues,
        issue_counts=issue_counts,
        scan_duration_ms=1,
        trust_before=0.6,
        diff_before=ctx.difficulty,
        strategy_before="scan",
        deepening_reason="",
        execution_mode="deep",
        should_short_circuit=False,
        snap_fp="snap",
        yc="normal",
        new_count=0,
        repeated_count=0,
        resolved_count=0,
        results=results,
        cat_reports=cat_reports,
        invalidated_categories=set(),
        dep_invalidations={},
        allow_invalidations=False,
        t0=time.monotonic(),
    )

    assert module.fix_calls == 1
    assert cat_reports[-1].outcome == "auto-fixed"


def test_run_fix_phase_writes_design_gate_before_structural_fix_at_low_difficulty(
    tmp_path, monkeypatch
):
    engine, loop_state, ctx, entry = _build_engine(tmp_path)
    ctx.difficulty = 0
    module = _StructuralModule()
    entry.module = module

    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.check_intentional_skip",
        lambda _path: "",
    )
    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.classify_fix",
        lambda *_args, **_kwargs: (FixClassification.STRUCTURAL, None),
    )
    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.collect_context",
        lambda **_kwargs: {
            "finding_band": "structural",
            "sources": [
                {
                    "kind": "adr",
                    "path": "project-brain/decisions/adrs/ADR-999.md",
                    "title": "Ownership",
                    "excerpt": "...",
                }
            ],
        },
    )
    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.write_design_gate",
        lambda **_kwargs: {"written": True, "path": str(tmp_path / "gate.md")},
    )

    issues = [
        {
            "path": "src/ownership.py",
            "detail": "Move scheduler ownership to codex",
            "ownership_change": True,
        }
    ]
    issue_counts = engine._count_issue_kinds(issues)
    results: list = []
    cat_reports: list = []

    run_fix_phase(
        engine=engine,
        loop_name="observability",
        loop_state=loop_state,
        entry=entry,
        ctx=ctx,
        issues=issues,
        issue_counts=issue_counts,
        scan_duration_ms=1,
        trust_before=0.6,
        diff_before=ctx.difficulty,
        strategy_before="scan",
        deepening_reason="",
        execution_mode="deep",
        should_short_circuit=False,
        snap_fp="snap",
        yc="normal",
        new_count=0,
        repeated_count=0,
        resolved_count=0,
        results=results,
        cat_reports=cat_reports,
        invalidated_categories=set(),
        dep_invalidations={},
        allow_invalidations=False,
        t0=time.monotonic(),
    )

    assert module.fix_calls == 0
    assert cat_reports[-1].outcome == "design-written"


def test_run_fix_phase_marks_blocked_needs_design_when_gate_write_fails(
    tmp_path, monkeypatch
):
    engine, loop_state, ctx, entry = _build_engine(tmp_path)
    ctx.difficulty = 2
    module = _StructuralModule()
    entry.module = module

    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.check_intentional_skip",
        lambda _path: "",
    )
    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.classify_fix",
        lambda *_args, **_kwargs: (FixClassification.STRUCTURAL, None),
    )
    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.collect_context",
        lambda **_kwargs: {
            "finding_band": "structural",
            "sources": [
                {
                    "kind": "adr",
                    "path": "project-brain/decisions/adrs/ADR-999.md",
                    "title": "Ownership",
                    "excerpt": "...",
                }
            ],
        },
    )

    def _raise(**_kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.write_design_gate",
        _raise,
    )

    issues = [
        {
            "path": "src/ownership.py",
            "detail": "Move scheduler ownership to codex",
            "ownership_change": True,
        }
    ]
    issue_counts = engine._count_issue_kinds(issues)
    results: list = []
    cat_reports: list = []

    run_fix_phase(
        engine=engine,
        loop_name="observability",
        loop_state=loop_state,
        entry=entry,
        ctx=ctx,
        issues=issues,
        issue_counts=issue_counts,
        scan_duration_ms=1,
        trust_before=0.6,
        diff_before=ctx.difficulty,
        strategy_before="scan",
        deepening_reason="",
        execution_mode="deep",
        should_short_circuit=False,
        snap_fp="snap",
        yc="normal",
        new_count=0,
        repeated_count=0,
        resolved_count=0,
        results=results,
        cat_reports=cat_reports,
        invalidated_categories=set(),
        dep_invalidations={},
        allow_invalidations=False,
        t0=time.monotonic(),
    )

    assert module.fix_calls == 0
    assert cat_reports[-1].outcome == "blocked-needs-design"


def test_run_fix_phase_respects_platform_report_only_mode(tmp_path, monkeypatch):
    engine, loop_state, ctx, entry = _build_engine(tmp_path)
    module = _ReportOnlyModule()
    entry.module = module
    ctx.config = {
        "_ops_fix_mode": "report_only",
        "_ops_skip_reason": "safe subset only",
    }

    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.check_intentional_skip",
        lambda _path: "",
    )
    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.classify_fix",
        lambda *_args, **_kwargs: (FixClassification.SAFE, None),
    )

    issues = [{"path": "src/report.py", "detail": "Windows-safe check finding"}]
    issue_counts = engine._count_issue_kinds(issues)
    results: list = []
    cat_reports: list = []

    run_fix_phase(
        engine=engine,
        loop_name="observability",
        loop_state=loop_state,
        entry=entry,
        ctx=ctx,
        issues=issues,
        issue_counts=issue_counts,
        scan_duration_ms=1,
        trust_before=0.6,
        diff_before=ctx.difficulty,
        strategy_before="scan",
        deepening_reason="",
        execution_mode="deep",
        should_short_circuit=False,
        snap_fp="snap",
        yc="normal",
        new_count=0,
        repeated_count=0,
        resolved_count=0,
        results=results,
        cat_reports=cat_reports,
        invalidated_categories=set(),
        dep_invalidations={},
        allow_invalidations=False,
        t0=time.monotonic(),
    )

    assert module.fix_calls == 0
    assert cat_reports[-1].outcome == "report-only"
    assert "safe subset only" in cat_reports[-1].action_summary


def test_run_fix_phase_respects_platform_report_only_mode_without_reason(
    tmp_path, monkeypatch
):
    engine, loop_state, ctx, entry = _build_engine(tmp_path)
    module = _ReportOnlyModule()
    entry.module = module
    ctx.config = {"_ops_fix_mode": "report_only", "_ops_skip_reason": ""}
    ctx.session = SessionContext(has_llm=True)

    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.check_intentional_skip",
        lambda _path: "",
    )
    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase.classify_fix",
        lambda *_args, **_kwargs: (FixClassification.SAFE, None),
    )
    monkeypatch.setattr(
        "skills.daemon.scripts.adaptive.engine_fix_phase._dispatch_llm_fix",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("generic LLM fallback must stay disabled")
        ),
    )

    issues = [{"path": "src/report.py", "detail": "Windows-safe check finding"}]
    issue_counts = engine._count_issue_kinds(issues)
    results: list = []
    cat_reports: list = []

    run_fix_phase(
        engine=engine,
        loop_name="observability",
        loop_state=loop_state,
        entry=entry,
        ctx=ctx,
        issues=issues,
        issue_counts=issue_counts,
        scan_duration_ms=1,
        trust_before=0.6,
        diff_before=ctx.difficulty,
        strategy_before="scan",
        deepening_reason="",
        execution_mode="deep",
        should_short_circuit=False,
        snap_fp="snap",
        yc="normal",
        new_count=0,
        repeated_count=0,
        resolved_count=0,
        results=results,
        cat_reports=cat_reports,
        invalidated_categories=set(),
        dep_invalidations={},
        allow_invalidations=False,
        t0=time.monotonic(),
    )

    assert module.fix_calls == 0
    assert cat_reports[-1].outcome == "report-only"
