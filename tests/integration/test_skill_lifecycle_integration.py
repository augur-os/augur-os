"""Integration test for the full skill lifecycle: discover → adopt → discover → status."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from src.mcp.augur_core.tools.core.skill_lifecycle import adopt_skill, skill_status
from src.plugins.skill_discovery import (
    _discover_all_skills_impl,
    invalidate_discovery_cache,
)


def _create_skill_md(path: Path, name: str, extra_fm: str = ""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nname: {name}\ndescription: {name} skill\n{extra_fm}---\n\nBody.\n")


def test_full_lifecycle():
    """Test: external skill → adopt → augur skill."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shared_skills = root / "project-brain" / "capabilities" / "skills"
        shared_skills.mkdir(parents=True)
        (root / ".claude" / "skills" / "ui-tool").mkdir(parents=True)
        _create_skill_md(root / ".claude" / "skills" / "ui-tool" / "SKILL.md", "ui-tool")

        # Phase 1: Discovery finds the Claude local skill
        with (
            patch("src.plugins.skill_discovery.get_project_brain_skills_dir", return_value=shared_skills),
            patch("src.plugins.skill_discovery.get_managed_skill_source_dirs", return_value=[shared_skills]),
            patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]),
            patch(
                "src.plugins.skill_discovery._get_client_skill_dirs",
                return_value={
                    "claude-local": root / ".claude" / "skills",
                    "claude-global": Path("/nonexistent"),
                    "codex-local": Path("/nonexistent"),
                    "codex-global": Path("/nonexistent"),
                },
            ),
        ):
            invalidate_discovery_cache()
            skills = _discover_all_skills_impl()

        ui = next((s for s in skills if s.name == "ui-tool"), None)
        assert ui is not None, "ui-tool should be discovered"
        assert ui.source == "claude-local"
        assert ui.ownership == "external"

        # Phase 2: Adopt
        result = adopt_skill("ui-tool", "claude-local", root)
        assert result["success"] is True, f"Adopt failed: {result['message']}"
        assert (shared_skills / "ui-tool" / "SKILL.md").exists()

        # Phase 3: Discovery now finds it as augur
        with (
            patch("src.plugins.skill_discovery.get_project_brain_skills_dir", return_value=shared_skills),
            patch("src.plugins.skill_discovery.get_managed_skill_source_dirs", return_value=[shared_skills]),
            patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]),
            patch(
                "src.plugins.skill_discovery._get_client_skill_dirs",
                return_value={
                    "claude-local": root / ".claude" / "skills",
                    "claude-global": Path("/nonexistent"),
                    "codex-local": Path("/nonexistent"),
                    "codex-global": Path("/nonexistent"),
                },
            ),
        ):
            invalidate_discovery_cache()
            skills = _discover_all_skills_impl()

        ui = next((s for s in skills if s.name == "ui-tool"), None)
        assert ui is not None, "ui-tool should still be discovered"
        assert ui.source == "project-brain", f"Expected source=project-brain after adopt, got {ui.source}"
        assert ui.ownership == "adopted"

        # Phase 4: Status shows ownership and upstream
        status = skill_status("ui-tool", root)
        assert status["ownership"] == "adopted"
        assert status["source"] == "project-brain"
        assert status["upstream"] == {
            "source": "claude-local",
            "path": ".claude/skills/ui-tool",
        }


def test_codex_lifecycle():
    """Test: Codex skill directory → adopt → augur skill."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shared_skills = root / "project-brain" / "capabilities" / "skills"
        shared_skills.mkdir(parents=True)
        codex_skills = root / ".codex" / "skills" / "codex-tool"
        codex_skills.mkdir(parents=True)
        (codex_skills / "SKILL.md").write_text("---\nname: codex-tool\ndescription: A codex skill\n---\n\nBody.\n")

        # Phase 1: Discover as codex-local
        with (
            patch("src.plugins.skill_discovery.get_project_brain_skills_dir", return_value=shared_skills),
            patch("src.plugins.skill_discovery.get_managed_skill_source_dirs", return_value=[shared_skills]),
            patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]),
            patch(
                "src.plugins.skill_discovery._get_client_skill_dirs",
                return_value={
                    "claude-local": Path("/nonexistent"),
                    "claude-global": Path("/nonexistent"),
                    "codex-local": root / ".codex" / "skills",
                    "codex-global": Path("/nonexistent"),
                },
            ),
        ):
            invalidate_discovery_cache()
            skills = _discover_all_skills_impl()

        ct = next((s for s in skills if s.name == "codex-tool"), None)
        assert ct is not None
        assert ct.source == "codex-local"
        assert ct.ownership == "external"

        # Phase 2: Adopt
        result = adopt_skill("codex-tool", "codex-local", root)
        assert result["success"] is True
        assert (shared_skills / "codex-tool" / "SKILL.md").exists()

        # Phase 3: Status shows adopted ownership and upstream
        status = skill_status("codex-tool", root)
        assert status["ownership"] == "adopted"
        assert status["source"] == "project-brain"
        assert status["upstream"] == {
            "source": "codex-local",
            "path": ".codex/skills/codex-tool",
        }


def test_adopt_already_exists_in_shared_vault_fails():
    """Cannot adopt if skill already exists in project-brain/capabilities/skills/."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "project-brain" / "capabilities" / "skills" / "existing").mkdir(parents=True)
        (root / "project-brain" / "capabilities" / "skills" / "existing" / "SKILL.md").write_text(
            "---\nname: existing\n---\n"
        )
        (root / ".claude" / "skills" / "existing").mkdir(parents=True)
        (root / ".claude" / "skills" / "existing" / "SKILL.md").write_text("---\nname: existing\n---\n")

        result = adopt_skill("existing", "claude-local", root)
        assert result["success"] is False


def test_adopt_ignores_stale_repo_root_skill():
    """A leftover root/skills copy does not block adoption into project-brain/capabilities/skills."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        stale_root_skill = root.joinpath("skills", "existing")
        stale_root_skill.mkdir(parents=True)
        (stale_root_skill / "SKILL.md").write_text("---\nname: existing\n---\n")
        (root / ".claude" / "skills" / "existing").mkdir(parents=True)
        (root / ".claude" / "skills" / "existing" / "SKILL.md").write_text("---\nname: existing\n---\n")

        result = adopt_skill("existing", "claude-local", root)

        assert result["success"] is True
        assert (root / "project-brain" / "capabilities" / "skills" / "existing" / "SKILL.md").exists()


def test_status_external_skill_reflects_client_location():
    """External skills should report their client location and external ownership."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "project-brain" / "capabilities" / "skills").mkdir(parents=True)
        (root / ".claude" / "skills" / "native").mkdir(parents=True)
        (root / ".claude" / "skills" / "native" / "SKILL.md").write_text(
            "---\nname: native\ndescription: outside project-brain skills\n---\n"
        )

        result = skill_status("native", root)
        assert result["ownership"] == "external"
        assert result["source"] == "claude-local"
        assert result["location"] == str(root / ".claude" / "skills" / "native")
        assert result["upstream"] == {}
