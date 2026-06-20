"""Shared test bootstrap for demo skill tests.

Mirrors the ingest skill conftest.py setup:
- pre-import the pip mcp SDK before any skill-local mcp package can shadow it
- add repo root to sys.path so `from src.X import Y` resolves
- add demo skill scripts/ to sys.path so `from <module>` works for tests
  that load demo internals
"""
from __future__ import annotations

import sys
from pathlib import Path

# Pre-import the pip mcp package before skill-local mcp dirs hit sys.path.
try:
    import mcp  # noqa: F401
    import mcp.types  # noqa: F401
    import mcp.server.fastmcp  # noqa: F401
except ImportError:
    pass

_REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Make `skills.demo.*` and `skills.ingest.*` dotted imports resolvable.
# project-brain/ is the parent of the `skills/` package directory.
_SHARED_VAULT = _REPO_ROOT / "project-brain"
if str(_SHARED_VAULT) not in sys.path:
    sys.path.insert(0, str(_SHARED_VAULT))

_DEMO_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_DEMO_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DEMO_SCRIPTS))
