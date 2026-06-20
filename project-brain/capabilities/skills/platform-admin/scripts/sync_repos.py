#!/usr/bin/env python3
"""
Sync Repos Script
Commits and pushes changes to repositories based on dynamic path configuration.
Supports both monorepo and multi-repo setups.
Respects pre-commit hooks and aborts if errors occur.

Usage:
    python3 sync_repos.py "commit message"
    python3 sync_repos.py --check-sizes  # Check sizes before sync
"""

import sys
import importlib.util
import shutil
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess, run  # nosec B404


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve executable path to absolute when available."""
    if not command:
        raise ValueError("Command must not be empty")

    executable = command[0]
    if Path(executable).is_absolute():
        return command

    resolved = shutil.which(executable)
    if not resolved:
        return command

    return [resolved, *command[1:]]


def _run_command(command: list[str], **kwargs: object) -> CompletedProcess:
    """Run subprocess command with resolved executable."""
    return run(_resolve_command(command), **kwargs)  # nosec B603


# Force UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

def _load_bootstrap_paths():
    bootstrap_path = Path(__file__).resolve().parent / "bootstrap_paths.py"
    spec = importlib.util.spec_from_file_location("platform_admin_bootstrap_paths", bootstrap_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load bootstrap_paths from {bootstrap_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ensure_project_paths = _load_bootstrap_paths().ensure_project_paths

PROJECT_ROOT = ensure_project_paths(__file__)
from src.lib.ops_protocol import OpsContext  # noqa: E402
from src.lib.staged_skill_catalog import find_skill_file  # noqa: E402


def _get_vault_path() -> Path | None:
    """
    Read vault path from config/system/vault.yaml.

    Returns:
        Resolved vault Path, or None if not configured or not a git repo.
    """
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        return None

    vault_config = PROJECT_ROOT / "config" / "system" / "vault.yaml"
    if not vault_config.exists():
        return None

    try:
        with vault_config.open() as fh:
            data = yaml.safe_load(fh)
        raw = data.get("vault", {}).get("path", "")
        if not raw:
            return None
        vault_path = Path(raw).expanduser().resolve()
        if not vault_path.exists():
            return None
        # Only include if it is actually a git repo
        git_dir = vault_path / ".git"
        if not git_dir.exists():
            return None
        return vault_path
    except Exception:
        return None


def get_repos_to_sync() -> list[tuple[Path, str]]:
    """
    Get list of repositories to sync based on dynamic path config.

    Includes the main Augur project repo and, when present, the vault repo
    auto-detected from config/system/vault.yaml.

    Returns:
        List of (repo_path, repo_name) tuples

    Raises:
        RuntimeError: If path config cannot be loaded
    """
    from src.config.path_config import get_path_config

    config = get_path_config()

    # Get unique git roots
    seen = set()
    repos = []

    for cat in config.categories:
        if cat.git_root and cat.git_root not in seen:
            seen.add(cat.git_root)
            # Determine name based on path
            if cat.id == "core":
                name = "Code Repo (augur)"
            elif "data" in str(cat.git_root).lower():
                name = "Data Repo"
            else:
                name = f"{cat.id.title()} Repo"
            repos.append((cat.git_root, name))

    if not repos:
        raise RuntimeError("No repositories found in path config")

    # Append vault repo if configured and not already included
    vault_path = _get_vault_path()
    if vault_path and vault_path not in seen:
        repos.append((vault_path, "Vault Repo"))

    return repos


def check_sizes_before_sync() -> bool:
    """
    Check path sizes and warn if any exceed thresholds.

    Returns:
        True if safe to proceed, False if critical threshold exceeded
    """
    try:
        from src.config.path_config import check_size_alerts, get_path_config

        config = get_path_config()
        config.refresh_sizes()
        alerts = check_size_alerts(config)

        if not alerts:
            return True

        _out("\n📊 Size Check:")
        has_critical = False

        for alert in alerts:
            if alert.level == "critical":
                _out(f"   🔴 CRITICAL: {alert.category} is {alert.size_mb:.1f} MB")
                has_critical = True
            elif alert.level == "warning":
                _out(f"   🟡 Warning: {alert.category} is {alert.size_mb:.1f} MB")
            else:
                _out(f"   📁 Large file: {alert.category} ({alert.size_mb:.1f} MB)")

        if has_critical:
            _out("\n⚠️  Critical size threshold exceeded. Consider cleanup before sync.")
            return False

        return True

    except ImportError:
        return True  # Can't check, proceed anyway


def run_git(repo_path, args, description):
    """Run a git command in the specified repo."""
    _out(f"[{description}] Running: git {' '.join(args)}")
    try:
        # We want to stream output so user sees pre-commit hook output
        _run_command(
            ["git"] + args,
            cwd=str(repo_path),
            check=True,
            text=True,
            stdout=None,  # Inherit stdout/stderr to show hook output
            stderr=None,
        )
        return True
    except CalledProcessError as e:
        _out(f"❌ Error during {description}: Command failed with exit code {e.returncode}")
        return False
    except Exception as e:
        _out(f"❌ Unexpected error during {description}: {e}")
        return False


def has_changes(repo_path):
    """Check if there are changes to commit."""
    try:
        # Check for modified/staged files
        status = _run_command(
            ["git", "status", "--porcelain"], cwd=str(repo_path), check=True, capture_output=True, text=True
        )
        return bool(status.stdout.strip())
    except Exception:
        return False


def pull_changes(repo_path, name):
    """Pull latest changes."""
    _out(f"\n⬇️  Pulling {name}...")
    return run_git(repo_path, ["pull", "--rebase"], f"Pull {name}")


def analyze_change(repo_path):
    """Analyze the changes in the repo to return stats and complexity."""
    try:
        # Get stats of what is staged (before commit) or committed (HEAD)
        # Since we run this before commit in push_changes, let's look at staged + unstaged?
        # Actually push_changes does 'git add .', then 'git commit'.
        # Best to check stats of 'git diff --cached' AFTER 'git add .' but BEFORE 'git commit'.

        # However, to be safe, let's do it after 'git add .'

        # We need to run this efficiently.
        result = _run_command(
            ["git", "diff", "--cached", "--shortstat"], cwd=str(repo_path), capture_output=True, text=True
        )

        output = result.stdout.strip()
        if not output:
            return None, False

        # Output format: " 3 files changed, 15 insertions(+), 5 deletions(-)"
        parts = output.split(",")
        files_changed = 0
        insertions = 0
        deletions = 0

        for part in parts:
            part = part.strip()
            if "file" in part:
                files_changed = int(part.split()[0])
            elif "insertion" in part:
                insertions = int(part.split()[0])
            elif "deletion" in part:
                deletions = int(part.split()[0])

        total_lines = insertions + deletions

        # Complexity Threshold
        is_complex = files_changed > 5 or total_lines > 100

        return {"summary": output, "files": files_changed, "lines": total_lines}, is_complex

    except Exception as e:
        _out(f"⚠️  Complexity analysis failed: {e}")
        return None, False


def trigger_code_review(repo_path, message):
    """Trigger the code review agent."""
    _out("\n🧐 Large change detected. Triggering Automated Code Review...")
    try:
        module_path = find_skill_file(PROJECT_ROOT, "auto-code-review", "scripts", "code_review.py")
        if module_path is None:
            _out("   ⚠️  Auto code review module not found")
            return
        spec = importlib.util.spec_from_file_location("auto_code_review_code_review", str(module_path))
        if spec is None or spec.loader is None:
            _out(f"   ⚠️  Auto code review module not found at {module_path}")
            return

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        ctx = OpsContext(project_root=repo_path, difficulty=1, dry_run=True)
        result = module.scan(ctx)
        _out(f"   Review complete: {result.summary}")
    except Exception as e:
        _out(f"   ⚠️  Failed to trigger code review: {e}")


def push_changes(repo_path, message, name):
    """Commit and push changes."""
    _out(f"\n📦 Syncing {name}...")

    if not has_changes(repo_path):
        _out(f"   No changes to commit in {name}.")
        run_git(repo_path, ["push"], f"Push {name}")
        return True

    # Add all
    if not run_git(repo_path, ["add", "."], f"Add files in {name}"):
        return False

    # ANALYZE (New Step)
    stats, is_complex = analyze_change(repo_path)
    if stats:
        _out(f"   📊 Stats: {stats['summary']}")

    # Commit
    if not run_git(repo_path, ["commit", "-m", message], f"Commit {name}"):
        _out(f"⛔ Commit failed in {name}. Likely due to pre-commit hook violations.")
        return False

    # Push
    if not run_git(repo_path, ["push"], f"Push {name}"):
        return False

    _out(f"✅ {name} Synced Safely.")

    # Trigger Review if complex AND it is the Code Repo
    if is_complex and name == "Code Repo (augur)":
        trigger_code_review(repo_path, message)

    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Sync repositories")
    parser.add_argument("message", nargs="?", default="Auto-sync from Dashboard", help="Commit message")
    parser.add_argument("--check-sizes", action="store_true", help="Check sizes before sync")
    parser.add_argument("--force", action="store_true", help="Force sync even if size warning")
    args = parser.parse_args()

    message = args.message

    # Get repos to sync
    try:
        repos = get_repos_to_sync()
    except Exception as e:
        _out(f"❌ Failed to get repos from path config: {e}")
        sys.exit(1)

    if not repos:
        _out("❌ No repositories found to sync")
        sys.exit(1)

    # Check sizes if requested
    if args.check_sizes and not args.force:
        if not check_sizes_before_sync():
            _out("\nUse --force to sync anyway.")
            sys.exit(1)

    _out("🔄 Starting Repository Sync...")
    _out(f"📝 Message: {message}")
    _out(f"📂 Repositories: {len(repos)}")

    for repo_path, repo_name in repos:
        _out(f"   - {repo_name}: {repo_path}")

    # Sync each repository
    failed = []
    for repo_path, repo_name in repos:
        if not repo_path.exists():
            _out(f"\n⚠️  {repo_name} not found at {repo_path}. Skipping.")
            continue

        if not push_changes(repo_path, message, repo_name):
            failed.append(repo_name)
            # Stop on first failure for code repo (critical)
            if "Code" in repo_name:
                _out(f"\n❌ Sync Aborted. Please fix the errors in {repo_name}.")
                sys.exit(1)

    if failed:
        _out(f"\n⚠️  Some repos failed to sync: {', '.join(failed)}")
        sys.exit(1)

    _out(f"\n🎉 {len(repos)} Repository(ies) Synced Successfully!")


if __name__ == "__main__":
    main()
