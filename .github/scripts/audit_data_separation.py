#!/usr/bin/env python3
"""
Audit data/code separation across the codebase.

Ensures user data is only written to augur repo, never to the code repo.

Checks for:
1. File writes to packages/ or shared/ directories
2. YAML/JSON data files in code repo that should be in data repo
3. Paths that don't use shared.config.paths for data operations

This enforces the two-repo architecture:
- augur/ = CODE REPO (Python, TypeScript, configs)
- augur/ = DATA REPO (User data, YAML databases)
"""

import ast
import re
import sys
from pathlib import Path
from typing import List, Tuple

IGNORE_DIRS = {
    ".git",
    ".next",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".DS_Store",
    ".venv",
    "venv",
    ".gemini",
    ".history",
    "tmp",
    "coverage",
    "_archive",
    ".claude",
    "test_discovery_data",
}

IGNORE_FILES = {
    "audit_data_separation.py",  # Ignore self
    "conftest.py",  # Test configuration
}

# Patterns that indicate data file operations
DATA_FILE_PATTERNS = [
    r'\.write_text\(',
    r'\.write_bytes\(',
    r'open\([^)]*["\']w["\']',  # open(..., 'w')
    r'open\([^)]*["\']a["\']',  # open(..., 'a')
    r'json\.dump\(',
    r'yaml\.dump\(',
    r'yaml\.safe_dump\(',
]

# Legitimate paths in code repo that can be written to
ALLOWED_WRITE_PATHS = [
    r'\.venv',
    r'node_modules',
    r'\.next',
    r'dist',
    r'build',
    r'coverage',
    r'__pycache__',
    r'\.pytest_cache',
    r'\.mypy_cache',
    r'\.ruff_cache',
    r'tmp/',
    r'test_',  # Test files can write to test directories
    r'tests/',  # Test directories
    r'GITHUB_OUTPUT',  # CI outputs
    r'\.git',
]

# Files that should NOT exist in code repo (belong in data repo)
DATA_FILE_EXTENSIONS = {
    # These are OK in code repo for configs
    # '.yaml',  # Could be config or data - check content
    # '.json',  # Could be package.json or data
}

# Directories that should only contain code, not user data
CODE_ONLY_DIRS = [
    'packages/',
    'src/',
    'plugins/',
]


def is_write_allowed(line: str, file_path: Path) -> bool:
    """Check if a write operation is to an allowed location."""
    for pattern in ALLOWED_WRITE_PATHS:
        if re.search(pattern, line):
            return True

    # Check if it's using path helpers from src.config.paths
    if (
        'get_config_dir' in line
        or 'get_runtime_dir' in line
        or 'get_memory_dir' in line
        or 'get_skill_data_dir' in line
        or 'get_project_root' in line
    ):
        return True

    # Check if it's writing to a temp file
    if 'tempfile' in line or 'NamedTemporaryFile' in line or 'mktemp' in line:
        return True

    return False


def check_file_for_violations(file_path: Path) -> List[Tuple[int, str, str]]:
    """
    Check Python file for data separation violations.

    Returns:
        List of (line_number, violation_type, message) tuples
    """
    violations = []

    try:
        with open(file_path) as f:
            content = f.read()
            lines = content.split('\n')

        # Check for write operations to code repo paths
        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()

            # Skip comments
            if line_stripped.startswith('#'):
                continue

            # Check for data file write patterns
            for pattern in DATA_FILE_PATTERNS:
                if re.search(pattern, line):
                    # Check if it's an allowed write
                    if not is_write_allowed(line, file_path):
                        # Check if it's writing to code repo paths
                        if any(code_dir in line for code_dir in ['packages/', 'src/', 'plugins/']):
                            violations.append(
                                (
                                    i,
                                    "write_to_code_repo",
                                    "Potential write to code repo - use get_project_root() or specific path helpers",
                                )
                            )
                        elif '__file__' in line and ('write' in line.lower() or 'dump' in line.lower()):
                            # Writing relative to __file__ in code repo
                            violations.append(
                                (i, "write_relative", "Writing relative to __file__ - ensure data goes to data repo")
                            )

        # AST-based checks for Path operations
        try:
            tree = ast.parse(content, filename=str(file_path))

            for node in ast.walk(tree):
                # Check for Path().write_text() or similar
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        if node.func.attr in ['write_text', 'write_bytes', 'mkdir']:
                            # Get the line for context
                            line_content = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                            if not is_write_allowed(line_content, file_path):
                                # Check if Path is constructed with code repo paths
                                path_str = ast.unparse(node.func.value) if hasattr(ast, 'unparse') else ""
                                if any(code_dir in path_str for code_dir in ['packages', 'shared']):
                                    violations.append(
                                        (
                                            node.lineno,
                                            "path_write",
                                            f"Path.{node.func.attr}() to code repo - use data repo instead",
                                        )
                                    )
        except (SyntaxError, ValueError):
            pass  # Skip AST errors (malformed Python)

    except (IOError, OSError) as e:
        print(f"Warning: Could not read {file_path}: {e}")

    return violations


