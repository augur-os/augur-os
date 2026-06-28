"""Unit tests for src.scripts._launch_worktree — worktree launcher helpers.

Pure/deterministic logic is tested directly; subprocess-driven helpers are
exercised with real tiny scripts or by monkeypatching the module's collaborators.
Nothing touches the real repo or vault.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from src.scripts import _launch_worktree


def test_helper_env_composes_pythonpath_without_existing(monkeypatch, tmp_path):
    monkeypatch.delenv("PYTHONPATH", raising=False)
    env = _launch_worktree.helper_env(tmp_path)
    parts = env["PYTHONPATH"].split(":") if sys.platform != "win32" else env["PYTHONPATH"].split(";")
    assert str(tmp_path) in parts
    assert str(tmp_path / "project-brain" / "capabilities") in parts


def test_helper_env_appends_existing_pythonpath(monkeypatch, tmp_path):
    monkeypatch.setenv("PYTHONPATH", "/existing/path")
    env = _launch_worktree.helper_env(tmp_path)
    assert env["PYTHONPATH"].endswith("/existing/path")


def test_derive_worktree_name_format():
    name = _launch_worktree.derive_worktree_name()
    assert name.startswith("wt-")
    # wt-YYYYmmdd-HHMMSS
    stamp = name[len("wt-") :]
    date_part, time_part = stamp.split("-")
    assert len(date_part) == 8 and date_part.isdigit()
    assert len(time_part) == 6 and time_part.isdigit()


def test_run_python_helper_missing_optional_returns_none(tmp_path):
    assert _launch_worktree.run_python_helper(tmp_path, "does/not/exist.py") is None


def test_run_python_helper_missing_required_raises(tmp_path):
    with pytest.raises(RuntimeError, match="required helper not found"):
        _launch_worktree.run_python_helper(tmp_path, "does/not/exist.py", required=True)


def test_run_python_helper_runs_real_script(tmp_path):
    script = tmp_path / "hello.py"
    script.write_text("print('hello-world')\n", encoding="utf-8")
    out = _launch_worktree.run_python_helper(tmp_path, "hello.py")
    assert out is not None
    assert "hello-world" in out


def test_run_python_helper_failing_optional_warns_returns_none(tmp_path, capsys):
    script = tmp_path / "boom.py"
    script.write_text("import sys; sys.exit(1)\n", encoding="utf-8")
    out = _launch_worktree.run_python_helper(tmp_path, "boom.py")
    assert out is None
    assert "Warning:" in capsys.readouterr().err


def test_run_python_helper_failing_required_raises(tmp_path):
    script = tmp_path / "boom.py"
    script.write_text("import sys; sys.stderr.write('kaboom'); sys.exit(2)\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="kaboom"):
        _launch_worktree.run_python_helper(tmp_path, "boom.py", required=True)


def test_register_worktree_writes_env_and_yaml(monkeypatch, tmp_path):
    wt_dir = tmp_path / "wt"
    wt_dir.mkdir()
    repo = tmp_path / "repo"

    payload = {
        "success": True,
        "worktree": {"dashboard_port": 3003, "mcp_port": 4003},
    }
    monkeypatch.setattr(
        _launch_worktree,
        "run_python_helper",
        lambda *a, **k: json.dumps(payload),
    )

    dash, mcp = _launch_worktree.register_worktree(repo, wt_dir, "wt-test")
    assert dash == "3003"
    assert mcp == "4003"

    env_local = (wt_dir / ".env.local").read_text(encoding="utf-8")
    assert "PORT=3003" in env_local

    wt_yaml = (wt_dir / ".augur-worktree.yaml").read_text(encoding="utf-8")
    assert "dashboard_port: 3003" in wt_yaml
    assert "mcp_port: 4003" in wt_yaml
    assert "name: wt-test" in wt_yaml


def test_register_worktree_helper_unavailable_returns_none_tuple(monkeypatch, tmp_path):
    monkeypatch.setattr(_launch_worktree, "run_python_helper", lambda *a, **k: None)
    assert _launch_worktree.register_worktree(tmp_path, tmp_path, "x") == (None, None)


def test_register_worktree_failure_payload_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(
        _launch_worktree,
        "run_python_helper",
        lambda *a, **k: json.dumps({"success": False, "error": "boom"}),
    )
    with pytest.raises(RuntimeError, match="boom"):
        _launch_worktree.register_worktree(tmp_path, tmp_path, "x")


def test_resolve_base_ref_prefers_origin_main(monkeypatch, tmp_path):
    def fake_run_git(repo, *args, check=True):
        if args[:1] == ("fetch",):
            return subprocess.CompletedProcess(args, 0, "", "")
        # rev-parse --verify --quiet origin/main
        return subprocess.CompletedProcess(args, 0, "abc123\n", "")

    monkeypatch.setattr(_launch_worktree, "run_git", fake_run_git)
    assert _launch_worktree.resolve_base_ref(tmp_path) == "origin/main"


def test_resolve_base_ref_falls_back_to_main(monkeypatch, tmp_path):
    def fake_run_git(repo, *args, check=True):
        if args[:1] == ("fetch",):
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 1, "", "no origin/main")

    monkeypatch.setattr(_launch_worktree, "run_git", fake_run_git)
    assert _launch_worktree.resolve_base_ref(tmp_path) == "main"
