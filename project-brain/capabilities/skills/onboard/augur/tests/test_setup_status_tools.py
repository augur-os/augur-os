"""Auto-generated importability test for setup_status_tools."""
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


def test_setup_status_tools_importable():
    """Verify that setup_status_tools can be imported without errors."""
    package_name = "onboard_mcp_testpkg"
    package_dir = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "onboard" / "scripts" / "mcp"

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

    mod = importlib.import_module(f"{package_name}.setup_status_tools")
    assert mod is not None
