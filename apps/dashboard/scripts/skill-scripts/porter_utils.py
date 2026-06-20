"""
Skill Porter Utilities

Shared constants, path helpers, and low-level utility functions
used across the skill porter pipeline.
"""

from __future__ import annotations

import logging
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from subprocess import CompletedProcess, run as subprocess_run  # nosec B404
from typing import Any, Iterable

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGES_DIR = REPO_ROOT / "plugins"

IGNORED_DIRS = {
    ".git",
    ".github",
    ".venv",
    "node_modules",
    ".next",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "dist",
    "build",
}

IGNORED_FILENAMES = {".DS_Store"}
IGNORED_FILE_REGEXES = [
    re.compile(r"^\.env(\..*)?$"),
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "imported-skill"


def is_kebab_case(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value))


def run(cmd: list[str], cwd: Path | None = None) -> CompletedProcess[str]:
    return subprocess_run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
    )  # nosec B603


def safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def should_ignore_path(path: Path) -> bool:
    name = path.name
    if name in IGNORED_FILENAMES:
        return True
    for rx in IGNORED_FILE_REGEXES:
        if rx.match(name):
            return True
    return False


def iter_copy_candidates(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_dir():
            if p.name in IGNORED_DIRS:
                continue
            continue
        if any(part in IGNORED_DIRS for part in p.parts):
            continue
        if should_ignore_path(p):
            continue
        yield p


def safe_extract_zip(zip_path: Path, dest_dir: Path) -> None:
    safe_mkdir(dest_dir)
    with zipfile.ZipFile(zip_path) as zf:
        members = zf.infolist()
        if len(members) > 5000:
            raise RuntimeError("Zip contains too many files (limit: 5000)")

        for member in members:
            # ZipSlip protection.
            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise RuntimeError(f"Unsafe zip entry path: {member.filename}")

        zf.extractall(dest_dir)


def find_skill_md(root: Path) -> list[Path]:
    matches: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.name.lower() == "skill.md":
            matches.append(p)
    return matches


def choose_skill_md(paths: list[Path]) -> Path:
    if not paths:
        raise RuntimeError("No SKILL.md found in source")

    from porter_markdown import parse_frontmatter

    scored: list[tuple[int, int, Path]] = []
    for p in paths:
        raw: str | None = None
        try:
            raw = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.debug("Failed reading candidate SKILL.md at %s: %s", p, exc)
        if raw is None:
            continue
        fm, _, had = parse_frontmatter(raw)
        has_name = 1 if (had and isinstance(fm.get("name"), str) and fm.get("name")) else 0
        depth = len(p.parts)
        scored.append((has_name * 1000 - depth, -depth, p))

    if scored:
        scored.sort(reverse=True)
        return scored[0][2]

    # Fallback: shortest path.
    return sorted(paths, key=lambda p: len(p.parts))[0]
