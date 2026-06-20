"""Content-based vault sync discovery scanner.

Discovers all syncable files in the vault by scanning for ``sync_target:``
in YAML frontmatter.  Replaces path-based discovery with content-based
detection so vault files stay syncable regardless of directory moves.

See ADR-473 for design rationale.

Usage (library):
    from src.lib.sync_discover import discover_sync_items
    items = discover_sync_items()

Usage (CLI):
    python -m src.lib.sync_discover                   # table output
    python -m src.lib.sync_discover --json             # JSON output
    python -m src.lib.sync_discover --target notes     # filter by target
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess  # nosec B404
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from subprocess import CalledProcessError
from typing import Optional

logger = logging.getLogger(__name__)

# ─── constants ────────────────────────────────────────────────────────────────

KNOWN_TARGETS = frozenset({"notes", "reminders", "calendar"})


# ─── data model ───────────────────────────────────────────────────────────────


@dataclass
class SyncItem:
    """A vault file that declares itself as syncable via frontmatter."""

    path: Path
    sync_target: str  # "notes", "reminders", "calendar"
    title: str
    modified: datetime
    sync_folder: Optional[str] = None
    sync_list: Optional[str] = None
    sync_id: Optional[str] = None


# ─── vault root resolution ───────────────────────────────────────────────────


def _resolve_vault_root() -> Path:
    """Resolve vault root via src.config.paths, fallback to AUGUR_VAULT env."""
    try:
        from src.config.paths import get_vault_dir

        return get_vault_dir()
    except (ImportError, Exception):
        from src.config.path_primitives import resolve_vault_standalone

        return resolve_vault_standalone()


# ─── frontmatter parsing ─────────────────────────────────────────────────────


def _parse_frontmatter(filepath: Path) -> dict:
    """Parse only the YAML frontmatter header between --- markers.

    Returns the parsed frontmatter dict, or {} if no valid frontmatter.
    Does NOT read the full file body.
    """
    import yaml

    try:
        with filepath.open("r", encoding="utf-8") as f:
            first_line = f.readline()
            if first_line.strip() != "---":
                return {}

            lines: list[str] = []
            for line in f:
                if line.strip() == "---":
                    break
                lines.append(line)
            else:
                # Reached EOF without closing ---
                return {}

        fm_text = "".join(lines)
        if not fm_text.strip():
            return {}

        result = yaml.safe_load(fm_text)
        return result if isinstance(result, dict) else {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        logger.warning("Failed to parse frontmatter of %s: %s", filepath, e)
        return {}


# ─── subprocess-based candidate finding ──────────────────────────────────────


def _find_candidates_rg(vault_root: Path) -> list[str]:
    """Find .md files containing sync_target: at line start using ripgrep."""
    rg_path = shutil.which("rg")
    if not rg_path:
        return []

    try:
        result = subprocess.run(
            [rg_path, "-l", "^sync_target:", str(vault_root), "--glob", "*.md"],
            capture_output=True,
            text=True,
            timeout=30,
        )  # nosec B603
        if result.returncode in (0, 1):  # 1 = no matches
            return [p for p in result.stdout.strip().splitlines() if p]
    except (CalledProcessError, OSError, TimeoutError) as e:
        logger.warning("rg failed, will fall back to grep: %s", e)

    return []


def _find_candidates_grep(vault_root: Path) -> list[str]:
    """Fallback: find .md files containing sync_target: using grep."""
    grep_path = shutil.which("grep")
    if not grep_path:
        logger.error("Neither rg nor grep found on PATH")
        return []

    try:
        result = subprocess.run(
            [grep_path, "-rl", "^sync_target:", "--include=*.md", str(vault_root)],
            capture_output=True,
            text=True,
            timeout=60,
        )  # nosec B603
        if result.returncode in (0, 1):
            return [p for p in result.stdout.strip().splitlines() if p]
    except (CalledProcessError, OSError, TimeoutError) as e:
        logger.error("grep fallback also failed: %s", e)

    return []


def _find_candidates(vault_root: Path) -> list[Path]:
    """Find .md files containing sync_target: using rg, falling back to grep."""
    paths_str = _find_candidates_rg(vault_root)
    if not paths_str:
        paths_str = _find_candidates_grep(vault_root)
    return sorted(Path(p).resolve() for p in paths_str if p)


# ─── Python glob fallback ────────────────────────────────────────────────────


def _find_candidates_glob(vault_root: Path) -> list[Path]:
    """Pure-Python fallback: glob for .md files and check for sync_target."""
    candidates: list[Path] = []
    for md_file in vault_root.rglob("*.md"):
        try:
            # Read just enough to check frontmatter (first ~2KB)
            with md_file.open("r", encoding="utf-8") as f:
                head = f.read(2048)
            if head.startswith("---") and "sync_target:" in head:
                candidates.append(md_file.resolve())
        except (OSError, UnicodeDecodeError):
            continue
    return sorted(candidates)


# ─── main discovery API ──────────────────────────────────────────────────────


def discover_sync_items(vault_root: Path | None = None) -> list[SyncItem]:
    """Discover all syncable files in the vault via frontmatter scanning.

    Walks ``vault_root`` (defaults to ``get_vault_dir()``) looking for markdown
    files with ``sync_target`` in YAML frontmatter.  Uses ripgrep for fast
    scanning when available, falls back to grep, then to Python glob.

    Args:
        vault_root: Override vault root path.  Defaults to src.config.paths
            resolution (``get_vault_dir()``).

    Returns:
        List of SyncItem instances sorted by (sync_target, path).
    """
    root = vault_root or _resolve_vault_root()
    if not root.is_dir():
        logger.warning("Vault root does not exist: %s", root)
        return []

    # Try rg/grep first, fall back to pure Python glob
    candidates = _find_candidates(root)
    if not candidates:
        # rg/grep may have returned nothing — try glob as final fallback
        candidates = _find_candidates_glob(root)

    items: list[SyncItem] = []
    for filepath in candidates:
        if not filepath.is_file():
            continue

        fm = _parse_frontmatter(filepath)
        if not fm:
            continue

        target = fm.get("sync_target")
        if not target or not isinstance(target, str):
            continue

        target = target.strip()
        if target not in KNOWN_TARGETS:
            logger.warning("Unknown sync_target '%s' in %s, skipping", target, filepath)
            continue

        # Get file modification time
        try:
            mtime = filepath.stat().st_mtime
            modified = datetime.fromtimestamp(mtime, tz=timezone.utc)
        except OSError:
            modified = datetime.now(tz=timezone.utc)

        items.append(
            SyncItem(
                path=filepath,
                sync_target=target,
                title=fm.get("title", filepath.stem),
                modified=modified,
                sync_folder=fm.get("sync_folder"),
                sync_list=fm.get("sync_list"),
                sync_id=fm.get("sync_id"),
            )
        )

    items.sort(key=lambda i: (i.sync_target, str(i.path)))
    return items


# ─── CLI ──────────────────────────────────────────────────────────────────────


def main() -> int:
    """CLI entry point for vault discovery scanner."""
    parser = argparse.ArgumentParser(description="Discover syncable vault files")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--target",
        choices=sorted(KNOWN_TARGETS),
        help="Filter by sync target",
    )
    parser.add_argument("--vault-root", type=Path, help="Override vault root path")
    args = parser.parse_args()

    items = discover_sync_items(vault_root=args.vault_root)
    if args.target:
        items = [i for i in items if i.sync_target == args.target]

    if args.json:
        print(
            json.dumps(
                [{**asdict(i), "path": str(i.path), "modified": i.modified.isoformat()} for i in items],
                indent=2,
            )
        )
    else:
        if not items:
            print("No syncable files found.")
            return 0
        print(f"{'Target':<12} {'Title':<30} {'Path'}")
        print(f"{'─' * 12} {'─' * 30} {'─' * 50}")
        for item in items:
            print(f"{item.sync_target:<12} {item.title:<30} {item.path}")
        print(f"\nTotal: {len(items)} syncable files")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
