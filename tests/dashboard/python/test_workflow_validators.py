"""Tests for apps/dashboard/scripts/skill-scripts/workflow/validators.py — workflow validation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Load module via importlib (directory has hyphens). File lives at
# apps/dashboard/scripts/skill-scripts/workflow/validators.py — this test sits at
# tests/dashboard/python/test_workflow_validators.py so parents[3] is the project root.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_MODULE_PATH = _REPO_ROOT / "apps" / "dashboard" / "scripts" / "skill-scripts" / "workflow" / "validators.py"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_spec = importlib.util.spec_from_file_location("validators", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
# Register in sys.modules before exec so @dataclass can resolve the module
sys.modules["validators"] = _mod
_spec.loader.exec_module(_mod)

ValidationIssue = _mod.ValidationIssue
ValidationResult = _mod.ValidationResult
validate_skill_md_layer1 = _mod.validate_skill_md_layer1
validate_augur_markers = _mod.validate_augur_markers
validate_dashboard_yaml = _mod.validate_dashboard_yaml
validate_directory_structure = _mod.validate_directory_structure


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------


class TestValidationResult:
    def test_default_is_passing(self):
        r = ValidationResult()
        assert r.passed is True
        assert r.score == 100.0
        assert r.issues == []

    def test_add_error_fails(self):
        r = ValidationResult()
        r.add_issue(ValidationIssue(rule="test", message="fail", severity="error"))
        assert r.passed is False
        assert len(r.errors) == 1
        assert r.score == 0.0

    def test_add_warning_still_passes(self):
        r = ValidationResult()
        r.add_issue(ValidationIssue(rule="test", message="warn", severity="warning"))
        assert r.passed is True
        assert len(r.warnings) == 1
        assert r.score == 100.0

    def test_to_dict(self):
        r = ValidationResult()
        r.add_issue(ValidationIssue(rule="r1", message="m1", severity="error"))
        d = r.to_dict()
        assert d["passed"] is False
        assert d["error_count"] == 1
        assert d["warning_count"] == 0
        assert len(d["issues"]) == 1

    def test_mixed_errors_and_warnings(self):
        r = ValidationResult()
        r.add_issue(ValidationIssue(rule="e1", message="err", severity="error"))
        r.add_issue(ValidationIssue(rule="w1", message="warn", severity="warning"))
        assert r.passed is False
        assert len(r.errors) == 1
        assert len(r.warnings) == 1


# ---------------------------------------------------------------------------
# validate_skill_md_layer1
# ---------------------------------------------------------------------------


class TestValidateSkillMdLayer1:
    def _write(self, path: Path, content: str):
        path.write_text(content, encoding="utf-8")

    def test_valid_skill_md(self, tmp_path):
        md = tmp_path / "SKILL.md"
        self._write(md, "---\nname: test-skill\nversion: 1.0.0\ndescription: A test skill\n---\n# Test\n")
        result = validate_skill_md_layer1(md)
        assert result.passed is True

    def test_missing_file(self, tmp_path):
        result = validate_skill_md_layer1(tmp_path / "SKILL.md")
        assert result.passed is False

    def test_no_frontmatter(self, tmp_path):
        md = tmp_path / "SKILL.md"
        self._write(md, "# Just markdown\n")
        result = validate_skill_md_layer1(md)
        assert result.passed is False

    def test_missing_required_fields(self, tmp_path):
        md = tmp_path / "SKILL.md"
        self._write(md, "---\nfoo: bar\n---\n# Test\n")
        result = validate_skill_md_layer1(md)
        assert result.passed is False
        rules = [i.rule for i in result.errors]
        assert "required_field_name" in rules
        assert "required_field_version" in rules
        assert "required_field_description" in rules

    def test_invalid_name_format(self, tmp_path):
        md = tmp_path / "SKILL.md"
        self._write(md, "---\nname: BadName\nversion: 1.0.0\ndescription: Test\n---\n# Test\n")
        result = validate_skill_md_layer1(md)
        assert any(i.rule == "name_format" for i in result.issues)


# ---------------------------------------------------------------------------
# validate_augur_markers
# ---------------------------------------------------------------------------


class TestValidateAugurMarkers:
    def test_balanced_blocks(self, tmp_path):
        md = tmp_path / "SKILL.md"
        md.write_text("---\nname: test\n# @augur-start\ncategory: dev # @augur\n# @augur-end\n---\n")
        result = validate_augur_markers(md)
        assert result.passed is True

    def test_unclosed_block(self, tmp_path):
        md = tmp_path / "SKILL.md"
        md.write_text("---\nname: test\n# @augur-start\ncategory: dev\n---\n")
        result = validate_augur_markers(md)
        assert any(i.rule == "augur_block_unclosed" for i in result.issues)

    def test_orphaned_end(self, tmp_path):
        md = tmp_path / "SKILL.md"
        md.write_text("---\nname: test\n# @augur-end\n---\n")
        result = validate_augur_markers(md)
        assert any(i.rule == "augur_block_orphan_end" for i in result.issues)

    def test_nonexistent_file(self, tmp_path):
        result = validate_augur_markers(tmp_path / "SKILL.md")
        assert result.passed is False


# ---------------------------------------------------------------------------
# validate_dashboard_yaml
# ---------------------------------------------------------------------------


class TestValidateDashboardYaml:
    def _write_yaml(self, path: Path, data: dict):
        path.write_text(yaml.dump(data), encoding="utf-8")

    def test_valid_dashboard(self, tmp_path):
        dy = tmp_path / "dashboard.yaml"
        self._write_yaml(
            dy,
            {
                "hub": {"id": "test", "title": "Test Hub"},
                "tabs": [{"id": "overview", "default": True}],
            },
        )
        result = validate_dashboard_yaml(dy)
        assert result.passed is True

    def test_missing_file(self, tmp_path):
        result = validate_dashboard_yaml(tmp_path / "dashboard.yaml")
        assert result.passed is False

    def test_minimal_profile_skips(self, tmp_path):
        result = validate_dashboard_yaml(tmp_path / "dashboard.yaml", profile="minimal")
        assert result.passed is True

    def test_missing_hub_id(self, tmp_path):
        dy = tmp_path / "dashboard.yaml"
        self._write_yaml(dy, {"hub": {"title": "Test"}, "tabs": []})
        result = validate_dashboard_yaml(dy)
        assert any(i.rule == "hub_id_required" for i in result.issues)

    def test_first_tab_not_overview(self, tmp_path):
        dy = tmp_path / "dashboard.yaml"
        self._write_yaml(
            dy,
            {
                "hub": {"id": "test", "title": "Test"},
                "tabs": [{"id": "settings", "default": True}],
            },
        )
        result = validate_dashboard_yaml(dy)
        assert any(i.rule == "first_tab_overview" for i in result.issues)


# ---------------------------------------------------------------------------
# validate_directory_structure
# ---------------------------------------------------------------------------


class TestValidateDirectoryStructure:
    def test_minimal_with_skill_md(self, tmp_path):
        (tmp_path / "SKILL.md").write_text("---\nname: x\n---\n")
        (tmp_path / "scripts").mkdir()
        result = validate_directory_structure(tmp_path, profile="minimal")
        assert result.passed is True

    def test_missing_skill_md(self, tmp_path):
        result = validate_directory_structure(tmp_path)
        assert any(i.rule == "skill_md_exists" for i in result.issues)

    def test_standard_profile_needs_dashboard(self, tmp_path):
        (tmp_path / "SKILL.md").write_text("---\nname: x\n---\n")
        (tmp_path / "scripts").mkdir()
        result = validate_directory_structure(tmp_path, profile="standard")
        assert any("dashboard" in i.rule for i in result.issues)
