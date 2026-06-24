"""npm-audit timeout + lockfile-hash cache for the hardening loop."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_REPO = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
_MOD = _REPO / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts" / "ops" / "security_scan.py"


def _load():
    spec = importlib.util.spec_from_file_location("security_scan_under_test", _MOD)
    m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m); return m


def _make_dashboard(tmp: Path, lock_body: str = "v1") -> Path:
    d = tmp / "apps" / "dashboard"; d.mkdir(parents=True)
    (d / "package.json").write_text('{"name":"x"}', encoding="utf-8")
    (d / "package-lock.json").write_text(lock_body, encoding="utf-8")
    return tmp


def test_audit_skipped_when_lockfile_unchanged(tmp_path, monkeypatch):
    m = _load()
    root = _make_dashboard(tmp_path)
    cache = tmp_path / "cache"
    calls = {"n": 0}
    def fake_run(*a, **k):
        calls["n"] += 1
        return subprocess.CompletedProcess(a[0], 0, stdout="{}", stderr="")
    monkeypatch.setattr(m.subprocess, "run", fake_run)
    first = m._scan_npm_audit(root, cache_dir=cache)
    second = m._scan_npm_audit(root, cache_dir=cache)   # lockfile unchanged
    assert calls["n"] == 1, "audit should run once then hit cache"
    assert first == second


def test_audit_reruns_when_lockfile_changes(tmp_path, monkeypatch):
    m = _load()
    root = _make_dashboard(tmp_path, "v1")
    cache = tmp_path / "cache"
    calls = {"n": 0}
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: (calls.__setitem__("n", calls["n"]+1) or subprocess.CompletedProcess(a[0], 0, stdout="{}", stderr="")))
    m._scan_npm_audit(root, cache_dir=cache)
    (root / "apps" / "dashboard" / "package-lock.json").write_text("v2", encoding="utf-8")
    m._scan_npm_audit(root, cache_dir=cache)
    assert calls["n"] == 2


def test_audit_timeout_is_non_fatal(tmp_path, monkeypatch):
    m = _load()
    root = _make_dashboard(tmp_path)
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd=a[0], timeout=30)
    monkeypatch.setattr(m.subprocess, "run", boom)
    out = m._scan_npm_audit(root, cache_dir=tmp_path / "c", timeout=30)
    assert any(i.get("action") == "npm-audit-skipped" for i in out)


def test_different_projects_do_not_share_cache(tmp_path, monkeypatch):
    m = _load()
    # two projects, both with NO lockfile (both would hash to "no-lock")
    a = tmp_path / "a"; (a / "apps" / "dashboard").mkdir(parents=True); (a / "apps" / "dashboard" / "package.json").write_text("{}", encoding="utf-8")
    b = tmp_path / "b"; (b / "apps" / "dashboard").mkdir(parents=True); (b / "apps" / "dashboard" / "package.json").write_text("{}", encoding="utf-8")
    cache = tmp_path / "shared-cache"
    calls = {"n": 0}
    monkeypatch.setattr(m.subprocess, "run", lambda *a_, **k: (calls.__setitem__("n", calls["n"]+1) or subprocess.CompletedProcess(a_[0], 0, stdout="{}", stderr="")))
    m._scan_npm_audit(a, cache_dir=cache)
    m._scan_npm_audit(b, cache_dir=cache)   # different project, same shared cache dir
    assert calls["n"] == 2, "each project must run its own audit (no cross-project cache share)"
