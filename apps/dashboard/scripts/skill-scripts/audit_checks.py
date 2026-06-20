"""Plugin audit check functions.

Individual compliance checks used by audit.py:
    check_required_files  — profile-aware required file validation
    check_dashboard_yaml  — dashboard.yaml schema compliance
    check_code_quality    — hardcoded path detection
    check_logging         — logging compliance (print, basicConfig)
    check_naming          — naming conventions

Size checks (count_lines, count_mcp_tools, check_size_limits) live
in audit_size.py and are re-exported here for backward compatibility.

Split from audit.py for module size management.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

import yaml

from audit import AuditResult, _collect_code_files, logger


def check_required_files(plugin_path: Path, spec: dict, profile: str = "full") -> List[AuditResult]:
    """Check for required files based on plugin profile (ADR-040).

    Args:
        plugin_path: Path to the plugin directory
        spec: Loaded plugin specification
        profile: Plugin profile ('minimal', 'standard', 'full')
    """
    results = []

    # === ALL PROFILES: SKILL.md is always required ===
    skill_md = plugin_path / "SKILL.md"
    results.append(
        AuditResult(
            rule="required_file",
            passed=skill_md.exists(),
            message="Required file: SKILL.md",
            file_path=str(skill_md),
        )
    )

    # Check SKILL.md frontmatter has required fields
    if skill_md.exists():
        try:
            content = skill_md.read_text()
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    fm = yaml.safe_load(parts[1]) or {}
                    for field in ["name", "version", "description"]:
                        results.append(
                            AuditResult(
                                rule="frontmatter_field",
                                passed=field in fm and fm[field],
                                message=f"SKILL.md frontmatter: '{field}' is required",
                                file_path=str(skill_md),
                            )
                        )
        except (OSError, UnicodeDecodeError, yaml.YAMLError, TypeError, ValueError) as exc:
            logger.debug("Failed to parse SKILL.md frontmatter for %s: %s", plugin_path, exc)

    # === MINIMAL PROFILE: at least one capability dir ===
    has_capability = (
        (plugin_path / "scripts").is_dir() or (plugin_path / "modules").is_dir() or (plugin_path / "mcp").is_dir()
    )
    results.append(
        AuditResult(
            rule="required_capability",
            passed=has_capability,
            message="At least one of: scripts/, modules/, mcp/ required",
            file_path=str(plugin_path),
        )
    )

    if profile == "minimal":
        return results

    # === STANDARD PROFILE: dashboard files ===
    dashboard_yaml = plugin_path / "dashboard.yaml"
    results.append(
        AuditResult(
            rule="required_file",
            passed=dashboard_yaml.exists(),
            message="Required file: dashboard.yaml",
            file_path=str(dashboard_yaml),
        )
    )

    for filename in ["page.tsx", "layout.tsx", "loading.tsx"]:
        file_path = plugin_path / "dashboard" / filename
        results.append(
            AuditResult(
                rule="required_file",
                passed=file_path.exists(),
                message=f"Required dashboard file: {filename}",
                file_path=str(file_path),
            )
        )

    # At least one test file
    test_files = list((plugin_path / "tests").glob("test_*.py")) if (plugin_path / "tests").exists() else []
    test_files.extend(list((plugin_path / "tests").glob("*.test.tsx")) if (plugin_path / "tests").exists() else [])
    test_files.extend(
        list((plugin_path / "dashboard").rglob("*.test.tsx")) if (plugin_path / "dashboard").exists() else []
    )
    results.append(
        AuditResult(
            rule="required_file",
            passed=len(test_files) > 0,
            message="At least one test file required (standard profile)",
            file_path=str(plugin_path / "tests"),
        )
    )

    if profile == "standard":
        return results

    # === FULL PROFILE: API, MCP, version ===
    health_route = plugin_path / "api" / "health" / "route.ts"
    results.append(
        AuditResult(
            rule="required_file",
            passed=health_route.exists(),
            message="Required API file: health/route.ts",
            file_path=str(health_route),
        )
    )

    for filename in ["__init__.py", "tools.py"]:
        file_path = plugin_path / "mcp" / filename
        results.append(
            AuditResult(
                rule="required_file",
                passed=file_path.exists(),
                message=f"Required MCP file: {filename}",
                file_path=str(file_path),
            )
        )

    version_yaml = plugin_path / "augur" / "version.yaml"
    results.append(
        AuditResult(
            rule="required_file",
            passed=version_yaml.exists(),
            message="Required file: augur/version.yaml",
            file_path=str(version_yaml),
        )
    )

    return results


def check_dashboard_yaml(plugin_path: Path, spec: dict) -> List[AuditResult]:
    """Check dashboard.yaml schema compliance."""
    results = []
    dashboard_yaml_path = plugin_path / "dashboard.yaml"

    if not dashboard_yaml_path.exists():
        results.append(
            AuditResult(
                rule="dashboard_yaml",
                passed=False,
                message="dashboard.yaml not found",
                file_path=str(dashboard_yaml_path),
            )
        )
        return results

    try:
        with open(dashboard_yaml_path) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        results.append(
            AuditResult(
                rule="dashboard_yaml",
                passed=False,
                message=f"Invalid YAML: {e}",
                file_path=str(dashboard_yaml_path),
            )
        )
        return results

    # Required hub fields
    hub = config.get("hub", {})
    required_hub_fields = ["id", "title", "subtitle", "icon"]
    for field_name in required_hub_fields:
        results.append(
            AuditResult(
                rule="dashboard_yaml_hub",
                passed=field_name in hub,
                message=f"hub.{field_name} is required",
                file_path=str(dashboard_yaml_path),
            )
        )

    # Valid mode
    valid_modes = ["all", "dev", "operation"]
    mode = config.get("mode", "all")
    results.append(
        AuditResult(
            rule="dashboard_yaml_mode",
            passed=mode in valid_modes,
            message=f"mode must be one of: {valid_modes}",
            file_path=str(dashboard_yaml_path),
        )
    )

    # Tabs - first must be overview with default: true
    tabs = config.get("tabs", [])
    if tabs:
        first_tab = tabs[0]
        results.append(
            AuditResult(
                rule="dashboard_yaml_tabs",
                passed=first_tab.get("id") == "overview" and first_tab.get("default") is True,
                message="First tab must be 'overview' with default: true",
                file_path=str(dashboard_yaml_path),
            )
        )

    # data_dir matches hub.id (flat structure)
    data_dir = config.get("data_dir", "")
    hub_id = hub.get("id", "")
    results.append(
        AuditResult(
            rule="dashboard_yaml_data_dir",
            passed=data_dir == hub_id or data_dir in ["", hub_id],
            message=f"data_dir should match hub.id ('{hub_id}')",
            file_path=str(dashboard_yaml_path),
        )
    )

    return results


def check_code_quality(plugin_path: Path, spec: dict) -> List[AuditResult]:
    """Check code quality rules."""
    results = []

    # Check for hardcoded paths (audit-ignore: these are detection patterns, not hardcoded paths)
    hardcoded_patterns = [
        r"/Users/\w+",  # audit-ignore
        r"C:\\Users\\",  # audit-ignore
    ]

    python_files = _collect_code_files(plugin_path, "*.py")
    ts_files = _collect_code_files(plugin_path, "*.ts")
    tsx_files = _collect_code_files(plugin_path, "*.tsx")

    all_code_files = python_files + ts_files + tsx_files

    for file_path in all_code_files:
        if "tests" in file_path.parts:
            continue
        try:
            for line in file_path.read_text().splitlines():
                if "audit-ignore" in line:
                    continue
                for pattern in hardcoded_patterns:
                    matches = re.findall(pattern, line)
                    if matches:
                        results.append(
                            AuditResult(
                                rule="hardcoded_path",
                                passed=False,
                                message=f"Hardcoded path found: {matches[0]}",
                                file_path=str(file_path),
                                fixable=False,
                            )
                        )
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            logger.debug("Failed while scanning %s for hardcoded paths: %s", file_path, exc)

    # If no hardcoded paths found, add a pass
    hardcoded_results = [r for r in results if r.rule == "hardcoded_path"]
    if not hardcoded_results:
        results.append(
            AuditResult(
                rule="hardcoded_path",
                passed=True,
                message="No hardcoded paths found",
            )
        )

    return results


def check_logging(plugin_path: Path, spec: dict) -> List[AuditResult]:
    """Check logging compliance."""
    results = []
    logging_spec = spec.get("logging", {})
    logging_spec.get("forbidden", [])
    exceptions = logging_spec.get("exceptions", [])

    # Get all Python files except exceptions
    python_files = _collect_code_files(plugin_path, "*.py")

    for file_path in python_files:
        # Skip exceptions
        relative_path = str(file_path.relative_to(plugin_path))
        skip = False
        for exc in exceptions:
            if exc.endswith("/"):
                if relative_path.startswith(exc):
                    skip = True
                    break
            elif exc in relative_path:
                skip = True
                break

        if skip:
            continue

        try:
            content = file_path.read_text()
            lines = content.split("\n")

            for i, line in enumerate(lines, 1):
                if "audit-ignore" in line:
                    continue
                if line.strip().startswith("#"):
                    continue

                # Check for print() (but not in comments or strings)
                if "pr" "int(" in line:  # audit-ignore: detector literal
                    # Simple check - not perfect but catches most cases
                    if not line.strip().startswith("#"):
                        results.append(
                            AuditResult(
                                rule="logging_print",
                                passed=False,
                                message="stdout print call found - use logger instead",
                                file_path=str(file_path),
                                line_number=i,
                                fixable=True,
                            )
                        )

                # Check for direct logging import
                if "import logging" in line and "augur_logging" not in line:
                    results.append(
                        AuditResult(
                            rule="logging_import",
                            passed=False,
                            message="Direct 'import logging' - use src/lib.augur_logging",
                            file_path=str(file_path),
                            line_number=i,
                            fixable=True,
                        )
                    )

                # Check for legacy logging basicConfig calls.
                if "logging." "basicConfig" in line:  # audit-ignore: detector literal
                    results.append(
                        AuditResult(
                            rule="logging_basicconfig",
                            passed=False,
                            message="logging basicConfig() found - configured centrally",
                            file_path=str(file_path),
                            line_number=i,
                            fixable=True,
                        )
                    )

        except (OSError, UnicodeDecodeError, ValueError) as exc:
            logger.debug("Failed while scanning %s for logging patterns: %s", file_path, exc)

    # If no logging issues found in library code, add a pass
    logging_results = [r for r in results if r.rule.startswith("logging_")]
    if not logging_results:
        results.append(
            AuditResult(
                rule="logging",
                passed=True,
                message="Logging compliance: OK",
            )
        )

    return results


def check_naming(plugin_path: Path, plugin_name: str) -> List[AuditResult]:
    """Check naming conventions."""
    results = []

    # Plugin folder should match hub.id
    dashboard_yaml_path = plugin_path / "dashboard.yaml"
    if dashboard_yaml_path.exists():
        try:
            with open(dashboard_yaml_path) as f:
                config = yaml.safe_load(f)
            hub_id = config.get("hub", {}).get("id", "")
            legacy_aliases = {
                "mcp-app-factory": {"factory"},
                "smb-client-template": {"smb-client-template"},
                "consulting-template": {"consulting-template"},
                "home-automation": {"home"},
            }
            allowed_hub_ids = {plugin_name} | legacy_aliases.get(plugin_name, set())
            results.append(
                AuditResult(
                    rule="naming_hub_id",
                    passed=hub_id in allowed_hub_ids,
                    message=f"Plugin folder '{plugin_name}' should match hub.id '{hub_id}'",
                    file_path=str(dashboard_yaml_path),
                )
            )
        except (OSError, UnicodeDecodeError, yaml.YAMLError, TypeError, ValueError) as exc:
            logger.debug("Failed to validate hub.id in %s: %s", dashboard_yaml_path, exc)

    # Schema files should end in .schema.yaml
    schemas_dir = plugin_path / "schemas"
    if schemas_dir.exists():
        schema_files = list(schemas_dir.glob("*.yaml"))
        bad_schemas = [f for f in schema_files if not f.name.endswith(".schema.yaml")]
        results.append(
            AuditResult(
                rule="naming_schema",
                passed=len(bad_schemas) == 0,
                message="Schema files must end in .schema.yaml",
                file_path=str(schemas_dir),
            )
        )

    return results


# Re-export size check functions for backward compatibility
from audit_size import count_lines, count_mcp_tools, check_size_limits  # noqa: F401
