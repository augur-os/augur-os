"""
Read/list/find skill discovery tool implementations.

Covers listing skills, loading a skill overview, finding the best skill
for a query, and reporting skill health.
"""

import json
from collections.abc import Callable

from .helpers import (
    compute_trigger_score,
    list_modules,
    list_references,
)
from .models import (
    FindSkillInput,
    GetSkillInput,
    ListSkillsInput,
    ResponseFormat,
)
from .skills_common import _get_skills_dir


async def list_skills_impl(
    params: ListSkillsInput,
    skill_cache,
    metrics,
    registry_list_skills: Callable,
) -> str:
    """List all available augur skills with minimal metadata.

    Returns skill names, trigger phrases, and token estimates.
    Use this first to discover which skill to use for a task.

    Args:
        params: ListSkillsInput with format preference
        skill_cache: SkillCache instance
        metrics: MetricsTracker instance
        registry_list_skills: Function to list skills

    Returns:
        str: JSON or markdown list of available skills
    """
    metrics.track_tool("list_skills")
    skills_dir = _get_skills_dir()

    # Check cache first
    requested_ownership = params.ownership.strip().lower() if params.ownership else None
    cache_key = f"list_skills:{params.format}:{requested_ownership or 'all'}"
    cached = skill_cache.get(cache_key)
    if cached:
        return cached

    skills = []
    skills_meta = registry_list_skills(plugins_dir=skills_dir)

    # De-duplicate by ID (first wins).
    # Adapted copies are already filtered by the registry's _parse_skill().
    unique_skills = {}
    for skill in skills_meta:
        sid = str(skill.name).strip().lower()
        if sid not in unique_skills:
            unique_skills[sid] = skill

    # Sorted list of unique skills
    sorted_unique = sorted(unique_skills.values(), key=lambda s: s.name)

    # Apply ownership filter if specified
    if requested_ownership:
        sorted_unique = [
            s
            for s in sorted_unique
            if str(getattr(s, "ownership", "augur") or "augur").strip().lower() == requested_ownership
        ]

    for skill in sorted_unique:
        description = skill.description
        if len(description) > 200:
            description = description[:200] + "..."
        hub = getattr(skill, "layer", None) or getattr(skill, "hub", "unknown")
        skills.append(
            {
                "name": skill.name,
                "display_name": skill.display_name,
                "description": description,
                "triggers": list(skill.triggers),
                "capabilities": list(skill.capabilities),
                "token_estimate": skill.token_estimate,
                "has_modules": skill.has_modules,
                "has_scripts": skill.has_scripts,
                "has_references": skill.has_references,
                "hub": hub,
                "master": getattr(skill, "master", None),
                "plugin": getattr(skill, "plugin", None),
                "visibility": getattr(skill, "visibility", None),
                "group": getattr(skill, "group", None),
                "release": getattr(skill, "release", None),
                "category": getattr(skill, "category", None),
                "requires_platform": getattr(skill, "requires_platform", False),
                "source": getattr(skill, "source", "augur"),
                "ownership": getattr(skill, "ownership", "augur") or "augur",
                "upstream": getattr(skill, "upstream", {}) or {},
                "skill_type": getattr(skill, "skill_type", "") or "",
                "tags": list(getattr(skill, "tags", ()) or ()),
                "origin": getattr(skill, "origin", "") or "",
                "author": getattr(skill, "author", "") or "",
            }
        )

    if params.format == ResponseFormat.JSON:
        result = json.dumps({"skills": skills, "count": len(skills)}, indent=2)
        skill_cache.set(cache_key, result)
        return result

    # Markdown format
    lines = ["# Available Augur Skills\n"]
    for s in skills:
        lines.append(f"## {s['name']}")
        lines.append(f"**Triggers**: {', '.join(s['triggers']) if s['triggers'] else 'N/A'}")
        lines.append(f"**Tokens**: ~{s['token_estimate']}")
        if s.get('capabilities'):
            lines.append("**Capabilities**:")
            for cap in s['capabilities']:
                lines.append(f"- {cap}")
        lines.append(f"_{s['description']}_\n")

    result = "\n".join(lines)
    skill_cache.set(cache_key, result)
    return result


