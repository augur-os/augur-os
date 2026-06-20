"""
Plugin Scaffolding Script

Generate a new Augur plugin from templates.

Usage:
    python scaffold.py --name my-plugin --category business --description "My plugin description"
    python scaffold.py --name my-plugin --category business --features mcp,dashboard,api,chains
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional


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

# Template directory (relative to mcp-app-factory)
TEMPLATES_DIR = PLUGIN_ROOT / "templates"

# Category to icon mapping
CATEGORY_ICONS = {
    "system": "Settings",
    "productivity": "Zap",
    "personal": "User",
    "business": "Briefcase",
}

# Valid categories
VALID_CATEGORIES = ["system", "productivity", "personal", "business"]

# Features that can be enabled
VALID_FEATURES = ["mcp", "dashboard", "api", "chains", "schemas", "backlog", "tests", "context"]


def to_kebab_case(name: str) -> str:
    """Convert name to kebab-case."""
    # Replace spaces and underscores with hyphens
    name = re.sub(r"[\s_]+", "-", name)
    # Insert hyphen before uppercase letters and lowercase
    name = re.sub(r"([a-z])([A-Z])", r"\1-\2", name)
    return name.lower()


def to_title_case(name: str) -> str:
    """Convert kebab-case to Title Case."""
    return " ".join(word.capitalize() for word in name.split("-"))


def to_snake_case(name: str) -> str:
    """Convert kebab-case to snake_case."""
    return name.replace("-", "_")


def read_template(template_name: str) -> str:
    """Read a template file."""
    template_path = TEMPLATES_DIR / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    return template_path.read_text()


def replace_placeholders(content: str, variables: dict) -> str:
    """Replace {PLACEHOLDER} variables in content."""
    for key, value in variables.items():
        content = content.replace(f"{{{key}}}", str(value))
    return content


def get_default_variables(
    name: str,
    category: str,
    description: str,
    features: List[str],
) -> dict:
    """Get default template variables."""
    plugin_name = to_kebab_case(name)
    plugin_title = to_title_case(name)

    return {
        "PLUGIN_NAME": plugin_name,
        "PLUGIN_TITLE": plugin_title,
        "PLUGIN_DESCRIPTION": description,
        "HUB_ID": plugin_name,
        "CATEGORY": category,
        "BUNDLE": plugin_name,  # Standalone bundles use plugin name
        "SKILL": plugin_name,
        "LUCIDE_ICON": CATEGORY_ICONS.get(category, "Box"),
        "DATE": datetime.now().strftime("%Y-%m-%d"),
        "DATA_DIR": plugin_name,
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
        "ACTION_ID": f"run-{plugin_name}",
        "ACTION_DESCRIPTION": f"Run {plugin_title}",
        "TRIGGER_1": f"run {plugin_name}",
        "TRIGGER_2": f"start {plugin_name}",
        "DETAILED_DESCRIPTION": description,
        "PLUGIN_DEPS": "(none)",
        "MCP_DEPS": "(none)",
        "DATA_FLOW_DESCRIPTION": f"User interacts with {plugin_title} UI → API routes process requests → Data stored in data/{plugin_name}/",
        "TAB_ID": "settings",
        "TAB_LABEL": "Settings",
        "TAB_ICON": "Settings",
        "TAB_COMPONENT": "SettingsTab",
        "OTHER_TAB": "SettingsTab",
        "TOOL_NAME_2": f"process_{to_snake_case(plugin_name)}_result",
        "NNN": "001",
        "TITLE": "Example",
        "DESCRIPTION": "Example description",
        "STEP_1": "First step",
        "STEP_2": "Second step",
        "EXPECTED": "Expected behavior",
        "ACTUAL": "Actual behavior",
        "FILE_PATH": f"plugins/{plugin_name}/skills/{plugin_name}/example.py",
        "LINE": "10",
        "USER": "user",
        "ACTION": "perform action",
        "BENEFIT": "achieve goal",
        "CRITERION_1": "First criterion",
        "CRITERION_2": "Second criterion",
        "NOTES": "Technical implementation notes",
        "PLUGINS": "(none)",
        "EXTERNAL": "(none)",
        "CURRENT": "Current state description",
        "PROPOSED": "Proposed state description",
        "BENEFIT_1": "First benefit",
        "BENEFIT_2": "Second benefit",
        # Context provider variables
        "CONTEXT_KEYS": f"get_{to_snake_case(plugin_name)}_data",
        "CONTEXT_KEY_1": f"get_{to_snake_case(plugin_name)}_data",
        "CONTEXT_KEY_2": f"process_{to_snake_case(plugin_name)}_item",
        "MODULE": "core",
    }


def create_directory_structure(
    plugin_path: Path,
    features: List[str],
) -> List[str]:
    """Create the plugin directory structure."""
    created = []

    # Always create root directories
    plugin_path.mkdir(parents=True, exist_ok=True)
    created.append(str(plugin_path))

    # Feature-specific directories
    if "dashboard" in features:
        (plugin_path / "dashboard" / "tabs").mkdir(parents=True, exist_ok=True)
        created.append(str(plugin_path / "dashboard" / "tabs"))

    if "api" in features:
        (plugin_path / "api" / "health").mkdir(parents=True, exist_ok=True)
        (plugin_path / "api" / "data").mkdir(parents=True, exist_ok=True)
        created.append(str(plugin_path / "api"))

    if "mcp" in features:
        (plugin_path / "mcp").mkdir(parents=True, exist_ok=True)
        created.append(str(plugin_path / "mcp"))

    if "chains" in features:
        (plugin_path / "chains").mkdir(parents=True, exist_ok=True)
        created.append(str(plugin_path / "chains"))

    if "schemas" in features:
        (plugin_path / "schemas").mkdir(parents=True, exist_ok=True)
        created.append(str(plugin_path / "schemas"))

    if "backlog" in features:
        (plugin_path / "backlog" / "bugs").mkdir(parents=True, exist_ok=True)
        (plugin_path / "backlog" / "features").mkdir(parents=True, exist_ok=True)
        (plugin_path / "backlog" / "improvements").mkdir(parents=True, exist_ok=True)
        created.append(str(plugin_path / "backlog"))

    if "tests" in features:
        (plugin_path / "tests").mkdir(parents=True, exist_ok=True)
        created.append(str(plugin_path / "tests"))

    # Scripts directory (always)
    (plugin_path / "scripts").mkdir(parents=True, exist_ok=True)
    created.append(str(plugin_path / "scripts"))

    return created


def generate_files(
    plugin_path: Path,
    variables: dict,
    features: List[str],
) -> List[str]:
    """Generate files from templates."""
    generated = []

    # Always generate core files
    core_files = [
        ("SKILL.md.template", "SKILL.md"),
        ("README.md.template", "README.md"),
        ("dashboard.yaml.template", "dashboard.yaml"),
        ("version.yaml.template", "augur/version.yaml"),
    ]

    for template_name, output_name in core_files:
        try:
            content = read_template(template_name)
            content = replace_placeholders(content, variables)
            output_path = plugin_path / output_name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content)
            generated.append(str(output_path))
        except FileNotFoundError:
            logger.warning(f"Template not found: {template_name}")

    # Create empty requirements.txt and package.json
    (plugin_path / "requirements.txt").write_text("# Python dependencies\n")
    generated.append(str(plugin_path / "requirements.txt"))

    (plugin_path / "package.json").write_text(
        f'{{"name": "{variables["PLUGIN_NAME"]}", "version": "1.0.0", "private": true}}\n'
    )
    generated.append(str(plugin_path / "package.json"))

    # Feature-specific files
    if "dashboard" in features:
        dashboard_files = [
            ("page.tsx.template", "dashboard/page.tsx"),
            ("layout.tsx.template", "dashboard/layout.tsx"),
            ("loading.tsx.template", "dashboard/loading.tsx"),
            ("OverviewTab.tsx.template", "dashboard/tabs/OverviewTab.tsx"),
        ]
        for template_name, output_name in dashboard_files:
            try:
                content = read_template(template_name)
                content = replace_placeholders(content, variables)
                output_path = plugin_path / output_name
                output_path.write_text(content)
                generated.append(str(output_path))
            except FileNotFoundError:
                logger.warning(f"Template not found: {template_name}")

    if "api" in features:
        api_files = [
            ("health-route.ts.template", "api/health/route.ts"),
            ("data-route.ts.template", "api/data/route.ts"),
        ]
        for template_name, output_name in api_files:
            try:
                content = read_template(template_name)
                content = replace_placeholders(content, variables)
                output_path = plugin_path / output_name
                output_path.write_text(content)
                generated.append(str(output_path))
            except FileNotFoundError:
                logger.warning(f"Template not found: {template_name}")

    if "mcp" in features:
        mcp_files = [
            ("mcp-init.py.template", "mcp/__init__.py"),
            ("mcp-tools.py.template", "mcp/tools.py"),
        ]
        for template_name, output_name in mcp_files:
            try:
                content = read_template(template_name)
                content = replace_placeholders(content, variables)
                output_path = plugin_path / output_name
                output_path.write_text(content)
                generated.append(str(output_path))
            except FileNotFoundError:
                logger.warning(f"Template not found: {template_name}")

    if "chains" in features:
        try:
            content = read_template("chain.yaml.template")
            content = replace_placeholders(content, variables)
            output_path = plugin_path / "chains" / f"{variables['PLUGIN_NAME']}.yaml"
            output_path.write_text(content)
            generated.append(str(output_path))
        except FileNotFoundError:
            logger.warning("Template not found: chain.yaml.template")

    if "schemas" in features:
        try:
            content = read_template("schema.yaml.template")
            content = replace_placeholders(content, variables)
            output_path = plugin_path / "schemas" / f"{variables['PLUGIN_NAME']}.schema.yaml"
            output_path.write_text(content)
            generated.append(str(output_path))
        except FileNotFoundError:
            logger.warning("Template not found: schema.yaml.template")

    if "backlog" in features:
        try:
            content = read_template("BACKLOG.md.template")
            content = replace_placeholders(content, variables)
            (plugin_path / "backlog" / "BACKLOG.md").write_text(content)
            generated.append(str(plugin_path / "backlog" / "BACKLOG.md"))
        except FileNotFoundError:
            logger.warning("Template not found: BACKLOG.md.template")

        # Create .gitkeep files
        for subdir in ["bugs", "features", "improvements"]:
            (plugin_path / "backlog" / subdir / ".gitkeep").touch()

    if "tests" in features:
        test_files = [
            ("test_mcp.py.template", "tests/test_mcp.py"),
            ("test_api.py.template", "tests/test_api.py"),
        ]
        for template_name, output_name in test_files:
            try:
                content = read_template(template_name)
                content = replace_placeholders(content, variables)
                output_path = plugin_path / output_name
                output_path.write_text(content)
                generated.append(str(output_path))
            except FileNotFoundError:
                logger.warning(f"Template not found: {template_name}")

        if "dashboard" in features:
            try:
                content = read_template("component.test.tsx.template")
                content = replace_placeholders(content, variables)
                (plugin_path / "tests" / "OverviewTab.test.tsx").write_text(content)
                generated.append(str(plugin_path / "tests" / "OverviewTab.test.tsx"))
            except FileNotFoundError:
                logger.warning("Template not found: component.test.tsx.template")

    # Context provider (for plugins that provide context to others)
    if "context" in features:
        try:
            content = read_template("context.py.template")
            content = replace_placeholders(content, variables)
            (plugin_path / "context.py").write_text(content)
            generated.append(str(plugin_path / "context.py"))
        except FileNotFoundError:
            logger.warning("Template not found: context.py.template")

    # Scripts (always)
    try:
        content = read_template("utils.py.template")
        content = replace_placeholders(content, variables)
        (plugin_path / "scripts" / f"{to_snake_case(variables['PLUGIN_NAME'])}_utils.py").write_text(content)
        generated.append(str(plugin_path / "scripts" / f"{to_snake_case(variables['PLUGIN_NAME'])}_utils.py"))
    except FileNotFoundError:
        logger.warning("Template not found: utils.py.template")

    return generated


def generate_plugin(
    name: str,
    category: str,
    description: str,
    features: Optional[List[str]] = None,
    target_dir: Optional[Path] = None,
) -> dict:
    """
    Generate a new plugin from templates.

    Args:
        name: Plugin name (will be converted to kebab-case)
        category: Plugin category (system, productivity, personal, business)
        description: Short description of the plugin
        features: List of features to enable (default: all)
        target_dir: Target directory for plugin (default: plugins/{name}/skills/{name}/)

    Returns:
        Dictionary with generation results
    """
    logger.info("Generating plugin", extra={"plugin_name": name, "category": category})

    # Validate category
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Invalid category: {category}. Must be one of: {VALID_CATEGORIES}")

    # Default features
    if features is None:
        features = VALID_FEATURES.copy()

    # Validate features
    invalid_features = set(features) - set(VALID_FEATURES)
    if invalid_features:
        raise ValueError(f"Invalid features: {invalid_features}. Must be from: {VALID_FEATURES}")

    # Normalize name
    plugin_name = to_kebab_case(name)

    # Determine target path
    if target_dir is None:
        target_dir = PROJECT_ROOT / "plugins" / plugin_name / "skills" / plugin_name

    if target_dir.exists():
        raise FileExistsError(f"Plugin directory already exists: {target_dir}")

    # Get template variables
    variables = get_default_variables(name, category, description, features)

    # Create directory structure
    created_dirs = create_directory_structure(target_dir, features)

    # Generate files
    generated_files = generate_files(target_dir, variables, features)

    # Create data directory (colocated with plugin per ADR-083)
    data_dir = target_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / ".gitkeep").touch()

    result = {
        "success": True,
        "plugin_name": plugin_name,
        "plugin_path": str(target_dir),
        "data_path": str(data_dir),
        "directories_created": created_dirs,
        "files_generated": generated_files,
        "features": features,
        "next_steps": [
            f"1. Register '{plugin_name}' in mount-plugins.ts PLUGIN_BUNDLES",
            "2. Run 'npm run build' in apps/dashboard/ to mount the plugin",
            f"3. Navigate to /{plugin_name} in the dashboard",
            "4. Customize templates as needed",
        ],
    }

    logger.info("Plugin generated successfully", extra={"plugin": plugin_name, "files": len(generated_files)})
    return result


def cli():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate a new Augur plugin from templates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --name my-plugin --category business --description "My plugin"
  %(prog)s --name data-viz --category productivity --features mcp,dashboard,api
        """,
    )
    parser.add_argument(
        "--name",
        "-n",
        required=True,
        help="Plugin name (will be converted to kebab-case)",
    )
    parser.add_argument(
        "--category",
        "-c",
        required=True,
        choices=VALID_CATEGORIES,
        help="Plugin category",
    )
    parser.add_argument(
        "--description",
        "-d",
        required=True,
        help="Short description of the plugin",
    )
    parser.add_argument(
        "--features",
        "-f",
        default=None,
        help=f"Comma-separated list of features (default: all). Options: {','.join(VALID_FEATURES)}",
    )
    parser.add_argument(
        "--target-dir",
        "-t",
        default=None,
        help="Target directory for plugin (default: plugins/{name}/skills/{name}/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without creating files",
    )

    args = parser.parse_args()

    features = None
    if args.features:
        features = [f.strip() for f in args.features.split(",")]

    target_dir = None
    if args.target_dir:
        target_dir = Path(args.target_dir)

    if args.dry_run:
        _out(f"Would create plugin '{to_kebab_case(args.name)}'")
        _out(f"  Category: {args.category}")
        _out(f"  Description: {args.description}")
        _out(f"  Features: {features or VALID_FEATURES}")
        return

    try:
        result = generate_plugin(
            name=args.name,
            category=args.category,
            description=args.description,
            features=features,
            target_dir=target_dir,
        )

        _out(f"\n✅ Plugin '{result['plugin_name']}' created successfully!")
        _out(f"\n📁 Plugin path: {result['plugin_path']}")
        _out(f"📁 Data path: {result['data_path']}")
        _out(f"\n📄 Files generated: {len(result['files_generated'])}")
        for f in result['files_generated'][:10]:
            _out(f"   - {f}")
        if len(result['files_generated']) > 10:
            _out(f"   ... and {len(result['files_generated']) - 10} more")
        _out("\n📋 Next steps:")
        for step in result['next_steps']:
            _out(f"   {step}")

    except (ValueError, FileExistsError) as e:
        _out(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
