#!/usr/bin/env python3
"""Migrate a hub's skills from plugins/ to a client directory.

Usage:
    python scripts/migrate/migrate_hub_to_client.py --hub productivity --client claude-code
    python scripts/migrate/migrate_hub_to_client.py --hub productivity --client claude-code --dry-run
"""

import argparse
import shutil
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter

CLIENT_SKILL_DIRS = {
    "claude-code": ".claude/skills",
    "codex": ".codex/prompts",
    "gemini": ".gemini/skills",
    "cursor": ".cursor/rules",
}


def migrate_skill(skill_dir: Path, target_dir: Path, client: str) -> bool:
    skill_name = skill_dir.name
    dest = target_dir / skill_name

    if dest.exists():
        print(f"  SKIP: {skill_name} — already exists at {dest.relative_to(project_root)}")
        return False

    shutil.copytree(skill_dir, dest)

    skill_md = dest / "SKILL.md"
    if skill_md.exists():
        try:
            fm, body = parse_frontmatter(skill_md)
            fm["x-augur-master"] = client
            write_frontmatter(skill_md, fm, body)
        except Exception as e:
            print(f"  WARNING: Could not update frontmatter for {skill_name}: {e}")

    shutil.rmtree(skill_dir)
    print(f"  Migrated: {skill_name} → {dest.relative_to(project_root)}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Migrate hub skills to client directory")
    parser.add_argument("--hub", required=True, help="Hub to migrate (e.g., productivity)")
    parser.add_argument("--client", required=True, choices=list(CLIENT_SKILL_DIRS.keys()),
                       help="Target client")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated")
    args = parser.parse_args()

    client_dir = CLIENT_SKILL_DIRS[args.client]
    target = project_root / client_dir
    target.mkdir(parents=True, exist_ok=True)

    hub_dir = project_root / "plugins" / args.hub / "skills"
    if not hub_dir.exists():
        print(f"No skills found at {hub_dir}")
        sys.exit(1)

    skills = sorted([d for d in hub_dir.iterdir() if d.is_dir()])
    print(f"{'[DRY RUN] ' if args.dry_run else ''}Migrating {len(skills)} skills from {args.hub} to {args.client}")

    if args.dry_run:
        for s in skills:
            dest = target / s.name
            status = "EXISTS" if dest.exists() else "OK"
            print(f"  [{status}] {s.name} → {client_dir}/{s.name}")
        return

    migrated = 0
    for skill_dir in skills:
        if migrate_skill(skill_dir, target, args.client):
            migrated += 1

    print(f"\nDone. Migrated: {migrated}/{len(skills)}")
    print(f"\nNext steps:")
    print(f"  1. Run: cd apps/dashboard && npx tsx scripts/mount-plugins.ts --dry-run")
    print(f"  2. Run: PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents fix")
    print(f"  3. Verify dashboard pages for {args.hub} hub")


if __name__ == "__main__":
    main()
