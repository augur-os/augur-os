#!/usr/bin/env python3
"""Export an Augur skill to Claude Code format (ADR-126).

Strips the Augur platform layer (`augur/` directory and legacy leftovers) and produces
a standard Claude skill that can be:
  - Uploaded to Claude.ai via Settings > Capabilities > Skills
  - Placed in a project's skills/ directory for Claude Code
  - Added to Messages API via container.skills parameter

Usage:
    # Export a single skill
    python3 src/scripts/export-skill.py project-brain/capabilities/skills/platform-admin/

    # Export to a specific output directory
    python3 src/scripts/export-skill.py project-brain/capabilities/skills/platform-admin/ --output /tmp/exports/

    # Preview what would be exported
    python3 src/scripts/export-skill.py project-brain/capabilities/skills/platform-admin/ --dry-run

    # Export as zip
    python3 src/scripts/export-skill.py project-brain/capabilities/skills/platform-admin/ --zip
"""

import argparse
import ast
import shutil
import sys
import zipfile
from pathlib import Path

_SCRIPT_ROOT = Path(__file__).resolve().parents[2]
if str(_SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_ROOT))

from src.config.paths import get_runtime_dir

# Portable directories that get copied unchanged
PORTABLE_DIRS = ["scripts", "references", "assets"]

# Portable files that get copied unchanged
PORTABLE_FILES = ["SKILL.md"]

# Augur-specific paths that get stripped
AUGUR_PATHS = ["augur"]

# Legacy Augur paths (pre-migration, still stripped)
LEGACY_AUGUR_PATHS = ["dashboard.yaml", "dashboard", "api", "mcp", "lib", "data", "chains"]


