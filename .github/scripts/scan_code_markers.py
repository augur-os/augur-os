#!/usr/bin/env python3
"""
Scan codebase for in-code TODO_ markers.

Unified marker system for tracking work items directly in code.
CI runs this daily to surface all items needing attention.

Marker Types (all prefixed with TODO_):
  TODO_BUG(category/severity): description   - Code bugs
  TODO_OUTDATED: description                 - Outdated docs/comments/code
  TODO_WORKAROUND: description               - Temporary workarounds to remove
  TODO_IMPROVE(category): description        - Enhancement opportunities
  TODO_MISPLACED: description                - File/code in wrong location
  TODO_CLEANUP: description                  - Dead code, unused imports, tech debt
  TODO_SECURITY: description                 - Needs security audit
  TODO_REFACTOR: description                 - Code structure needs improvement
  TODO_IDEA: description                     - Future ideas for plugin backlog
  TODO_PERFORMANCE: description              - Performance optimization needed
  TODO_NEWSKILL: description                 - New skill detected by plugin watcher (ADR-122)
  TODO_SKILL_REMOVED: description            - Skill removed by plugin watcher (ADR-122)
  TODO_BROKEN_DEP: description               - Broken dependency from skill removal (ADR-122)

Usage:
  python3 .github/scripts/scan_code_markers.py              # Print all markers
  python3 .github/scripts/scan_code_markers.py --type bug   # Only TODO_BUG markers
  python3 .github/scripts/scan_code_markers.py --json       # JSON output
  python3 .github/scripts/scan_code_markers.py --ci         # CI mode (exit 1 if critical)
  python3 .github/scripts/scan_code_markers.py --summary    # Summary counts only
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class MarkerType(str, Enum):
    BUG = "bug"
    OUTDATED = "outdated"
    WORKAROUND = "workaround"
    IMPROVE = "improve"
    MISPLACED = "misplaced"
    CLEANUP = "cleanup"
    SECURITY = "security"
    REFACTOR = "refactor"
    IDEA = "idea"           # Future ideas for plugin backlog
    PERFORMANCE = "performance"  # Performance optimization needed
    NEWSKILL = "newskill"   # New skill detected by plugin watcher (ADR-122)
    SKILL_REMOVED = "skill_removed"  # Skill removed by plugin watcher (ADR-122)
    BROKEN_DEP = "broken_dep"  # Broken dependency from skill removal (ADR-122)


# Priority levels (for CI enforcement)
PRIORITY_CRITICAL = "critical"  # Blocks release
PRIORITY_HIGH = "high"          # Should fix soon
PRIORITY_MEDIUM = "medium"      # Fix when possible
PRIORITY_LOW = "low"            # Nice to have

# Valid categories for typed markers
BUG_CATEGORIES = {"security", "performance", "ux", "data", "integration"}
BUG_SEVERITIES = {"critical", "high", "medium", "low"}
IMPROVE_CATEGORIES = {"performance", "ux", "maintainability", "security", "testing"}


@dataclass
class CodeMarker:
    """Represents a marker found in code."""
    marker_type: str
    file: str
    line: int
    description: str
    category: Optional[str] = None
    severity: Optional[str] = None
    fix: Optional[str] = None

    @property
    def priority(self) -> str:
        """Determine priority based on marker type and severity."""
        if self.marker_type == MarkerType.BUG:
            return self.severity or PRIORITY_MEDIUM
        elif self.marker_type == MarkerType.SECURITY:
            return PRIORITY_HIGH
        elif self.marker_type == MarkerType.PERFORMANCE:
            return PRIORITY_MEDIUM
        elif self.marker_type == MarkerType.WORKAROUND:
            return PRIORITY_MEDIUM
        elif self.marker_type == MarkerType.MISPLACED:
            return PRIORITY_MEDIUM
        else:
            return PRIORITY_LOW


def get_project_root() -> Path:
    """Get project root directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        return Path(__file__).parent.parent.parent


