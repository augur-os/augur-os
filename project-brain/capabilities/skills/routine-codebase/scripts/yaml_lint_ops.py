"""auto-yaml-lint: Lint YAML config files for syntax errors and formatting issues.

Scan locations:
  config/, project-brain/capabilities/skills/*/augur/, apps/dashboard/

Difficulty levels:
  d0: Surface — validate YAML syntax (yaml.safe_load)
  d1: Content — check trailing whitespace, missing newline at EOF, duplicate keys
  d2: Deep — detect empty YAML files, deeply nested structures (>6 levels)
"""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import logging
from pathlib import Path

from src.config.paths import get_project_root
from src.lib.ops_protocol import (
    DifficultySpec,
    FixResult,
    OpsContext,
    ScanResult,
    evolution_gap,
    make_issue,
)

name = "auto-yaml-lint"

DIFFICULTY_SPEC: DifficultySpec = {
    0: "Surface — validate YAML syntax via safe_load",
    1: "Content — trailing whitespace, missing EOF newline, duplicate keys",
    2: "Deep — empty files, deep nesting (>6 levels)",
}

logger = logging.getLogger(__name__)

# Directories to scan (relative to project root)
SCAN_DIRS = ["config"]
# Glob patterns for skill-level YAML
SKILL_YAML_GLOBS = [
    "project-brain/capabilities/skills/*/augur/**/*.yaml",
    "project-brain/capabilities/skills/*/augur/**/*.yml",
]


def _collect_yaml_files(project_root: Path) -> list[Path]:
    """Collect all YAML files to lint."""
    files: list[Path] = []

    # config/ directory
    for scan_dir_name in SCAN_DIRS:
        scan_dir = project_root / scan_dir_name
        if scan_dir.is_dir():
            for ext in ("*.yaml", "*.yml"):
                files.extend(scan_dir.rglob(ext))

    # project-brain/capabilities/skills/*/augur/ YAML
    for pattern in SKILL_YAML_GLOBS:
        files.extend(project_root.glob(pattern))

    # Deduplicate and filter
    seen: set[Path] = set()
    result: list[Path] = []
    for f in files:
        resolved = f.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if f.is_file() and not any(
            part.startswith(".") or part == "node_modules"
            for part in f.parts
        ):
            result.append(f)
    return sorted(result)


def _extract_frontmatter(content: str) -> str | None:
    """Extract YAML frontmatter from a file that uses --- delimiters.

    Returns the frontmatter YAML string if the file uses frontmatter format,
    or None if the file is plain YAML (no frontmatter delimiters).
    Per ADR-404, user-facing data files use markdown with YAML frontmatter.
    """
    stripped = content.lstrip()
    if not stripped.startswith("---"):
        return None
    # Find the closing --- delimiter (must be on its own line after the opening ---)
    lines = stripped.split("\n")
    if len(lines) < 2:
        return None
    # First line is '---', find the next '---' line
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            # Return just the frontmatter content between the delimiters
            return "\n".join(lines[1:i]) + "\n"
    return None


def _check_yaml_syntax(path: Path) -> str | None:
    """Try to parse YAML. Returns error string or None on success.

    Handles both plain YAML files and frontmatter-delimited files (ADR-404).
    For frontmatter files, only the YAML portion between --- delimiters is validated.
    """
    import yaml

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as e:
        return f"Cannot read file: {e}"

    # Check if this is a frontmatter file and extract just the YAML portion
    frontmatter = _extract_frontmatter(content)
    parse_content = frontmatter if frontmatter is not None else content

    try:
        yaml.safe_load(parse_content)
    except yaml.YAMLError as e:
        return str(e)
    return None


def _check_duplicate_keys(path: Path) -> list[str]:
    """Check for duplicate keys in a YAML file."""
    import yaml

    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return []

    # Handle frontmatter files — only check the YAML portion
    frontmatter = _extract_frontmatter(content)
    parse_content = frontmatter if frontmatter is not None else content

    # Use a custom loader that tracks duplicates
    duplicates: list[str] = []

    class DuplicateKeyLoader(yaml.SafeLoader):
        pass

    def _check_duplicates(loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
        mapping: dict = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in mapping:
                duplicates.append(f"Duplicate key '{key}' at line {key_node.start_mark.line + 1}")
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping

    DuplicateKeyLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        _check_duplicates,
    )

    try:
        yaml.load(parse_content, Loader=DuplicateKeyLoader)  # nosec B506  # custom Loader subclass, not the unsafe bare yaml.load risk
    except yaml.YAMLError:
        pass  # Syntax errors already caught by _check_yaml_syntax

    return duplicates


def _max_nesting_depth(path: Path) -> int:
    """Calculate maximum nesting depth of a YAML file."""
    import yaml

    try:
        content = path.read_text(encoding="utf-8")
        # Handle frontmatter files — only check the YAML portion
        frontmatter = _extract_frontmatter(content)
        parse_content = frontmatter if frontmatter is not None else content
        data = yaml.safe_load(parse_content)
    except Exception:
        return 0

    def _depth(obj: object, current: int = 0) -> int:
        if isinstance(obj, dict):
            if not obj:
                return current
            return max(_depth(v, current + 1) for v in obj.values())
        if isinstance(obj, list):
            if not obj:
                return current
            return max(_depth(v, current + 1) for v in obj)
        return current

    return _depth(data)


