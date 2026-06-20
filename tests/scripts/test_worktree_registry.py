"""Tests for worktree registry branch resolution.

Regression coverage for the bug where registering a worktree from inside a
*different* worktree recorded the caller's branch instead of the registered
worktree's branch — because branch detection ran git in the caller's cwd.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from src.config.paths import get_project_root

PROJECT_ROOT = get_project_root()
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import worktree_registry  # noqa: E402


def _init_repo(path: Path, branch: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, env=env)
    subprocess.run(["git", "checkout", "-q", "-b", branch], cwd=path, check=True, env=env)
    (path / "f").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True, env=env)


def test_get_worktree_branch_reads_target_not_caller(tmp_path: Path, monkeypatch) -> None:
    """Branch must come from the target worktree, even when cwd is elsewhere."""
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    _init_repo(repo_a, "caller-branch")
    _init_repo(repo_b, "feature/target-branch")

    # Simulate registering repo_b's worktree while sitting inside repo_a.
    monkeypatch.chdir(repo_a)
    assert worktree_registry.get_worktree_branch(str(repo_b)) == "feature/target-branch"
    # And the caller's own branch is still resolvable when asked for explicitly.
    assert worktree_registry.get_worktree_branch(str(repo_a)) == "caller-branch"


def test_get_worktree_branch_unknown_for_non_git_path(tmp_path: Path) -> None:
    assert worktree_registry.get_worktree_branch(str(tmp_path / "nope")) == "unknown"


def test_register_records_target_worktree_branch(tmp_path: Path, monkeypatch) -> None:
    """cmd_register must persist the registered worktree's branch, not the caller's."""
    caller = tmp_path / "caller"
    _init_repo(caller, "caller-branch")
    # Register a real *linked* worktree on its own branch — the realistic input
    # for register(). (A standalone repo is now refused as a main working tree.)
    worktree = tmp_path / "wt"
    subprocess.run(
        ["git", "-C", str(caller), "worktree", "add", "-b", "feature/registered", str(worktree)],
        check=True,
        capture_output=True,
    )

    registry_file = tmp_path / "worktree_registry.yaml"
    monkeypatch.setattr(worktree_registry, "REGISTRY_FILE", registry_file)
    monkeypatch.setattr(worktree_registry, "RUNTIME_DIR", tmp_path)
    monkeypatch.chdir(caller)

    result = worktree_registry.cmd_register(str(worktree), "wt")

    assert result["success"] is True
    assert result["branch"] == "feature/registered"
    persisted = worktree_registry.load_worktree_registry()
    assert persisted[str(worktree.resolve())]["branch"] == "feature/registered"


def test_register_refuses_main_working_tree(tmp_path: Path, monkeypatch) -> None:
    """The main checkout must never be registered as a worktree — it owns the
    default dashboard port. Guards the `--from-hook` cwd fallback that registered
    the main repo and broke `aug dev build` port resolution.
    """
    repo = tmp_path / "repo"
    _init_repo(repo, "main")

    registry_file = tmp_path / "worktree_registry.yaml"
    monkeypatch.setattr(worktree_registry, "REGISTRY_FILE", registry_file)
    monkeypatch.setattr(worktree_registry, "RUNTIME_DIR", tmp_path)

    result = worktree_registry.cmd_register(str(repo), "repo")

    assert result["success"] is False
    assert "main checkout" in result["error"]
    assert worktree_registry.load_worktree_registry() == {}


def test_is_main_working_tree_distinguishes_main_from_linked_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo, "main")
    worktree = tmp_path / "wt"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-b", "feat", str(worktree)],
        check=True,
        capture_output=True,
    )

    assert worktree_registry.is_main_working_tree(str(repo)) is True
    assert worktree_registry.is_main_working_tree(str(worktree)) is False
    # Non-git paths are not main working trees (registration governed elsewhere).
    assert worktree_registry.is_main_working_tree(str(tmp_path / "nope")) is False
