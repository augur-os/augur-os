from __future__ import annotations

import stat

import scripts.verify_worktree_toolchain as verifier


def test_remove_tree_removes_readonly_files(tmp_path):
    root = tmp_path / "tree"
    root.mkdir()
    readonly = root / "readonly.txt"
    readonly.write_text("locked", encoding="utf-8")
    readonly.chmod(stat.S_IREAD)

    verifier._remove_tree(root)

    assert not root.exists()


def test_windows_volume_delta_budget_allows_hardlink_install_overhead(monkeypatch):
    monkeypatch.setattr("scripts.verify_worktree_toolchain._is_windows", lambda: True)

    assert verifier._volume_delta_limit_mb() >= 600


def test_posix_volume_delta_budget_stays_strict(monkeypatch):
    monkeypatch.setattr("scripts.verify_worktree_toolchain._is_windows", lambda: False)

    assert verifier._volume_delta_limit_mb() == 200
