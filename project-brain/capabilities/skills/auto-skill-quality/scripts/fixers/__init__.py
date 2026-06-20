"""Skill quality fixers — one module per quality dimension.

Each fixer exposes a single entry function:
  fix_instruction(skill_name, skill_dir, signals, ctx_info) -> list[str]
  fix_product(skill_name, skill_dir, signals, ctx_info)     -> list[str]
  fix_ui(skill_name, skill_dir, signals, ctx_info)          -> list[str]
  fix_wiring(skill_name, skill_dir, signals, ctx_info)      -> list[str]

Also exports:
  read_skill_context(skill_name, skill_dir) -> dict
  generate_seed_evals(skill_path, fm)       -> dict
"""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter

from .git_safety import git_commit, git_revert, is_blacklisted, record_revert, verify_build
from .instruction import fix_instruction
from .llm_escalation import llm_fix
from .product import fix_product, generate_seed_evals
from .ui import fix_ui
from .wiring import fix_wiring


def read_skill_context(skill_name: str, skill_dir: Path) -> dict:
    """Read skill context for user-journey-aware fixes."""
    context: dict = {"name": skill_name, "hub": "system", "purpose": "", "has_pages": False}

    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        try:
            fm, body = parse_frontmatter(skill_md)
            context["fm"] = fm
            context["body"] = body
            # Hub can be in x-augur-hub (top-level) or x-augur-config.hub
            context["hub"] = fm.get("x-augur-hub") or (fm.get("x-augur-config") or {}).get("hub", "system")
            context["purpose"] = fm.get("description", "")
            pages = ((fm.get("x-augur-config") or {}).get("contributions") or {}).get("pages") or []
            context["has_pages"] = len(pages) > 0
            context["pages"] = pages
        except Exception:
            context["fm"] = {}
            context["body"] = ""

    # Check what directories exist
    context["has_data"] = (skill_dir / "data").is_dir()
    context["has_scripts"] = (skill_dir / "scripts").is_dir()
    context["has_references"] = (skill_dir / "references").is_dir()
    context["has_augur"] = (skill_dir / "augur").is_dir()
    context["has_seed"] = (skill_dir / "augur" / "seed").is_dir()

    return context


__all__ = [
    "fix_instruction",
    "fix_product",
    "fix_ui",
    "fix_wiring",
    "generate_seed_evals",
    "git_commit",
    "git_revert",
    "is_blacklisted",
    "llm_fix",
    "read_skill_context",
    "record_revert",
    "verify_build",
]
