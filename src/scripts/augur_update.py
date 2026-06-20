#!/usr/bin/env python3
"""
Augur Update Script (ADR-048)

One-command update that pulls upstream changes and rebuilds the dashboard.

Usage:
    python3 src/scripts/augur_update.py
    python3 src/scripts/augur_update.py --skip-build
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config.paths import get_project_root


def run_cmd(
    args: list[str],
    cwd: Path | None = None,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    """Run a shell command and return the result.

    Args:
        args: Command and arguments as a list.
        cwd: Working directory for the command.
        capture: Whether to capture stdout/stderr.

    Returns:
        CompletedProcess instance with stdout/stderr as strings.
    """
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=capture,
        text=True,
    )


def read_version(project_root: Path) -> str:
    """Read the current version from the VERSION file.

    Args:
        project_root: Path to the project root directory.

    Returns:
        Version string, or "unknown" if the file cannot be read.
    """
    version_file = project_root / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    return "unknown"


def check_upstream_remote(project_root: Path) -> bool:
    """Verify that the 'upstream' git remote exists.

    Args:
        project_root: Path to the project root directory.

    Returns:
        True if the upstream remote is configured.
    """
    result = run_cmd(["git", "remote"], cwd=project_root)
    if result.returncode != 0:
        print("ERROR: Failed to list git remotes.")
        print(result.stderr.strip())
        return False

    remotes = result.stdout.strip().splitlines()
    if "upstream" not in remotes:
        print("ERROR: No 'upstream' remote found.")
        print()
        print("Add it with:")
        print("  git remote add upstream <upstream-repo-url>")
        print()
        print("Then run this script again.")
        return False

    return True


def stash_changes(project_root: Path) -> bool:
    """Stash any uncommitted changes.

    Args:
        project_root: Path to the project root directory.

    Returns:
        True if changes were stashed, False if working tree was clean.
    """
    # Check if there are changes to stash
    status = run_cmd(["git", "status", "--porcelain"], cwd=project_root)
    if status.returncode != 0:
        print("ERROR: Failed to check git status.")
        print(status.stderr.strip())
        sys.exit(1)

    if not status.stdout.strip():
        return False

    result = run_cmd(
        ["git", "stash", "push", "-m", "augur-update: auto-stash before update"],
        cwd=project_root,
    )
    if result.returncode != 0:
        print("ERROR: Failed to stash changes.")
        print(result.stderr.strip())
        sys.exit(1)

    print("  Stashed uncommitted changes.")
    return True


def fetch_upstream(project_root: Path) -> bool:
    """Fetch from the upstream remote.

    Args:
        project_root: Path to the project root directory.

    Returns:
        True on success.
    """
    result = run_cmd(["git", "fetch", "upstream"], cwd=project_root)
    if result.returncode != 0:
        print("ERROR: Failed to fetch upstream.")
        print(result.stderr.strip())
        return False

    print("  Fetched upstream changes.")
    return True


def merge_upstream(project_root: Path) -> bool:
    """Attempt to merge upstream/main into the current branch.

    The .gitattributes file protects data/ files from conflicts.

    Args:
        project_root: Path to the project root directory.

    Returns:
        True if merge succeeded, False if there were conflicts.
    """
    result = run_cmd(
        ["git", "merge", "upstream/main", "--no-edit"],
        cwd=project_root,
    )
    if result.returncode != 0:
        # Check if it was a merge conflict
        conflict_check = run_cmd(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=project_root,
        )
        conflicting_files = conflict_check.stdout.strip()

        if conflicting_files:
            print("ERROR: Merge conflicts detected in the following files:")
            print()
            for f in conflicting_files.splitlines():
                print(f"  - {f}")
            print()
            print("To resolve:")
            print("  1. Fix conflicts in the listed files")
            print("  2. Run: git add <resolved-files>")
            print("  3. Run: git merge --continue")
            print("  4. Re-run this update script")
            print()
            print("Or to abort the merge:")
            print("  git merge --abort")
        else:
            print("ERROR: Merge failed.")
            print(result.stderr.strip())
            # Attempt to abort the merge to leave repo in clean state
            run_cmd(["git", "merge", "--abort"], cwd=project_root)

        return False

    print("  Merged upstream/main successfully.")
    return True


def rebuild_dashboard(project_root: Path) -> bool:
    """Rebuild the dashboard with npm run build.

    Args:
        project_root: Path to the project root directory.

    Returns:
        True on success.
    """
    dashboard_dir = project_root / "apps" / "dashboard"
    if not dashboard_dir.exists():
        print("  Dashboard directory not found, skipping build.")
        return True

    package_json = dashboard_dir / "package.json"
    if not package_json.exists():
        print("  No package.json in dashboard, skipping build.")
        return True

    print("  Building dashboard (this may take a moment)...")
    result = run_cmd(["npm", "run", "build"], cwd=dashboard_dir)
    if result.returncode != 0:
        print("WARNING: Dashboard build failed.")
        if result.stderr.strip():
            # Show last 20 lines of stderr to keep output manageable
            stderr_lines = result.stderr.strip().splitlines()
            for line in stderr_lines[-20:]:
                print(f"    {line}")
        return False

    print("  Dashboard rebuilt successfully.")
    return True


def unstash_changes(project_root: Path) -> None:
    """Pop stashed changes back onto the working tree.

    Args:
        project_root: Path to the project root directory.
    """
    result = run_cmd(["git", "stash", "pop"], cwd=project_root)
    if result.returncode != 0:
        print("WARNING: Failed to restore stashed changes.")
        print("  Your changes are still in the stash. Restore manually with:")
        print("    git stash pop")
        if result.stderr.strip():
            print(result.stderr.strip())
    else:
        print("  Restored stashed changes.")


def main() -> None:
    """Run the full Augur update pipeline."""
    parser = argparse.ArgumentParser(
        description="Update Augur from upstream and rebuild.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip the dashboard rebuild step.",
    )
    args = parser.parse_args()

    project_root = get_project_root()
    print("Augur Update")
    print("=" * 40)
    print(f"Project root: {project_root}")
    print()

    # Record version before update
    version_before = read_version(project_root)

    # Step 1: Verify upstream remote
    print("[1/6] Checking upstream remote...")
    if not check_upstream_remote(project_root):
        sys.exit(1)

    # Step 2: Stash uncommitted changes
    print("[2/6] Stashing uncommitted changes...")
    had_stash = stash_changes(project_root)
    if not had_stash:
        print("  Working tree clean, nothing to stash.")

    # Step 3: Fetch upstream
    print("[3/6] Fetching upstream...")
    if not fetch_upstream(project_root):
        if had_stash:
            print("  Restoring stashed changes before exit...")
            unstash_changes(project_root)
        sys.exit(1)

    # Step 4: Merge upstream/main
    print("[4/6] Merging upstream/main...")
    if not merge_upstream(project_root):
        if had_stash:
            print()
            print("NOTE: Your changes are still stashed.")
            print("  After resolving conflicts, run: git stash pop")
        sys.exit(1)

    # Step 5: Rebuild dashboard
    if args.skip_build:
        print("[5/5] Skipping dashboard build (--skip-build).")
    else:
        print("[5/5] Rebuilding dashboard...")
        rebuild_dashboard(project_root)

    # Step 7: Unstash
    if had_stash:
        print("Restoring stashed changes...")
        unstash_changes(project_root)

    # Summary
    version_after = read_version(project_root)
    print()
    print(f"{'=' * 40}")
    print(f"Updated from v{version_before} -> v{version_after}.")
    print("Done.")


if __name__ == "__main__":
    main()
