"""Tests for augur/lib/discovery.py — project asset discovery utilities.

Validates skill scanning, workflow scanning, frontmatter parsing, and
distributed command discovery.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
AI_BRIDGE_AUGUR = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(AI_BRIDGE_AUGUR) not in sys.path:
    sys.path.insert(0, str(AI_BRIDGE_AUGUR))

from src.lib.ai.discovery import (
    find_project_root,
    scan_skills,
    scan_workflows,
    strip_yaml_frontmatter,
    parse_frontmatter,
    clear_frontmatter_cache,
    extract_workflow_description_from_content,
    _extract_skill_description,
)


# ---------------------------------------------------------------------------
# find_project_root
# ---------------------------------------------------------------------------


class TestFindProjectRoot:
    def test_finds_root_with_git(self, tmp_path: Path):
        (tmp_path / ".git").mkdir()
        result = find_project_root(start=tmp_path)
        assert result == tmp_path

    def test_finds_root_with_pyproject(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[tool.poetry]", encoding="utf-8")
        result = find_project_root(start=tmp_path)
        assert result == tmp_path

    def test_raises_when_no_marker(self, tmp_path: Path):
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        with pytest.raises(FileNotFoundError):
            find_project_root(start=nested, markers=["NONEXISTENT_MARKER"])

    def test_custom_markers(self, tmp_path: Path):
        (tmp_path / "MY_MARKER").write_text("", encoding="utf-8")
        result = find_project_root(start=tmp_path, markers=["MY_MARKER"])
        assert result == tmp_path


# ---------------------------------------------------------------------------
# scan_skills
# ---------------------------------------------------------------------------


class TestScanSkills:
    def test_no_skills_dir_returns_empty(self, tmp_path: Path):
        result = scan_skills(tmp_path)
        assert result == []

    def test_discovers_skills_with_skill_md(self, tmp_path: Path):
        skill = tmp_path / "project-brain" / "capabilities" / "skills" / "my-skill"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\ndescription: My skill\n---\n# My Skill", encoding="utf-8"
        )

        clear_frontmatter_cache()
        result = scan_skills(tmp_path)
        assert len(result) == 1
        assert result[0]["name"] == "my-skill"
        # ADR-802 removed the hub-driven category; it is always "uncategorized".
        assert result[0]["category"] == "uncategorized"

    def test_category_defaults_to_uncategorized(self, tmp_path: Path):
        skill = tmp_path / "project-brain" / "capabilities" / "skills" / "bare-skill"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# Bare Skill", encoding="utf-8")

        clear_frontmatter_cache()
        result = scan_skills(tmp_path)
        assert len(result) == 1
        assert result[0]["category"] == "uncategorized"

    def test_ignores_skills_without_skill_md(self, tmp_path: Path):
        skill = tmp_path / "project-brain" / "capabilities" / "skills" / "incomplete"
        skill.mkdir(parents=True)

        result = scan_skills(tmp_path)
        assert result == []

    def test_sorts_by_category_then_name(self, tmp_path: Path):
        for hub, name in [("dev", "zed"), ("ai", "alpha"), ("dev", "beta")]:
            skill = tmp_path / "project-brain" / "capabilities" / "skills" / name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                f"---\nx-augur-hub: {hub}\n---\n# {name}", encoding="utf-8"
            )

        clear_frontmatter_cache()
        result = scan_skills(tmp_path)
        names = [s["name"] for s in result]
        assert names == ["alpha", "beta", "zed"]


# ---------------------------------------------------------------------------
# scan_workflows
# ---------------------------------------------------------------------------


class TestScanWorkflows:
    def test_no_dir_returns_empty(self, tmp_path: Path):
        result = scan_workflows(tmp_path / "nonexistent")
        assert result == []

    def test_discovers_workflow_files(self, tmp_path: Path):
        wf_dir = tmp_path / "workflows"
        wf_dir.mkdir()
        (wf_dir / "deploy.md").write_text(
            "---\nvisibility: core\n---\n# Deploy\nDeploy to production.",
            encoding="utf-8",
        )

        result = scan_workflows(wf_dir)
        assert len(result) == 1
        assert result[0]["name"] == "deploy"


# ---------------------------------------------------------------------------
# strip_yaml_frontmatter
# ---------------------------------------------------------------------------


class TestStripYamlFrontmatter:
    def test_no_frontmatter(self):
        content = "# Hello\nWorld"
        assert strip_yaml_frontmatter(content) == content

    def test_strips_frontmatter(self):
        content = "---\ntitle: Test\n---\n# Hello\nWorld"
        result = strip_yaml_frontmatter(content)
        assert result == "# Hello\nWorld"

    def test_unclosed_frontmatter(self):
        content = "---\ntitle: Test\nNo closing marker"
        result = strip_yaml_frontmatter(content)
        assert result == content


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def setup_method(self):
        clear_frontmatter_cache()

    def test_no_frontmatter(self, tmp_path: Path):
        f = tmp_path / "test.md"
        f.write_text("# Hello\nWorld", encoding="utf-8")
        fm, content = parse_frontmatter(f)
        assert fm is None
        assert "Hello" in content

    def test_valid_frontmatter(self, tmp_path: Path):
        f = tmp_path / "test.md"
        f.write_text("---\ntitle: Test\nvisibility: core\n---\n# Content", encoding="utf-8")
        fm, content = parse_frontmatter(f)
        assert fm is not None
        assert fm["title"] == "Test"
        assert fm["visibility"] == "core"
        assert "# Content" in content

    def test_caching(self, tmp_path: Path):
        f = tmp_path / "test.md"
        f.write_text("---\ntitle: V1\n---\nBody", encoding="utf-8")
        fm1, _ = parse_frontmatter(f, use_cache=True)

        f.write_text("---\ntitle: V2\n---\nBody", encoding="utf-8")
        fm2, _ = parse_frontmatter(f, use_cache=True)

        # Cache should return V1
        assert fm2["title"] == "V1"

        # Without cache should return V2
        fm3, _ = parse_frontmatter(f, use_cache=False)
        assert fm3["title"] == "V2"


# ---------------------------------------------------------------------------
# extract_workflow_description_from_content
# ---------------------------------------------------------------------------


class TestExtractDescription:
    def test_skips_headers_and_frontmatter(self):
        content = "---\ntitle: X\n---\n# Header\n\nFirst real line here."
        result = extract_workflow_description_from_content(content)
        assert result == "First real line here."

    def test_skips_comments(self):
        content = "<!-- comment -->\n// turbo\nActual description."
        result = extract_workflow_description_from_content(content)
        assert result == "Actual description."

    def test_empty_content(self):
        result = extract_workflow_description_from_content("")
        assert result is None


# ---------------------------------------------------------------------------
# _extract_skill_description
# ---------------------------------------------------------------------------


class TestExtractSkillDescription:
    def test_from_frontmatter(self):
        content = "---\ndescription: My skill does things\n---\n# Skill"
        result = _extract_skill_description(content)
        assert result == "My skill does things"

    def test_fallback_to_content(self):
        content = "# My Skill\nThis skill processes data."
        result = _extract_skill_description(content)
        assert result == "This skill processes data."
