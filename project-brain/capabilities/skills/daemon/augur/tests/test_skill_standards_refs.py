"""Tests for auto-skill-refs auto-command."""
import importlib.util
from pathlib import Path

import pytest

from src.lib.ops_protocol import OpsContext


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "skill_standards_refs.py"
SPEC = importlib.util.spec_from_file_location("skill_standards_refs_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
skill_standards_refs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(skill_standards_refs)


def _ctx(project_root: Path, difficulty: int = 0, dry_run: bool = False) -> OpsContext:
    return OpsContext(project_root=project_root, difficulty=difficulty, dry_run=dry_run)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _make_skill(tmp_path: Path, bundle: str, name: str, skill_md: str, extra_files: dict | None = None):
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    _write(skill_dir / "SKILL.md", skill_md)
    if extra_files:
        for fname, content in extra_files.items():
            _write(skill_dir / fname, content)
    return skill_dir


class TestScan:
    def test_detects_broken_reference(self, tmp_path: Path):
        _make_skill(
            tmp_path, "ai", "my-skill",
            "---\nname: my-skill\ndescription: Test\n---\n\nSee [guide](docs/guide.md)\n",
        )
        result = skill_standards_refs.scan(_ctx(tmp_path, difficulty=1))
        assert any(i["action"] == "broken-ref" for i in result.issues)

    def test_valid_reference_no_issue(self, tmp_path: Path):
        _make_skill(
            tmp_path, "ai", "my-skill",
            "---\nname: my-skill\ndescription: Test\n---\n\nSee [guide](docs/guide.md)\n",
            extra_files={"docs/guide.md": "# Guide\n"},
        )
        result = skill_standards_refs.scan(_ctx(tmp_path))
        assert not any(i["action"] == "broken-ref" for i in result.issues)

    def test_detects_loose_script_at_d1(self, tmp_path: Path):
        _make_skill(
            tmp_path, "ai", "my-skill",
            "---\nname: my-skill\ndescription: Test\n---\n\nBody.\n",
            extra_files={"helper.py": "# script\n"},
        )
        result = skill_standards_refs.scan(_ctx(tmp_path, difficulty=1))
        assert any(i["action"] == "loose-script" for i in result.issues)

    def test_detects_long_skill_md_at_d2(self, tmp_path: Path):
        _make_skill(
            tmp_path, "ai", "my-skill",
            "---\nname: my-skill\ndescription: Test\n---\n\n" + "line\n" * 600,
        )
        result = skill_standards_refs.scan(_ctx(tmp_path, difficulty=2))
        assert any(i["action"] == "skill-md-too-long" for i in result.issues)

    def test_detects_orphaned_files_at_d3(self, tmp_path: Path):
        _make_skill(
            tmp_path, "ai", "my-skill",
            "---\nname: my-skill\ndescription: Test\n---\n\nBody.\n",
            extra_files={"notes/orphan.md": "# Orphan\n"},
        )
        result = skill_standards_refs.scan(_ctx(tmp_path, difficulty=3))
        assert any(i["action"] == "orphaned-file" for i in result.issues)

    def test_skips_skills_without_skill_md(self, tmp_path: Path):
        skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "no-md"
        skill_dir.mkdir(parents=True)
        _write(skill_dir / "helper.py", "# script\n")
        result = skill_standards_refs.scan(_ctx(tmp_path, difficulty=1))
        assert len(result.issues) == 0


class TestFix:
    def test_moves_loose_script_to_scripts_dir(self, tmp_path: Path):
        skill_dir = _make_skill(
            tmp_path, "ai", "my-skill",
            "---\nname: my-skill\ndescription: Test\n---\n\nBody.\n",
            extra_files={"helper.py": "# script\n"},
        )
        scan_result = skill_standards_refs.scan(_ctx(tmp_path, difficulty=1))
        fix_result = skill_standards_refs.fix(_ctx(tmp_path), scan_result.issues)
        assert fix_result.success is True
        assert (skill_dir / "scripts" / "helper.py").exists()
        assert not (skill_dir / "helper.py").exists()

    def test_dry_run_no_changes(self, tmp_path: Path):
        skill_dir = _make_skill(
            tmp_path, "ai", "my-skill",
            "---\nname: my-skill\ndescription: Test\n---\n\nBody.\n",
            extra_files={"helper.py": "# script\n"},
        )
        scan_result = skill_standards_refs.scan(_ctx(tmp_path, difficulty=1))
        fix_result = skill_standards_refs.fix(_ctx(tmp_path, dry_run=True), scan_result.issues)
        assert (skill_dir / "helper.py").exists()
        assert not (skill_dir / "scripts" / "helper.py").exists()

    def test_broken_ref_fix_writes_posix_markdown_links(self, tmp_path: Path):
        skill_dir = _make_skill(
            tmp_path, "ai", "my-skill",
            "---\nname: my-skill\ndescription: Test\n---\n\nSee [run](assets/actions/run.md)\n",
            extra_files={"commands/run.md": "# Run\n"},
        )
        scan_result = skill_standards_refs.scan(_ctx(tmp_path, difficulty=1))
        fix_result = skill_standards_refs.fix(_ctx(tmp_path), scan_result.issues)

        assert fix_result.success is True
        content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        assert "(commands/run.md)" in content
        assert "(commands\\run.md)" not in content

    def test_broken_ref_fix_does_not_use_case_only_match(self, tmp_path: Path):
        skill_dir = _make_skill(
            tmp_path, "ai", "my-skill",
            "---\nname: my-skill\ndescription: Test\n---\n\nSee [mac](assets/MacOS/Augur)\n",
            extra_files={"augur/README.md": "# Not the app binary\n"},
        )
        scan_result = skill_standards_refs.scan(_ctx(tmp_path, difficulty=1))
        fix_result = skill_standards_refs.fix(_ctx(tmp_path), scan_result.issues)

        assert fix_result.success is True
        content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        assert "(assets/MacOS/Augur)" in content
        assert "(augur)" not in content
