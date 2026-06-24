"""Unit tests for src.scripts._launch_git — git helpers run against a real
throwaway repo in tmp_path (never the real repo)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.scripts import _launch_git


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=path, check=True)
    return path


def _commit(repo: Path, name: str, content: str) -> None:
    (repo / name).write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", f"add {name}"], cwd=repo, check=True)


def test_run_git_returns_completed_process(tmp_path):
    repo = _init_repo(tmp_path / "r")
    result = _launch_git.run_git(repo, "status", "--porcelain")
    assert isinstance(result, subprocess.CompletedProcess)
    assert result.returncode == 0


def test_run_git_raises_on_failure_when_checked(tmp_path):
    repo = _init_repo(tmp_path / "r")
    with pytest.raises(RuntimeError):
        _launch_git.run_git(repo, "not-a-real-subcommand")


def test_run_git_no_raise_when_check_false(tmp_path):
    repo = _init_repo(tmp_path / "r")
    result = _launch_git.run_git(repo, "not-a-real-subcommand", check=False)
    assert result.returncode != 0


def test_git_stdout_strips(tmp_path):
    repo = _init_repo(tmp_path / "r")
    _commit(repo, "a.txt", "hello")
    branch = _launch_git.git_stdout(repo, "rev-parse", "--abbrev-ref", "HEAD")
    assert branch != ""
    assert branch == branch.strip()


def test_repo_is_dirty_clean_then_dirty(tmp_path):
    repo = _init_repo(tmp_path / "r")
    _commit(repo, "a.txt", "hello")
    assert _launch_git.repo_is_dirty(repo) is False
    (repo / "untracked.txt").write_text("x", encoding="utf-8")
    assert _launch_git.repo_is_dirty(repo) is True


def test_rev_count(tmp_path):
    repo = _init_repo(tmp_path / "r")
    _commit(repo, "a.txt", "1")
    _commit(repo, "b.txt", "2")
    assert _launch_git.rev_count(repo, "HEAD") == 2


def test_stash_returns_false_on_clean_tree(tmp_path):
    repo = _init_repo(tmp_path / "r")
    _commit(repo, "a.txt", "1")
    assert _launch_git.stash(repo) is False


def test_stash_and_restore_roundtrip(tmp_path):
    repo = _init_repo(tmp_path / "r")
    _commit(repo, "a.txt", "1")
    (repo / "a.txt").write_text("modified", encoding="utf-8")
    assert _launch_git.repo_is_dirty(repo) is True

    assert _launch_git.stash(repo) is True
    # Working tree clean after stash.
    assert _launch_git.repo_is_dirty(repo) is False

    _launch_git.restore_stash(repo)
    # Modification restored.
    assert (repo / "a.txt").read_text(encoding="utf-8") == "modified"


def test_abort_merge_if_active_noop_when_no_merge(tmp_path):
    repo = _init_repo(tmp_path / "r")
    _commit(repo, "a.txt", "1")
    # No active merge -> should be a silent no-op (no exception).
    _launch_git.abort_merge_if_active(repo)
