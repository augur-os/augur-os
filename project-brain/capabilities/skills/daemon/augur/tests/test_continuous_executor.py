"""Tests for continuous_executor.py -- background task execution daemon."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SHARED_VAULT_ROOT = REPO_ROOT / "project-brain"
SCRIPTS_PATH = Path(__file__).resolve().parents[2] / "scripts" / "continuous_executor.py"

for _path in (REPO_ROOT, SHARED_VAULT_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

# Provide a stub for task_utils before loading the module
import types

_tu = types.ModuleType("task_utils")
_tu.all_backlog_dirs = lambda: []
_tu.is_task_available = lambda fm, stale_hours=2: True
_tu.read_task = lambda path: ({}, "")
_tu.resolve_user_data_base = lambda: Path("/tmp/augur-test-data")
sys.modules["task_utils"] = _tu

_spec = importlib.util.spec_from_file_location("continuous_executor", SCRIPTS_PATH)
continuous_executor = importlib.util.module_from_spec(_spec)
sys.modules["continuous_executor"] = continuous_executor
assert _spec.loader is not None
_spec.loader.exec_module(continuous_executor)


def test_continuous_executor_uses_platform_admin_scripts_dir():
    """Autonomous executor utilities live in platform-admin after the skill split."""
    expected = SHARED_VAULT_ROOT / "capabilities" / "skills" / "platform-admin" / "scripts"
    assert continuous_executor.DEVOPS_SCRIPTS == expected


def test_resolve_platform_admin_scripts_uses_shared_vault_when_skill_root_lookup_fails(tmp_path, monkeypatch):
    """Fallback resolution must not revive the retired repo-root skills tree."""
    shared_scripts = tmp_path / "project-brain" / "capabilities" / "skills" / "platform-admin" / "scripts"
    legacy_scripts = tmp_path / "skills" / "platform-admin" / "scripts"
    shared_scripts.mkdir(parents=True)
    legacy_scripts.mkdir(parents=True)

    monkeypatch.setattr(continuous_executor, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        continuous_executor,
        "get_skill_root",
        lambda _skill_name: (_ for _ in ()).throw(ValueError("not found")),
    )

    assert continuous_executor._resolve_platform_admin_scripts() == shared_scripts


class TestDeepMerge:
    """Tests for _deep_merge config utility."""

    def test_flat_override(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = continuous_executor._deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"outer": {"a": 1, "b": 2}}
        override = {"outer": {"b": 3}}
        result = continuous_executor._deep_merge(base, override)
        assert result == {"outer": {"a": 1, "b": 3}}

    def test_override_replaces_non_dict_with_dict(self):
        base = {"x": 1}
        override = {"x": {"nested": True}}
        result = continuous_executor._deep_merge(base, override)
        assert result == {"x": {"nested": True}}


class TestLoadConfig:
    """Tests for config loading with defaults."""

    def test_nonexistent_path_returns_defaults(self, tmp_path):
        fake_path = tmp_path / "does-not-exist.yaml"
        with patch.object(continuous_executor, "_load_services_config", return_value={}):
            config = continuous_executor.load_config(fake_path)
        assert config["enabled"] is True
        assert config["max_parallel"] == 3
        assert config["poll_interval_seconds"] == 300

    def test_yaml_file_merges_with_defaults(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("max_parallel: 5\nmodel: opus\n", encoding="utf-8")
        with patch.object(continuous_executor, "_load_services_config", return_value={}):
            config = continuous_executor.load_config(cfg_file)
        assert config["max_parallel"] == 5
        assert config["model"] == "opus"
        assert config["poll_interval_seconds"] == 300  # default preserved

    def test_services_config_overlays(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("max_parallel: 2\n", encoding="utf-8")
        overlay = {"max_parallel": 8, "model": "haiku"}
        with patch.object(continuous_executor, "_load_services_config", return_value=overlay):
            config = continuous_executor.load_config(cfg_file)
        assert config["max_parallel"] == 8
        assert config["model"] == "haiku"


class TestWriteCycleLog:
    """Tests for cycle log writing."""

    def test_writes_json_log(self, tmp_path):
        results = [
            {"task_path": "/t/1.md", "success": True, "exit_code": 0, "stdout": "", "stderr": ""},
            {"task_path": "/t/2.md", "success": False, "exit_code": 1, "stdout": "", "stderr": "err"},
        ]
        continuous_executor.write_cycle_log(
            cycle=1, tasks_found=3, tasks_started=2, results=results, log_dir=tmp_path
        )
        log_files = list(tmp_path.glob("cycle-*.json"))
        assert len(log_files) == 1
        data = json.loads(log_files[0].read_text())
        assert data["cycle"] == 1
        assert data["succeeded"] == 1
        assert data["failed"] == 1
        assert data["tasks_found"] == 3


class TestFindAutonomousTasks:
    """Tests for autonomous task discovery."""

    def test_returns_empty_when_no_backlog_dirs(self):
        with patch.object(_tu, "all_backlog_dirs", return_value=[]):
            tasks = continuous_executor.find_autonomous_tasks()
        assert tasks == []

    def test_discovers_autonomous_tasks(self, tmp_path):
        task_file = tmp_path / "tasks" / "fix-bug.md"
        task_file.parent.mkdir(parents=True)
        task_file.write_text(
            "---\ntitle: Fix bug\nautonomous: true\npriority: high\nstatus: backlog\n---\nFix the thing.\n"
        )

        def mock_all_backlog():
            return [tmp_path / "tasks"]

        def mock_read(path):
            return (
                {"title": "Fix bug", "autonomous": True, "priority": "high", "status": "backlog"},
                "Fix the thing.",
            )

        with patch.object(continuous_executor, "all_backlog_dirs", mock_all_backlog), \
             patch.object(continuous_executor, "read_task", mock_read), \
             patch.object(continuous_executor, "is_task_available", return_value=True):
            tasks = continuous_executor.find_autonomous_tasks()
        assert len(tasks) == 1
        assert tasks[0].name == "fix-bug.md"
