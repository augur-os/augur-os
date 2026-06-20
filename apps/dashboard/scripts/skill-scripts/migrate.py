"""
Plugin Migration Script

Analyze existing skills and migrate them to compliant Augur plugins.

Usage:
    python migrate.py --analyze career          # Analyze what exists vs required
    python migrate.py --migrate career          # Generate missing files only
    python migrate.py --migrate career --force  # Overwrite existing files
"""

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

import yaml


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Add project root to path
SCRIPT_DIR = Path(__file__).parent
PLUGIN_ROOT = SCRIPT_DIR.parent

try:
    from src.config.paths import get_project_root
    PROJECT_ROOT = get_project_root()
except ImportError:
    PROJECT_ROOT = PLUGIN_ROOT.parent.parent.parent.parent  # fallback

sys.path.insert(0, str(PROJECT_ROOT))

from src.logging import get_entity_logger  # noqa: E402

logger = get_entity_logger("mcp-app-factory")

# Template directory
TEMPLATES_DIR = PLUGIN_ROOT / "templates"

# Plugin spec
SPEC_PATH = PLUGIN_ROOT / "plugin-spec.yaml"


@dataclass
class FileStatus:
    """Status of a required file."""

    path: str
    required: bool
    exists: bool
    compliant: bool = True
    issues: List[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Result of analyzing an existing skill."""

    skill_name: str
    skill_path: str
    bundle: str
    exists: bool
    has_dashboard_yaml: bool
    has_skill_md: bool

    # File analysis
    existing_files: List[str] = field(default_factory=list)
    missing_required: List[str] = field(default_factory=list)
    missing_optional: List[str] = field(default_factory=list)

    # Code analysis
    uses_print: List[Dict[str, Any]] = field(default_factory=list)
    uses_direct_logging: List[Dict[str, Any]] = field(default_factory=list)
    hardcoded_paths: List[Dict[str, Any]] = field(default_factory=list)

    # dashboard.yaml analysis
    dashboard_yaml_issues: List[str] = field(default_factory=list)

    # Extracted info for migration
    detected_hub_id: Optional[str] = None
    detected_title: Optional[str] = None
    detected_description: Optional[str] = None
    detected_category: Optional[str] = None

    @property
    def migration_score(self) -> float:
        """Calculate how much work is needed (0-100, higher = more complete)."""
        total_checks = 10
        passed = 0

        if self.exists:
            passed += 1
        if self.has_dashboard_yaml:
            passed += 2
        if self.has_skill_md:
            passed += 1
        if len(self.missing_required) == 0:
            passed += 2
        if len(self.uses_print) == 0:
            passed += 1
        if len(self.uses_direct_logging) == 0:
            passed += 1
        if len(self.hardcoded_paths) == 0:
            passed += 1
        if len(self.dashboard_yaml_issues) == 0:
            passed += 1

        return (passed / total_checks) * 100


def load_spec() -> dict:
    """Load the plugin specification."""
    if not SPEC_PATH.exists():
        logger.warning(f"Plugin spec not found at {SPEC_PATH}, utilizing defaults")
        return {}
    with open(SPEC_PATH) as f:
        return yaml.safe_load(f)


def discover_skills() -> List[tuple]:
    """Discover all skills in the plugins/ directory and external app directories."""
    skills = []
    
    # 1. Internal skills
    plugins_dir = PROJECT_ROOT / "plugins"
    if plugins_dir.exists():
        for bundle_dir in plugins_dir.iterdir():
            if not bundle_dir.is_dir():
                continue
            bundle_name = bundle_dir.name

            skills_dir = bundle_dir / "skills"
            if not skills_dir.exists():
                continue

            for skill_dir in skills_dir.iterdir():
                if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                    continue
                skills.append((bundle_name, skill_dir.name, skill_dir))

    # 2. External skills
    external_skill_dirs = [
        ("codex", Path.home() / ".codex" / "skills"),
        ("claude", Path.home() / ".claude" / "plugins"),
        ("cowork", Path.home() / ".cowork" / "skills"),
    ]
    for ext_bundle, ext_dir in external_skill_dirs:
        if ext_dir.exists() and ext_dir.is_dir():
            for skill_dir in ext_dir.iterdir():
                if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                    continue
                skills.append((ext_bundle, skill_dir.name, skill_dir))

    return skills


def find_skill(name: str) -> Optional[tuple]:
    """Find a skill by name."""
    skills = discover_skills()
    for bundle, skill_name, skill_path in skills:
        if skill_name == name:
            return (bundle, skill_name, skill_path)
    return None


def find_skill_path(name: str) -> Optional[str]:
    """Find a skill path by name."""
    result = find_skill(name)
    if result:
        return result[2]  # Return the path (3rd element of tuple)
    return None


def analyze_python_file(file_path: Path) -> Dict[str, List[Dict]]:
    """Analyze a Python file for issues."""
    issues = {
        "print_statements": [],
        "direct_logging": [],
        "hardcoded_paths": [],
    }

    try:
        content = file_path.read_text()
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # Skip comments
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            # Check for print()
            if "_out(" in line:
                issues["print_statements"].append(
                    {
                        "file": str(file_path),
                        "line": i,
                        "content": line.strip()[:100],
                    }
                )

            # Check for direct logging import
            if "import logging" in line and "augur_logging" not in line:
                issues["direct_logging"].append(
                    {
                        "file": str(file_path),
                        "line": i,
                        "content": line.strip(),
                    }
                )

            # Check for hardcoded paths (audit-ignore: these are detection patterns)
            import re

            path_patterns = [
                r'/Users/\w+',  # audit-ignore
                r'~/Projects/',  # audit-ignore
                r'C:\\Users\\',  # audit-ignore
                r'/home/\w+',  # audit-ignore
            ]
            for pattern in path_patterns:
                if re.search(pattern, line):
                    issues["hardcoded_paths"].append(
                        {
                            "file": str(file_path),
                            "line": i,
                            "content": line.strip()[:100],
                            "pattern": pattern,
                        }
                    )
                    break

    except Exception as e:
        logger.warning(f"Could not analyze {file_path}: {e}")

    return issues


def analyze_dashboard_yaml(yaml_path: Path) -> tuple:
    """Analyze dashboard.yaml and extract info."""
    issues = []
    info = {}

    if not yaml_path.exists():
        return issues, info

    try:
        with open(yaml_path) as f:
            config = yaml.safe_load(f)

        hub = config.get("hub", {})

        # Extract info
        info["hub_id"] = hub.get("id")
        info["title"] = hub.get("title")
        info["subtitle"] = hub.get("subtitle")
        info["category"] = hub.get("category")
        info["icon"] = hub.get("icon")

        # Check required fields
        required_hub = ["id", "title", "subtitle", "icon", "category"]
        for field in required_hub:
            if field not in hub:
                issues.append(f"Missing hub.{field}")

        # Check category validity
        valid_categories = ["system", "productivity", "personal", "business"]
        if hub.get("category") and hub.get("category") not in valid_categories:
            issues.append(f"Invalid category: {hub.get('category')}")

        # Check mode
        valid_modes = ["all", "dev", "operation"]
        mode = config.get("mode")
        if mode and mode not in valid_modes:
            issues.append(f"Invalid mode: {mode}")

        # Check tabs
        tabs = config.get("tabs", [])
        if tabs:
            first_tab = tabs[0]
            if first_tab.get("id") != "overview":
                issues.append("First tab should be 'overview'")
            if not first_tab.get("default"):
                issues.append("First tab should have default: true")

        # Check data_dir
        data_dir = config.get("data_dir")
        hub_id = hub.get("id")
        if data_dir and hub_id and data_dir != hub_id:
            issues.append(f"data_dir '{data_dir}' should match hub.id '{hub_id}'")

    except Exception as e:
        issues.append(f"YAML parse error: {e}")

    return issues, info


def analyze_skill(skill_path: Path, skill_name: str, bundle: str) -> AnalysisResult:
    """Analyze an existing skill for migration."""
    result = AnalysisResult(
        skill_name=skill_name,
        skill_path=str(skill_path),
        bundle=bundle,
        exists=skill_path.exists(),
        has_dashboard_yaml=(skill_path / "dashboard.yaml").exists(),
        has_skill_md=(skill_path / "SKILL.md").exists(),
    )

    if not result.exists:
        return result

    # Scan existing files
    for file_path in skill_path.rglob("*"):
        if file_path.is_file():
            rel_path = str(file_path.relative_to(skill_path))
            result.existing_files.append(rel_path)

    # Check required files
    required_files = [
        "dashboard.yaml",
        "SKILL.md",
        "README.md",
        "augur/version.yaml",
        "requirements.txt",
        "package.json",
    ]

    for req_file in required_files:
        if not (skill_path / req_file).exists():
            result.missing_required.append(req_file)

    # Check dashboard files
    if (skill_path / "dashboard").exists():
        dashboard_required = [
            "dashboard/page.tsx",
            "dashboard/layout.tsx",
            "dashboard/loading.tsx",
            "dashboard/tabs/OverviewTab.tsx",
        ]
        for req_file in dashboard_required:
            if not (skill_path / req_file).exists():
                result.missing_required.append(req_file)

    # Check API files
    if (skill_path / "api").exists():
        if not (skill_path / "api" / "health" / "route.ts").exists():
            result.missing_required.append("api/health/route.ts")

    # Check MCP files
    if (skill_path / "mcp").exists():
        mcp_required = ["mcp/__init__.py", "mcp/tools.py"]
        for req_file in mcp_required:
            if not (skill_path / req_file).exists():
                result.missing_required.append(req_file)

    # Check optional directories
    optional_dirs = ["backlog", "chains", "schemas", "tests", "scripts"]
    for opt_dir in optional_dirs:
        if not (skill_path / opt_dir).exists():
            result.missing_optional.append(f"{opt_dir}/")

    # Analyze Python files for code issues
    for py_file in skill_path.rglob("*.py"):
        # Skip test files and CLI scripts
        rel_path = str(py_file.relative_to(skill_path))
        if "test" in rel_path.lower() or "__main__" in rel_path or "cli.py" in rel_path:
            continue

        issues = analyze_python_file(py_file)
        result.uses_print.extend(issues["print_statements"])
        result.uses_direct_logging.extend(issues["direct_logging"])
        result.hardcoded_paths.extend(issues["hardcoded_paths"])

    # Analyze dashboard.yaml
    dashboard_issues, dashboard_info = analyze_dashboard_yaml(skill_path / "dashboard.yaml")
    result.dashboard_yaml_issues = dashboard_issues
    result.detected_hub_id = dashboard_info.get("hub_id")
    result.detected_title = dashboard_info.get("title")
    result.detected_description = dashboard_info.get("subtitle")
    result.detected_category = dashboard_info.get("category")

    return result


def read_template(template_name: str) -> str:
    """Read a template file."""
    template_path = TEMPLATES_DIR / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    return template_path.read_text()


def to_kebab_case(name: str) -> str:
    """Convert name to kebab-case."""
    import re

    name = re.sub(r"[\s_]+", "-", name)
    name = re.sub(r"([a-z])([A-Z])", r"\1-\2", name)
    return name.lower()


def to_title_case(name: str) -> str:
    """Convert kebab-case to Title Case."""
    return " ".join(word.capitalize() for word in name.split("-"))


def to_snake_case(name: str) -> str:
    """Convert kebab-case to snake_case."""
    return name.replace("-", "_")


def get_template_variables(analysis: AnalysisResult) -> dict:
    """Generate template variables from analysis."""
    plugin_name = to_kebab_case(analysis.skill_name)
    plugin_title = analysis.detected_title or to_title_case(analysis.skill_name)

    category_icons = {
        "system": "Settings",
        "productivity": "Zap",
        "personal": "User",
        "business": "Briefcase",
    }

    category = analysis.detected_category or "productivity"

    return {
        "PLUGIN_NAME": plugin_name,
        "PLUGIN_TITLE": plugin_title,
        "PLUGIN_DESCRIPTION": analysis.detected_description or f"{plugin_title} plugin",
        "HUB_ID": analysis.detected_hub_id or plugin_name,
        "CATEGORY": category,
        "BUNDLE": analysis.bundle,
        "SKILL": analysis.skill_name,
        "LUCIDE_ICON": category_icons.get(category, "Box"),
        "DATE": datetime.now().strftime("%Y-%m-%d"),
        "DATA_DIR": analysis.detected_hub_id or plugin_name,
        "TOOL_NAME": f"get_{to_snake_case(plugin_name)}_data",
        "TOOL_DESCRIPTION": f"Get {plugin_title} data",
        "PARAM_DESCRIPTION": "Input parameter",
        "RETURN_DESCRIPTION": "Result dictionary",
        "RESOURCE": "data",
        "RESOURCE_DESCRIPTION": "Get data",
        "CHAIN_NAME": f"{plugin_name}-workflow",
        "CHAIN_DESCRIPTION": f"{plugin_title} workflow",
        "SCHEMA_NAME": f"{plugin_name}-item",
        "SCHEMA_DESCRIPTION": f"{plugin_title} item schema",
    }


def replace_placeholders(content: str, variables: dict) -> str:
    """Replace {PLACEHOLDER} variables in content."""
    for key, value in variables.items():
        content = content.replace(f"{{{key}}}", str(value))
    return content


def generate_missing_files(
    analysis: AnalysisResult,
    force: bool = False,
    dry_run: bool = False,
) -> Dict[str, List[str]]:
    """Generate missing files for a skill."""
    skill_path = Path(analysis.skill_path)
    variables = get_template_variables(analysis)

    result = {
        "created": [],
        "skipped": [],
        "errors": [],
    }

    # File mappings: (template_name, output_path)
    file_mappings = [
        # Root files
        ("version.yaml.template", "augur/version.yaml"),
        ("README.md.template", "README.md"),
        # Dashboard files (only if dashboard/ exists)
        ("loading.tsx.template", "dashboard/loading.tsx"),
        ("OverviewTab.tsx.template", "dashboard/tabs/OverviewTab.tsx"),
        # API files (only if api/ exists)
        ("health-route.ts.template", "api/health/route.ts"),
        # MCP files (only if mcp/ exists)
        ("mcp-init.py.template", "mcp/__init__.py"),
        ("mcp-tools.py.template", "mcp/tools.py"),
        # Backlog
        ("BACKLOG.md.template", "backlog/BACKLOG.md"),
        # Scripts
        ("utils.py.template", f"scripts/{to_snake_case(variables['PLUGIN_NAME'])}_utils.py"),
    ]

    for template_name, output_path in file_mappings:
        full_output_path = skill_path / output_path

        # Check if parent directory condition is met
        parent_dir = output_path.split("/")[0] if "/" in output_path else None
        if parent_dir in ["dashboard", "api", "mcp"]:
            if not (skill_path / parent_dir).exists():
                continue  # Skip if parent doesn't exist

        # Check if file already exists
        if full_output_path.exists() and not force:
            result["skipped"].append(output_path)
            continue

        try:
            template_content = read_template(template_name)
            content = replace_placeholders(template_content, variables)

            if dry_run:
                result["created"].append(f"{output_path} (dry-run)")
            else:
                full_output_path.parent.mkdir(parents=True, exist_ok=True)
                full_output_path.write_text(content)
                result["created"].append(output_path)

        except FileNotFoundError:
            result["errors"].append(f"Template not found: {template_name}")
        except Exception as e:
            result["errors"].append(f"Error creating {output_path}: {e}")

    # Create empty requirements.txt and package.json if missing
    simple_files = [
        ("requirements.txt", "# Python dependencies\n"),
        ("package.json", f'{{"name": "{variables["PLUGIN_NAME"]}", "version": "1.0.0", "private": true}}\n'),
    ]

    for filename, content in simple_files:
        file_path = skill_path / filename
        if not file_path.exists() or force:
            if dry_run:
                result["created"].append(f"{filename} (dry-run)")
            else:
                file_path.write_text(content)
                result["created"].append(filename)
        else:
            result["skipped"].append(filename)

    # Create backlog directories
    backlog_dirs = ["backlog/bugs", "backlog/features", "backlog/improvements"]
    for dir_path in backlog_dirs:
        full_dir = skill_path / dir_path
        if not full_dir.exists():
            if not dry_run:
                full_dir.mkdir(parents=True, exist_ok=True)
                (full_dir / ".gitkeep").touch()
            result["created"].append(f"{dir_path}/.gitkeep")

    return result


def format_analysis_report(analysis: AnalysisResult) -> str:
    """Format analysis results as a report."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"Migration Analysis: {analysis.skill_name}")
    lines.append("=" * 60)
    lines.append("")

    # Basic info
    lines.append(f"Bundle: {analysis.bundle}")
    lines.append(f"Path: {analysis.skill_path}")
    lines.append(f"Migration Score: {analysis.migration_score:.1f}%")
    lines.append("")

    # Status indicators
    lines.append("Status:")
    lines.append(f"  {'✅' if analysis.exists else '❌'} Skill directory exists")
    lines.append(f"  {'✅' if analysis.has_dashboard_yaml else '❌'} Has dashboard.yaml")
    lines.append(f"  {'✅' if analysis.has_skill_md else '❌'} Has SKILL.md")
    lines.append("")

    # Detected info
    if analysis.detected_hub_id:
        lines.append("Detected Configuration:")
        lines.append(f"  Hub ID: {analysis.detected_hub_id}")
        lines.append(f"  Title: {analysis.detected_title}")
        lines.append(f"  Category: {analysis.detected_category}")
        lines.append("")

    # Missing files
    if analysis.missing_required:
        lines.append(f"Missing Required Files ({len(analysis.missing_required)}):")
        for f in analysis.missing_required:
            lines.append(f"  ⛔ {f}")
        lines.append("")

    if analysis.missing_optional:
        lines.append(f"Missing Optional Directories ({len(analysis.missing_optional)}):")
        for f in analysis.missing_optional:
            lines.append(f"  ⚠️  {f}")
        lines.append("")

    # dashboard.yaml issues
    if analysis.dashboard_yaml_issues:
        lines.append(f"Dashboard.yaml Issues ({len(analysis.dashboard_yaml_issues)}):")
        for issue in analysis.dashboard_yaml_issues:
            lines.append(f"  ⛔ {issue}")
        lines.append("")

    # Code issues
    if analysis.uses_print:
        lines.append(f"_out() Statements Found ({len(analysis.uses_print)}):")
        for item in analysis.uses_print[:5]:
            lines.append(f"  📝 {item['file']}:{item['line']}")
            lines.append(f"     {item['content']}")
        if len(analysis.uses_print) > 5:
            lines.append(f"  ... and {len(analysis.uses_print) - 5} more")
        lines.append("")

    if analysis.uses_direct_logging:
        lines.append(f"Direct Logging Imports ({len(analysis.uses_direct_logging)}):")
        for item in analysis.uses_direct_logging[:5]:
            lines.append(f"  📝 {item['file']}:{item['line']}")
        if len(analysis.uses_direct_logging) > 5:
            lines.append(f"  ... and {len(analysis.uses_direct_logging) - 5} more")
        lines.append("")

    if analysis.hardcoded_paths:
        lines.append(f"Hardcoded Paths ({len(analysis.hardcoded_paths)}):")
        for item in analysis.hardcoded_paths[:5]:
            lines.append(f"  📝 {item['file']}:{item['line']}")
            lines.append(f"     {item['content']}")
        if len(analysis.hardcoded_paths) > 5:
            lines.append(f"  ... and {len(analysis.hardcoded_paths) - 5} more")
        lines.append("")

    # Summary
    total_issues = (
        len(analysis.missing_required)
        + len(analysis.dashboard_yaml_issues)
        + len(analysis.uses_print)
        + len(analysis.uses_direct_logging)
        + len(analysis.hardcoded_paths)
    )

    if total_issues == 0:
        lines.append("✅ No migration issues found!")
    else:
        lines.append(f"Total Issues: {total_issues}")
        lines.append("")
        lines.append("Run with --migrate to generate missing files")
        lines.append("Run transform.py to fix code issues")

    return "\n".join(lines)


def cli():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze and migrate skills to compliant Augur plugins",
    )
    parser.add_argument(
        "skill_name",
        help="Skill name to analyze/migrate",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze skill and show migration report",
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Generate missing files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files during migration",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without creating files",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    # Find the skill
    skill_info = find_skill(args.skill_name)
    if not skill_info:
        _out(f"❌ Skill not found: {args.skill_name}")
        _out("\nAvailable skills:")
        for bundle, name, path in discover_skills():
            _out(f"  - {name} ({bundle})")
        sys.exit(1)

    bundle, skill_name, skill_path = skill_info

    # Analyze
    analysis = analyze_skill(skill_path, skill_name, bundle)

    if args.analyze or (not args.migrate):
        if args.json:
            import json

            output = {
                "skill_name": analysis.skill_name,
                "skill_path": analysis.skill_path,
                "bundle": analysis.bundle,
                "migration_score": analysis.migration_score,
                "exists": analysis.exists,
                "has_dashboard_yaml": analysis.has_dashboard_yaml,
                "has_skill_md": analysis.has_skill_md,
                "missing_required": analysis.missing_required,
                "missing_optional": analysis.missing_optional,
                "dashboard_yaml_issues": analysis.dashboard_yaml_issues,
                "print_statements": len(analysis.uses_print),
                "direct_logging": len(analysis.uses_direct_logging),
                "hardcoded_paths": len(analysis.hardcoded_paths),
            }
            _out(json.dumps(output, indent=2))
        else:
            report = format_analysis_report(analysis)
            _out(report)

    if args.migrate:
        _out("\n" + "=" * 60)
        _out("Migration")
        _out("=" * 60 + "\n")

        result = generate_missing_files(
            analysis,
            force=args.force,
            dry_run=args.dry_run,
        )

        if result["created"]:
            _out(f"Created ({len(result['created'])}):")
            for f in result["created"]:
                _out(f"  ✅ {f}")

        if result["skipped"]:
            _out(f"\nSkipped (already exists) ({len(result['skipped'])}):")
            for f in result["skipped"]:
                _out(f"  ⏭️  {f}")

        if result["errors"]:
            _out(f"\nErrors ({len(result['errors'])}):")
            for e in result["errors"]:
                _out(f"  ❌ {e}")

        if not args.dry_run:
            _out("\n✅ Migration complete!")
            _out("\nNext steps:")
            _out("  1. Run transform.py to fix code issues (print, logging, paths)")
            _out("  2. Run audit.py to verify compliance")
            _out("  3. Update dashboard.yaml with missing fields")


if __name__ == "__main__":
    cli()
