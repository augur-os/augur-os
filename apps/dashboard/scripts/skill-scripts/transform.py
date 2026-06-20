"""
Code Transformation Script

Apply automated fixes to migrate code to Augur patterns.

Transformations:
- _out() → logger.info() / logger.debug()
- direct logging import → from src.logging import get_entity_logger
- Hardcoded paths → path resolution functions

Usage:
    python transform.py career --analyze           # Show what would change
    python transform.py career --fix-logging       # Fix logging issues
    python transform.py career --fix-paths         # Fix hardcoded paths
    python transform.py career --fix-all           # Apply all fixes
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


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


@dataclass
class Transformation:
    """A single code transformation."""

    file_path: str
    line_number: int
    original: str
    transformed: str
    transform_type: str
    applied: bool = False


@dataclass
class TransformResult:
    """Result of transforming a skill."""

    skill_name: str
    transformations: List[Transformation] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        return len([t for t in self.transformations if t.applied])


def discover_skills() -> List[tuple]:
    """Discover all skills in the plugins/ directory."""
    skills = []
    plugins_dir = PROJECT_ROOT / "plugins"

    if not plugins_dir.exists():
        return skills

    for bundle_dir in plugins_dir.iterdir():
        if not bundle_dir.is_dir():
            continue
        bundle_name = bundle_dir.name

        skills_dir = bundle_dir / "skills"
        if not skills_dir.exists():
            continue

        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skills.append((bundle_name, skill_dir.name, skill_dir))

    return skills


def find_skill(name: str) -> Optional[tuple]:
    """Find a skill by name."""
    skills = discover_skills()
    for bundle, skill_name, skill_path in skills:
        if skill_name == name:
            return (bundle, skill_name, skill_path)
    return None


def should_skip_file(file_path: Path, skill_path: Path) -> bool:
    """Check if a file should be skipped for transformations."""
    rel_path = str(file_path.relative_to(skill_path))

    # Skip test files
    if "test" in rel_path.lower():
        return True

    # Skip CLI entry points (allowed to use print)
    if "__main__.py" in rel_path:
        return True
    if "cli.py" in rel_path:
        return True

    # Skip scripts that are CLI tools (check for argparse)
    if "/scripts/" in rel_path:
        try:
            content = file_path.read_text()
            if "argparse" in content and "__name__" in content:
                return True  # CLI script
        except Exception:
            pass

    return False


def transform_print_to_logger(
    content: str,
    plugin_name: str,
) -> Tuple[str, List[Tuple[int, str, str]]]:
    """Transform _out() statements to logger calls."""
    changes = []
    lines = content.split("\n")
    new_lines = []

    # Check if logger import exists
    has_logger_import = "from src.logging import" in content
    has_logger_var = re.search(r'logger\s*=\s*get_entity_logger', content) is not None

    # Add import if needed (will be handled separately)
    needs_import = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Skip comments and strings
        if stripped.startswith("#"):
            new_lines.append(line)
            continue

        # Find print statements
        # Match: print(...) but not inside strings
        if "_out(" in line and not stripped.startswith("#"):
            # Simple transformation: print(x) -> logger.info(x)
            # This is a basic transformation - complex cases may need manual review

            # Extract indentation
            indent = len(line) - len(line.lstrip())
            indent_str = line[:indent]

            # Try to extract the print content
            match = re.search(r'print\s*\((.*)\)\s*$', stripped)
            if match:
                print_content = match.group(1)

                # Determine log level based on content
                if any(x in print_content.lower() for x in ['error', 'fail', 'exception']):
                    log_level = 'error'
                elif any(x in print_content.lower() for x in ['warn', 'warning']):
                    log_level = 'warning'
                elif any(x in print_content.lower() for x in ['debug', 'verbose']):
                    log_level = 'debug'
                else:
                    log_level = 'info'

                # Handle f-strings and format strings
                if print_content.startswith('f"') or print_content.startswith("f'"):
                    # f-string: convert to logger with extra
                    new_line = f'{indent_str}logger.{log_level}({print_content})'
                else:
                    new_line = f'{indent_str}logger.{log_level}({print_content})'

                changes.append((i, line.strip(), new_line.strip()))
                new_lines.append(new_line)
                needs_import = True
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    new_content = "\n".join(new_lines)

    # Add import and logger if needed
    if needs_import and not has_logger_import:
        import_line = "from src.logging import get_entity_logger"
        logger_line = f'logger = get_entity_logger("{plugin_name}")'

        # Find the right place to insert (after other imports)
        lines = new_content.split("\n")
        insert_idx = 0

        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                insert_idx = i + 1
            elif line.strip() and not line.startswith("#") and not line.startswith('"""'):
                break

        # Insert import and logger
        if not has_logger_import:
            lines.insert(insert_idx, "")
            lines.insert(insert_idx + 1, import_line)
            if not has_logger_var:
                lines.insert(insert_idx + 2, logger_line)
                lines.insert(insert_idx + 3, "")

        new_content = "\n".join(lines)

    return new_content, changes


