"""Auto-generated importability test for tools_voice_profile."""
from __future__ import annotations

import sys
from pathlib import Path

import importlib
import importlib.util

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MCP_SRC = PROJECT_ROOT / "src" / "mcp"
if str(MCP_SRC) not in sys.path:
    sys.path.insert(0, str(MCP_SRC))


def test_tools_voice_profile_importable():
    """Verify that tools_voice_profile can be imported without errors."""
    package_name = "knowledge_mcp_testpkg"
    package_dir = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "knowledge" / "scripts" / "mcp"

    if package_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            package_name,
            package_dir / "__init__.py",
            submodule_search_locations=[str(package_dir)],
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[package_name] = module
        spec.loader.exec_module(module)

    mod = importlib.import_module(f"{package_name}.tools_voice_profile")
    assert mod is not None
