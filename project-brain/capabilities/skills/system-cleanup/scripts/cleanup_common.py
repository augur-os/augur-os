"""Shared category config, sizing helpers, and safety guards for system-cleanup.

Safety contract (documented in SKILL.md):
- Scans are read-only and side-effect-free.
- Execution moves items to the OS Trash via send2trash — reversible by design,
  never ``rm -rf`` / ``shutil.rmtree`` / ``unlink``.
- Protected roots are never trashed: the Augur repo, the configured vault and
  documents stores, ``~/Documents``, the home directory itself, and anything
  outside the user's home.
- The ``trash`` category is report-only: emptying the OS Trash is not
  reversible, so this skill never does it (use Finder's Empty Trash).
"""
from __future__ import annotations

import subprocess  # nosec B404
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Project bootstrap (mirrors validator/scripts/bootstrap_paths.py)
# ---------------------------------------------------------------------------

def find_project_root(start_file: str | Path = __file__) -> Path:
    """Find the Augur project root by repo landmarks."""
    start = Path(start_file).resolve()
    for candidate in (start.parent, *start.parents):
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "src" / "config" / "paths.py").is_file()
        ):
            return candidate
    raise RuntimeError(f"Unable to locate Augur project root from {start}")


def _ensure_project_on_path() -> Path:
    root = find_project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


# ---------------------------------------------------------------------------
# Category configuration (ported from the staged r3 draft)
# ---------------------------------------------------------------------------

# Path-based categories. Scans enumerate direct children (or glob matches);
# execution trashes individual scanned items, never the category root.
CATEGORY_PATHS: dict[str, list[str]] = {
    "browser-caches": [
        "~/Library/Caches/com.apple.Safari",
        "~/Library/Caches/Google/Chrome",
        "~/Library/Caches/Firefox",
        "~/Library/Caches/com.google.Chrome",
        "~/Library/Caches/org.mozilla.firefox",
    ],
    "app-caches": ["~/Library/Caches"],
    "system-logs": ["~/Library/Logs"],
    "trash": ["~/.Trash"],  # report-only: never executed (see REPORT_ONLY_CATEGORIES)
    "downloads-installers": [
        "~/Downloads/*.dmg",
        "~/Downloads/*.pkg",
        "~/Downloads/*.zip",
    ],
    "xcode-derived": [
        "~/Library/Developer/Xcode/DerivedData",
        "~/Library/Developer/Xcode/Archives",
        "~/Library/Developer/Xcode/iOS DeviceSupport",
    ],
    "gemini-antigravity": [
        "~/.gemini/antigravity/browser_recordings",
        "~/.gemini/antigravity-browser-profile",
        "~/Library/Application Support/Antigravity",
    ],
    "dev-caches": [
        "~/.cache/whisper",
        "~/Library/Caches/ms-playwright",
    ],
}

# Computed categories (scanned, not path-listed): dev-artifacts, large-files.
COMPUTED_CATEGORIES = ("dev-artifacts", "large-files")

# Categories that are scanned and reported but never executed.
REPORT_ONLY_CATEGORIES = frozenset({"trash"})

DEV_ARTIFACT_NAMES = frozenset([
    "node_modules", ".venv", "venv", "target", "dist", "build",
    "__pycache__", ".pytest_cache", ".next", ".turbo",
])

DEV_SCAN_ROOTS = [
    "~/Projects",
    "~/Developer",
    "~/Code",
    "~/repos",
    "~/src",
    "~/work",
]

LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100 MB

# ~/Documents was in the staged draft but is a protected root (never trashed),
# so it is excluded from the scan dirs as well — scan results must stay
# actionable.
LARGE_FILE_SCAN_DIRS = [
    "~/Downloads",
    "~/Desktop",
]


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_bytes(b: float) -> str:
    """Human-readable byte size."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def dir_size(path: Path) -> tuple[int, int]:
    """Return (total_bytes, item_count) for a directory via rglob."""
    total = 0
    count = 0
    try:
        if path.is_file():
            return path.stat().st_size, 1
        for entry in path.rglob("*"):
            try:
                if entry.is_file():
                    total += entry.stat().st_size
                    count += 1
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        pass
    return total, count


def dir_size_fast(path: Path) -> tuple[int, int]:
    """Fast directory size using du on macOS/Linux, falling back to rglob."""
    try:
        result = subprocess.run(  # nosec B603
            ["du", "-sk", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            kb = int(result.stdout.split()[0])
            return kb * 1024, 1
    except (subprocess.TimeoutExpired, ValueError, IndexError, OSError):
        pass
    return dir_size(path)


def walk_limited(root: Path, max_depth: int) -> list[Path]:
    """Walk a directory tree up to max_depth levels, returning all entries."""
    results: list[Path] = []
    queue: list[tuple[Path, int]] = [(root, 0)]
    while queue:
        current, depth = queue.pop(0)
        if depth > max_depth:
            continue
        try:
            for entry in current.iterdir():
                results.append(entry)
                if entry.is_dir() and depth < max_depth:
                    # Don't descend into artifact dirs themselves
                    if entry.name not in DEV_ARTIFACT_NAMES:
                        queue.append((entry, depth + 1))
        except (PermissionError, OSError):
            continue
    return results


# ---------------------------------------------------------------------------
# Safety guards
# ---------------------------------------------------------------------------

def protected_roots() -> list[Path]:
    """Roots that must never be trashed: repo, vault, documents, ~/Documents."""
    roots: list[Path] = [find_project_root().resolve()]
    _ensure_project_on_path()
    try:
        from src.config.paths import get_documents_dir, get_vault_dir
        for helper in (get_vault_dir, get_documents_dir):
            try:
                roots.append(Path(helper()).resolve())
            except Exception:
                # Unconfigured store on this machine; the base guards
                # (repo, home root, ~/Documents, outside-home) still apply.
                continue
    except ImportError:
        pass
    roots.append((Path.home() / "Documents").resolve())
    return roots


def is_protected(
    path: Path | str,
    roots: list[Path] | None = None,
    home: Path | None = None,
) -> bool:
    """True when a path must never be trashed.

    Protected: the home directory itself, anything outside the user's home,
    and anything at or under a protected root (repo, vault, documents stores,
    ~/Documents).
    """
    resolved = Path(path).resolve()
    home_resolved = (home or Path.home()).resolve()
    if resolved == home_resolved:
        return True
    if home_resolved not in resolved.parents:
        return True
    for root in (roots if roots is not None else protected_roots()):
        if resolved == root or root in resolved.parents:
            return True
    return False


# ---------------------------------------------------------------------------
# Reversible delete (prior art: file-manager-augur scripts/trash.py)
# ---------------------------------------------------------------------------

def send_to_trash(path: Path | str) -> dict:
    """Move one file/dir to the OS Trash. Returns a result dict; never raises."""
    p = Path(path)
    if not p.exists() and not p.is_symlink():
        return {"path": str(p), "trashed": False, "reversible": True,
                "error": "file not found"}
    try:
        from send2trash import send2trash as _send2trash
    except ImportError as exc:  # pragma: no cover - env-dependent
        return {"path": str(p), "trashed": False, "reversible": True,
                "error": f"send2trash unavailable: {exc}"}
    try:
        _send2trash(str(p))
        return {"path": str(p), "trashed": True, "reversible": True, "error": None}
    except Exception as exc:
        return {"path": str(p), "trashed": False, "reversible": True,
                "error": str(exc)}
