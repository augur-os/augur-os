#!/usr/bin/env python3
"""
Skill Import Tool

Import external skills into the Augur plugin structure.

Supports importing from:
- Local directory with SKILL.md
- Claude commands folder (~/.claude/commands/)
- Git repository URL

Usage:
    # Import a local skill into the crew bundle
    python skill_import.py ./my-skill --bundle crew

    # Import a Claude command
    python skill_import.py ~/.claude/commands/my-command --bundle crew

    # Preview import without making changes
    python skill_import.py ./my-skill --bundle crew --dry-run

    # Import to user global skills (~/skills/)
    python skill_import.py ./my-skill --user-global
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.logging import get_entity_logger
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        logging = importlib.import_module("logging")
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger


logger = get_entity_logger("skill-import")

PLUGINS_DIR = PROJECT_ROOT / "plugins"
USER_SKILLS_DIR = Path.home() / ".claude" / "skills"

IGNORED_FILES = {".DS_Store", ".git", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules"}


@dataclass
class SkillSource:
    """Represents a skill source to import."""

    path: Path
    name: str
    has_skill_md: bool
    has_scripts: bool
    has_modules: bool
    has_references: bool
    description: str
    version: str

    @classmethod
    def from_path(cls, source_path: Path) -> Optional["SkillSource"]:
        """Analyze a source path and extract skill metadata."""
        if not source_path.exists():
            return None

        # Handle single file (SKILL.md)
        if source_path.is_file() and source_path.name == "SKILL.md":
            source_path = source_path.parent

        if not source_path.is_dir():
            return None

        skill_md = source_path / "SKILL.md"
        if not skill_md.exists():
            # Check for Claude command format
            command_md = source_path / "command.md"
            if command_md.exists():
                # Claude command format
                name = slugify(source_path.name)
                return cls(
                    path=source_path,
                    name=name,
                    has_skill_md=False,
                    has_scripts=False,
                    has_modules=False,
                    has_references=False,
                    description=f"Imported from Claude command: {source_path.name}",
                    version="1.0.0",
                )
            return None

        # Parse SKILL.md frontmatter
        content = skill_md.read_text(encoding="utf-8")
        frontmatter = extract_frontmatter(content)

        name = frontmatter.get("name", source_path.name)
        name = slugify(name)

        return cls(
            path=source_path,
            name=name,
            has_skill_md=True,
            has_scripts=(source_path / "scripts").exists(),
            has_modules=(source_path / "modules").exists(),
            has_references=(source_path / "references").exists(),
            description=frontmatter.get("description", ""),
            version=frontmatter.get("version", "1.0.0"),
        )


def slugify(value: str) -> str:
    """Convert to kebab-case slug."""
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "imported-skill"


def extract_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from markdown."""
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except Exception:
        return {}


def discover_bundles() -> list[str]:
    """Discover available plugin bundles."""
    bundles = []
    if not PLUGINS_DIR.exists():
        return bundles

    for entry in PLUGINS_DIR.iterdir():
        if entry.name.startswith(".") or not entry.is_dir():
            continue
        skills_dir = entry / "skills"
        if skills_dir.exists() and skills_dir.is_dir():
            bundles.append(entry.name)

    return sorted(bundles)


def copy_skill_files(source: SkillSource, target_dir: Path) -> None:
    """Copy skill files to target directory."""
    target_dir.mkdir(parents=True, exist_ok=True)

    for item in source.path.iterdir():
        if item.name in IGNORED_FILES:
            continue

        target = target_dir / item.name
        if item.is_dir():
            if item.name not in IGNORED_FILES:
                shutil.copytree(item, target, ignore=shutil.ignore_patterns(*IGNORED_FILES))
        else:
            shutil.copy2(item, target)