PROJECT_ROOT = get_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.config.paths import get_runtime_dir
except ImportError:
    def get_runtime_dir() -> Path:
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "Augur" / "state"
        return Path.home() / ".local" / "state" / "augur"


def get_grep_base_cmd() -> list[str]:
    """Get base grep command (ripgrep preferred)."""
    try:
        subprocess.run(["rg", "--version"], capture_output=True, check=True)
        return [
            "rg", "-n", "--no-heading",
            "-g", "!node_modules",
            "-g", "!.venv",
            "-g", "!*.min.js",
            "-g", "!dist",
            "-g", "!*.md",       # Skip documentation
            "-g", "!*.yaml",     # Skip config examples
            "-g", "!*.lock",     # Skip lock files
            "-g", "!scan_code_markers.py",  # Skip self (has examples in docstring)
            "-t", "py",
            "-t", "ts",
            "-t", "js",
        ]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ["grep", "-rn", "--include=*.py", "--include=*.ts", "--include=*.tsx", "--include=*.js"]


def scan_bugs(project_root: Path) -> list[CodeMarker]:
    """Scan for TODO_BUG(category/severity): markers."""
    markers = []
    grep_cmd = get_grep_base_cmd()
    pattern = r"TODO_BUG\(([^/]+)/([^)]+)\):\s*(.+)"

    try:
        result = subprocess.run(
            grep_cmd + [pattern, str(project_root)],
            capture_output=True,
            text=True,
        )

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            parts = line.split(":", 2)
            if len(parts) < 3:
                continue

            file_path, line_num_str, content = parts[0], parts[1], parts[2]
            try:
                line_num = int(line_num_str)
            except ValueError:
                continue

            match = re.search(pattern, content)
            if match:
                category = match.group(1).strip().lower()
                severity = match.group(2).strip().lower()
                description = match.group(3).strip()

                # Validate to skip documentation examples
                if category not in BUG_CATEGORIES or severity not in BUG_SEVERITIES:
                    continue

                # Skip markers that appear in code (not comments)
                if not _is_in_comment(content, "TODO_BUG"):
                    continue

                rel_path = _relative_path(file_path, project_root)
                fix = _get_fix_comment(file_path, line_num)

                markers.append(CodeMarker(
                    marker_type=MarkerType.BUG,
                    file=rel_path,
                    line=line_num,
                    category=category,
                    severity=severity,
                    description=description,
                    fix=fix,
                ))

    except subprocess.CalledProcessError:
        pass

    return markers


def scan_simple_marker(project_root: Path, marker_name: str, marker_type: MarkerType) -> list[CodeMarker]:
    """Scan for simple markers like TODO_OUTDATED:, TODO_CLEANUP:, etc."""
    markers = []
    grep_cmd = get_grep_base_cmd()
    pattern = rf"{marker_name}:\s*(.+)"

    try:
        result = subprocess.run(
            grep_cmd + [pattern, str(project_root)],
            capture_output=True,
            text=True,
        )

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            parts = line.split(":", 2)
            if len(parts) < 3:
                continue

            file_path, line_num_str, content = parts[0], parts[1], parts[2]
            try:
                line_num = int(line_num_str)
            except ValueError:
                continue

            match = re.search(pattern, content)
            if match:
                # Skip markers that appear in code (not comments)
                if not _is_in_comment(content, marker_name):
                    continue

                description = match.group(1).strip()
                rel_path = _relative_path(file_path, project_root)

                markers.append(CodeMarker(
                    marker_type=marker_type,
                    file=rel_path,
                    line=line_num,
                    description=description,
                ))

    except subprocess.CalledProcessError:
        pass

    return markers


