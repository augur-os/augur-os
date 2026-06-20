#!/usr/bin/env python3
"""
Validate File Placement Script

Pre-commit hook that validates new files are created in the correct category paths.

Rules:
- Code files (.py, .ts, .tsx) should be in CORE (framework)
- User data files (.yaml, .json with user data) should be in DATA
- Runtime files (logs, temp, cache) should be in RUNTIME and gitignored

Usage:
    python3 validate_file_placement.py                    # Check staged files
    python3 validate_file_placement.py file1.py file2.ts  # Check specific files
"""


import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.paths import get_runtime_dir


# Paths that have been migrated and should not be used
FORBIDDEN_LEGACY_PATHS = {
    "src/skills": "src/plugins/skill_discovery.py or src/plugins/",
    "plugins/data": "project-brain/capabilities/skills/{skill}/augur/data/",
    "plugins/factory-core": "project-brain/capabilities/skills/",
    "plugins/services-core": "project-brain/capabilities/skills/",
    "plugins/vertical-life": "project-brain/capabilities/skills/",
    ".claude/skills": "generated client export, not canonical project-brain/capabilities/skills/",
}

# Allowed top-level directories and files in project root.
# Any new root-level directory not in this set will be blocked by the pre-commit hook.
ALLOWED_ROOT_ENTRIES = {
    # Directories
    "apps", "config", "dist", "docs", "node_modules", "plugins", "scripts",
    "security", "skills", "src", "tests",
    # Dot-directories (managed by tools)
    ".agent", ".agent-data", ".antigravity", ".claude", ".clinerules",
    ".codex", ".cursor", ".gemini", ".git", ".githooks", ".github",
    ".opencode", ".playwright-mcp", ".pytest_cache", ".superpowers",
    ".venv", ".vscode", ".windsurf", ".worktrees",
    # Root files
    "AGENTS.md", "CHANGELOG.md", "CLAUDE.md", "CODEX.md", "CONTRIBUTING.md",
    "LICENSE", "Makefile", "README.md", "SECURITY.md", "VERSION",
    "package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "project.yaml",
    "pyproject.toml", "tsconfig.base.json", "uv.lock",
    # Dot-files
    ".cursorignore", ".gitattributes", ".gitignore",
    ".gitleaksignore", ".npmrc", ".pre-commit-config.yaml",
}


@dataclass
class ValidationResult:
    valid: bool
    message: str = ""
    suggestion: str = ""
    expected_category: str = ""


def is_user_data_file(path: Path) -> bool:
    """Detect if file contains user data vs code config."""
    if not path.exists() or not path.is_file():
        return False

    if path.suffix not in [".yaml", ".json"]:
        return False

    try:
        content = path.read_text(encoding="utf-8")
        # User data patterns
        data_patterns = [
            r"created_at:",
            r"updated_at:",
            r"user_id:",
            r"entries:",
            r"^\s*-\s+id:",  # List of items with IDs
            r"last_modified:",
            r"timestamp:",
        ]
        return any(re.search(p, content, re.MULTILINE) for p in data_patterns)
    except (OSError, UnicodeDecodeError):
        return False


def is_runtime_file(path: Path) -> bool:
    """Detect if file is state, log, cache, or temp data."""
    runtime_root = re.escape(str(get_runtime_dir()).replace("\\", "/"))
    runtime_patterns = [
        r"\.log$",
        r"\.tmp$",
        r"\.cache$",
        r"\.pid$",
        r"/logs/",
        r"/temp/",
        r"/cache/",
        r"/ipc/",
        r"_archive/",
        runtime_root,
    ]
    path_str = str(path).replace("\\", "/")
    return any(re.search(p, path_str) for p in runtime_patterns)


def is_gitignored(path: Path, git_root: Path) -> bool:
    """Check if a path is gitignored."""
    if not git_root or not path.exists():
        return False

    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(path)],
            cwd=git_root,
            capture_output=True,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def find_git_root(path: Path) -> Path | None:
    """Find the .git directory for a path."""
    current = path.resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