def convert_claude_command(source: SkillSource, target_dir: Path) -> None:
    """Convert a Claude command to a skill."""
    target_dir.mkdir(parents=True, exist_ok=True)

    # Create SKILL.md from command.md
    command_md = source.path / "command.md"
    if command_md.exists():
        content = command_md.read_text(encoding="utf-8")

        # Generate SKILL.md
        skill_md_content = f"""---
name: {source.name}
version: 1.0.0
description: Imported from Claude command
category: imported
mode: ide
status: active
triggers:
  - {source.name}
dependencies:
  plugins: []
  mcp_servers: []
  python: []
  npm: []
---

# {source.name.replace('-', ' ').title()}

Imported from Claude command: `{source.path.name}`

## Original Command

{content}
"""
        (target_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")

    # Copy other files
    for item in source.path.iterdir():
        if item.name in IGNORED_FILES or item.name == "command.md":
            continue

        target = target_dir / item.name
        if item.is_dir():
            shutil.copytree(item, target, ignore=shutil.ignore_patterns(*IGNORED_FILES))
        else:
            shutil.copy2(item, target)


def generate_dashboard_yaml(skill_name: str, target_dir: Path) -> None:
    """Generate a basic dashboard.yaml for the skill."""
    dashboard_yaml = target_dir / "dashboard.yaml"
    if dashboard_yaml.exists():
        return  # Don't overwrite existing

    content = f"""# Dashboard configuration for {skill_name}
# See docs/guides/dashboard-yaml.md for full options

# Hub where this skill appears
hub: control

# Tabs contributed by this skill
tabs: []

# Action buttons
actions: []
"""
    dashboard_yaml.write_text(content, encoding="utf-8")


def generate_tests_template(skill_name: str, target_dir: Path) -> None:
    """Generate a tests template for the skill."""
    tests_dir = target_dir / "tests"
    tests_dir.mkdir(exist_ok=True)

    test_file = tests_dir / f"test_{skill_name.replace('-', '_')}.py"
    if test_file.exists():
        return  # Don't overwrite existing

    content = f'''"""Tests for {skill_name} skill."""

import pytest
from pathlib import Path


SKILL_DIR = Path(__file__).parent.parent


def test_skill_md_exists():
    """Verify SKILL.md exists and has frontmatter."""
    skill_md = SKILL_DIR / "SKILL.md"
    assert skill_md.exists(), "SKILL.md is required"

    content = skill_md.read_text()
    assert content.startswith("---"), "SKILL.md must have YAML frontmatter"


def test_skill_has_description():
    """Verify skill has a description in frontmatter."""
    import yaml

    skill_md = SKILL_DIR / "SKILL.md"
    content = skill_md.read_text()

    # Extract frontmatter
    parts = content.split("---", 2)
    assert len(parts) >= 3, "Invalid frontmatter format"

    frontmatter = yaml.safe_load(parts[1])
    assert frontmatter.get("description"), "description is required in frontmatter"
'''
    test_file.write_text(content, encoding="utf-8")


def import_skill(
    source_path: Path,
    bundle: Optional[str] = None,
    user_global: bool = False,
    dry_run: bool = False,
) -> bool:
    """
    Import a skill from source path.

    Args:
        source_path: Path to skill directory or SKILL.md
        bundle: Target plugin bundle (e.g., "dev", "ai", "lifestyle", "career")
        user_global: If True, import to ~/skills/ instead
        dry_run: If True, only show what would be done

    Returns:
        True if successful
    """
    # Analyze source
    source = SkillSource.from_path(source_path)
    if not source:
        logger.error(f"Invalid skill source: {source_path}")
        logger.error("Source must be a directory containing SKILL.md or command.md")
        return False

    logger.info(f"Importing skill: {source.name}")
    logger.info(f"  Source: {source.path}")
    logger.info(f"  Description: {source.description}")
    logger.info(f"  Has SKILL.md: {source.has_skill_md}")
    logger.info(f"  Has scripts: {source.has_scripts}")
    logger.info(f"  Has modules: {source.has_modules}")

    # Determine target directory
    if user_global:
        target_dir = USER_SKILLS_DIR / source.name
        logger.info(f"  Target: {target_dir} (user global)")
    elif bundle:
        bundle_dir = PLUGINS_DIR / bundle
        if not bundle_dir.exists():
            logger.error(f"Bundle not found: {bundle}")
            logger.error(f"Available bundles: {', '.join(discover_bundles())}")
            return False
        target_dir = bundle_dir / "skills" / source.name
        logger.info(f"  Target: {target_dir}")
    else:
        logger.error("Must specify --bundle or --user-global")
        return False

    # Check if skill already exists
    if target_dir.exists():
        logger.error(f"Skill already exists at: {target_dir}")
        logger.error("Use --force to overwrite (not implemented yet)")
        return False

    if dry_run:
        logger.info("\n[DRY RUN] Would perform the following:")
        logger.info(f"  - Create directory: {target_dir}")
        if source.has_skill_md:
            logger.info("  - Copy skill files")
        else:
            logger.info("  - Convert Claude command to skill")
        logger.info("  - Generate dashboard.yaml template")
        logger.info("  - Generate tests template")
        return True

    # Perform import
    try:
        if source.has_skill_md:
            copy_skill_files(source, target_dir)
        else:
            convert_claude_command(source, target_dir)

        # Generate optional files
        generate_dashboard_yaml(source.name, target_dir)
        generate_tests_template(source.name, target_dir)

        logger.info(f"\n✅ Skill imported successfully to: {target_dir}")
        logger.info("\nNext steps:")
        logger.info(f"  1. Review the imported skill: cat {target_dir}/SKILL.md")
        logger.info("  2. Update dashboard.yaml if you want UI integration")
        logger.info(f"  3. Run tests: pytest {target_dir}/tests/")

        return True

    except Exception as e:
        logger.error(f"Import failed: {e}")
        # Cleanup on failure
        if target_dir.exists():
            shutil.rmtree(target_dir)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Import external skills into Augur plugin structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import a local skill into the crew bundle
  %(prog)s ./my-skill --bundle crew

  # Import a Claude command
  %(prog)s ~/.claude/commands/my-command --bundle crew

  # Preview import without making changes
  %(prog)s ./my-skill --bundle crew --dry-run

  # Import to user global skills
  %(prog)s ./my-skill --user-global
""",
    )

    parser.add_argument("source", type=Path, nargs="?", help="Path to skill directory or SKILL.md")
    parser.add_argument("--bundle", "-b", help="Target plugin bundle (e.g., crew, factory)")
    parser.add_argument("--user-global", "-u", action="store_true", help="Import to ~/skills/")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--list-bundles", action="store_true", help="List available bundles and exit")

    args = parser.parse_args()

    if args.list_bundles:
        bundles = discover_bundles()
        _out(f"Available bundles ({len(bundles)}):")
        for b in bundles:
            _out(f"  - {b}")
        return

    # Validate required arguments for import
    if not args.source:
        parser.error("source is required for import")

    if not args.bundle and not args.user_global:
        parser.error("must specify --bundle or --user-global")

    success = import_skill(
        source_path=args.source,
        bundle=args.bundle,
        user_global=args.user_global,
        dry_run=args.dry_run,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