def scan_improve(project_root: Path) -> list[CodeMarker]:
    """Scan for TODO_IMPROVE(category): markers."""
    markers = []
    grep_cmd = get_grep_base_cmd()
    pattern = r"TODO_IMPROVE\(([^)]+)\):\s*(.+)"

    try:
        result = subprocess.run(
            grep_cmd + [pattern, str(project_root)],
            capture_output=True,
            text=True,
        )

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            parts = line.split(":", 2)
            if len(parts) < 3:
                continue

            file_path, line_num_str, content = parts[0], parts[1], parts[2]
            try:
                line_num = int(line_num_str)
            except ValueError:
                continue

            match = re.search(pattern, content)
            if match:
                category = match.group(1).strip().lower()
                description = match.group(2).strip()

                # Validate category
                if category not in IMPROVE_CATEGORIES:
                    continue

                # Skip markers that appear in code (not comments)
                if not _is_in_comment(content, "TODO_IMPROVE"):
                    continue

                rel_path = _relative_path(file_path, project_root)

                markers.append(CodeMarker(
                    marker_type=MarkerType.IMPROVE,
                    file=rel_path,
                    line=line_num,
                    category=category,
                    description=description,
                ))

    except subprocess.CalledProcessError:
        pass

    return markers


def _is_in_comment(line: str, marker: str) -> bool:
    """Check that a TODO_ marker appears inside a comment, not in code.

    This filters false positives from e.g. dictionary keys that reference
    marker names like ``{ TODO_SECURITY: ShieldAlert }``.

    Supported comment styles: ``#``, ``//``, ``/*``, ``{/*``.
    """
    idx = line.find(marker)
    if idx < 0:
        return False
    prefix = line[:idx].rstrip()
    # Python / shell / YAML line comments
    if "#" in prefix:
        return True
    # JS / TS line comments
    if "//" in prefix:
        return True
    # Block comments (/* ... */) including JSX {/* ... */}
    if "/*" in prefix:
        return True
    return False


def _relative_path(file_path: str, project_root: Path) -> str:
    """Convert to relative path."""
    try:
        return str(Path(file_path).relative_to(project_root))
    except ValueError:
        return file_path


def _get_fix_comment(file_path: str, line_num: int) -> Optional[str]:
    """Look for FIX: comment on the next line."""
    try:
        result = subprocess.run(
            ["sed", "-n", f"{line_num + 1}p", file_path],
            capture_output=True,
            text=True,
        )
        fix_match = re.search(r"#\s*FIX:\s*(.+)", result.stdout.strip())
        if fix_match:
            return fix_match.group(1).strip()
    except subprocess.CalledProcessError:
        pass
    return None


def scan_filesystem_todo_files(project_root: Path) -> list[CodeMarker]:
    """
    Scan for ADR-122 plugin lifecycle markers on the filesystem.

    New-skill detection uses .config status field (ADR-129):
    - plugins/{bundle}/skills/{skill}/.config with status: new

    Legacy TODO_NEWSKILL files are flagged as CLEANUP markers.

    Other filesystem markers:
    - state todo markers for removed skills and broken dependencies
    """
    markers: list[CodeMarker] = []

    try:
        import yaml as _yaml
    except ImportError:
        _yaml = None  # type: ignore[assignment]

    # Scan skill dirs for .config status: new (replaces TODO_NEWSKILL)
    plugins_dir = project_root / "plugins"
    if plugins_dir.exists():
        for bundle_dir in sorted(plugins_dir.iterdir()):
            if not bundle_dir.is_dir() or bundle_dir.name.startswith("."):
                continue
            skills_dir = bundle_dir / "skills"
            if not skills_dir.is_dir():
                continue
            for skill_dir in sorted(skills_dir.iterdir()):
                if not skill_dir.is_dir():
                    continue

                # Check .config for status: new
                config_path = skill_dir / ".config"
                if config_path.exists() and _yaml is not None:
                    try:
                        raw = _yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
                        if raw.get("status") == "new":
                            rel = _relative_path(str(config_path), project_root)
                            description = f"New skill needs setup: {bundle_dir.name}/{skill_dir.name}"
                            markers.append(CodeMarker(
                                marker_type=MarkerType.NEWSKILL,
                                file=rel,
                                line=1,
                                description=description,
                            ))
                    except Exception:
                        pass

                # Flag stale TODO_NEWSKILL files as CLEANUP
                todo_path = skill_dir / "augur" / "TODO_NEWSKILL"
                if todo_path.exists():
                    rel = _relative_path(str(todo_path), project_root)
                    description = f"Stale TODO_NEWSKILL file — status now tracked in .config: {bundle_dir.name}/{skill_dir.name}"
                    markers.append(CodeMarker(
                        marker_type=MarkerType.CLEANUP,
                        file=rel,
                        line=1,
                        description=description,
                    ))

    # Scan persistent state todo markers for plugin lifecycle cleanup.
    todos_dir = get_runtime_dir() / "todos"
    if todos_dir.exists():
        for todo_file in sorted(todos_dir.iterdir()):
            if not todo_file.is_file():
                continue
            name = todo_file.name
            rel = _relative_path(str(todo_file), project_root)
            if name.startswith("TODO_SKILL_REMOVED_"):
                suffix = name[len("TODO_SKILL_REMOVED_"):]
                description = f"Skill removed, cleanup needed: {suffix.replace('_', '/', 1)}"
                markers.append(CodeMarker(
                    marker_type=MarkerType.SKILL_REMOVED,
                    file=rel,
                    line=1,
                    description=description,
                ))
            elif name.startswith("TODO_BROKEN_DEP_"):
                suffix = name[len("TODO_BROKEN_DEP_"):]
                description = f"Broken required dependency: {suffix.replace('_', '/', 1)}"
                markers.append(CodeMarker(
                    marker_type=MarkerType.BROKEN_DEP,
                    file=rel,
                    line=1,
                    description=description,
                ))

    return markers


