"""
Discover Skills - DevOps Agent

Scans all skills across plugin hubs and generates a catalog.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)


def _resolve_plugins_dir() -> Path:
    """Resolve plugins directory."""
    return PROJECT_ROOT / "plugins"


def _parse_frontmatter(content: str) -> dict[str, Any]:
    """Parse YAML frontmatter from skill file."""
    if not content.startswith("---"):
        return {}

    end = content.find("---", 3)
    if end == -1:
        return {}

    frontmatter = content[3:end].strip()
    result = {}
    for line in frontmatter.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip()
    return result


def _extract_commands(content: str) -> list[str]:
    """Extract command names from SKILL.md content."""
    commands = []
    in_table = False
    for line in content.split("\n"):
        if "| Command |" in line or "| `" in line:
            in_table = True
        if in_table and line.startswith("|"):
            match = re.search(r"`([^`]+)`", line)
            if match:
                commands.append(match.group(1).split(":")[0].strip())
    return commands


def _discover_skill(skill_path: Path) -> dict[str, Any] | None:
    """Discover a single skill from its SKILL.md file."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return None

    content = skill_md.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(content)

    # Determine hub from path (plugins/{hub}/skills/{name})
    hub = "unknown"
    parts = skill_path.parts
    if "plugins" in parts and "skills" in parts:
        plugins_idx = parts.index("plugins")
        if plugins_idx + 1 < len(parts):
            hub = parts[plugins_idx + 1]

    # Check for scripts
    scripts_dir = skill_path / "scripts"
    has_scripts = scripts_dir.exists() and any(scripts_dir.glob("*.py"))

    # Check for modules
    modules_dir = skill_path / "modules"
    has_modules = modules_dir.exists() and any(modules_dir.glob("*.md"))

    # Check for references
    refs_dir = skill_path / "references"
    has_references = refs_dir.exists() and any(refs_dir.glob("*.md"))

    return {
        "name": frontmatter.get("name", skill_path.name),
        "description": (
            frontmatter.get("description", "")[:100] + "..."
            if len(frontmatter.get("description", "")) > 100
            else frontmatter.get("description", "")
        ),
        "hub": hub,
        "path": str(skill_path),
        "commands": _extract_commands(content),
        "has_scripts": has_scripts,
        "has_modules": has_modules,
        "has_references": has_references,
        "lines": len(content.split("\n")),
    }


def discover_skills(params: dict = None) -> str:
    """
    Discover all skills across the system.

    Args:
        params: Optional dictionary with:
            - hub: Filter by hub (e.g., ai, dev, career, etc.)
            - format: 'json' or 'markdown' (default: 'markdown')

    Returns:
        Catalog of discovered skills
    """
    params = params or {}
    hub_filter = params.get("hub") or params.get("layer")
    output_format = params.get("format", "markdown")

    plugins_dir = _resolve_plugins_dir()
    skills = []

    for hub_dir in sorted(plugins_dir.iterdir()):
        if not hub_dir.is_dir():
            continue
        if hub_filter and hub_dir.name != hub_filter:
            continue

        skills_dir = hub_dir / "skills"
        if not skills_dir.exists():
            continue

        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill = _discover_skill(skill_dir)
            if skill:
                skills.append(skill)

    if output_format == "json":
        return json.dumps({"skills": skills, "count": len(skills)}, indent=2)

    return _format_markdown(skills)


def _format_markdown(skills: list[dict]) -> str:
    """Format skills as markdown catalog."""
    lines = [
        "# Augur Skill Catalog",
        "",
        f"**Total Skills**: {len(skills)}",
        "",
    ]

    # Group by hub
    hubs = sorted(set(s["hub"] for s in skills))
    for hub in hubs:
        hub_skills = [s for s in skills if s["hub"] == hub]
        if not hub_skills:
            continue

        lines.append(f"## {hub.title()} Hub ({len(hub_skills)} skills)")
        lines.append("")
        lines.append("| Skill | Description | Scripts | Modules |")
        lines.append("|-------|-------------|---------|---------|")

        for skill in hub_skills:
            scripts = "yes" if skill["has_scripts"] else "-"
            modules = "yes" if skill["has_modules"] else "-"
            desc = skill["description"][:50] + "..." if len(skill["description"]) > 50 else skill["description"]
            lines.append(f"| {skill['name']} | {desc} | {scripts} | {modules} |")

        lines.append("")

    return "\n".join(lines)


def main(params: dict = None) -> str:
    """Main entry point."""
    return discover_skills(params)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        _out(main({"format": "json"}))
    else:
        _out(main())
