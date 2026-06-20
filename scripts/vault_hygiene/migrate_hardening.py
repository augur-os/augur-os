#!/usr/bin/env python3
"""Move hardening-reports/ from vault to runtime state dir (ADR-416)."""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path

def _get_vault() -> Path:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.config.paths import get_vault_dir
    return get_vault_dir()

def _get_state() -> Path:
    """Runtime state dir for hardening reports."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.config.paths import get_runtime_dir
    return get_runtime_dir() / "hardening"

def migrate(dry_run: bool = True) -> dict:
    vault = _get_vault()
    target_root = _get_state()
    stats = {"dirs": 0, "files": 0, "errors": []}

    print(f"{'DRY RUN' if dry_run else 'APPLYING'}: Move hardening-reports from vault to state dir\n")
    print(f"Source: {vault}")
    print(f"Target: {target_root}\n")

    for hr_dir in sorted(vault.rglob("hardening-reports")):
        if not hr_dir.is_dir():
            continue
        files = [f for f in hr_dir.rglob("*") if f.is_file()]
        if not files:
            # Remove empty dir
            if not dry_run:
                shutil.rmtree(hr_dir, ignore_errors=True)
            continue

        rel = hr_dir.relative_to(vault)
        parts = rel.parts  # e.g., ('career', 'career', 'hardening-reports')
        skill_key = "/".join(parts[:-1])
        target = target_root / skill_key

        if dry_run:
            print(f"  {skill_key}: {len(files)} files → {target}")
        else:
            target.mkdir(parents=True, exist_ok=True)
            for f in files:
                dest = target / f.relative_to(hr_dir)
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(str(f), str(dest))
                except Exception as e:
                    stats["errors"].append(f"{f}: {e}")
            shutil.rmtree(hr_dir, ignore_errors=True)
            print(f"  MOVED: {skill_key} ({len(files)} files)")

        stats["dirs"] += 1
        stats["files"] += len(files)

    print(f"\n{'Would move' if dry_run else 'Moved'}: {stats['dirs']} dirs, {stats['files']} files")
    if stats["errors"]:
        print(f"Errors: {len(stats['errors'])}")
        for e in stats["errors"][:5]:
            print(f"  {e}")
    return stats

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Move hardening-reports from vault to state dir (ADR-416)")
    p.add_argument("--apply", action="store_true", help="Apply changes (default: dry run)")
    args = p.parse_args()
    migrate(dry_run=not args.apply)
