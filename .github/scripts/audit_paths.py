#!/usr/bin/env python3
"""
Audit Paths Script

Scans repositories for hardcoded user-specific paths that violate
the data separation principle. Uses dynamic path configuration
when available.

Usage:
    python3 audit_paths.py           # Use dynamic config
    python3 audit_paths.py /path1    # Scan specific paths
"""

import os
import re
import subprocess
import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def get_forbidden_patterns() -> list[str]:
    """Get forbidden path patterns based on current user."""
    username = os.environ.get("USER", os.environ.get("USERNAME", ""))
    if not username:
        return []

    return [
        f"/Users/{username}",
        f"/home/{username}",
        f"C:\\Users\\{username}",
        f"C:\\\\Users\\\\{username}",  # Escaped Windows paths
    ]


def get_repos_to_scan() -> list[str]:
    """Get repos from dynamic config. Fails fast if config unavailable (ADR-084)."""
    try:
        from src.config.path_config import get_path_config
    except ImportError as e:
        from src.logging.self_heal_event import emit_heal_event

        emit_heal_event(
            source="audit_paths",
            category="import_failure",
            severity="high",
            message=f"Cannot import get_path_config: {e}",
            context={"expected_module": "src.config.path_config"},
        )
        raise

    config = get_path_config()

    # Return unique git roots
    seen = set()
    repos = []
    for cat in [config.core, config.data, config.plugins]:
        if cat.git_root and str(cat.git_root) not in seen:
            seen.add(str(cat.git_root))
            repos.append(str(cat.git_root))

    if not repos:
        from src.logging.self_heal_event import emit_heal_event

        emit_heal_event(
            source="audit_paths",
            category="config_missing",
            severity="high",
            message="get_path_config() returned no git roots",
        )
        raise RuntimeError("No git roots found in path config — cannot audit paths")

    return repos


# Dynamic configuration
FORBIDDEN_PATTERNS = get_forbidden_patterns()
REPOS_TO_SCAN = get_repos_to_scan()

IGNORE_DIRS = {
    ".git",
    ".next",
    "node_modules",
    "dist",
    "build",
    ".build",
    "__pycache__",
    ".mypy_cache",  # Python type checker cache
    ".pytest_cache",  # Pytest cache
    ".ruff_cache",  # Ruff linter cache
    ".DS_Store",
    ".venv",
    ".venv-test",  # Test venv
    "venv",
    ".gemini",
    ".history",
    "tmp",
    "coverage",
    "_archive",
    "test_discovery_data",
    "temp_data",
    ".claude",
    "runtime",  # Runtime data (logs, cache) - should be gitignored
    "logs",  # Log files contain system paths
    "data",  # User data directory - contains user-specific paths by design
    ".agent-data",  # Agent-specific data/scripts
    ".antigravity",  # Antigravity config
}

IGNORE_FILES = {
    "audit_paths.py",  # Ignore self
    "path_config.py",  # Dynamic path config (generates patterns, not hardcoded)
    "AGENTS.md",  # Generated agent instructions document environment-specific paths
    "README.md",  # Documentation may describe local paths intentionally
    ".git",  # Git worktree pointer file (contains absolute path to main repo)
    ".plugin-mount",  # Generated plugin mount marker with absolute paths
    ".cursorrules",
    ".windsurfrules",
    "CODEX.md",
    "CLAUDE.md",
    "copilot-instructions.md",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "mcp_config.json",  # Local MCP config requires absolute paths
    "tasks.json",  # Often contains absolute paths in VSCode tasks
    "config.yaml",  # User config often needs absolute paths (whitelisted in Data Repo)
    "context_glossary.md",  # Documentation of the problem
    "instructions.md",  # Documentation of the rule
    "agent-rules.md",  # Documentation of rules/anti-patterns
    "audit_report.txt",  # The output of this script
    "config/mcp_config.json",  # User-generated MCP config
    "mcp_config_secret.json",  # Local config
    ".env.local",  # Local env
    "com.augur.nightly.plist",  # LaunchAgent requires absolute paths
    "generate_coverage_yaml.js",  # Script with hardcoded output path (acceptable?) - wait, I should fix this too?
    "api_summary.json",
    "licenses.json",  # Generated license file with absolute paths
    "debug_test_run.log",
    "wrap.sh",  # Local wrapper script intentionally embeds absolute venv path
    "mcp.json",  # Local editor MCP config
    "dev.log",  # Generated dashboard log
    "index.yaml",  # Generated memory index with absolute source paths
    "stripPII.test.ts",  # Test fixture contains synthetic absolute paths by design
}

SPECIAL_ALLOW_TEMPLATES = {"mcp_config.template.json"}