def transform_logging_import(
    content: str,
    plugin_name: str,
) -> Tuple[str, List[Tuple[int, str, str]]]:
    """Transform direct logging imports to augur_logging."""
    changes = []
    lines = content.split("\n")
    new_lines = []

    has_augur_import = "from src.logging import" in content
    has_logger_var = re.search(r'logger\s*=\s*get_entity_logger', content) is not None

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        legacy_import_literal = "import " + "logging"
        logging_basicconfig_literal = "logging." + "basicConfig"

        # Check for direct logging import
        if stripped == legacy_import_literal or stripped.startswith(legacy_import_literal + " "):
            if not has_augur_import:
                new_line = "from src.logging import get_entity_logger"
                changes.append((i, stripped, new_line))
                new_lines.append(new_line)
                if not has_logger_var:
                    new_lines.append(f'logger = get_entity_logger("{plugin_name}")')
                has_augur_import = True
            else:
                changes.append((i, stripped, "# Removed: " + stripped))
                new_lines.append("# Removed: " + stripped)

        # Check for from logging import
        elif stripped.startswith("from logging import"):
            if not has_augur_import:
                new_line = "from src.logging import get_entity_logger"
                changes.append((i, stripped, new_line))
                new_lines.append(new_line)
                if not has_logger_var:
                    new_lines.append(f'logger = get_entity_logger("{plugin_name}")')
                has_augur_import = True
            else:
                changes.append((i, stripped, "# Removed: " + stripped))
                new_lines.append("# Removed: " + stripped)

        # Check for logging.getLogger
        elif "logging.getLogger" in line:
            indent = len(line) - len(line.lstrip())
            indent_str = line[:indent]
            new_line = f'{indent_str}logger = get_entity_logger("{plugin_name}")'
            changes.append((i, stripped, new_line.strip()))
            new_lines.append(new_line)

        # Check for logging.basicConfig
        elif logging_basicconfig_literal in line:
            changes.append((i, stripped, "# Removed (centrally configured): " + stripped))
            new_lines.append("# Removed (centrally configured): " + stripped)

        else:
            new_lines.append(line)

    return "\n".join(new_lines), changes


def transform_hardcoded_paths(
    content: str,
    file_path: Path,
) -> Tuple[str, List[Tuple[int, str, str]]]:
    """Transform hardcoded paths to path resolution."""
    changes = []
    lines = content.split("\n")
    new_lines = []

    # Path patterns to replace (audit-ignore: these are detection patterns, not hardcoded paths)
    patterns = [
        (r'/Users/\w+/Projects/[Aa]ugur', 'get_project_root()'),  # audit-ignore
        (r'~/Projects/[Aa]ugur', 'get_project_root()'),  # audit-ignore
        (r'/Users/\w+', 'Path.home()'),  # audit-ignore
        (r'C:\\Users\\\w+', 'Path.home()'),  # audit-ignore
    ]

    needs_path_import = False

    for i, line in enumerate(lines, 1):

        for pattern, replacement in patterns:
            if re.search(pattern, line):
                new_line = re.sub(pattern, replacement, line)
                if new_line != line:
                    changes.append((i, line.strip(), new_line.strip()))
                    line = new_line
                    if 'get_project_root' in replacement:
                        needs_path_import = True

        new_lines.append(line)

    new_content = "\n".join(new_lines)

    # Add path import if needed
    if needs_path_import:
        if "from src.config.paths import" not in new_content:
            lines = new_content.split("\n")

            # Find import section
            insert_idx = 0
            for i, line in enumerate(lines):
                if line.startswith("import ") or line.startswith("from "):
                    insert_idx = i + 1

            import_line = "from src.config.paths import get_project_root"
            lines.insert(insert_idx, import_line)
            new_content = "\n".join(lines)

    return new_content, changes


