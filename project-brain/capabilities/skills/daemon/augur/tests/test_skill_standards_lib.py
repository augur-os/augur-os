"""Tests for skill_standards_lib — data types, parsing, validation, writing."""
from pathlib import Path

import pytest
import yaml

from skills.daemon.scripts.ops.skill_standards_lib import (
    SkillMdInfo,
    parse_skill_md,
    extract_command_callables,
    iter_all_skills,
    validate_name,
    validate_frontmatter,
    validate_folder_structure,
    write_skill_md,
    update_frontmatter,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class TestParseSkillMd:
    def test_parses_valid_frontmatter_and_body(self, tmp_path: Path):
        skill_dir = tmp_path / "plugins" / "ai" / "skills" / "my-skill"
        _write(
            skill_dir / "SKILL.md",
            "---\nname: my-skill\ndescription: Does things\n---\n\n# My Skill\n\nBody text here.\n",
        )
        info = parse_skill_md(skill_dir)
        assert info.exists is True
        assert info.frontmatter["name"] == "my-skill"
        assert info.frontmatter["description"] == "Does things"
        assert "Body text here." in info.body

    def test_missing_skill_md(self, tmp_path: Path):
        skill_dir = tmp_path / "plugins" / "ai" / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        info = parse_skill_md(skill_dir)
        assert info.exists is False
        assert info.frontmatter == {}
        assert info.body == ""

    def test_skill_md_without_frontmatter(self, tmp_path: Path):
        skill_dir = tmp_path / "plugins" / "ai" / "skills" / "my-skill"
        _write(skill_dir / "SKILL.md", "# Just markdown\n\nNo frontmatter.\n")
        info = parse_skill_md(skill_dir)
        assert info.exists is True
        assert info.frontmatter == {}
        assert "No frontmatter." in info.body

    def test_extracts_file_references(self, tmp_path: Path):
        skill_dir = tmp_path / "plugins" / "ai" / "skills" / "my-skill"
        _write(
            skill_dir / "SKILL.md",
            "---\nname: my-skill\ndescription: test\n---\n\nSee [ref](docs/guide.md) and [other](scripts/run.sh)\n",
        )
        info = parse_skill_md(skill_dir)
        assert "docs/guide.md" in info.file_refs
        assert "scripts/run.sh" in info.file_refs


class TestIterAllSkills:
    def test_discovers_skills(self, tmp_path: Path):
        for name in ["skill-a", "skill-b"]:
            d = tmp_path / "project-brain" / "capabilities" / "skills" / name
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Test\n---\n")
        skills = list(iter_all_skills(tmp_path))
        names = [s.name for s in skills]
        assert "skill-a" in names
        assert "skill-b" in names

    def test_skips_non_skill_dirs(self, tmp_path: Path):
        (tmp_path / "not-skills" / "foo").mkdir(parents=True)
        skills = list(iter_all_skills(tmp_path))
        assert len(skills) == 0


class TestValidateName:
    def test_valid_name(self):
        assert validate_name("my-skill", "my-skill") == []

    def test_valid_underscore_name(self):
        assert validate_name("ai", "ai") == []

    def test_missing_name(self):
        issues = validate_name(None, "my-skill")
        assert len(issues) == 1
        assert issues[0]["problem"] == "missing"

    def test_name_mismatch(self):
        issues = validate_name("other-name", "my-skill")
        assert len(issues) == 1
        assert issues[0]["problem"] == "mismatch"

    def test_invalid_chars(self):
        issues = validate_name("My_Skill", "My_Skill")
        assert len(issues) == 1
        assert issues[0]["problem"] == "invalid_chars"


class TestValidateFrontmatter:
    def test_valid_frontmatter(self):
        info = SkillMdInfo(exists=True, frontmatter={"name": "x", "description": "y"})
        assert validate_frontmatter(info) == []

    def test_missing_description(self):
        info = SkillMdInfo(exists=True, frontmatter={"name": "x"})
        issues = validate_frontmatter(info)
        assert any(i["field"] == "description" for i in issues)

    def test_unknown_field_flagged(self):
        info = SkillMdInfo(exists=True, frontmatter={"name": "x", "description": "y", "bogus": True})
        issues = validate_frontmatter(info)
        assert any(i["field"] == "bogus" for i in issues)

    def test_x_augur_fields_allowed(self):
        info = SkillMdInfo(
            exists=True,
            frontmatter={"name": "x", "description": "y", "x-augur-hub": "ai"},
        )
        assert validate_frontmatter(info) == []


class TestValidateFolderStructure:
    def test_loose_script_flagged(self, tmp_path: Path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "helper.py").write_text("# script")
        (skill_dir / "SKILL.md").write_text("---\nname: x\n---\nBody\n")
        issues = validate_folder_structure(skill_dir)
        assert any(i["problem"] == "loose_script" for i in issues)

    def test_init_py_not_flagged(self, tmp_path: Path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "__init__.py").write_text("")
        (skill_dir / "SKILL.md").write_text("---\nname: x\n---\nBody\n")
        issues = validate_folder_structure(skill_dir)
        assert not any(i["problem"] == "loose_script" for i in issues)

    def test_long_skill_md_flagged(self, tmp_path: Path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("line\n" * 600)
        issues = validate_folder_structure(skill_dir)
        assert any(i["problem"] == "too_long" for i in issues)


class TestExtractCommandCallables:
    def test_reads_inline_commands(self):
        frontmatter = {
            "x-augur-commands": [
                {"id": "auto-foo", "callable": "scripts/ops/foo.py"},
                {"id": "auto-bar"},
            ]
        }
        assert extract_command_callables(frontmatter) == {"scripts/ops/foo.py"}

    def test_reads_sidecar_config_commands(self):
        frontmatter = {
            "x-augur-config": {
                "contributions": {
                    "commands": [
                        {"id": "auto-foo", "callable": "scripts/ops/foo.py"},
                    ]
                }
            }
        }
        assert extract_command_callables(frontmatter) == {"scripts/ops/foo.py"}


class TestWriteSkillMd:
    def test_roundtrip(self, tmp_path: Path):
        path = tmp_path / "SKILL.md"
        write_skill_md(path, {"name": "test", "description": "A test"}, "# Hello\n\nWorld.")
        info = parse_skill_md(tmp_path)
        assert info.frontmatter["name"] == "test"
        assert "World." in info.body

    def test_update_frontmatter_preserves_body(self, tmp_path: Path):
        path = tmp_path / "SKILL.md"
        write_skill_md(path, {"name": "test"}, "# Body preserved")
        update_frontmatter(path, {"description": "Added"})
        info = parse_skill_md(tmp_path)
        assert info.frontmatter["description"] == "Added"
        assert "Body preserved" in info.body
