from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

from src.config.runtime_identity import (
    GlobalIdentityError,
    GlobalIdentityLock,
    GlobalMutationGuard,
    build_worktree_overlay_env,
    global_mcp_project_root,
    resolve_runtime_identity,
)


def _linked_worktree(tmp_path: Path) -> tuple[Path, Path]:
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


def test_linked_worktree_identity_uses_main_authority(tmp_path: Path) -> None:
    main_root, worktree_root = _linked_worktree(tmp_path)

    identity = resolve_runtime_identity(worktree_root)

    assert identity.current_root == worktree_root.resolve()
    assert identity.authority_root == main_root.resolve()
    assert identity.main_root == main_root.resolve()
    assert identity.is_linked_worktree is True
    assert identity.can_mutate_global is False


def test_main_checkout_can_mutate_global_identity(tmp_path: Path) -> None:
    main_root = tmp_path / "Augur"
    main_root.mkdir()
    (main_root / ".git").mkdir()
    (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")

    identity = resolve_runtime_identity(main_root)

    assert identity.authority_root == main_root.resolve()
    assert identity.is_linked_worktree is False
    assert identity.can_mutate_global is True


def test_main_checkout_with_actual_linked_worktree_keeps_main_authority(tmp_path: Path) -> None:
    main_root = tmp_path / "Augur"
    worktree_root = tmp_path / ".worktrees" / "feature"
    main_root.mkdir()
    subprocess.run(["git", "init"], cwd=main_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=main_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=main_root, check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=main_root, check=True)
    (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    subprocess.run(["git", "add", "project.yaml"], cwd=main_root, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=main_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "worktree", "add", "-b", "feature", str(worktree_root)],
        cwd=main_root,
        check=True,
        capture_output=True,
        text=True,
    )

    identity = resolve_runtime_identity(main_root)

    assert identity.authority_root == main_root.resolve()
    assert identity.main_root is None
    assert identity.is_linked_worktree is False
    assert identity.can_mutate_global is True


def test_fresh_real_worktree_without_marker_roots_global_at_main(tmp_path: Path) -> None:
    """A freshly-created real `git worktree add` worktree — before any
    `.augur-worktree.yaml` marker exists — must still resolve its global
    authority to the main checkout via `git worktree list`.

    Regression for the global-MCP-config leak: a session hook firing right after
    `git worktree add` (no Augur marker written yet) must NOT stamp the worktree
    path into user-global client configs. Detection is git-based, not marker-
    based, so the marker-creation timing cannot open a leak window. Unlike the
    simulated `_linked_worktree` fixture (which exercises the `.git`-file
    fallback), this drives the primary `git worktree list --porcelain` path.
    """
    main_root = tmp_path / "Augur"
    worktree_root = tmp_path / ".worktrees" / "feature"
    main_root.mkdir()
    subprocess.run(["git", "init"], cwd=main_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=main_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=main_root, check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=main_root, check=True)
    (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    subprocess.run(["git", "add", "project.yaml"], cwd=main_root, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=main_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "worktree", "add", "-b", "feature", str(worktree_root)],
        cwd=main_root,
        check=True,
        capture_output=True,
        text=True,
    )
    # Exact creation-race scenario: the worktree carries project.yaml but has no
    # Augur worktree marker yet.
    assert not (worktree_root / ".augur-worktree.yaml").exists()

    identity = resolve_runtime_identity(worktree_root)
    assert identity.is_linked_worktree is True
    assert identity.authority_root == main_root.resolve()
    assert identity.main_root == main_root.resolve()
    assert identity.can_mutate_global is False
    # The property that prevents the global-config leak:
    assert global_mcp_project_root(worktree_root) == main_root.resolve()


def test_mutation_guard_blocks_worktree_targeting_itself(tmp_path: Path) -> None:
    _main_root, worktree_root = _linked_worktree(tmp_path)
    identity = resolve_runtime_identity(worktree_root)

    with pytest.raises(GlobalIdentityError, match="worktree cannot mutate shared global identity"):
        with GlobalMutationGuard(identity, target_root=worktree_root, operation="editable-install"):
            raise AssertionError("guard did not block")


def test_mutation_guard_allows_delegated_sync_to_authority(tmp_path: Path) -> None:
    main_root, worktree_root = _linked_worktree(tmp_path)
    identity = resolve_runtime_identity(worktree_root)

    with GlobalMutationGuard(
        identity,
        target_root=main_root,
        operation="client-sync",
        allow_delegated=True,
    ):
        marker = "entered"

    assert marker == "entered"


def test_worktree_overlay_env_is_process_local_and_points_at_current_worktree(
    tmp_path: Path,
) -> None:
    main_root, worktree_root = _linked_worktree(tmp_path)
    identity = resolve_runtime_identity(worktree_root)

    env = build_worktree_overlay_env(identity, {"PYTHONPATH": "/outside"})

    pythonpath = env["PYTHONPATH"].split(os.pathsep)
    assert env["AUGUR_PROJECT_ROOT"] == str(worktree_root.resolve())
    assert env["AUGUR_ROOT"] == str(worktree_root.resolve())
    assert env["AUGUR_CORE"] == str(worktree_root.resolve())
    assert env["AUGUR_REPO"] == str(worktree_root.resolve())
    assert pythonpath[:3] == [
        str(worktree_root.resolve() / "project-brain" / "capabilities"),
        str(worktree_root.resolve()),
        str(worktree_root.resolve() / "src" / "mcp"),
    ]
    assert "/outside" in pythonpath
    assert str(main_root.resolve()) not in pythonpath


def test_global_identity_lock_serializes_two_threads(tmp_path: Path) -> None:
    lock_path = tmp_path / "identity.lock"
    order: list[str] = []

    def first() -> None:
        with GlobalIdentityLock(lock_path):
            order.append("first-enter")
            time.sleep(0.05)
            order.append("first-exit")

    def second() -> None:
        time.sleep(0.01)
        with GlobalIdentityLock(lock_path):
            order.append("second-enter")

    t1 = threading.Thread(target=first)
    t2 = threading.Thread(target=second)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert order == ["first-enter", "first-exit", "second-enter"]
