"""Git safety helpers — commit, verify build, revert on failure, blacklist."""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import json
import subprocess
import time
from pathlib import Path

from src.config.paths import get_runtime_dir

# Revert blacklist: tracks (skill_name, change_type) -> cooldown expiry.
# Prevents commit-revert oscillation where the same fix is attempted and
# reverted on every cycle.
_BLACKLIST_FILENAME = "skill-quality-revert-blacklist.json"
_COOLDOWN_SECONDS = 86400  # 24 hours
_MAX_REVERTS_BEFORE_PERMANENT = 3


def _blacklist_path() -> Path:
    """Path to the revert blacklist state file (runtime dir, not project root)."""
    state_dir = get_runtime_dir() / "skill-quality"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / _BLACKLIST_FILENAME


def _load_blacklist() -> dict:
    """Load the revert blacklist from disk."""
    path = _blacklist_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_blacklist(blacklist: dict) -> None:
    """Save the revert blacklist to disk."""
    path = _blacklist_path()
    path.write_text(json.dumps(blacklist, indent=2))


def is_blacklisted(project_root: Path, skill_name: str) -> bool:
    """Check if a skill is currently blacklisted (recently reverted)."""
    blacklist = _load_blacklist()
    entry = blacklist.get(skill_name)
    if not entry:
        return False
    now = time.time()
    if entry.get("revert_count", 0) >= _MAX_REVERTS_BEFORE_PERMANENT:
        return True
    return now < entry.get("cooldown_until", 0)


def record_revert(project_root: Path, skill_name: str, reason: str) -> None:
    """Record that a skill's fix was reverted. Adds/extends cooldown."""
    blacklist = _load_blacklist()
    entry = blacklist.get(skill_name, {"revert_count": 0, "reasons": []})
    entry["revert_count"] = entry.get("revert_count", 0) + 1
    entry["last_revert"] = time.time()
    cooldown = _COOLDOWN_SECONDS * entry["revert_count"]
    entry["cooldown_until"] = time.time() + cooldown
    reasons = entry.get("reasons", [])
    reasons.append(reason)
    entry["reasons"] = reasons[-5:]
    blacklist[skill_name] = entry
    _save_blacklist(blacklist)


def verify_build(project_root: Path, dimensions: set[str] | None = None) -> bool:
    """Verify that changes don't break the dashboard.

    Args:
        project_root: Repository root.
        dimensions: Set of quality dimensions touched (instruction, product, ui, wiring).
            When only text-safe dimensions (instruction, product) are touched,
            skips the full build — SKILL.md text changes cannot break TypeScript.
            When UI or wiring dimensions are touched, runs the full pnpm build.
    """
    text_only_dims = {"instruction", "product"}
    if dimensions and dimensions.issubset(text_only_dims):
        return True

    try:
        result = subprocess.run(
            ["pnpm", "run", "build"],
            cwd=str(project_root / "apps" / "dashboard"),
            capture_output=True,
            timeout=180,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def git_commit(project_root: Path, message: str, paths: list[str] | None = None) -> bool:
    """Stage specific paths and commit with semantic diff gate.

    Uses the shared is_diff_significant() to reject whitespace-only commits.

    Args:
        project_root: Repository root.
        message: Commit message.
        paths: Files/directories to stage.  When *None* (legacy callers),
               falls back to ``git add -A`` but this should be avoided —
               it sweeps unrelated working-tree changes into the commit,
               and a subsequent ``git revert`` destroys those edits.
    """
    from src.lib.git_ops import is_diff_significant

    if paths:
        subprocess.run(["git", "add", "--"] + paths, cwd=str(project_root), capture_output=True)
    else:
        subprocess.run(["git", "add", "-A"], cwd=str(project_root), capture_output=True)

    # Check if anything meaningful was staged
    if not is_diff_significant(project_root):
        subprocess.run(["git", "reset", "HEAD"], cwd=str(project_root), capture_output=True)
        return False

    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=str(project_root),
        capture_output=True,
    )
    return result.returncode == 0


def git_revert(project_root: Path) -> bool:
    """Revert the last commit."""
    result = subprocess.run(
        ["git", "revert", "HEAD", "--no-edit"],
        cwd=str(project_root),
        capture_output=True,
    )
    return result.returncode == 0
