#!/usr/bin/env python3
"""
Validate entity boundaries at commit time.

Checks for:
1. Forbidden Python imports (e.g., CLI importing skills)
2. Subprocess patterns in TypeScript (execFile, spawn, exec)
3. Inline Python code generation in TypeScript
"""

import ast
import re
import sys
from pathlib import Path
from typing import List

BOUNDARY_RULES = {
    "src/cli.py": {
        "forbidden": ["packages."],  # CLI can't import skills
        "required": [],
    },
    "apps/dashboard/app/api": {
        "forbidden_patterns": [
            r"execFile\(",
            r"spawn\(",
            r"exec\(",
            r'import\s+sys.*sys\.path\.insert.*".*augur"',  # Inline Python
        ],
        "required": [],
    },
}

# Route families that intentionally proxy provider-specific subprocess bridges.
# Keep this list explicit and narrow.
TS_SUBPROCESS_ALLOWLIST = {
    "apps/dashboard/app/api/google-workspace/",
}


def check_python_imports(file_path: Path) -> List[str]:
    """
    Check Python file for forbidden imports.

    Args:
        file_path: Path to Python file

    Returns:
        List of violation messages
    """
    violations = []

    try:
        with open(file_path) as f:
            tree = ast.parse(f.read(), filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    violations.extend(check_import(file_path, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    violations.extend(check_import(file_path, node.module))

    except SyntaxError:
        pass  # Skip files with syntax errors

    return violations


def check_import(file_path: Path, module_name: str) -> List[str]:
    """
    Check if import violates boundary rules.

    Args:
        file_path: Path to file
        module_name: Module being imported

    Returns:
        List of violation messages
    """
    violations = []

    for path_pattern, rules in BOUNDARY_RULES.items():
        if path_pattern in str(file_path):
            # Check forbidden imports
            for forbidden in rules.get("forbidden", []):
                if module_name.startswith(forbidden):
                    violations.append(
                        f"{file_path}: Forbidden import '{module_name}' " f"(violates boundary rule for {path_pattern})"
                    )

    return violations


def has_typescript_subprocess_exemption(content: str, pattern: str) -> bool:
    """Return True when a route explicitly documents a subprocess exemption."""
    if "boundary-ignore: all" in content:
        return True
    if f"boundary-ignore: {pattern}" in content:
        return True
    if "@spawn-exempt:" in content:
        return True
    return False


def check_typescript_subprocess(file_path: Path) -> List[str]:
    """
    Check TypeScript file for subprocess patterns.

    Args:
        file_path: Path to TypeScript file

    Returns:
        List of violation messages
    """
    violations = []

    try:
        with open(file_path) as f:
            content = f.read()

        # Check if file is in API routes
        if "apps/dashboard/app/api" in str(file_path):
            if any(allowed in str(file_path) for allowed in TS_SUBPROCESS_ALLOWLIST):
                return violations
            for pattern in BOUNDARY_RULES["apps/dashboard/app/api"]["forbidden_patterns"]:
                if re.search(pattern, content):
                    # Check if violation is explicitly ignored
                    if has_typescript_subprocess_exemption(content, pattern):
                        continue
                    violations.append(
                        f"{file_path}: Found subprocess pattern '{pattern}' " f"(should use MCPBridge instead)"
                    )

    except Exception:
        # Skip files that can't be read
        pass

    return violations


def main():
    """Run boundary validation."""
    project_root = Path(__file__).parent.parent.parent
    violations = []

    print("🔍 Validating entity boundaries...")

    # Check Python files
    for py_file in project_root.rglob("*.py"):
        if ".venv" in str(py_file) or "node_modules" in str(py_file):
            continue
        violations.extend(check_python_imports(py_file))

    # Check TypeScript files
    for ts_file in project_root.rglob("*.ts"):
        if "node_modules" in str(ts_file) or ".next" in str(ts_file):
            continue
        violations.extend(check_typescript_subprocess(ts_file))

    if violations:
        print("\n❌ BOUNDARY VIOLATIONS DETECTED:\n")
        for violation in violations:
            print(f"  • {violation}")
        print("\n💡 Fix these violations before committing. " "See docs/adr/ADR-002-mcp-only-communication.md\n")
        sys.exit(1)

    print("✅ All boundary checks passed\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
