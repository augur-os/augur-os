"""Path self-discovery engine.

When a configured vault or documents path doesn't exist, this module
scans for marker files (.augur-vault, .augur-docs) and falls back to
structure fingerprinting.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_MARKERS = {
    "vault": ".augur-vault",
    "documents": ".augur-docs",
}

_discovery_cache: dict[str, Optional[Path]] = {}

_DEFAULT_MAX_CANDIDATES = 100
_DEFAULT_TIMEOUT_SECS = 5.0


def default_search_roots(configured: Path) -> list[Path]:
    """Build default scan locations from the configured (stale) path."""
    roots: list[Path] = []
    if configured.parent.exists():
        roots.append(configured.parent)
    roots.append(Path.home())
    docs = Path.home() / "Documents"
    if docs.exists():
        roots.append(docs)
    desktop = Path.home() / "Desktop"
    if desktop.exists():
        roots.append(desktop)
    return roots


def _is_vault_fingerprint(candidate: Path, skills_dir: Optional[Path] = None) -> bool:
    """Check if a directory looks like a vault by structure."""
    if not (candidate / "memory").is_dir():
        return False
    if skills_dir and skills_dir.is_dir():
        try:
            skill_names = {d.name for d in skills_dir.iterdir() if d.is_dir()}
        except OSError:
            skill_names = set()
        if skill_names:
            matching = 0
            for d in candidate.iterdir():
                if d.is_dir() and d.name in skill_names:
                    matching += 1
                    if matching >= 3:
                        return True
            return False
    return (candidate / "dev").is_dir() and (candidate / "config").is_dir()


def _is_docs_fingerprint(candidate: Path, skills_dir: Optional[Path] = None) -> bool:
    """Check if a directory looks like a documents root."""
    if not candidate.is_dir():
        return False
    subdirs = [d for d in candidate.iterdir() if d.is_dir()]
    if len(subdirs) < 2:
        return False
    if skills_dir and skills_dir.is_dir():
        try:
            skill_names = {d.name for d in skills_dir.iterdir() if d.is_dir()}
        except OSError:
            skill_names = set()
        if skill_names:
            subdirs = [d for d in subdirs if d.name in skill_names]
            if len(subdirs) < 2:
                return False
    for subdir in subdirs[:5]:
        for f in subdir.iterdir():
            if f.is_file() and f.suffix in {".pdf", ".docx", ".xlsx", ".pptx", ".zip"}:
                return True
    return False


def discover_path(
    path_type: str,
    configured: Path,
    search_roots: Optional[list[Path]] = None,
    skills_dir: Optional[Path] = None,
    max_candidates: int = _DEFAULT_MAX_CANDIDATES,
    timeout_secs: float = _DEFAULT_TIMEOUT_SECS,
) -> Optional[Path]:
    """Discover a moved vault or documents directory."""
    if path_type in _discovery_cache:
        return _discovery_cache[path_type]

    marker_name = _MARKERS.get(path_type)
    if not marker_name:
        _discovery_cache[path_type] = None
        return None

    roots = search_roots or default_search_roots(configured)
    fingerprint_fn = _is_vault_fingerprint if path_type == "vault" else _is_docs_fingerprint

    candidates_checked = 0
    start_time = time.monotonic()

    # Skip heavy system dirs during level-2 recursion
    _SKIP_LEVEL2 = {
        "Library",
        "Applications",
        "Music",
        "Movies",
        "Pictures",
        "Photos",
        "node_modules",
        ".Trash",
        "go",
        ".cargo",
        ".rustup",
    }

    def _collect_candidates() -> list[Path]:
        """Collect all candidate directories (2 levels deep) within budget."""
        nonlocal candidates_checked
        result: list[Path] = []
        for root in roots:
            if not root.is_dir():
                continue
            try:
                children = sorted(root.iterdir())
            except OSError:
                continue
            for child in children:
                if not child.is_dir() or child.name.startswith("."):
                    continue
                candidates_checked += 1
                if candidates_checked > max_candidates or time.monotonic() - start_time > timeout_secs:
                    return result
                result.append(child)
                # Level 2: recurse into non-system dirs
                if child.name in _SKIP_LEVEL2:
                    continue
                try:
                    grandchildren = sorted(child.iterdir())
                except OSError:
                    continue
                for grandchild in grandchildren:
                    if not grandchild.is_dir() or grandchild.name.startswith("."):
                        continue
                    candidates_checked += 1
                    if candidates_checked > max_candidates or time.monotonic() - start_time > timeout_secs:
                        return result
                    result.append(grandchild)
        return result

    candidates = _collect_candidates()

    # Pass 1: marker files only (authoritative, no false positives)
    for candidate in candidates:
        if (candidate / marker_name).is_file():
            logger.info(
                "%s not found at %s. Found at %s (marker file).",
                path_type,
                configured,
                candidate,
            )
            _discovery_cache[path_type] = candidate
            return candidate

    # Pass 2: fingerprint heuristic (fallback if no marker found)
    for candidate in candidates:
        if fingerprint_fn(candidate, skills_dir=skills_dir):
            logger.info(
                "%s not found at %s. Found at %s (structure match).",
                path_type,
                configured,
                candidate,
            )
            _discovery_cache[path_type] = candidate
            return candidate

    if candidates_checked >= max_candidates:
        logger.warning(
            "Discovery budget exhausted (%d candidates) without finding %s",
            max_candidates,
            path_type,
        )
    elif time.monotonic() - start_time > timeout_secs:
        logger.warning(
            "Discovery timeout (%.1fs) without finding %s",
            timeout_secs,
            path_type,
        )

    _discovery_cache[path_type] = None
    return None


def prompt_update(path_type: str, old_path: Path, new_path: Path) -> bool:
    """Prompt the user to update project.yaml if running interactively."""
    if not sys.stdin.isatty():
        logger.warning(
            "%s config stale: configured %s, using discovered %s. " "Run 'augur config fix' to update project.yaml.",
            path_type,
            old_path,
            new_path,
        )
        return False

    print(f"\n{path_type.title()} not found at: {old_path}")
    print(f"Discovered at:  {new_path}")
    try:
        answer = input("Update project.yaml? (y/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("y", "yes")


def update_project_yaml(key: str, new_path: Path) -> None:
    """Atomically update a single path in project.yaml."""
    import tempfile

    import yaml

    from src.config.paths import get_project_root, invalidate_project_cache

    project_yaml = get_project_root() / "project.yaml"
    data = yaml.safe_load(project_yaml.read_text(encoding="utf-8")) or {}
    if "paths" not in data or not isinstance(data["paths"], dict):
        data["paths"] = {}
    data["paths"][key] = str(new_path)

    tmp_fd, tmp_path = tempfile.mkstemp(dir=project_yaml.parent, suffix=".yaml")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp_path, project_yaml)
    except BaseException:
        os.unlink(tmp_path)
        raise

    invalidate_project_cache()
    logger.info("Updated project.yaml: paths.%s = %s", key, new_path)


def create_marker(path_type: str, directory: Path) -> None:
    """Create a discovery marker file in the given directory."""
    marker_name = _MARKERS.get(path_type)
    if not marker_name:
        return
    marker = directory / marker_name
    if marker.exists():
        return
    try:
        from src.config.paths import get_project_name

        project_name = get_project_name()
    except ImportError:
        project_name = "Augur"
    marker.write_text(f"project: {project_name}\ncreated: {date.today().isoformat()}\n")
    logger.info("Created %s marker at %s", path_type, marker)
