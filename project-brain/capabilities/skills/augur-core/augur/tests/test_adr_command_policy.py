"""Regression tests for the /adr command workflow policy."""

from pathlib import Path


def test_adr_implement_reuses_current_worktree_by_default():
    command_path = Path(__file__).resolve().parents[2] / "commands" / "adr.md"
    text = command_path.read_text(encoding="utf-8")

    assert "If the current checkout is already a linked Augur worktree" in text
    assert "reuse the current worktree" in text
    assert "Only create a new implementation worktree when invoked from the main checkout" in text
    assert "create an isolated worktree on a fresh branch from `main`" not in text
