"""Wave-1 Au-docs flatten (file-naming spec 2026-06-12).

Au-docs is NOT a git repo — manifest accounting is the only safety net.
Hard-fails on count mismatch (half-migrated state is worse than aborted).
Manifests written to Au-docs/_augur/migration-naming-{before,after}.json.

KEPT deliberately (not in MOVES):
- career/cheat-sheets/<topic>/ — spec: topic grouping stays (≤ depth 3 under domain)
- career/cv/v3-column — purposeful versioned set, ≤ depth 2 under cv
- career/cv/hebrew — purposeful, ≤ depth 2 under cv
- career/cv/tailored — purposeful, ≤ depth 2 under cv

Usage:
  uv run python scripts/migrations/flatten_audocs_2026_06_12.py --dry-run
  uv run python scripts/migrations/flatten_audocs_2026_06_12.py --execute
  uv run python scripts/migrations/flatten_audocs_2026_06_12.py --phase-2 --dry-run
  uv run python scripts/migrations/flatten_audocs_2026_06_12.py --phase-2 --execute

Phase 2 (spec amendment 2026-06-12, "generated output moves out"): the deck
pipeline's generated outputs move to _augur/; user-authored decks stay in
venture/deck. Phase-2 manifests: _augur/migration-naming2-{before,after}.json.

Phase 3 (controller decision 2026-06-12): the four prompt/action template
trees under career/ are dead gbrain-era collateral (only reference anywhere
was wiki_quality.py's own exclusion-marker list) — archived to
_augur/archive/2026-06-12-naming/legacy-templates/. Phase-3 manifests:
_augur/migration-naming3-{before,after}.json.

  uv run python scripts/migrations/flatten_audocs_2026_06_12.py --phase-3 --dry-run
  uv run python scripts/migrations/flatten_audocs_2026_06_12.py --phase-3 --execute
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config.paths import get_documents_dir  # noqa: E402

# (src_rel, dst_rel) — dir merge: move each child; file: direct rename.
# ORDER MATTERS: assets must move before notes (notes dir will merge into
# career/growth/notes which already exists with different asset files).
MOVES = [
    # Remotion code project = tooling, not career content
    ("career/content/video", "_augur/video-studio"),
    # nested career/content/career/* tree (legacy import nesting)
    # assets move FIRST, then notes (remaining after assets move), then remaining children
    ("career/content/career/notes/hard-skills/assets", "career/assets/hard-skills"),
    ("career/content/career/notes", "career/growth/notes"),   # remaining notes after assets move
    ("career/content/career", "career/content"),              # any remaining children up one level
    # cv zone: v1 superseded by v2 (user-designated baseline 2026-06-08) -> archive
    ("career/cv/v1", "_augur/archive/2026-06-12-naming/cv-v1"),
    # flatten v2 format dirs into cv/ (files carry _v2 + extension distinguishes format)
    ("career/cv/v2/MD", "career/cv"),
    ("career/cv/v2/HTML", "career/cv"),
    ("career/cv/v2/PDF", "career/cv"),
    # rename AI LAB CTO dir to lowercase-hyphen convention
    ("career/cv/AI LAB CTO", "career/cv/ai-lab-cto"),
    # single-child chain under apple/voice-memos
    ("apple/voice-memos/2026-01-15", "apple/voice-memos"),
    # orphaned run artifact
    ("inbox/claude", "_augur/archive/2026-06-12-naming/inbox-claude"),
    # Guriqo entries (plan KEPT paragraph): Hebrew forum dir flattens into guriqo-forum/
    ("venture/Guriqo/פורום דבורה", "venture/guriqo-forum"),
    ("venture/Guriqo", "venture/guriqo-forum"),
]

EMPTY_AFTER = [
    "career/content/video",
    "career/content/career",
    "career/cv/v2",
]

# Phase 2 (spec amendment): generated deck pipeline outputs out of venture/deck.
PHASE2_MOVES = [
    ("venture/deck/pipeline-outputs", "_augur/deck-pipeline-outputs"),
]

PHASE2_EMPTY_AFTER = [
    "venture/deck/pipeline-outputs",
]

# Phase 3 (controller decision): dead gbrain-era template trees -> archive.
_LEGACY_TEMPLATES = "_augur/archive/2026-06-12-naming/legacy-templates"
PHASE3_MOVES = [
    ("career/content/actions", f"{_LEGACY_TEMPLATES}/content-actions"),
    ("career/content/prompts", f"{_LEGACY_TEMPLATES}/content-prompts"),
    ("career/growth/actions", f"{_LEGACY_TEMPLATES}/growth-actions"),
    ("career/growth/prompts", f"{_LEGACY_TEMPLATES}/growth-prompts"),
]

PHASE3_EMPTY_AFTER = [
    "career/content/actions",
    "career/content/prompts",
    "career/growth/actions",
    "career/growth/prompts",
]


def manifest(root: Path) -> dict:
    """Enumerate all files under root, excluding .DS_Store and naming manifests."""
    files = sorted(
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file()
        and p.name != ".DS_Store"
        and not p.name.startswith("migration-naming")
    )
    return {"count": len(files), "files": files}


def move(src: Path, dst: Path, dry: bool) -> None:
    """Move src to dst using Path.rename; creates parents, refuses to overwrite.

    Merges directories by moving each child individually.
    Skips .DS_Store files.
    Raises RuntimeError on any failure so one bad move aborts the whole script.
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
        # After merging all children, remove the now-empty source dir.
        # rmdir fails when .DS_Store is the only remnant — use rmtree in that case.
        if not dry:
            leftover_files = [p for p in src.rglob("*") if p.is_file() and p.name != ".DS_Store"]
            if not leftover_files:
                shutil.rmtree(src, ignore_errors=True)
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


