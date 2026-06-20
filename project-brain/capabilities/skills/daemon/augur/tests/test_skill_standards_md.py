"""Tests for auto-skill-md auto-command."""
import importlib.util
from pathlib import Path

import pytest

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "skill_standards_md.py"
SPEC = importlib.util.spec_from_file_location("skill_standards_md_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
skill_standards_md = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(skill_standards_md)


def _ctx(project_root: Path, difficulty: int = 0, dry_run: bool = False) -> OpsContext:
    return OpsContext(project_root=project_root, difficulty=difficulty, dry_run=dry_run)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _make_skill(tmp_path: Path, bundle: str, name: str, skill_md: str | None = None):
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    if skill_md is not None:
        _write(skill_dir / "SKILL.md", skill_md)
    else:
        _write(skill_dir / "scripts" / "placeholder.py", "# placeholder\n")
    return skill_dir


class TestScan:
    def test_detects_missing_skill_md(self, tmp_path: Path):
        _make_skill(tmp_path, "ai", "my-skill")
        result = skill_standards_md.scan(_ctx(tmp_path))
        assert len(result.issues) >= 1
        assert any(i["action"] == "missing-skill-md" for i in result.issues)

    def test_clean_skill_no_issues(self, tmp_path: Path):
        _make_skill(
            tmp_path, "ai", "my-skill",
            "---\nname: my-skill\ndescription: Test\n---\n\n# My Skill\n\nDoes things.\n",
        )
        result = skill_standards_md.scan(_ctx(tmp_path))
        assert len(result.issues) == 0

    def test_detects_missing_name(self, tmp_path: Path):
        _make_skill(
            tmp_path, "ai", "my-skill",
            "---\ndescription: Test\n---\n\nBody.\n",
        )
        result = skill_standards_md.scan(_ctx(tmp_path, difficulty=1))
        assert any(i["action"] == "invalid-name" for i in result.issues)

    def test_detects_name_mismatch(self, tmp_path: Path):
        _make_skill(
            tmp_path, "ai", "my-skill",
            "---\nname: wrong-name\ndescription: Test\n---\n\nBody.\n",
        )
        result = skill_standards_md.scan(_ctx(tmp_path, difficulty=1))
        assert any(i["action"] == "invalid-name" for i in result.issues)

    def test_detects_missing_description(self, tmp_path: Path):
        _make_skill(
            tmp_path, "ai", "my-skill",
            "---\nname: my-skill\n---\n\nBody.\n",
        )
        result = skill_standards_md.scan(_ctx(tmp_path, difficulty=1))
        assert any(i["action"] == "invalid-frontmatter" for i in result.issues)

    def test_detects_unknown_fields(self, tmp_path: Path):
        _make_skill(
            tmp_path, "ai", "my-skill",
            "---\nname: my-skill\ndescription: Test\nbogus: true\n---\n\nBody.\n",
        )
        result = skill_standards_md.scan(_ctx(tmp_path, difficulty=2))
        assert any(i["action"] == "invalid-frontmatter" for i in result.issues)

    def test_detects_empty_body(self, tmp_path: Path):
        _make_skill(
            tmp_path, "ai", "my-skill",
            "---\nname: my-skill\ndescription: Test\n---\n",
        )
        result = skill_standards_md.scan(_ctx(tmp_path))
        assert any(i["action"] == "empty-body" for i in result.issues)

    def test_severity_escalation(self, tmp_path: Path):
        _make_skill(tmp_path, "ai", "my-skill")
        result = skill_standards_md.scan(_ctx(tmp_path))
        assert result.severity in ("warning", "error")


class TestStandardBundleSkip:
    """Standard-skill bundles (DESCRIPTION.md + nested sub-skill SKILL.md, no
    top-level SKILL.md) must NOT produce a missing-skill-md finding."""

    def _make_bundle(self, tmp_path: Path, name: str) -> Path:
        """Build a minimal standard bundle: DESCRIPTION.md + sub/SKILL.md."""
        bundle_dir = tmp_path / "project-brain" / "capabilities" / "skills" / name
        bundle_dir.mkdir(parents=True, exist_ok=True)
        (bundle_dir / "DESCRIPTION.md").write_text(
            f"# {name}\n\nBundle description.\n"
        )
        sub_dir = bundle_dir / "sub"
        sub_dir.mkdir()
        (sub_dir / "SKILL.md").write_text(
            "---\nname: sub\ndescription: Sub-skill\n---\n\nDoes things.\n"
        )
        return bundle_dir

    def _make_leaf_no_skill_md(self, tmp_path: Path, name: str) -> Path:
        """Build a plain leaf skill dir with neither SKILL.md nor DESCRIPTION.md."""
        skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "scripts" / "placeholder.py").parent.mkdir(parents=True, exist_ok=True)
        (skill_dir / "scripts" / "placeholder.py").write_text("# placeholder\n")
        return skill_dir

    def test_bundle_not_flagged_as_missing_skill_md(self, tmp_path: Path):
        """A standard bundle with DESCRIPTION.md must not emit missing-skill-md."""
        self._make_bundle(tmp_path, "my-bundle")
        result = skill_standards_md.scan(_ctx(tmp_path))
        bundle_issues = [
            i for i in result.issues
            if i["action"] == "missing-skill-md"
            and "my-bundle" in i.get("file", "")
            and "sub" not in i.get("file", "")
        ]
        assert bundle_issues == [], (
            f"Standard bundle should NOT be flagged for missing-skill-md, got: {bundle_issues}"
        )

    def test_plain_leaf_still_flagged(self, tmp_path: Path):
        """A plain leaf dir with no SKILL.md and no DESCRIPTION.md must still be flagged."""
        self._make_leaf_no_skill_md(tmp_path, "missing-skill")
        result = skill_standards_md.scan(_ctx(tmp_path))
        flagged = [
            i for i in result.issues
            if i["action"] == "missing-skill-md" and "missing-skill" in i.get("file", "")
        ]
        assert len(flagged) >= 1, (
            "Plain leaf skill with no SKILL.md and no DESCRIPTION.md must be flagged"
        )

    def test_bundle_and_leaf_together(self, tmp_path: Path):
        """Bundle is skipped; plain leaf is flagged — both in same scan."""
        self._make_bundle(tmp_path, "my-bundle")
        self._make_leaf_no_skill_md(tmp_path, "missing-skill")
        result = skill_standards_md.scan(_ctx(tmp_path))
        bundle_issues = [
            i for i in result.issues
            if i["action"] == "missing-skill-md"
            and "my-bundle" in i.get("file", "")
            and "sub" not in i.get("file", "")
        ]
        leaf_issues = [
            i for i in result.issues
            if i["action"] == "missing-skill-md" and "missing-skill" in i.get("file", "")
        ]
        assert bundle_issues == [], f"Bundle must not be flagged, got: {bundle_issues}"
        assert len(leaf_issues) >= 1, "Plain leaf must still be flagged"


