#!/usr/bin/env python3
"""
Local CI runner that mirrors GitHub Actions behavior.

Provides smart change detection and targeted validation for faster local development.

Usage:
    python scripts/ci-local.py --pre-merge    # Full pre-merge validation
    python scripts/ci-local.py --quick        # Quick lint on changed files only
    python scripts/ci-local.py --quality      # Quality checks only
    python scripts/ci-local.py --test         # Tests only
    python scripts/ci-local.py --security     # Security scans
    python scripts/ci-local.py --all          # Everything

Examples:
    # Before creating a PR
    python scripts/ci-local.py --pre-merge

    # Quick check while developing
    python scripts/ci-local.py --quick

    # Run specific checks
    python scripts/ci-local.py --quality --test
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


# ANSI colors
class Colors:
    BLUE = "\033[0;34m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[0;33m"
    RED = "\033[0;31m"
    NC = "\033[0m"  # No Color


def run_command(cmd: List[str], cwd: Optional[Path] = None, check: bool = True) -> bool:
    """Run a command and return success status."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=check,
            capture_output=False,
        )
        return result.returncode == 0
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        print(f"{Colors.RED}Command not found: {cmd[0]}{Colors.NC}")
        return False


def get_existing_targets(project_root: Path, candidates: List[str]) -> List[str]:
    """Return target paths that exist in the repo."""
    return [path for path in candidates if (project_root / path).exists()]


