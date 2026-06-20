"""auto-repo-pollution: Detect working-tree junk that git cannot see.

The repo .gitignore carries blanket binary patterns (*.png, *.pdf, *.wav),
so session artifacts dropped anywhere in the tree never appear in git
status and accumulate silently. This loop scans the working tree itself:

- OS junk (.DS_Store) and orphan __pycache__/*.pyc anywhere
- gitignored binary artifacts outside sanctioned output dirs
- stray untracked-or-ignored files at the repo root that are not part of
  the canonical root set
- empty directories left behind by migrations

d1 fix removes OS junk, orphan pycache, expired session artifacts
(browser proofs, tmp_* media), and empty dirs. Binaries that look like
user work products are reported with a suggested Documents destination,
never deleted.
"""
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
import logging
import re
import shutil
import subprocess
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, make_issue

name = "auto-repo-pollution"

DIFFICULTY_SPEC = {
    0: "Report — list working-tree junk and stray artifacts",
    1: "Auto-fix — remove OS junk, orphan pycache, expired session artifacts, empty dirs",
}

logger = logging.getLogger(__name__)

# Never descend into these (vcs, deps, envs, generated build trees, worktrees).
# __pycache__ is handled specially: not descended, but flagged when orphaned.
SKIP_DIR_NAMES = {
    ".git", "node_modules", ".venv", ".worktrees", ".next", ".pytest_cache",
    ".ruff_cache", ".pnpm-store",
}

# Dirs whose binary/generated content is by design (relative to repo root).
SANCTIONED_OUTPUT_DIRS = ("build",)

# Binary suffixes that the repo .gitignore blanket-hides from git status.
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".wav", ".mp3", ".mp4", ".m4a", ".zip", ".docx", ".xlsx"}

# Expired session artifacts: safe to delete at d1.
SESSION_ARTIFACT_PATTERNS = (
    re.compile(r"(browser[-_]?(proof|verif)|merge-verify|-proof-)", re.IGNORECASE),
    re.compile(r"^tmp[-_]", re.IGNORECASE),
    re.compile(r"^\.codex-browser-proof", re.IGNORECASE),
)

OS_JUNK_NAMES = {".DS_Store", "Thumbs.db"}


def _is_session_artifact(path: Path) -> bool:
    for pat in SESSION_ARTIFACT_PATTERNS:
        # Anchored patterns describe filenames; unanchored ones may match
        # a marker anywhere in the path (e.g. a browser-proof/ parent dir).
        target = path.name if pat.pattern.startswith("^") else str(path)
        if pat.search(target):
            return True
    return False


def _iter_tree(root: Path):
    """Walk the repo tree skipping vcs/dep/build dirs."""
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir() and not entry.is_symlink():
                if entry.name in SKIP_DIR_NAMES:
                    continue
                if current == root and entry.name in SANCTIONED_OUTPUT_DIRS:
                    continue
                # Nested git checkout (e.g. .claude/worktrees/*) — a separate
                # working tree, possibly owned by a live session (rule 24).
                if (entry / ".git").exists():
                    continue
                if entry.name != "__pycache__":
                    stack.append(entry)
            yield entry


