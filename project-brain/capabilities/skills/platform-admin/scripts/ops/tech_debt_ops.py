"""auto-tech-debt: Identify, categorize, and prioritize technical debt.

Debt signals:
  - TODO/FIXME/HACK/XXX comments (note: TODO_ markers handled by auto-tidy)
  - Oversized files (>500 lines)
  - Long functions (>50 lines)
  - Deprecated imports
  - High-churn files (from git log)

Difficulty levels:
  d0: Surface — count bare TODO/FIXME/HACK/XXX comments, flag oversized files
  d1: Content — detect long functions, deprecated imports
  d2: Deep — git churn analysis (last 50 commits), generate prioritized report
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
import re
import subprocess
from pathlib import Path

from src.config.paths import get_project_root
from src.lib.ops_protocol import (
    DifficultySpec,
    FixResult,
    OpsContext,
    ScanResult,
    evolution_gap,
    make_issue,
    report_only_fix,
)

name = "auto-tech-debt"

DIFFICULTY_SPEC: DifficultySpec = {
    0: "Surface — oversized files (>800 lines only)",
    1: "Content — bare TODO/FIXME/HACK/XXX counts, oversized files (>500 lines), long functions (>50 lines), deprecated imports",
    2: "Deep — git churn analysis, prioritized debt report",
}

logger = logging.getLogger(__name__)

# Extensions to scan
SCAN_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}

# Directories to scan
SCAN_DIRS = ["skills", "src", "apps"]

# Bare comment markers (not TODO_ which is handled by auto-tidy)
BARE_MARKER_PATTERN = re.compile(
    r"\b(TODO|FIXME|HACK|XXX)\b(?!_)",
    re.IGNORECASE,
)

# Deprecated import patterns
DEPRECATED_PATTERNS: list[tuple[str, str]] = [
    (r"from\s+unittest\s+import\s+mock", "Use unittest.mock directly or pytest-mock"),
    (r"import\s+imp\b", "Use importlib instead of deprecated imp module"),
    (r"from\s+collections\s+import.*\bMutableMapping\b", "Import from collections.abc"),
    (r"from\s+collections\s+import.*\bMapping\b", "Import from collections.abc"),
    (r"from\s+typing\s+import.*\bDict\b", "Use dict instead of typing.Dict (Python 3.9+)"),
    (r"from\s+typing\s+import.*\bList\b", "Use list instead of typing.List (Python 3.9+)"),
    (r"from\s+typing\s+import.*\bTuple\b", "Use tuple instead of typing.Tuple (Python 3.9+)"),
    (r"from\s+typing\s+import.*\bSet\b", "Use set instead of typing.Set (Python 3.9+)"),
    (r"from\s+typing\s+import.*\bOptional\b", "Use X | None instead of Optional[X] (Python 3.10+)"),
    (r"from\s+typing\s+import.*\bUnion\b", "Use X | Y instead of Union[X, Y] (Python 3.10+)"),
]
DEPRECATED_RE = [(re.compile(p), msg) for p, msg in DEPRECATED_PATTERNS]

# Function definition patterns
PY_FUNC_RE = re.compile(r"^(\s*)def\s+\w+")
TS_FUNC_RE = re.compile(
    r"^(\s*)(?:export\s+)?(?:async\s+)?function\s+\w+"
    r"|^(\s*)(?:export\s+)?const\s+\w+\s*=\s*(?:async\s+)?\("
)

OVERSIZED_THRESHOLD = 500
LONG_FUNC_THRESHOLD = 50


def _count_function_lines(lines: list[str], start: int, indent: str, lang: str) -> int:
    """Count lines in a function body starting from the definition line."""
    base_indent = len(indent)
    count = 1  # Include the definition line
    for i in range(start + 1, len(lines)):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            count += 1
            continue
        current_indent = len(line) - len(line.lstrip())
        if current_indent <= base_indent:
            # Sibling def/class at the same or shallower indent ends this function.
            # `stripped` is leading-and-trailing stripped so the prefix check sees
            # the keyword regardless of leading whitespace (the previous rstrip-only
            # form silently ignored every nested method, vastly inflating counts).
            if lang == "py" and (
                stripped.startswith("def ")
                or stripped.startswith("async def ")
                or stripped.startswith("class ")
                or stripped.startswith("@")
            ):
                break
            if lang == "ts" and (
                stripped.startswith("function ")
                or stripped.startswith("export ")
            ):
                if not stripped.startswith("export default"):
                    break
            if current_indent < base_indent:
                break
        count += 1
    return count


def _find_long_functions(path: Path, project_root: Path) -> list[dict]:
    """Find functions longer than LONG_FUNC_THRESHOLD lines."""
    hits: list[dict] = []
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return hits

    lines = content.splitlines()
    rel = str(path.relative_to(project_root))
    lang = "py" if path.suffix == ".py" else "ts"
    func_re = PY_FUNC_RE if lang == "py" else TS_FUNC_RE

    for i, line in enumerate(lines):
        m = func_re.match(line)
        if m:
            indent = m.group(1) or ""
            func_len = _count_function_lines(lines, i, indent, lang)
            if func_len > LONG_FUNC_THRESHOLD:
                # Extract function name
                stripped = line.strip()
                func_name = stripped[:60]
                hits.append({
                    "path": rel,
                    "line": i + 1,
                    "length": func_len,
                    "name": func_name,
                })
    return hits


def _git_churn_analysis(project_root: Path, commit_count: int = 50) -> list[dict]:
    """Analyze git log for high-churn files."""
    try:
        result = subprocess.run(
            ["git", "log", f"-{commit_count}", "--format=format:", "--name-only"],
            cwd=str(project_root),
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return []
    except Exception:
        return []

    # Count file occurrences
    file_counts: dict[str, int] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # Only count files in our scan dirs with our extensions
        parts = line.split("/")
        if not parts:
            continue
        if parts[0] not in SCAN_DIRS:
            continue
        ext = Path(line).suffix
        if ext not in SCAN_EXTENSIONS:
            continue
        file_counts[line] = file_counts.get(line, 0) + 1

    # High churn = files changed in >20% of commits
    threshold = max(3, commit_count // 5)
    churn_files = [
        {"path": path, "changes": count}
        for path, count in sorted(file_counts.items(), key=lambda x: -x[1])
        if count >= threshold
    ]
    return churn_files[:20]  # Top 20


def scan(ctx: OpsContext) -> ScanResult:
    """Scan codebase for technical debt signals."""
    project_root = get_project_root()
    issues: list[dict] = []
    items_scanned = 0

    # Collect files
    all_files: list[Path] = []
    for scan_dir_name in SCAN_DIRS:
        scan_dir = project_root / scan_dir_name
        if not scan_dir.is_dir():
            continue
        for path in scan_dir.rglob("*"):
            if not path.is_file() or path.suffix not in SCAN_EXTENSIONS:
                continue
            if any(part.startswith(".") or part == "node_modules" for part in path.parts):
                continue
            all_files.append(path)

    items_scanned = len(all_files)

    for path in all_files:
        rel = str(path.relative_to(project_root))

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        lines = content.splitlines()

        # --- d1+: Bare TODO/FIXME/HACK/XXX ---
        # Bare markers are informational debt, not errors — gate behind d1
        if ctx.difficulty >= 1:
            bare_count = 0
            for line in lines:
                bare_count += len(BARE_MARKER_PATTERN.findall(line))
            if bare_count > 0:
                issues.append(make_issue(
                    category="tech-debt",
                    detail=f"{bare_count} bare TODO/FIXME/HACK/XXX comment(s) — consider converting to TODO_ markers",
                    path=rel,
                    kind="maintenance",
                    root_cause_type="manual_debt",
                    fixability="manual",
                    debt_type="bare-markers",
                    count=bare_count,
                ))

        # --- d0: Oversized files (d0 uses 800-line threshold, d1+ uses 500) ---
        effective_threshold = OVERSIZED_THRESHOLD if ctx.difficulty >= 1 else 800
        if len(lines) > effective_threshold:
            issues.append(make_issue(
                category="tech-debt",
                detail=f"File has {len(lines)} lines (threshold: {effective_threshold}) — consider splitting",
                path=rel,
                kind="maintenance",
                root_cause_type="manual_debt",
                fixability="manual",
                debt_type="oversized-file",
                line_count=len(lines),
            ))

        # --- d1: Deprecated imports ---
        if ctx.difficulty >= 1 and path.suffix == ".py":
            for pattern, message in DEPRECATED_RE:
                for lineno, line in enumerate(lines, 1):
                    if pattern.search(line):
                        issues.append(make_issue(
                            category="tech-debt",
                            detail=f"Deprecated import at line {lineno}: {message}",
                            path=rel,
                            kind="maintenance",
                            root_cause_type="manual_debt",
                            fixability="manual",
                            debt_type="deprecated-import",
                            line=lineno,
                        ))
                        break  # One per pattern per file

    # --- d1: Long functions ---
    if ctx.difficulty >= 1:
        for path in all_files:
            long_funcs = _find_long_functions(path, project_root)
            for func in long_funcs:
                issues.append(make_issue(
                    category="tech-debt",
                    detail=f"Function ({func['length']} lines, threshold: {LONG_FUNC_THRESHOLD}): {func['name']}",
                    path=func["path"],
                    kind="maintenance",
                    root_cause_type="manual_debt",
                    fixability="manual",
                    debt_type="long-function",
                    line=func["line"],
                    function_length=func["length"],
                ))

    # --- d2: Git churn ---
    if ctx.difficulty >= 2:
        churn_files = _git_churn_analysis(project_root)
        for churn in churn_files:
            issues.append(make_issue(
                category="tech-debt",
                detail=f"High churn: {churn['changes']} changes in last 50 commits — possible stability issue",
                path=churn["path"],
                kind="maintenance",
                root_cause_type="manual_debt",
                fixability="manual",
                debt_type="high-churn",
                change_count=churn["changes"],
            ))

    # Evolution gap
    if ctx.difficulty >= 2 and not issues:
        issues.append(evolution_gap(
            "No tech debt signals detected. "
            "Consider adding: cyclomatic complexity analysis, "
            "dependency freshness checks (outdated npm/pip packages), "
            "test-to-code ratio tracking. "
            "Next: implement complexity scoring via radon or similar.",
            category="tech-debt",
        ))

    # Categorize summary
    by_type: dict[str, int] = {}
    for i in issues:
        dt = i.get("debt_type", "other")
        by_type[dt] = by_type.get(dt, 0) + 1

    severity = "warning" if len(issues) > 10 else "info"
    health = "degraded" if severity == "warning" else "verified"

    type_summary = ", ".join(f"{k}={v}" for k, v in sorted(by_type.items()))
    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} debt signal(s) ({type_summary})" if issues else "No tech debt signals",
        severity=severity,
        health=health,
        items_scanned=items_scanned,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Tech debt is report-only — no auto-fix, just categorize and prioritize."""
    return report_only_fix(ctx, "tech-debt-report.json", issues, noun="debt signal")
