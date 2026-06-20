"""
Tests for skill refactor functionality.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "skill_refactor.py"
_SPEC = importlib.util.spec_from_file_location("skill_refactor_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)

analyze_skill = _MOD.analyze_skill
format_analysis_report = _MOD.format_analysis_report
create_backlog_tasks = _MOD.create_backlog_tasks


def test_analyze_nonexistent_skill():
    """Test analyzing a skill that doesn't exist."""
    result = analyze_skill("nonexistent-skill")

    assert "error" in result
    assert "not found" in result["error"].lower()
    assert "available_skills" in result


def test_iter_skill_dirs_uses_shared_vault_root(tmp_path):
    """Skill refactor inventory should read project-brain live skill sources."""
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\n---\n# Demo\n", encoding="utf-8")

    assert _MOD._iter_skill_dirs(tmp_path) == [skill_dir]


def test_create_backlog_tasks_uses_runtime_dir(tmp_path, monkeypatch):
    """Refactor backlog state should not be written under the repo root."""
    runtime_dir = tmp_path / "external-state"
    repo_root = tmp_path / "repo"
    monkeypatch.setattr(_MOD, "get_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(_MOD, "_get_project_root", lambda: repo_root)

    result = create_backlog_tasks(
        "demo",
        {
            "issues": [
                {
                    "severity": "medium",
                    "type": "missing_docs",
                    "file": "SKILL.md",
                    "message": "Missing docs",
                    "suggestion": "Add docs",
                }
            ]
        },
    )

    assert result["tasks_created"] == 1
    assert list((runtime_dir / "agent-tasks" / "backlog").glob("*.md"))
    assert not (repo_root / "runtime").exists()


def test_analyze_platform_admin():
    """Test analyzing the platform-admin skill itself."""
    result = analyze_skill("platform-admin")

    assert "error" not in result
    assert result["skill"] == "platform-admin"
    assert "total_issues" in result
    assert "severity_counts" in result
    assert "issues_by_category" in result
    assert isinstance(result["total_issues"], int)


def test_format_error_report():
    """Test formatting an error report."""
    analysis = {"error": "Skill not found", "available_skills": ["skill-1", "skill-2"]}

    report = format_analysis_report(analysis)

    assert "Error" in report
    assert "skill-1" in report
    assert "skill-2" in report


def test_format_successful_report():
    """Test formatting a successful analysis report."""
    analysis = {
        "skill": "test-skill",
        "total_issues": 2,
        "severity_counts": {"critical": 0, "high": 1, "medium": 0, "low": 1, "info": 0},
        "issues_by_category": {
            "documentation": [
                {
                    "category": "documentation",
                    "severity": "high",
                    "type": "missing_docs",
                    "file": "README.md",
                    "message": "Documentation missing",
                    "suggestion": "Add documentation",
                }
            ],
            "tests": [
                {
                    "category": "tests",
                    "severity": "low",
                    "type": "missing_test",
                    "file": "test_something.py",
                    "message": "Test missing",
                    "suggestion": "Add tests",
                }
            ],
        },
        "issues": [],
    }

    report = format_analysis_report(analysis)

    assert "test-skill" in report
    assert "Total Issues Found" in report
    assert "Documentation" in report
    assert "Tests" in report
    assert "missing_docs" in report
    assert "missing_test" in report


def test_format_clean_report():
    """Test formatting a report with no issues."""
    analysis = {
        "skill": "clean-skill",
        "total_issues": 0,
        "severity_counts": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
        "issues_by_category": {},
        "issues": [],
    }

    report = format_analysis_report(analysis)

    assert "clean-skill" in report
    assert "No issues found" in report or "looks good" in report.lower()
