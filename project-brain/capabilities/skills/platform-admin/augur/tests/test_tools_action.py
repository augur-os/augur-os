"""Auto-generated importability test for tools_action."""
from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MCP_SRC = PROJECT_ROOT / "src" / "mcp"
if str(MCP_SRC) not in sys.path:
    sys.path.insert(0, str(MCP_SRC))


def test_tools_action_importable():
    """Verify that tools_action can be imported without errors."""
    package_name = "platform_admin_mcp_testpkg"
    package_dir = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "platform-admin" / "scripts" / "mcp"

    if "mcp.types" not in sys.modules:
        try:
            import mcp as mcp_module  # type: ignore
        except ImportError:
            mcp_module = types.ModuleType("mcp")
            sys.modules["mcp"] = mcp_module
        mcp_types = types.ModuleType("mcp.types")

        class ToolAnnotations(dict):
            pass

        mcp_types.ToolAnnotations = ToolAnnotations
        mcp_module.types = mcp_types
        sys.modules["mcp.types"] = mcp_types

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

    mod = importlib.import_module(f"{package_name}.tools_action")
    assert mod is not None


def test_shared_runner_resolves_shared_vault_script_paths(tmp_path, monkeypatch):
    """The MCP runner should execute project-brain script paths, not root skills paths."""
    package_name = "platform_admin_mcp_testpkg"
    package_dir = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "platform-admin" / "scripts" / "mcp"

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

    shared = importlib.import_module(f"{package_name}._shared")
    script = tmp_path / "project-brain" / "capabilities" / "skills" / "platform-admin" / "scripts" / "probe.py"
    script.parent.mkdir(parents=True)
    script.write_text('import json; print(json.dumps({"ok": True}))\n', encoding="utf-8")
    monkeypatch.setattr(shared, "get_project_root", lambda: tmp_path)

    result = shared._run_python_script(
        "project-brain/capabilities/skills/platform-admin/scripts/probe.py"
    )

    assert result["success"] is True
    assert result["result"] == {"ok": True}
