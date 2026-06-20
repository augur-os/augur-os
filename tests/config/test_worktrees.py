from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import src.config.worktrees as worktrees
from src.config.worktrees import is_linked_worktree


def _linked_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """Build a linked-worktree layout resolvable via the .git-file fallback."""
    main_root = tmp_path / "Augur"
    worktree_root = tmp_path / ".worktrees" / "feature"
    gitdir = main_root / ".git" / "worktrees" / "feature"
    gitdir.mkdir(parents=True)
    main_root.mkdir(parents=True, exist_ok=True)
    worktree_root.mkdir(parents=True)
    (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree_root / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    return main_root, worktree_root


def test_linked_worktree_returns_true(tmp_path: Path) -> None:
    _main_root, worktree_root = _linked_worktree(tmp_path)

    result = is_linked_worktree(worktree_root)

    assert result is True


def test_plain_directory_returns_false(tmp_path: Path) -> None:
    plain = tmp_path / "not-a-worktree"
    plain.mkdir()

    result = is_linked_worktree(plain)

    assert result is False


def test_git_file_without_worktrees_segment_returns_false(tmp_path: Path) -> None:
    """A .git file that points outside a worktrees/ gitdir is not a linked worktree."""
    root = tmp_path / "repo"
    gitdir = tmp_path / "somewhere" / "else" / ".git"
    gitdir.mkdir(parents=True)
    root.mkdir()
    (root / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")

    assert is_linked_worktree(root) is False


def test_result_is_strict_bool(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()

    assert isinstance(is_linked_worktree(plain), bool)


def test_returns_true_when_dependency_resolves_main_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """is_linked_worktree is True exactly when a non-None main checkout is found."""
    seen: list[Path] = []

    def fake_main_checkout(project_root: Path) -> Path:
        seen.append(project_root)
        return tmp_path / "main"

    monkeypatch.setattr(worktrees, "main_checkout_for_worktree", fake_main_checkout)

    target = tmp_path / "wt"
    assert is_linked_worktree(target) is True
    assert seen == [target]


def test_returns_false_when_dependency_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worktrees, "main_checkout_for_worktree", lambda _root: None)

    assert is_linked_worktree(tmp_path) is False


def test_real_git_main_checkout_is_not_linked_but_worktree_is(tmp_path: Path) -> None:
    """End-to-end with real git: the main checkout is not linked, its worktree is."""
    main_root = tmp_path / "Augur"
    worktree_root = tmp_path / ".worktrees" / "feature"
    main_root.mkdir()
    subprocess.run(["git", "init"], cwd=main_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=main_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=main_root, check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=main_root, check=True)
    (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    subprocess.run(["git", "add", "project.yaml"], cwd=main_root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=main_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "worktree", "add", "-b", "feature", str(worktree_root)],
        cwd=main_root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert is_linked_worktree(main_root) is False
    assert is_linked_worktree(worktree_root) is True
