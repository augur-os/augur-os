"""Skill analyzers using src/lib infrastructure.

These analyzers leverage:
- src/lib/skills/registry.py for skill metadata
- skill_maintenance.py patterns for health checks
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Attempt to import from src/lib infrastructure
try:
    from src.plugins.skill_discovery import SkillMetadata, resolve_skill
except ImportError:
    SkillMetadata = None  # type: ignore[misc, assignment]
    resolve_skill = None  # type: ignore[misc, assignment]


class BaseAnalyzer:
    """Base analyzer interface."""

    def __init__(self, skill_path: Path, data_path: Path) -> None:
        self.skill_path = skill_path
        self.data_path = data_path
        self.skill_name = skill_path.name
        self._metadata: SkillMetadata | None = None

    def _get_metadata(self) -> SkillMetadata | None:
        """Get skill metadata from registry."""
        if self._metadata is not None:
            return self._metadata
        if resolve_skill is None:
            return None
        self._metadata = resolve_skill(self.skill_name, include_disabled=True)
        return self._metadata

    def analyze(self) -> list[dict[str, Any]]:
        """Run analysis and return issues."""
        return []


class DataAnalyzer(BaseAnalyzer):
    """Analyze skill data layout and structure."""

    def analyze(self) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []

        # Check for scripts directory
        scripts_dir = self.skill_path / "scripts"
        if not scripts_dir.exists():
            issues.append(
                {
                    "category": "data_structure",
                    "type": "missing_scripts",
                    "severity": "medium",
                    "file": str(self.skill_path),
                    "message": "No scripts/ directory found",
                    "suggestion": "Add scripts/ directory with MCP-callable scripts",
                    "auto_fixable": False,
                }
            )
        else:
            # Check for __init__.py in scripts
            if not (scripts_dir / "__init__.py").exists():
                issues.append(
                    {
                        "category": "data_structure",
                        "type": "missing_init",
                        "severity": "low",
                        "file": str(scripts_dir),
                        "message": "scripts/ missing __init__.py",
                        "suggestion": "Add __init__.py for proper Python packaging",
                        "auto_fixable": True,
                    }
                )

            # Check script count
            py_files = list(scripts_dir.glob("*.py"))
            if len(py_files) == 0:
                issues.append(
                    {
                        "category": "data_structure",
                        "type": "empty_scripts",
                        "severity": "medium",
                        "file": str(scripts_dir),
                        "message": "scripts/ directory has no Python files",
                        "suggestion": "Add at least one MCP-callable script",
                        "auto_fixable": False,
                    }
                )

        # Check for modules directory
        modules_dir = self.skill_path / "modules"
        if modules_dir.exists():
            md_files = list(modules_dir.glob("*.md"))
            if len(md_files) == 0:
                issues.append(
                    {
                        "category": "data_structure",
                        "type": "empty_modules",
                        "severity": "low",
                        "file": str(modules_dir),
                        "message": "modules/ directory exists but has no .md files",
                        "suggestion": "Add module documentation or remove empty directory",
                        "auto_fixable": False,
                    }
                )

        # Check for references directory
        references_dir = self.skill_path / "references"
        if references_dir.exists():
            ref_files = list(references_dir.glob("*.md"))
            if len(ref_files) == 0:
                issues.append(
                    {
                        "category": "data_structure",
                        "type": "empty_references",
                        "severity": "low",
                        "file": str(references_dir),
                        "message": "references/ directory exists but has no .md files",
                        "suggestion": "Add reference documentation or remove empty directory",
                        "auto_fixable": False,
                    }
                )

        # Check for version.yaml
        if not (self.skill_path / "augur" / "version.yaml").exists():
            issues.append(
                {
                    "category": "data_structure",
                    "type": "missing_version",
                    "severity": "medium",
                    "file": str(self.skill_path),
                    "message": "Missing version.yaml",
                    "suggestion": "Add version.yaml with version tracking",
                    "auto_fixable": True,
                }
            )

        # Check data directory structure
        if self.data_path.exists():
            # Check for overly nested structures
            max_depth = 0
            for path in self.data_path.rglob("*"):
                if path.is_file():
                    depth = len(path.relative_to(self.data_path).parts)
                    max_depth = max(max_depth, depth)
            if max_depth > 5:
                issues.append(
                    {
                        "category": "data_structure",
                        "type": "deep_nesting",
                        "severity": "low",
                        "file": str(self.data_path),
                        "message": f"Data directory has deep nesting ({max_depth} levels)",
                        "suggestion": "Consider flattening directory structure",
                        "auto_fixable": False,
                    }
                )

        return issues


class DocAnalyzer(BaseAnalyzer):
    """Analyze skill documentation quality."""

    def analyze(self) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []

        skill_md = self.skill_path / "SKILL.md"
        if not skill_md.exists():
            issues.append(
                {
                    "category": "documentation",
                    "type": "missing_skill_md",
                    "severity": "critical",
                    "file": str(self.skill_path),
                    "message": "Missing SKILL.md file",
                    "suggestion": "Create SKILL.md with frontmatter and capabilities",
                    "auto_fixable": False,
                }
            )
            return issues

        content = skill_md.read_text(encoding="utf-8")
        size = len(content)

        # Check SKILL.md size
        if size < 100:
            issues.append(
                {
                    "category": "documentation",
                    "type": "skill_md_too_small",
                    "severity": "high",
                    "file": str(skill_md),
                    "message": f"SKILL.md too small ({size} bytes)",
                    "suggestion": "Add description, capabilities, and usage examples",
                    "auto_fixable": False,
                }
            )
        elif size > 20000:
            issues.append(
                {
                    "category": "documentation",
                    "type": "skill_md_too_large",
                    "severity": "medium",
                    "file": str(skill_md),
                    "message": f"SKILL.md too large ({size} bytes, ~{size // 4} tokens)",
                    "suggestion": "Move detailed docs to modules/ or references/",
                    "auto_fixable": False,
                }
            )

        # Check for frontmatter
        if not content.startswith("---"):
            issues.append(
                {
                    "category": "documentation",
                    "type": "missing_frontmatter",
                    "severity": "high",
                    "file": str(skill_md),
                    "message": "SKILL.md missing YAML frontmatter",
                    "suggestion": "Add --- delimited frontmatter with name, description, triggers",
                    "auto_fixable": False,
                }
            )
        else:
            # Check frontmatter fields
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                required_fields = ["name", "description"]
                for field in required_fields:
                    if f"{field}:" not in frontmatter:
                        issues.append(
                            {
                                "category": "documentation",
                                "type": f"missing_{field}",
                                "severity": "medium",
                                "file": str(skill_md),
                                "message": f"Frontmatter missing '{field}' field",
                                "suggestion": f"Add {field}: to SKILL.md frontmatter",
                                "auto_fixable": False,
                            }
                        )

                # Check for triggers
                if "triggers:" not in frontmatter:
                    issues.append(
                        {
                            "category": "documentation",
                            "type": "missing_triggers",
                            "severity": "low",
                            "file": str(skill_md),
                            "message": "Frontmatter missing 'triggers' field",
                            "suggestion": "Add triggers: with keywords that invoke this skill",
                            "auto_fixable": False,
                        }
                    )

        # Check for Capabilities section
        if "## Capabilities" not in content and "## capabilities" not in content.lower():
            issues.append(
                {
                    "category": "documentation",
                    "type": "missing_capabilities_section",
                    "severity": "medium",
                    "file": str(skill_md),
                    "message": "SKILL.md missing '## Capabilities' section",
                    "suggestion": "Add capabilities section listing what the skill can do",
                    "auto_fixable": False,
                }
            )

        # Check for README
        readme = self.skill_path / "README.md"
        if not readme.exists():
            issues.append(
                {
                    "category": "documentation",
                    "type": "missing_readme",
                    "severity": "low",
                    "file": str(self.skill_path),
                    "message": "No README.md for developer documentation",
                    "suggestion": "Add README.md with setup instructions and examples",
                    "auto_fixable": False,
                }
            )

        return issues


class TestAnalyzer(BaseAnalyzer):
    """Analyze skill test coverage."""

    def analyze(self) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []

        # Check for tests directory
        tests_dir = self.skill_path / "tests"
        if not tests_dir.exists():
            # Also check _dev/tests pattern
            dev_tests = self.skill_path / "_dev" / "tests"
            if not dev_tests.exists():
                issues.append(
                    {
                        "category": "tests",
                        "type": "missing_tests_dir",
                        "severity": "medium",
                        "file": str(self.skill_path),
                        "message": "No tests/ directory found",
                        "suggestion": "Add tests/ directory with pytest tests",
                        "auto_fixable": False,
                    }
                )
                return issues
            else:
                tests_dir = dev_tests

        # Check for test files
        test_files = list(tests_dir.glob("test_*.py")) + list(tests_dir.glob("*_test.py"))
        if len(test_files) == 0:
            issues.append(
                {
                    "category": "tests",
                    "type": "no_test_files",
                    "severity": "medium",
                    "file": str(tests_dir),
                    "message": "tests/ directory has no test files",
                    "suggestion": "Add test_*.py files with pytest tests",
                    "auto_fixable": False,
                }
            )
            return issues

        # Check test coverage by comparing to scripts
        scripts_dir = self.skill_path / "scripts"
        if scripts_dir.exists():
            script_files = [f.stem for f in scripts_dir.glob("*.py") if f.stem != "__init__"]
            tested_scripts: set[str] = set()

            for test_file in test_files:
                content = test_file.read_text(encoding="utf-8")
                for script in script_files:
                    # Look for imports or references to the script
                    if script in content or script.replace("_", " ") in content:
                        tested_scripts.add(script)

            untested = set(script_files) - tested_scripts
            if untested and len(untested) < len(script_files):
                for script in untested:
                    issues.append(
                        {
                            "category": "tests",
                            "type": "untested_script",
                            "severity": "low",
                            "file": str(scripts_dir / f"{script}.py"),
                            "message": f"Script '{script}.py' appears untested",
                            "suggestion": f"Add test__{script}.py with tests for this script",
                            "auto_fixable": False,
                        }
                    )

        # Check for conftest.py
        if not (tests_dir / "conftest.py").exists():
            issues.append(
                {
                    "category": "tests",
                    "type": "missing_conftest",
                    "severity": "info",
                    "file": str(tests_dir),
                    "message": "No conftest.py for src/lib fixtures",
                    "suggestion": "Add conftest.py if tests need src/lib fixtures",
                    "auto_fixable": False,
                }
            )

        # Check for pytest.ini or pyproject.toml test config
        has_config = (
            (self.skill_path / "pytest.ini").exists()
            or (self.skill_path / "pyproject.toml").exists()
            or (self.skill_path / "_dev" / "pytest.ini").exists()
        )
        if not has_config:
            issues.append(
                {
                    "category": "tests",
                    "type": "missing_test_config",
                    "severity": "info",
                    "file": str(self.skill_path),
                    "message": "No pytest configuration found",
                    "suggestion": "Add pytest.ini or pyproject.toml with [tool.pytest] section",
                    "auto_fixable": False,
                }
            )

        return issues
