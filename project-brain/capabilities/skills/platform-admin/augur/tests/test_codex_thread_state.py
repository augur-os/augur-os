"""Tests for repairing Codex thread state after worktree cleanup."""
from __future__ import annotations

import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
MODULE_PATH = SCRIPTS_DIR / "codex_thread_state.py"


def _module():
    module_name = "platform_admin_codex_thread_state_test"
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
    (repo / "README.md").write_text("root\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")
    return repo


def _create_codex_db(codex_home: Path, stale_cwd: Path, other_cwd: Path) -> Path:
    codex_home.mkdir()
    db_path = codex_home / "state_5.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "create table threads (id text, cwd text, git_branch text, git_sha text)"
        )
        conn.execute(
            "insert into threads values (?, ?, ?, ?)",
            ("stale", str(stale_cwd), "wt-old", "old-sha"),
        )
        conn.execute(
            "insert into threads values (?, ?, ?, ?)",
            ("other", str(other_cwd), "feature", "other-sha"),
        )
    return db_path


def test_repoint_threads_for_removed_worktree_updates_only_matching_cwd(tmp_path: Path):
    mod = _module()
    repo = _init_repo(tmp_path)
    stale_worktree = tmp_path / "augur-wt-old"
    other_worktree = tmp_path / "augur-wt-other"
    codex_home = tmp_path / ".codex"
    _create_codex_db(codex_home, stale_worktree, other_worktree)

    result = mod.repoint_threads_for_removed_worktree(
        worktree_path=stale_worktree,
        repo_root=repo,
        target_branch="main",
        codex_home=codex_home,
    )

    with sqlite3.connect(codex_home / "state_5.sqlite") as conn:
        rows = conn.execute(
            "select id, cwd, git_branch, git_sha from threads order by id"
        ).fetchall()

    assert result.updated_threads == 1
    assert rows == [
        ("other", str(other_worktree), "feature", "other-sha"),
        ("stale", str(repo.resolve()), "main", _git(repo, "rev-parse", "HEAD")),
    ]


def test_repoint_threads_for_removed_worktree_skips_when_codex_db_is_missing(tmp_path: Path):
    mod = _module()
    repo = _init_repo(tmp_path)

    result = mod.repoint_threads_for_removed_worktree(
        worktree_path=tmp_path / "missing-worktree",
        repo_root=repo,
        codex_home=tmp_path / ".codex",
    )

    assert result.status == "missing_codex_state"
    assert result.updated_threads == 0