def scan(ctx: OpsContext) -> ScanResult:
    """Scan YAML files for syntax errors and formatting issues."""
    project_root = get_project_root()
    yaml_files = _collect_yaml_files(project_root)
    issues: list[dict] = []
    items_scanned = len(yaml_files)

    for path in yaml_files:
        rel = str(path.relative_to(project_root))

        # --- d0: Syntax check ---
        error = _check_yaml_syntax(path)
        if error:
            issues.append(make_issue(
                category="yaml-lint",
                detail=f"YAML syntax error: {error[:200]}",
                path=rel,
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="manual",
            ))
            continue  # Skip further checks for unparseable files

        # --- d1: Formatting checks ---
        if ctx.difficulty >= 1:
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue

            # Trailing whitespace
            for lineno, line in enumerate(content.splitlines(), 1):
                if line != line.rstrip():
                    issues.append(make_issue(
                        category="yaml-lint",
                        detail=f"Trailing whitespace at line {lineno}",
                        path=rel,
                        kind="actionable",
                        root_cause_type="repo_bug",
                        fixability="auto",
                        line=lineno,
                        fix_type="trailing-whitespace",
                    ))
                    break  # One issue per file for trailing whitespace

            # Missing newline at EOF
            if content and not content.endswith("\n"):
                issues.append(make_issue(
                    category="yaml-lint",
                    detail="Missing newline at end of file",
                    path=rel,
                    kind="actionable",
                    root_cause_type="repo_bug",
                    fixability="auto",
                    fix_type="missing-eof-newline",
                ))

            # Duplicate keys
            dupes = _check_duplicate_keys(path)
            for dupe_msg in dupes:
                issues.append(make_issue(
                    category="yaml-lint",
                    detail=dupe_msg,
                    path=rel,
                    kind="actionable",
                    root_cause_type="repo_bug",
                    fixability="manual",
                ))

        # --- d2: Deep checks ---
        if ctx.difficulty >= 2:
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue

            # Empty YAML files
            if not content.strip() or content.strip() in ("---", "---\n"):
                issues.append(make_issue(
                    category="yaml-lint",
                    detail="Empty YAML file — remove or populate",
                    path=rel,
                    kind="actionable",
                    root_cause_type="manual_debt",
                    fixability="auto",
                    fix_type="remove-empty",
                ))

            # Deep nesting
            depth = _max_nesting_depth(path)
            if depth > 6:
                issues.append(make_issue(
                    category="yaml-lint",
                    detail=f"Deeply nested YAML ({depth} levels) — consider flattening",
                    path=rel,
                    kind="maintenance",
                    root_cause_type="manual_debt",
                    fixability="manual",
                    nesting_depth=depth,
                ))

    # Evolution gap at max difficulty with no issues
    if ctx.difficulty >= 2 and not issues:
        issues.append(evolution_gap(
            "All YAML files pass syntax and formatting checks. "
            "Consider adding: schema validation against known config schemas, "
            "check for unused config keys, validate cross-references between YAML files. "
            "Next: implement JSON Schema validation for config/*.yaml.",
            category="yaml-lint",
        ))

    severity = "error" if any(
        "syntax error" in i.get("detail", "") for i in issues
    ) else "warning" if issues else "info"
    # "broken" means the scanner itself is broken; finding issues means the scanner works
    health = "degraded" if issues else "verified"

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} YAML issue(s) in {items_scanned} file(s)" if issues else f"All {items_scanned} YAML files clean",
        severity=severity,
        health=health,
        items_scanned=items_scanned,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix YAML formatting issues.

    d0: Report only.
    d1+: Auto-fix trailing whitespace and missing EOF newlines.
    d2+: Remove empty YAML files.
    """
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} YAML issues found")

    if not issues:
        return FixResult(success=True, summary="No YAML issues to fix")

    if ctx.difficulty < 1:
        return FixResult(
            success=True,
            summary=f"{len(issues)} YAML issues found (report only at d0)",
            fix_type="report",
        )

    project_root = get_project_root()
    actions: list[dict] = []
    changes: list[str] = []

    # Group auto-fixable issues by file
    fixable_files: dict[str, set[str]] = {}  # path -> set of fix types
    for issue in issues:
        if issue.get("fixability") != "auto":
            continue
        fix_type = issue.get("fix_type", "")
        path = issue.get("path", "")
        if path and fix_type:
            fixable_files.setdefault(path, set()).add(fix_type)

    for rel_path, fix_types in fixable_files.items():
        full_path = project_root / rel_path
        if not full_path.is_file():
            continue

        # d2+: Remove empty YAML files
        if "remove-empty" in fix_types and ctx.difficulty >= 2:
            try:
                full_path.unlink()
                actions.append({
                    "action": "remove_empty",
                    "file": rel_path,
                })
                changes.append(f"Removed empty YAML file {rel_path}")
                continue  # File is gone, skip formatting fixes
            except OSError as e:
                logger.warning("Failed to remove empty file %s: %s", rel_path, e)

        # d1+: Fix formatting
        try:
            content = full_path.read_text(encoding="utf-8")
            original = content

            if "trailing-whitespace" in fix_types:
                content = "\n".join(line.rstrip() for line in content.split("\n"))

            if "missing-eof-newline" in fix_types:
                if content and not content.endswith("\n"):
                    content += "\n"

            if content != original:
                full_path.write_text(content, encoding="utf-8")
                applied = sorted(ft for ft in fix_types if ft != "remove-empty")
                actions.append({
                    "action": "yaml_format",
                    "file": rel_path,
                    "fixes": applied,
                })
                changes.append(f"Fixed {', '.join(applied)} in {rel_path}")
        except OSError as e:
            logger.warning("Failed to fix %s: %s", rel_path, e)

    manual_count = sum(1 for i in issues if i.get("fixability") != "auto")
    summary_parts = []
    if actions:
        summary_parts.append(f"Fixed {len(actions)} file(s)")
    if manual_count > 0:
        summary_parts.append(f"{manual_count} issue(s) require manual review")
    summary = "; ".join(summary_parts) if summary_parts else "No auto-fixable YAML issues"

    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=summary,
        fix_type="code-fix" if actions else "report",
    )
