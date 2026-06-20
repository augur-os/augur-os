#!/usr/bin/env python3
"""
Skill Refactor Command - MCP Script

Analyzes a skill's structure and suggests improvements.

Usage via MCP:
    skill_refactor(skill_name="job-analyzer")

Author: Claude Code
Version: 0.1.0
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Add service module directory to path for imports.
skill_root = Path(__file__).parent.parent
service_root = skill_root / "augur" / "modules" / "services" / "setup_manager"
if str(service_root) not in sys.path:
    sys.path.insert(0, str(service_root))

from analyzers import DataAnalyzer, DocAnalyzer, TestAnalyzer  # noqa: E402
from src.config.paths import get_runtime_dir  # noqa: E402


def _get_project_root() -> Path:
    """Get the project root directory."""
    start = Path(__file__).resolve()
    for parent in (start,) + tuple(start.parents):
        shared_skills = parent / "project-brain" / "capabilities" / "skills"
        if shared_skills.is_dir() and (parent / "data").is_dir():
            return parent
        if shared_skills.is_dir() and (parent / "src").is_dir():
            return parent
        if (shared_skills / "platform-admin" / "data" / "dependencies.yaml").exists():
            return parent
    for parent in (start,) + tuple(start.parents):
        if (parent / "pyproject.toml").exists() and (parent / "project-brain" / "capabilities" / "skills").is_dir():
            return parent
    return start.parents[-1]


def _iter_skill_dirs(project_root: Path) -> list[Path]:
    skill_dirs: list[Path] = []

    skills_root = project_root / "project-brain" / "capabilities" / "skills"
    if skills_root.exists():
        for skill_dir in skills_root.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                skill_dirs.append(skill_dir)

    return skill_dirs


def _skill_name_from_dir(skill_dir: Path) -> str:
    version_path = skill_dir / "augur" / "version.yaml"
    if version_path.exists():
        for line in version_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("skill:"):
                return line.split(":", 1)[1].strip().strip("'\"")
    return skill_dir.name


def _resolve_skill_path(project_root: Path, skill_name: str) -> Path | None:
    """Resolve a skill path across legacy and layered layouts."""
    for skill_dir in _iter_skill_dirs(project_root):
        if skill_dir.name == skill_name or _skill_name_from_dir(skill_dir) == skill_name:
            return skill_dir

    return None


def _list_available_skills(project_root: Path) -> list[str]:
    skills: set[str] = set()

    for skill_dir in _iter_skill_dirs(project_root):
        skill_name = _skill_name_from_dir(skill_dir)
        if skill_name:
            skills.add(skill_name)

    return sorted(skills)


def _get_data_dir() -> Path:
    """Resolve the user data directory."""
    env = os.environ.get("AUGUR_ROOT")
    if env:
        return Path(env).expanduser().resolve()

    # Try to import from src/lib config
    try:
        project_root = _get_project_root()
        sys.path.insert(0, str(project_root))
        from src.config.paths import get_project_root

        return get_project_root()
    except (ImportError, ModuleNotFoundError):
        pass

    # Fallback to monorepo data directory when config import is unavailable
    return (_get_project_root() / "data").resolve()


def analyze_skill(skill_name: str) -> dict[str, Any]:
    """
    Analyze a skill for refactoring opportunities.

    Args:
        skill_name: Name of the skill to analyze (e.g., "job-analyzer")

    Returns:
        Dictionary with analysis results
    """
    project_root = _get_project_root()
    skill_path = _resolve_skill_path(project_root, skill_name)
    data_path = _get_data_dir() / skill_name

    # Validate skill exists
    if not skill_path or not skill_path.exists():
        available_skills = _list_available_skills(project_root)
        return {"error": f"Skill '{skill_name}' not found", "available_skills": available_skills}

    # Run analyzers
    data_analyzer = DataAnalyzer(skill_path, data_path)
    doc_analyzer = DocAnalyzer(skill_path, data_path)
    test_analyzer = TestAnalyzer(skill_path, data_path)

    data_issues = data_analyzer.analyze()
    doc_issues = doc_analyzer.analyze()
    test_issues = test_analyzer.analyze()

    all_issues = data_issues + doc_issues + test_issues

    # Group by category
    issues_by_category = {}
    for issue in all_issues:
        category = issue.get("category", "unknown")
        if category not in issues_by_category:
            issues_by_category[category] = []
        issues_by_category[category].append(issue)

    # Count by severity
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for issue in all_issues:
        severity = issue.get("severity", "info")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

    return {
        "skill": skill_name,
        "skill_path": str(skill_path),
        "data_path": str(data_path),
        "total_issues": len(all_issues),
        "severity_counts": severity_counts,
        "issues_by_category": issues_by_category,
        "issues": all_issues,
    }


def format_analysis_report(analysis: dict[str, Any]) -> str:
    """
    Format analysis results as a readable report.

    Args:
        analysis: Analysis results from analyze_skill()

    Returns:
        Formatted markdown report
    """
    if "error" in analysis:
        return (
            f"❌ **Error**: {analysis['error']}\n\nAvailable skills: {', '.join(analysis.get('available_skills', []))}"
        )

    skill_name = analysis["skill"]
    total = analysis["total_issues"]
    severity = analysis["severity_counts"]

    # Build report
    lines = [
        f"# 🔧 Refactor Analysis: {skill_name}",
        "",
        f"**Total Issues Found**: {total}",
        "",
    ]

    # Severity breakdown
    if total > 0:
        lines.append("## Severity Breakdown")
        lines.append("")
        if severity["critical"] > 0:
            lines.append(f"- 🔴 Critical: {severity['critical']}")
        if severity["high"] > 0:
            lines.append(f"- 🟠 High: {severity['high']}")
        if severity["medium"] > 0:
            lines.append(f"- 🟡 Medium: {severity['medium']}")
        if severity["low"] > 0:
            lines.append(f"- 🔵 Low: {severity['low']}")
        if severity["info"] > 0:
            lines.append(f"- ⚪ Info: {severity['info']}")
        lines.append("")

    # Issues by category
    issues_by_cat = analysis["issues_by_category"]

    if "documentation" in issues_by_cat:
        lines.append("## 📄 Documentation")
        lines.append("")
        for issue in issues_by_cat["documentation"]:
            severity_icon = _get_severity_icon(issue["severity"])
            lines.append(f"- {severity_icon} **{issue['type']}**: {issue['message']}")
            lines.append(f"  - File: `{issue['file']}`")
            lines.append(f"  - Suggestion: {issue['suggestion']}")
        lines.append("")

    if "data_structure" in issues_by_cat:
        lines.append("## 📁 Data Structure")
        lines.append("")
        for issue in issues_by_cat["data_structure"]:
            severity_icon = _get_severity_icon(issue["severity"])
            lines.append(f"- {severity_icon} **{issue['type']}**: {issue['message']}")
            lines.append(f"  - File: `{issue['file']}`")
            lines.append(f"  - Suggestion: {issue['suggestion']}")
        lines.append("")

    if "tests" in issues_by_cat:
        lines.append("## 🧪 Tests")
        lines.append("")
        for issue in issues_by_cat["tests"]:
            severity_icon = _get_severity_icon(issue["severity"])
            lines.append(f"- {severity_icon} **{issue['type']}**: {issue['message']}")
            lines.append(f"  - File: `{issue['file']}`")
            lines.append(f"  - Suggestion: {issue['suggestion']}")
        lines.append("")

    if total == 0:
        lines.append("✅ **No issues found!** This skill looks good.")
        lines.append("")

    # Next steps
    if total > 0:
        lines.append("## 💡 Next Steps")
        lines.append("")
        lines.append("1. Review the issues above")
        lines.append("2. Prioritize by severity (critical → high → medium → low → info)")
        lines.append("3. Fix issues manually or create agent tasks for them")
        lines.append("")

    return "\n".join(lines)


def _get_severity_icon(severity: str) -> str:
    """Get emoji icon for severity level."""
    icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}
    return icons.get(severity, "⚪")


def create_backlog_tasks(skill_name: str, analysis: dict[str, Any]) -> dict[str, Any]:
    """
    Create agent-tasks in backlog from refactor analysis.

    Args:
        skill_name: Name of the skill analyzed
        analysis: Analysis results from analyze_skill()

    Returns:
        Dictionary with task creation results
    """
    if "error" in analysis:
        return {"error": "Cannot create tasks from failed analysis", "analysis_error": analysis["error"]}

    issues = analysis.get("issues", [])
    if not issues:
        return {"message": "No issues found, no tasks created", "tasks_created": 0}

    # Group issues by severity for prioritization
    severity_priority = {"critical": "high", "high": "high", "medium": "medium", "low": "low", "info": "low"}

    created_tasks = []
    errors = []
    backlog_dir = get_runtime_dir() / "agent-tasks" / "backlog"
    backlog_dir.mkdir(parents=True, exist_ok=True)

    # Only create tasks for medium+ severity issues
    for issue in issues:
        severity = issue.get("severity", "info")
        if severity in ["info"]:  # Skip info-level issues
            continue

        # Create refactor task
        objective = f"Fix {issue['type']} in {skill_name}: {issue['message']}"
        priority = severity_priority.get(severity, "low")

        try:
            task_id = f"refactor-{skill_name}-{issue['type']}-{len(created_tasks) + len(errors) + 1}"
            task_path = backlog_dir / f"{task_id}.md"
            content = f"""---
