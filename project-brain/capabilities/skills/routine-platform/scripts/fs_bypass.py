"""auto-fs-bypass: Detect direct filesystem access in API routes.

Scans all **/api/**/route.ts files for fs operations that violate
CLAUDE.md rule #11 (MCP-first API) and ADR-453 (vault decoupling).

Routes with @fs-exempt markers are reported as exemptions, not violations.
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
import re
import sys
from pathlib import Path

from src.config.paths import get_project_root
from src.lib.ops_protocol import (
    OpsContext,
    ScanResult,
    declare_ops_capabilities,
    report_only_fix,
)

name = "auto-fs-bypass"
OPS_CAPABILITIES = declare_ops_capabilities(
    platforms=("cross_platform",),
    windows_fix_mode="report_only",
    skip_reason="filesystem bypass fixes stay report-only on Windows in v1",
)

DIFFICULTY_SPEC = {
    0: "Surface — count API route files",
    1: "Detect fs import/require statements",
    2: "Detect inline fs method calls",
    3: "Full scan with exemption tracking",
}

# fs operations to detect — covers import statements and inline usage
_FS_OPERATION_RE = re.compile(
    r"\b(?:readFile|writeFile|readdir|readFileSync|writeFileSync|readdirSync"
    r"|statSync|mkdirSync|unlinkSync|appendFile)\b"
)

# Import patterns for fs modules
_FS_IMPORT_RE = re.compile(
    r"""(?:import\s+.*\s+from\s+['"](?:node:)?fs(?:/promises)?['"]"""
    r"""|require\s*\(\s*['"](?:node:)?fs(?:/promises)?['"]\s*\))""",
)

# Exemption marker
_EXEMPT_RE = re.compile(r"@fs-exempt")

# Single-line comment
_SINGLE_LINE_COMMENT_RE = re.compile(r"//")

# Block comment boundaries
_BLOCK_OPEN_RE = re.compile(r"/\*")
_BLOCK_CLOSE_RE = re.compile(r"\*/")


def _is_inside_comment(line_text: str, col: int) -> bool:
    """Check if a column position in a line falls inside a JS/TS comment.

    Handles:
    - // single-line comments
    - Lines inside /* */ block comments (lines starting with * or /*)
    - Inline /* */ comments wrapping the match
    """
    stripped = line_text.lstrip()

    # Line is inside a block comment body (e.g. " * some text")
    if stripped.startswith("*") and not stripped.startswith("*/"):
        return True

    # Line opens a block comment (e.g. "/* some text" or "/** some text")
    if stripped.startswith("/*"):
        return True

    # Check if // appears before the match column
    for m in _SINGLE_LINE_COMMENT_RE.finditer(line_text):
        if m.start() < col:
            return True

    # Check if an inline /* */ block contains the match position
    for m in _BLOCK_OPEN_RE.finditer(line_text):
        open_pos = m.start()
        if open_pos >= col:
            break
        close_m = _BLOCK_CLOSE_RE.search(line_text, open_pos + 2)
        close_pos = close_m.end() if close_m else len(line_text)
        if open_pos < col < close_pos:
            return True

    return False


_ROUTE_GLOBS = [
    "apps/dashboard/app/api/**/route.ts",
    "plugins/*/skills/*/augur/api/**/route.ts",
    "project-brain/capabilities/skills/*/augur/api/**/route.ts",
]


def _iter_route_files(project_root: Path):
    """Yield all API route files, deduplicating."""
    seen: set[str] = set()
    for pattern in _ROUTE_GLOBS:
        for f in sorted(project_root.glob(pattern)):
            rel = str(f.relative_to(project_root))
            if rel not in seen:
                seen.add(rel)
                yield f, rel


def _scan_file(file_path: Path, rel: str, difficulty: int) -> tuple[list[dict], bool]:
    """Scan a single file. Returns (issues, is_exempt)."""
    content = file_path.read_text(errors="replace")
    issues: list[dict] = []
    is_exempt = bool(_EXEMPT_RE.search(content))
    lines = content.splitlines()

    # d1+: Check for fs import/require
    if difficulty >= 1:
        for match in _FS_IMPORT_RE.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            # Check if this specific line has @fs-exempt
            line_text = lines[line_num - 1] if line_num <= len(lines) else ""
            line_exempt = bool(_EXEMPT_RE.search(line_text)) or is_exempt
            issues.append({
                "category": "fs-import",
                "type": "exemption" if line_exempt else "violation",
                "file": rel,
                "line": line_num,
                "detail": f"fs import: {match.group(0).strip()[:80]}",
                "exempt": line_exempt,
            })

    # d2+: Check for inline fs method calls
    if difficulty >= 2:
        for match in _FS_OPERATION_RE.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            line_text = lines[line_num - 1] if line_num <= len(lines) else ""

            # Skip matches inside comments (false positives from TODO markers, etc.)
            line_start = content.rfind("\n", 0, match.start()) + 1
            col = match.start() - line_start
            if _is_inside_comment(line_text, col):
                continue

            line_exempt = bool(_EXEMPT_RE.search(line_text)) or is_exempt
            issues.append({
                "category": "fs-call",
                "type": "exemption" if line_exempt else "violation",
                "file": rel,
                "line": line_num,
                "detail": f"fs operation: {match.group(0)}",
                "exempt": line_exempt,
            })

    return issues, is_exempt


def scan(ctx: OpsContext) -> ScanResult:
    """Scan API routes for direct filesystem access."""
    all_issues: list[dict] = []
    file_count = 0
    exempt_files = 0

    for file_path, rel in _iter_route_files(ctx.project_root):
        file_count += 1

        if ctx.difficulty < 1:
            continue

        issues, is_exempt = _scan_file(file_path, rel, ctx.difficulty)
        if is_exempt:
            exempt_files += 1
        all_issues.extend(issues)

    if ctx.difficulty < 1:
        return ScanResult(
            issues=[],
            summary=f"{file_count} API route files scanned (d0 surface)",
            severity="info",
            health="verified",
            items_scanned=file_count,
        )

    violations = [i for i in all_issues if not i.get("exempt")]
    exemptions = [i for i in all_issues if i.get("exempt")]

    if violations:
        severity = "warning"
        health = "degraded"
        summary = (
            f"{len(violations)} fs violation(s) in {file_count} routes"
            f" ({len(exemptions)} exemption(s) acknowledged)"
        )
    else:
        severity = "info"
        health = "verified"
        if exemptions:
            summary = (
                f"{len(exemptions)} exemption(s) acknowledged, 0 new violations"
                f" in {file_count} routes"
            )
        else:
            summary = f"No fs access detected in {file_count} routes"

    # Only return actual violations as issues — acknowledged exemptions
    # should not count toward the engine's issue total.  When all fs usage
    # is properly exempted the scan is "clean".
    return ScanResult(
        issues=violations,
        summary=summary,
        severity=severity,
        health=health,
        items_scanned=file_count,
    )


def fix(ctx: OpsContext, issues: list[dict]):
    """Report-only — fs bypass fixes require MCP tool migration."""
    return report_only_fix(ctx, "fs-bypass-latest.json", issues, noun="fs bypass")


def main():
    """CLI entry point for standalone execution."""
    project_root = get_project_root()
    ctx = OpsContext(project_root=project_root, difficulty=3, verbose=True)
    result = scan(ctx)

    # result.issues contains only violations (exemptions are excluded).
    # To display exemptions in CLI output, re-scan files for exempt entries.
    violations = result.issues
    exemptions: list[dict] = []
    for file_path, rel in _iter_route_files(project_root):
        file_issues, _ = _scan_file(file_path, rel, ctx.difficulty)
        exemptions.extend(i for i in file_issues if i.get("exempt"))

    print(f"\n=== auto-fs-bypass scan ===")
    print(f"Summary: {result.summary}")
    print(f"Health: {result.health}")

    if violations:
        print(f"\nViolations ({len(violations)}):")
        for v in violations:
            print(f"  {v['file']}:{v['line']} — {v['detail']}")

    if exemptions:
        print(f"\nExemptions acknowledged ({len(exemptions)}):")
        for e in exemptions:
            print(f"  {e['file']}:{e['line']} — {e['detail']}")

    if not violations and not exemptions:
        print("\nNo fs access detected in any API route.")

    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
