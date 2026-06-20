"""Tests for skill analyzers."""

from pathlib import Path

from modules.services.setup_manager.analyzers import DataAnalyzer, DocAnalyzer, TestAnalyzer as SetupTestAnalyzer


def test_data_analyzer_missing_scripts(tmp_path: Path) -> None:
    """DataAnalyzer should flag missing scripts directory."""
    skill_path = tmp_path / "test-skill"
    skill_path.mkdir()
    (skill_path / "SKILL.md").write_text("# Test Skill\n")

    data_path = tmp_path / "data" / "test-skill"

    analyzer = DataAnalyzer(skill_path, data_path)
    issues = analyzer.analyze()

    assert any(i["type"] == "missing_scripts" for i in issues)


def test_data_analyzer_empty_scripts(tmp_path: Path) -> None:
    """DataAnalyzer should flag empty scripts directory."""
    skill_path = tmp_path / "test-skill"
    skill_path.mkdir()
    (skill_path / "scripts").mkdir()
    (skill_path / "SKILL.md").write_text("# Test Skill\n")

    data_path = tmp_path / "data" / "test-skill"

    analyzer = DataAnalyzer(skill_path, data_path)
    issues = analyzer.analyze()

    assert any(i["type"] == "empty_scripts" for i in issues)


def test_data_analyzer_healthy_skill(tmp_path: Path) -> None:
    """DataAnalyzer should return fewer issues for well-structured skill."""
    skill_path = tmp_path / "test-skill"
    skill_path.mkdir()
    scripts_dir = skill_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "__init__.py").write_text("")
    (scripts_dir / "main.py").write_text("def main(): pass")
    (skill_path / "augur").mkdir()
    (skill_path / "augur" / "version.yaml").write_text("version: 1.0.0")
    (skill_path / "SKILL.md").write_text("# Test Skill\n")

    data_path = tmp_path / "data" / "test-skill"

    analyzer = DataAnalyzer(skill_path, data_path)
    issues = analyzer.analyze()

    # Should have no critical/high issues
    critical_high = [i for i in issues if i["severity"] in ("critical", "high")]
    assert len(critical_high) == 0


def test_doc_analyzer_missing_skill_md(tmp_path: Path) -> None:
    """DocAnalyzer should flag missing SKILL.md."""
    skill_path = tmp_path / "test-skill"
    skill_path.mkdir()

    data_path = tmp_path / "data" / "test-skill"

    analyzer = DocAnalyzer(skill_path, data_path)
    issues = analyzer.analyze()

    assert any(i["type"] == "missing_skill_md" for i in issues)
    assert any(i["severity"] == "critical" for i in issues)


def test_doc_analyzer_small_skill_md(tmp_path: Path) -> None:
    """DocAnalyzer should flag too-small SKILL.md."""
    skill_path = tmp_path / "test-skill"
    skill_path.mkdir()
    (skill_path / "SKILL.md").write_text("# X\n")  # Very small

    data_path = tmp_path / "data" / "test-skill"

    analyzer = DocAnalyzer(skill_path, data_path)
    issues = analyzer.analyze()

    assert any(i["type"] == "skill_md_too_small" for i in issues)


def test_doc_analyzer_missing_frontmatter(tmp_path: Path) -> None:
    """DocAnalyzer should flag missing frontmatter."""
    skill_path = tmp_path / "test-skill"
    skill_path.mkdir()
    # No --- at start
    (skill_path / "SKILL.md").write_text("# Test Skill\n\nThis is a description.\n" * 10)

    data_path = tmp_path / "data" / "test-skill"

    analyzer = DocAnalyzer(skill_path, data_path)
    issues = analyzer.analyze()

    assert any(i["type"] == "missing_frontmatter" for i in issues)


def test_doc_analyzer_healthy_skill_md(tmp_path: Path) -> None:
    """DocAnalyzer should have fewer issues for well-documented skill."""
    skill_path = tmp_path / "test-skill"
    skill_path.mkdir()
    (skill_path / "SKILL.md").write_text("""---
name: test-skill
description: A test skill for unit testing
triggers:
  - test
  - analyze
---

# Test Skill

A skill for testing purposes.

## Capabilities

- Run tests
- Analyze code
- Generate reports
""")
    (skill_path / "README.md").write_text("# Test Skill\n\nDeveloper docs here.")

    data_path = tmp_path / "data" / "test-skill"

    analyzer = DocAnalyzer(skill_path, data_path)
    issues = analyzer.analyze()

    # Should have no critical/high issues
    critical_high = [i for i in issues if i["severity"] in ("critical", "high")]
    assert len(critical_high) == 0


def test_test_analyzer_missing_tests(tmp_path: Path) -> None:
    """TestAnalyzer should flag missing tests directory."""
    skill_path = tmp_path / "test-skill"
    skill_path.mkdir()
    (skill_path / "SKILL.md").write_text("# Test Skill\n")

    data_path = tmp_path / "data" / "test-skill"

    analyzer = SetupTestAnalyzer(skill_path, data_path)
    issues = analyzer.analyze()

    assert any(i["type"] == "missing_tests_dir" for i in issues)


def test_test_analyzer_empty_tests(tmp_path: Path) -> None:
    """TestAnalyzer should flag empty tests directory."""
    skill_path = tmp_path / "test-skill"
    skill_path.mkdir()
    (skill_path / "tests").mkdir()
    (skill_path / "SKILL.md").write_text("# Test Skill\n")

    data_path = tmp_path / "data" / "test-skill"

    analyzer = SetupTestAnalyzer(skill_path, data_path)
    issues = analyzer.analyze()

    assert any(i["type"] == "no_test_files" for i in issues)


def test_test_analyzer_with_tests(tmp_path: Path) -> None:
    """TestAnalyzer should have fewer issues when tests exist."""
    skill_path = tmp_path / "test-skill"
    skill_path.mkdir()
    tests_dir = skill_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_main.py").write_text("def test_example(): assert True")
    (tests_dir / "conftest.py").write_text("import pytest")
    (skill_path / "SKILL.md").write_text("# Test Skill\n")
    (skill_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")

    data_path = tmp_path / "data" / "test-skill"

    analyzer = SetupTestAnalyzer(skill_path, data_path)
    issues = analyzer.analyze()

    # Should have no medium+ issues about missing tests
    missing_tests = [i for i in issues if "missing" in i["type"] and i["severity"] in ("critical", "high", "medium")]
    assert len(missing_tests) == 0
