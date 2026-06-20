#!/usr/bin/env python3
"""Migrate non-standard skill directories to schema-compliant locations.

Migrations:
1. docs/ -> references/ (merge if references/ already exists)
2. data/ at skill root -> delete (empty/.gitkeep) or move to assets/ (real content)
3. augur/seed/ -> assets/seeds/
4. ai/lib/ -> scripts/ (portable utilities)
5. enterprise/.augur-plugin/ -> delete
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config.paths import get_skills_dir


def log(msg: str, dry_run: bool) -> None:
    prefix = "[DRY-RUN] " if dry_run else ""
    print(f"{prefix}{msg}")


def move_file(src: Path, dst: Path, dry_run: bool) -> None:
    """Move a single file, creating parent dirs as needed."""
    log(f"  mv {src} -> {dst}", dry_run)
    if not dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))


def merge_dir(src_dir: Path, dst_dir: Path, dry_run: bool) -> int:
    """Move all files from src_dir into dst_dir. Returns count of files moved."""
    count = 0
    for item in sorted(src_dir.iterdir()):
        if item.is_file():
            move_file(item, dst_dir / item.name, dry_run)
            count += 1
        elif item.is_dir():
            # Recurse
            count += merge_dir(item, dst_dir / item.name, dry_run)
    return count


def rmdir(path: Path, dry_run: bool) -> None:
    log(f"  rmdir {path}", dry_run)
    if not dry_run:
        shutil.rmtree(str(path))


# ---------------------------------------------------------------------------
# Migration 1: docs/ -> references/
# ---------------------------------------------------------------------------
DOCS_TO_REFS_SKILLS = [
    "apple", "career", "daemon", "dev-loops", "google-workspace", "lifestyle", "venture"
]


def migrate_docs_to_references(skills_dir: Path, dry_run: bool) -> dict:
    results = {"renamed": [], "merged": [], "skipped": []}
    for skill_name in DOCS_TO_REFS_SKILLS:
        skill_dir = skills_dir / skill_name
        docs_dir = skill_dir / "docs"
        refs_dir = skill_dir / "references"

        if not docs_dir.exists():
            results["skipped"].append(f"{skill_name}: no docs/ found")
            continue

        if refs_dir.exists():
            # Merge docs/ into references/
            log(f"[1] MERGE {skill_name}/docs/ -> references/ (both exist)", dry_run)
            files_moved = merge_dir(docs_dir, refs_dir, dry_run)
            if files_moved > 0 or not dry_run:
                rmdir(docs_dir, dry_run)
            results["merged"].append(f"{skill_name}: merged {files_moved} files")
        else:
            # Rename docs/ to references/
            log(f"[1] RENAME {skill_name}/docs/ -> references/", dry_run)
            if not dry_run:
                docs_dir.rename(refs_dir)
            results["renamed"].append(skill_name)

    return results


# ---------------------------------------------------------------------------
# Migration 2: data/ at skill root -> delete or move to assets/
# ---------------------------------------------------------------------------

def is_empty_or_gitkeep(data_dir: Path) -> bool:
    """Return True if data_dir contains only .gitkeep files (or is empty)."""
    for item in data_dir.rglob("*"):
        if item.is_file() and item.name != ".gitkeep":
            return False
    return True


def migrate_data_dirs(skills_dir: Path, dry_run: bool) -> dict:
    results = {"deleted": [], "moved_to_assets": [], "skipped": []}

    data_dirs = sorted(
        d for d in skills_dir.glob("*/data")
        if d.is_dir() and "augur" not in d.parts
    )

    for data_dir in data_dirs:
        skill_name = data_dir.parent.name

        if is_empty_or_gitkeep(data_dir):
            log(f"[2] DELETE {skill_name}/data/ (empty/.gitkeep only)", dry_run)
            rmdir(data_dir, dry_run)
            results["deleted"].append(skill_name)
        else:
            # Real content — move to assets/
            assets_dir = data_dir.parent / "assets"
            log(f"[2] MOVE {skill_name}/data/* -> assets/", dry_run)
            # Move files individually (don't nest data/ inside assets/)
            files_moved = merge_dir(data_dir, assets_dir, dry_run)
            rmdir(data_dir, dry_run)
            results["moved_to_assets"].append(f"{skill_name}: {files_moved} files")

    return results


# ---------------------------------------------------------------------------
# Migration 3: augur/seed/ -> assets/seeds/
# ---------------------------------------------------------------------------

def migrate_augur_seed(skills_dir: Path, dry_run: bool) -> dict:
    results = {"migrated": [], "merged": [], "skipped": []}

    seed_dirs = sorted(skills_dir.glob("*/augur/seed"))

    for seed_dir in seed_dirs:
        if not seed_dir.is_dir():
            continue
        skill_name = seed_dir.parent.parent.name
        assets_seeds = seed_dir.parent.parent / "assets" / "seeds"

        if assets_seeds.exists():
            # Merge
            log(f"[3] MERGE {skill_name}/augur/seed/ -> assets/seeds/ (both exist)", dry_run)
            files_moved = merge_dir(seed_dir, assets_seeds, dry_run)
            rmdir(seed_dir, dry_run)
            results["merged"].append(f"{skill_name}: {files_moved} files")
        else:
            # Move
            log(f"[3] MOVE {skill_name}/augur/seed/ -> assets/seeds/", dry_run)
            if not dry_run:
                assets_seeds.parent.mkdir(parents=True, exist_ok=True)
                seed_dir.rename(assets_seeds)
            results["migrated"].append(skill_name)

    return results


# ---------------------------------------------------------------------------
# Migration 4: ai/lib/ -> scripts/
# ---------------------------------------------------------------------------

def migrate_ai_lib(skills_dir: Path, dry_run: bool) -> dict:
    results = {}
    lib_dir = skills_dir / "ai" / "lib"
    scripts_dir = skills_dir / "ai" / "scripts"

    if not lib_dir.exists():
        results["skipped"] = "ai/lib/ not found"
        return results

    log(f"[4] MOVE ai/lib/ -> scripts/ (portable utilities)", dry_run)
    files_moved = 0
    for item in sorted(lib_dir.iterdir()):
        if item.is_file() and item.name != "__pycache__":
            move_file(item, scripts_dir / item.name, dry_run)
            files_moved += 1
        elif item.is_dir() and item.name != "__pycache__":
            files_moved += merge_dir(item, scripts_dir / item.name, dry_run)

    rmdir(lib_dir, dry_run)
    results["migrated"] = f"{files_moved} files"
    return results


# ---------------------------------------------------------------------------
# Migration 5: enterprise/.augur-plugin/ -> delete
# ---------------------------------------------------------------------------

def migrate_enterprise_augur_plugin(skills_dir: Path, dry_run: bool) -> dict:
    plugin_dir = skills_dir / "enterprise" / ".augur-plugin"
    if not plugin_dir.exists():
        return {"skipped": "enterprise/.augur-plugin/ not found"}

    log(f"[5] DELETE enterprise/.augur-plugin/", dry_run)
    rmdir(plugin_dir, dry_run)
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without making changes")
    args = parser.parse_args()

    dry_run = args.dry_run
    skills_dir = get_skills_dir()

    print(f"\n{'DRY RUN — ' if dry_run else ''}Migrating skill directories in: {skills_dir}\n")
    print("=" * 70)

    # 1. docs/ -> references/
    print("\n--- Migration 1: docs/ -> references/ ---")
    r1 = migrate_docs_to_references(skills_dir, dry_run)
    print(f"  Renamed: {len(r1['renamed'])} skills: {r1['renamed']}")
    print(f"  Merged:  {len(r1['merged'])} skills: {r1['merged']}")
    print(f"  Skipped: {len(r1['skipped'])}: {r1['skipped']}")

    # 2. data/ -> delete or assets/
    print("\n--- Migration 2: data/ -> delete or assets/ ---")
    r2 = migrate_data_dirs(skills_dir, dry_run)
    print(f"  Deleted (empty): {len(r2['deleted'])} dirs")
    print(f"  Moved to assets: {r2['moved_to_assets']}")

    # 3. augur/seed/ -> assets/seeds/
    print("\n--- Migration 3: augur/seed/ -> assets/seeds/ ---")
    r3 = migrate_augur_seed(skills_dir, dry_run)
    print(f"  Migrated: {len(r3['migrated'])} skills")
    print(f"  Merged:   {len(r3['merged'])} skills: {r3['merged']}")

    # 4. ai/lib/ -> scripts/
    print("\n--- Migration 4: ai/lib/ -> scripts/ ---")
    r4 = migrate_ai_lib(skills_dir, dry_run)
    print(f"  Result: {r4}")

    # 5. enterprise/.augur-plugin/ -> delete
    print("\n--- Migration 5: enterprise/.augur-plugin/ -> delete ---")
    r5 = migrate_enterprise_augur_plugin(skills_dir, dry_run)
    print(f"  Result: {r5}")

    print("\n" + "=" * 70)
    print("SUMMARY:")
    print(f"  [1] docs->refs: {len(r1['renamed'])} renamed, {len(r1['merged'])} merged")
    print(f"  [2] data/ dirs: {len(r2['deleted'])} deleted, {len(r2['moved_to_assets'])} moved to assets")
    print(f"  [3] augur/seed: {len(r3['migrated'])} moved, {len(r3['merged'])} merged")
    print(f"  [4] ai/lib: {r4}")
    print(f"  [5] enterprise/.augur-plugin: {r5}")

    if dry_run:
        print("\nRe-run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