def validate_file_placement(file_path: Path) -> ValidationResult:
    """
    Validate that a file is in the correct category path.

    Returns:
        ValidationResult with validation status and messages
    """
    try:
        from src.config.path_config import get_path_config

        config = get_path_config()
    except ImportError as e:
        # ADR-084: emit event instead of silent pass-through
        try:
            from src.logging.self_heal_event import emit_heal_event

            emit_heal_event(
                source="validate_file_placement",
                category="import_failure",
                severity="medium",
                message=f"Cannot import path_config — file placement validation skipped: {e}",
                context={"file_path": str(file_path)},
            )
        except ImportError:
            pass
        # Still return valid since we can't validate without config,
        # but the event alerts the daemon
        return ValidationResult(valid=True)

    file_path = file_path.resolve()

    # Check if runtime file
    if is_runtime_file(file_path):
        git_root = find_git_root(file_path)
        if git_root and not is_gitignored(file_path, git_root):
            return ValidationResult(
                valid=False,
                message=f"Runtime file should be gitignored: {file_path}",
                suggestion="Add to .gitignore or move to runtime folder",
                expected_category="runtime",
            )

    # Check for legacy paths
    # file_str = str(file_path)
    # Normalize path separator for checking
    rel_path = str(file_path.relative_to(PROJECT_ROOT)) if file_path.is_absolute() else str(file_path)
    
    # Check for unknown root-level entries
    root_entry = rel_path.split("/")[0]
    if root_entry and root_entry not in ALLOWED_ROOT_ENTRIES:
        return ValidationResult(
            valid=False,
            message=f"Unknown root-level entry: {root_entry}/",
            suggestion=(
                f"Move to an existing directory (src/, docs/, project-brain/, etc.) "
                f"or add '{root_entry}' to ALLOWED_ROOT_ENTRIES in validate_file_placement.py"
            ),
            expected_category="root_allowlist",
        )

    for forbidden, replacement in FORBIDDEN_LEGACY_PATHS.items():
        # Check if file is inside a forbidden directory
        # We check if it starts with the forbidden path + / or is the path itself
        if rel_path == forbidden or rel_path.startswith(f"{forbidden}/"):
             return ValidationResult(
                valid=False,
                message=f"Legacy path usage detected: {file_path}",
                suggestion=f"Move to {replacement}",
                expected_category="migrated_structure",
            )

    # Check if user data file in wrong location
    if is_user_data_file(file_path):
        # Check if it's in CORE path (should be in DATA)
        try:
            file_path.relative_to(config.core.path)
            # It's in core - that's wrong for data files
            return ValidationResult(
                valid=False,
                message=f"Data file should be in DATA ({config.data.path}), not CORE",
                suggestion=f"Move to: {config.data.path / file_path.name}",
                expected_category="data",
            )
        except ValueError:
            pass  # Not in core, that's OK

    return ValidationResult(valid=True)


def get_staged_files() -> list[Path]:
    """Get list of staged files from git."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        if result.returncode == 0:
            return [PROJECT_ROOT / f for f in result.stdout.strip().split("\n") if f]
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return []


def main():
    # Get files to check
    if len(sys.argv) > 1:
        files = [Path(f) for f in sys.argv[1:]]
    else:
        files = get_staged_files()

    if not files:
        print("No files to check")
        return 0

    issues = []

    for file_path in files:
        if not file_path.exists():
            continue

        result = validate_file_placement(file_path)
        if not result.valid:
            issues.append((file_path, result))

    if issues:
        print("\n❌ File Placement Violations:")
        print("=" * 60)

        for file_path, result in issues:
            print(f"\n📄 {file_path}")
            print(f"   {result.message}")
            if result.suggestion:
                print(f"   💡 {result.suggestion}")

        print(f"\n⚠️  Found {len(issues)} placement issue(s)")
        return 1

    print("✅ All files in correct locations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
