"""auto-stale-actions: Detect and fix stale page: fields in action YAML files.

Extracted from HardeningLoop._scan_stale_action_pages and _fix_stale_action_page (ADR-200).

Scans discovered action YAML files from vault `actions/` overrides and
`assets/actions/*.yaml` for page: fields that do not match any route in
apps/dashboard/app/**/page.tsx, then regex-replaces stale values with the
resolved correct route.
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
from dataclasses import dataclass
from pathlib import Path

import yaml

from src.config.paths import get_all_client_skill_dirs, get_skill_root
from src.config.path_primitives import resolve_vault_standalone
from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, find_page_routes

name = "auto-stale-actions"


@dataclass(frozen=True)
class ActionFileRef:
    path: Path
    skill_name: str


def _commit_files(project_root: Path, message: str, paths: list[str]) -> str | None:
    """Stage specific paths and commit. Returns commit hash or None."""
    for p in paths:
        subprocess.run(
            ["git", "add", p],
            capture_output=True,
            cwd=str(project_root),
        )
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


def _discover_dashboard_routes(
    project_root: Path,
    shared_snapshot: dict | None = None,
) -> set[str]:
    """Walk apps/dashboard/app/**/page.tsx to build set of valid routes."""
    return {
        route.lstrip("/")
        for route in find_page_routes(project_root, shared_snapshot)
        if route and route != "/"
    }


def _iter_action_yaml_files(project_root: Path) -> list[ActionFileRef]:
    """Discover action YAML files with vault precedence and assets fallback."""
    action_files: list[ActionFileRef] = []
    seen: set[tuple[str, str]] = set()
    vault_root = resolve_vault_standalone()

    for client_skills_dir in get_all_client_skill_dirs(project_root):
        for skill_dir in sorted(client_skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_name = skill_dir.name
            hub = None
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                try:
                    meta, _body = parse_frontmatter(skill_md)
                    raw_hub = meta.get("x-augur-hub")
                    if isinstance(raw_hub, str) and raw_hub:
                        hub = raw_hub
                except OSError:
                    pass

            candidate_dirs: list[Path] = []
            if hub:
                candidate_dirs.append(vault_root / hub / skill_name / "actions")
            candidate_dirs.append(skill_dir / "assets" / "actions")

            for actions_dir in candidate_dirs:
                if not actions_dir.exists():
                    continue
                for action_yaml in sorted(actions_dir.glob("*.yaml")):
                    key = (skill_name, action_yaml.name)
                    if key in seen:
                        continue
                    seen.add(key)
                    action_files.append(ActionFileRef(path=action_yaml, skill_name=skill_name))

    return action_files


def _find_correct_route(
    stale_route: str,
    skill_name: str,
    known_routes: set[str],
) -> str | None:
    """Try to resolve the correct route for a stale page reference.

    Strategies:
    1. Prepend hub from SKILL.md x-augur-hub
    2. Suffix match against known routes (hub-aware)
    3. Skill-name match under known hub
    """
    hub = None
    try:
        skill_md = get_skill_root(skill_name) / "SKILL.md"
    except ValueError:
        skill_md = None

    if skill_md and skill_md.exists():
        try:
            meta, _body = parse_frontmatter(skill_md)
            raw_hub = meta.get("x-augur-hub")
            if isinstance(raw_hub, str) and raw_hub:
                hub = raw_hub
        except OSError:
            pass

    # Strategy 1: Prepend hub
    if hub:
        candidate = (
            f"{hub}/{stale_route}"
            if not stale_route.startswith(f"{hub}/")
            else stale_route
        )
        if candidate in known_routes:
            return f"/{candidate}"
        # Hub-root match for single-segment stale routes matching skill name
        if hub in known_routes and "/" not in stale_route:
            if stale_route == skill_name:
                return f"/{hub}"

    # Strategy 2: Suffix match
    suffix_matches = [
        r for r in known_routes
        if r.endswith(f"/{stale_route}") or r == stale_route
    ]
    if hub:
        hub_matches = [r for r in suffix_matches if r.startswith(f"{hub}/")]
        if len(hub_matches) == 1:
            return f"/{hub_matches[0]}"
    elif len(suffix_matches) == 1:
        return f"/{suffix_matches[0]}"

    # Strategy 3: Skill-name match under known hub
    last_segment = stale_route.split("/")[-1]
    if hub:
        for known in sorted(known_routes):
            if known.startswith(f"{hub}/") and last_segment in known.split("/"):
                return f"/{known}"

    return None


def scan(ctx: OpsContext) -> ScanResult:
    """Find action YAML files with stale page: fields."""
    known_routes = _discover_dashboard_routes(ctx.project_root, ctx.shared_snapshot)
    if not known_routes:
        return ScanResult(
            issues=[],
            summary="No dashboard routes discoverable",
            severity="info",
        )

    issues = []
    for action_ref in _iter_action_yaml_files(ctx.project_root):
        action_file = action_ref.path
        try:
            data = yaml.safe_load(action_file.read_text()) or {}
        except yaml.YAMLError:
            continue

        page = data.get("page")
        if not page:
            continue

        route = page.lstrip("/")
        if not route or route in known_routes:
            continue

        # Route is stale — try to resolve the correct one
        correct = _find_correct_route(route, action_ref.skill_name, known_routes)
        if correct:
            action_id = data.get("id", action_file.stem)
            issues.append({
                "action": f"fix-stale-page-{action_id}",
                "file": (
                    str(action_file.relative_to(ctx.project_root))
                    if action_file.is_relative_to(ctx.project_root)
                    else str(action_file)
                ),
                "file_path": str(action_file),
                "detail": f"page: {page} -> {correct}",
                "stale_page": page,
                "correct_page": correct,
            })

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} stale action page reference(s)",
        severity="warning" if issues else "info",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Regex-replace the stale page: field in each action YAML file and commit."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would fix {len(issues)} stale page reference(s)",
        )

    all_changes: list[str] = []
    all_actions: list[dict] = []
    overall_success = True

    for issue in issues:
        file_rel = issue.get("file", "")
        file_path_raw = issue.get("file_path", "")
        stale_page = issue.get("stale_page", "")
        correct_page = issue.get("correct_page", "")

        if not file_path_raw or not stale_page or not correct_page:
            overall_success = False
            all_actions.append({"skipped": file_rel, "reason": "incomplete issue data"})
            continue

        file_path = Path(file_path_raw)
        if not file_path.exists():
            overall_success = False
            all_actions.append({"failed": file_rel, "reason": "file not found"})
            continue

        content = file_path.read_text()
        new_content = re.sub(
            rf"^(page:\s*){re.escape(stale_page)}\s*$",
            rf"\g<1>{correct_page}",
            content,
            flags=re.MULTILINE,
        )

        if new_content == content:
            # No substitution — field not found or already correct
            all_actions.append({"skipped": file_rel, "reason": "no substitution made"})
            continue

        file_path.write_text(new_content)

        action_id = file_path.stem
        commit = None
        if file_path.is_relative_to(ctx.project_root):
            commit = _commit_files(
                ctx.project_root,
                f"fix(adaptive): update stale page ref in action '{action_id}'",
                paths=[str(file_path.relative_to(ctx.project_root))],
            )
        all_changes.append(file_rel)
        all_actions.append({"fixed": file_rel, "commit": commit})

    return FixResult(
        success=overall_success,
        actions=all_actions,
        changes=all_changes,
        summary=(
            f"Fixed {len(all_changes)} stale page reference(s)"
            if all_changes
            else "No changes made"
        ),
    )
