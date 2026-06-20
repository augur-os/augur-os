"""Tests for apps/dashboard/scripts/skill-scripts/skill_generation/validation_service.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load module via importlib (directory has hyphens). File lives at
# apps/dashboard/scripts/skill-scripts/skill_generation/validation_service.py — this
# test sits at tests/dashboard/python/test_validation_service.py so parents[3] is
# the project root.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_MODULE_PATH = (
    _REPO_ROOT / "apps" / "dashboard" / "scripts" / "skill-scripts" / "skill_generation" / "validation_service.py"
)

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_spec = importlib.util.spec_from_file_location("validation_service", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

validate_skill_name = _mod.validate_skill_name
validate_skill_md = _mod.validate_skill_md
validate_skill_structure = _mod.validate_skill_structure
validate_version_yaml = _mod.validate_version_yaml
validate_skill = _mod.validate_skill


# ---------------------------------------------------------------------------
# validate_skill_name
# ---------------------------------------------------------------------------


class TestValidateSkillName:
    def test_valid_name(self):
        is_valid, errors = validate_skill_name("my-skill")
        assert is_valid is True
        assert errors == []

    def test_valid_single_word(self):
        is_valid, errors = validate_skill_name("skill")
        assert is_valid is True

    def test_valid_with_numbers(self):
        is_valid, errors = validate_skill_name("skill-v2")
        assert is_valid is True

    def test_empty_name(self):
        is_valid, errors = validate_skill_name("")
        assert is_valid is False
        assert any("empty" in e.lower() for e in errors)

    def test_uppercase_rejected(self):
        is_valid, errors = validate_skill_name("MySkill")
        assert is_valid is False

    def test_consecutive_hyphens_rejected(self):
        is_valid, errors = validate_skill_name("my--skill")
        assert is_valid is False

    def test_starts_with_hyphen_rejected(self):
        is_valid, errors = validate_skill_name("-skill")
        assert is_valid is False

    def test_ends_with_hyphen_rejected(self):
        is_valid, errors = validate_skill_name("skill-")
        assert is_valid is False

    def test_starts_with_number_rejected(self):
        is_valid, errors = validate_skill_name("2cool")
        assert is_valid is False


# ---------------------------------------------------------------------------
# validate_skill_md
# ---------------------------------------------------------------------------


class TestValidateSkillMd:
    def _write_skill_md(self, path: Path, content: str):
        path.write_text(content, encoding="utf-8")

    def test_valid_skill_md(self, tmp_path):
        md = tmp_path / "SKILL.md"
        self._write_skill_md(
            md, "---\nname: my-skill\ndescription: A comprehensive skill for testing things out\n---\n# My Skill\n"
        )
        is_valid, errors, warnings = validate_skill_md(md)
        assert is_valid is True
        assert errors == []

    def test_missing_frontmatter(self, tmp_path):
        md = tmp_path / "SKILL.md"
        self._write_skill_md(md, "# No frontmatter\n")
        is_valid, errors, warnings = validate_skill_md(md)
        assert is_valid is False
        assert any("frontmatter" in e.lower() for e in errors)

    def test_missing_name_field(self, tmp_path):
        md = tmp_path / "SKILL.md"
        self._write_skill_md(md, "---\ndescription: A comprehensive skill for testing things out\n---\n# Skill\n")
        is_valid, errors, warnings = validate_skill_md(md)
        assert is_valid is False
        assert any("name" in e.lower() for e in errors)

    def test_missing_description_field(self, tmp_path):
        md = tmp_path / "SKILL.md"
        self._write_skill_md(md, "---\nname: my-skill\n---\n# Skill\n")
        is_valid, errors, warnings = validate_skill_md(md)
        assert is_valid is False
        assert any("description" in e.lower() for e in errors)

    def test_short_description_warns(self, tmp_path):
        md = tmp_path / "SKILL.md"
        self._write_skill_md(md, "---\nname: my-skill\ndescription: Short\n---\n# Skill\n")
        is_valid, errors, warnings = validate_skill_md(md)
        assert any("20 char" in w.lower() for w in warnings)


# ---------------------------------------------------------------------------
# validate_version_yaml
# ---------------------------------------------------------------------------


class TestValidateVersionYaml:
    def test_valid_version(self, tmp_path):
        vy = tmp_path / "version.yaml"
        vy.write_text("version: 1.0.0\nupdated: 2025-01-01\nskill: my-skill\n")
        is_valid, errors = validate_version_yaml(vy)
        assert is_valid is True
        assert errors == []

    def test_missing_version_field(self, tmp_path):
        vy = tmp_path / "version.yaml"
        vy.write_text("updated: 2025-01-01\nskill: my-skill\n")
        is_valid, errors = validate_version_yaml(vy)
        assert is_valid is False
        assert any("version" in e.lower() for e in errors)

    def test_invalid_semver(self, tmp_path):
        vy = tmp_path / "version.yaml"
        vy.write_text("version: abc\nupdated: 2025-01-01\nskill: my-skill\n")
        is_valid, errors = validate_version_yaml(vy)
        assert is_valid is False
        assert any("semver" in e.lower() for e in errors)

    def test_empty_file(self, tmp_path):
        vy = tmp_path / "version.yaml"
        vy.write_text("")
        is_valid, errors = validate_version_yaml(vy)
        assert is_valid is False


# ---------------------------------------------------------------------------
# validate_skill_structure
# ---------------------------------------------------------------------------


class TestValidateSkillStructure:
    def test_nonexistent_dir(self, tmp_path):
        is_valid, errors, warnings = validate_skill_structure(tmp_path / "nope")
        assert is_valid is False

    def test_missing_skill_md(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        is_valid, errors, warnings = validate_skill_structure(skill_dir)
        assert is_valid is False
        assert any("SKILL.md" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_skill (comprehensive)
# ---------------------------------------------------------------------------


class TestValidateSkill:
    def test_returns_dict_with_status(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        result = validate_skill(skill_dir)
        assert "validation_status" in result
        assert "errors" in result
        assert "warnings" in result
        assert result["skill_name"] == "my-skill"

    def test_failed_status_on_missing_files(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        result = validate_skill(skill_dir)
        assert result["validation_status"] == "failed"
