"""auto-debt-scan: Identify and prioritize technical debt.
Extracted from /ops-debt (ADR-200).

Scan: analyzes large files and git churn to build a prioritized
technical debt inventory.
Fix: generates a debt report with severity ranking and recommendations.

Note: TODO marker scanning is handled by auto-markers (code-quality loop).
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
import subprocess
from pathlib import Path

from src.lib.git_ops import commit_files
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, check_intentional_skip


name = "auto-debt-scan"

_LARGE_FILE_THRESHOLD = 600  # lines
_MARKER_INJECTION_THRESHOLD = 800  # lines — inject TODO_CLEANUP at d>=1
_MARKER_REMOVAL_THRESHOLD = 600   # lines — hysteresis: only remove markers below this
_HELPER_EXTRACTION_THRESHOLD = 1600  # lines — suggest extraction at d>=2
_SKIP_DIRS = {"node_modules", ".next", "__pycache__", "runtime", ".venv", ".venv-test", ".git", "dist"}
_SKIP_FILES = {"generated-registry.ts", "generated-block-registry.ts"}
# Auto-generated dashboard copies (source lives in plugin augur/dashboard/) — skip to avoid double-counting
_SKIP_PATH_PREFIXES = ("apps/dashboard/app/",)
_TEST_THRESHOLD_MULTIPLIER = 2.0  # Test files get a higher line threshold
_TODO_CLEANUP_MARKER = "TODO_CLEANUP: This file is "
_TODO_CLEANUP_LINE = re.compile(
    r"^\s*(?:#|//)\s+TODO_CLEANUP: This file is (?P<lines>\d+) lines — consider splitting into smaller modules\s*$"
)


def _scan_large_files(project_root: Path, difficulty: int) -> list[dict]:
    """Find oversized source files that should be refactored."""
    if difficulty < 1:
        return []

    issues: list[dict] = []
    threshold = max(300, _LARGE_FILE_THRESHOLD - (difficulty * 50))  # Floor at 300 lines

    for ext in ("*.py", "*.ts", "*.tsx"):
        for filepath in project_root.glob(f"**/{ext}"):
            if any(skip in filepath.parts for skip in _SKIP_DIRS):
                continue
            if filepath.name in _SKIP_FILES:
                continue
            # Skip auto-generated dashboard copies to avoid double-counting
            rel = str(filepath.relative_to(project_root))
            if any(rel.startswith(prefix) for prefix in _SKIP_PATH_PREFIXES):
                continue
            # ADR-269: skip files with INTENTIONAL_SKIP markers
            if check_intentional_skip(filepath):
                continue
            try:
                lines = filepath.read_text(encoding="utf-8", errors="ignore").splitlines()
                # Test files get a higher threshold (they're naturally longer)
                is_test = "test" in filepath.stem.lower() or "/tests/" in str(filepath)
                effective = int(threshold * _TEST_THRESHOLD_MULTIPLIER) if is_test else threshold
                if len(lines) > effective:
                    issues.append({
                        "action": "large-file",
                        "file": rel,
                        "lines": len(lines),
                        "threshold": effective,
                    })
            except OSError:
                continue

    return issues


def _scan_git_churn(project_root: Path, difficulty: int) -> list[dict]:
    """Find files that change frequently (high churn = maintenance burden)."""
    if difficulty < 2:
        return []

    try:
        result = subprocess.run(
            ["git", "log", "--format=", "--name-only", "-n", "50"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        if result.returncode != 0:
            return []

        file_counts: dict[str, int] = {}
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if line and (line.endswith(".py") or line.endswith(".ts") or line.endswith(".tsx")):
                file_counts[line] = file_counts.get(line, 0) + 1

        issues = []
        for filepath, count in sorted(file_counts.items(), key=lambda x: -x[1]):
            if count >= 5:
                issues.append({
                    "action": "high-churn",
                    "file": filepath,
                    "changes_in_last_50": count,
                })
        return issues[:10]  # Top 10 churning files

    except (OSError, subprocess.SubprocessError):
        return []


def scan(ctx: OpsContext) -> ScanResult:
    all_issues: list[dict] = []

    large = _scan_large_files(ctx.project_root, ctx.difficulty)
    all_issues.extend(large)

    churn = _scan_git_churn(ctx.project_root, ctx.difficulty)
    all_issues.extend(churn)

    if not all_issues:
        return ScanResult(issues=[], summary="No significant technical debt found", severity="info")

    parts = []
    if large:
        parts.append(f"{len(large)} oversized files")
    if churn:
        parts.append(f"{len(churn)} high-churn files")

    return ScanResult(
        issues=all_issues,
        summary=f"Debt scan: {', '.join(parts)}",
        severity="warning",
    )


def _already_has_debt_marker(filepath: Path) -> bool:
    """Check if a file already has ANY TODO_CLEANUP marker anywhere."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        return _TODO_CLEANUP_MARKER in content
    except OSError:
        return True  # Assume marked to avoid double-injection


