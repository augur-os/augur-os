from pathlib import Path
from unittest.mock import patch

from src.mcp.augur_shared.adapters.skill_detection import is_adapted_copy
from src.mcp.augur_shared.adapters.filesystem_registry import FilesystemSkillRegistry
from src.plugins.skill_discovery import SkillRecord


def _make_record(name: str, description: str, path: Path, **kwargs) -> SkillRecord:
    """Create a SkillRecord with sensible defaults for required fields."""
    defaults = dict(
        master="",
        hub="",
        visibility="",
        loop_config={},
        dependencies={},
        mcp_tools=[],
        dashboard_pages=[],
        commands=[],
        config={},
        agent=None,
        skill_type="",
        tags=(),
        tier=4,
        author="bundled",
    )
    defaults.update(kwargs)
    return SkillRecord(name=name, description=description, path=path, **defaults)


class TestIsAdaptedCopy:
    def test_adapted_copy_marker(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\nname: foo\n---\n<!-- AUGUR-ADAPTED-COPY source=claude-code -->\nBody")
        assert is_adapted_copy(skill_md) is True

    def test_stub_marker(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\nname: foo\n---\n<!-- AUGUR-STUB — full content via MCP get-skill -->\n")
        assert is_adapted_copy(skill_md) is True

    def test_master_skill(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\nname: foo\ndescription: real skill\n---\n# Foo\n\nReal content here.")
        assert is_adapted_copy(skill_md) is False

    def test_legacy_auto_generated(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("<!-- AUTO-GENERATED FILE -->\n---\nname: foo\n---\nBody")
        assert is_adapted_copy(skill_md) is True

    def test_nonexistent_file(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        assert is_adapted_copy(skill_md) is False

    def test_empty_file(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("")
        assert is_adapted_copy(skill_md) is False


class TestRegistryDedup:
    def _make_skill_dir(self, tmp_path, client_dir, skill_name, content):
        skill_dir = tmp_path / client_dir / skill_name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(content)
        return skill_dir

    def test_master_wins_over_adapted_copy(self, tmp_path):
        master_content = "---\nname: apple\ndescription: Apple integration\n---\n# Apple\nReal content"
        adapted_content = (
            "---\nname: apple\ndescription: Apple integration\n---\n<!-- AUGUR-ADAPTED-COPY source=claude-code -->"
        )
        self._make_skill_dir(tmp_path, ".claude/skills", "apple", master_content)
        self._make_skill_dir(tmp_path, ".gemini/skills", "apple", adapted_content)
        registry = FilesystemSkillRegistry(plugins_dir=tmp_path)
        # discover_all_skills handles dedup — master wins over adapted copy
        mock_records = [
            _make_record("apple", "Apple integration", tmp_path / ".claude/skills/apple"),
        ]
        with patch("src.mcp.augur_shared.adapters.filesystem_registry.discover_all_skills", return_value=mock_records):
            skills = registry._scan_skills()
        apple = [s for s in skills if s.name == "apple"]
        assert len(apple) == 1
        # Master should win — its path should be under .claude
        assert ".claude" in str(apple[0].path)

    def test_stub_excluded_from_registry(self, tmp_path):
        master_content = "---\nname: foo\ndescription: Foo skill\n---\n# Foo\nReal content"
        stub_content = (
            "---\nname: foo\ndescription: Foo skill\n---\n<!-- AUGUR-STUB — full content via MCP get-skill -->"
        )
        self._make_skill_dir(tmp_path, ".claude/skills", "foo", master_content)
        self._make_skill_dir(tmp_path, ".gemini/skills", "foo", stub_content)
        registry = FilesystemSkillRegistry(plugins_dir=tmp_path)
        # discover_all_skills filters stubs — only master remains
        mock_records = [
            _make_record("foo", "Foo skill", tmp_path / ".claude/skills/foo"),
        ]
        with patch("src.mcp.augur_shared.adapters.filesystem_registry.discover_all_skills", return_value=mock_records):
            skills = registry._scan_skills()
        foo = [s for s in skills if s.name == "foo"]
        assert len(foo) == 1
        assert ".claude" in str(foo[0].path)

    def test_adapted_copy_without_master_excluded(self, tmp_path):
        """An orphaned adapted copy (no master) is excluded entirely."""
        adapted_content = (
            "---\nname: orphan\ndescription: Orphan skill\n---\n<!-- AUGUR-ADAPTED-COPY source=claude-code -->"
        )
        self._make_skill_dir(tmp_path, ".gemini/skills", "orphan", adapted_content)
        registry = FilesystemSkillRegistry(plugins_dir=tmp_path)
        # discover_all_skills excludes orphaned adapted copies
        mock_records: list = []
        with patch("src.mcp.augur_shared.adapters.filesystem_registry.discover_all_skills", return_value=mock_records):
            skills = registry._scan_skills()
        orphan = [s for s in skills if s.name == "orphan"]
        assert len(orphan) == 0


class TestCrossClientResourceAccess:
    """Verify that the registry resolves to master skills, not stubs/adapted copies,
    so cross-client MCP resource access always returns full content."""

    def test_registry_resolves_to_master_not_stub(self, tmp_path):
        master_dir = tmp_path / "skills/apple"
        master_dir.mkdir(parents=True)
        (master_dir / "SKILL.md").write_text("---\nname: apple\ndescription: Apple\n---\n# Apple\nReal.")
        (master_dir / "scripts").mkdir()
        (master_dir / "scripts" / "run.py").write_text("print('hello')")

        stub_dir = tmp_path / ".gemini/skills/apple"
        stub_dir.mkdir(parents=True)
        (stub_dir / "SKILL.md").write_text("---\nname: apple\n---\n<!-- AUGUR-STUB -->")

        registry = FilesystemSkillRegistry(plugins_dir=tmp_path)
        # discover_all_skills resolves to master, not stub
        mock_records = [
            _make_record("apple", "Apple", master_dir),
        ]
        with patch("src.mcp.augur_shared.adapters.filesystem_registry.discover_all_skills", return_value=mock_records):
            skills = registry._scan_skills()

        apple = [s for s in skills if s.name == "apple"]
        assert len(apple) == 1
        assert (apple[0].path / "scripts" / "run.py").exists()
