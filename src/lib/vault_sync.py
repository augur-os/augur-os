"""Vault repo sync state + one-click commit→pull→push (dashboard-driven).

Client-neutral engine (rule 38). Operates on the vault repo resolved from
get_vault_dir(). Read path (vault_sync_status) is local-only and fast; write
path (vault_sync_run) is the only thing that touches the network.
"""

from __future__ import annotations

import subprocess  # nosec B404
from pathlib import Path
from typing import Any


def _resolve_vault(vault_dir: Path | str | None) -> Path:
    if vault_dir is not None:
        return Path(vault_dir)
    from src.config.paths import get_vault_dir

    return Path(get_vault_dir())


def _git(repo: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(  # nosec B603 B607
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _is_git_repo(repo: Path) -> bool:
    return (repo / ".git").exists()


def vault_sync_status(vault_dir: Path | str | None = None) -> dict[str, Any]:
    """Read-only sync state of the vault repo (no network/fetch)."""
    repo = _resolve_vault(vault_dir)
    if not repo.exists() or not _is_git_repo(repo):
        return {
            "vault_configured": False,
            "synced": True,
            "uncommitted": 0,
            "unpushed": 0,
            "behind": 0,
            "has_upstream": False,
            "detail": "no vault repo configured",
        }

    _, porcelain, _ = _git(repo, "status", "--porcelain")
    uncommitted = len([ln for ln in porcelain.splitlines() if ln.strip()])

    up_rc, _, _ = _git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    has_upstream = up_rc == 0
    if has_upstream:
        _, ahead, _ = _git(repo, "rev-list", "--count", "@{u}..HEAD")
        _, behind, _ = _git(repo, "rev-list", "--count", "HEAD..@{u}")
        unpushed = int(ahead or "0")
        behind_n = int(behind or "0")
    else:
        _, allc, _ = _git(repo, "rev-list", "--count", "HEAD")
        unpushed = int(allc or "0")
        behind_n = 0

    synced = uncommitted == 0 and unpushed == 0
    if synced:
        detail = "vault synced"
    else:
        parts = []
        if uncommitted:
            parts.append(f"{uncommitted} uncommitted")
        if unpushed:
            parts.append(f"{unpushed} unpushed")
        detail = ", ".join(parts)
    return {
        "vault_configured": True,
        "synced": synced,
        "uncommitted": uncommitted,
        "unpushed": unpushed,
        "behind": behind_n,
        "has_upstream": has_upstream,
        "detail": detail,
    }


_MAX_FILE_BYTES = 95 * 1024 * 1024  # GitHub hard limit is 100 MB


def _oversized_files(repo: Path) -> list[str]:
    _, porcelain, _ = _git(repo, "status", "--porcelain")
    big: list[str] = []
    for line in porcelain.splitlines():
        name = line[3:].strip().strip('"')
        if not name:
            continue
        fp = repo / name
        try:
            if fp.is_file() and fp.stat().st_size > _MAX_FILE_BYTES:
                big.append(name)
        except OSError:
            continue
    return big


def vault_sync_run(vault_dir: Path | str | None = None) -> dict[str, Any]:
    """Commit (if dirty) → pull (ff, else merge) → push. Vault repo only.

    Never forces. On a real merge conflict: abort the merge, restore the
    working tree, and surface the conflicted paths.
    """
    repo = _resolve_vault(vault_dir)
    base = {"success": False, "committed": 0, "pulled": 0, "pushed": 0, "conflict": False, "message": ""}
    if not repo.exists() or not _is_git_repo(repo):
        return {**base, "success": False, "message": "no vault repo configured"}

    # 1. commit (if dirty), with a size guard
    _, porcelain, _ = _git(repo, "status", "--porcelain")
    dirty = bool([ln for ln in porcelain.splitlines() if ln.strip()])
    committed = 0
    if dirty:
        oversized = _oversized_files(repo)
        if oversized:
            return {**base, "message": f"refusing to commit oversized file(s): {', '.join(oversized)}"}
        n = len([ln for ln in porcelain.splitlines() if ln.strip()])
        rc, _, err = _git(repo, "add", "-A")
        if rc != 0:
            return {**base, "message": f"git add failed: {err}"}
        rc, _, err = _git(repo, "commit", "-m", f"chore(vault): sync {n} change(s) from dashboard")
        if rc != 0:
            return {**base, "message": f"git commit failed: {err}"}
        committed = n

    # 2. pull (only if an upstream exists)
    pulled = 0
    up_rc, _, _ = _git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    has_upstream = up_rc == 0
    if has_upstream:
        rc, _, err = _git(repo, "fetch", "origin")
        if rc != 0:
            return {**base, "committed": committed, "message": f"git fetch failed: {err}"}
        _, behind, _ = _git(repo, "rev-list", "--count", "HEAD..@{u}")
        pulled = int(behind or "0")
        if pulled:
            rc, _, _ = _git(repo, "merge", "--ff-only", "@{u}")
            if rc != 0:  # diverged → real merge, may conflict
                m_rc, _, _ = _git(repo, "merge", "--no-edit", "@{u}")
                if m_rc != 0:
                    _, conflicted, _ = _git(repo, "diff", "--name-only", "--diff-filter=U")
                    _git(repo, "merge", "--abort")
                    return {
                        **base,
                        "committed": committed,
                        "conflict": True,
                        "message": f"merge conflict in: {conflicted.replace(chr(10), ', ')}",
                    }

    # 3. push
    _, branch, _ = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    target = "@{u}..HEAD" if has_upstream else "HEAD"
    _, ahead, _ = _git(repo, "rev-list", "--count", target)
    pushed = int(ahead or "0")
    if has_upstream:
        rc, _, err = _git(repo, "push")
    else:
        rc, _, err = _git(repo, "push", "-u", "origin", branch)
    if rc != 0:
        return {**base, "committed": committed, "pulled": pulled, "message": f"git push failed: {err}"}

    return {
        "success": True,
        "committed": committed,
        "pulled": pulled,
        "pushed": pushed,
        "conflict": False,
        "message": f"committed {committed}, pulled {pulled}, pushed {pushed}",
    }