class TestFix:
    def test_generates_missing_skill_md(self, tmp_path: Path):
        _make_skill(tmp_path, "ai", "my-skill")
        scan_result = skill_standards_md.scan(_ctx(tmp_path))
        fix_result = skill_standards_md.fix(_ctx(tmp_path), scan_result.issues)
        assert fix_result.success is True
        skill_md = tmp_path / "project-brain" / "capabilities" / "skills" / "my-skill" / "SKILL.md"
        assert skill_md.exists()
        content = skill_md.read_text()
        assert "name: my-skill" in content
        assert "my-skill skill" in content

    def test_fixes_missing_name(self, tmp_path: Path):
        skill_dir = _make_skill(
            tmp_path, "ai", "my-skill",
            "---\ndescription: Test\n---\n\nBody.\n",
        )
        issues = [{"action": "invalid-name", "file": str(skill_dir.relative_to(tmp_path)), "detail": "Missing name", "fix_value": "my-skill"}]
        fix_result = skill_standards_md.fix(_ctx(tmp_path), issues)
        assert fix_result.success is True
        content = (skill_dir / "SKILL.md").read_text()
        assert "name: my-skill" in content

    def test_dry_run_no_changes(self, tmp_path: Path):
        _make_skill(tmp_path, "ai", "my-skill")
        scan_result = skill_standards_md.scan(_ctx(tmp_path))
        fix_result = skill_standards_md.fix(_ctx(tmp_path, dry_run=True), scan_result.issues)
        assert fix_result.success is True
        skill_md = tmp_path / "project-brain" / "capabilities" / "skills" / "my-skill" / "SKILL.md"
        assert not skill_md.exists()

    def test_generates_body_from_commands(self, tmp_path: Path):
        skill_dir = _make_skill(
            tmp_path, "ai", "my-skill",
        )
        cmd_dir = skill_dir / "commands"
        cmd_dir.mkdir(parents=True)
        (cmd_dir / "do-thing.md").write_text("# Do Thing\n\nThis does a thing.\n")
        scan_result = skill_standards_md.scan(_ctx(tmp_path))
        skill_standards_md.fix(_ctx(tmp_path), scan_result.issues)
        content = (skill_dir / "SKILL.md").read_text()
        assert "do-thing" in content.lower() or "Do Thing" in content