def _iter_source_files(project_root: Path):
    """Yield (filepath, rel_path) for all source files in scan scope."""
    for ext in ("*.py", "*.ts", "*.tsx", "*.js", "*.jsx"):
        for filepath in project_root.glob(f"**/{ext}"):
            if any(skip in filepath.parts for skip in _SKIP_DIRS):
                continue
            rel = str(filepath.relative_to(project_root))
            if any(rel.startswith(prefix) for prefix in _SKIP_PATH_PREFIXES):
                continue
            yield filepath, rel


def _inject_todo_markers(
    project_root: Path, large_issues: list[dict],
) -> list[str]:
    """Inject TODO_CLEANUP markers into files exceeding the injection threshold.

    ADR-417: At d>=1, add markers for 800+ line files.
    Idempotent: skips files that already have a marker.
    Returns list of modified file paths (relative).
    """
    changed: list[str] = []
    for iss in large_issues:
        line_count = iss["lines"]
        if line_count < _MARKER_INJECTION_THRESHOLD:
            continue
        filepath = project_root / iss["file"]
        if _already_has_debt_marker(filepath):
            continue
        try:
            content = filepath.read_text(encoding="utf-8")
        except OSError:
            continue

        # Determine comment style
        ext = filepath.suffix
        if ext in (".py",):
            marker = f"# TODO_CLEANUP: This file is {line_count} lines — consider splitting into smaller modules\n"
        elif ext in (".ts", ".tsx", ".js", ".jsx"):
            marker = f"// TODO_CLEANUP: This file is {line_count} lines — consider splitting into smaller modules\n"
        else:
            continue

        lines = content.splitlines(keepends=True)
        insert_at = 0
        if ext == ".py":
            insert_at = _python_marker_insert_index(lines)
        elif ext in (".ts", ".tsx", ".js", ".jsx"):
            insert_at = _js_marker_insert_index(lines)

        lines.insert(insert_at, marker)
        filepath.write_text("".join(lines), encoding="utf-8")
        changed.append(iss["file"])

    return changed


def _python_marker_insert_index(lines: list[str]) -> int:
    """Return a syntax-safe insertion point for a top-level Python marker."""
    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    if len(lines) > insert_at and "coding" in lines[insert_at].lower():
        insert_at += 1

    while insert_at < len(lines) and not lines[insert_at].strip():
        insert_at += 1

    if insert_at < len(lines):
        stripped = lines[insert_at].strip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            quote = stripped[:3]
            if stripped.count(quote) >= 2 and len(stripped) > 3:
                insert_at += 1
            else:
                for idx in range(insert_at + 1, len(lines)):
                    if quote in lines[idx]:
                        insert_at = idx + 1
                        break

    while insert_at < len(lines) and not lines[insert_at].strip():
        insert_at += 1

    while insert_at < len(lines) and lines[insert_at].strip().startswith("from __future__ import "):
        insert_at += 1
        while insert_at < len(lines) and not lines[insert_at].strip():
            insert_at += 1

    return insert_at


def _js_marker_insert_index(lines: list[str]) -> int:
    """Return an insertion point that preserves JS/TS file directives."""
    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    while insert_at < len(lines) and not lines[insert_at].strip():
        insert_at += 1
    directive = lines[insert_at].strip() if insert_at < len(lines) else ""
    if directive in {'"use client";', "'use client';", '"use server";', "'use server';"}:
        insert_at += 1
    return insert_at


