"""
Phase 1: Build rename map from git history.

Detects directory renames via git log, combines with hardcoded known renames,
resolves chains (A->B, B->C to A->C), and filters out still-existing paths.
"""

from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path

try:
    from .stale_config import KNOWN_RENAMES
except ImportError:
    from stale_config import KNOWN_RENAMES


def get_project_root() -> Path:
    """Get project root via git or file location."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        return Path(__file__).parent.parent.parent


def _resolve_chains(rename_map: dict[str, str]) -> dict[str, str]:
    """
    Resolve rename chains to their final destination.

    If A -> B and B -> C exist, produce A -> C (and keep B -> C).
    Prevents stale intermediate targets like factory -> crew when
    crew -> dev also exists.
    """
    resolved: dict[str, str] = {}
    for old, new in rename_map.items():
        # Follow the chain up to 10 hops to avoid infinite loops
        target = new
        for _ in range(10):
            next_target = None
            for k, v in rename_map.items():
                if k == old:
                    continue
                if target.rstrip("/").startswith(k.rstrip("/")):
                    next_target = target.replace(
                        k.rstrip("/"), v.rstrip("/"), 1
                    )
                    break
            if next_target and next_target != target:
                target = next_target
            else:
                break
        resolved[old] = target
    return resolved


def _filter_existing_sources(
    rename_map: dict[str, str], project_root: Path
) -> dict[str, str]:
    """
    Remove entries where the old path still exists on disk as a
    populated directory -- these are not stale, both dirs coexist.

    Also remove entries where old == new after chain resolution.

    IMPORTANT: Skill-level renames (plugins/X/skills/Y) are NEVER
    filtered out even if the parent hub directory (plugins/X/) still
    exists. This is because hub rebalancing moves individual skills
    between hubs -- the parent hub stays but the specific skill is gone.
    """
    filtered: dict[str, str] = {}
    for old, new in rename_map.items():
        # Drop identity mappings
        if old.rstrip("/") == new.rstrip("/"):
            continue

        old_abs = project_root / old.rstrip("/")

        # Skill-level renames: always keep, check the specific path
        if "/skills/" in old:
            if old_abs.is_dir():
                continue
            filtered[old] = new
            continue

        # Hub/directory-level renames: check if populated
        if old_abs.is_dir():
            try:
                children = list(old_abs.iterdir())
                real = [c for c in children if c.name not in {
                    "__pycache__", ".DS_Store", "__init__.py",
                }]
                if real:
                    continue
            except PermissionError:
                continue

        filtered[old] = new
    return filtered


def build_rename_map(project_root: Path) -> tuple[dict[str, str], int]:
    """
    Build a mapping of old directory paths to new paths.

    Combines git history analysis with hardcoded known renames.
    Git history is filtered to only detect renames within plugins/
    to avoid false positives from ancient data/ restructuring.

    Post-processing:
    - Resolves chains (A->B, B->C becomes A->C)
    - Filters out entries where old path still exists on disk

    Returns:
        (rename_map, git_renames_count)
    """
    raw_map = dict(KNOWN_RENAMES)
    git_count = 0

    try:
        result = subprocess.run(
            ["git", "log", "--all", "--diff-filter=R",
             "--name-status", "--format=", "-500"],
            capture_output=True, text=True, cwd=project_root,
        )

        dir_moves: Counter[tuple[str, str]] = Counter()
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line or not line.startswith("R"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            old_path, new_path = parts[1], parts[2]

            if not (old_path.startswith("plugins/") or old_path.startswith("src/")):
                continue

            old_dir = str(Path(old_path).parent) + "/"
            new_dir = str(Path(new_path).parent) + "/"
            if old_dir != new_dir:
                dir_moves[(old_dir, new_dir)] += 1

        for (old_dir, new_dir), count in dir_moves.items():
            if count < 5:
                continue
            old_parts = old_dir.rstrip("/").split("/")
            new_parts = new_dir.rstrip("/").split("/")

            if len(old_parts) < 2 or len(new_parts) < 2:
                continue

            common_len = 0
            for a, b in zip(old_parts, new_parts):
                if a == b:
                    common_len += 1
                else:
                    break
            if common_len < len(old_parts):
                old_prefix = "/".join(old_parts[:common_len + 1]) + "/"
                new_prefix = "/".join(new_parts[:common_len + 1]) + "/"
                if old_prefix != new_prefix and old_prefix not in raw_map:
                    raw_map[old_prefix] = new_prefix
                    git_count += 1

    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Post-process: filter, resolve chains, filter again
    filtered = _filter_existing_sources(raw_map, project_root)
    filtered = _resolve_chains(filtered)
    filtered = _filter_existing_sources(filtered, project_root)

    return filtered, git_count
