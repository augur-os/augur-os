#!/usr/bin/env python3
"""
Audit logging usage across the codebase.

Ensures all Python code uses shared.augur_logging instead of:
- Direct print() statements (in non-test files)
- logging.basicConfig() calls
- Raw logging module usage without shared.augur_logging

This enforces centralized logging with correlation ID support.
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
    ".venv-test",
    "venv",
    "site-packages",
    ".gemini",
    ".history",
    "tmp",
    "coverage",
    "_archive",
    ".archive",
    ".claude",
    "augur_logging",
    ".agent",
    "_dev",
    "packages",  # External packages have their own logging
    "logging",  # The logging infrastructure itself must use standard logging
}

IGNORE_FILES = {
    "audit_logging.py",  # Ignore self
    "conftest.py",  # Test configuration often needs direct logging
}

# Files/patterns where raw logging import is acceptable (CLI scripts with __main__)
RAW_LOGGING_ALLOWED_PATTERNS = [
    r"project-brain/capabilities/skills/.*/scripts/",  # Skill CLI scripts
    r"project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/",  # IDE adapters use stdlib logging bridges
    r"project-brain/capabilities/skills/ai/augur/adapters/",  # Relocated IDE adapters (vscode_copilot, cursor) use stdlib logging bridges
    r"src/lib/ai/config\.py$",  # Config loader fallback logger
    r".github/scripts/",  # CI/utility scripts
    r"src/mcp/augur_(core|framework|shared)/",  # MCP server/bootstrap uses stdlib logging wiring
    r"src/scripts/migrations/",  # Migration runner bootstrap
    r"apps/dashboard/lib/plugins/",  # Dashboard plugins
    r"apps/dashboard/scripts/skill-scripts/",  # Dashboard skill CLI/porter scripts
    r"scripts/mcp_surface_audit\.py$",  # CLI audit script bridges stdlib logging (logging.disable)
    # Standalone-importable modules: must not hard-depend on src.* at module top
    # (they ship a no-src fallback path), so they keep stdlib logging.
    r"src/lib/skill_paths\.py$",
    r"src/lib/sync_discover\.py$",
    r"src/config/path_discovery\.py$",
    # Test files that exercise stdlib logging behavior (caplog levels, logging.disable).
    # `tests/` is print-allowed but raw imports also need an explicit test glob;
    # `src/tests/` does not match the bare `tests/` print pattern.
    r"src/tests/",
    r"(^|/)tests/",
]

# Files/patterns where logging.basicConfig() is acceptable (CLI scripts)
BASICCONFIG_ALLOWED_PATTERNS = [
    r"project-brain/capabilities/skills/.*/scripts/",  # Skill CLI scripts
    r".github/scripts/",  # CI/utility scripts
]

# Files/patterns where print() is acceptable
PRINT_ALLOWED_PATTERNS = [
    r"tests/",  # Test files can use print
    r"_test\.py$",  # Test files
    r"test_.*\.py$",  # Test files
    r"scripts/ci_",  # CI scripts output to stdout
    r"scripts/audit_",  # Audit scripts output to stdout
    r"scripts/validate_",  # Validation scripts output to stdout
    r"install\.py$",  # Installation scripts
    r"setup\.py$",  # Setup scripts
    r"__main__\.py$",  # CLI entry points
    r"cli\.py$",  # CLI modules
    r".github/scripts/",  # Shared CLI/utility scripts
    r"packages/.*/scripts/",  # Skill scripts/CLI utilities
    r"src/rag/examples/",  # Example usage scripts
    r"docs/qa/",  # QA synthetic-data generator CLI scripts (print() is the tool's stdout)
    r"scripts/",  # Root scripts
    r"plugins/vertical-.*/skills/.*/actions/",  # CLI actions output
    r"plugins/.*/skills/.*/scripts/",  # Plugin CLI scripts
    r"plugins/.*/skills/.*/lib/",  # Plugin library modules (may use print for CLI utilities)
    r"src/mcp/augur_framework/__main__\.py$",  # MCP startup/status console output
    r"src/mcp/augur_shared/",  # MCP server bootstrap stderr diagnostics + usage output
    r"src/lib/llm_retry\.py$",  # Retry helper interactive fallback output
    # CLI command modules split out of src/cli.py — print() IS the user-facing command output.
    r"src/_cli_commands\.py$",
    r"src/_cli_mcp\.py$",
    r"src/config/precommit_check\.py$",  # Pre-commit validator CLI (__main__) stdout/stderr
    r"src/config/path_discovery\.py$",  # Interactive path-update prompt output (precedes input())
    r"src/cli_config/config_sync\.py$",  # `aug config sync/status` command output
    r"src/lib/sync_discover\.py$",  # `python -m src.lib.sync_discover` table/JSON CLI output
    r"src/lib/vault_links\.py$",  # `python -m src.lib.vault_links` CLI output (__main__)
    r"src/lib/runtime/codex_automations\.py$",  # CLI (__main__) prints written automation paths
    r"src/lib/onboard/driver\.py$",  # Interactive onboarding wizard step progress output
    r"src/lib/index/enrich_descriptions\.py$",  # CLI (__main__) + dry-run "what would change" report
    r"src/lib/index/symbol_extractor\.py$",  # symbols.yaml extraction CLI utility (__main__)
    r"src/lib/index/unified_indexer\.py$",  # Intentional stderr progress (MCP stdio-safe) + CLI (__main__)
    r"project-brain/capabilities/skills/routine-vault/evals/fixtures/build_fixtures\.py$",  # Fixture builder CLI
]


def is_print_allowed(file_path: Path) -> bool:
    """Check if print() is allowed in this file."""
    path_str = str(file_path)
    for pattern in PRINT_ALLOWED_PATTERNS:
        if re.search(pattern, path_str):
            return True
    return False


def is_raw_logging_allowed(file_path: Path) -> bool:
    """Check if raw logging import is allowed in this file (CLI scripts)."""
    path_str = str(file_path)
    for pattern in RAW_LOGGING_ALLOWED_PATTERNS:
        if re.search(pattern, path_str):
            return True
    return False


def is_basicconfig_allowed(file_path: Path) -> bool:
    """Check if logging.basicConfig() is allowed in this file (CLI scripts)."""
    path_str = str(file_path)
    for pattern in BASICCONFIG_ALLOWED_PATTERNS:
        if re.search(pattern, path_str):
            return True
    return False


def check_logging_usage(file_path: Path) -> List[Tuple[int, str, str]]:
    """
    Check Python file for logging violations.

    Returns:
        List of (line_number, violation_type, message) tuples
    """
    violations = []

    try:
        with open(file_path) as f:
            content = f.read()
            lines = content.split('\n')

        tree = ast.parse(content, filename=str(file_path))

        # Track imports
        has_augur_logging_import = False
        has_raw_logging_import = False
        raw_logging_in_fallback = False  # import logging inside except ImportError

        # First pass: detect if import logging is inside an except ImportError block (fallback pattern)
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                # Check if this is an ImportError handler
                is_import_error_handler = (
                    node.type is None  # bare except
                    or (isinstance(node.type, ast.Name) and node.type.id == "ImportError")
                    or (
                        isinstance(node.type, ast.Tuple)
                        and any(isinstance(t, ast.Name) and t.id == "ImportError" for t in node.type.elts)
                    )
                )
                if is_import_error_handler:
                    # Check if import logging is inside this handler
                    for child in ast.walk(node):
                        if isinstance(child, ast.Import):
                            for alias in child.names:
                                if alias.name == "logging":
                                    raw_logging_in_fallback = True

        for node in ast.walk(tree):
            # Check for centralized logging import (src.logging or shared.augur_logging)
            if isinstance(node, ast.ImportFrom):
                if node.module and ("shared.augur_logging" in node.module or "src.logging" in node.module):
                    has_augur_logging_import = True
                elif node.module == "logging":
                    has_raw_logging_import = True

            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "logging":
                        has_raw_logging_import = True

            # Check for logging.basicConfig() - but allow in __main__ blocks (CLI scripts)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if (
                        node.func.attr == "basicConfig"
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "logging"
                    ):
                        # Check if this is inside an if __name__ == "__main__" block
                        # by looking at the line content
                        in_main_block = False
                        if node.lineno <= len(lines):
                            # Look backwards for if __name__ == "__main__"
                            for i in range(node.lineno - 1, max(0, node.lineno - 20), -1):
                                line = lines[i].strip()
                                if 'if __name__' in line and '__main__' in line:
                                    in_main_block = True
                                    break
                                # Stop if we hit a function or class definition that's not indented
                                if (line.startswith('def ') or line.startswith('class ')) and not lines[i].startswith(
                                    ' '
                                ):
                                    break

                        if not in_main_block and not is_basicconfig_allowed(file_path):
                            violations.append(
                                (
                                    node.lineno,
                                    "basicConfig",
                                    "logging.basicConfig() - use shared.augur_logging.get_entity_logger() instead",
                                )
                            )

                # Check for print() in non-allowed files
                if isinstance(node.func, ast.Name) and node.func.id == "print":
                    if not is_print_allowed(file_path):
                        # Get the line content for context
                        line_content = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                        # Skip if it looks like a doctest or example
                        if ">>>" not in line_content and "# noqa" not in line_content:
                            violations.append(
                                (node.lineno, "print", "print() statement - use logger.info() for production code")
                            )

        # Check for raw logging import without augur_logging
        # Skip if:
        # 1. import logging is inside an except ImportError block (legitimate fallback pattern)
        # 2. File is in RAW_LOGGING_ALLOWED_PATTERNS (CLI scripts)
        if (
            has_raw_logging_import
            and not has_augur_logging_import
            and not raw_logging_in_fallback
            and not is_raw_logging_allowed(file_path)
        ):
            # Find the import line
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "logging":
                            violations.append(
                                (
                                    node.lineno,
                                    "raw_import",
                                    "import logging - use 'from src.logging import get_entity_logger' instead",
                                )
                            )
                if isinstance(node, ast.ImportFrom) and node.module == "logging":
                    violations.append(
                        (
                            node.lineno,
                            "raw_import",
                            "from logging import ... - use 'from src.logging import get_entity_logger' instead",
                        )
                    )

    except SyntaxError:
        pass  # Skip files with syntax errors

    return violations


def scan_repo(repo_path: Path) -> int:
    """Scan repository for logging violations."""
    print(f"\nScanning for logging violations: {repo_path}")
    print("=" * 60)

    total_violations = 0
    files_with_violations = 0

    for py_file in repo_path.rglob("*.py"):
        # Skip ignored directories
        if any(ignored in py_file.parts for ignored in IGNORE_DIRS):
            continue

        # Skip ignored files
        if py_file.name in IGNORE_FILES:
            continue

        violations = check_logging_usage(py_file)

        if violations:
            files_with_violations += 1
            rel_path = py_file.relative_to(repo_path)
            print(f"\n{rel_path}")

            for line_num, vtype, message in violations:
                print(f"   Line {line_num}: [{vtype}] {message}")
                total_violations += 1

    if total_violations == 0:
        print("\n All Python files use centralized logging correctly!")
        return 0
    else:
        print(f"\n Found {total_violations} violations in {files_with_violations} files.")
        print("\n Use 'from src.logging import get_entity_logger' for proper logging.")
        return 1


def main():
    """Run logging audit."""
    project_root = Path(__file__).parent.parent.parent

    print("Auditing logging usage...")

    exit_code = scan_repo(project_root)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
