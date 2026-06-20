"""Tests for cleanup_temp_files root junk detection."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    script_path = PROJECT_ROOT / ".github" / "scripts" / "cleanup_temp_files.py"
    spec = importlib.util.spec_from_file_location("cleanup_temp_files", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("cleanup_temp_files", module)
    spec.loader.exec_module(module)
    return module


def test_find_temp_files_catches_root_pollution_patterns(tmp_path):
    mod = _load_module()

    (tmp_path / ".DS_Store").write_text("", encoding="utf-8")
    (tmp_path / "tmp-browse-regular.png").write_bytes(b"png")
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "artifact.txt").write_text("x", encoding="utf-8")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "artifact.txt").write_text("x", encoding="utf-8")

    temp_files, temp_dirs = mod.find_temp_files(tmp_path)

    found_files = {path.name for path in temp_files}
    found_dirs = {path.name for path in temp_dirs}

    assert ".DS_Store" in found_files
    assert "tmp-browse-regular.png" in found_files
    assert "output" in found_dirs
    assert "build" in found_dirs


def test_find_temp_files_skips_tracked_files_with_ambiguous_names(tmp_path):
    mod = _load_module()

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    tracked = tmp_path / "DEBUGGING.md"
    tracked.write_text("kept", encoding="utf-8")
    subprocess.run(["git", "add", "DEBUGGING.md"], cwd=tmp_path, check=True, capture_output=True, text=True)

    temp_files, _temp_dirs = mod.find_temp_files(tmp_path)
    found_files = {path.name for path in temp_files}

    assert "DEBUGGING.md" not in found_files


def test_find_temp_files_only_applies_risky_name_patterns_at_repo_root(tmp_path):
    mod = _load_module()

    nested = tmp_path / ".codex" / "prompts"
    nested.mkdir(parents=True)
    (nested / "draft-reply.md").write_text("keep", encoding="utf-8")

    temp_files, _temp_dirs = mod.find_temp_files(tmp_path)
    found_files = {str(path.relative_to(tmp_path)) for path in temp_files}

    assert ".codex/prompts/draft-reply.md" not in found_files
