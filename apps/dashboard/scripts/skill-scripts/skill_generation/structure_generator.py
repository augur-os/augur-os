"""
Structure Generator Service

Creates skill directory structure and validates skill names.
Supports the canonical project-brain/capabilities/skills layout via environment configuration.
"""

import os
import re
from pathlib import Path
from typing import Optional


def get_plugins_dir() -> Path:
    """
    Get canonical skills directory from config or environment.

    Supports both monorepo and starter-template scenarios:
    1. AUGUR_ROOT env var - monorepo root, skills at {root}/project-brain/capabilities/skills
    2. Fallback - relative to this script (monorepo development)

    Returns:
        Path to canonical skills directory
    """
    # 1. Check AUGUR_ROOT env var (monorepo with custom root)
    if root := os.environ.get('AUGUR_ROOT'):
        return Path(root).expanduser().resolve() / 'project-brain' / 'capabilities' / 'skills'

    # 2. Fallback to relative path (monorepo development)
    return Path(__file__).resolve().parents[5] / 'project-brain' / 'capabilities' / 'skills'


def get_layer_dir(layer: str) -> Path:
    """
    Get the canonical directory for skill generation.

    Args:
        layer: Layer name (factory, horizontal, vertical)

    Returns:
        Path to the top-level skills directory
    """
    _unused_layer = layer
    return get_plugins_dir()


# Legacy constants for backwards compatibility
REPO_ROOT = Path(__file__).resolve().parents[5]
PACKAGES_DIR = REPO_ROOT / 'project-brain' / 'capabilities' / 'skills'


def validate_skill_name(name: str) -> tuple[bool, Optional[str]]:
    """
    Validate skill name format (kebab-case).

    Args:
        name: Skill name to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name or not name.strip():
        return False, "Skill name cannot be empty"

    # Reject placeholder/test names
    if name == 'new-skill':
        return False, "Skill name cannot be 'new-skill' (placeholder). Please provide a real skill name."

    # Kebab-case pattern: lowercase letters, numbers, hyphens only
    # Must start with a letter
    kebab_pattern = r'^[a-z][a-z0-9-]*$'

    if not re.match(kebab_pattern, name):
        return False, "Skill name must be kebab-case (lowercase letters, numbers, hyphens only, starting with a letter)"

    # Check for consecutive hyphens
    if '--' in name:
        return False, "Skill name cannot contain consecutive hyphens"

    # Check for leading/trailing hyphens
    if name.startswith('-') or name.endswith('-'):
        return False, "Skill name cannot start or end with a hyphen"

    return True, None


def check_skill_exists(name: str, layer: str) -> tuple[bool, Optional[Path]]:
    """
    Check if a skill with the given name already exists in the specified layer.

    Args:
        name: Skill name
        layer: Layer (factory, horizontal, vertical)

    Returns:
        Tuple of (exists, skill_path)
    """
    if layer not in ['factory', 'horizontal', 'vertical']:
        return False, None

    # Use environment-aware path resolution
    layer_dir = get_layer_dir(layer)
    skill_dir = layer_dir / name
    if skill_dir.exists():
        return True, skill_dir
    return False, None


def generate_structure(
    name: str, layer: str = 'vertical', create_subdirs: bool = True
) -> tuple[bool, Optional[Path], Optional[str]]:
    """
    Generate skill directory structure.

    Args:
        name: Skill name (kebab-case)
        layer: Layer (factory, horizontal, vertical)
        create_subdirs: Whether to create subdirectories (modules, references, etc.)

    Returns:
        Tuple of (success, skill_dir_path, error_message)
    """
    # Validate layer
    if layer not in ['factory', 'horizontal', 'vertical']:
        return False, None, f"Invalid layer: {layer}. Must be 'factory', 'horizontal', or 'vertical'"

    # Validate skill name
    is_valid, error = validate_skill_name(name)
    if not is_valid:
        return False, None, error

    # Check if skill already exists
    exists, existing_path = check_skill_exists(name, layer)
    if exists:
        return False, None, f"Skill '{name}' already exists at {existing_path}"

    # Create skill directory using environment-aware path resolution
    layer_dir = get_layer_dir(layer)
    skill_dir = layer_dir / name

    try:
        skill_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        return False, None, f"Skill directory already exists: {skill_dir}"
    except Exception as e:
        return False, None, f"Failed to create skill directory: {e}"

    # Create subdirectories if requested
    if create_subdirs:
        subdirs = [
            'skill-package',
            'skill-package/modules',
            'skill-package/references',
            'skill-package/tests',
            'scripts',
            'config',
        ]

        for subdir in subdirs:
            subdir_path = skill_dir / subdir
            try:
                subdir_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return False, skill_dir, f"Failed to create subdirectory {subdir}: {e}"

    return True, skill_dir, None