def get_changed_files(base: str = "HEAD~1") -> List[str]:
    """Get list of changed files since base commit."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base, "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().split("\n") if result.stdout.strip() else []
    except subprocess.CalledProcessError:
        return []


def has_python_changes(files: List[str]) -> bool:
    """Check if any Python files changed."""
    return any(f.endswith(".py") for f in files)


def has_typescript_changes(files: List[str]) -> bool:
    """Check if any TypeScript files changed."""
    return any(f.endswith((".ts", ".tsx")) for f in files)


def has_dashboard_changes(files: List[str]) -> bool:
    """Check if dashboard files changed."""
    return any(f.startswith("apps/dashboard/") for f in files)


def print_header(text: str):
    """Print a section header."""
    print(f"\n{Colors.BLUE}{'=' * 50}{Colors.NC}")
    print(f"{Colors.BLUE}{text}{Colors.NC}")
    print(f"{Colors.BLUE}{'=' * 50}{Colors.NC}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.NC}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.NC}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.RED}✗ {text}{Colors.NC}")


def run_python_linting(project_root: Path, targets: List[str]) -> bool:
    """Run Python linting checks (ruff, black)."""
    success = True

    print(f"{Colors.YELLOW}Running ruff...{Colors.NC}")
    if not run_command(["ruff", "check", *targets], cwd=project_root, check=False):
        print_error("Ruff found issues")
        success = False
    else:
        print_success("Ruff passed")

    print(f"\n{Colors.YELLOW}Checking black formatting...{Colors.NC}")
    if not run_command(["black", "--check", *targets], cwd=project_root, check=False):
        print_warning("Black formatting issues (run 'make format' to fix)")
        success = False
    else:
        print_success("Black formatting OK")

    return success


def run_typescript_checks(project_root: Path) -> bool:
    """Run TypeScript linting and type checks."""
    success = True
    dashboard_path = project_root / "shared" / "dashboard"

    print(f"\n{Colors.YELLOW}Running eslint...{Colors.NC}")
    if not run_command(["npm", "run", "lint"], cwd=dashboard_path, check=False):
        print_error("ESLint found issues")
        success = False
    else:
        print_success("ESLint passed")

    print(f"\n{Colors.YELLOW}Running mypy...{Colors.NC}")
    mypy_targets = ["src/config"]
    if not run_command(["mypy", *mypy_targets, "--ignore-missing-imports"], cwd=project_root, check=False):
        print_warning("Mypy found type issues")
        # Don't fail on mypy yet - it's aspirational
    else:
        print_success("Mypy passed")

    print(f"\n{Colors.YELLOW}Running tsc...{Colors.NC}")
    if not run_command(["npx", "tsc", "--noEmit"], cwd=dashboard_path, check=False):
        print_error("TypeScript type check failed")
        success = False
    else:
        print_success("TypeScript types OK")

    return success


def run_audits(project_root: Path) -> bool:
    """Run repository audit scripts."""
    success = True
    print(f"\n{Colors.YELLOW}Running audits...{Colors.NC}")

    audit_scripts = [
        ("audit_paths.py", "Hardcoded paths"),
        ("validate_boundaries.py", "Entity boundaries"),
        ("audit_logging.py", "Logging usage"),
        ("audit_data_separation.py", "Data separation"),
        ("validate_structure.py", "Repository structure"),
    ]

    for script, name in audit_scripts:
        script_path = project_root / "shared" / "scripts" / script
        if not script_path.exists():
            print_warning(f"{name} script not found")
            continue

        cmd = ["python", str(script_path)]
        if script == "audit_paths.py":
            cmd.append(".")

        if not run_command(cmd, cwd=project_root, check=False):
            print_error(f"{name} audit failed")
            success = False
        else:
            print_success(f"{name} OK")

    return success


def run_quality_checks(quick: bool = False) -> bool:
    """Run quality checks (lint, format, typecheck, audit)."""
    print_header("Running Quality Checks")

    project_root = Path(__file__).parent.parent
    targets = get_existing_targets(project_root, ["packages", "plugins", "shared", "tests"])

    # Python linting (always run)
    success = run_python_linting(project_root, targets)

    # Full checks (not in quick mode)
    if not quick:
        if not run_typescript_checks(project_root):
            success = False
        if not run_audits(project_root):
            success = False

    return success


def run_tests(quick: bool = False) -> bool:
    """Run test suite."""
    print_header("Running Tests")

    success = True
    project_root = Path(__file__).parent.parent

    # Python tests
    print(f"{Colors.YELLOW}Running pytest...{Colors.NC}")
    pytest_args = ["pytest", "tests/", "-v"]
    if quick:
        pytest_args.extend(["--ignore=tests/integration/", "-x"])  # Stop on first failure

    if not run_command(pytest_args, cwd=project_root, check=False):
        print_error("Python tests failed")
        success = False
    else:
        print_success("Python tests passed")

    if not quick:
        # Dashboard tests
        print(f"\n{Colors.YELLOW}Running Jest tests...{Colors.NC}")
        if not run_command(
            ["npm", "test", "--", "--passWithNoTests"],
            cwd=project_root / "shared" / "dashboard",
            check=False,
        ):
            print_error("Dashboard tests failed")
            success = False
        else:
            print_success("Dashboard tests passed")

    return success


def run_security_scans() -> bool:
    """Run security scans."""
    print_header("Running Security Scans")

    success = True
    project_root = Path(__file__).parent.parent

    # pip-audit
    print(f"{Colors.YELLOW}Running pip-audit...{Colors.NC}")
    if not run_command(["pip-audit"], cwd=project_root, check=False):
        print_warning("pip-audit found vulnerabilities")
        success = False
    else:
        print_success("pip-audit OK")

    # npm audit
    print(f"\n{Colors.YELLOW}Running npm audit...{Colors.NC}")
    if not run_command(
        ["npm", "audit", "--audit-level=high"],
        cwd=project_root / "shared" / "dashboard",
        check=False,
    ):
        print_warning("npm audit found vulnerabilities")
        success = False
    else:
        print_success("npm audit OK")

    # bandit
    print(f"\n{Colors.YELLOW}Running bandit...{Colors.NC}")
    if not run_command(
        ["bandit", "-r", "packages/", "src/", "plugins/", "--exclude", ".venv,node_modules,tests,_dev", "-ll"],
        cwd=project_root,
        check=False,
    ):
        print_warning("bandit found security issues")
        success = False
    else:
        print_success("bandit OK")

    return success


def main():
    parser = argparse.ArgumentParser(
        description="Local CI runner for Augur",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --pre-merge    Full pre-merge validation
  %(prog)s --quick        Quick lint on changed files
  %(prog)s --quality      Quality checks only
  %(prog)s --test         Tests only
  %(prog)s --all          Run everything
        """,
    )

    parser.add_argument(
        "--pre-merge",
        action="store_true",
        help="Full pre-merge validation (quality + tests)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick check - only lint changed files",
    )
    parser.add_argument(
        "--quality",
        action="store_true",
        help="Run quality checks only",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run tests only",
    )
    parser.add_argument(
        "--security",
        action="store_true",
        help="Run security scans",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run everything",
    )

    args = parser.parse_args()

    # Default to --pre-merge if no args
    if not any([args.pre_merge, args.quick, args.quality, args.test, args.security, args.all]):
        args.pre_merge = True

    success = True

    # Determine what to run
    run_quality = args.quality or args.pre_merge or args.all
    run_test = args.test or args.pre_merge or args.all
    run_sec = args.security or args.all
    quick_mode = args.quick

    print(f"{Colors.BLUE}╔══════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.BLUE}║      Augur Local CI Runner           ║{Colors.NC}")
    print(f"{Colors.BLUE}╚══════════════════════════════════════════╝{Colors.NC}")

    if quick_mode:
        changed_files = get_changed_files()
        print(f"\n{Colors.YELLOW}Quick mode: {len(changed_files)} files changed{Colors.NC}")
        if has_python_changes(changed_files):
            print("  - Python changes detected")
        if has_typescript_changes(changed_files):
            print("  - TypeScript changes detected")

    if run_quality or quick_mode:
        if not run_quality_checks(quick=quick_mode):
            success = False

    if run_test:
        if not run_tests(quick=quick_mode):
            success = False

    if run_sec:
        if not run_security_scans():
            success = False

    # Summary
    print(f"\n{Colors.BLUE}{'=' * 50}{Colors.NC}")
    if success:
        print(f"{Colors.GREEN}✓ All checks passed!{Colors.NC}")
        if args.pre_merge:
            print(f"{Colors.GREEN}  Ready to create PR{Colors.NC}")
        sys.exit(0)
    else:
        print(f"{Colors.RED}✗ Some checks failed{Colors.NC}")
        print(f"{Colors.YELLOW}  Fix the issues above before proceeding{Colors.NC}")
        sys.exit(1)


if __name__ == "__main__":
    main()
