"""Tests for ci_change_detector.py — CI change detection and skill scanning."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import ci_change_detector as ccd


# ---------------------------------------------------------------------------
# get_skill_name
# ---------------------------------------------------------------------------


class TestGetSkillName:
    def test_returns_basename_when_no_skill_md(self, tmp_path):
        result = ccd.get_skill_name(str(tmp_path))
        assert result == tmp_path.name

    def test_extracts_name_from_skill_md(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\nname: my-cool-skill\n---\n")
        result = ccd.get_skill_name(str(tmp_path))
        assert result == "my-cool-skill"

    def test_falls_back_on_parse_failure(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("no name field here")
        result = ccd.get_skill_name(str(tmp_path))
        assert result == tmp_path.name


# ---------------------------------------------------------------------------
# get_changed_files
# ---------------------------------------------------------------------------


class TestGetChangedFiles:
    @patch.object(ccd, "_run_command")
    def test_returns_list_of_files(self, mock_run):
        mock_run.return_value = MagicMock(stdout="file1.py\nfile2.py\n", returncode=0)
        result = ccd.get_changed_files("abc123", "def456")
        assert result == ["file1.py", "file2.py"]

    @patch.object(ccd, "_run_command")
    def test_returns_empty_on_error(self, mock_run):
        from subprocess import CalledProcessError
        mock_run.side_effect = CalledProcessError(1, "git diff")
        result = ccd.get_changed_files("abc", "def")
        assert result == []


# ---------------------------------------------------------------------------
# scan_all_skills
# ---------------------------------------------------------------------------


class TestScanAllSkills:
    def test_scans_plugins_structure(self, tmp_path, monkeypatch):
        """Build a minimal plugin structure and verify scanning works."""
        monkeypatch.chdir(tmp_path)

        # Create a plugin structure
        skill_dir = tmp_path / "plugins" / "dev" / "skills" / "platform-admin"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: platform-admin\n---\n")

        # Remove GITHUB_OUTPUT to get local output
        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

        # Capture stdout
        import io
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stdout", buf)

        ccd.scan_all_skills()
        output = json.loads(buf.getvalue())
        assert output["has_skills"] == "true"
        matrix = json.loads(output["matrix"])
        names = [s["name"] for s in matrix]
        assert "platform-admin" in names

    def test_scans_shared_vault_structure(self, tmp_path, monkeypatch):
        """Shared-vault skills are active skill roots after the migration."""
        monkeypatch.chdir(tmp_path)

        skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "platform-admin"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: platform-admin\n---\n")

        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

        import io
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stdout", buf)

        ccd.scan_all_skills()
        output = json.loads(buf.getvalue())
        matrix = json.loads(output["matrix"])

        assert {
            "name": "platform-admin",
            "path": "project-brain/capabilities/skills/platform-admin",
            "layer": "project-brain",
        } in matrix

    def test_main_detects_shared_vault_skill_changes(self, tmp_path, monkeypatch):
        """Changed project-brain skills should produce a skill matrix entry."""
        monkeypatch.chdir(tmp_path)

        skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "platform-admin"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: platform-admin\n---\n")

        monkeypatch.setattr(sys, "argv", ["ci_change_detector.py", "base", "head"])
        monkeypatch.setattr(
            ccd,
            "get_changed_files",
            lambda _base, _head: ["project-brain/capabilities/skills/platform-admin/SKILL.md"],
        )
        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

        import io
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stdout", buf)

        ccd.main()
        output = json.loads(buf.getvalue())
        matrix = json.loads(output["matrix"])

        assert matrix == [
            {
                "name": "platform-admin",
                "path": "project-brain/capabilities/skills/platform-admin",
                "layer": "project-brain",
            }
        ]
