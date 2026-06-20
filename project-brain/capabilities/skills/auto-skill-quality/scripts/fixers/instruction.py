"""Instruction dimension fixer — improve SKILL.md description and body content."""
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

from src.lib.frontmatter_utils import write_frontmatter


def _normalize_text(text: str) -> str:
    """Normalize text for semantic comparison — collapse whitespace, strip."""
    return " ".join(text.split()).strip()


def fix_instruction(skill_name: str, skill_dir: Path, signals: dict, ctx_info: dict) -> list[str]:
    """Improve SKILL.md description and body content.

    Idempotent: skips if normalized content would be unchanged.
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return []

    fm = ctx_info.get("fm", {})
    body = ctx_info.get("body", "")
    changes: list[str] = []

    # 1. Expand thin description (< 20 words)
    desc = fm.get("description", "") or ""
    desc_words = len(desc.split()) if desc.strip() else 0
    if desc_words < 20:
        hub = ctx_info.get("hub", "system")
        new_desc = _generate_description(skill_name, hub, body, desc)
        new_desc_words = len(new_desc.split()) if new_desc else 0
        # Semantic diff gate: only count as a change if the normalized
        # content actually differs and word count increased
        if (
            new_desc
            and new_desc_words >= 15
            and new_desc_words > desc_words
            and _normalize_text(new_desc) != _normalize_text(desc)
        ):
            fm["description"] = new_desc
            changes.append(f"expanded description from {desc_words} to {new_desc_words} words")

    # 2. Add missing sections to thin bodies (< 20 lines)
    body_lines = len(body.strip().split("\n")) if body.strip() else 0
    if body_lines < 20:
        new_body = _expand_body(skill_name, ctx_info, body)
        new_body_lines = len(new_body.strip().split("\n")) if new_body else 0
        # Semantic diff gate: only count if normalized content differs
        if (
            new_body
            and new_body_lines > body_lines
            and _normalize_text(new_body) != _normalize_text(body)
        ):
            body = new_body
            changes.append(f"expanded body from {body_lines} to {new_body_lines} lines")

    if changes:
        write_frontmatter(skill_md, fm, body)

    return changes


def _generate_description(skill_name: str, hub: str, body: str, current_desc: str) -> str:
    """Generate a richer description based on skill context."""
    lines = body.strip().split("\n") if body.strip() else []
    headings = [line.lstrip("#").strip() for line in lines if line.startswith("#")]

    name_parts = skill_name.replace("-", " ").replace("_", " ")

    # If current desc is a placeholder, replace entirely
    if current_desc.startswith("Skill:") or len(current_desc.split()) < 3:
        base = f"{name_parts.title()} management"
    else:
        base = current_desc

    # Add hub context
    hub_context = {
        "career": "for job search and professional development",
        "health": "for personal health tracking",
        "finance": "for financial planning and budgeting",
        "admin": "for system administration and maintenance",
        "dev": "for development workflow automation",
        "ai": "for AI integration and knowledge management",
        "adaptive": "for adaptive engine and self-healing automation",
        "observability": "for system monitoring and observability",
        "productivity": "for task management and productivity",
        "lifestyle": "for personal lifestyle and wellness",
        "consulting": "for client management and consulting",
        "professional": "for professional development and business",
        "enterprise": "for enterprise integration features",
        "home": "for home automation and smart devices",
        "core": "for core system functionality",
    }
    suffix = hub_context.get(hub, "")

    # Add heading-derived capabilities
    capabilities = []
    for h in headings[:3]:
        if len(h) > 3 and h.lower() not in ("overview", "usage", "configuration", "notes"):
            capabilities.append(h.lower())

    desc = base
    if suffix and suffix not in desc:
        desc = f"{desc} {suffix}"
    if capabilities and "Covers:" not in desc:
        desc = f"{desc}. Covers: {', '.join(capabilities)}"

    # Ensure minimum length with trigger guidance
    if len(desc.split()) < 15 and "Use when" not in desc:
        desc = f"{desc}. Use when working with {name_parts} features or data."

    return desc.strip()


def _expand_body(skill_name: str, ctx_info: dict, current_body: str) -> str:
    """Expand a thin SKILL.md body with useful sections."""
    sections: list[str] = []

    # Keep existing content
    if current_body.strip():
        sections.append(current_body.strip())

    # Add overview if missing
    if "## Overview" not in current_body and "## " not in current_body:
        desc = ctx_info.get("purpose", "")
        if desc:
            sections.append(f"\n## Overview\n\n{desc}")

    # Add difficulty levels if this is an auto-command
    if skill_name.startswith("auto-") and "## Difficulty" not in current_body:
        sections.append(
            "\n## Difficulty Levels\n\n"
            "- **d0**: Surface scan — discover and count issues\n"
            "- **d1**: Content check — validate correctness\n"
            "- **d2**: Deep check — root-cause classification\n"
        )

    # Add integration section if has pages or data
    if ctx_info.get("has_pages") and "## Dashboard" not in current_body:
        sections.append(
            "\n## Dashboard\n\n"
            f"This skill contributes pages to the {ctx_info.get('hub', 'system')} hub."
        )

    if ctx_info.get("has_data") and "## Data" not in current_body:
        sections.append(
            "\n## Data\n\n"
            "Skill data stored in `data/` directory within the skill folder."
        )

    return "\n".join(sections)
