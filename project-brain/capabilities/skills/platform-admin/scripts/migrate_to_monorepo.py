#!/usr/bin/env python3
"""
Migrate to Monorepo Script

Safely migrates from a 2-repo setup (augur + augur) to a single
monorepo setup. Includes backup, validation, and rollback capabilities.

Usage:
    python3 migrate_to_monorepo.py --check      # Dry run, show what would happen
    python3 migrate_to_monorepo.py --migrate    # Perform the migration
    python3 migrate_to_monorepo.py --rollback   # Rollback to previous state
"""


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
import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path
from subprocess import run as subprocess_run  # nosec B404


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Add project root to path for imports
try:
    from src.config.paths import get_project_root
    PROJECT_ROOT = get_project_root()
except ImportError:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # fallback
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# Configuration
HOME = Path.home()
CODE_REPO = HOME / "Projects" / "augur"
DATA_REPO = HOME / "Projects" / "augur"
BACKUP_DIR = HOME / "Projects" / ".augur-backup"
CONFIG_FILE = DATA_REPO / "config" / "paths.yaml"

# What to migrate - FULL DATA REPO STRUCTURE
# Format: (source_name, dest_name, category)
# Categories: 'data' (user data), 'plugins' (plugin code/skills), 'config' (settings), 'runtime' (logs/cache)
#
# NOTE: Code repo already has plugins/ with:
#   - plugins/enterprise/, plugins/dev-core/, plugins/ai/rag/, etc.
# Data repo has plugins/ with:
#   - skills/*, skills/*, skills/*
# These will be MERGED - copytree with dirs_exist_ok=True handles this.
#
MIGRATION_MAP = [
    # Historical monorepo migration map from pre-2026 layout.
    # Keep legacy source keys for one-time backfill audits; do not use for new setups.
    # Data folders (user data)
    ("core-data", "data/core", "data"),
    ("services-data", "data/services", "data"),
    ("apps-data", "plugins", "data"),
    # Legacy folders that might exist (if empty/small, skip)
    ("core", "data/core-legacy", "data"),
    ("services-core", "data/services-core", "data"),
    # Plugins - MERGE with existing plugins folder
    # data-repo/plugins/consulting/* -> code-repo/plugins/consulting/* (merge - adds skills/, bossanova/)
    # data-repo/plugins/orchestration/* -> code-repo/plugins/orchestration/* (merge - adds skills/)
    # data-repo/plugins/ai/* -> code-repo/plugins/ai/* (merge - adds skills/)
    ("plugins/consulting", "plugins/consulting", "plugins"),
    ("plugins/orchestration", "plugins/orchestration", "plugins"),
    ("plugins/ai", "plugins/ai", "plugins"),
    # Config folder from data repo
    ("config", "config-data", "config"),
    # Operations folder from data repo (different from code repo's operations/)
    ("operations", "operations-data", "data"),
    # Runtime/cache (will be gitignored)
    ("cache", "runtime/cache", "runtime"),
    # Root config files
    ("config.yaml", "config-config.yaml", "config_file"),
    ("llm.yaml", "config-data/llm.yaml", "config_file"),
]

# Files to skip (already in code repo or not needed)
SKIP_FILES = [".git", ".DS_Store", "LICENSE", "README.md", ".github"]


def print_header(text: str):
    """Print a formatted header."""
    _out(f"\n{'=' * 60}")
    _out(f"  {text}")
    _out(f"{'=' * 60}\n")


def print_step(step: int, total: int, text: str):
    """Print a step indicator."""
    _out(f"[{step}/{total}] {text}")


