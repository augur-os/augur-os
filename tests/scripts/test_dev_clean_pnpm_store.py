"""Tests for dev_clean pnpm store pruning."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEV_CLEAN_SCRIPTS = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "platform-admin" / "scripts"
if str(DEV_CLEAN_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DEV_CLEAN_SCRIPTS))

import dev_clean  # noqa: E402


def test_prune_pnpm_store_skips_when_pnpm_and_corepack_are_missing(monkeypatch):
    monkeypatch.setattr(dev_clean.shutil, "which", lambda _tool: None)

    result = dev_clean._prune_pnpm_store(dry_run=False)

    assert result.name == "pnpm-store-prune"
    assert result.skipped_reason is not None
    assert "pnpm not found" in result.skipped_reason


def test_prune_pnpm_store_parses_removed_files_and_packages(monkeypatch):
    monkeypatch.setattr(
        dev_clean.shutil,
        "which",
        lambda tool: "/opt/bin/pnpm" if tool == "pnpm" else None,
    )

    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["/opt/bin/pnpm", "store", "path"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        assert cmd[:3] == ["/opt/bin/pnpm", "store", "prune"]
        assert "--dry-run" not in cmd
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout="Removed 100 files\nRemoved 5 packages\n",
            stderr="",
        )

    monkeypatch.setattr(dev_clean.subprocess, "run", fake_run)

    result = dev_clean._prune_pnpm_store(dry_run=False)

    assert result.skipped_reason is None
    assert result.files_reclaimed == 100
    assert any("5 packages" in note or "Removed 5 packages" in note for note in result.notes)
    assert result.targets_touched == 1


def test_prune_pnpm_store_nonzero_exit_reports_stderr(monkeypatch):
    monkeypatch.setattr(
        dev_clean.shutil,
        "which",
        lambda tool: "/opt/bin/pnpm" if tool == "pnpm" else None,
    )

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="out of space\n")

    monkeypatch.setattr(dev_clean.subprocess, "run", fake_run)

    result = dev_clean._prune_pnpm_store(dry_run=False)

    assert result.skipped_reason is not None
    assert "out of space" in result.skipped_reason


def test_prune_pnpm_store_timeout_reports_timed_out(monkeypatch):
    monkeypatch.setattr(
        dev_clean.shutil,
        "which",
        lambda tool: "/opt/bin/pnpm" if tool == "pnpm" else None,
    )

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr(dev_clean.subprocess, "run", fake_run)

    result = dev_clean._prune_pnpm_store(dry_run=False)

    assert result.skipped_reason is not None
    assert "timed out" in result.skipped_reason


def test_prune_pnpm_store_dry_run_passes_dry_run_flag_and_reports_note(monkeypatch):
    monkeypatch.setattr(
        dev_clean.shutil,
        "which",
        lambda tool: "/opt/bin/pnpm" if tool == "pnpm" else None,
    )
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["/opt/bin/pnpm", "store", "path"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout="Removed 100 files\nRemoved 5 packages\n",
            stderr="",
        )

    monkeypatch.setattr(dev_clean.subprocess, "run", fake_run)

    result = dev_clean._prune_pnpm_store(dry_run=True)

    assert calls[-1] == ["/opt/bin/pnpm", "store", "prune", "--dry-run"]
    assert result.files_reclaimed == 100
    assert result.targets_touched == 0
    assert any("dry" in note.lower() for note in result.notes)


def test_prune_pnpm_store_dry_run_estimates_when_pnpm_lacks_dry_run(monkeypatch, tmp_path: Path):
    store = tmp_path / "store"
    store.mkdir()
    (store / "package.tgz").write_bytes(b"x" * 32)
    monkeypatch.setattr(
        dev_clean.shutil,
        "which",
        lambda tool: "/opt/bin/pnpm" if tool == "pnpm" else None,
    )

    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["/opt/bin/pnpm", "store", "path"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{store}\n", stderr="")
        return subprocess.CompletedProcess(
            cmd,
            1,
            stdout="",
            stderr="ERROR Unknown option: 'dry-run'\n",
        )

    monkeypatch.setattr(dev_clean.subprocess, "run", fake_run)

    result = dev_clean._prune_pnpm_store(dry_run=True)

    assert result.skipped_reason is None
    assert result.bytes_reclaimed == 32
    assert result.files_reclaimed == 1
    assert result.targets_touched == 0
    assert any("upper bound" in note for note in result.notes)


def test_prune_pnpm_store_uses_corepack_fallback_when_pnpm_is_missing(monkeypatch):
    monkeypatch.setattr(
        dev_clean.shutil,
        "which",
        lambda tool: "/opt/bin/corepack" if tool == "corepack" else None,
    )
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:4] == ["/opt/bin/corepack", "pnpm", "store", "path"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="Removed 0 files\n", stderr="")

    monkeypatch.setattr(dev_clean.subprocess, "run", fake_run)

    result = dev_clean._prune_pnpm_store(dry_run=False)

    assert result.skipped_reason is None
    assert calls[-1] == ["/opt/bin/corepack", "pnpm", "store", "prune"]


def test_build_operations_gates_pnpm_store_prune_with_tier_2_operations():
    with_tier_2 = {operation.name for operation in dev_clean.build_operations(include_git=True)}
    without_tier_2 = {operation.name for operation in dev_clean.build_operations(include_git=False)}

    assert "pnpm-store-prune" in with_tier_2
    assert "pnpm-store-prune" not in without_tier_2


def test_git_dir_bytes_uses_git_common_dir_for_linked_worktrees(monkeypatch, tmp_path: Path):
    common_git = tmp_path / "repo" / ".git"
    common_git.mkdir(parents=True)
    (common_git / "objects.pack").write_bytes(b"x" * 64)
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {common_git}\n", encoding="utf-8")

    monkeypatch.setattr(dev_clean, "REPO_ROOT", worktree)

    def fake_git(*args, **kwargs):
        assert args == ("rev-parse", "--git-common-dir")
        return subprocess.CompletedProcess(["git", *args], 0, stdout=f"{common_git}\n", stderr="")

    monkeypatch.setattr(dev_clean, "_git", fake_git)

    assert dev_clean._git_dir_bytes() == 64
