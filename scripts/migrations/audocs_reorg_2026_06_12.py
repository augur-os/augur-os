"""One-shot Au-docs reorganization to mirror the vault domains layout (spec 2026-06-12).

Au-docs is NOT a git repo — manifest accounting is the only safety net.
Hard-fails on count mismatch (half-migrated state is worse than aborted).
Manifests are written to Au-docs/_augur/migration-{before,after}.json.

Usage:
  uv run python scripts/migrations/audocs_reorg_2026_06_12.py --dry-run
  uv run python scripts/migrations/audocs_reorg_2026_06_12.py --execute
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config.paths import get_documents_dir  # noqa: E402

TOP_MOVES = [
    ("medical", "health"),
    ("reading", "books"),
    ("venture-augur", "venture"),
    ("insurance", "finance/insurance"),
    ("evals", "_augur/evals"),
    ("test-security", "_augur/test-security"),
    ("dev", "_augur/dev"),
    ("reports", "_augur/reports"),
    ("consulting-template", "_augur/consulting-template"),
]

CAREER_MOVES = [
    ("career/UpdatedCV", "career/cv"),
    ("career/tailored", "career/cv/tailored"),
    ("career/growth/cheat-sheets", "career/cheat-sheets"),
]


def manifest(root: Path) -> dict:
    """Enumerate all files under root, excluding .DS_Store and migration manifests."""
    files = sorted(
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file()
        and p.name != ".DS_Store"
        and "migration-before" not in p.name
        and "migration-after" not in p.name
    )
    return {"count": len(files), "files": files}


def move(src: Path, dst: Path, dry: bool) -> None:
    """Move src to dst using Path.rename; creates parents, refuses to overwrite.

    Raises RuntimeError on any failure so one bad move aborts the whole script.
    Skips .DS_Store files during merging.
    """
    if not src.exists():
        print(f"SKIP missing {src}")
        return

    if src.is_dir() and dst.exists() and dst.is_dir():
        # Merge: move each child individually
        for child in sorted(src.iterdir()):
            if child.name == ".DS_Store":
                continue
            move(child, dst / child.name, dry)
        # After merging all children, try to remove the now-empty source dir
        if not dry:
            try:
                src.rmdir()  # only succeeds if empty
            except OSError:
                pass  # non-empty (e.g. nested DS_Store) — leave for cleanup
        return

    if dst.exists():
        raise RuntimeError(
            f"ABORT: destination already exists, refusing to overwrite: {dst}"
        )

    print(("DRY  " if dry else "RUN  ") + f"move {src} → {dst}")
    if not dry:
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            src.rename(dst)
        except Exception as exc:
            raise RuntimeError(f"ABORT: failed to move {src} → {dst}: {exc}") from exc


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    dry = args.dry_run
    docs = get_documents_dir()

    before = manifest(docs)

    augur_dir = docs / "_augur"
    if not dry:
        augur_dir.mkdir(exist_ok=True)
        (augur_dir / "migration-before.json").write_text(json.dumps(before, indent=1))

    for src_rel, dst_rel in TOP_MOVES:
        move(docs / src_rel, docs / dst_rel, dry)

    for src_rel, dst_rel in CAREER_MOVES:
        move(docs / src_rel, docs / dst_rel, dry)

    # Summary count of files per top-level destination (eyeball check)
    print(
        "\n--- DRY-RUN: current file distribution (pre-move snapshot; final shown on --execute) ---"
        if dry
        else "\n--- file distribution per top-level destination ---"
    )
    dest_counts: dict[str, int] = {}
    for p in docs.rglob("*"):
        if not p.is_file() or p.name == ".DS_Store":
            continue
        rel = p.relative_to(docs)
        top = rel.parts[0] if len(rel.parts) > 1 else "<root>"
        dest_counts[top] = dest_counts.get(top, 0) + 1
    for top in sorted(dest_counts):
        print(f"  {top}: {dest_counts[top]} files")

    if not dry:
        after = manifest(docs)
        (augur_dir / "migration-after.json").write_text(json.dumps(after, indent=1))
        print(f"before={before['count']} after={after['count']}")
        if before["count"] != after["count"]:
            print("FATAL: file count changed — investigate before committing.")
            sys.exit(1)
    print("done")


if __name__ == "__main__":
    main()