def scan_all_markers(project_root: Path, marker_filter: Optional[str] = None) -> list[CodeMarker]:
    """Scan for all marker types."""
    markers = []

    # Filesystem-based TODO files (ADR-122 plugin lifecycle) — scanned separately
    # from code-comment markers because they are standalone files, not source lines.
    filesystem_todo_types = {"newskill", "skill_removed", "broken_dep"}

    type_map = {
        "bug": (scan_bugs, [project_root]),
        "outdated": (scan_simple_marker, [project_root, "TODO_OUTDATED", MarkerType.OUTDATED]),
        "workaround": (scan_simple_marker, [project_root, "TODO_WORKAROUND", MarkerType.WORKAROUND]),
        "improve": (scan_improve, [project_root]),
        "misplaced": (scan_simple_marker, [project_root, "TODO_MISPLACED", MarkerType.MISPLACED]),
        "cleanup": (scan_simple_marker, [project_root, "TODO_CLEANUP", MarkerType.CLEANUP]),
        "security": (scan_simple_marker, [project_root, "TODO_SECURITY", MarkerType.SECURITY]),
        "refactor": (scan_simple_marker, [project_root, "TODO_REFACTOR", MarkerType.REFACTOR]),
        "idea": (scan_simple_marker, [project_root, "TODO_IDEA", MarkerType.IDEA]),
        "performance": (scan_simple_marker, [project_root, "TODO_PERFORMANCE", MarkerType.PERFORMANCE]),
    }

    if marker_filter:
        if marker_filter in filesystem_todo_types:
            # Scan filesystem files, then filter to requested type
            all_fs = scan_filesystem_todo_files(project_root)
            markers.extend(m for m in all_fs if m.marker_type == marker_filter)
        elif marker_filter in type_map:
            func, args = type_map[marker_filter]
            markers.extend(func(*args))
    else:
        for func, args in type_map.values():
            markers.extend(func(*args))
        # Always include filesystem TODO markers in full scan
        markers.extend(scan_filesystem_todo_files(project_root))

    return markers


