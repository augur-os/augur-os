"""Tests for worktree_toolchain module."""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import patch

from src.config.paths import get_project_root

PROJECT_ROOT = get_project_root()
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import worktree_toolchain  # noqa: E402


def test_verify_pnpm_alignment_returns_none_when_devices_match(tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    store_dir = tmp_path / "store"
    store_dir.mkdir()

    with (
        patch.object(worktree_toolchain, "_resolve_pnpm_store_dir", return_value=store_dir),
        patch.object(worktree_toolchain, "_device_id", return_value=42),
    ):
        result = worktree_toolchain.verify_pnpm_alignment(project_root)

    assert result is None


def test_verify_pnpm_alignment_returns_incident_when_devices_differ(tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    store_dir = tmp_path / "store"
    store_dir.mkdir()

    devices = {project_root: 1, store_dir: 2}

    with (
        patch.object(worktree_toolchain, "_resolve_pnpm_store_dir", return_value=store_dir),
        patch.object(worktree_toolchain, "_device_id", side_effect=lambda p: devices[p]),
    ):
        result = worktree_toolchain.verify_pnpm_alignment(project_root)

    assert result is not None
    assert result.severity == "high"
    assert "different filesystem volume" in result.message.lower()
    assert str(project_root) in result.message
    assert str(store_dir) in result.message
    assert result.safe_to_repair is False  # user must choose remediation
    assert result.fingerprint == "worktree/toolchain/pnpm-store-misaligned"


def test_verify_pnpm_alignment_returns_incident_when_store_missing(tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir()

    with patch.object(worktree_toolchain, "_resolve_pnpm_store_dir", return_value=None):
        result = worktree_toolchain.verify_pnpm_alignment(project_root)

    assert result is not None
    assert result.severity == "high"
    assert "store-dir" in result.message.lower()
    assert result.fingerprint == "worktree/toolchain/pnpm-store-unresolved"


def test_probe_clone_primitive_returns_callable_on_apfs(monkeypatch):
    monkeypatch.setattr(worktree_toolchain.sys, "platform", "darwin")
    monkeypatch.setattr(worktree_toolchain, "_detect_fs_type", lambda p: "apfs")
    result = worktree_toolchain.probe_clone_primitive(Path("/tmp"))
    assert result is not None
    assert callable(result)


def test_probe_clone_primitive_returns_callable_on_btrfs(monkeypatch):
    monkeypatch.setattr(worktree_toolchain.sys, "platform", "linux")
    monkeypatch.setattr(worktree_toolchain, "_detect_fs_type", lambda p: "btrfs")
    result = worktree_toolchain.probe_clone_primitive(Path("/tmp"))
    assert result is not None
    assert callable(result)


def test_probe_clone_primitive_returns_none_on_ntfs(monkeypatch):
    monkeypatch.setattr(worktree_toolchain.sys, "platform", "win32")
    monkeypatch.setattr(worktree_toolchain, "_detect_fs_type", lambda p: "ntfs")
    result = worktree_toolchain.probe_clone_primitive(Path("C:\\tmp"))
    assert result is None


def test_probe_clone_primitive_returns_none_on_ext4(monkeypatch):
    monkeypatch.setattr(worktree_toolchain.sys, "platform", "linux")
    monkeypatch.setattr(worktree_toolchain, "_detect_fs_type", lambda p: "ext4")
    result = worktree_toolchain.probe_clone_primitive(Path("/tmp"))
    assert result is None


def test_probe_clone_primitive_callable_invokes_cp_dash_c_on_apfs(monkeypatch, tmp_path):
    monkeypatch.setattr(worktree_toolchain.sys, "platform", "darwin")
    monkeypatch.setattr(worktree_toolchain, "_detect_fs_type", lambda p: "apfs")

    recorded = {}

    def fake_run(cmd, **kwargs):
        recorded["cmd"] = cmd
        recorded["kwargs"] = kwargs
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(worktree_toolchain.subprocess, "run", fake_run)

    fn = worktree_toolchain.probe_clone_primitive(tmp_path)
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    fn(src, dst)

    assert recorded["cmd"][:3] == ["cp", "-c", "-R"]
    assert recorded["cmd"][-2:] == [str(src), str(dst)]


def _make_worktree(tmp_path: Path, name: str, lockfile_content: str = "lock-v1\n") -> Path:
    wt = tmp_path / name
    dashboard = wt / "apps" / "dashboard"
    dashboard.mkdir(parents=True)
    (dashboard / "pnpm-lock.yaml").write_text(lockfile_content)
    return wt


def _populate_node_modules(wt: Path, with_next_bin: bool = True) -> None:
    node_modules = wt / "apps" / "dashboard" / "node_modules"
    node_modules.mkdir(parents=True, exist_ok=True)
    (node_modules / "marker.txt").write_text("populated")
    if with_next_bin:
        bin_dir = node_modules / ".bin"
        bin_dir.mkdir(exist_ok=True)
        (bin_dir / "next").write_text("#!/bin/sh\nexit 0\n")
        (bin_dir / "next").chmod(0o755)


def test_pnpm_install_frozen_forces_hardlink_import_method(monkeypatch, tmp_path):
    dashboard = tmp_path / "apps" / "dashboard"
    dashboard.mkdir(parents=True)

    monkeypatch.setattr(
        worktree_toolchain.shutil,
        "which",
        lambda name: "/usr/bin/pnpm" if name == "pnpm" else None,
    )

    recorded = {}

    def fake_run(cmd, **kwargs):
        recorded["cmd"] = cmd
        recorded["cwd"] = kwargs.get("cwd")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(worktree_toolchain.subprocess, "run", fake_run)

    assert worktree_toolchain._pnpm_install_frozen(dashboard) is None

    assert recorded["cmd"] == [
        "/usr/bin/pnpm",
        "install",
        "--frozen-lockfile",
        "--package-import-method",
        "hardlink",
    ]
    assert recorded["cwd"] == dashboard


def test_materialize_skips_when_next_bin_already_exists(tmp_path):
    target = _make_worktree(tmp_path, "target")
    _populate_node_modules(target, with_next_bin=True)

    result = worktree_toolchain.materialize_node_modules(target, source_worktree=None)

    assert result.method == "skip"
    assert result.incidents == []


def test_materialize_clones_when_lockfile_matches_and_primitive_available(tmp_path, monkeypatch):
    source = _make_worktree(tmp_path, "source")
    _populate_node_modules(source, with_next_bin=True)
    target = _make_worktree(tmp_path, "target")  # same lockfile content

    clone_calls = []

    def fake_clone(src, dst):
        clone_calls.append((src, dst))
        # Simulate the clone effect:
        shutil.copytree(src, dst)

    monkeypatch.setattr(worktree_toolchain, "probe_clone_primitive", lambda p: fake_clone)

    result = worktree_toolchain.materialize_node_modules(target, source_worktree=source)

    assert result.method == "clone"
    assert len(clone_calls) == 1
    assert (target / "apps" / "dashboard" / "node_modules" / ".bin" / "next").exists()
    assert result.incidents == []


def test_materialize_falls_through_to_install_when_lockfile_differs(tmp_path, monkeypatch):
    source = _make_worktree(tmp_path, "source", lockfile_content="lock-v1\n")
    _populate_node_modules(source, with_next_bin=True)
    target = _make_worktree(tmp_path, "target", lockfile_content="lock-v2\n")

    clone_called = False

    def fake_clone(src, dst):
        nonlocal clone_called
        clone_called = True

    monkeypatch.setattr(worktree_toolchain, "probe_clone_primitive", lambda p: fake_clone)

    install_called = {"count": 0}

    def fake_install(dashboard_dir):
        install_called["count"] += 1
        _populate_node_modules(dashboard_dir.parent.parent, with_next_bin=True)
        return None  # no incident

    monkeypatch.setattr(worktree_toolchain, "_pnpm_install_frozen", fake_install)

    result = worktree_toolchain.materialize_node_modules(target, source_worktree=source)

    assert clone_called is False
    assert install_called["count"] == 1
    assert result.method == "install"


def test_materialize_falls_through_when_clone_primitive_unavailable(tmp_path, monkeypatch):
    source = _make_worktree(tmp_path, "source")
    _populate_node_modules(source, with_next_bin=True)
    target = _make_worktree(tmp_path, "target")

    monkeypatch.setattr(worktree_toolchain, "probe_clone_primitive", lambda p: None)

    install_called = {"count": 0}

    def fake_install(dashboard_dir):
        install_called["count"] += 1
        _populate_node_modules(dashboard_dir.parent.parent, with_next_bin=True)
        return None

    monkeypatch.setattr(worktree_toolchain, "_pnpm_install_frozen", fake_install)

    result = worktree_toolchain.materialize_node_modules(target, source_worktree=source)

    assert install_called["count"] == 1
    assert result.method == "install"


def test_materialize_falls_through_when_source_missing_next_bin(tmp_path, monkeypatch):
    source = _make_worktree(tmp_path, "source")  # no node_modules populated
    target = _make_worktree(tmp_path, "target")

    clone_called = False

    def fake_clone(src, dst):
        nonlocal clone_called
        clone_called = True

    monkeypatch.setattr(worktree_toolchain, "probe_clone_primitive", lambda p: fake_clone)

    def fake_install(dashboard_dir):
        _populate_node_modules(dashboard_dir.parent.parent, with_next_bin=True)
        return None

    monkeypatch.setattr(worktree_toolchain, "_pnpm_install_frozen", fake_install)

    result = worktree_toolchain.materialize_node_modules(target, source_worktree=source)

    assert clone_called is False
    assert result.method == "install"


def test_materialize_clone_failure_falls_through_to_install(tmp_path, monkeypatch):
    source = _make_worktree(tmp_path, "source")
    _populate_node_modules(source, with_next_bin=True)
    target = _make_worktree(tmp_path, "target")

    def failing_clone(src, dst):
        raise RuntimeError("simulated clone failure")

    monkeypatch.setattr(worktree_toolchain, "probe_clone_primitive", lambda p: failing_clone)

    install_called = {"count": 0}

    def fake_install(dashboard_dir):
        install_called["count"] += 1
        _populate_node_modules(dashboard_dir.parent.parent, with_next_bin=True)
        return None

    monkeypatch.setattr(worktree_toolchain, "_pnpm_install_frozen", fake_install)

    result = worktree_toolchain.materialize_node_modules(target, source_worktree=source)

    assert install_called["count"] == 1
    assert result.method == "install"
    nm = target / "apps" / "dashboard" / "node_modules"
    if nm.exists():
        # Confirm install completed cleanly after clone failure was cleaned up.
        assert (nm / ".bin" / "next").exists()


def test_materialize_install_failure_returns_failed_with_incident(tmp_path, monkeypatch):
    target = _make_worktree(tmp_path, "target")

    monkeypatch.setattr(worktree_toolchain, "probe_clone_primitive", lambda p: None)

    def failing_install(dashboard_dir):
        return worktree_toolchain.Incident(
            fingerprint="worktree/toolchain/install-failed",
            severity="high",
            message="pnpm install failed: simulated",
            owner_path=str(dashboard_dir),
            safe_to_repair=False,
            repaired=False,
        )

    monkeypatch.setattr(worktree_toolchain, "_pnpm_install_frozen", failing_install)

    result = worktree_toolchain.materialize_node_modules(target, source_worktree=None)

    assert result.method == "failed"
    assert len(result.incidents) == 1
    assert "install failed" in result.incidents[0].message.lower()


def test_materialize_serializes_concurrent_calls(tmp_path, monkeypatch):
    target = _make_worktree(tmp_path, "target")

    monkeypatch.setattr(worktree_toolchain, "probe_clone_primitive", lambda p: None)

    install_call_count = {"n": 0}
    install_started = threading.Event()
    install_can_finish = threading.Event()

    def slow_install(dashboard_dir):
        install_call_count["n"] += 1
        install_started.set()
        install_can_finish.wait(timeout=5)
        _populate_node_modules(dashboard_dir.parent.parent, with_next_bin=True)
        return None

    monkeypatch.setattr(worktree_toolchain, "_pnpm_install_frozen", slow_install)

    results: list[worktree_toolchain.MaterializeResult] = []

    def run():
        results.append(worktree_toolchain.materialize_node_modules(target, source_worktree=None))

    t1 = threading.Thread(target=run)
    t2 = threading.Thread(target=run)
    t1.start()
    install_started.wait(timeout=5)
    t2.start()
    install_can_finish.set()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert install_call_count["n"] == 1
    methods = sorted(r.method for r in results)
    assert methods == ["install", "skip"]