def check_data_files_in_code_repo(repo_path: Path) -> List[Tuple[Path, str]]:
    """
    Check for data files that shouldn't be in the code repo.

    Returns:
        List of (file_path, reason) tuples
    """
    violations = []

    # Check for YAML files that look like data (not config)
    for yaml_file in repo_path.rglob("*.yaml"):
        if any(ignored in yaml_file.parts for ignored in IGNORE_DIRS):
            continue

        # Skip known config files
        if yaml_file.name in ['dependencies.yaml', 'SKILL.md', '.pre-commit-config.yaml']:
            continue

        # Check if file contains user data patterns
        try:
            content = yaml_file.read_text()
            # Data files often have timestamps, IDs, or user-specific content
            if re.search(r'created_at:|updated_at:|user_id:|entries:', content):
                # This might be a data file
                rel_path = yaml_file.relative_to(repo_path)
                rel_path_str = str(rel_path)

                # Monorepo architecture: plugin-owned data and schemas are valid in-tree.
                if rel_path_str.startswith("plugins/") and ("/data/" in rel_path_str or "/schemas/" in rel_path_str):
                    continue

                # Only flag if in packages/ or shared/ (not in tests or _dev)
                if rel_path_str.startswith(('packages/', 'src/', 'plugins/')):
                    if '/tests/' not in rel_path_str and '/_dev/' not in rel_path_str:
                        violations.append((yaml_file, "YAML file appears to contain user data - should be in augur"))
        except (IOError, OSError, UnicodeDecodeError):
            pass  # Skip files that can't be read (binary, permission denied, etc.)

    return violations


def scan_repo(repo_path: Path) -> int:
    """Scan repository for data separation violations."""
    print(f"\nScanning for data separation violations: {repo_path}")
    print("=" * 60)

    total_violations = 0
    files_with_violations = 0

    # Check Python files
    for py_file in repo_path.rglob("*.py"):
        # Skip ignored directories
        if any(ignored in py_file.parts for ignored in IGNORE_DIRS):
            continue

        # Skip ignored files
        if py_file.name in IGNORE_FILES:
            continue

        # Skip test files - they're allowed to write test data
        if '/tests/' in str(py_file) or py_file.name.startswith('test_'):
            continue

        violations = check_file_for_violations(py_file)

        if violations:
            files_with_violations += 1
            rel_path = py_file.relative_to(repo_path)
            print(f"\n{rel_path}")

            for line_num, vtype, message in violations:
                print(f"   Line {line_num}: [{vtype}] {message}")
                total_violations += 1

    # Check for data files in code repo
    data_file_violations = check_data_files_in_code_repo(repo_path)
    for file_path, reason in data_file_violations:
        rel_path = file_path.relative_to(repo_path)
        print(f"\n{rel_path}")
        print(f"   [data_file] {reason}")
        total_violations += 1

    if total_violations == 0:
        print("\n Data separation is correct!")
        return 0
    else:
        print(f"\n Found {total_violations} potential violations.")
        print("\n Remember:")
        print("   - CODE REPO (augur/): Python, TypeScript, configs only")
        print("   - DATA REPO (augur/): User data, YAML databases")
        print("   - Use src.config.paths helpers (get_config_dir, get_runtime_dir, etc.) for data writes")
        return 1


def main():
    """Run data separation audit."""
    project_root = Path(__file__).parent.parent.parent

    print("Auditing data/code separation...")

    exit_code = scan_repo(project_root)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
