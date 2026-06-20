"""Tests for the vault reorg migration helpers (scripts/migrations/vault_reorg_2026_06_12.py).

Hermetic: every test runs against a scratch git repo under tmp_path.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.migrations.vault_reorg_2026_06_12 import git_mv, reset_sim


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _commit_all(repo: Path) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "test")
    reset_sim()
    return tmp_path


def test_tracked_file_move(repo: Path):
    (repo / "a").mkdir()
    (repo / "a" / "x.md").write_text("x", encoding="utf-8")
    _commit_all(repo)

    git_mv(repo, "a/x.md", "b/x.md", dry=False)

    assert (repo / "b" / "x.md").is_file()
    assert not (repo / "a" / "x.md").exists()


def test_tracked_dir_move(repo: Path):
    (repo / "a" / "sub").mkdir(parents=True)
    (repo / "a" / "x.md").write_text("x", encoding="utf-8")
    (repo / "a" / "sub" / "y.md").write_text("y", encoding="utf-8")
    _commit_all(repo)

    git_mv(repo, "a", "z/a", dry=False)

    assert (repo / "z" / "a" / "x.md").is_file()
    assert (repo / "z" / "a" / "sub" / "y.md").is_file()
    assert not (repo / "a").exists()


def test_dir_merge_with_collision_aborts(repo: Path):
    (repo / "a").mkdir()
    (repo / "a" / "x.md").write_text("from a", encoding="utf-8")
    (repo / "b").mkdir()
    (repo / "b" / "x.md").write_text("from b", encoding="utf-8")
    _commit_all(repo)

    with pytest.raises(subprocess.CalledProcessError):
        git_mv(repo, "a", "b", dry=False)

    # nothing overwritten
    assert (repo / "b" / "x.md").read_text(encoding="utf-8") == "from b"
    assert (repo / "a" / "x.md").read_text(encoding="utf-8") == "from a"


def test_dir_merge_without_collision(repo: Path):
    (repo / "a").mkdir()
    (repo / "a" / "new.md").write_text("n", encoding="utf-8")
    (repo / "b").mkdir()
    (repo / "b" / "old.md").write_text("o", encoding="utf-8")
    _commit_all(repo)

    git_mv(repo, "a", "b", dry=False)

    assert (repo / "b" / "new.md").is_file()
    assert (repo / "b" / "old.md").is_file()


def test_dry_merge_collision_surfaces_in_preview(repo: Path, capsys):
    (repo / "a").mkdir()
    (repo / "a" / "x.md").write_text("from a", encoding="utf-8")
    (repo / "b").mkdir()
    (repo / "b" / "x.md").write_text("from b", encoding="utf-8")
    _commit_all(repo)

    git_mv(repo, "a", "b", dry=True)

    out = capsys.readouterr().out
    assert "COLLISION (execute would abort): b/x.md" in out
    # dry run touched nothing
    assert (repo / "a" / "x.md").read_text(encoding="utf-8") == "from a"


def test_empty_husk_removed_on_execute(repo: Path, capsys):
    # dir with zero tracked files and no real files (only an empty subdir)
    (repo / "husk" / "sub").mkdir(parents=True)
    (repo / "seed.md").write_text("s", encoding="utf-8")
    _commit_all(repo)

    git_mv(repo, "husk", "_augur/husk", dry=False)

    out = capsys.readouterr().out
    assert "EMPTY-HUSK remove husk (no tracked or untracked files)" in out
    assert not (repo / "husk").exists()
    assert not (repo / "_augur" / "husk").exists()  # nothing recreated


def test_empty_husk_printed_not_removed_on_dry(repo: Path, capsys):
    (repo / "husk" / "sub").mkdir(parents=True)
    (repo / "seed.md").write_text("s", encoding="utf-8")
    _commit_all(repo)

    git_mv(repo, "husk", "_augur/husk", dry=True)

    out = capsys.readouterr().out
    assert "DRY  EMPTY-HUSK remove husk (no tracked or untracked files)" in out
    assert (repo / "husk" / "sub").is_dir()  # untouched


def test_untracked_only_dir_moved_with_warn(repo: Path, capsys):
    (repo / "seed.md").write_text("s", encoding="utf-8")
    _commit_all(repo)
    (repo / "loose").mkdir()
    (repo / "loose" / "y.md").write_text("y", encoding="utf-8")  # untracked

    git_mv(repo, "loose", "_augur/loose", dry=False)

    out = capsys.readouterr().out
    assert "WARN  untracked content moved outside git: loose -> _augur/loose (1 files)" in out
    assert (repo / "_augur" / "loose" / "y.md").is_file()
    assert not (repo / "loose").exists()


def test_untracked_only_dir_dry_prints_decision(repo: Path, capsys):
    (repo / "seed.md").write_text("s", encoding="utf-8")
    _commit_all(repo)
    (repo / "loose").mkdir()
    (repo / "loose" / "y.md").write_text("y", encoding="utf-8")

    git_mv(repo, "loose", "_augur/loose", dry=True)

    out = capsys.readouterr().out
    assert "WARN  untracked content moved outside git" in out
    assert "shutil.move" in out
    assert (repo / "loose" / "y.md").is_file()  # untouched