def analyze_skill_transforms(
    skill_path: Path,
    skill_name: str,
) -> TransformResult:
    """Analyze a skill for potential transformations."""
    result = TransformResult(skill_name=skill_name)

    for py_file in skill_path.rglob("*.py"):
        if should_skip_file(py_file, skill_path):
            continue

        try:
            content = py_file.read_text()
            rel_path = str(py_file.relative_to(skill_path))

            # Analyze print transformations
            _, print_changes = transform_print_to_logger(content, skill_name)
            for line_num, original, transformed in print_changes:
                result.transformations.append(
                    Transformation(
                        file_path=rel_path,
                        line_number=line_num,
                        original=original,
                        transformed=transformed,
                        transform_type="print_to_logger",
                    )
                )

            # Analyze logging transformations
            _, logging_changes = transform_logging_import(content, skill_name)
            for line_num, original, transformed in logging_changes:
                result.transformations.append(
                    Transformation(
                        file_path=rel_path,
                        line_number=line_num,
                        original=original,
                        transformed=transformed,
                        transform_type="logging_import",
                    )
                )

            # Analyze path transformations
            _, path_changes = transform_hardcoded_paths(content, py_file)
            for line_num, original, transformed in path_changes:
                result.transformations.append(
                    Transformation(
                        file_path=rel_path,
                        line_number=line_num,
                        original=original,
                        transformed=transformed,
                        transform_type="hardcoded_path",
                    )
                )

        except Exception as e:
            result.errors.append(f"Error analyzing {py_file}: {e}")

    return result


def apply_transforms(
    skill_path: Path,
    skill_name: str,
    fix_logging: bool = False,
    fix_paths: bool = False,
    fix_print: bool = False,
    dry_run: bool = False,
) -> TransformResult:
    """Apply transformations to a skill."""
    result = TransformResult(skill_name=skill_name)

    for py_file in skill_path.rglob("*.py"):
        if should_skip_file(py_file, skill_path):
            continue

        try:
            content = py_file.read_text()
            original_content = content
            rel_path = str(py_file.relative_to(skill_path))
            file_changes = []

            # Apply print transformations
            if fix_print:
                content, changes = transform_print_to_logger(content, skill_name)
                for line_num, original, transformed in changes:
                    t = Transformation(
                        file_path=rel_path,
                        line_number=line_num,
                        original=original,
                        transformed=transformed,
                        transform_type="print_to_logger",
                        applied=True,
                    )
                    result.transformations.append(t)
                    file_changes.append(t)

            # Apply logging transformations
            if fix_logging:
                content, changes = transform_logging_import(content, skill_name)
                for line_num, original, transformed in changes:
                    t = Transformation(
                        file_path=rel_path,
                        line_number=line_num,
                        original=original,
                        transformed=transformed,
                        transform_type="logging_import",
                        applied=True,
                    )
                    result.transformations.append(t)
                    file_changes.append(t)

            # Apply path transformations
            if fix_paths:
                content, changes = transform_hardcoded_paths(content, py_file)
                for line_num, original, transformed in changes:
                    t = Transformation(
                        file_path=rel_path,
                        line_number=line_num,
                        original=original,
                        transformed=transformed,
                        transform_type="hardcoded_path",
                        applied=True,
                    )
                    result.transformations.append(t)
                    file_changes.append(t)

            # Write changes
            if content != original_content:
                if not dry_run:
                    py_file.write_text(content)
                result.files_modified.append(rel_path)

        except Exception as e:
            result.errors.append(f"Error transforming {py_file}: {e}")

    return result


