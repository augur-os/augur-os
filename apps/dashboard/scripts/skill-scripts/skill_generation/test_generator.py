"""
Test Generator Service

Generates test files for skills:
- conftest.py with common fixtures
- test_{skill}_smoke.py with basic validation
"""

from pathlib import Path
from typing import Optional


def generate_conftest(skill_name: str) -> str:
    """
    Generate conftest.py with common fixtures.

    Args:
        skill_name: Skill name (kebab-case)

    Returns:
        conftest.py content
    """
    return f'''"""
Pytest configuration and fixtures for {skill_name} skill tests.
"""

import pytest
from pathlib import Path


@pytest.fixture
def skill_dir():
    """Return the skill directory path."""
    return Path(__file__).parent.parent


@pytest.fixture
def skill_name():
    """Return the skill name."""
    return "{skill_name}"
'''


def generate_smoke_test(skill_name: str) -> str:
    """
    Generate smoke test file.

    Args:
        skill_name: Skill name (kebab-case)

    Returns:
        test_{skill_name}_smoke.py content
    """
    skill_display = skill_name.replace('-', ' ').title()
    return f'''"""
Smoke tests for {skill_display} skill.

These tests validate basic skill structure and configuration.
"""

import yaml
import re
from pathlib import Path
import pytest


def parse_yaml_frontmatter(content: str):
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return None, content
    
    match = re.match(r"^---\\n(.*?)\\n---\\n?(.*)", content, re.DOTALL)
    if not match:
        return None, content
    
    try:
        frontmatter = yaml.safe_load(match.group(1))
        return frontmatter, match.group(2)
    except yaml.YAMLError:
        return None, content


def test_skill_md_exists(skill_dir):
    """SKILL.md MUST exist."""
    # Check both skill-package subdirectory and root
    skill_md = skill_dir / "skill-package" / "SKILL.md"
    if not skill_md.exists():
        skill_md = skill_dir / "SKILL.md"
    assert skill_md.exists(), f"Missing SKILL.md in {{skill_dir}}"


def test_skill_md_has_frontmatter(skill_dir):
    """SKILL.md MUST have YAML frontmatter."""
    skill_md = skill_dir / "skill-package" / "SKILL.md"
    if not skill_md.exists():
        skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        pytest.skip("SKILL.md not found")
    
    content = skill_md.read_text()
    frontmatter, _ = parse_yaml_frontmatter(content)
    
    assert frontmatter is not None, "SKILL.md must have YAML frontmatter"


def test_skill_md_has_name(skill_dir, skill_name):
    """SKILL.md frontmatter MUST have 'name' field matching skill name."""
    skill_md = skill_dir / "skill-package" / "SKILL.md"
    if not skill_md.exists():
        skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        pytest.skip("SKILL.md not found")
    
    content = skill_md.read_text()
    frontmatter, _ = parse_yaml_frontmatter(content)
    
    if frontmatter is None:
        pytest.skip("No frontmatter found")
    
    assert "name" in frontmatter, "SKILL.md must have 'name' field"
    assert frontmatter["name"] == skill_name, f"SKILL.md 'name' should be '{{skill_name}}'"


def test_skill_md_has_description(skill_dir):
    """SKILL.md frontmatter MUST have 'description' field."""
    skill_md = skill_dir / "skill-package" / "SKILL.md"
    if not skill_md.exists():
        skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        pytest.skip("SKILL.md not found")
    
    content = skill_md.read_text()
    frontmatter, _ = parse_yaml_frontmatter(content)
    
    if frontmatter is None:
        pytest.skip("No frontmatter found")
    
    assert "description" in frontmatter, "SKILL.md must have 'description' field"
    assert len(frontmatter["description"]) >= 20, "Description should be at least 20 characters"


def test_version_yaml_exists(skill_dir):
    """version.yaml MUST exist."""
    # Check augur/ subdirectory (new location)
    version_file = skill_dir / "augur" / "version.yaml"
    assert version_file.exists(), f"Missing version.yaml in {{skill_dir}}"


def test_version_yaml_is_valid(skill_dir):
    """version.yaml MUST be valid YAML."""
    version_file = skill_dir / "augur" / "version.yaml"
    if not version_file.exists():
        pytest.skip("version.yaml not found")

    content = version_file.read_text()
    try:
        data = yaml.safe_load(content)
        assert data is not None, "version.yaml is empty"
    except yaml.YAMLError as e:
        pytest.fail(f"version.yaml has invalid YAML: {{e}}")


def test_version_yaml_has_required_fields(skill_dir, skill_name):
    """version.yaml MUST have required fields."""
    version_file = skill_dir / "augur" / "version.yaml"
    if not version_file.exists():
        pytest.skip("version.yaml not found")
    
    content = version_file.read_text()
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError:
        pytest.skip("Invalid YAML")
    
    assert "version" in data, "version.yaml must have 'version' field"
    assert "updated" in data, "version.yaml must have 'updated' field"
    assert "skill" in data, "version.yaml must have 'skill' field"
    assert data["skill"] == skill_name, f"version.yaml 'skill' should be '{{skill_name}}'"
    
    # Validate semver format
    version = str(data["version"])
    semver_pattern = r"^\\d+\\.\\d+\\.\\d+(-[a-zA-Z0-9.]+)?(\\+[a-zA-Z0-9.]+)?$"
    assert re.match(semver_pattern, version), f"Version '{{version}}' doesn't follow semver format"


def test_modules_directory_exists(skill_dir):
    """modules/ directory SHOULD exist if skill uses modules."""
    # Check both skill-package subdirectory and root
    modules_dir = skill_dir / "skill-package" / "modules"
    if not modules_dir.exists():
        modules_dir = skill_dir / "modules"
    # This is optional, so we just check if it exists when expected
    if modules_dir.exists():
        assert modules_dir.is_dir(), "modules should be a directory"
'''


def generate_tests(skill_dir: Path, skill_name: str) -> tuple[bool, Optional[str]]:
    """
    Generate test files for a skill.

    Args:
        skill_dir: Skill directory path
        skill_name: Skill name (kebab-case)

    Returns:
        Tuple of (success, error_message)
    """
    tests_dir = skill_dir / 'skill-package' / 'tests'

    try:
        tests_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, f"Failed to create tests directory: {e}"

    # Generate conftest.py
    conftest_path = tests_dir / 'conftest.py'
    try:
        conftest_path.write_text(generate_conftest(skill_name), encoding='utf-8')
    except Exception as e:
        return False, f"Failed to write conftest.py: {e}"

    # Generate smoke test
    smoke_test_path = tests_dir / f'test_{skill_name}_smoke.py'
    try:
        smoke_test_path.write_text(generate_smoke_test(skill_name), encoding='utf-8')
    except Exception as e:
        return False, f"Failed to write smoke test: {e}"

    return True, None
