"""Content-preserving cross-repo move (two separate git repos, no-loss)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _verify_committed(repo: Path, rel: str) -> bool:
    out = subprocess.run(["git", "-C", str(repo), "ls-files", "--", rel], capture_output=True, text=True).stdout
    return bool(out.strip())


def move_file_across_repos(*, src: Path, dst: Path, src_repo: Path, dst_repo: Path, message: str) -> None:
    """Add+commit in dst_repo, verify, then rm+commit in src_repo. Never lose content."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    dst_rel = str(dst.relative_to(dst_repo))
    _git(dst_repo, "add", "--", dst_rel)
    _git(dst_repo, "commit", "-qm", f"chore(brain-cleanup): add {dst_rel} — {message}")
    if not _verify_committed(dst_repo, dst_rel):
        raise RuntimeError(f"target not verified in {dst_repo}: {dst_rel}")
    src_rel = str(src.relative_to(src_repo))
    _git(src_repo, "rm", "-q", "--", src_rel)
    _git(src_repo, "commit", "-qm", f"chore(brain-cleanup): remove {src_rel} — {message}")