def print_report(markers: list[CodeMarker]) -> None:
    """Print human-readable marker report."""
    if not markers:
        print("No TODO_ markers found in codebase")
        return

    # Group by marker type
    by_type: dict[str, list[CodeMarker]] = {}
    for m in markers:
        by_type.setdefault(m.marker_type, []).append(m)

    print(f"Found {len(markers)} TODO_ marker(s)\n")

    type_icons = {
        MarkerType.BUG: "BUG",
        MarkerType.OUTDATED: "OUTDATED",
        MarkerType.WORKAROUND: "WORKAROUND",
        MarkerType.IMPROVE: "IMPROVE",
        MarkerType.MISPLACED: "MISPLACED",
        MarkerType.CLEANUP: "CLEANUP",
        MarkerType.SECURITY: "SECURITY",
        MarkerType.REFACTOR: "REFACTOR",
        MarkerType.IDEA: "IDEA",
        MarkerType.PERFORMANCE: "PERFORMANCE",
        MarkerType.NEWSKILL: "NEWSKILL",
        MarkerType.SKILL_REMOVED: "SKILL_REMOVED",
        MarkerType.BROKEN_DEP: "BROKEN_DEP",
    }

    for marker_type, type_markers in by_type.items():
        label = type_icons.get(marker_type, marker_type.upper())
        print(f"TODO_{label} ({len(type_markers)})")
        print("-" * 50)

        for m in type_markers:
            print(f"  {m.file}:{m.line}")
            if m.category and m.severity:
                print(f"     [{m.category}/{m.severity}] {m.description}")
            elif m.category:
                print(f"     [{m.category}] {m.description}")
            else:
                print(f"     {m.description}")
            if m.fix:
                print(f"     FIX: {m.fix}")
        print()


def print_summary(markers: list[CodeMarker]) -> None:
    """Print summary counts only."""
    if not markers:
        print("No TODO_ markers found")
        return

    # Count by type
    by_type: dict[str, int] = {}
    for m in markers:
        by_type[m.marker_type] = by_type.get(m.marker_type, 0) + 1

    # Count by priority
    by_priority: dict[str, int] = {}
    for m in markers:
        by_priority[m.priority] = by_priority.get(m.priority, 0) + 1

    print(f"TODO_ Markers Summary: {len(markers)} total\n")

    print("By Type:")
    for t, count in sorted(by_type.items()):
        print(f"  TODO_{t.upper()}: {count}")

    print("\nBy Priority:")
    for p in [PRIORITY_CRITICAL, PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW]:
        if p in by_priority:
            print(f"  {p}: {by_priority[p]}")


def main():
    parser = argparse.ArgumentParser(description="Scan codebase for TODO_ markers")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--ci", action="store_true", help="CI mode: exit 1 if critical/high items")
    parser.add_argument("--summary", action="store_true", help="Print summary counts only")
    parser.add_argument("--type", type=str, choices=[
        "bug", "outdated", "workaround", "improve",
        "misplaced", "cleanup", "security", "refactor", "idea", "performance",
        "newskill", "skill_removed", "broken_dep"
    ], help="Filter to specific marker type")
    parser.add_argument("--path", type=str, help="Path to scan (default: project root)")
    args = parser.parse_args()

    project_root = Path(args.path) if args.path else get_project_root()
    markers = scan_all_markers(project_root, args.type)

    if args.json:
        output = [
            {
                "marker": f"TODO_{m.marker_type.upper()}",
                "file": m.file,
                "line": m.line,
                "text": m.description,
                "category": m.category,
                "severity": m.severity,
                "priority": m.priority,
            }
            for m in markers
        ]
        print(json.dumps(output, indent=2))
    elif args.summary:
        print_summary(markers)
    else:
        print_report(markers)

    # CI mode: fail if critical or high priority items
    if args.ci:
        critical_count = sum(1 for m in markers if m.priority == PRIORITY_CRITICAL)
        high_count = sum(1 for m in markers if m.priority == PRIORITY_HIGH)

        if critical_count > 0:
            print(f"\nCI FAILURE: {critical_count} critical item(s) found", file=sys.stderr)
            sys.exit(1)

        if high_count > 0:
            print(f"\nCI WARNING: {high_count} high-priority item(s) found", file=sys.stderr)
            # Don't fail on high, just warn

    return 0


if __name__ == "__main__":
    sys.exit(main())
