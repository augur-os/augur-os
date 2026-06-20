"""One-shot Au-vault reorganization to the domains layout (spec 2026-06-12).

Archive-first: nothing is deleted; everything removed from view moves to
_augur/archive/2026-06-12-pre-reorg/. Uses `git mv` (vault is a git repo).

Usage:
  uv run python scripts/migrations/vault_reorg_2026_06_12.py --dry-run
  uv run python scripts/migrations/vault_reorg_2026_06_12.py --execute
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config.paths import get_vault_dir  # noqa: E402

ARCHIVE = "_augur/archive/2026-06-12-pre-reorg"

# (src_relative, dst_relative) — order matters; dirs first, then knowledge lift.
TOP_MOVES = [
    ("drafts", "_augur/drafts"),
    ("capabilities", "_augur/capabilities"),
    ("config", "_augur/config"),
    ("memory", "_augur/memory"),
    ("prompts", "_augur/prompts"),
    ("activity", "_augur/activity"),
    ("decisions", "_augur/decisions"),
    ("instructions", "_augur/instructions"),
    ("voice-memos", "_augur/voice-memos"),
    ("system", "_augur/system"),              # machine config (pins.yaml)
    ("integrations", "_augur/integrations"),  # machine config (onboard CLI scan yaml)
    ("knowledge", "_augur/knowledge"),  # notes/wiki/sources lifted back out below
]

LIFT_MOVES = [
    ("_augur/knowledge/wiki", "wiki"),
    ("_augur/knowledge/sources", "sources"),
    # domain folders out of the old notes root
    ("_augur/knowledge/notes/venture", "venture"),
    ("_augur/knowledge/notes/lifestyle", "lifestyle"),
    ("_augur/knowledge/notes/books", "books"),
    ("_augur/knowledge/notes/finance", "finance"),
    ("_augur/knowledge/notes/health", "health"),
    ("_augur/knowledge/notes/augur", "augur"),
    # merges
    ("_augur/knowledge/notes/reading-list", "books"),       # merge into books/
    ("_augur/knowledge/notes/jobs", "career/pipeline"),     # merge
    # archives (user-approved)
    ("_augur/knowledge/notes/demo", f"{ARCHIVE}/demo"),
    ("_augur/knowledge/notes/examples", f"{ARCHIVE}/examples"),
]

# career restructure (spec career tree)
CAREER_MOVES = [
    ("_augur/knowledge/notes/career/cv.md", "career/cv.md"),
    ("_augur/knowledge/notes/career/interview-prep/story-bank.md", "career/interview/story-bank.md"),
    ("_augur/knowledge/notes/career/growth/notion-career-growth-tell-me-about-yourself.md", "career/interview/tell-me-about-yourself.md"),
    ("_augur/knowledge/notes/career/growth/notion-career-growth-how-to-interview.md", "career/interview/how-to-interview.md"),
    ("_augur/knowledge/notes/career/growth/notion-career-growth-salary-negotiation.md", "career/interview/salary-negotiation.md"),
    ("_augur/knowledge/notes/career/growth/notion-career-growth-tech-interview-prep-embedded.md", "career/interview/tech-review.md"),
    ("_augur/knowledge/notes/career/hard-skills", "career/skills"),
    ("_augur/knowledge/notes/career/learning/scoring-formulas.md", "career/pipeline/scoring-formulas.md"),
    ("_augur/knowledge/notes/career/data", "career/pipeline"),       # contents merged
    ("_augur/knowledge/notes/career/sessions", "career/pipeline"),
    ("_augur/knowledge/notes/career/proposals", "career/pipeline"),
    ("_augur/knowledge/notes/career/output", "career"),              # cv variants to domain root
    ("_augur/knowledge/notes/career/growth", "career/growth"),       # remaining growth notes
]

# loose files in old notes root: test artifacts → archive, everything else → inbox/
TEST_ARTIFACT_MARKERS = ("-verification", "adr-751-", "adr-752-", "iana", "example-domain")

EMPTY_SCAFFOLD = ["workflows", "specs", "reports", "policies", "plans", "dev", "archive"]

STRIP_PREFIXES = ("notion-career-growth-", "notion-soft-skills-", "notion-priority-dashboard-", "notion-")


def run(cmd: list[str], cwd: Path, dry: bool) -> None:
    print(("DRY  " if dry else "RUN  ") + " ".join(cmd))
    if not dry:
        subprocess.run(cmd, cwd=cwd, check=True)


MACHINE_PREFIX = "_augur/"

# Dry-run simulation registry: vault-relative paths at their post-move
# locations, populated as moves are previewed so that later dir merges and
# name collisions surface in the preview instead of at execute time.
_SIM: dict[str, set[str]] = {"files": set(), "dirs": set()}


def reset_sim() -> None:
    _SIM["files"].clear()
    _SIM["dirs"].clear()


def _tracked_count(vault: Path, rel: str) -> int:
    out = subprocess.run(
        ["git", "ls-files", "--", rel],
        cwd=vault,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return sum(1 for line in out.splitlines() if line.strip())


def _real_files(root: Path) -> list[Path]:
    return [
        p
        for p in root.rglob("*")
        if p.is_file() and p.name not in (".DS_Store", ".gitkeep")
    ]


def _record_sim_dir_move(source: Path, dst: str) -> None:
    _SIM["dirs"].add(dst)
    for p in _real_files(source):
        _SIM["files"].add(f"{dst}/{p.relative_to(source)}")


def _sim_dst_dir_exists(dst: str) -> bool:
    prefix = dst + "/"
    return dst in _SIM["dirs"] or any(f.startswith(prefix) for f in _SIM["files"])


def git_mv(vault: Path, src: str, dst: str, dry: bool) -> None:
    s, d = vault / src, vault / dst
    note = ""
    if dry and not s.exists() and src.startswith(MACHINE_PREFIX):
        # Honest dry-run: before --execute the TOP_MOVES have not happened, so
        # post-top-move sources under _augur/ do not exist yet. Preview the
        # move from the equivalent PRE-move path instead of printing SKIP.
        pre = src[len(MACHINE_PREFIX):]
        if (vault / pre).exists():
            s = vault / pre
            note = f" (post-top-move path: {src})"
    if not s.exists():
        print(f"SKIP missing {src}")
        return

    if s.is_dir():
        # Trackless dir sources crash `git mv` (exit 128) — handle them first.
        if _tracked_count(vault, str(s.relative_to(vault))) == 0:
            real = _real_files(s)
            if not real:
                # Scaffold husk: no tracked and no real untracked files.
                # Remove it; the domains skeleton owns the _augur structure.
                print(("DRY  " if dry else "") + f"EMPTY-HUSK remove {src} (no tracked or untracked files)")
                if not dry:
                    shutil.rmtree(s)
                return
            print(f"WARN  untracked content moved outside git: {src} -> {dst} ({len(real)} files)")
            if d.exists() or (dry and _sim_dst_dir_exists(dst)):
                raise RuntimeError(f"ABORT: destination already exists for untracked move: {dst}")
            if dry:
                _record_sim_dir_move(s, dst)
                print(f"DRY  shutil.move {s} {d}{note}")
            else:
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(s), str(d))
                print(f"RUN  shutil.move {s} {d}")
            return

        dst_is_dir = d.exists() and d.is_dir()
        if dry and not dst_is_dir:
            dst_is_dir = _sim_dst_dir_exists(dst)
        if dst_is_dir:
            # Merge: recurse per child (also in the dry preview, so name
            # collisions surface in the preview rather than at execute time).
            for child in sorted(s.iterdir()):
                if child.name == ".DS_Store":
                    continue
                git_mv(vault, f"{src}/{child.name}", f"{dst}/{child.name}", dry)
            return

        if dry:
            _record_sim_dir_move(s, dst)
            print(f"DRY  git mv {s} {d}{note}")
            return
        d.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "mv", str(s), str(d)], vault, dry)
        return

    # File source: keep plain `git mv` (an untracked file source aborts the
    # script via check=True — atomicity-by-abort is intended).
    if dry:
        if dst in _SIM["files"] or d.exists():
            print(f"COLLISION (execute would abort): {dst} already exists; cannot move {src}")
        _SIM["files"].add(dst)
        print(f"DRY  git mv {s} {d}{note}")
        return
    d.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "mv", str(s), str(d)], vault, dry)


def manifest(vault: Path) -> dict:
    files = sorted(
        str(p.relative_to(vault))
        for p in vault.rglob("*")
        if p.is_file()
        and ".git" not in p.parts
        and p.name != ".DS_Store"
        and "migration-before" not in p.name
        and "migration-after" not in p.name
    )
    return {"count": len(files), "files": files}


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    dry = args.dry_run
    vault = get_vault_dir()
    reset_sim()

    before = manifest(vault)
    if not dry:
        (vault / "_augur").mkdir(exist_ok=True)
        (vault / "_augur" / "migration-before.json").write_text(json.dumps(before, indent=1))

    for src, dst in TOP_MOVES:
        git_mv(vault, src, dst, dry)
    for src, dst in LIFT_MOVES:
        git_mv(vault, src, dst, dry)
    for src, dst in CAREER_MOVES:
        git_mv(vault, src, dst, dry)

    # strip ugly prefixes inside career/growth
    growth = vault / "career" / "growth"
    moved_out: set[str] = set()
    if dry and not growth.is_dir():
        # Pre-move preview: growth still sits under the old notes root; the
        # interview files CAREER_MOVES pulls out of it must not be renamed here.
        pre_growth = vault / "knowledge" / "notes" / "career" / "growth"
        if pre_growth.is_dir():
            growth = pre_growth
            moved_out = {
                Path(s).name
                for s, _ in CAREER_MOVES
                if s.startswith("_augur/knowledge/notes/career/growth/")
            }
    if growth.is_dir():
        for f in sorted(growth.glob("*.md")):
            if f.name in moved_out:
                continue
            new = f.name
            for pre in STRIP_PREFIXES:
                if new.startswith(pre):
                    new = new[len(pre):]
                    break
            if new != f.name and not (growth / new).exists():
                run(["git", "mv", str(f), str(vault / "career" / "growth" / new)], vault, dry)

    # loose notes in the old notes root
    notes_root = vault / "_augur" / "knowledge" / "notes"
    if dry and not notes_root.is_dir():
        notes_root = vault / "knowledge" / "notes"  # pre-move preview
    if notes_root.is_dir():
        for f in sorted(notes_root.glob("*.md")):
            rel = str(f.relative_to(vault))
            if any(m in f.name for m in TEST_ARTIFACT_MARKERS):
                git_mv(vault, rel, f"{ARCHIVE}/loose-notes/{f.name}", dry)
            else:
                git_mv(vault, rel, f"inbox/{f.name}", dry)

    # leftover career folder fragments → archive (must inspect manually if non-empty)
    leftover = vault / "_augur" / "knowledge" / "notes"
    if leftover.is_dir() and not dry:
        remaining = [p for p in leftover.rglob("*") if p.is_file() and p.name != ".DS_Store"]
        if remaining:
            print(f"WARNING: {len(remaining)} files left under old notes root — resolve before commit:")
            for p in remaining:
                print("  ", p.relative_to(vault))

    # Dry-run equivalent: simulate which files under the (pre-move) notes root
    # are NOT covered by any move map — these would be the execute-time leftovers.
    if dry:
        pre_notes = vault / "knowledge" / "notes"
        if pre_notes.is_dir():
            covered = [
                src[len(MACHINE_PREFIX):]
                for src, _ in LIFT_MOVES + CAREER_MOVES
                if src.startswith(f"{MACHINE_PREFIX}knowledge/notes/")
            ]
            stranded = []
            for p in sorted(pre_notes.rglob("*")):
                if not p.is_file() or p.name == ".DS_Store":
                    continue
                rel = str(p.relative_to(vault))
                if p.parent == pre_notes and p.suffix == ".md":
                    continue  # loose note — classified to inbox/archive above
                if any(rel == c or rel.startswith(c + "/") for c in covered):
                    continue
                stranded.append(rel)
            if stranded:
                print(f"DRY-WARNING: {len(stranded)} files would remain under old notes root after all moves:")
                for r in stranded:
                    print("  ", r)

    # empty scaffold dirs (verify empty, then plain remove — nothing to archive)
    for name in EMPTY_SCAFFOLD:
        d = vault / name
        if d.is_dir():
            contents = [p for p in d.rglob("*") if p.is_file() and p.name not in (".DS_Store", ".gitkeep")]
            if contents:
                print(f"NOT EMPTY, skipping removal: {name} ({len(contents)} files)")
            elif dry:
                print(f"DRY  would remove empty scaffold: {name}/")
            else:
                run(["rm", "-rf", str(d)], vault, dry)  # empty scaffolding only, verified above

    # Summary count of files per top-level destination (so operator can eyeball the result)
    print(
        "\n--- DRY-RUN: current file distribution (pre-move snapshot; final shown on --execute) ---"
        if dry
        else "\n--- file distribution per top-level destination ---"
    )
    dest_counts: dict[str, int] = {}
    for p in vault.rglob("*"):
        if not p.is_file() or ".git" in p.parts or p.name == ".DS_Store":
            continue
        rel = p.relative_to(vault)
        top = rel.parts[0] if len(rel.parts) > 1 else "<root>"
        dest_counts[top] = dest_counts.get(top, 0) + 1
    for top in sorted(dest_counts):
        print(f"  {top}: {dest_counts[top]} files")

    if not dry:
        after = manifest(vault)
        (vault / "_augur" / "migration-after.json").write_text(json.dumps(after, indent=1))
        print(f"before={before['count']} after={after['count']}")
        if before["count"] != after["count"]:
            print("FATAL: file count changed — investigate before committing.")
            sys.exit(1)
        # declare the new layout
        brain_yaml = vault / "BRAIN.yaml"
        text = brain_yaml.read_text(encoding="utf-8")
        if "layout:" not in text:
            brain_yaml.write_text(text.rstrip() + "\nlayout: domains\n", encoding="utf-8")
            print("NOTE: restart the Augur daemon/watcher — brain_layout is cached per-process")
    print("done")


if __name__ == "__main__":
    main()
