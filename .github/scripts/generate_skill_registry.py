#!/usr/bin/env python3
"""
Generate Local Markdown Skill Registry

Scans project-brain/capabilities/skills/*/SKILL.md files, extracts name, description, and
x-augur-hub frontmatter, groups by hub, and outputs docs/generated/skill-registry.md.
That Markdown file is ignored by Git; tracked consumers should use
docs/generated/skill-manifest.json instead.

Usage:
    python3 .github/scripts/generate_skill_registry.py
"""

import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.lib.generated_artifacts import write_stable_text

OUTPUT = PROJECT_ROOT / "docs" / "generated" / "skill-registry.md"


def extract_frontmatter(skill_md: Path) -> dict[str, str]:
    """Extract YAML frontmatter key-value pairs from a SKILL.md file."""
    result: dict[str, str] = {}
    try:
        lines = skill_md.read_text(encoding="utf-8").splitlines()
    except OSError:
        return result
    if not lines or lines[0].strip() != "---":
        return result
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip().strip("'\"")
    return result


def extract_description(skill_md: Path) -> str:
    """Extract first non-heading, non-empty, non-frontmatter line as description."""
    try:
        in_frontmatter = False
        for line in skill_md.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped == "---":
                in_frontmatter = not in_frontmatter
                continue
            if in_frontmatter:
                continue
            if not stripped or stripped.startswith("#"):
                continue
            return stripped[:120]
    except OSError:
        pass
    return ""


def scan_all_skills() -> tuple[list[dict], set[str]]:
    """Scan project-brain/capabilities/skills/ for skills with SKILL.md and x-augur-hub frontmatter."""
    skills_dir = PROJECT_ROOT / "project-brain" / "capabilities" / "skills"
    skills: list[dict] = []
    hubs: set[str] = set()
    if not skills_dir.is_dir():
        return skills, hubs
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        fm = extract_frontmatter(skill_md)
        hub = fm.get("x-augur-hub", "")
        if not hub:
            continue
        hubs.add(hub)
        rel_path = skill_dir.relative_to(PROJECT_ROOT)
        skills.append(
            {
                "name": skill_dir.name,
                "bundle": hub,
                "path": str(rel_path),
                "description": extract_description(skill_md),
            }
        )
    return skills, hubs


def generate_markdown(skills: list[dict], hub_count: int) -> str:
    """Generate the skill registry markdown."""
    lines = [
        "# Skill Registry",
        "",
        f"> Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}. Do not hand-edit.",
        "",
        f"**{len(skills)} skills** across {hub_count} hubs.",
        "",
        "| Skill | Hub | Path |",
        "|-------|-----|------|",
    ]
    for s in skills:
        lines.append(f"| {s['name']} | {s['bundle']} | `{s['path']}` |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    skills, hubs = scan_all_skills()
    if not skills:
        print("No skills found.", file=sys.stderr)
        return 1

    content = generate_markdown(skills, len(hubs))
    write_stable_text(OUTPUT, content, volatile_line_prefixes=("> Auto-generated on ",))
    print(f"Generated {OUTPUT.relative_to(PROJECT_ROOT)} ({len(skills)} skills)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
