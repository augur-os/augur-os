"""Tests for data_migration_safety.py — backup, YAML validation, orphan detection."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from data_migration_safety import (
    backup_file,
    detect_orphaned_data,
    validate_yaml,
)


# ---------------------------------------------------------------------------
# validate_yaml
# ---------------------------------------------------------------------------


class TestValidateYaml:
    def test_valid_yaml(self, tmp_path):
        f = tmp_path / "good.yaml"
        f.write_text("name: test\nversion: 1\n")
        issues = validate_yaml(f)
        assert issues == []

    def test_empty_yaml(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text("")
        issues = validate_yaml(f)
        assert len(issues) == 1
        assert "empty" in issues[0].lower()

    def test_invalid_yaml(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text("key: [unterminated\n")
        issues = validate_yaml(f)
        assert len(issues) >= 1
        assert "parse error" in issues[0].lower()


# ---------------------------------------------------------------------------
# backup_file
# ---------------------------------------------------------------------------


class TestBackupFile:
    @patch("data_migration_safety.get_runtime_dir")
    @patch("data_migration_safety.get_project_root")
    def test_creates_backup(self, mock_root, mock_runtime, tmp_path):
        mock_root.return_value = tmp_path
        mock_runtime.return_value = tmp_path / "runtime"

        source = tmp_path / "data.yaml"
        source.write_text("key: value\n")

        backup_path = backup_file(source)
        assert backup_path.exists()
        assert backup_path.read_text() == "key: value\n"

    @patch("data_migration_safety.get_runtime_dir")
    @patch("data_migration_safety.get_project_root")
    def test_backup_preserves_extension(self, mock_root, mock_runtime, tmp_path):
        mock_root.return_value = tmp_path
        mock_runtime.return_value = tmp_path / "runtime"

        source = tmp_path / "tasks.yaml"
        source.write_text("items: []\n")

        backup_path = backup_file(source)
        assert backup_path.suffix == ".yaml"


# ---------------------------------------------------------------------------
# detect_orphaned_data
# ---------------------------------------------------------------------------


class TestDetectOrphanedData:
    def test_no_plugins_dir(self, tmp_path):
        issues = detect_orphaned_data(tmp_path)
        assert len(issues) == 1
        assert "not found" in issues[0]

    def test_no_orphans(self, tmp_path):
        skill_dir = tmp_path / "plugins" / "dev" / "skills" / "devops"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("name: platform-admin")
        (skill_dir / "data").mkdir()
        (skill_dir / "data" / "config.yaml").write_text("key: value")
        issues = detect_orphaned_data(tmp_path)
        assert issues == []

    def test_detects_orphaned_data(self, tmp_path):
        skill_dir = tmp_path / "plugins" / "dev" / "skills" / "orphan-skill"
        skill_dir.mkdir(parents=True)
        # Create data dir without any code files
        data_dir = skill_dir / "data"
        data_dir.mkdir()
        (data_dir / "something.yaml").write_text("orphaned: true")

        issues = detect_orphaned_data(tmp_path)
        assert len(issues) == 1
        assert "Orphaned data" in issues[0]
        assert "orphan-skill" in issues[0]
