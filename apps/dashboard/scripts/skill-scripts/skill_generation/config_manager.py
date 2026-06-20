"""
Configuration Manager Service

Manages skill configuration files (config.yaml, version.yaml, etc.)
"""

import yaml
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Dict


def create_config(
    skill_dir: Path,
    skill_name: str,
    layer: str,
    rag_project_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> tuple[bool, Optional[str]]:
    """
    Create skill configuration files.

    Args:
        skill_dir: Skill directory path
        skill_name: Skill name (kebab-case)
        layer: Layer (factory, horizontal, vertical)
        rag_project_id: Optional RAG project ID
        metadata: Optional additional metadata

    Returns:
        Tuple of (success, error_message)
    """
    # Create version.yaml
    version_yaml = {
        'version': '1.0.0',
        'updated': datetime.now().strftime('%Y-%m-%d'),
        'skill': skill_name,
        'codename': 'Initial Release',
    }

    version_path = skill_dir / 'augur' / 'version.yaml'
    try:
        version_path.parent.mkdir(parents=True, exist_ok=True)
        with open(version_path, 'w', encoding='utf-8') as f:
            yaml.dump(version_yaml, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        return False, f"Failed to create version.yaml: {e}"

    # Create config.yaml if needed
    config_path = skill_dir / 'config' / 'config.yaml'
    if config_path.parent.exists() or rag_project_id or metadata:
        config_data = {
            'skill': skill_name,
            'layer': layer,
        }

        if rag_project_id:
            config_data['rag'] = {
                'project_id': rag_project_id,
            }

        if metadata:
            config_data.update(metadata)

        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            return False, f"Failed to create config.yaml: {e}"

    return True, None


def update_config(skill_dir: Path, updates: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Update skill configuration.

    Args:
        skill_dir: Skill directory path
        updates: Dictionary of updates to apply

    Returns:
        Tuple of (success, error_message)
    """
    config_path = skill_dir / 'config' / 'config.yaml'

    # Load existing config or create new
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
        except Exception as e:
            return False, f"Failed to read config.yaml: {e}"
    else:
        config_data = {}

    # Apply updates
    config_data.update(updates)

    # Write back
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        return False, f"Failed to write config.yaml: {e}"

    return True, None


def get_config(skill_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Get skill configuration.

    Args:
        skill_dir: Skill directory path

    Returns:
        Configuration dict or None if not found
    """
    config_path = skill_dir / 'config' / 'config.yaml'

    if not config_path.exists():
        return None

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception:
        return None
