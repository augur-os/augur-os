"""
Shared skill generation services.

This package provides reusable services for generating Augur skills
from various input sources (form data, imported skills, document analysis).
"""

from .structure_generator import (
    generate_structure,
    validate_skill_name,
    check_skill_exists,
)
from .skill_md_generator import (
    generate_skill_md,
    generate_from_form_data,
    generate_from_rag_analysis,
    normalize_imported_skill_md,
)
from .script_generator import generate_scripts
from .test_generator import (
    generate_tests,
    generate_conftest,
    generate_smoke_test,
)
from .mcp_generator import generate_mcp_server
from .dashboard_yaml_generator import generate_dashboard_yaml
from .structure_generator import get_plugins_dir, get_layer_dir
from .validation_service import (
    validate_skill,
    validate_skill_structure,
    validate_skill_md,
    validate_mcp_tools,
)
from .config_manager import (
    create_config,
    update_config,
    get_config,
)
from .epic_generator import (
    generate_epic,
    generate_epic_content,
    generate_feature_content,
    generate_user_story_content,
    generate_data_structure_content,
)

__all__ = [
    # Structure
    'generate_structure',
    'validate_skill_name',
    'check_skill_exists',
    # SKILL.md
    'generate_skill_md',
    'generate_from_form_data',
    'generate_from_rag_analysis',
    'normalize_imported_skill_md',
    # Scripts
    'generate_scripts',
    # Tests
    'generate_tests',
    'generate_conftest',
    'generate_smoke_test',
    # MCP
    'generate_mcp_server',
    # Dashboard
    'generate_dashboard_yaml',
    # Path Configuration
    'get_plugins_dir',
    'get_layer_dir',
    # Validation
    'validate_skill',
    'validate_skill_structure',
    'validate_skill_md',
    'validate_mcp_tools',
    # Config
    'create_config',
    'update_config',
    'get_config',
    # Epic Generation
    'generate_epic',
    'generate_epic_content',
    'generate_feature_content',
    'generate_user_story_content',
    'generate_data_structure_content',
]
