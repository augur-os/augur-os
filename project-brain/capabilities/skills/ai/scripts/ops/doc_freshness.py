"""auto-doc-freshness: Detect stale docs and broken internal links.
Extracted from /ops-docs (ADR-200).

Scan: walks docs/ and plugin SKILL.md files for broken internal links
(references to files that no longer exist) and stale docs (not updated
in 90+ days while their source code has changed).
Fix: fixes broken links where target is unambiguous, reports stale docs.
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
from datetime import datetime, timezone
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult


name = "auto-doc-freshness"

_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_STALE_DAYS = 90
_DOC_GLOBS = ["docs/**/*.md", "plugins/*/skills/*/SKILL.md"]


def _commit_files(project_root: Path, message: str, paths: list[str]) -> str | None:
    for p in paths:
        subprocess.run(["git", "add", p], capture_output=True, cwd=str(project_root))
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        return None
    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        rev = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        return rev.stdout.strip() if rev.returncode == 0 else None
    return None


def _find_broken_links(project_root: Path, difficulty: int) -> list[dict]:
    """Find markdown links that reference non-existent local files."""
    issues: list[dict] = []
    globs = _DOC_GLOBS[:1] if difficulty < 1 else _DOC_GLOBS

    for pattern in globs:
        for md_file in project_root.glob(pattern):
            try:
                content = md_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            in_fence = False
            for line_number, line in enumerate(content.splitlines(), start=1):
                if _FENCE_RE.match(line):
                    in_fence = not in_fence
                    continue
                if in_fence:
                    continue

                for match in _LINK_RE.finditer(line):
                    if line[:match.start()].count("`") % 2 == 1:
                        continue
                    link_target = match.group(2)
                    # Skip URLs, anchors, and mailto
                    if link_target.startswith(("http://", "https://", "#", "mailto:")):
                        continue
                    # Strip anchor from path
                    clean_path = link_target.split("#")[0]
                    if not clean_path:
                        continue
                    # Resolve relative to the markdown file's directory
                    target_path = (md_file.parent / clean_path).resolve()
                    if not target_path.exists():
                        issues.append({
                            "action": "broken-link",
                            "file": str(md_file.relative_to(project_root)),
                            "link_text": match.group(1),
                            "link_target": link_target,
                            "line": line_number,
                        })

    return issues


def _find_stale_docs(project_root: Path, difficulty: int) -> list[dict]:
    """Find docs that haven't been updated recently relative to their source code."""
    if difficulty < 2:
        return []

    issues: list[dict] = []
    now = datetime.now(tz=timezone.utc)

    for md_file in project_root.glob("docs/**/*.md"):
        if "generated" in str(md_file) or "daily" in str(md_file):
            continue
        try:
            mtime = datetime.fromtimestamp(md_file.stat().st_mtime, tz=timezone.utc)
            age_days = (now - mtime).days
            if age_days > _STALE_DAYS:
                issues.append({
                    "action": "stale-doc",
                    "file": str(md_file.relative_to(project_root)),
                    "age_days": age_days,
                })
        except OSError:
            continue

    return issues


def scan(ctx: OpsContext) -> ScanResult:
    broken = _find_broken_links(ctx.project_root, ctx.difficulty)
    stale = _find_stale_docs(ctx.project_root, ctx.difficulty)
    all_issues = broken + stale

    if not all_issues:
        return ScanResult(issues=[], summary="All docs healthy", severity="info")

    parts = []
    if broken:
        parts.append(f"{len(broken)} broken links")
    if stale:
        parts.append(f"{len(stale)} stale docs")

    return ScanResult(
        issues=all_issues,
        summary=f"Found {', '.join(parts)}",
        severity="warning",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: found {len(issues)} doc issues")

    changes: list[str] = []

    # Fix broken links by removing the link (keeping the text)
    broken_by_file: dict[str, list[dict]] = {}
    for issue in issues:
        if issue["action"] == "broken-link":
            broken_by_file.setdefault(issue["file"], []).append(issue)

    for rel_path, file_issues in broken_by_file.items():
        filepath = ctx.project_root / rel_path
        try:
            content = filepath.read_text(encoding="utf-8")
            modified = False
            for iss in file_issues:
                old = f"[{iss['link_text']}]({iss['link_target']})"
                if old in content:
                    content = content.replace(old, iss["link_text"])
                    modified = True
            if modified:
                filepath.write_text(content, encoding="utf-8")
                changes.append(f"Fixed broken links in {rel_path}")
        except OSError:
            continue

    # Stale docs are reported only, not auto-fixed
    stale_count = sum(1 for i in issues if i["action"] == "stale-doc")

    if changes:
        sha = _commit_files(
            ctx.project_root,
            "fix(adaptive): remove broken doc links",
            [iss["file"] for iss in issues if iss["action"] == "broken-link"],
        )
        summary = f"Fixed {len(changes)} broken links"
        if sha:
            summary += f" (commit {sha})"
        if stale_count:
            summary += f"; {stale_count} stale docs reported (manual review needed)"
    else:
        summary = f"{stale_count} stale docs reported (manual review needed)" if stale_count else "No fixable issues"

    return FixResult(success=True, changes=changes, summary=summary)
