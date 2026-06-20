"""
conftest.py for skills/rag/augur/tests/

Sets up the import alias so that `from plugins.ai.skills.rag.scripts.*`
resolves to `skills/rag/scripts/*` in the project tree.

The historical import path `plugins.ai.skills.rag` predates the directory
migration (ADR-512) that moved skill code to `skills/`. This conftest
bridges the gap without touching the test files.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve project root
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).parent
# skills/rag/augur/tests → skills/rag/augur → skills/rag → skills → root
_PROJ_ROOT = _THIS_DIR.parent.parent.parent.parent

if str(_PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJ_ROOT))

_RAG_ROOT = _PROJ_ROOT / "skills" / "rag"

# ---------------------------------------------------------------------------
# Virtual namespace packages for ancestor chain
# ---------------------------------------------------------------------------
# `plugins` already exists as a real namespace package pointing to plugins/.
# Python resolves dotted imports step by step:
#   plugins  → real namespace package (plugins/)
#   plugins.ai → NOT found in plugins/ → ImportError
#   plugins.ai.skills.rag.* → never reached
#
# Strategy: register stub modules for plugins.ai, plugins.ai.skills,
# plugins.ai.skills.rag, plugins.ai.skills.rag.scripts so that Python
# finds them in sys.modules and skips the directory search entirely.
# Then use a MetaPathFinder to load scripts/modules from the real path.


def _stub(name: str) -> types.ModuleType:
    """Insert a bare namespace module into sys.modules if not already present."""
    if name not in sys.modules:
        mod = types.ModuleType(name)
        mod.__path__ = []  # mark as package
        mod.__package__ = name
        sys.modules[name] = mod
    return sys.modules[name]


_stub("plugins.ai")
_stub("plugins.ai.skills")

# Register plugins.ai.skills.rag pointing at the real skill root
_rag_pkg = _stub("plugins.ai.skills.rag")
_rag_pkg.__path__ = [str(_RAG_ROOT)]
_rag_pkg.__package__ = "plugins.ai.skills.rag"

# Register scripts sub-package
_scripts_dir = _RAG_ROOT / "scripts"
_scripts_pkg = _stub("plugins.ai.skills.rag.scripts")
_scripts_pkg.__path__ = [str(_scripts_dir)]
_scripts_pkg.__package__ = "plugins.ai.skills.rag.scripts"

# Register augur sub-package (for augur.tests etc.)
_augur_dir = _RAG_ROOT / "augur"
_augur_pkg = _stub("plugins.ai.skills.rag.augur")
_augur_pkg.__path__ = [str(_augur_dir)]
_augur_pkg.__package__ = "plugins.ai.skills.rag.augur"


# ---------------------------------------------------------------------------
# Custom MetaPathFinder: loads modules under plugins.ai.skills.rag.*
# ---------------------------------------------------------------------------

_VIRTUAL_PREFIX = "plugins.ai.skills.rag"


class _RagSkillFinder(importlib.abc.MetaPathFinder):
    """Maps `plugins.ai.skills.rag.*` module imports → real files under skills/rag/."""

    def find_spec(self, fullname: str, path, target=None):
        if fullname == _VIRTUAL_PREFIX or fullname.startswith(_VIRTUAL_PREFIX + "."):
            # If already registered as a stub, let sys.modules handle it
            if fullname in sys.modules:
                return None
        else:
            return None

        # Compute relative path inside _RAG_ROOT
        suffix = fullname[len(_VIRTUAL_PREFIX):]  # e.g. ".scripts.retrieval"
        rel_parts = suffix.lstrip(".").split(".") if suffix.strip(".") else []

        if not rel_parts:
            # Root package spec
            spec = importlib.machinery.ModuleSpec(_VIRTUAL_PREFIX, None, is_package=True)
            spec.submodule_search_locations = [str(_RAG_ROOT)]
            return spec

        candidate_file = _RAG_ROOT.joinpath(*rel_parts).with_suffix(".py")
        candidate_pkg = _RAG_ROOT.joinpath(*rel_parts)

        if candidate_file.exists():
            return importlib.util.spec_from_file_location(fullname, candidate_file)

        init = candidate_pkg / "__init__.py"
        if init.exists():
            return importlib.util.spec_from_file_location(
                fullname,
                init,
                submodule_search_locations=[str(candidate_pkg)],
            )

        if candidate_pkg.is_dir():
            spec = importlib.machinery.ModuleSpec(fullname, None, is_package=True)
            spec.submodule_search_locations = [str(candidate_pkg)]
            return spec

        return None


if not any(isinstance(f, _RagSkillFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _RagSkillFinder())
