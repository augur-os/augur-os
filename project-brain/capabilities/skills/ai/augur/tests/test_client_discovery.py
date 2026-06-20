"""Tests for client-native skill discovery."""

import sys
import os
import pytest
from pathlib import Path
from unittest.mock import patch

# Add AI ops scripts to path for import
_SCRIPTS_DIR = str(Path(__file__).resolve().parents[2] / "scripts" / "ops")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


@pytest.fixture
def mock_claude_home(tmp_path):
    """Create a mock Claude Code config directory."""
    claude_dir = tmp_path / ".claude"

    # Augur-synced skill (symlink)
    synced = claude_dir / "skills" / "career"
    synced.mkdir(parents=True)
    (synced / "SKILL.md").write_text("---\nname: career\ndescription: Career skill\n---\n")
    (synced / ".augur-symlink").write_text("")  # marker for test

    # Client-native skill (not a symlink)
    native = claude_dir / "plugins" / "cache" / "test-plugin" / "skills" / "brainstorming"
    native.mkdir(parents=True)
    (native / "SKILL.md").write_text(
        "---\nname: brainstorming\ndescription: Brainstorm ideas\nx-augur-mcp-tools: []\n---\n"
    )

    # Client-native command
    cmd = claude_dir / "commands" / "review"
    cmd.mkdir(parents=True)
    (cmd / "SKILL.md").write_text("---\nname: review\ndescription: Code review\n---\n")

    return claude_dir


class TestDiscoverClientSkills:
    def test_discovers_native_skills(self, mock_claude_home):
        from client_discovery import discover_client_skills

        with patch.dict(os.environ, {"AUGUR_CLAUDE_CONFIG": str(mock_claude_home)}):
            skills = discover_client_skills(clients=["claude-code"])

        names = [s["name"] for s in skills]
        assert "brainstorming" in names
        assert "review" in names

    def test_excludes_augur_synced_symlinks(self, mock_claude_home, tmp_path):
        """Symlinked skills pointing to Augur project tree should be excluded."""
        from client_discovery import discover_client_skills

        # Create a real symlink pointing to Augur project
        augur_root = tmp_path / "augur-project"
        augur_skill = augur_root / "plugins" / "career" / "skills" / "career" / "SKILL.md"
        augur_skill.parent.mkdir(parents=True)
        augur_skill.write_text("---\nname: career\n---\n")

        synced_dir = mock_claude_home / "skills" / "career-linked"
        synced_dir.mkdir(parents=True, exist_ok=True)
        synced_skill = synced_dir / "SKILL.md"
        real_symlink = True
        try:
            synced_skill.symlink_to(augur_skill)
        except OSError:
            real_symlink = False
            synced_skill.write_text("---\nname: career-linked\n---\n")

        with patch("client_discovery.get_project_root", return_value=augur_root), patch.dict(
            os.environ, {"AUGUR_CLAUDE_CONFIG": str(mock_claude_home)}
        ):
            if real_symlink:
                skills = discover_client_skills(clients=["claude-code"])
            else:
                # Windows without Developer Mode/admin cannot create symlinks.
                # Keep the behavior under test by making only this path behave
                # like a link back into the synthetic Augur root.
                original_is_symlink = Path.is_symlink
                original_resolve = Path.resolve

                def fake_is_symlink(path):
                    return path == synced_skill or original_is_symlink(path)

                def fake_resolve(path, *args, **kwargs):
                    if path == synced_skill:
                        return augur_skill
                    return original_resolve(path, *args, **kwargs)

                with patch.object(Path, "is_symlink", fake_is_symlink), patch.object(
                    Path, "resolve", fake_resolve
                ):
                    skills = discover_client_skills(clients=["claude-code"])

        names = [s["name"] for s in skills]
        assert "career-linked" not in names

    def test_returns_correct_metadata_shape(self, mock_claude_home):
        from client_discovery import discover_client_skills

        with patch.dict(os.environ, {"AUGUR_CLAUDE_CONFIG": str(mock_claude_home)}):
            skills = discover_client_skills(clients=["claude-code"])

        skill = next(s for s in skills if s["name"] == "brainstorming")
        assert skill["source_client"] == "claude-code"
        assert skill["scope"] == "global"
        assert skill["has_skill_md"] is True
        assert "path" in skill
        assert "description" in skill

    def test_handles_missing_client_dir_gracefully(self):
        from client_discovery import discover_client_skills

        with patch.dict(os.environ, {"AUGUR_CLAUDE_CONFIG": "/nonexistent/path"}):
            skills = discover_client_skills(clients=["claude-code"])

        assert skills == []

    def test_codex_excludes_augur_managed_native_bundle(self, tmp_path):
        from client_discovery import discover_client_skills

        project_codex = tmp_path / ".codex-project"
        project_augur = project_codex / "skills" / "ask"
        project_augur.mkdir(parents=True)
        (project_augur.parent / ".augur-managed.json").write_text('{"skills":["ask"]}\n')
        (project_augur / "SKILL.md").write_text(
            "---\nname: ask\ndescription: Reflective query\n---\n"
        )
        global_codex = tmp_path / ".codex-global"
        project_personal = global_codex / "skills" / "ui-ux-pro-max"
        project_personal.mkdir(parents=True)
        (project_personal / "SKILL.md").write_text(
            "---\nname: ui-ux-pro-max\ndescription: Personal skill\n---\n"
        )

        personal_bundle = tmp_path / ".agents" / "skills" / "superpowers" / "brainstorming"
        personal_bundle.mkdir(parents=True)
        (personal_bundle / "SKILL.md").write_text(
            "---\nname: brainstorming\ndescription: Brainstorm ideas\n---\n"
        )

        with patch(
            "client_discovery.get_client_config_dir",
            side_effect=lambda client, scope="global": project_codex if scope == "project" else global_codex if client == "codex" else Path("/nonexistent"),
        ):
            skills = discover_client_skills(clients=["codex"])

        names = [s["name"] for s in skills]
        assert "ask" not in names
        assert "ui-ux-pro-max" in names
        assert "brainstorming" not in names