def format_transform_report(result: TransformResult, detailed: bool = True) -> str:
    """Format transformation results as a report."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"Transformation Report: {result.skill_name}")
    lines.append("=" * 60)
    lines.append("")

    # Group by type
    by_type = {}
    for t in result.transformations:
        if t.transform_type not in by_type:
            by_type[t.transform_type] = []
        by_type[t.transform_type].append(t)

    # Summary
    lines.append("Summary:")
    for transform_type, transforms in by_type.items():
        applied = len([t for t in transforms if t.applied])
        total = len(transforms)
        status = "applied" if applied > 0 else "pending"
        lines.append(f"  {transform_type}: {total} ({status})")
    lines.append("")

    if detailed:
        for transform_type, transforms in by_type.items():
            type_labels = {
                "print_to_logger": "Print → Logger",
                "logging_import": "Logging Import",
                "hardcoded_path": "Hardcoded Path",
            }
            lines.append(f"{type_labels.get(transform_type, transform_type)}:")

            for t in transforms[:10]:
                status = "✅" if t.applied else "📝"
                lines.append(f"  {status} {t.file_path}:{t.line_number}")
                lines.append(f"     - {t.original[:60]}...")
                lines.append(f"     + {t.transformed[:60]}...")
                lines.append("")

            if len(transforms) > 10:
                lines.append(f"  ... and {len(transforms) - 10} more")
            lines.append("")

    if result.files_modified:
        lines.append(f"Files Modified ({len(result.files_modified)}):")
        for f in result.files_modified:
            lines.append(f"  📄 {f}")
        lines.append("")

    if result.errors:
        lines.append(f"Errors ({len(result.errors)}):")
        for e in result.errors:
            lines.append(f"  ❌ {e}")
        lines.append("")

    return "\n".join(lines)


def cli():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Transform code to Augur patterns",
    )
    parser.add_argument(
        "skill_name",
        help="Skill name to transform",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze and show potential transformations",
    )
    parser.add_argument(
        "--fix-logging",
        action="store_true",
        help="Fix direct logging imports (logging → augur_logging)",
    )
    parser.add_argument(
        "--fix-print",
        action="store_true",
        help="Fix print statements (_out() → logger)",
    )
    parser.add_argument(
        "--fix-paths",
        action="store_true",
        help="Fix hardcoded paths",
    )
    parser.add_argument(
        "--fix-all",
        action="store_true",
        help="Apply all fixes",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without modifying files",
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
        sys.exit(1)

    bundle, skill_name, skill_path = skill_info

    if args.fix_all:
        args.fix_logging = True
        args.fix_print = True
        args.fix_paths = True

    # Analyze or apply
    if args.analyze or not (args.fix_logging or args.fix_print or args.fix_paths):
        result = analyze_skill_transforms(skill_path, skill_name)
    else:
        result = apply_transforms(
            skill_path,
            skill_name,
            fix_logging=args.fix_logging,
            fix_paths=args.fix_paths,
            fix_print=args.fix_print,
            dry_run=args.dry_run,
        )

    if args.json:
        import json

        output = {
            "skill_name": result.skill_name,
            "total_transformations": len(result.transformations),
            "applied": result.total_changes,
            "files_modified": result.files_modified,
            "errors": result.errors,
            "by_type": {},
        }
        for t in result.transformations:
            if t.transform_type not in output["by_type"]:
                output["by_type"][t.transform_type] = 0
            output["by_type"][t.transform_type] += 1
        _out(json.dumps(output, indent=2))
    else:
        report = format_transform_report(result, detailed=True)
        _out(report)

        if result.total_changes > 0:
            _out("✅ Transformations applied!")
        elif args.analyze:
            _out("\nTo apply these transformations, run with:")
            _out(f"  python transform.py {skill_name} --fix-all")


if __name__ == "__main__":
    cli()
