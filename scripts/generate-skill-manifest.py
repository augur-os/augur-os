#!/usr/bin/env python3
"""Generate skill-manifest.json from canonical skill discovery.

Writes docs/generated/skill-manifest.json — the single JSON manifest
that TypeScript consumers read instead of scanning the filesystem.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from src.lib.generated_artifacts import write_stable_json
from src.plugins.skill_discovery import discover_all_skills


def _relative_path(path: Path, base: Path) -> str:
    """Return path relative to base if it's under base, else absolute."""
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def _compact_dict(d: dict) -> dict | None:
    """Return dict if non-empty, else None (saves JSON space)."""
    return d if d else None


def _compact_list(lst: list) -> list | None:
    """Return list if non-empty, else None (saves JSON space)."""
    return lst if lst else None


def discover_manifest_skills():
    """Discover only repo-owned skills for the committed manifest."""
    return discover_all_skills(tiers=(0,))


def build_manifest(skills, *, project_root: str = ".") -> dict:
    """Build the skill manifest payload."""
    return {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": project_root,
        "skills": [
            {
                "name": s.name,
                "description": s.description,
                "path": _relative_path(s.path, root),
                "master": s.master,
                "hub": s.hub or None,
                "visibility": getattr(s, "visibility", None) or None,
                "group": getattr(s, "group", None) or None,
                "release": getattr(s, "release", None) or None,
                "category": getattr(s, "category", None) or None,
                "requires_platform": getattr(s, "requires_platform", False),
                "ownership": getattr(s, "ownership", "augur") or "augur",
                "source": getattr(s, "source", "augur") or "augur",
                "loop_config": _compact_dict(s.loop_config),
                "dependencies": _compact_dict(s.dependencies),
                "mcp_tools": _compact_list(s.mcp_tools),
                "dashboard_pages": _compact_list(s.dashboard_pages),
                "commands": _compact_list(s.commands),
                # config omitted — too large; read SKILL.md/frontmatter on demand
                "agent": s.agent,
                "tier": s.tier,
            }
            for s in skills
        ],
        "total": len(skills),
    }


def main() -> None:
    skills = discover_manifest_skills()
    manifest = build_manifest(skills)
    out_path = root / "docs" / "generated" / "skill-manifest.json"
    write_stable_json(out_path, manifest, volatile_keys=["generated_at"])
    print(f"Generated {out_path}: {len(skills)} skills")


if __name__ == "__main__":
    main()
