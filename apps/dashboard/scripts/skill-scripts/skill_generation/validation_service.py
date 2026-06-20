"""
Validation Service

Validates skill structure, SKILL.md format, MCP tools, and configuration.
"""

import re
import yaml
from pathlib import Path
from typing import Any, Optional, Dict


def validate_skill_name(name: str) -> tuple[bool, list[str]]:
    """
    Validate skill name format.

    Returns:
        Tuple of (is_valid, errors)
    """
    errors = []

    if not name or not name.strip():
        errors.append("Skill name cannot be empty")
        return False, errors

    kebab_pattern = r'^[a-z][a-z0-9-]*$'
    if not re.match(kebab_pattern, name):
        errors.append(
            "Skill name must be kebab-case (lowercase letters, numbers, hyphens only, starting with a letter)"
        )

    if '--' in name:
        errors.append("Skill name cannot contain consecutive hyphens")

    if name.startswith('-') or name.endswith('-'):
        errors.append("Skill name cannot start or end with a hyphen")

    return len(errors) == 0, errors


def validate_skill_structure(skill_dir: Path) -> tuple[bool, list[str], list[str]]:
    """
    Validate skill directory structure.

    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    errors = []
    warnings = []

    if not skill_dir.exists():
        errors.append(f"Skill directory does not exist: {skill_dir}")
        return False, errors, warnings

    # Check for SKILL.md (in skill-package or root)
    skill_md = skill_dir / 'skill-package' / 'SKILL.md'
    if not skill_md.exists():
        skill_md = skill_dir / 'SKILL.md'
    if not skill_md.exists():
        errors.append("Missing required file: SKILL.md")
    else:
        # Validate SKILL.md format
        is_valid, md_errors, md_warnings = validate_skill_md(skill_md)
        errors.extend(md_errors)
        warnings.extend(md_warnings)

    # Check for version.yaml
    version_yaml = skill_dir / 'augur' / 'version.yaml'
    if not version_yaml.exists():
        errors.append("Missing required file: version.yaml")
    else:
        # Validate version.yaml
        is_valid, yaml_errors = validate_version_yaml(version_yaml)
        errors.extend(yaml_errors)

    # Check for tests directory (optional but recommended)
    tests_dir = skill_dir / 'skill-package' / 'tests'
    if not tests_dir.exists():
        warnings.append("No tests directory found (recommended)")

    return len(errors) == 0, errors, warnings


def validate_skill_md(skill_md_path: Path) -> tuple[bool, list[str], list[str]]:
    """
    Validate SKILL.md format.

    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    errors = []
    warnings = []

    try:
        content = skill_md_path.read_text(encoding='utf-8')
    except Exception as e:
        errors.append(f"Failed to read SKILL.md: {e}")
        return False, errors, warnings

    # Check for frontmatter
    if not content.startswith("---"):
        errors.append("SKILL.md must have YAML frontmatter")
        return False, errors, warnings

    # Parse frontmatter
    match = re.match(r"^---\n(.*?)\n---\n?(.*)", content, re.DOTALL)
    if not match:
        errors.append("SKILL.md frontmatter is malformed")
        return False, errors, warnings

    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        errors.append(f"SKILL.md frontmatter has invalid YAML: {e}")
        return False, errors, warnings

    if not frontmatter:
        errors.append("SKILL.md frontmatter is empty")
        return False, errors, warnings

    # Check required fields
    if 'name' not in frontmatter:
        errors.append("SKILL.md frontmatter must have 'name' field")

    if 'description' not in frontmatter:
        errors.append("SKILL.md frontmatter must have 'description' field")
    elif len(frontmatter.get('description', '')) < 20:
        warnings.append("SKILL.md description should be at least 20 characters")

    # Check line count (should be < 100 lines)
    line_count = len(content.split('\n'))
    if line_count > 100:
        warnings.append(f"SKILL.md is {line_count} lines (recommended < 100 lines)")

    return len(errors) == 0, errors, warnings


def validate_version_yaml(version_yaml_path: Path) -> tuple[bool, list[str]]:
    """
    Validate version.yaml format.

    Returns:
        Tuple of (is_valid, errors)
    """
    errors = []

    try:
        content = version_yaml_path.read_text(encoding='utf-8')
        data = yaml.safe_load(content)
    except Exception as e:
        errors.append(f"Failed to read/parse version.yaml: {e}")
        return False, errors

    if not data:
        errors.append("version.yaml is empty")
        return False, errors

    # Check required fields
    if 'version' not in data:
        errors.append("version.yaml must have 'version' field")

    if 'updated' not in data:
        errors.append("version.yaml must have 'updated' field")

    if 'skill' not in data:
        errors.append("version.yaml must have 'skill' field")

    # Validate semver format
    if 'version' in data:
        version = str(data['version'])
        semver_pattern = r'^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?(\+[a-zA-Z0-9.]+)?$'
        if not re.match(semver_pattern, version):
            errors.append(f"Version '{version}' doesn't follow semver format")

    return len(errors) == 0, errors


def validate_mcp_tools(skill_dir: Path, pillars: Dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    """
    Validate MCP tools match Five Pillar mapping.

    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    errors = []
    warnings = []

    # Check if mcp.py exists
    mcp_file = skill_dir / 'mcp.py'
    if not mcp_file.exists():
        mcp_file = skill_dir / 'mcp_server.py'

    if not mcp_file.exists():
        # MCP file is optional, but if pillars are defined, it should exist
        relevant_pillars = [p for p, data in pillars.items() if data.get('relevance', 0) > 0.5]
        if relevant_pillars:
            warnings.append("MCP server file not found but pillars are defined")
        return True, errors, warnings

    # TODO: Parse MCP file and validate tools match pillars
    # This would require parsing Python AST or using a more sophisticated approach

    return True, errors, warnings


def validate_skill(skill_dir: Path, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Comprehensive skill validation.

    Args:
        skill_dir: Skill directory path
        config: Optional skill configuration (for pillar validation)

    Returns:
        Validation result dict with:
        - validation_status: 'passed' | 'passed_with_warnings' | 'failed'
        - errors: List of error messages
        - warnings: List of warning messages
    """
    errors = []
    warnings = []

    # Validate skill name from directory
    skill_name = skill_dir.name
    is_valid, name_errors = validate_skill_name(skill_name)
    errors.extend(name_errors)

    # Validate structure
    is_valid, struct_errors, struct_warnings = validate_skill_structure(skill_dir)
    errors.extend(struct_errors)
    warnings.extend(struct_warnings)

    # Validate MCP tools if config provided
    if config and 'pillars' in config:
        is_valid, mcp_errors, mcp_warnings = validate_mcp_tools(skill_dir, config['pillars'])
        errors.extend(mcp_errors)
        warnings.extend(mcp_warnings)

    # Determine status
    if errors:
        status = 'failed'
    elif warnings:
        status = 'passed_with_warnings'
    else:
        status = 'passed'

    return {
        'validation_status': status,
        'errors': errors,
        'warnings': warnings,
        'skill_dir': str(skill_dir),
        'skill_name': skill_name,
    }
