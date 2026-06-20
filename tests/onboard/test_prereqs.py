from pathlib import Path

import src.lib.onboard.prereqs as p
from src.lib.onboard.result import OnboardContext


def test_all_present_returns_ok(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(p.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(p, "_node_major", lambda: p.MIN_NODE_MAJOR)
    r = p.detect_prereqs(OnboardContext(repo_root=tmp_path))
    assert r.status == "ok"


def test_old_node_returns_guide(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(p, "_current_os", lambda: "darwin")
    monkeypatch.setattr(p.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(p, "_node_major", lambda: p.MIN_NODE_MAJOR - 1)
    r = p.detect_prereqs(OnboardContext(repo_root=tmp_path))
    assert r.status == "guide"
    assert f">= {p.MIN_NODE_MAJOR}" in r.message
    assert r.details["node_major"] == p.MIN_NODE_MAJOR - 1


def test_undeterminable_node_does_not_block(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(p.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(p, "_node_major", lambda: None)
    r = p.detect_prereqs(OnboardContext(repo_root=tmp_path))
    assert r.status == "ok"


def test_missing_tool_returns_guide_with_command(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(p, "_current_os", lambda: "darwin")
    monkeypatch.setattr(p.shutil, "which", lambda tool: None if tool == "uv" else "/usr/bin/x")
    r = p.detect_prereqs(OnboardContext(repo_root=tmp_path))
    assert r.status == "guide"
    assert "uv" in r.message
    assert "astral.sh/uv/install.sh" in r.message  # macOS guidance
    assert r.details["missing"] == ["uv"]


def test_missing_tool_windows_guidance(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(p, "_current_os", lambda: "windows")
    monkeypatch.setattr(p.shutil, "which", lambda tool: None if tool == "node" else "/usr/bin/x")
    r = p.detect_prereqs(OnboardContext(repo_root=tmp_path))
    assert r.status == "guide"
    assert "winget install OpenJS.NodeJS" in r.message