def _cleanup_markers(project_root: Path, large_issues: list[dict]) -> tuple[list[str], list[str]]:
    """Single-pass marker cleanup: deduplicate stacked markers AND prune stale ones.

    Returns (deduped_files, pruned_files).
    - deduped: files where duplicate markers were collapsed to one
    - pruned: files where markers were removed (file no longer above threshold)
    """
    tracked_large = {
        issue["file"]
        for issue in large_issues
        if issue["lines"] >= _MARKER_REMOVAL_THRESHOLD
    }
    deduped: list[str] = []
    pruned: list[str] = []

    for filepath, rel in _iter_source_files(project_root):
        try:
            lines = filepath.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
        except OSError:
            continue

        marker_indices = [
            i for i, line in enumerate(lines)
            if _TODO_CLEANUP_LINE.match(line.rstrip("\n\r"))
        ]
        if not marker_indices:
            continue

        if rel not in tracked_large:
            # File no longer above threshold — remove ALL markers
            new_lines = [line for i, line in enumerate(lines) if i not in set(marker_indices)]
            if len(new_lines) < len(lines):
                filepath.write_text("".join(new_lines), encoding="utf-8")
                pruned.append(rel)
        elif len(marker_indices) > 1:
            # File still large but has duplicate markers — keep only the last
            drop = set(marker_indices[:-1])
            new_lines = [line for i, line in enumerate(lines) if i not in drop]
            if len(new_lines) < len(lines):
                filepath.write_text("".join(new_lines), encoding="utf-8")
                deduped.append(rel)

    return deduped, pruned


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} debt items found")

    large = [i for i in issues if i["action"] == "large-file"]
    churn = [i for i in issues if i["action"] == "high-churn"]
    all_changes: list[str] = []

    # Single-pass: deduplicate stacked markers AND prune stale ones
    deduped, pruned = _cleanup_markers(ctx.project_root, large)
    all_changes.extend(deduped)
    all_changes.extend(pruned)

    # Idempotent: _already_has_debt_marker checks the full file content
    if ctx.difficulty >= 1 and large:
        injected = _inject_todo_markers(ctx.project_root, large)
        for path in injected:
            if path not in all_changes:
                all_changes.append(path)

    # Generate debt report
    report_dir = ctx.project_root / "docs" / "generated"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / "tech-debt-report.md"

    lines = [
        "# Technical Debt Report",
        "",
    ]

    if large:
        lines.extend([
            "## Oversized Files",
            "",
            "| File | Lines | Threshold |",
            "|------|-------|-----------|",
        ])
        for iss in sorted(large, key=lambda x: -x["lines"]):
            marker_status = " (marker injected)" if iss["file"] in all_changes else ""
            lines.append(f"| `{iss['file']}` | {iss['lines']} | {iss['threshold']} |{marker_status}")
        lines.append("")

    if churn:
        lines.extend([
            "## High Churn Files (last 50 commits)",
            "",
            "| File | Changes |",
            "|------|---------|",
        ])
        for iss in churn:
            lines.append(f"| `{iss['file']}` | {iss['changes_in_last_50']} |")
        lines.append("")

    # ADR-417: At d>=2, flag files needing helper extraction
    extraction_candidates = [i for i in large if i["lines"] >= _HELPER_EXTRACTION_THRESHOLD]
    if extraction_candidates and ctx.difficulty >= 2:
        lines.extend([
            "## Helper Extraction Candidates (1600+ lines)",
            "",
            "| File | Lines | Suggested Action |",
            "|------|-------|-----------------|",
        ])
        for iss in sorted(extraction_candidates, key=lambda x: -x["lines"]):
            lines.append(
                f"| `{iss['file']}` | {iss['lines']} | "
                f"Extract helper functions into separate module |"
            )
        lines.append("")

    report_file.write_text("\n".join(lines), encoding="utf-8")
    all_changes.append(str(report_file.relative_to(ctx.project_root)))

    sha = commit_files(
        ctx.project_root,
        "chore(auto-debt-scan): update debt report and inject TODO_CLEANUP markers"
        if len(all_changes) > 1
        else "docs(adaptive): update technical debt report",
        [str(Path(c).relative_to(ctx.project_root)) if Path(c).is_absolute() else c for c in all_changes],
    )

    parts = [f"{len(large)} oversized", f"{len(churn)} high-churn"]
    injected_count = len([c for c in all_changes if c != str(report_file.relative_to(ctx.project_root))])
    if injected_count:
        parts.append(f"{injected_count} markers injected")
    if pruned:
        parts.append(f"{len(pruned)} stale markers removed")
    if extraction_candidates and ctx.difficulty >= 2:
        parts.append(f"{len(extraction_candidates)} extraction candidates")
    summary = f"Debt scan: {', '.join(parts)}"
    if sha:
        summary += f" (commit {sha})"

    fix_type = "code-fix" if injected_count else "report"
    actions = [{"commit": sha}] if sha else []
    return FixResult(
        success=True, changes=all_changes, actions=actions,
        summary=summary, fix_type=fix_type,
    )
