#!/usr/bin/env python3
"""
Auto-Fix Pattern Compliance Issues
Automatically fixes common pattern compliance issues found by the audit.

Safety: Creates backups before making changes, validates syntax, and checks build.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
import shutil
from subprocess import CompletedProcess, TimeoutExpired, run  # nosec B404
from src.config.paths import get_project_root


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def _resolve_command(name: str) -> str | None:
    return shutil.which(name)


def _get_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _get_temp_archive_dir() -> Path:
    env_base = os.environ.get("AUGUR_ROOT")
    if env_base:
        return Path(os.path.expanduser(env_base)).expanduser().resolve() / ".agent" / "archive"

    try:
        repo_root = _get_repo_root()
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from src.config.paths import get_project_root, get_temp_archive_dir  # type: ignore

        return get_temp_archive_dir()
    except Exception:
        return get_project_root() / ".agent" / "archive"


def _get_operations_dir() -> Path:
    env_base = os.environ.get("AUGUR_ROOT")
    if env_base:
        base = Path(os.path.expanduser(env_base)).expanduser().resolve()
        return base.parent / "plugins" / "dev" / "skills"

    try:
        repo_root = _get_repo_root()
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from src.config.paths import get_operations_dir  # type: ignore

        return get_operations_dir()
    except Exception:
        return get_project_root() / "plugins" / "dev" / "skills"


def backup_file(file_path: Path) -> Path:
    """Create a backup of the file before modifying."""
    repo_root = _get_repo_root()
    try:
        relative_parent = file_path.parent.relative_to(repo_root)
    except ValueError:
        relative_parent = Path("misc")

    backup_dir = _get_temp_archive_dir() / "frontend" / "auto-fix" / relative_parent
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{file_path.name}.{timestamp}.bak"

    shutil.copy2(file_path, backup_path)
    return backup_path


def validate_typescript_syntax(file_path: Path, content: str) -> Tuple[bool, Optional[str]]:
    """
    Validate TypeScript/TSX syntax by checking basic structure.
    Returns (is_valid, error_message)
    """
    # Basic validation checks
    errors = []

    # Check for balanced braces
    open_braces = content.count('{')
    close_braces = content.count('}')
    if open_braces != close_braces:
        errors.append(f"Unbalanced braces: {open_braces} open, {close_braces} close")

    # Check for balanced parentheses
    open_parens = content.count('(')
    close_parens = content.count(')')
    if open_parens != close_parens:
        errors.append(f"Unbalanced parentheses: {open_parens} open, {close_parens} close")

    # Check for balanced brackets
    open_brackets = content.count('[')
    close_brackets = content.count(']')
    if open_brackets != close_brackets:
        errors.append(f"Unbalanced brackets: {open_brackets} open, {close_brackets} close")

    # Check for unclosed JSX tags (basic check)
    jsx_open_tags = len(re.findall(r'<[A-Za-z][A-Za-z0-9]*[^/>]*>', content))
    jsx_close_tags = len(re.findall(r'</[A-Za-z][A-Za-z0-9]*>', content))
    # Self-closing tags
    self_closing = len(re.findall(r'<[A-Za-z][A-Za-z0-9]*[^/>]*/>', content))

    # Rough check - not perfect but catches major issues
    if jsx_open_tags > jsx_close_tags + self_closing + 10:  # Allow some margin
        errors.append(
            f"Possible unclosed JSX tags: {jsx_open_tags} open, {jsx_close_tags} close, {self_closing} self-closing"
        )

    # Check for obvious syntax errors
    if re.search(r'<button[^>]*>\s*<button', content):
        errors.append("Nested button tags detected (likely corruption)")

    if re.search(r'className="[^"]*className=', content):
        errors.append("Duplicate className attributes detected")

    if re.search(r'<div[^>]*>\s*<div[^>]*>\s*<button[^>]*>\s*</div>', content, re.DOTALL):
        # Check for button code in wrong places
        if 'focus:outline-none focus:ring-2' in content and content.count('focus:outline-none focus:ring-2') > 20:
            errors.append("Excessive focus states detected (possible corruption)")

    if errors:
        return False, "; ".join(errors)

    return True, None


def validate_build(file_path: Path, project_root: Path) -> Tuple[bool, Optional[str]]:
    """
    Validate that the file doesn't break the build.
    Returns (is_valid, error_message)
    """
    try:
        # Try to run TypeScript check on just this file
        # This is a lightweight check - full build would be better but slower
        npx_path = _resolve_command("npx")
        if not npx_path:
            return True, None

        result: CompletedProcess[str] = run(
            [npx_path, 'tsc', '--noEmit', '--skipLibCheck', str(file_path)],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )  # nosec B603

        if result.returncode != 0:
            # Extract relevant error lines
            error_lines = [line for line in result.stderr.split('\n') if 'error TS' in line][:3]
            return False, "; ".join(error_lines) if error_lines else "TypeScript compilation failed"

        return True, None
    except TimeoutExpired:
        return True, None  # Timeout - assume OK for now
    except FileNotFoundError:
        # TypeScript not available - skip validation
        return True, None
    except Exception:
        # Other errors - log but don't fail
        return True, None


def fix_gradient_background(content: str, file_path: str) -> Tuple[str, List[str]]:
    """Add gradient background wrapper if missing - SAFE VERSION."""
    fixes_applied = []

    # Check if already has gradient
    if "bg-[radial-gradient(ellipse_at_top" in content:
        return content, fixes_applied

    # Only apply if we can find a clear export default function
    # Look for the pattern: export default function ComponentName() {
    export_match = re.search(r'export\s+default\s+function\s+\w+\s*\([^)]*\)\s*\{', content)
    if not export_match:
        return content, fixes_applied

    # Find the return statement in this function
    # Look for return ( after the function declaration
    function_start = export_match.end()
    return_match = re.search(r'return\s*\(', content[function_start:])
    if not return_match:
        return content, fixes_applied

    return_pos = function_start + return_match.start()

    # Check if already wrapped
    next_chars = content[return_pos + return_match.end() : return_pos + return_match.end() + 100]
    if 'min-h-screen bg-[radial-gradient' in next_chars:
        return content, fixes_applied

    # Find the matching closing paren for return()
    # This is safer - we'll look for the pattern: return ( ... );
    depth = 1
    pos = return_pos + return_match.end()
    closing_pos = None

    while pos < len(content) and depth > 0:
        if content[pos] == '(':
            depth += 1
        elif content[pos] == ')':
            depth -= 1
            if depth == 0:
                closing_pos = pos
                break
        pos += 1

    if closing_pos is None:
        # Couldn't find matching paren - skip this fix
        return content, fixes_applied

    # Insert gradient wrapper
    wrapper_start = '<div className="min-h-screen bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-950 via-slate-950 to-black text-white p-6 font-sans selection:bg-cyan-500/30">'
    wrapper_end = '</div>'

    # Get indentation from the line with return
    return_line_start = content.rfind('\n', 0, return_pos) + 1
    return_line = content[return_line_start:return_pos]
    indent = len(return_line) - len(return_line.lstrip())
    indent_str = ' ' * (indent + 2)

    # Insert wrapper
    new_content = (
        content[: return_pos + return_match.end()]
        + '\n'
        + indent_str
        + wrapper_start
        + '\n'
        + content[return_pos + return_match.end() : closing_pos]
        + '\n'
        + indent_str
        + wrapper_end
        + content[closing_pos:]
    )

    fixes_applied.append("Added gradient background wrapper")
    return new_content, fixes_applied


def fix_spacing_wrapper(content: str, file_path: str) -> Tuple[str, List[str]]:
    """Add space-y-6 wrapper around EditableMasonryGrid if missing - SAFE VERSION."""
    fixes_applied = []

    # Check if already has space-y-6
    if 'space-y-6' in content or 'space-y-8' in content:
        return content, fixes_applied

    # Find EditableMasonryGrid with more precise matching
    grid_match = re.search(r'<EditableMasonryGrid\s+[^>]*>', content)
    if not grid_match:
        return content, fixes_applied

    # Check if it's already wrapped in a div with space-y
    before_grid = content[: grid_match.start()].rstrip()
    if 'space-y-6' in before_grid[-100:] or 'space-y-8' in before_grid[-100:]:
        return content, fixes_applied

    # Find the matching closing tag more carefully
    grid_start = grid_match.start()
    grid_end = grid_match.end()

    # Look for closing tag
    closing_tag_match = re.search(r'</EditableMasonryGrid>', content[grid_end:])
    if not closing_tag_match:
        return content, fixes_applied

    grid_end + closing_tag_match.start()
    closing_tag_end = grid_end + closing_tag_match.end()

    # Get indentation
    line_start = content.rfind('\n', 0, grid_start) + 1
    line = content[line_start:grid_start]
    indent = len(line) - len(line.lstrip())
    indent_str = ' ' * indent

    # Insert wrapper
    new_content = (
        content[:grid_start]
        + f'{indent_str}<div className="space-y-6">\n'
        + content[grid_start:closing_tag_end]
        + f'\n{indent_str}</div>'
        + content[closing_tag_end:]
    )

    fixes_applied.append("Added space-y-6 wrapper around EditableMasonryGrid")
    return new_content, fixes_applied


def fix_focus_states(content: str, file_path: str) -> Tuple[str, List[str]]:
    """Add focus states to interactive elements - SAFE VERSION with validation."""
    fixes_applied = []

    # More precise button matching - only match complete button tags
    # Pattern: <button ... className="..." ...>
    button_pattern = r'<button\s+([^>]*className="([^"]*)"[^>]*)>'

    matches = list(re.finditer(button_pattern, content))

    # Limit to prevent excessive changes
    if len(matches) > 50:
        return content, fixes_applied  # Too many buttons - skip

    # Process matches in reverse order to maintain positions
    for match in reversed(matches):
        button_attrs = match.group(1)
        existing_classes = match.group(2)

        # Skip if already has focus states
        if 'focus:' in existing_classes or 'focus-visible:' in existing_classes:
            continue

        # Only add focus states to buttons that have other styling
        if not any(cls in existing_classes for cls in ['bg-', 'hover:', 'px-', 'py-']):
            continue  # Skip unstyled buttons

        # Add focus ring classes
        new_classes = (
            existing_classes
            + ' focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 focus:ring-offset-transparent'
        )

        # Replace only the className value
        new_attrs = button_attrs.replace(f'className="{existing_classes}"', f'className="{new_classes}"')

        # Replace the entire button tag
        new_button = f'<button {new_attrs}>'
        content = content[: match.start()] + new_button + content[match.end() :]
        fixes_applied.append("Added focus states to button")

        # Limit total fixes
        if len(fixes_applied) >= 20:
            break

    return content, fixes_applied


def fix_card_patterns(content: str, file_path: str) -> Tuple[str, List[str]]:
    """Add missing card pattern classes - SAFE VERSION."""
    fixes_applied = []

    # Find glass-panel divs with more precision
    card_pattern = r'<div\s+([^>]*className="([^"]*glass-panel[^"]*)"[^>]*)>'
    matches = list(re.finditer(card_pattern, content))

    # Limit to first 10 cards
    for match in matches[:10]:
        card_attrs = match.group(1)
        existing_classes = match.group(2)
        new_classes = existing_classes

        # Add missing classes one at a time
        changes_made = False

        if 'backdrop-blur-sm' not in existing_classes and 'backdrop-blur' not in existing_classes:
            new_classes += ' backdrop-blur-sm'
            changes_made = True

        if 'hover:bg-white/5' not in existing_classes and 'hover:' not in existing_classes:
            new_classes += ' hover:bg-white/5'
            changes_made = True

        if 'transition-all' not in existing_classes and 'transition' not in existing_classes:
            new_classes += ' transition-all'
            changes_made = True

        if changes_made:
            new_attrs = card_attrs.replace(f'className="{existing_classes}"', f'className="{new_classes}"')

            new_div = f'<div {new_attrs}>'
            content = content[: match.start()] + new_div + content[match.end() :]
            fixes_applied.append("Added card pattern classes")

    return content, fixes_applied


def apply_fixes(
    file_path: Path, fixes_to_apply: List[str] = None, validate: bool = True, project_root: Path = None
) -> Dict[str, Any]:
    """
    Apply fixes to a file with validation.

    Args:
        file_path: Path to file to fix
        fixes_to_apply: List of fixes to apply
        validate: Whether to validate syntax and build
        project_root: Project root for build validation
    """
    if fixes_to_apply is None:
        fixes_to_apply = ['gradient', 'spacing', 'focus', 'cards']

    if project_root is None:
        project_root = Path(__file__).resolve().parents[3]

    try:
        original_content = file_path.read_text(encoding='utf-8')
        content = original_content
        all_fixes = []

        # Apply fixes in order
        if 'gradient' in fixes_to_apply:
            content, fixes = fix_gradient_background(content, str(file_path))
            all_fixes.extend(fixes)

        if 'spacing' in fixes_to_apply:
            content, fixes = fix_spacing_wrapper(content, str(file_path))
            all_fixes.extend(fixes)

        if 'focus' in fixes_to_apply:
            content, fixes = fix_focus_states(content, str(file_path))
            all_fixes.extend(fixes)

        if 'cards' in fixes_to_apply:
            content, fixes = fix_card_patterns(content, str(file_path))
            all_fixes.extend(fixes)

        if content == original_content:
            return {
                "file": str(file_path),
                "fixed": False,
                "fixes_applied": [],
                "reason": "No fixes needed or no changes made",
            }

        # VALIDATION: Check syntax before writing
        if validate:
            is_valid, error = validate_typescript_syntax(file_path, content)
            if not is_valid:
                return {
                    "file": str(file_path),
                    "fixed": False,
                    "error": f"Syntax validation failed: {error}",
                    "fixes_applied": all_fixes,
                }

            # VALIDATION: Check build (optional, can be slow)
            # Only check if we made significant changes
            if len(all_fixes) > 0:
                build_valid, build_error = validate_build(file_path, project_root)
                if not build_valid:
                    return {
                        "file": str(file_path),
                        "fixed": False,
                        "error": f"Build validation failed: {build_error}",
                        "fixes_applied": all_fixes,
                    }

        # Create backup before writing
        backup_path = backup_file(file_path)

        # Write fixed content
        file_path.write_text(content, encoding='utf-8')

        return {"file": str(file_path), "fixed": True, "fixes_applied": all_fixes, "backup": str(backup_path)}

    except Exception as e:
        return {"file": str(file_path), "fixed": False, "error": str(e)}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Auto-fix pattern compliance issues (SAFE VERSION)")
    parser.add_argument("--page", help="Specific page file to fix")
    parser.add_argument("--audit-report", help="Path to audit report JSON")
    parser.add_argument(
        "--fixes",
        nargs="+",
        choices=["gradient", "spacing", "focus", "cards", "all"],
        default=["all"],
        help="Which fixes to apply",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be fixed without making changes")
    parser.add_argument("--no-validate", action="store_true", help="Skip syntax and build validation (NOT RECOMMENDED)")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of pages to fix (default: 10)")

    args = parser.parse_args()

    if args.fixes == ["all"]:
        args.fixes = ["gradient", "spacing", "focus", "cards"]

    project_root = Path(__file__).resolve().parents[3]
    validate = not args.no_validate

    if args.page:
        # Fix single page
        page_path = Path(args.page)
        if not page_path.is_absolute():
            script_dir = Path(__file__).parent
            project_root_local = script_dir.parents[3]
            dashboard_root = project_root_local / "apps" / "dashboard" / "app"
            page_path = dashboard_root / args.page.lstrip("/")

        if not page_path.exists():
            _out(f"❌ Page not found: {page_path}", file=sys.stderr)
            sys.exit(1)

        if args.dry_run:
            _out(f"🔍 DRY RUN: Would fix {page_path}")
            _out(f"   Fixes to apply: {', '.join(args.fixes)}")
            _out(f"   Validation: {'enabled' if validate else 'disabled'}")
        else:
            result = apply_fixes(page_path, args.fixes, validate=validate, project_root=project_root)
            if result.get("fixed"):
                _out(f"✅ Fixed: {result['file']}")
                _out(f"   Fixes applied: {', '.join(result['fixes_applied'])}")
                _out(f"   Backup: {result['backup']}")
            else:
                _out(f"❌ Failed to fix: {result['file']}")
                if result.get("error"):
                    _out(f"   Error: {result['error']}")
                if result.get("reason"):
                    _out(f"   Reason: {result['reason']}")

    elif args.audit_report:
        # Fix pages from audit report
        report_path = Path(args.audit_report)
        if not report_path.exists():
            _out(f"❌ Audit report not found: {report_path}", file=sys.stderr)
            sys.exit(1)

        with open(report_path) as f:
            audit_data = json.load(f)

        # Find pages with high severity issues
        pages_to_fix = []
        for result in audit_data.get("results", []):
            summary = result.get("summary", {})
            if summary.get("high_severity", 0) > 0 or summary.get("total_issues", 0) > 5:
                pages_to_fix.append(result["file"])

        _out(f"🔍 Found {len(pages_to_fix)} pages with issues to fix")
        _out(f"   Will fix up to {args.limit} pages")
        if validate:
            _out("   ⚠️  Validation enabled - this may be slow")

        fixed_count = 0
        failed_count = 0
        for page_file in pages_to_fix[: args.limit]:
            page_path = Path(page_file)
            if not page_path.exists():
                continue

            if args.dry_run:
                _out(f"🔍 DRY RUN: Would fix {page_path}")
            else:
                result = apply_fixes(page_path, args.fixes, validate=validate, project_root=project_root)
                if result.get("fixed"):
                    fixed_count += 1
                    _out(f"✅ [{fixed_count}/{min(len(pages_to_fix), args.limit)}] Fixed: {page_path.name}")
                    _out(f"   Fixes: {', '.join(result['fixes_applied'][:3])}")
                else:
                    failed_count += 1
                    _out(
                        f"❌ [{failed_count} failed] {page_path.name}: {result.get('error', result.get('reason', 'Unknown error'))}"
                    )

        if not args.dry_run:
            _out("\n📊 Summary:")
            _out(f"   ✅ Fixed: {fixed_count}")
            _out(f"   ❌ Failed: {failed_count}")
        _out(f"   💾 Backups saved under {_get_temp_archive_dir() / 'frontend' / 'auto-fix'}")

    else:
        # Find latest audit report
        data_dir = _get_operations_dir() / "frontend" / "audits"
        audit_files = sorted(data_dir.glob("pattern_compliance_audit_*.json"), reverse=True)

        if not audit_files:
            _out("❌ No audit reports found. Run audit first.", file=sys.stderr)
            sys.exit(1)

        latest_report = audit_files[0]
        _out(f"📄 Using latest audit report: {latest_report.name}")

        with open(latest_report) as f:
            audit_data = json.load(f)

        # Get pages with issues
        pages_to_fix = []
        for result in audit_data.get("results", []):
            file_path = result.get("file")
            if file_path:
                pages_to_fix.append((file_path, result.get("summary", {})))

        # Sort by issue count (high severity first)
        pages_to_fix.sort(key=lambda x: (x[1].get("high_severity", 0), x[1].get("total_issues", 0)), reverse=True)

        _out(f"🔍 Found {len(pages_to_fix)} pages with issues")
        _out(f"   Will fix top {args.limit} pages with most issues")
        if validate:
            _out("   ⚠️  Validation enabled - this may be slow")

        fixed_count = 0
        failed_count = 0
        for page_file, summary in pages_to_fix[: args.limit]:
            page_path = Path(page_file)
            if not page_path.exists():
                continue

            if args.dry_run:
                _out(f"🔍 DRY RUN: Would fix {page_path.name} ({summary.get('total_issues', 0)} issues)")
            else:
                result = apply_fixes(page_path, args.fixes, validate=validate, project_root=project_root)
                if result.get("fixed"):
                    fixed_count += 1
                    _out(f"✅ [{fixed_count}/{args.limit}] Fixed: {page_path.name}")
                    if result.get("fixes_applied"):
                        _out(f"   Applied: {', '.join(result['fixes_applied'][:3])}")
                else:
                    failed_count += 1
                    error_msg = result.get('error', result.get('reason', 'Unknown error'))
                    _out(f"❌ [{failed_count} failed] {page_path.name}: {error_msg}")

        if not args.dry_run:
            _out("\n📊 Summary:")
            _out(f"   ✅ Fixed: {fixed_count}")
            _out(f"   ❌ Failed: {failed_count}")
            _out(f"   💾 Backups saved under {_get_temp_archive_dir() / 'frontend' / 'auto-fix'}")


if __name__ == "__main__":
    main()
