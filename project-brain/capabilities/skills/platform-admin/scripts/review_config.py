"""
Review Configuration - DevOps Agent

Comprehensive review of setup and configuration to identify issues.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

from src.config.paths import get_project_root


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))

def _check_file_exists(path: Path, description: str) -> dict[str, Any]:
    """Check if a required file exists."""
    exists = path.exists()
    return {
        "check": description,
        "path": str(path),
        "status": "pass" if exists else "fail",
        "message": "Found" if exists else "Missing",
    }


def _check_env_var(var: str, description: str, required: bool = False) -> dict[str, Any]:
    """Check environment variable."""
    value = os.environ.get(var)
    if value:
        return {
            "check": description,
            "env_var": var,
            "status": "pass",
            "message": f"Set to: {value[:50]}..." if len(value) > 50 else f"Set to: {value}",
        }
    elif required:
        return {
            "check": description,
            "env_var": var,
            "status": "fail",
            "message": "Required but not set",
        }
    else:
        return {
            "check": description,
            "env_var": var,
            "status": "warn",
            "message": "Not set (optional)",
        }


def _check_directory_structure(base: Path) -> list[dict[str, Any]]:
    """Check expected directory structure."""
    checks = []

    expected_dirs = [
        ("plugins/dev", "Factory layer"),
        ("plugins/observability", "Observability hub"),
        ("plugins/vertical", "Vertical layer"),
        ("apps/dashboard", "Dashboard"),
        ("src/config", "Config modules"),
        ("scripts", "Scripts directory"),
        (".venv", "Virtual environment"),
    ]

    for dir_path, description in expected_dirs:
        full_path = base / dir_path
        checks.append(_check_file_exists(full_path, description))

    return checks


def _check_config_files(base: Path, data_dir: Path) -> list[dict[str, Any]]:
    """Check configuration files."""
    checks = []

    # Code repo configs
    code_configs = [
        ("SETUP.md", "Setup documentation"),
        ("scripts/install.sh", "Install script"),
        ("config/mcp_config.json", "MCP configuration"),
    ]

    for file_path, description in code_configs:
        checks.append(_check_file_exists(base / file_path, f"[code] {description}"))

    # Data repo configs
    if data_dir.exists():
        data_configs = [
            ("config.yaml", "Main configuration"),
            ("llm.yaml", "LLM configuration"),
        ]
        for file_path, description in data_configs:
            checks.append(_check_file_exists(data_dir / file_path, f"[data] {description}"))

    return checks


def _check_dependencies(base: Path) -> list[dict[str, Any]]:
    """Check dependency status."""
    checks = []

    # Python venv
    venv_path = base / ".venv"
    if venv_path.exists():
        checks.append(
            {
                "check": "Python virtual environment",
                "status": "pass",
                "message": "Exists",
            }
        )
    else:
        checks.append(
            {
                "check": "Python virtual environment",
                "status": "fail",
                "message": "Missing - run ./scripts/install.sh",
            }
        )

    # Node modules
    node_modules = base / "apps" / "dashboard" / "node_modules"
    if node_modules.exists():
        checks.append(
            {
                "check": "Dashboard dependencies",
                "status": "pass",
                "message": "Installed",
            }
        )
    else:
        checks.append(
            {
                "check": "Dashboard dependencies",
                "status": "fail",
                "message": "Missing - run: cd apps/dashboard && npm install",
            }
        )

    return checks


def review_config(params: dict = None) -> str:
    """
    Comprehensive configuration review.

    Returns:
        JSON report with all checks and their status
    """
    params = params or {}

    data_dir = Path(os.environ.get("AUGUR_ROOT", get_project_root()))

    results = {
        "directory_structure": _check_directory_structure(PROJECT_ROOT),
        "config_files": _check_config_files(PROJECT_ROOT, data_dir),
        "dependencies": _check_dependencies(PROJECT_ROOT),
        "environment": [
            _check_env_var("AUGUR_ROOT", "Data directory path"),
            _check_env_var("AUGUR_LLM_PROFILE", "LLM profile"),
            _check_env_var("OPENAI_API_KEY", "OpenAI API key"),
        ],
    }

    # Summary
    total = sum(len(v) for v in results.values())
    passed = sum(1 for cat in results.values() for c in cat if c["status"] == "pass")
    failed = sum(1 for cat in results.values() for c in cat if c["status"] == "fail")
    warnings = sum(1 for cat in results.values() for c in cat if c["status"] == "warn")

    results["summary"] = {
        "total_checks": total,
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "status": "healthy" if failed == 0 else "issues_found",
    }

    output_format = params.get("format", "markdown")
    if output_format == "json":
        return json.dumps(results, indent=2)

    return _format_markdown(results)


def _format_markdown(results: dict) -> str:
    """Format results as markdown."""
    lines = [
        "# Configuration Review",
        "",
        f"**Status**: {results['summary']['status'].upper()}",
        f"**Checks**: {results['summary']['passed']}/{results['summary']['total_checks']} passed",
        "",
    ]

    status_icons = {"pass": "✓", "fail": "✗", "warn": "⚠"}

    for category, checks in results.items():
        if category == "summary":
            continue

        lines.append(f"## {category.replace('_', ' ').title()}")
        for check in checks:
            icon = status_icons.get(check["status"], "?")
            lines.append(f"- {icon} {check['check']}: {check['message']}")
        lines.append("")

    if results["summary"]["failed"] > 0:
        lines.append("## Action Required")
        for cat in results.values():
            if isinstance(cat, list):
                for c in cat:
                    if c["status"] == "fail":
                        lines.append(f"- Fix: {c['check']} - {c['message']}")

    return "\n".join(lines)


def main(params: dict = None) -> str:
    """Main entry point."""
    return review_config(params)


if __name__ == "__main__":
    if any(arg in {"-h", "--help"} for arg in sys.argv[1:]):
        _out("usage: review_config.py [--json]")
        _out()
        _out("Review Augur setup and configuration.")
    elif len(sys.argv) > 1 and sys.argv[1] == "--json":
        _out(main({"format": "json"}))
    else:
        _out(main())
