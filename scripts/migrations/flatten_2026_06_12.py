# scripts/migrations/flatten_2026_06_12.py
"""Wave-1 deterministic vault flatten (file-naming spec 2026-06-12).

Phase 1 (default): the original plan map. Phase 2 (``--phase-2``): the
execution-discovered flatten map from the spec amendment (structured-zone
exemption). EXEMPT structured zones — never mapped here: ``lifestyle/apple/**``
(Apple sync mirrors, one-dir-per-list is generated) and
``health/virtual-doctor/**`` (skill-owned data).

Usage:
  uv run python scripts/migrations/flatten_2026_06_12.py --dry-run
  uv run python scripts/migrations/flatten_2026_06_12.py --execute
  uv run python scripts/migrations/flatten_2026_06_12.py --phase-2 --dry-run
  uv run python scripts/migrations/flatten_2026_06_12.py --phase-2 --execute
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config.paths import get_vault_dir  # noqa: E402

# (src, dst) — dirs merge per-child; missing src is a hard error (maps are
# enumerated from the real vault; drift means re-audit, not skip).
MOVES = [
    ("venture/content/linkedin/posts", "venture/linkedin"),
    ("venture/content/linkedin/context", "venture/linkedin/context"),
    ("venture/content/linkedin/assets", "venture/linkedin/assets"),
    ("venture/content/linkedin", "venture/linkedin"),          # loose md after subdirs
    ("venture/content/strategies", "venture/strategy"),
    ("lifestyle/apple/notes-sync/augur", "lifestyle/apple"),
    ("augur/platform-admin/setup/ollama", "augur/platform-admin"),
]

# Mechanical renames where the stripped remainder is already meaningful.
RENAMES = [
    ("lifestyle/knowledge/notion-notes.md", "lifestyle/knowledge/apple-notes-import.md"),
    ("lifestyle/eisenhower/notion-clarity-os.md", "lifestyle/eisenhower/clarity-os.md"),
    ("lifestyle/eisenhower/notion-priority-dashboard-framework.md", "lifestyle/eisenhower/priority-dashboard.md"),
    ("lifestyle/eisenhower/notion-unified-prioritization-framework.md", "lifestyle/eisenhower/prioritization-framework.md"),
]

EMPTY_AFTER = ["venture/content", "lifestyle/apple/notes-sync", "augur/platform-admin/setup"]

# --- Phase 2 (spec amendment: execution-discovered flatten map) ---------------
MOVES_2 = [
    ("lifestyle/knowledge/kids", "lifestyle/kids"),
    ("lifestyle/knowledge", "lifestyle"),               # apple-notes-import.md, screentech-warranty.md ride up
    ("venture/knowledge/startups", "venture/startups"),
    ("venture/knowledge", "venture"),                   # anything left rides up; FATAL-empty check after
    ("venture/brand/strategy", "venture/brand"),
    ("venture/linkedin/assets", "venture/linkedin"),    # 2 loose files; assets dir removed
    ("lifestyle/recipe-manager/recipes/to-try", "lifestyle/recipes"),
    ("lifestyle/recipe-manager/recipes/perfected", "lifestyle/recipes"),
    ("lifestyle/recipe-manager/inbox.yaml", "lifestyle/recipes/inbox.yaml"),
]
EMPTY_AFTER_2 = ["lifestyle/knowledge", "venture/knowledge", "venture/brand/strategy", "venture/linkedin/assets", "lifestyle/recipe-manager"]

# Source folder -> status frontmatter value, stamped BEFORE the recipe moves so
# the to-try/perfected folder distinction is not lost in the merged dir.
RECIPE_STATUS = [
    ("lifestyle/recipe-manager/recipes/to-try", "to-try"),
    ("lifestyle/recipe-manager/recipes/perfected", "perfected"),
]


def run(cmd: list[str], cwd: Path, dry: bool) -> None:
    print(("DRY  " if dry else "RUN  ") + " ".join(cmd))
    if not dry:
        subprocess.run(cmd, cwd=cwd, check=True)


def git_mv(vault: Path, src: str, dst: str, dry: bool) -> None:
    s, d = vault / src, vault / dst
    if not s.exists():
        raise SystemExit(f"FATAL: missing source {src} — re-audit the map")
    if s.is_dir() and d.exists() and d.is_dir():
        for child in sorted(s.iterdir()):
            if child.name == ".DS_Store":
                continue
            git_mv(vault, str(child.relative_to(vault)), f"{dst}/{child.name}", dry)
        return
    if d.exists():
        raise SystemExit(f"FATAL: destination exists {dst}")
    if not dry:
        d.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "mv", str(s), str(d)], vault, dry)


def assert_empty_then_remove(vault: Path, empty_after: list[str], dry: bool) -> None:
    for rel in empty_after:
        d = vault / rel
        if d.is_dir():
            leftovers = [p for p in d.rglob("*") if p.is_file() and p.name != ".DS_Store"]
            if leftovers:
                raise SystemExit(f"FATAL: {rel} not empty after moves: {leftovers[:5]}")
            run(["rm", "-rf", str(d)], vault, dry)


def assert_phase1_done(vault: Path) -> None:
    """Phase-1 sources reappearing means the vault regressed — hard stop."""
    for src, _dst in [*MOVES, *RENAMES]:
        if (vault / src).exists():
            raise SystemExit(f"FATAL: phase-1 source reappeared: {src}")


def stamp_recipe_status(vault: Path, dry: bool) -> None:
    """Write status frontmatter from the source folder; FATAL on name collisions."""
    from src.lib.frontmatter_utils import parse_frontmatter, write_vault_frontmatter

    seen: dict[str, str] = {}
    for rel, status in RECIPE_STATUS:
        d = vault / rel
        if not d.is_dir():
            raise SystemExit(f"FATAL: missing recipe dir {rel} — re-audit the map")
        for md in sorted(d.glob("*.md")):
            if md.name in seen:
                raise SystemExit(
                    f"FATAL: recipe name collision {md.name} ({seen[md.name]} vs {rel}) — inspect manually"
                )
            seen[md.name] = rel
            print(("DRY  " if dry else "RUN  ") + f"frontmatter status: {status} -> {rel}/{md.name}")
            if not dry:
                _meta, body = parse_frontmatter(md, include_sidecar_config=False)
                write_vault_frontmatter(md, {"status": status}, body)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase-2", action="store_true", help="apply the spec-amendment map (MOVES_2)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    dry = args.dry_run
    vault = get_vault_dir()
    if args.phase_2:
        assert_phase1_done(vault)
        stamp_recipe_status(vault, dry)
        moves, empty_after = MOVES_2, EMPTY_AFTER_2
        renames: list[tuple[str, str]] = []
    else:
        moves, renames, empty_after = MOVES, RENAMES, EMPTY_AFTER
    for src, dst in moves:
        if (vault / src).exists():  # later entries may be emptied by earlier ones
            git_mv(vault, src, dst, dry)
    for src, dst in renames:
        git_mv(vault, src, dst, dry)
    assert_empty_then_remove(vault, empty_after, dry)
    print("done")


if __name__ == "__main__":
    main()
