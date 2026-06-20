"""Unit tests for the WorktreeCreate provisioning (`scripts/worktree_create.py`).

The harness `WorktreeCreate` hook must create the worktree and echo ONLY its path.
`create_and_provision` builds a sibling `augur-<name>` worktree and registers it
(port + `.augur-worktree.yaml`). Git/registry I/O is mocked here; the end-to-end
hook→harness path is exercised live via EnterWorktree.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import worktree_create as wc  # noqa: E402


def test_create_and_provision_builds_sibling_and_registers(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    calls: dict[str, object] = {}

    monkeypatch.setattr(wc, "resolve_base_ref", lambda r: "origin/main")
    monkeypatch.setattr(wc, "run_git", lambda r, *a: calls.__setitem__("git", tuple(a)))
    monkeypatch.setattr(wc, "register_worktree", lambda r, w, n: calls.__setitem__("register", (str(w), n)))

    wt = wc.create_and_provision(repo, "wt-demo")

    # Sibling augur-<name> directory, NOT a nested path.
    assert wt == repo.parent / "augur-wt-demo"
    # Created the git worktree on a branch named after the worktree.
    assert calls["git"][:2] == ("worktree", "add")
    assert "-b" in calls["git"] and "wt-demo" in calls["git"]
    # Registered it (allocates ports + writes .augur-worktree.yaml).
    assert calls["register"] == (str(repo.parent / "augur-wt-demo"), "wt-demo")


def test_create_and_provision_idempotent_when_worktree_exists(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    existing = repo.parent / "augur-wt-demo"
    existing.mkdir(parents=True)
    git_called = {"n": 0}

    monkeypatch.setattr(wc, "resolve_base_ref", lambda r: "origin/main")
    monkeypatch.setattr(wc, "run_git", lambda r, *a: git_called.__setitem__("n", git_called["n"] + 1))
    monkeypatch.setattr(wc, "register_worktree", lambda r, w, n: None)

    wt = wc.create_and_provision(repo, "wt-demo")

    assert wt == existing
    # Existing worktree dir → do NOT re-run `git worktree add`.
    assert git_called["n"] == 0