def check_v2_word(docs: Path) -> None:
    """FATAL if career/cv/v2/WORD exists (unexpected; would corrupt the flatten)."""
    word_dir = docs / "career/cv/v2/WORD"
    if word_dir.exists():
        raise SystemExit(
            f"FATAL: career/cv/v2/WORD exists unexpectedly — investigate before proceeding.\n"
            f"Contents: {list(word_dir.iterdir())}"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    pg = ap.add_mutually_exclusive_group()
    pg.add_argument("--phase-2", action="store_true",
                    help="run the phase-2 moves (deck pipeline outputs to _augur)")
    pg.add_argument("--phase-3", action="store_true",
                    help="run the phase-3 moves (legacy template trees to archive)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    dry = args.dry_run
    docs = get_documents_dir()

    if args.phase_2:
        moves, empty_after, manifest_prefix = (
            PHASE2_MOVES, PHASE2_EMPTY_AFTER, "migration-naming2"
        )
    elif args.phase_3:
        moves, empty_after, manifest_prefix = (
            PHASE3_MOVES, PHASE3_EMPTY_AFTER, "migration-naming3"
        )
    else:
        moves, empty_after, manifest_prefix = MOVES, EMPTY_AFTER, "migration-naming"
        # FATAL guard: v2/WORD must not exist (phase-1 cv flatten only)
        check_v2_word(docs)

    before = manifest(docs)

    augur_dir = docs / "_augur"
    if not dry:
        augur_dir.mkdir(exist_ok=True)
        (augur_dir / f"{manifest_prefix}-before.json").write_text(
            json.dumps(before, indent=1), encoding="utf-8"
        )

    for src_rel, dst_rel in moves:
        src = docs / src_rel
        dst = docs / dst_rel
        if not src.exists():
            # Later entries may already be consumed by earlier moves (e.g. dir emptied)
            print(f"SKIP (already gone) {src_rel}")
            continue
        move(src, dst, dry)

    # Verify EMPTY_AFTER dirs are gone (or empty) — only meaningful after real moves
    if not dry:
        for rel in empty_after:
            d = docs / rel
            if d.is_dir():
                leftovers = [
                    p for p in d.rglob("*") if p.is_file() and p.name != ".DS_Store"
                ]
                if leftovers:
                    raise RuntimeError(
                        f"FATAL: {rel} not empty after moves — leftover files: {leftovers[:5]}"
                    )
                try:
                    d.rmdir()
                except OSError:
                    pass

    print(
        "\n--- DRY-RUN: current file distribution (pre-move snapshot) ---"
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
        (augur_dir / f"{manifest_prefix}-after.json").write_text(
            json.dumps(after, indent=1), encoding="utf-8"
        )
        print(f"\nbefore={before['count']} after={after['count']}")
        if before["count"] != after["count"]:
            print("FATAL: file count changed — investigate before committing.")
            sys.exit(1)

    print("done")


if __name__ == "__main__":
    main()
