"""Importability test for apps/dashboard/scripts/skill-scripts/skill_generation/mcp_generator.py (auto-generated)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = PROJECT_ROOT / "apps/dashboard/scripts/skill-scripts/skill_generation/mcp_generator.py"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_module(module_path):
    """Load the target module, supporting relative imports if it lives in a package
    and bare imports of sibling modules under skill-scripts/."""
    # Make sibling modules resolvable for `from sibling import X` lookups.
    skill_scripts_root = module_path
    while skill_scripts_root.name != "skill-scripts" and skill_scripts_root.parent != skill_scripts_root:
        skill_scripts_root = skill_scripts_root.parent
    if skill_scripts_root.name == "skill-scripts" and str(skill_scripts_root) not in sys.path:
        sys.path.insert(0, str(skill_scripts_root))
    if str(module_path.parent) not in sys.path:
        sys.path.insert(0, str(module_path.parent))

    parent = module_path.parent
    init = parent / "__init__.py"
    if init.exists():
        # Parent is a real Python package — load it FIRST so relative imports resolve.
        package_name = "dashboard_skill_scripts_" + parent.name.replace("-", "_")
        if package_name not in sys.modules:
            pkg_spec = importlib.util.spec_from_file_location(
                package_name, init, submodule_search_locations=[str(parent)]
            )
            pkg = importlib.util.module_from_spec(pkg_spec)
            sys.modules[package_name] = pkg
            pkg_spec.loader.exec_module(pkg)
        mod_full_name = package_name + "." + module_path.stem
        spec = importlib.util.spec_from_file_location(mod_full_name, module_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_full_name] = mod
        spec.loader.exec_module(mod)
        return mod
    # Standalone module — direct load.
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_path.stem] = mod
    spec.loader.exec_module(mod)
    return mod


def test_mcp_generator_importable():
    """Verify that mcp_generator can be imported without errors."""
    assert MODULE_PATH.exists(), f"{MODULE_PATH} not found"
    mod = _load_module(MODULE_PATH)
    assert mod is not None