def run_command(cmd: list[str], cwd: Path | None = None) -> tuple[bool, str]:
    """Run a command and return success status and output."""
    try:
        result = subprocess_run(  # nosec B603
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def get_directory_size(path: Path) -> float:
    """Get directory size in MB."""
    if not path.exists():
        return 0.0

    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass

    return total / (1024 * 1024)


def check_prerequisites() -> list[str]:
    """Check if migration can proceed. Returns list of issues."""
    issues = []

    # Check repos exist
    if not CODE_REPO.exists():
        issues.append(f"Code repo not found: {CODE_REPO}")
    if not DATA_REPO.exists():
        issues.append(f"Data repo not found: {DATA_REPO}")

    # Check for uncommitted changes in code repo
    if CODE_REPO.exists():
        success, output = run_command(["git", "status", "--porcelain"], CODE_REPO)
        if success and output.strip():
            issues.append("Code repo has uncommitted changes. Commit or stash first.")

    # Check for uncommitted changes in data repo
    if DATA_REPO.exists():
        success, output = run_command(["git", "status", "--porcelain"], DATA_REPO)
        if success and output.strip():
            issues.append("Data repo has uncommitted changes. Commit or stash first.")

    # Check target directories don't already exist (warn but allow override)
    existing_targets = []
    for src_name, dest_name, category in MIGRATION_MAP:
        dest_path = CODE_REPO / dest_name
        if dest_path.exists():
            existing_targets.append(dest_name)

    if existing_targets:
        issues.append(
            f"Target folders already exist: {', '.join(existing_targets[:5])}{'...' if len(existing_targets) > 5 else ''}"
        )

    return issues


def calculate_migration_size() -> dict[str, float]:
    """Calculate sizes of what will be migrated."""
    sizes = {}

    for src_name, dest_name, category in MIGRATION_MAP:
        src_path = DATA_REPO / src_name
        if src_path.exists():
            if src_path.is_dir():
                sizes[dest_name] = get_directory_size(src_path)
            else:
                sizes[dest_name] = src_path.stat().st_size / (1024 * 1024)

    sizes["total"] = sum(sizes.values())

    return sizes


def create_backup() -> Path:
    """Create a backup of current state."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / timestamp

    backup_path.mkdir(parents=True, exist_ok=True)

    # Backup paths.yaml if it exists
    if CONFIG_FILE.exists():
        shutil.copy2(CONFIG_FILE, backup_path / "paths.yaml.backup")

    # Save current state info
    state_file = backup_path / "migration_state.txt"
    with open(state_file, "w") as f:
        f.write(f"Migration backup created: {timestamp}\n")
        f.write(f"Code repo: {CODE_REPO}\n")
        f.write(f"Data repo: {DATA_REPO}\n")
        f.write(f"Data repo exists: {DATA_REPO.exists()}\n")

    _out(f"   Backup created at: {backup_path}")
    return backup_path


def update_gitignore():
    """Update .gitignore in code repo for monorepo setup."""
    gitignore_path = CODE_REPO / ".gitignore"

    additions = """
# Monorepo - Runtime (never commit)
runtime/

# Monorepo - Large data files (optional)
data/*/vectors/
data/*/cache/
*.db
*.sqlite
"""

    if gitignore_path.exists():
        content = gitignore_path.read_text()
        if "# Monorepo - Runtime" not in content:
            with open(gitignore_path, "a") as f:
                f.write(additions)
            _out("   Updated .gitignore with monorepo patterns")
    else:
        gitignore_path.write_text(additions.strip())
        _out("   Created .gitignore with monorepo patterns")


def update_paths_yaml():
    """Update paths.yaml for monorepo configuration."""
    # Put config in config-data folder (merged from data repo)
    new_config_dir = CODE_REPO / "config-data"
    new_config_dir.mkdir(exist_ok=True)

    new_config_path = new_config_dir / "paths.yaml"

    config_content = f"""# Path Configuration for Augur
# Generated by migrate_to_monorepo.py on {datetime.now().isoformat()}

version: 1

# Monorepo configuration - all paths within single repo
paths:
  core: {CODE_REPO}
  data: {CODE_REPO / "data"}
  data_subdirs:
    - core
    - services
    - apps
  plugins: {CODE_REPO / "plugins"}
  runtime: {CODE_REPO / "runtime"}
  config: {CODE_REPO / "config-data"}

# Size thresholds for alerts
alerts:
  size_warning_mb: 500
  size_critical_mb: 1000
  large_file_mb: 50

# Previous configuration (for reference/rollback)
# previous:
#   core: {CODE_REPO}
#   data: {DATA_REPO}
#   plugins: {DATA_REPO / "plugins"}
#   runtime: {DATA_REPO / "runtime"}
#   config: {DATA_REPO / "config"}
"""

    new_config_path.write_text(config_content)
    _out(f"   Created new paths.yaml at: {new_config_path}")


def perform_migration(dry_run: bool = False) -> bool:
    """Perform the actual migration."""
    print_header("Migrating to Monorepo")

    total_steps = 4
    step = 0

    # Step 1: Create backup
    step += 1
    print_step(step, total_steps, "Creating backup...")
    if not dry_run:
        create_backup()
    else:
        _out("   [DRY RUN] Would create backup")

    # Step 2: Create target directories and copy files
    step += 1
    print_step(step, total_steps, "Creating directories and copying files...")

    # First, create all needed parent directories
    needed_dirs = set()
    for src_name, dest_name, category in MIGRATION_MAP:
        dest_path = CODE_REPO / dest_name
        if "/" in dest_name:
            needed_dirs.add(dest_path.parent)
        needed_dirs.add(dest_path if (DATA_REPO / src_name).is_dir() else dest_path.parent)

    for dir_path in sorted(needed_dirs):
        if not dry_run:
            dir_path.mkdir(parents=True, exist_ok=True)
        else:
            if not dir_path.exists():
                _out(f"   [DRY RUN] Would create: {dir_path}")

    # Now copy everything according to the migration map
    for src_name, dest_name, category in MIGRATION_MAP:
        src_path = DATA_REPO / src_name
        dest_path = CODE_REPO / dest_name

        if not src_path.exists():
            continue

        if src_path.is_dir():
            if not dry_run:
                shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
                _out(f"   Copied: {src_name}/ -> {dest_name}/")
            else:
                _out(f"   [DRY RUN] Would copy: {src_name}/ -> {dest_name}/")
        else:
            # It's a file
            if not dry_run:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dest_path)
                _out(f"   Copied: {src_name} -> {dest_name}")
            else:
                _out(f"   [DRY RUN] Would copy: {src_name} -> {dest_name}")

    # Step 3: Update .gitignore
    step += 1
    print_step(step, total_steps, "Updating .gitignore...")
    if not dry_run:
        update_gitignore()
    else:
        _out("   [DRY RUN] Would update .gitignore")

    # Step 4: Update paths.yaml
    step += 1
    print_step(step, total_steps, "Creating new paths.yaml...")
    if not dry_run:
        update_paths_yaml()
    else:
        _out("   [DRY RUN] Would create new paths.yaml")

    return True


def perform_rollback() -> bool:
    """Rollback to previous state."""
    print_header("Rolling Back Migration")

    # Find latest backup
    if not BACKUP_DIR.exists():
        _out("No backup found. Cannot rollback.")
        return False

    backups = sorted([d for d in BACKUP_DIR.iterdir() if d.is_dir()], reverse=True)
    if not backups:
        _out("No backup found. Cannot rollback.")
        return False

    latest_backup = backups[0]
    _out(f"Using backup: {latest_backup}")

    # Get all unique destination folders to remove
    folders_to_remove = set()
    for src_name, dest_name, category in MIGRATION_MAP:
        # Get the top-level folder
        top_level = dest_name.split("/")[0]
        folders_to_remove.add(CODE_REPO / top_level)

    for folder in sorted(folders_to_remove):
        if folder.exists():
            _out(f"   Removing: {folder}")
            shutil.rmtree(folder)

    # Restore original paths.yaml
    backup_config = latest_backup / "paths.yaml.backup"
    if backup_config.exists():
        if CONFIG_FILE.parent.exists():
            shutil.copy2(backup_config, CONFIG_FILE)
            _out(f"   Restored: {CONFIG_FILE}")

    _out("\nRollback complete. Your original 2-repo setup has been restored.")
    _out("Note: The data repo was not modified during migration.")

    return True


def show_status():
    """Show current migration status."""
    print_header("Current Status")

    _out("Repositories:")
    _out(f"   Code repo: {CODE_REPO}")
    _out(f"      Exists: {CODE_REPO.exists()}")

    _out(f"   Data repo: {DATA_REPO}")
    _out(f"      Exists: {DATA_REPO.exists()}")

    # Check if already migrated
    is_monorepo = (CODE_REPO / "data").exists() and (CODE_REPO / "plugins").exists()
    _out(f"\nMonorepo mode: {'Yes' if is_monorepo else 'No'}")

    # Show what will be migrated
    _out("\nMigration mapping:")
    for src_name, dest_name, category in MIGRATION_MAP:
        src_path = DATA_REPO / src_name
        if src_path.exists():
            size = get_directory_size(src_path) if src_path.is_dir() else src_path.stat().st_size / (1024 * 1024)
            marker = "📁" if src_path.is_dir() else "📄"
            _out(f"   {marker} {src_name} -> {dest_name} ({size:.1f} MB)")

    # Show totals by category
    _out("\nSizes by category:")
    sizes = calculate_migration_size()
    categories = {"data": 0, "plugins": 0, "config": 0, "runtime": 0, "config_file": 0}
    for src_name, dest_name, category in MIGRATION_MAP:
        if dest_name in sizes:
            categories[category] = categories.get(category, 0) + sizes[dest_name]

    for cat, size in categories.items():
        if size > 0:
            _out(f"   {cat}: {size:.1f} MB")
    _out("   ────────────────")
    _out(f"   Total: {sizes.get('total', 0):.1f} MB")

    # Check prerequisites
    issues = check_prerequisites()
    if issues:
        _out("\nIssues to resolve before migration:")
        for issue in issues:
            _out(f"   ⚠️  {issue}")
    else:
        _out("\n✅ No issues found. Ready to migrate.")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate Augur to monorepo setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python migrate_to_monorepo.py --check      # See what would happen
  python migrate_to_monorepo.py --migrate    # Perform migration
  python migrate_to_monorepo.py --rollback   # Undo migration
        """,
    )
    parser.add_argument("--check", action="store_true", help="Dry run - show what would happen")
    parser.add_argument("--migrate", action="store_true", help="Perform the migration")
    parser.add_argument("--rollback", action="store_true", help="Rollback to previous state")
    parser.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--force", action="store_true", help="Skip prerequisite checks")

    args = parser.parse_args()

    if not any([args.check, args.migrate, args.rollback, args.status]):
        # Default to status
        args.status = True

    if args.status:
        show_status()
        return 0

    if args.rollback:
        if perform_rollback():
            return 0
        return 1

    # Check or migrate
    if args.check or args.migrate:
        # Check prerequisites
        if not args.force:
            issues = check_prerequisites()
            if issues:
                print_header("Prerequisites Check Failed")
                for issue in issues:
                    _out(f"   - {issue}")
                _out("\nFix these issues or use --force to skip checks.")
                return 1

        # Show what will happen
        show_status()

        if args.check:
            print_header("Dry Run")
            perform_migration(dry_run=True)
            _out("\nThis was a dry run. Use --migrate to perform the actual migration.")
            return 0

        if args.migrate:
            # Confirm
            _out("\nThis will migrate to a monorepo setup.")
            _out("A backup will be created before any changes.")
            response = input("\nProceed with migration? [y/N]: ")

            if response.lower() != "y":
                _out("Migration cancelled.")
                return 0

            if perform_migration(dry_run=False):
                print_header("Migration Complete!")
                _out("Next steps:")
                _out("   1. Review the changes in the code repo")
                _out("   2. Run: pre-commit run --all-files")
                _out("   3. Test the dashboard: cd apps/dashboard && npm run dev")
                _out("   4. Commit the changes: git add -A && git commit -m 'Migrate to monorepo'")
                _out("")
                _out("To rollback: python migrate_to_monorepo.py --rollback")
                return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
