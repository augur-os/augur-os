"""Shared test fixtures and path bootstrap for document-extractor tests."""
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parents[4]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Some unrelated tests install a lightweight `mcp` stub into sys.modules.
# This skill imports its local `scripts/mcp` package, so remove non-package
# stubs to keep cross-suite import order from breaking collection.
_mcp_mod = sys.modules.get("mcp")
if _mcp_mod is not None and not hasattr(_mcp_mod, "__path__"):
    sys.modules.pop("mcp", None)
    sys.modules.pop("mcp.server", None)
    sys.modules.pop("mcp.server.fastmcp", None)
