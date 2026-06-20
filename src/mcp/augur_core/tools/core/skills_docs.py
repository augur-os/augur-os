"""
Doc/module/config skill discovery tool implementations.

Covers loading modules and references, reading skill config, and the
read/write pair for a skill's SKILL.md documentation body.
"""

import json
import shutil
from collections.abc import Callable
from pathlib import Path

from .helpers import (
    iter_override_paths,
    list_modules,
    list_references,
    safe_join,
)
from .models import (
    LoadModuleInput,
    LoadReferenceInput,
)
from .skills_common import (
    _generated_source_path,
    _get_data_dir,
    _is_generated_skill_doc,
    _strip_generated_header,
)


async def load_module_impl(
    params: LoadModuleInput,
    resolve_skill_entry: Callable,
    metrics,
) -> str:
    """Load a specific module's detailed documentation.

    Modules contain specialized workflows, formulas, and procedures.
    Only load modules when you need their specific functionality.

    Args:
        params: LoadModuleInput with skill_name and module_name
        resolve_skill_entry: Function to resolve skill by name
        metrics: MetricsTracker instance

    Returns:
        str: Module content in markdown
    """
    skill_entry = resolve_skill_entry(params.skill_name)
    if not skill_entry:
        return f"Error: Skill '{params.skill_name}' not found."

    metrics.track_tool("load_module", skill=skill_entry.name, module=params.module_name)

    data_dir = _get_data_dir()

    # Check for overrides in data repo
    for override_path in iter_override_paths(skill_entry, params.skill_name, params.module_name, data_dir):
        if override_path.exists():
            content = override_path.read_text(encoding="utf-8")
            return f"# Module: {params.module_name}\n\n<!-- Source: augur override -->\n\n{content}"

    module_path = safe_join(skill_entry.path, "modules", f"{params.module_name}.md")

    if not module_path.exists():
        available = list_modules(skill_entry.path)
        return f"Error: Module '{params.module_name}' not found.\nAvailable: {', '.join(available) or 'none'}"

    content = module_path.read_text(encoding="utf-8")
    return f"# Module: {params.module_name}\n\n{content}"


async def load_reference_impl(
    params: LoadReferenceInput,
    resolve_skill_entry: Callable,
) -> str:
    """Load reference documentation for a skill.

    References contain setup guides, examples, and background info.

    Args:
        params: LoadReferenceInput with skill_name and reference_name
        resolve_skill_entry: Function to resolve skill by name

    Returns:
        str: Reference content in markdown
    """
    skill_entry = resolve_skill_entry(params.skill_name)
    if not skill_entry:
        return f"Error: Skill '{params.skill_name}' not found."

    skill_path = skill_entry.path
    ref_path = skill_path / "references" / f"{params.reference_name}.md"

    if not ref_path.exists():
        available = list_references(skill_path)
        return f"Error: Reference '{params.reference_name}' not found.\nAvailable: {', '.join(available) or 'none'}"

    return ref_path.read_text()


async def get_config_impl(
    skill_name: str,
    resolve_skill_entry: Callable,
) -> str:
    """Get configuration file for a skill if available.

    Args:
        skill_name: Name of the skill
        resolve_skill_entry: Function to resolve skill by name

    Returns:
        str: Configuration content or error message
    """
    data_dir = _get_data_dir()
    skill_entry = resolve_skill_entry(skill_name, include_disabled=True)

    candidate_names: list[str] = []
    if skill_entry:
        candidate_names.append(skill_entry.name)
    candidate_names.append(skill_name)

    seen: set[str] = set()
    config_paths: list[Path] = []
    if skill_entry:
        config_paths.append(skill_entry.path / "config" / "config.yaml")
        config_paths.append(skill_entry.path / "config.yaml")

    for candidate in candidate_names:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        config_paths.append(data_dir / candidate / "config.yaml")
        config_paths.append(data_dir / candidate.replace("-", "/") / "config.yaml")

    for config_path in config_paths:
        if config_path.exists():
            return f"# Config: {config_path}\n\n```yaml\n{config_path.read_text()}\n```"

    return f"No configuration found for '{skill_name}'"


async def get_skill_doc_impl(
    skill_name: str,
    resolve_skill_entry: Callable,
) -> str:
    """Get SKILL.md documentation content for a skill.

    Returns the body (without frontmatter) for rendering in a MarkdownBlock.

    Args:
        skill_name: Name of the skill
        resolve_skill_entry: Function to resolve skill by name

    Returns:
        str: JSON with content field
    """
    from src.lib.frontmatter_utils import parse_frontmatter

    skill_entry = resolve_skill_entry(skill_name)
    if not skill_entry:
        return json.dumps(
            {
                "content": f"Skill '{skill_name}' not found.",
                "editable": False,
                "generated": False,
            }
        )

    skill_md = skill_entry.path / "SKILL.md"
    if not skill_md.exists():
        return json.dumps(
            {
                "content": "No documentation available.",
                "editable": False,
                "generated": False,
                "path": str(skill_md),
            }
        )

    raw_content = skill_md.read_text(encoding="utf-8")
    _fm, body = parse_frontmatter(skill_md)
    generated = _is_generated_skill_doc(skill_md, raw_content)
    content = _strip_generated_header(body) if generated else body.strip()
    payload = {
        "content": content,
        "editable": not generated,
        "generated": generated,
        "path": str(skill_md),
    }
    source_path = _generated_source_path(raw_content)
    if source_path:
        payload["source_path"] = source_path
    return json.dumps(payload)


async def update_skill_doc_impl(
    skill_name: str,
    content: str,
    resolve_skill_entry: Callable,
    *,
    create_backup: bool = True,
) -> str:
    """Update the markdown body of a skill's SKILL.md.

    Preserves existing YAML frontmatter and replaces only the markdown body.
    This is the write-side pair for ``get-skill-doc`` used by dashboard
    auto-page markdown editing.
    """
    from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter

    name = skill_name.strip()
    if not name:
        return json.dumps({"success": False, "error": "skill_name is required"})

    skill_entry = resolve_skill_entry(name)
    if not skill_entry:
        return json.dumps({"success": False, "error": f"Skill '{name}' not found."})

    skill_md = skill_entry.path / "SKILL.md"
    if not skill_md.exists():
        return json.dumps({"success": False, "error": "SKILL.md not found."})

    raw_content = skill_md.read_text(encoding="utf-8")
    if _is_generated_skill_doc(skill_md, raw_content):
        response = {
            "success": False,
            "error": "Generated skill documentation cannot be edited directly.",
            "generated": True,
            "path": str(skill_md),
        }
        source_path = _generated_source_path(raw_content)
        if source_path:
            response["source_path"] = source_path
        return json.dumps(response)

    frontmatter, _body = parse_frontmatter(skill_md, include_sidecar_config=False)
    backup_path: Path | None = None
    if create_backup:
        backup_path = skill_md.with_suffix(skill_md.suffix + ".bak")
        shutil.copy2(skill_md, backup_path)

    write_frontmatter(skill_md, frontmatter, content.rstrip() + "\n")

    return json.dumps(
        {
            "success": True,
            "path": str(skill_md),
            "backup_path": str(backup_path) if backup_path else None,
            "bytes_written": skill_md.stat().st_size,
        }
    )
