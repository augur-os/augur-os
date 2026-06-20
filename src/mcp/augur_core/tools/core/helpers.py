"""
Helper functions for core MCP tools.

These utilities handle skill resolution, module listing, and trigger scoring.
"""

from collections.abc import Iterable
from pathlib import Path


def _get_skills_dir() -> Path:
    """Get the canonical skills directory."""
    from src.mcp.augur_shared.config import get_config

    return get_config().plugins_dir


def _get_data_dir() -> Path:
    """Get the project root directory."""
    from src.mcp.augur_shared.config import get_project_root

    return get_project_root()


def list_modules(skill_path: Path) -> list[str]:
    """List available modules for a skill.

    Args:
        skill_path: Path to the skill directory

    Returns:
        List of module names (without .md extension)
    """
    modules_dir = skill_path / "modules"
    if not modules_dir.exists():
        return []
    return [f.stem for f in modules_dir.glob("*.md")]


def list_references(skill_path: Path) -> list[str]:
    """List available references for a skill.

    Args:
        skill_path: Path to the skill directory

    Returns:
        List of reference names (without .md extension)
    """
    refs_dir = skill_path / "references"
    if not refs_dir.exists():
        return []
    return [f.stem for f in refs_dir.glob("*.md")]


def compute_trigger_score(query: str, skill_info: dict) -> float:
    """Score how well a query matches a skill's triggers.

    Args:
        query: User's natural language query
        skill_info: Dict with 'name', 'description', 'triggers' keys

    Returns:
        Float score (higher = better match)
    """
    query_lower = query.lower()
    query_words = set(query_lower.split())

    score = 0.0

    # Exact trigger match (highest)
    for trigger in skill_info.get("triggers", []):
        if trigger.lower() in query_lower:
            score += 10.0

    # Skill name match
    if skill_info["name"].lower() in query_lower:
        score += 8.0

    # Word overlap with triggers
    for trigger in skill_info.get("triggers", []):
        trigger_words = set(trigger.lower().split())
        overlap = len(query_words & trigger_words)
        score += overlap * 2.0

    # Description word overlap
    desc = skill_info.get("description", "").lower()
    desc_words = set(desc.split())
    desc_overlap = len(query_words & desc_words)
    score += desc_overlap * 0.5

    return score


def safe_join(base: Path, *parts: str) -> Path:
    """Safely join path parts, preventing directory traversal.

    Args:
        base: Base directory path
        *parts: Path parts to join

    Returns:
        Resolved path within base directory

    Raises:
        ValueError: If resulting path is outside base directory
    """
    target = (base.joinpath(*parts)).resolve()
    base_resolved = base.resolve()
    try:
        target.relative_to(base_resolved)
    except ValueError as exc:
        raise ValueError("Path is outside allowed root") from exc
    return target


def iter_override_paths(skill_entry, skill_name: str, module_name: str, data_dir: Path) -> Iterable[Path]:
    """Iterate over possible override paths for a module.

    Args:
        skill_entry: SkillRecord entry
        skill_name: Requested skill name
        module_name: Module name to find
        data_dir: User data directory

    Yields:
        Possible override paths in priority order
    """
    seen: set[str] = set()
    for name in (skill_entry.name, skill_name):
        if not name:
            continue
        if name in seen:
            continue
        seen.add(name)
        try:
            yield safe_join(data_dir, name, "modules", f"{module_name}.md")
        except ValueError:
            continue


__all__ = [
    "list_modules",
    "list_references",
    "compute_trigger_score",
    "safe_join",
    "iter_override_paths",
]
