"""Auto-generated importability test for harness."""

from __future__ import annotations

import sys
import site
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _prefer_installed_mcp() -> None:
    """Ensure the pip MCP package wins over local skill script folders."""
    search_roots = [path for path in site.getsitepackages() if path]
    user_site = site.getusersitepackages()
    if user_site:
        search_roots.append(user_site)

    for root in reversed(search_roots):
        if root in sys.path:
            sys.path.remove(root)
        sys.path.insert(0, root)

    current = sys.modules.get("mcp")
    current_file = Path(getattr(current, "__file__", "")) if current else None
    if current_file and "site-packages" not in str(current_file):
        for module_name in list(sys.modules):
            if module_name == "mcp" or module_name.startswith("mcp."):
                sys.modules.pop(module_name, None)


def test_harness_importable():
    """Verify that harness can be imported without errors."""
    _prefer_installed_mcp()
    import src.mcp.augur_framework.tools.infrastructure.harness

    assert src.mcp.augur_framework.tools.infrastructure.harness is not None
