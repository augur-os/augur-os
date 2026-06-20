#!/usr/bin/env python3
"""Move config.yaml from data directories into _config/ subdirs (ADR-416)."""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path

SKIP_DIRS = {"_config", "_cache", "hardening-reports", "prompts", "actions", "chains"}

def _get_vault() -> Path:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.config.paths import get_vault_dir
    return get_vault_dir()

def migrate(dry_run: bool = True) -> dict:
    vault = _get_vault()
    stats = {"moved": 0, "skipped": 0, "errors": []}

    print(f"{'DRY RUN' if dry_run else 'APPLYING'}: Move config.yaml into _config/ subdirs\n")

    for config_file in sorted(vault.rglob("config.yaml")):
        parent = config_file.parent
        if parent.name in SKIP_DIRS or parent.name.startswith("_"):
            stats["skipped"] += 1
            continue
        # Only move if config sits alongside .md user data
        sibling_mds = list(parent.glob("*.md"))
        if not sibling_mds:
            stats["skipped"] += 1
            continue

        rel = config_file.relative_to(vault)
        target_dir = parent / "_config"
        target = target_dir / "config.yaml"

        if dry_run:
            print(f"  {rel} → {target.relative_to(vault)}")
        else:
            target_dir.mkdir(exist_ok=True)
            try:
                shutil.move(str(config_file), str(target))
                print(f"  MOVED: {rel}")
            except Exception as e:
                stats["errors"].append(f"{rel}: {e}")
        stats["moved"] += 1

    print(f"\n{'Would move' if dry_run else 'Moved'}: {stats['moved']} config files (skipped {stats['skipped']})")
    return stats

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Move config.yaml into _config/ subdirs (ADR-416)")
    p.add_argument("--apply", action="store_true", help="Apply changes (default: dry run)")
    args = p.parse_args()
    migrate(dry_run=not args.apply)
