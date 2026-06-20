"""Tests for the deferred worktree purge queue (hooks-driven auto-purge)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
MODULE_PATH = SCRIPTS_DIR / "worktree_purge_queue.py"


def _module():
    module_name = "platform_admin_worktree_purge_queue_test"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mod(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_WORKTREE_PURGE_DIR", str(tmp_path / "queue"))
    return _module()


def _record(m, **kw):
    base = dict(name="wt-x", path="/tmp/wt-x", branch="wt-x", target="main")
    base.update(kw)
    return m.PurgeRecord(**base)


def _patch_state(m, monkeypatch, *, exists=True, branch=True, merged=True, dirty=False, owners=None):
    monkeypatch.setattr(m, "worktree_exists", lambda p: exists)
    monkeypatch.setattr(m, "main_checkout_for", lambda p: "/main")
    monkeypatch.setattr(m, "branch_exists", lambda main, b: branch)
    monkeypatch.setattr(m, "branch_merged", lambda main, t, b: merged)
    monkeypatch.setattr(m, "worktree_dirty", lambda p: dirty)
    monkeypatch.setattr(m, "active_owners", lambda p: list(owners or []))


def test_enqueue_list_remove_roundtrip(mod):
    m = mod
    m.save_record(_record(m, enqueued_at="t0"))
    assert [r.name for r in m.load_records()] == ["wt-x"]
    m.remove_record("wt-x")
    assert m.load_records() == []


def test_decision_gone_when_dir_missing(mod, monkeypatch):
    m = mod
    _patch_state(m, monkeypatch, exists=False)
    assert m.purge_decision(_record(m))[0] == "gone"


def test_decision_skip_unmerged(mod, monkeypatch):
    m = mod
    _patch_state(m, monkeypatch, merged=False)
    assert m.purge_decision(_record(m))[0] == "skip_unmerged"


def test_decision_skip_dirty(mod, monkeypatch):
    m = mod
    _patch_state(m, monkeypatch, dirty=True)
    assert m.purge_decision(_record(m))[0] == "skip_dirty"


def test_decision_skip_owned_reports_pids(mod, monkeypatch):
    m = mod
    _patch_state(m, monkeypatch, owners=[SimpleNamespace(pid=123, command="claude")])
    decision, reason = m.purge_decision(_record(m))
    assert decision == "skip_owned"
    assert "123" in reason


def test_decision_purge_when_clean_and_free(mod, monkeypatch):
    m = mod
    _patch_state(m, monkeypatch)
    assert m.purge_decision(_record(m))[0] == "purge"


def test_sweep_purges_and_removes_record(mod, monkeypatch):
    m = mod
    m.save_record(_record(m))
    _patch_state(m, monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(m, "do_purge", lambda main, path: (calls.append(path), (True, "ok"))[1])
    assert m.cmd_sweep(SimpleNamespace(from_hook=True)) == 0
    assert calls == ["/tmp/wt-x"]
    assert m.load_records() == []


def test_sweep_keeps_record_when_owned(mod, monkeypatch):
    m = mod
    m.save_record(_record(m))
    _patch_state(m, monkeypatch, owners=[SimpleNamespace(pid=1, command="cowork")])

    def _boom(main, path):
        raise AssertionError("must not purge an owned worktree")

    monkeypatch.setattr(m, "do_purge", _boom)
    assert m.cmd_sweep(SimpleNamespace(from_hook=True)) == 0
    records = m.load_records()
    assert len(records) == 1
    assert records[0].last_status == "skip_owned"


def test_sweep_keeps_record_when_unmerged(mod, monkeypatch):
    m = mod
    m.save_record(_record(m))
    _patch_state(m, monkeypatch, merged=False)

    def _boom(main, path):
        raise AssertionError("must not purge an unmerged worktree")

    monkeypatch.setattr(m, "do_purge", _boom)
    assert m.cmd_sweep(SimpleNamespace(from_hook=True)) == 0
    assert m.load_records()[0].last_status == "skip_unmerged"
