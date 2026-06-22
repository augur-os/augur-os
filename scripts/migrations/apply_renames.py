"""Apply a rename map (old<TAB>new[<TAB>rationale]) with wikilink rewrite.

- git mode (vault): `git mv` + wikilink rewrite across every *.md outside
  _augur/.
- plain mode (docs store): Path.rename, refuse overwrite; vault-side links
  are rewritten when `extra_link_roots` is given (binaries are embedded from
  the vault via files/ links).

Link forms handled: stem form (`[[stem]]`, `[[stem|alias]]`, `[[stem#h]]`,
`![[stem]]`) and path-qualified form (`[[dir/stem]]`, `[[dir/stem|alias]]`,
... — with the .md suffix omitted, as Obsidian writes them). NOT handled:
full-filename embeds (`![[img.png]]`) and markdown-style `](path)` links —
callers must verify those independently (current vault has zero of either
in scope, verified 2026-06-12).

Safety guards:
- map entries may not contain ``\\``, ``[``, ``]``, ``|``, ``#`` or control
  characters (replacement is inserted literally via lambda, but reject early),
  nor be absolute or contain a ``..`` component (plain mode could escape the
  root);
- sources must be regular files (a directory in a map would corrupt
  unrelated [[note]] links);
- a rename is refused when the OLD stem matches more than one file across
  the link roots AND the stem is wikilink-referenced — rewriting `[[stem]]`
  would retarget links pointing at the other file. Unreferenced duplicates
  (common for images like image-4.png across topic dirs) proceed with a NOTE.

Note on _rewrite_links performance: for a 25-entry map over a 600-file vault
this is ~15 k file reads (25 renames × 600 files), plus one full file scan
per rename for the ambiguity guard. Acceptable for one-shot migration use;
do not call in hot loops.

Usage:
  uv run python scripts/migrations/apply_renames.py --root vault --map batch1.tsv --execute
  uv run python scripts/migrations/apply_renames.py --root docs  --map images.tsv --execute
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config.paths import get_documents_dir, get_vault_dir  # noqa: E402

_FORBIDDEN_CHARS = set("\\[]|#")


def _validate_entry(entry: str, line: str) -> str:
    if any(c in _FORBIDDEN_CHARS or ord(c) < 32 or ord(c) == 127 for c in entry):
        raise SystemExit(f"FATAL: forbidden character in map line: {line!r}")
    # Map files are posix-relative. `Path("/abs").is_absolute()` is False on
    # Windows (no drive), so also reject a leading "/" explicitly — an absolute
    # path must be rejected on every platform, not just where it has a drive.
    if entry.startswith("/") or Path(entry).is_absolute() or ".." in Path(entry).parts:
        raise SystemExit(f"FATAL: absolute or parent-escaping path in map line: {line!r}")
    return entry


def parse_map(path: Path) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            raise SystemExit(f"FATAL: bad map line: {line!r}")
        pairs.append((_validate_entry(parts[0].strip(), line),
                      _validate_entry(parts[1].strip(), line)))
    return pairs


def _strip_md(rel: Path) -> str:
    posix = rel.as_posix()
    return posix[:-3] if posix.endswith(".md") else posix


def _rewrite_links(root: Path, old_rel: Path, new_rel: Path, link_roots: list[Path]) -> int:
    """Rewrite Obsidian wikilinks for a renamed file across all *.md in link_roots.

    Rewrites BOTH forms, each anchored by a lookahead for ], |, or # so a stem
    that is a prefix of another stem (e.g. 'star' vs 'star-method') is never
    touched:
    - stem form:           [[old_stem]] / [[old_stem|alias]] / [[old_stem#h]] / ![[old_stem]]
    - path-qualified form: [[old/rel/path]] (.md suffix omitted) + alias/#/embed variants

    The embed prefix `!` survives because replacement starts at `[[`. The new
    name is inserted via a lambda so it is always literal — regex template
    escapes such as a `\\g` in a filename must never be interpreted.

    Note: reads every *.md in each root per rename call. For a 25-entry map
    over a 600-file vault this is ~15 k reads — acceptable for one-shot use.
    """
    old_stem, new_stem = old_rel.stem, new_rel.stem
    old_path, new_path = _strip_md(old_rel), _strip_md(new_rel)
    subs: list[tuple[re.Pattern[str], str]] = []
    if old_path != new_path:
        subs.append((re.compile(r"\[\[" + re.escape(old_path) + r"(?=[\]|#])"), new_path))
    if old_stem != new_stem and old_stem != old_path:
        subs.append((re.compile(r"\[\[" + re.escape(old_stem) + r"(?=[\]|#])"), new_stem))
    if not subs:
        return 0
    changed = 0
    for base in link_roots:
        for md in base.rglob("*.md"):
            if "_augur" in md.parts or md.is_symlink():
                continue
            text = md.read_text(encoding="utf-8")
            new_text = text
            for pattern, repl in subs:
                new_text = pattern.sub(lambda m, r=repl: "[[" + r, new_text)
            if new_text != text:
                md.write_text(new_text, encoding="utf-8")
                changed += 1
    return changed


def _files_with_stem(stem: str, link_roots: list[Path]) -> list[Path]:
    """All regular files matching `stem` across link_roots.

    Excludes _augur/, dot-dirs (.git, .obsidian), and symlinks (the vault's
    files/ links into the docs store) so the same file is never counted twice.
    """
    hits: list[Path] = []
    for base in link_roots:
        for p in base.rglob("*"):
            if p.is_symlink() or not p.is_file():
                continue
            rel_parts = p.relative_to(base).parts
            if "_augur" in rel_parts or any(part.startswith(".") for part in rel_parts):
                continue
            if p.stem == stem:
                hits.append(p)
    return hits


def _has_wikilink_refs(old_rel: Path, link_roots: list[Path]) -> bool:
    """True if any *.md outside _augur references old_rel by wikilink.

    Checks the same two forms the rewrite handles: stem (`[[stem` with the
    `(?=[\\]|#])` lookahead) and path-qualified (`[[<old_rel sans ext>` with
    the same lookahead).
    """
    forms = {old_rel.stem, old_rel.with_suffix("").as_posix()}
    patterns = [re.compile(r"\[\[" + re.escape(f) + r"(?=[\]|#])") for f in forms]
    for base in link_roots:
        for md in base.rglob("*.md"):
            if "_augur" in md.parts or md.is_symlink():
                continue
            text = md.read_text(encoding="utf-8")
            if any(p.search(text) for p in patterns):
                return True
    return False


def apply_map(root: Path, pairs: list[tuple[str, str]], *, use_git: bool,
              extra_link_roots: list[Path] | None = None, dry: bool = False) -> None:
    link_roots = [root] + (extra_link_roots or [])
    for old_rel, new_rel in pairs:
        src, dst = root / old_rel, root / new_rel
        if not src.exists():
            raise SystemExit(f"FATAL: missing {old_rel}")
        if not src.is_file():
            raise SystemExit(f"FATAL: not a regular file: {old_rel}")
        if dst.exists():
            raise SystemExit(f"FATAL: destination exists {new_rel}")
        stem_hits = _files_with_stem(src.stem, link_roots)
        if len(stem_hits) > 1:
            # Only fatal when the stem is actually link-referenced: rewriting
            # [[stem]] would retarget links aimed at the OTHER file. Unlinked
            # duplicates (e.g. image-4.png across topic dirs) are safe.
            if _has_wikilink_refs(Path(old_rel), link_roots):
                raise SystemExit(
                    f"FATAL: ambiguous stem {src.stem!r} for {old_rel} is link-referenced "
                    f"— matches {len(stem_hits)} files: {[str(h) for h in stem_hits]}"
                )
            print(f"NOTE: duplicate stem {src.stem} unreferenced — proceeding")
        print(("DRY  " if dry else "RUN  ") + f"{old_rel} -> {new_rel}")
        if dry:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if use_git:
            subprocess.run(["git", "mv", str(src), str(dst)], cwd=root, check=True)
        else:
            src.rename(dst)
        n = _rewrite_links(root, Path(old_rel), Path(new_rel), link_roots)
        if n:
            print(f"     rewrote links in {n} files")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", choices=["vault", "docs"], required=True)
    ap.add_argument("--map", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    root = get_vault_dir() if args.root == "vault" else get_documents_dir()
    extra = [get_vault_dir()] if args.root == "docs" else None
    apply_map(root, parse_map(Path(args.map)), use_git=(args.root == "vault"),
              extra_link_roots=extra, dry=args.dry_run)
    print("done")


if __name__ == "__main__":
    main()