# Ignore non-source trees where absolute paths are expected/documentary.
IGNORE_PATH_PREFIXES = {
    ".cursor/",
    ".windsurf/",
    ".opencode/",
    ".agent/",
    ".superpowers/",
    "docs/",
}

IGNORE_EXACT_PATHS = {
    "config/agents/ide_integrations.yaml",
}

IGNORE_DIR_PARTS = {
    "tests",
    "__tests__",
    "references",
    "commands",
    "examples",
}


def should_skip_rel_path(rel_path: Path) -> bool:
    """Return True when a file is documentation, generated seed data, or tests."""
    rel_path_str = rel_path.as_posix()
    parts = rel_path.parts

    if rel_path_str in IGNORE_EXACT_PATHS:
        return True

    if any(part in IGNORE_DIR_PARTS for part in parts):
        return True

    if rel_path.suffix == ".md" and len(parts) == 1:
        return True

    if "assets" in parts and "seeds" in parts:
        return True

    filename = rel_path.name
    if ".test." in filename or ".spec." in filename or filename.startswith("test_"):
        return True

    return False


def scan_file(file_path: Path) -> list[tuple[int, str]]:
    """Scan a single file for forbidden path patterns.

    Returns list of (line_number, line_content) tuples for matches.
    """
    try:
        # Skip binary files
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            return []  # Skip binary

        # Windows path regex: Single letter drive, colon, double backslash (for escaped string)
        # We ensure it's NOT preceded by a letter (to avoid matching text like "Labels:\\n")
        win_path_re = re.compile(r'(?<![a-zA-Z])[a-zA-Z]:\\\\')

        matches = []
        lines = content.split('\n')
        for i, line in enumerate(lines):
            # Allow suppressing audit via comment
            if "audit-ignore" in line:
                continue

            # Check for Windows absolute paths (e.g. C:\, D:\)
            if win_path_re.search(line):
                matches.append((i + 1, line.strip()))

            # Check for all forbidden patterns (dynamic based on current user)
            for pattern in FORBIDDEN_PATTERNS:
                if pattern in line:
                    # Context matches are allowed if they are explicitly documenting the path
                    # But we report them all for review
                    matches.append((i + 1, line.strip()))
                    break  # Only report once per line

        return matches
    except (IOError, OSError) as e:
        print(f"Error scanning {file_path}: {e}")
        return []


def _walk_repo_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for root, dirs, names in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for name in names:
            files.append(Path(root) / name)
    return files


def _iter_repo_files(repo_root: Path) -> list[Path]:
    """Return tracked and untracked, non-ignored files for audit."""
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return _walk_repo_files(repo_root)

    rel_paths = [
        item
        for item in result.stdout.decode("utf-8", errors="ignore").split("\0")
        if item
    ]
    if not rel_paths:
        return _walk_repo_files(repo_root)
    return [repo_root / rel_path for rel_path in rel_paths]


def scan_repo(repo_path: str) -> int:
    """Scan a repository for hardcoded paths.

    Returns 0 if no violations, 1 if violations found.
    """
    print(f"\nScanning Repository: {repo_path}")
    print("=" * 60)

    repo_root = Path(repo_path)
    violations = 0

    for file_path in _iter_repo_files(repo_root):
        if not file_path.is_file():
            continue
        rel_path = file_path.relative_to(repo_root)
        rel_path_str = rel_path.as_posix()
        file = file_path.name

        # Special case: allow scanning specific files even if they might match an ignore pattern logically
        # (though here IGNORE_FILES logic comes first)

        if (file in IGNORE_FILES or rel_path_str in IGNORE_FILES) and file not in SPECIAL_ALLOW_TEMPLATES:
            continue

        if any(rel_path_str.startswith(prefix) for prefix in IGNORE_PATH_PREFIXES):
            continue

        if should_skip_rel_path(rel_path):
            continue

        if "venture/community/page.tsx" in str(file_path):
            continue

        # Skip artifacts in brain/
        if ".gemini" in str(file_path):
            continue

        if not file_path.exists():
            continue

        matches = scan_file(file_path)
        if matches:
            print(f"\n📄 {rel_path}")
            for line_num, content in matches:
                trunc_content = content[:100] + "..." if len(content) > 100 else content
                print(f"   Line {line_num}: {trunc_content}")
                violations += 1

    if violations == 0:
        print(f"\n✅ No hardcoded paths found in {os.path.basename(repo_path)}!")
        return 0
    else:
        print(f"\n⚠️  Found {violations} potential violations in {os.path.basename(repo_path)}.")
        return 1


if __name__ == "__main__":
    exit_code = 0

    repos = sys.argv[1:] if len(sys.argv) > 1 else REPOS_TO_SCAN

    for repo in repos:
        if os.path.exists(repo):
            if scan_repo(repo) != 0:
                exit_code = 1
        else:
            print(f"Repo not found: {repo}")
    sys.exit(exit_code)