def find_project_root() -> Path:
    """Find Augur project root."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "config" / "system").is_dir():
            return parent
    return Path.cwd()


def extract_mcp_tool_docs(skill_path: Path) -> str | None:
    """Extract MCP tool docstrings from scripts/mcp/__init__.py.

    Parses the Python AST to find functions decorated with @mcp.tool()
    and extracts their docstrings and signatures.

    Returns markdown content for references/mcp-tools.md, or None if no tools found.
    """
    mcp_init = skill_path / "scripts" / "mcp" / "__init__.py"
    if not mcp_init.exists():
        # Try legacy path
        mcp_init = skill_path / "mcp" / "__init__.py"
        if not mcp_init.exists():
            return None

    try:
        source = mcp_init.read_text()
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return None

    tools = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # Check for @mcp.tool() or similar decorators
        is_tool = False
        for dec in node.decorator_list:
            dec_str = ast.dump(dec)
            if "tool" in dec_str.lower():
                is_tool = True
                break

        if not is_tool:
            continue

        # Extract function name, docstring, and parameters
        name = node.name.replace("_", "-")
        docstring = ast.get_docstring(node) or "No description available."

        # Extract parameters (skip 'self' and 'ctx')
        params = []
        for arg in node.args.args:
            arg_name = arg.arg
            if arg_name in ("self", "ctx", "context"):
                continue
            annotation = ""
            if arg.annotation:
                try:
                    annotation = f": {ast.unparse(arg.annotation)}"
                except Exception:
                    pass
            params.append(f"  - `{arg_name}{annotation}`")

        tool_doc = f"### `{name}`\n\n{docstring}\n"
        if params:
            tool_doc += "\n**Parameters:**\n" + "\n".join(params) + "\n"
        tools.append(tool_doc)

    if not tools:
        return None

    header = "# MCP Tools Reference\n\n"
    header += "These MCP tools are provided by this skill when running with the Augur MCP server.\n"
    header += "To use these tools in Claude Code, connect the Augur MCP server.\n\n"

    return header + "\n---\n\n".join(tools)


def export_skill(
    skill_path: Path,
    output_dir: Path,
    dry_run: bool = False,
    verbose: bool = False,
) -> Path:
    """Export a skill directory to Claude Code format.

    Args:
        skill_path: Path to the skill source directory
        output_dir: Where to write the exported skill
        dry_run: If True, only print what would happen
        verbose: If True, print detailed progress

    Returns:
        Path to the exported skill directory
    """
    skill_path = skill_path.resolve()
    skill_name = skill_path.name

    # Validate
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        print(f"ERROR: No SKILL.md found in {skill_path}", file=sys.stderr)
        sys.exit(1)

    export_dir = output_dir / skill_name
    if dry_run:
        print(f"[DRY RUN] Would export {skill_name} to {export_dir}\n")
    else:
        export_dir.mkdir(parents=True, exist_ok=True)

    # Copy SKILL.md
    if dry_run:
        print("  COPY: SKILL.md")
    else:
        shutil.copy2(skill_md, export_dir / "SKILL.md")
        if verbose:
            print("  Copied SKILL.md")

    # Copy portable directories
    for dir_name in PORTABLE_DIRS:
        src = skill_path / dir_name
        if src.is_dir():
            if dry_run:
                file_count = sum(1 for _ in src.rglob("*") if _.is_file())
                print(f"  COPY: {dir_name}/ ({file_count} files)")
            else:
                dst = export_dir / dir_name
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                if verbose:
                    print(f"  Copied {dir_name}/")

    # Generate MCP tools reference
    mcp_docs = extract_mcp_tool_docs(skill_path)
    if mcp_docs:
        refs_dir = export_dir / "references"
        if dry_run:
            print("  GENERATE: references/mcp-tools.md (from MCP tool docstrings)")
        else:
            refs_dir.mkdir(parents=True, exist_ok=True)
            (refs_dir / "mcp-tools.md").write_text(mcp_docs)
            if verbose:
                print("  Generated references/mcp-tools.md")

    # Report what was stripped
    stripped = []
    for name in AUGUR_PATHS + LEGACY_AUGUR_PATHS:
        p = skill_path / name
        if p.exists():
            stripped.append(name)

    if stripped:
        if dry_run:
            print(f"\n  STRIPPED (not copied): {', '.join(stripped)}")
        elif verbose:
            print(f"  Stripped: {', '.join(stripped)}")

    return export_dir


def create_zip(export_dir: Path) -> Path:
    """Create a zip archive of the exported skill."""
    zip_path = export_dir.parent / f"{export_dir.name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in export_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(export_dir.parent)
                zf.write(file_path, arcname)
    return zip_path


def validate_export(export_dir: Path) -> list[str]:
    """Validate the exported skill meets Claude's requirements."""
    errors = []

    # Must have SKILL.md
    skill_md = export_dir / "SKILL.md"
    if not skill_md.exists():
        errors.append("Missing SKILL.md")
        return errors

    # Check SKILL.md has valid frontmatter
    content = skill_md.read_text()
    if not content.startswith("---"):
        errors.append("SKILL.md missing YAML frontmatter")
    else:
        # Parse frontmatter
        try:
            import yaml

            parts = content.split("---", 2)
            if len(parts) >= 3:
                fm = yaml.safe_load(parts[1])
                if not fm:
                    errors.append("SKILL.md has empty frontmatter")
                elif "name" not in fm:
                    errors.append("SKILL.md frontmatter missing 'name' field")
                elif "description" not in fm:
                    errors.append("SKILL.md frontmatter missing 'description' field")

                # Check for non-standard fields
                standard_fields = {"name", "description", "license", "compatibility", "metadata"}
                non_standard = set(fm.keys()) - standard_fields if fm else set()
                if non_standard:
                    errors.append(f"SKILL.md frontmatter has non-standard fields: {non_standard}")

                # Check description length
                desc = fm.get("description", "") if fm else ""
                if len(str(desc)) > 1024:
                    errors.append(f"SKILL.md description exceeds 1024 chars ({len(str(desc))} chars)")

                # Check name doesn't contain 'claude' or 'anthropic'
                name = fm.get("name", "") if fm else ""
                if "claude" in name.lower() or "anthropic" in name.lower():
                    errors.append(f"SKILL.md name '{name}' contains restricted word")
        except Exception as e:
            errors.append(f"Failed to parse SKILL.md frontmatter: {e}")

    # Should not contain Augur-specific files
    for name in AUGUR_PATHS + LEGACY_AUGUR_PATHS:
        if (export_dir / name).exists():
            errors.append(f"Export contains Augur-specific path: {name}")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Export Augur skill to Claude Code format (ADR-126)")
    parser.add_argument("skill_path", help="Path to skill directory")
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output directory (default: external state exports/)",
    )
    parser.add_argument(
        "--target",
        choices=["claude-code"],
        default="claude-code",
        help="Export target format",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--zip", action="store_true", help="Create zip archive")
    parser.add_argument("--validate", action="store_true", help="Validate export after creation")
    args = parser.parse_args()

    skill_path = Path(args.skill_path).resolve()
    if not skill_path.is_dir():
        print(f"ERROR: Not a directory: {skill_path}", file=sys.stderr)
        return 1

    output_dir = Path(args.output) if args.output else get_runtime_dir() / "exports"

    export_dir = export_skill(skill_path, output_dir, dry_run=args.dry_run, verbose=args.verbose)

    if args.dry_run:
        print("\n[DRY RUN] No files written.")
        return 0

    print(f"\nExported: {export_dir}")

    if args.zip:
        zip_path = create_zip(export_dir)
        print(f"Zipped: {zip_path}")

    if args.validate:
        errors = validate_export(export_dir)
        if errors:
            print("\nValidation FAILED:")
            for err in errors:
                print(f"  - {err}")
            return 1
        else:
            print("\nValidation PASSED")

    return 0


if __name__ == "__main__":
    sys.exit(main())