async def get_skill_impl(
    params: GetSkillInput,
    resolve_skill_entry: Callable,
    available_skill_ids: Callable,
    metrics,
) -> str:
    """Load a skill's SKILL.md overview and command reference.

    Returns the full skill documentation without loading modules.
    Use this to understand commands before executing actions.

    Args:
        params: GetSkillInput with skill_name and optional include_modules
        resolve_skill_entry: Function to resolve skill by name
        available_skill_ids: Function to get list of skill IDs
        metrics: MetricsTracker instance

    Returns:
        str: Skill documentation in markdown
    """
    skill_entry = resolve_skill_entry(params.skill_name)
    if not skill_entry:
        return f"Error: Skill '{params.skill_name}' not found.\nAvailable: {', '.join(available_skill_ids())}"

    metrics.track_tool("get_skill", skill=skill_entry.name)

    skill_path = skill_entry.path
    skill_file = skill_path / "SKILL.md"

    content = skill_file.read_text()

    if params.include_modules:
        modules = list_modules(skill_path)
        references = list_references(skill_path)

        content += "\n\n---\n## Available Modules\n"
        if modules:
            content += "Load these for detailed workflows:\n"
            for m in modules:
                content += f"- `{m}`\n"
        else:
            content += "_No modules available_\n"

        content += "\n## Available References\n"
        if references:
            for r in references:
                content += f"- `{r}`\n"
        else:
            content += "_No references available_\n"

    return content


async def find_skill_impl(
    params: FindSkillInput,
    skill_cache,
    metrics,
    registry_list_skills: Callable,
) -> str:
    """Find the best skill for a user query.

    Uses keyword scoring and semantic heuristics to improved discovery.
    Example: "prepare for interview" -> interview-prep (score 95)

    Args:
        params: FindSkillInput with natural language query
        skill_cache: SkillCache instance
        metrics: MetricsTracker instance
        registry_list_skills: Function to list skills

    Returns:
        str: JSON list of matching skills with scores
    """
    metrics.track_tool("find_skill")
    skills_dir = _get_skills_dir()

    # Check cache
    cache_key = f"find:{params.query}:{params.top_k}"
    cached = skill_cache.get(cache_key)
    if cached:
        return cached

    results = []
    for skill in registry_list_skills(plugins_dir=skills_dir):
        info = {
            "name": skill.name,
            "description": skill.description,
            "triggers": list(skill.triggers),
        }
        score = compute_trigger_score(params.query, info)
        if score > 0:
            results.append({"skill": skill.name, "score": score, "description": skill.description})

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    top_results = results[: params.top_k]

    output = json.dumps({"query": params.query, "matches": top_results}, indent=2)

    skill_cache.set(cache_key, output)
    return output


async def get_skill_health_impl(
    skill_name: str,
    resolve_skill_entry: Callable,
) -> str:
    """Get health status for a skill.

    Returns JSON with status, lastCheck, errors24h for the HealthBlock.

    Args:
        skill_name: Name of the skill
        resolve_skill_entry: Function to resolve skill by name

    Returns:
        str: JSON health data
    """
    from datetime import datetime, timezone

    skill_entry = resolve_skill_entry(skill_name)
    if not skill_entry:
        return json.dumps(
            {
                "status": "unknown",
                "lastCheck": datetime.now(timezone.utc).isoformat(),
                "errors24h": 0,
                "structure": {"resolved": False},
            }
        )

    skill_path = skill_entry.path
    skill_md = skill_path / "SKILL.md"

    # Determine status from skill structure
    has_skill_md = skill_md.exists()
    has_scripts = (skill_path / "scripts").is_dir()
    has_commands = (skill_path / "commands").is_dir()

    if has_skill_md and (has_scripts or has_commands):
        status = "healthy"
    elif has_skill_md:
        status = "degraded"
    else:
        status = "unknown"

    # NOTE: "structure" dict prevents useBlockData's unwrapToolData from
    # converting this all-scalar response into a [{value,label}] array.
    # HealthBlock reads status/lastCheck/errors24h as top-level fields.
    return json.dumps(
        {
            "status": status,
            "lastCheck": datetime.now(timezone.utc).isoformat(),
            "errors24h": 0,
            "uptime": "available" if has_skill_md else "unavailable",
            "structure": {
                "has_skill_md": has_skill_md,
                "has_scripts": has_scripts,
                "has_commands": has_commands,
            },
        }
    )
