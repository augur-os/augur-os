"""auto-command-hub-coverage: repair stale legacy references in command docs."""
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
from pathlib import Path

import yaml

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, make_issue


name = "auto-command-hub-coverage"

DIFFICULTY_SPEC = {
    0: "Surface scan — find stale command-hub references",
    1: "Content check — resolve replacements against live skill and command paths",
    2: "Deep check — rewrite stale command-hub references in-place",
}

_MARKDOWN_GLOBS = ("SKILL.md", "references/*.md", "modules/*.md", "commands/*.md", "augur/modules/*.md")
_LEGACY_SKILL_PATH_RE = re.compile(r"plugins/([a-z-]+)/skills/([a-z0-9_-]+)(/[^\s`'\"<)]*)?")
_EXACT_REPLACEMENTS: dict[str, str] = {}


def _read_frontmatter(skill_md: Path) -> dict:
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    try:
        _, fm, _ = text.split("---", 2)
    except ValueError:
        return {}
    data = yaml.safe_load(fm) or {}
    return data if isinstance(data, dict) else {}


def _iter_command_markdown_files(project_root: Path) -> list[Path]:
    files: list[Path] = []
    for skill_md in sorted((project_root / "project-brain" / "capabilities" / "skills").glob("*/SKILL.md")):
        fm = _read_frontmatter(skill_md)
        if fm.get("x-augur-hub") != "command":
            continue
        skill_dir = skill_md.parent
        for pattern in _MARKDOWN_GLOBS:
            files.extend(sorted(skill_dir.glob(pattern)))
    return sorted(set(files))


def _replacement_path(project_root: Path, match: re.Match[str]) -> str | None:
    bundle, skill, suffix = match.group(1), match.group(2), match.group(3) or ""
    del bundle
    new_root = project_root / "project-brain" / "capabilities" / "skills" / skill
    if not new_root.exists():
        return None
    normalized_suffix = suffix.lstrip("/")
    candidate = new_root / normalized_suffix if normalized_suffix else new_root
    if candidate.exists() or candidate.parent.exists():
        replacement = f"project-brain/capabilities/skills/{skill}"
        if suffix:
            replacement += suffix
        return replacement
    return None


def _find_replacements(project_root: Path, text: str) -> list[dict]:
    replacements: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for old, new in _EXACT_REPLACEMENTS.items():
        if old in text:
            key = (old, new)
            if key not in seen:
                seen.add(key)
                replacements.append({"old": old, "new": new})

    for match in _LEGACY_SKILL_PATH_RE.finditer(text):
        old = match.group(0)
        new = _replacement_path(project_root, match)
        if not new:
            continue
        key = (old, new)
        if key in seen:
            continue
        seen.add(key)
        replacements.append({"old": old, "new": new})

    return replacements


def scan(ctx: OpsContext) -> ScanResult:
    issues: list[dict] = []
    for md_file in _iter_command_markdown_files(ctx.project_root):
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            continue
        replacements = _find_replacements(ctx.project_root, text)
        if not replacements:
            continue
        rel_path = str(md_file.relative_to(ctx.project_root))
        issues.append(make_issue(
            category=name,
            path=rel_path,
            detail=(
                f"{md_file.name} still references legacy or removed command-hub paths. "
                f"Next: rewrite {len(replacements)} reference(s) to live command, daemon, or skill locations."
            ),
            root_cause_type="stale_reference",
            fixability="auto",
            replacements=replacements,
        ))

    if not issues:
        return ScanResult(
            issues=[],
            summary="Command hub markdown references are aligned with the live skill layout",
            severity="info",
            health="verified",
        )

    return ScanResult(
        issues=issues,
        summary=f"Found {len(issues)} command markdown file(s) with stale legacy references",
        severity="warning",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix stale command hub references.

    d0: Report summary only.
    d1+: Rewrite stale legacy paths to current skill layout in-place.
    """
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} command doc fix(es)")

    if not issues:
        return FixResult(success=True, summary="No command hub issues to fix")

    if ctx.difficulty < 1:
        total_replacements = sum(len(i.get("replacements", [])) for i in issues)
        return FixResult(
            success=True,
            summary=f"{len(issues)} file(s) with {total_replacements} stale reference(s) (report only at d0)",
            fix_type="report",
        )

    changes: list[str] = []
    actions: list[dict] = []
    for issue in issues:
        rel_path = issue.get("path", "")
        replacements = issue.get("replacements", [])
        if not rel_path or not replacements:
            continue
        target = ctx.project_root / rel_path
        if not target.exists():
            continue
        try:
            original = target.read_text(encoding="utf-8")
        except OSError:
            continue
        updated = original
        applied: list[dict] = []
        for item in replacements:
            old = item.get("old", "")
            new = item.get("new", "")
            if not old or not new:
                continue
            if old in updated:
                updated = updated.replace(old, new)
                applied.append({"old": old, "new": new})
        if updated == original:
            continue
        target.write_text(updated, encoding="utf-8")
        changes.append(rel_path)
        actions.append({
            "file": rel_path,
            "status": "fixed",
            "replacements": applied,
        })

    if not changes:
        return FixResult(success=True, summary="No command hub reference changes were required", fix_type="verified")

    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=f"Repaired stale command hub references in {len(changes)} markdown file(s)",
        fix_type="code-fix",
    )
