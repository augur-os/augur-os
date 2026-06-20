"""auto-life-hub-coverage: repair stale legacy references in life docs."""
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
from pathlib import Path

import yaml

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, make_issue


name = "auto-life-hub-coverage"

DIFFICULTY_SPEC = {
    0: "Surface scan — find stale life-hub references",
    1: "Content check — resolve replacements against live skill data and script paths",
    2: "Deep check — rewrite stale life-hub references in-place",
}

_MARKDOWN_GLOBS = ("SKILL.md", "references/*.md", "modules/*.md", "commands/*.md", "augur/modules/*.md")
_EXACT_REPLACEMENTS = {
    "augur/data/notes/": 'get_skill_data_dir("<skill>") / "notes/"',
    "plugins/*/skills/*/augur/data/notes/": 'get_skill_data_dir("<skill>") / "notes/"',
    "skills/health/augur/data/": 'get_skill_data_dir("health") / ""',
    "skills/health/augur/data/virtual-doctor.yaml": 'get_skill_data_dir("health") / "virtual-doctor.yaml"',
    "plugins/admin/skills/channels/scripts/fetch_patch.py": "project-brain/capabilities/skills/channels/scripts/fetch_patch.py",
    "plugins/admin/skills/channels/scripts/verify_patch.py": "project-brain/capabilities/skills/channels/scripts/verify_patch.py",
}


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


def _iter_life_markdown_files(project_root: Path) -> list[Path]:
    files: list[Path] = []
    for skill_md in sorted((project_root / "project-brain" / "capabilities" / "skills").glob("*/SKILL.md")):
        fm = _read_frontmatter(skill_md)
        if fm.get("x-augur-hub") != "life":
            continue
        skill_dir = skill_md.parent
        for pattern in _MARKDOWN_GLOBS:
            files.extend(sorted(skill_dir.glob(pattern)))
    return sorted(set(files))


def _find_replacements(text: str) -> list[dict]:
    replacements: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for old, new in _EXACT_REPLACEMENTS.items():
        if old in text:
            key = (old, new)
            if key in seen:
                continue
            seen.add(key)
            replacements.append({"old": old, "new": new})
    return replacements


def scan(ctx: OpsContext) -> ScanResult:
    issues: list[dict] = []
    for md_file in _iter_life_markdown_files(ctx.project_root):
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            continue
        replacements = _find_replacements(text)
        if not replacements:
            continue
        rel_path = str(md_file.relative_to(ctx.project_root))
        issues.append(make_issue(
            category=name,
            path=rel_path,
            detail=(
                f"{md_file.name} still references stale life-hub data or script paths. "
                f"Next: rewrite {len(replacements)} reference(s) to live vault-backed data or skill scripts."
            ),
            root_cause_type="stale_reference",
            fixability="auto",
            replacements=replacements,
        ))

    if not issues:
        return ScanResult(
            issues=[],
            summary="Life hub markdown references are aligned with live data and script locations",
            severity="info",
            health="verified",
        )

    return ScanResult(
        issues=issues,
        summary=f"Found {len(issues)} life markdown file(s) with stale references",
        severity="warning",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} life doc fix(es)")

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
        original = target.read_text(encoding="utf-8")
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
        return FixResult(success=True, summary="No life hub reference changes were required", fix_type="verified")

    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=f"Repaired stale life hub references in {len(changes)} markdown file(s)",
        fix_type="code-fix",
    )
