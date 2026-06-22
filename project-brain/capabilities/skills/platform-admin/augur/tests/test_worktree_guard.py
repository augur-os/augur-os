"""Tests for worktree branch safety + worktree-removal (live-process) guards."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
MODULE_PATH = SCRIPTS_DIR / "worktree_guard.py"


def _module():
    module_name = "platform_admin_worktree_guard_test"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Codex")
    _git(repo, "config", "user.email", "codex@example.com")
    (repo / "README.md").write_text("root\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")
    return repo


def _init_unborn_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "unborn"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    return repo


def test_main_checkout_guard_passes_on_main(tmp_path: Path) -> None:
    mod = _module()
    repo = _init_repo(tmp_path)

    result = mod.check_main_checkout_branch(repo)

    assert result.ok is True
    assert result.branch == "main"
    assert result.is_main_checkout is True


def test_main_checkout_guard_passes_on_unborn_main_branch(tmp_path: Path) -> None:
    mod = _module()
    repo = _init_unborn_repo(tmp_path)

    result = mod.check_main_checkout_branch(repo)

    assert result.ok is True
    assert result.branch == "main"
    assert result.is_main_checkout is True


def test_main_checkout_guard_blocks_non_main_primary_checkout(tmp_path: Path, monkeypatch) -> None:
    mod = _module()
    repo = _init_repo(tmp_path)
    _git(repo, "checkout", "-b", "feature")
    # The guard is bypassed in CI; this test asserts the developer-machine
    # behaviour, so clear the CI markers the runner itself sets.
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    result = mod.check_main_checkout_branch(repo)

    assert result.ok is False
    assert result.branch == "feature"
    assert result.is_main_checkout is True
    assert "main checkout is on feature" in result.message


def test_main_checkout_guard_bypassed_in_ci_on_non_main(tmp_path: Path, monkeypatch) -> None:
    mod = _module()
    repo = _init_repo(tmp_path)
    _git(repo, "checkout", "-b", "release/v9.9.9")
    monkeypatch.setenv("CI", "true")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    result = mod.check_main_checkout_branch(repo)

    assert result.ok is True
    assert result.branch == "release/v9.9.9"
    assert result.is_main_checkout is True
    assert "bypassed in CI" in result.message


def test_main_checkout_guard_allows_non_main_linked_worktree(tmp_path: Path) -> None:
    mod = _module()
    repo = _init_repo(tmp_path)
    worktree = tmp_path / "augur-wt-feature"
    _git(repo, "worktree", "add", "-b", "feature", str(worktree))

    result = mod.check_main_checkout_branch(worktree)

    assert result.ok is True
    assert result.branch == "feature"
    assert result.is_main_checkout is False


# ── Live AI/client process ownership guard ────────────────────────────────────
# The shared guard every worktree-removal path runs before deleting a worktree.


def test_active_ai_processes_parses_lsof_stdout_when_returncode_is_nonzero(monkeypatch):
    mod = _module()

    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout="p123\nccodex\np456\ncnode\n",
            stderr="",
        )

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(mod, "_current_process_lineage", lambda: set())

    assert mod.active_ai_processes_for_path(Path("/tmp/augur-wt-active")) == [
        mod.ActiveWorktreeProcess(pid=123, command="codex")
    ]


def test_current_process_lineage_includes_self_and_ancestors():
    mod = _module()
    lineage = mod._current_process_lineage()

    # The running test process is always part of its own lineage, and on any
    # real OS it has at least one ancestor (the shell / runner that spawned it).
    assert os.getpid() in lineage
    assert len(lineage) >= 1


def test_current_process_lineage_falls_back_when_ps_is_unavailable(monkeypatch):
    mod = _module()

    def fake_run(*_args, **_kwargs):
        raise FileNotFoundError("ps")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(
        mod,
        "_windows_process_rows",
        lambda: [
            {"ProcessId": os.getpid(), "ParentProcessId": 1234},
            {"ProcessId": 1234, "ParentProcessId": 0},
        ],
    )

    assert mod._current_process_lineage() == {os.getpid(), 1234}


def test_active_ai_processes_excludes_own_process_lineage(monkeypatch):
    """The shell that invokes a worktree-removal path routinely carries the
    target worktree path in its command line (Codex repair args) and matches
    `claude` via the shell-snapshot path. It must not be reported as a foreign
    owner — only genuine foreign sessions block removal."""
    mod = _module()
    worktree_path = Path("/tmp/augur-wt-active")

    def fake_run(args, **_kwargs):
        if args[:2] == ["lsof", "-Fpc"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        if args[:2] == ["ps", "-axo"]:
            return SimpleNamespace(
                returncode=0,
                stdout=(
                    " 111 /bin/zsh -c codex_thread_state.py "
                    "--worktree-path /tmp/augur-wt-active\n"
                    " 222 /Users/x/.local/bin/claude "
                    "--dangerously-skip-permissions /tmp/augur-wt-active\n"
                ),
                stderr="",
            )
        if args == ["ps", "-axE", "-o", "pid=,command="]:
            # Env-var detection finds nothing in this scenario.
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(args)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    # PID 111 is the invoking shell (in our lineage); PID 222 is a genuine
    # foreign Claude session that still owns the worktree.
    monkeypatch.setattr(mod, "_current_process_lineage", lambda: {111})

    assert mod.active_ai_processes_for_path(worktree_path) == [
        mod.ActiveWorktreeProcess(
            pid=222,
            command=(
                "/Users/x/.local/bin/claude "
                "--dangerously-skip-permissions /tmp/augur-wt-active"
            ),
        )
    ]


def test_active_ai_processes_detects_worktree_owned_process_from_commandline(monkeypatch):
    mod = _module()
    worktree_path = Path("/tmp/augur-wt-active")

    def fake_run(args, **_kwargs):
        if args[:2] == ["lsof", "-Fpc"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        if args[:2] == ["ps", "-axo"]:
            return SimpleNamespace(
                returncode=0,
                stdout=(
                    " 123 /tmp/augur-wt-active/.venv/bin/python3 -m augur_mcp --client-id cowork\n"
                    " 456 /usr/bin/python3 -m unrelated\n"
                ),
                stderr="",
            )
        if args == ["ps", "-axE", "-o", "pid=,command="]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(args)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(mod, "_current_process_lineage", lambda: set())

    assert mod.active_ai_processes_for_path(worktree_path) == [
        mod.ActiveWorktreeProcess(
            pid=123,
            command="/tmp/augur-wt-active/.venv/bin/python3 -m augur_mcp --client-id cowork",
        )
    ]


def test_active_ai_processes_uses_windows_rows_when_ps_is_unavailable(monkeypatch):
    mod = _module()
    worktree_path = Path("/tmp/augur-wt-active")

    def fake_run(*_args, **_kwargs):
        raise FileNotFoundError("ps")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(mod, "_current_process_lineage", lambda: set())
    monkeypatch.setattr(
        mod,
        "_windows_process_rows",
        lambda: [
            {
                "ProcessId": 321,
                "CommandLine": "/tmp/augur-wt-active/.venv/bin/python -m augur_core --client-id claude",
                "ExecutablePath": "/tmp/augur-wt-active/.venv/bin/python",
            },
            {
                "ProcessId": 654,
                "CommandLine": "/usr/bin/python -m unrelated",
                "ExecutablePath": "/usr/bin/python",
            },
        ],
    )

    assert mod.active_ai_processes_for_path(worktree_path) == [
        mod.ActiveWorktreeProcess(
            pid=321,
            command="/tmp/augur-wt-active/.venv/bin/python -m augur_core --client-id claude",
        )
    ]


def test_active_ai_processes_detects_env_var_bound_session(monkeypatch):
    """A claude/codex session with `CLAUDE_PROJECT_DIR=<worktree>` in its env
    is bound to the worktree even when its process cwd has relocated and
    `lsof +D` finds nothing under the path. The hooks it has configured
    expand `${CLAUDE_PROJECT_DIR}` at fire time, so removing the worktree
    breaks them — the same orphan symptom lsof-ownership protects against.

    `ps -E` reports the env after the command line. The guard must spot the
    `CLAUDE_PROJECT_DIR=<exact_path>` token and return the binding process."""
    mod = _module()
    worktree_path = Path("/tmp/augur-wt-relocated")

    def fake_run(args, **_kwargs):
        if args[:2] == ["lsof", "-Fpc"]:
            # No FDs under the path — the session relocated since launch.
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        if args == ["ps", "-axo", "pid=,command="]:
            # The argv-embedding mechanism finds nothing either.
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args == ["ps", "-axE", "-o", "pid=,command="]:
            return SimpleNamespace(
                returncode=0,
                stdout=(
                    " 555 /Users/x/.local/bin/claude --dangerously-skip-permissions "
                    "USER=x CLAUDE_PROJECT_DIR=/tmp/augur-wt-relocated PWD=/Users/x\n"
                    " 666 /usr/bin/python3 -m unrelated PATH=/usr/bin\n"
                ),
                stderr="",
            )
        raise AssertionError(args)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(mod, "_current_process_lineage", lambda: set())

    assert mod.active_ai_processes_for_path(worktree_path) == [
        mod.ActiveWorktreeProcess(
            pid=555,
            command=(
                "/Users/x/.local/bin/claude --dangerously-skip-permissions "
                "USER=x CLAUDE_PROJECT_DIR=/tmp/augur-wt-relocated PWD=/Users/x"
            ),
        )
    ]


def test_active_ai_processes_reports_lsof_owner_even_in_own_lineage(monkeypatch):
    """An `lsof` hit is hard evidence of ownership (open FD / cwd under the
    path) and must be reported even for our own process tree — a `/dev-merge`
    cleaning up the worktree it is itself running from must see itself and
    defer. (The lineage filter applies only to the soft `ps`-argv signal.)"""
    mod = _module()
    worktree_path = Path("/tmp/augur-wt-self")

    def fake_run(args, **_kwargs):
        if args[:2] == ["lsof", "-Fpc"]:
            # PID 999 holds an open handle under the worktree — and it is in
            # our own lineage (it is the session running this very cleanup).
            return SimpleNamespace(
                returncode=0,
                stdout="p999\ncclaude --dangerously-skip-permissions\n",
                stderr="",
            )
        if args[:2] == ["ps", "-axo"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args == ["ps", "-axE", "-o", "pid=,command="]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(args)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(mod, "_current_process_lineage", lambda: {999})

    assert mod.active_ai_processes_for_path(worktree_path) == [
        mod.ActiveWorktreeProcess(pid=999, command="claude --dangerously-skip-permissions")
    ]
