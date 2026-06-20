#!/usr/bin/env python3
"""Resolve duplicate folder names in the vault (ADR-416)."""
from __future__ import annotations
import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.paths import get_vault_dir

# Merge: source → destination (source is stub/smaller, destination is canonical)
MERGE = {
}

# Rename: disambiguate by renaming the less-specific one
RENAME = {
}

# Flatten: nested self-duplicate merges into parent
FLATTEN = [
    "admin/channels/reviews/reviews",
    "dev/mcp-app-factory/mcp-app-factory",
]

def _get_vault() -> Path:
    return get_vault_dir()

def migrate(dry_run: bool = True) -> dict:
    vault = _get_vault()
    stats = {"merged": 0, "renamed": 0, "flattened": 0, "errors": []}

    print(f"{'DRY RUN' if dry_run else 'APPLYING'}: Deduplicate vault folders\n")

    # Merge
    for src_rel, dst_rel in MERGE.items():
        src = vault / src_rel
        dst = vault / dst_rel
        if not src.exists():
            continue
        files = [f for f in src.rglob("*") if f.is_file()]
        if dry_run:
            print(f"  MERGE: {src_rel} ({len(files)} files) → {dst_rel}")
        else:
            dst.mkdir(parents=True, exist_ok=True)
            for f in files:
                dest = dst / f.relative_to(src)
                if not dest.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(f), str(dest))
            shutil.rmtree(src, ignore_errors=True)
            print(f"  MERGED: {src_rel} → {dst_rel}")
        stats["merged"] += 1

    # Rename
    for old_rel, new_rel in RENAME.items():
        old = vault / old_rel
        new = vault / new_rel
        if not old.exists():
            continue
        files = [f for f in old.rglob("*") if f.is_file()]
        if dry_run:
            print(f"  RENAME: {old_rel} ({len(files)} files) → {new_rel}")
        else:
            try:
                old.rename(new)
                print(f"  RENAMED: {old_rel} → {new_rel}")
            except Exception as e:
                stats["errors"].append(f"rename {old_rel}: {e}")
        stats["renamed"] += 1

    # Flatten
    for inner_rel in FLATTEN:
        inner = vault / inner_rel
        if not inner.exists():
            continue
        parent = inner.parent
        files = [f for f in inner.rglob("*") if f.is_file()]
        if dry_run:
            print(f"  FLATTEN: {inner_rel} ({len(files)} files) → {parent.relative_to(vault)}")
        else:
            for f in files:
                dest = parent / f.relative_to(inner)
                if not dest.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(f), str(dest))
            shutil.rmtree(inner, ignore_errors=True)
            print(f"  FLATTENED: {inner_rel}")
        stats["flattened"] += 1

    total = stats["merged"] + stats["renamed"] + stats["flattened"]
    print(f"\n{'Would process' if dry_run else 'Processed'}: {total} ({stats['merged']} merged, {stats['renamed']} renamed, {stats['flattened']} flattened)")
    return stats

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Deduplicate vault folders (ADR-416)")
    p.add_argument("--apply", action="store_true", help="Apply changes (default: dry run)")
    args = p.parse_args()
    migrate(dry_run=not args.apply)