id: {task_id}
type: refactor
priority: {priority}
status: ready
skill: {skill_name}
created: {datetime.now().isoformat()}
source: skill-refactor
---

# {objective}

## Context

- **Issue Type**: {issue['type']}
- **Severity**: {severity}
- **File**: `{issue['file']}`
- **Message**: {issue['message']}
- **Suggestion**: {issue['suggestion']}
- **Auto-fixable**: {issue.get('auto_fixable', False)}

Generated from skill refactor analysis.
"""
            task_path.write_text(content, encoding="utf-8")
            created_tasks.append({"task_id": task_id, "issue": issue["type"], "severity": severity})
        except Exception as e:
            errors.append({"issue": issue["type"], "error": str(e)})

    return {
        "skill": skill_name,
        "tasks_created": len(created_tasks),
        "created_tasks": created_tasks,
        "errors": errors if errors else None,
    }


def main(params: dict = {}) -> str:
    """
    Main entry point for the MCP script.

    Args:
        params: Dictionary with:
            - skill_name: Name of skill to analyze (required)
            - format: "markdown" or "json" (default: "markdown")
            - create_tasks: If True, create backlog tasks from analysis (default: False)

    Returns:
        JSON string or formatted report
    """
    skill_name = params.get("skill_name", "")
    format_type = params.get("format", "markdown")  # "markdown" or "json"
    create_tasks_flag = params.get("create_tasks", False)

    if not skill_name:
        return json.dumps(
            {
                "error": "skill_name parameter is required",
                "usage": "skill_refactor(skill_name='job-analyzer', create_tasks=True)",
            },
            indent=2,
        )

    # Run analysis
    analysis = analyze_skill(skill_name)

    # Create backlog tasks if requested
    if create_tasks_flag and "error" not in analysis:
        task_result = create_backlog_tasks(skill_name, analysis)

        # Add task creation info to analysis
        if format_type == "json":
            analysis["backlog_tasks"] = task_result
        else:
            # Append to markdown report
            report = format_analysis_report(analysis)
            if task_result.get("tasks_created", 0) > 0:
                report += "\n## ✅ Backlog Tasks Created\n\n"
                report += f"Created **{task_result['tasks_created']} tasks** in backlog:\n\n"
                for task in task_result.get("created_tasks", []):
                    severity_icon = _get_severity_icon(task["severity"])
                    report += f"- {severity_icon} `{task['task_id']}` - {task['issue']}\n"
                report += "\nView with: `show backlog`\n"
            return report

    # Return based on format
    if format_type == "json":
        return json.dumps(analysis, indent=2)
    else:
        return format_analysis_report(analysis)


if __name__ == "__main__":
    # Test mode
    if len(sys.argv) > 1:
        result = main({"skill_name": sys.argv[1]})
        _out(result)
    else:
        _out("Usage: python skill_refactor.py <skill-name>")
        _out("Example: python skill_refactor.py job-analyzer")
