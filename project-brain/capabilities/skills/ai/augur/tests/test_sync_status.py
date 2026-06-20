"""Tests for sync status checking."""

import sys
from pathlib import Path
from unittest.mock import patch

# Add AI ops scripts to path for import
_SCRIPTS_DIR = str(Path(__file__).resolve().parents[2] / "scripts" / "ops")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


class TestGetSyncStatus:
    def test_returns_status_per_client(self, tmp_path):
        from sync_status import get_sync_status

        # Create mock Claude skills dir with a synced skill
        claude_skills = tmp_path / ".claude" / "skills" / "career"
        claude_skills.mkdir(parents=True)
        (claude_skills / "SKILL.md").write_text("---\nname: career\n---\n")

        with patch("sync_status.get_client_config_dir") as mock_dir, \
             patch("sync_status.get_client_skill_dirs") as mock_skill_dirs:
            mock_dir.return_value = tmp_path / ".claude"
            mock_skill_dirs.return_value = {
                "claude-local": tmp_path / ".claude" / "skills",
                "claude-global": Path("/nonexistent"),
            }
            status = get_sync_status(clients=["claude-code"])

        assert "claude-code" in status
        assert "synced_skills" in status["claude-code"]
        assert isinstance(status["claude-code"]["synced_skills"], list)
        assert status["claude-code"]["synced_skills"] == ["career"]

    def test_reports_missing_client_dir(self):
        from sync_status import get_sync_status

        with patch("sync_status.get_client_config_dir") as mock_dir, \
             patch("sync_status.get_client_skill_dirs") as mock_skill_dirs:
            mock_dir.return_value = Path("/nonexistent")
            mock_skill_dirs.return_value = {}
            status = get_sync_status(clients=["claude-code"])

        assert status["claude-code"]["status"] == "not_installed"

    def test_reports_opencode_subdir_skills(self, tmp_path):
        from sync_status import get_sync_status

        opencode_skill = tmp_path / ".config" / "opencode" / "skills" / "apple"
        opencode_skill.mkdir(parents=True)
        (opencode_skill / "SKILL.md").write_text("---\nname: apple\n---\n")

        with patch("sync_status.get_client_config_dir") as mock_dir, \
             patch("sync_status.get_client_skill_dirs") as mock_skill_dirs:
            mock_dir.return_value = tmp_path / ".config" / "opencode"
            mock_skill_dirs.return_value = {
                "opencode-local": Path("/nonexistent"),
                "opencode-global": tmp_path / ".config" / "opencode" / "skills",
            }
            status = get_sync_status(clients=["opencode"])

        assert status["opencode"]["status"] == "healthy"
        assert status["opencode"]["synced_skills"] == ["apple"]

    def test_codex_status_reports_client_skill_dirs_only(self, tmp_path):
        from sync_status import get_sync_status

        project_skill = tmp_path / ".codex-project" / "skills" / "commands"
        project_skill.mkdir(parents=True)
        (project_skill / "SKILL.md").write_text("---\nname: commands\n---\n")
        (project_skill.parent / ".augur-managed.json").write_text('{"skills":["commands"]}\n')

        global_skill = tmp_path / ".codex-global" / "skills" / "search"
        global_skill.mkdir(parents=True)
        (global_skill / "SKILL.md").write_text("---\nname: search\n---\n")
        (global_skill.parent / ".augur-managed.json").write_text('{"skills":["search"]}\n')

        old_native_skill = tmp_path / ".agents" / "skills" / "augur" / "legacy"
        old_native_skill.mkdir(parents=True)
        (old_native_skill / "SKILL.md").write_text("---\nname: legacy\n---\n")

        with patch(
            "sync_status.get_client_config_dir",
            side_effect=lambda client, scope="global": tmp_path / ".codex-project" if scope == "project" else tmp_path / ".codex-global",
        ), patch("sync_status.get_client_skill_dirs") as mock_skill_dirs:
            mock_skill_dirs.return_value = {
                "codex-local": project_skill.parent,
                "codex-global": global_skill.parent,
            }
            status = get_sync_status(clients=["codex"])

        assert status["codex"]["status"] == "healthy"
        assert status["codex"]["synced_skills"] == ["commands", "search"]
