"""vault-status MCP tool — returns vault git state for dashboard.

ADR-474: Vault Git Integration.
Returns structured git status including dirty_files, unpushed commits,
recent commit log, and a health summary derived from lightweight hygiene checks.
"""

from __future__ import annotations

import time
from pathlib import Path

from src.mcp.augur_shared.logging import get_entity_logger
from src.mcp.augur_shared.safe_subprocess import safe_run

logger = get_entity_logger("mcp")

_BINARY_EXTENSIONS = {
    ".m4a",
    ".xlsx",
    ".docx",
    ".png",
    ".svg",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".mp3",
    ".mp4",
    ".wav",
}
_SKIP_DIRS = {"_config", "_cache", ".DS_Store"}


def _compute_health_score(vault: Path) -> tuple[str, list[str]]:
    """Run lightweight vault hygiene checks and return (score_str, issue_categories).

    Checks (5 categories):
      binary_files  — any file with a binary extension
      orphan_dirs   — skill subdirs with no matching skills/ entry
      stale_files   — files not modified in 90+ days
      large_files   — files > 1 MB
      empty_dirs    — directories with no children (excludes dotdirs like .git)
    """
    issues: list[str] = []

    # 1. Binary files
    has_binary = any(
        f.suffix.lower() in _BINARY_EXTENSIONS
        for f in vault.rglob("*")
        if f.is_file() and not _is_inside_dotdir(f, vault)
    )
    if has_binary:
        issues.append("binary_files")

    # 2. Orphan dirs (vault plugin subdirs with no matching skill)
    try:
        from src.config.paths import get_project_brain_skills_dir
        from src.mcp.augur_shared.compat import get_project_root

        skills_dir = get_project_brain_skills_dir(Path(get_project_root()))
        from src.lib.brain_layout import brain_layout
        from src.lib.brain_manifest import brain_skeleton_top_dirs
        from src.lib.dir_alignment import AUGUR_RUNTIME_DIRS

        # Post-ADR-771: the brain skeleton + Augur runtime dirs are the
        # sanctioned top-level set (legacy "memory"/"dev" names retired).
        _ALLOWED_TOP = {"config", *brain_skeleton_top_dirs(brain_layout(vault)), *AUGUR_RUNTIME_DIRS}
        for plugin_dir in vault.iterdir():
            if not plugin_dir.is_dir() or plugin_dir.name.startswith("."):
                continue
            if plugin_dir.name in _ALLOWED_TOP:
                continue
            for skill_dir in plugin_dir.iterdir():
                if skill_dir.is_dir() and not (skills_dir / skill_dir.name).exists():
                    issues.append("orphan_dirs")
                    break
            else:
                continue
            break
    except Exception:
        pass

    # 3. Stale files (90+ days)
    ninety_days_ago = time.time() - (90 * 86400)
    stale = any(
        f.stat().st_mtime < ninety_days_ago
        for f in vault.rglob("*")
        if f.is_file() and not f.name.startswith(".") and not _is_inside_dotdir(f, vault) and _safe_stat(f) is not None
    )
    if stale:
        issues.append("stale_files")

    # 4. Large files (> 1 MB)
    has_large = any(
        _safe_size(f) > 1_000_000 for f in vault.rglob("*") if f.is_file() and not _is_inside_dotdir(f, vault)
    )
    if has_large:
        issues.append("large_files")

    # 5. Empty dirs (skip dotdirs like .git and dirs inside them)
    has_empty = any(
        not any(d.iterdir()) and d.name not in _SKIP_DIRS
        for d in vault.rglob("*")
        if d.is_dir() and not d.name.startswith(".") and not _is_inside_dotdir(d, vault)
    )
    if has_empty:
        issues.append("empty_dirs")

    total = 5
    passed = total - len(issues)
    return f"{passed}/{total}", issues


def _is_inside_dotdir(path: Path, root: Path) -> bool:
    """Check if path is inside a dot-prefixed directory relative to root."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    return any(part.startswith(".") for part in rel.parts)


def _safe_stat(path: Path):
    try:
        return path.stat()
    except OSError:
        return None


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _get_vault_path() -> Path | None:
    """Read vault path from config/system/vault.yaml."""
    try:
        import yaml
        from src.mcp.augur_shared.compat import get_project_root

        vault_yaml = Path(get_project_root()) / "config" / "system" / "vault.yaml"
        if not vault_yaml.exists():
            return None
        data = yaml.safe_load(vault_yaml.read_text())
        raw_path = data.get("vault", {}).get("path", "")
        return Path(raw_path).expanduser() if raw_path else None
    except Exception:
        return None


def _run_git(vault: Path, *args: str) -> str:
    """Run a git command in the vault, return stdout or empty string on error."""
    try:
        result = safe_run(
            ["git", *args],
            cwd=str(vault),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def register_vault_tools(mcp, config: dict):
    """Register vault status tool."""

    @mcp.tool(name="vault-status", description="Get vault git status, sync state, and health summary")
    def vault_status() -> dict:
        vault = _get_vault_path()

        _DEFAULTS = {
            "dirty_files": 0,
            "unpushed": 0,
            "recent_commits": [],
            "health": "clean",
            "last_commit": "no commits",
            "has_remote": False,
            "repo_size_mb": 0,
            "health_score": "0/5",
            "health_issues": [],
        }

        if not vault or not vault.exists():
            return {
                **_DEFAULTS,
                "state": "missing",
                "health": "clean",
                "message": "Vault directory not found. Run onboard --full to create.",
            }

        if not (vault / ".git").exists():
            return {
                **_DEFAULTS,
                "state": "no_git",
                "health": "clean",
                "message": "Vault exists but is not a git repo. Run git init.",
            }

        # Git status
        status_output = _run_git(vault, "status", "--porcelain")
        dirty_files = len(status_output.splitlines()) if status_output else 0

        # Last commit
        last_commit = _run_git(vault, "log", "-1", "--format=%ci")

        # Push status
        unpushed_output = _run_git(vault, "log", "--oneline", "@{u}..HEAD")
        unpushed_count = len(unpushed_output.splitlines()) if unpushed_output else 0
        has_remote = bool(_run_git(vault, "remote", "get-url", "origin"))

        # Repo size
        git_dir = vault / ".git"
        git_size = sum(f.stat().st_size for f in git_dir.rglob("*") if f.is_file()) if git_dir.exists() else 0

        # Recent commits
        recent = _run_git(vault, "log", "--oneline", "-5")

        # Health score (lightweight hygiene scan — no subprocess, no git log)
        health_score, health_issues = _compute_health_score(vault)

        # Determine health status (ADR-474 spec)
        if dirty_files > 0:
            health = "dirty"
        elif unpushed_count > 0:
            health = "unpushed"
        else:
            health = "clean"

        return {
            "state": "ok",
            "dirty_files": dirty_files,
            "unpushed": unpushed_count,
            "recent_commits": recent.splitlines() if recent else [],
            "health": health,
            "last_commit": last_commit or "no commits",
            "has_remote": has_remote,
            "repo_size_mb": round(git_size / 1_000_000, 1),
            "health_score": health_score,
            "health_issues": health_issues,
        }
