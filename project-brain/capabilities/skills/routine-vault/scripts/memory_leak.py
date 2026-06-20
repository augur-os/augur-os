"""
auto-memory-leak — Detect dashboard memory leaks.

Scans TypeScript/TSX files for patterns that cause memory leaks:
  - setInterval without cleanup in useEffect
  - Aggressive polling (< 10s intervals)
  - HMR-unsafe module-level setInterval (no globalThis guard)
  - Unbounded module-level Map/Set caches
  - autoRefresh defaulting to true

Implements OpsCommand protocol (scan / fix).
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
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from src.config.paths import get_all_client_skill_dirs
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

# ---------------------------------------------------------------------------
# Module metadata (OpsCommand protocol)
# ---------------------------------------------------------------------------
name = "auto-memory-leak"

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# setInterval at module level (outside functions/classes)
_RE_MODULE_INTERVAL = re.compile(
    r"^(?:const|let|var)?\s*\w*\s*=?\s*setInterval\s*\(",
    re.MULTILINE,
)

# globalThis singleton guard
_RE_GLOBAL_THIS = re.compile(r"globalThis\s+as\s+unknown\s+as")

# Unbounded module-level Map / Set / plain object cache
_RE_MODULE_CACHE = re.compile(
    r"^(?:const|let|var)\s+\w+\s*=\s*new\s+(?:Map|Set|WeakMap|WeakSet)\s*[<(]",
    re.MULTILINE,
)

# MAX size guard near a cache declaration
_RE_MAX_GUARD = re.compile(r"MAX_\w*(?:ENTRIES|SIZE|CACHE|LIMIT)", re.IGNORECASE)

# setInterval inside useEffect without clearInterval in return
_RE_USE_EFFECT = re.compile(
    r"useEffect\s*\(\s*\(\)\s*=>\s*\{",
)

# Cleanup return with clearInterval/clearTimeout — matches both block and expression form
_RE_USE_EFFECT_CLEANUP = re.compile(
    r"return\s*\(\)\s*=>\s*(?:\{[^}]*)?clear(?:Interval|Timeout)",
    re.DOTALL,
)

# setInterval call
_RE_SET_INTERVAL = re.compile(r"setInterval\s*\(")

_RE_POLLING_SIGNAL = re.compile(
    r"\b(?:fetch|refetch|refresh|reload|poll|queryClient|mutate|request|sync)\b|/api/|router\.refresh",
    re.IGNORECASE,
)
_RE_MARKER = re.compile(
    r"^\s*// TODO_BUG\(auto-memory-leak\): (?P<pattern>[\w-]+) — "
)

# autoRefresh defaulting to true
_RE_AUTOREFRESH_TRUE = re.compile(
    r"useState\s*(?:<[^>]*>)?\s*\(\s*true\s*\).*autoRefresh",
    re.IGNORECASE,
)
_RE_AUTOREFRESH_TRUE_ALT = re.compile(
    r"autoRefresh.*useState\s*(?:<[^>]*>)?\s*\(\s*true\s*\)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_client_component(content: str) -> bool:
    """Check if file is a React client component."""
    return content.lstrip().startswith(("'use client'", '"use client"'))


def _find_use_effect_blocks(content: str) -> list[tuple[int, str]]:
    """Return (line_number, block_text) for each useEffect in content."""
    blocks: list[tuple[int, str]] = []
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if "useEffect" in line and "=>" in line:
            # Collect the full useEffect block by counting braces
            depth = 0
            block_lines = []
            start_line = i + 1  # 1-indexed
            started = False
            for j in range(i, len(lines)):
                block_lines.append(lines[j])
                depth += lines[j].count("{") - lines[j].count("}")
                if "{" in lines[j]:
                    started = True
                if started and depth <= 0:
                    break
            blocks.append((start_line, "\n".join(block_lines)))
            i = j + 1 if "j" in dir() else i + 1
            continue
        i += 1
    return blocks


def _is_marked(lines: list[str], line_idx: int) -> bool:
    if line_idx >= len(lines):
        return False
    if "TODO_BUG(auto-memory-leak)" in lines[line_idx]:
        return True
    if line_idx > 0 and "TODO_BUG(auto-memory-leak)" in lines[line_idx - 1]:
        return True
    return False


def _extract_call_args(content: str, match_start: int) -> str | None:
    """Return the raw argument list for a function call starting at match_start."""
    open_paren = content.find("(", match_start)
    if open_paren == -1:
        return None

    depth = 0
    quote: str | None = None
    escaped = False
    for idx in range(open_paren, len(content)):
        char = content[idx]
        if quote is not None:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == quote:
                quote = None
            continue

        if char in {"'", '"', "`"}:
            quote = char
            continue
        if char == "(":
            depth += 1
            continue
        if char == ")":
            depth -= 1
            if depth == 0:
                return content[open_paren + 1 : idx]

    return None


def _split_top_level_args(raw_args: str) -> list[str]:
    """Split call arguments while ignoring nested commas."""
    args: list[str] = []
    start = 0
    depths = {"(": 0, "{": 0, "[": 0}
    quote: str | None = None
    escaped = False

    for idx, char in enumerate(raw_args):
        if quote is not None:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == quote:
                quote = None
            continue

        if char in {"'", '"', "`"}:
            quote = char
            continue
        if char == "(":
            depths["("] += 1
            continue
        if char == ")":
            depths["("] -= 1
            continue
        if char == "{":
            depths["{"] += 1
            continue
        if char == "}":
            depths["{"] -= 1
            continue
        if char == "[":
            depths["["] += 1
            continue
        if char == "]":
            depths["["] -= 1
            continue

        if char == "," and all(depth == 0 for depth in depths.values()):
            args.append(raw_args[start:idx].strip())
            start = idx + 1

    args.append(raw_args[start:].strip())
    return args


def _iter_short_interval_pollers(content: str) -> list[tuple[int, int, str]]:
    """Yield (line_number, interval_ms, callback_source) for short setInterval pollers."""
    pollers: list[tuple[int, int, str]] = []
    for match in _RE_SET_INTERVAL.finditer(content):
        raw_args = _extract_call_args(content, match.start())
        if raw_args is None:
            continue
        args = _split_top_level_args(raw_args)
        if len(args) < 2:
            continue

        raw_interval = args[1].replace("_", "").strip()
        try:
            interval_ms = int(raw_interval)
        except ValueError:
            continue
        if interval_ms >= 10_000:
            continue

        callback_source = args[0]
        if not _RE_POLLING_SIGNAL.search(callback_source):
            continue

        line_num = content[: match.start()].count("\n") + 1
        pollers.append((line_num, interval_ms, callback_source))

    return pollers


def _prune_stale_markers(project_root: Path, dry_run: bool) -> tuple[list[dict[str, Any]], list[str]]:
    """Remove TODO markers for issues that no longer reproduce."""
    actions: list[dict[str, Any]] = []
    changed_files: list[str] = []

    for client_skills_dir in get_all_client_skill_dirs(project_root):
        for ext in ("*.ts", "*.tsx"):
            for filepath in client_skills_dir.rglob(ext):
                parts = filepath.parts
                if any(p in parts for p in ("node_modules", ".next", "__tests__", "__mocks__", "tests")):
                    continue
                try:
                    rel = filepath.relative_to(project_root)
                except ValueError:
                    continue
                try:
                    content = filepath.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue

                lines = content.split("\n")
                if not any("TODO_BUG(auto-memory-leak)" in line for line in lines):
                    continue

                marker_free_lines = [
                    line for line in lines if "TODO_BUG(auto-memory-leak)" not in line
                ]
                active_issues = _scan_file(rel, "\n".join(marker_free_lines))
                active_keys = {
                    (issue["pattern"], issue["line"])
                    for issue in active_issues
                }

                next_lines: list[str] = []
                code_line = 0
                modified = False
                for line in lines:
                    marker_match = _RE_MARKER.match(line)
                    if marker_match:
                        pattern = marker_match.group("pattern")
                        target_line = code_line + 1
                        if (pattern, target_line) in active_keys:
                            next_lines.append(line)
                        else:
                            modified = True
                            actions.append(
                                {
                                    "status": "removed",
                                    "pattern": pattern,
                                    "file": str(rel),
                                    "line": target_line,
                                }
                            )
                        continue

                    next_lines.append(line)
                    code_line += 1

                if modified:
                    if not dry_run:
                        filepath.write_text("\n".join(next_lines), encoding="utf-8")
                    changed_files.append(str(rel))

    return actions, changed_files


def _scan_file(filepath: Path, content: str) -> list[dict[str, Any]]:
    """Scan a single file for memory leak patterns."""
    issues: list[dict[str, Any]] = []
    lines = content.split("\n")
    rel = str(filepath)
    is_client = _is_client_component(content)

    # --- 1. Module-level setInterval without globalThis guard ---
    if _RE_MODULE_INTERVAL.search(content) and not _RE_GLOBAL_THIS.search(content):
        for i, line in enumerate(lines, 1):
            if _RE_MODULE_INTERVAL.match(line.lstrip()) and not _is_marked(lines, i - 1):
                issues.append({
                    "file": rel,
                    "line": i,
                    "pattern": "hmr-unsafe-interval",
                    "severity": "high",
                    "message": f"Module-level setInterval without globalThis guard — leaks on HMR reload",
                })

    # --- 2. Unbounded module-level cache ---
    if _RE_MODULE_CACHE.search(content) and not _RE_MAX_GUARD.search(content):
        for i, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if _RE_MODULE_CACHE.match(stripped) and not _is_marked(lines, i - 1):
                # Check it's at module level (indent <= 2 or no function wrapper)
                indent = len(line) - len(stripped)
                if indent <= 2:
                    issues.append({
                        "file": rel,
                        "line": i,
                        "pattern": "unbounded-cache",
                        "severity": "medium",
                        "message": f"Module-level Map/Set without MAX size guard — grows without bound",
                    })

    # --- 3. useEffect with setInterval but no cleanup ---
    if is_client:
        for line_num, block in _find_use_effect_blocks(content):
            if _RE_SET_INTERVAL.search(block) and not _RE_USE_EFFECT_CLEANUP.search(block) and not _is_marked(lines, line_num - 1):
                issues.append({
                    "file": rel,
                    "line": line_num,
                    "pattern": "setInterval-without-cleanup",
                    "severity": "high",
                    "message": "setInterval in useEffect without clearInterval in cleanup return",
                })

    # --- 4. Aggressive polling (< 10s) for actual refresh/network loops ---
    for line_num, ms, _callback in _iter_short_interval_pollers(content):
        if not _is_marked(lines, line_num - 1):
            issues.append({
                "file": rel,
                "line": line_num,
                "pattern": "aggressive-polling",
                "severity": "medium",
                "message": f"Polling interval {ms}ms is under 10s — causes high CPU/network usage",
            })

    # --- 5. autoRefresh defaulting to true ---
    for i, line in enumerate(lines, 1):
        if ("autoRefresh" in line and "useState" in line and "true" in line) or \
           (_RE_AUTOREFRESH_TRUE.search(line) or _RE_AUTOREFRESH_TRUE_ALT.search(line)):
            if not _is_marked(lines, i - 1):
                issues.append({
                    "file": rel,
                    "line": i,
                    "pattern": "autorefresh-default-true",
                    "severity": "low",
                    "message": "autoRefresh defaults to true — prefer opt-in to reduce background load",
                })

    return issues


# ---------------------------------------------------------------------------
# OpsCommand: scan
# ---------------------------------------------------------------------------

def scan(ctx: OpsContext) -> ScanResult:
    """Scan skill source for memory leak patterns."""
    project_root = ctx.project_root

    all_issues: list[dict[str, Any]] = []
    n_files_scanned = 0
    for client_skills_dir in get_all_client_skill_dirs(project_root):
        for ext in ("*.ts", "*.tsx"):
            for filepath in client_skills_dir.rglob(ext):
                # Skip node_modules, .next, test files
                parts = filepath.parts
                if any(p in parts for p in ("node_modules", ".next", "__tests__", "__mocks__", "tests")):
                    continue
                try:
                    content = filepath.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                try:
                    rel = filepath.relative_to(project_root)
                except ValueError:
                    # Client skill discovery may include cached plugins outside the
                    # current repo; those are not part of this project's fix scope.
                    continue
                n_files_scanned += 1
                file_issues = _scan_file(rel, content)
                all_issues.extend(file_issues)

    # Deduplicate by (file, line, pattern)
    seen = set()
    unique: list[dict[str, Any]] = []
    for issue in all_issues:
        key = (issue["file"], issue["line"], issue["pattern"])
        if key not in seen:
            seen.add(key)
            unique.append(issue)

    high = sum(1 for i in unique if i["severity"] == "high")
    medium = sum(1 for i in unique if i["severity"] == "medium")
    low = sum(1 for i in unique if i["severity"] == "low")

    severity = "error" if high > 0 else "warning" if (medium > 0 or low > 0) else "info"

    return ScanResult(
        issues=unique,
        summary=f"Found {len(unique)} memory leak patterns ({high} high, {medium} medium, {low} low)",
        severity=severity,
        items_scanned=n_files_scanned,
    )


# ---------------------------------------------------------------------------
# OpsCommand: fix
# ---------------------------------------------------------------------------

def _commit_files(project_root: Path, files: list[str], message: str) -> bool:
    """Stage and commit files."""
    import subprocess as _subprocess

    try:
        _subprocess.run(
            ["git", "add"] + files,
            check=True,
            capture_output=True,
            cwd=str(project_root),
        )
        _subprocess.run(
            ["git", "commit", "-m", message],
            check=True,
            capture_output=True,
            cwd=str(project_root),
        )
        return True
    except _subprocess.CalledProcessError:
        return False


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Insert TODO_BUG markers for active issues and prune stale ones."""

    dry_run = ctx.dry_run
    project_root = ctx.project_root
    actions, changed_files = _prune_stale_markers(project_root, dry_run)

    if not issues:
        if changed_files and not dry_run:
            _commit_files(
                project_root,
                changed_files,
                f"fix(auto-memory-leak): remove {len(actions)} stale TODO_BUG markers",
            )
        summary = (
            f"{'Would remove' if dry_run else 'Removed'} {len(actions)} stale memory leak markers"
            if actions
            else "No memory leak issues to fix"
        )
        return FixResult(success=True, actions=actions, changes=changed_files, summary=summary)

    # Group issues by file
    by_file: dict[str, list[dict]] = {}
    for issue in issues:
        by_file.setdefault(issue["file"], []).append(issue)

    for rel_path, file_issues in by_file.items():
        filepath = project_root / rel_path
        if not filepath.exists():
            continue

        try:
            lines = filepath.read_text(encoding="utf-8").split("\n")
        except (OSError, UnicodeDecodeError):
            continue

        modified = False
        # Process in reverse line order to preserve line numbers
        for issue in sorted(file_issues, key=lambda i: i["line"], reverse=True):
            line_idx = issue["line"] - 1
            if line_idx < 0 or line_idx >= len(lines):
                continue

            marker = f"// TODO_BUG(auto-memory-leak): {issue['pattern']} — {issue['message']}"

            # Don't insert if marker already exists
            if "TODO_BUG(auto-memory-leak)" in lines[line_idx]:
                continue
            if line_idx > 0 and "TODO_BUG(auto-memory-leak)" in lines[line_idx - 1]:
                continue

            lines.insert(line_idx, marker)
            modified = True
            actions.append(
                {
                    "status": "marked",
                    "pattern": issue["pattern"],
                    "file": rel_path,
                    "line": issue["line"],
                }
            )

        if modified and not dry_run:
            filepath.write_text("\n".join(lines), encoding="utf-8")
            if str(rel_path) not in changed_files:
                changed_files.append(str(rel_path))

    if changed_files and not dry_run:
        _commit_files(
            project_root,
            changed_files,
            f"fix(auto-memory-leak): sync {len(actions)} memory leak TODO_BUG markers",
        )

    marked_count = sum(1 for action in actions if action["status"] == "marked")
    removed_count = sum(1 for action in actions if action["status"] == "removed")
    return FixResult(
        success=True,
        actions=actions,
        changes=changed_files,
        summary=(
            f"{'Would sync' if dry_run else 'Synced'} {len(actions)} memory leak markers "
            f"({marked_count} added, {removed_count} removed)"
        ),
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    project_root = Path(os.environ.get("AUGUR_PROJECT_ROOT", "."))
    ctx = OpsContext(project_root=project_root, dry_run=False)
    mode = sys.argv[1] if len(sys.argv) > 1 else "scan"
    if mode == "scan":
        result = scan(ctx)
    elif mode == "fix":
        result = fix(ctx, scan(ctx).issues)
    else:
        print(f"Usage: {sys.argv[0]} [scan|fix]", file=sys.stderr)
        sys.exit(1)

    if mode == "scan":
        payload = {
            "issues": result.issues,
            "summary": result.summary,
            "severity": result.severity,
        }
    else:
        payload = {
            "success": result.success,
            "actions": result.actions,
            "changes": result.changes,
            "summary": result.summary,
        }
    print(json.dumps(payload, indent=2))