def _tracked_files(root: Path) -> set[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files"], cwd=str(root), capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return set(result.stdout.splitlines())
    except Exception:
        pass
    return set()


def scan(ctx: OpsContext) -> ScanResult:
    root = ctx.project_root
    if not (root / ".git").exists():
        return ScanResult(issues=[], summary="Not a git repo", severity="info")

    tracked = _tracked_files(root)
    issues: list[dict] = []
    empty_dirs: list[str] = []

    for entry in _iter_tree(root):
        try:
            rel = str(entry.relative_to(root))
        except ValueError:
            continue

        if entry.is_symlink():
            # Symlinked dirs (e.g. caches redirected per ADR-270) are not
            # repo pollution; their targets are managed elsewhere.
            continue

        if entry.is_dir():
            if entry.name == "__pycache__":
                # Orphaned compiled cache: no Python source left beside it.
                if not any(entry.parent.glob("*.py")):
                    issues.append(make_issue(
                        category="orphan-pycache",
                        detail=f"orphan __pycache__ (no sibling .py): {rel}",
                        path=str(entry), kind="maintenance",
                        root_cause_type="stale_accumulation", fixability="auto",
                    ))
                continue
            try:
                if not any(entry.iterdir()):
                    empty_dirs.append(rel)
            except OSError:
                pass
            continue

        if not entry.is_file():
            continue

        if entry.name in OS_JUNK_NAMES:
            issues.append(make_issue(
                category="os-junk", detail=f"OS junk file: {rel}", path=str(entry),
                kind="maintenance", root_cause_type="stale_accumulation", fixability="auto",
            ))
            continue

        if entry.suffix == ".pyc":
            issues.append(make_issue(
                category="orphan-pycache", detail=f"compiled cache: {rel}", path=str(entry),
                kind="maintenance", root_cause_type="stale_accumulation", fixability="auto",
            ))
            continue

        if entry.suffix.lower() in BINARY_SUFFIXES and rel not in tracked:
            if _is_session_artifact(entry):
                issues.append(make_issue(
                    category="session-artifact",
                    detail=f"expired session artifact: {rel}", path=str(entry),
                    kind="maintenance", root_cause_type="stale_accumulation", fixability="auto",
                ))
            else:
                issues.append(make_issue(
                    category="stray-binary",
                    detail=(
                        f"untracked binary hidden by .gitignore: {rel} — "
                        "move to the Documents store (get_documents_dir()) if it is a work product"
                    ),
                    path=str(entry), kind="maintenance",
                    root_cause_type="manual_debt", fixability="manual",
                ))

    for rel in sorted(empty_dirs):
        issues.append(make_issue(
            category="empty-dir", detail=f"empty directory: {rel}",
            path=str(root / rel), kind="maintenance",
            root_cause_type="stale_accumulation", fixability="auto",
        ))

    if not issues:
        return ScanResult(issues=[], summary="Working tree clean — no pollution detected", severity="info")

    auto = sum(1 for i in issues if i.get("fixability") == "auto")
    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} working-tree pollution issue(s) ({auto} auto-fixable)",
        severity="warning",
        items_scanned=len(issues),
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} issues found")
    if ctx.difficulty < 1:
        return FixResult(
            success=True, fix_type="report",
            summary=f"d0 report only: {len(issues)} pollution issue(s)",
        )

    changes: list[str] = []
    skipped: list[str] = []
    for issue in issues:
        category = issue.get("category")
        path = Path(issue.get("path", ""))
        if category in ("os-junk", "orphan-pycache", "session-artifact"):
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                    changes.append(f"removed {category}: {path.name}")
                elif path.is_file():
                    path.unlink()
                    changes.append(f"removed {category}: {path.name}")
            except OSError as e:
                logger.warning("Failed to remove %s: %s", path, e)
        elif category == "empty-dir":
            if path.is_dir() and not path.is_symlink():
                try:
                    path.rmdir()
                    changes.append(f"removed empty dir: {issue.get('detail', '')}")
                except OSError:
                    continue
                # Cascade: removing a leaf can leave a newly-empty parent chain.
                parent = path.parent
                while parent != ctx.project_root:
                    try:
                        if any(parent.iterdir()):
                            break
                        parent.rmdir()
                        changes.append(f"removed empty dir: {parent.name} (emptied by cascade)")
                    except OSError:
                        break
                    parent = parent.parent
        else:
            skipped.append(issue.get("detail", str(path)))

    summary = f"Removed {len(changes)} item(s)"
    if skipped:
        summary += f"; {len(skipped)} manual item(s) reported (work products are never auto-deleted)"
    return FixResult(success=True, summary=summary, changes=changes)
