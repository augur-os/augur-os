"""
Source configuration module.

Exposes path resolution and configuration utilities.
"""

from .paths import (
    get_config_dir,
    get_compiled_wiki_dir,
    get_ide_integration_dir,
    get_ide_registry_path,
    get_logs_dir,
    get_memory_dir,
    get_project_root,
    get_runtime_wiki_dir,
    get_runtime_dir,
    get_skill_data_dir,
    get_wiki_dir,
)

__all__ = [
    # Path resolution (ADR-087)
    "get_config_dir",
    "get_compiled_wiki_dir",
    "get_ide_integration_dir",
    "get_ide_registry_path",
    "get_logs_dir",
    "get_memory_dir",
    "get_project_root",
    "get_runtime_wiki_dir",
    "get_runtime_dir",
    "get_skill_data_dir",
    "get_wiki_dir",
]
