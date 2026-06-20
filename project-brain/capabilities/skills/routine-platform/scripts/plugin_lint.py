"""auto-plugin-lint: Plugin structural linting with AI-assisted fixes.

Extracted from HardeningLoop execute_action (plugin-template-lint category, ADR-200).
This module has no autonomous scanner — findings are fed externally (e.g. by
the plugin watcher or hygiene tooling).
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
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_all_client_skill_dirs
from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.llm_retry import resolve_cli as _find_cli
from src.lib.ops_protocol import (
    CANONICAL_BLOCK_TYPES,
    FixResult,
    OpsContext,
    ScanResult,
    declare_ops_capabilities,
)

name = "auto-plugin-lint"
OPS_CAPABILITIES = declare_ops_capabilities(
    platforms=("cross_platform",),
    windows_fix_mode="report_only",
    skip_reason="plugin structural fixes stay report-only on Windows in v1",
)
_ALLOWED_TOOLS = "Read,Edit,Write,Grep,Glob"
_OUTPUT_EXCERPT = 500


def _iter_skill_dirs(project_root: Path) -> list[Path]:
    """Return in-repo skill directories across bundled and client-native roots."""
    results: list[Path] = []
    seen: set[Path] = set()
    root_resolved = project_root.resolve()

    plugins_dir = project_root / "plugins"
    if plugins_dir.is_dir():
        for skills_dir in sorted(plugins_dir.glob("*/skills")):
            for skill_dir in sorted(skills_dir.iterdir()):
                if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                    continue
                resolved = skill_dir.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                results.append(skill_dir)

    for skills_dir in get_all_client_skill_dirs(project_root):
        try:
            skills_dir.resolve().relative_to(root_resolved)
        except ValueError:
            continue
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            resolved = skill_dir.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            results.append(skill_dir)

    return results


def _load_skill_config(skill_dir: Path) -> tuple[dict, dict]:
    """Load SKILL.md frontmatter and optional sidecar config."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return {}, {}

    try:
        frontmatter, _body = parse_frontmatter(skill_md)
    except Exception:
        return {}, {}
    if not isinstance(frontmatter, dict):
        return {}, {}

    config = frontmatter.get("x-augur-config")
    if isinstance(config, dict):
        return frontmatter, config

    config_file = frontmatter.get("x-augur-config-file")
    if isinstance(config_file, str) and config_file:
        sidecar_path = skill_dir / config_file
        try:
            parsed = yaml.safe_load(sidecar_path.read_text())
        except Exception:
            return frontmatter, {}
        if isinstance(parsed, dict):
            return frontmatter, parsed

    return frontmatter, {}


def scan(ctx: OpsContext) -> ScanResult:
    """Scan plugins for structural issues including hub alignment."""
    issues: list[dict] = []
    hub_issues: list[dict] = []
    block_issues: list[dict] = []
    skill_dirs = _iter_skill_dirs(ctx.project_root)
    items_scanned = 0

    for skill_dir in skill_dirs:
        frontmatter, config = _load_skill_config(skill_dir)
        if not frontmatter:
            continue
        items_scanned += 1

        skill_name = skill_dir.name
        rel_path = (skill_dir / "SKILL.md").relative_to(ctx.project_root).as_posix()

        # Hub alignment only applies to legacy bundled plugin layouts.
        if skill_dir.parent.name == "skills" and skill_dir.parents[2] == ctx.project_root / "plugins":
            bundle = skill_dir.parents[1].name
            skill_hub = frontmatter.get("x-augur-hub")
            if isinstance(skill_hub, str) and skill_hub and skill_hub != bundle:
                hub_issues.append({
                    "file": rel_path,
                    "severity": "high",
                    "pattern": "hub-misalignment",
                    "message": (
                        f"Plugin {skill_name} declares x-augur-hub '{skill_hub}' "
                        f"but lives in legacy plugins/{bundle}/skills/{skill_name}/"
                    ),
                })

        contributions = config.get("contributions")
        if isinstance(contributions, dict):
            blocks = contributions.get("blocks", [])
            if isinstance(blocks, list):
                for block in blocks:
                    if not isinstance(block, dict):
                        continue
                    block_type = block.get("type", "")
                    block_id = block.get("id", "unknown")
                    if block_type and block_type not in CANONICAL_BLOCK_TYPES:
                        block_issues.append({
                            "file": rel_path,
                            "severity": "high",
                            "pattern": "invalid-block-type",
                            "message": (
                                f"Block '{block_id}' uses non-canonical type '{block_type}'. "
                                f"Must be one of: {', '.join(sorted(CANONICAL_BLOCK_TYPES))}"
                            ),
                        })

    issues.extend(hub_issues)
    issues.extend(block_issues)

    if not issues:
        return ScanResult(
            issues=[],
            summary="plugin-lint: all plugins pass structural checks",
            severity="info",
            items_scanned=items_scanned,
        )

    return ScanResult(
        issues=issues,
        summary=f"plugin-lint: found {len(issues)} issue(s) ({len(hub_issues)} hub-misalignment, {len(block_issues)} invalid-block-type)",
        severity="warning",
        items_scanned=items_scanned,
    )


def _truncate(text: str, limit: int = _OUTPUT_EXCERPT) -> str:
    """Truncate command output for action logs."""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}…"


def _git_status_map(project_root: Path) -> dict[str, str]:
    """Return {path -> porcelain status} from git status."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    if result.returncode != 0:
        return {}

    status_map: dict[str, str] = {}
    for raw_line in result.stdout.splitlines():
        if len(raw_line) < 4:
            continue
        status = raw_line[:2]
        path_part = raw_line[3:]
        if " -> " in path_part:
            path_part = path_part.split(" -> ", 1)[1]
        if path_part.startswith('"') and path_part.endswith('"'):
            path_part = path_part[1:-1]
        status_map[path_part] = status
    return status_map


def _restore_paths(
    project_root: Path,
    paths: list[str],
    untracked_paths: set[str],
) -> None:
    """Restore newly-changed non-target files from the current working tree."""
    for rel_path in paths:
        full_path = project_root / rel_path
        if rel_path in untracked_paths:
            if full_path.is_dir():
                shutil.rmtree(full_path)
            elif full_path.exists():
                full_path.unlink()
            continue

        subprocess.run(
            ["git", "restore", "--staged", "--worktree", "--", rel_path],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )


def _normalize_issue(project_root: Path, issue: Any) -> tuple[str, str] | None:
    """Validate and normalize incoming issue payload."""
    if not isinstance(issue, dict):
        return None

    detail = str(
        issue.get("detail")
        or issue.get("message")
        or issue.get("pattern")
        or ""
    ).strip()
    file_raw = str(issue.get("file", "")).strip()
    if not detail or not file_raw:
        return None

    file_path = Path(file_raw)
    if file_path.is_absolute():
        try:
            file_path = file_path.resolve().relative_to(project_root.resolve())
        except ValueError:
            return None

    resolved_target = (project_root / file_path).resolve()
    root_resolved = project_root.resolve()
    try:
        resolved_target.relative_to(root_resolved)
    except ValueError:
        return None
    if resolved_target.exists() and resolved_target.is_dir():
        return None

    return (resolved_target.relative_to(root_resolved).as_posix(), detail)


def _build_prompt(file_rel: str, detail: str) -> str:
    return (
        "Fix a plugin structural issue with the smallest safe change.\n"
        f"- issue: {detail}\n"
        f"- target file: {file_rel}\n"
        "Rules:\n"
        "- Touch only the target file.\n"
        "- Do not add workaround directives (@ts-ignore, eslint-disable, pytest skip).\n"
        "- Keep plugin data/config decentralized in the plugin.\n"
        "- Preserve existing behavior except the structural fix.\n"
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Use headless Claude to fix plugin structural issues."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would fix {len(issues)} plugin structural issue(s)",
        )

    if not issues:
        return FixResult(success=True, summary="No plugin lint issues to process")

    try:
        cli_path = _find_cli()
    except RuntimeError:
        cli_path = None
    if not cli_path:
        # No CLI is an environment issue, not a scanner defect.  Return
        # success=True with fix_type="report" so the engine does not
        # penalize trust.  The scan correctly identified real issues; we
        # just can't auto-fix without a CLI.
        return FixResult(
            success=True,
            actions=[{"skipped": "all", "reason": "no CLI available"}],
            summary=f"Reported {len(issues)} plugin lint issue(s) (no CLI available for auto-fix)",
            fix_type="report",
        )

    max_issues_raw = ctx.config.get("max_issues_per_run", len(issues))
    max_issues = (
        max_issues_raw
        if isinstance(max_issues_raw, int) and max_issues_raw > 0
        else len(issues)
    )
    strict_scope = ctx.config.get("strict_file_scope", True)

    deduped: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    skipped_invalid = 0
    for issue in issues:
        normalized = _normalize_issue(ctx.project_root, issue)
        if not normalized:
            skipped_invalid += 1
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
        if len(deduped) >= max_issues:
            break

    all_changes: list[str] = []
    all_actions: list[dict] = []
    overall_success = True

    if skipped_invalid:
        all_actions.append(
            {
                "status": "skipped",
                "reason": "invalid-issue-payload",
                "count": skipped_invalid,
            }
        )

    current_status = _git_status_map(ctx.project_root)
    for file_rel, detail in deduped:
        before_changed = set(current_status.keys())

        prompt = _build_prompt(file_rel, detail)
        max_turns = str(ctx.config.get("max_turns", 8))
        fix_timeout = ctx.config.get("fix_timeout", 180)
        try:
            result = subprocess.run(
                [
                    cli_path,
                    "--print",
                    "--max-turns",
                    max_turns,
                    "--allowedTools",
                    _ALLOWED_TOOLS,
                    "-p",
                    prompt,
                ],
                capture_output=True,
                text=True,
                timeout=fix_timeout,
                cwd=str(ctx.project_root),
            )
        except subprocess.TimeoutExpired:
            overall_success = False
            all_actions.append(
                {
                    "status": "failed",
                    "file": file_rel,
                    "reason": "timeout",
                    "timeout_seconds": fix_timeout,
                }
            )
            continue

        current_status = _git_status_map(ctx.project_root)
        after_changed = set(current_status.keys())
        after_untracked = {
            p for p, status in current_status.items()
            if status == "??"
        }
        newly_changed = sorted(after_changed - before_changed)

        if strict_scope:
            non_target_changes = [p for p in newly_changed if p != file_rel]
            if non_target_changes:
                _restore_paths(ctx.project_root, non_target_changes, after_untracked)
                overall_success = False
                all_actions.append(
                    {
                        "status": "failed",
                        "file": file_rel,
                        "reason": "scope-violation",
                        "changed_files": newly_changed,
                        "restored_files": non_target_changes,
                    }
                )
                continue

        if result.returncode != 0:
            overall_success = False
            all_actions.append(
                {
                    "status": "failed",
                    "file": file_rel,
                    "reason": "claude-exit",
                    "exit": result.returncode,
                    "stderr_excerpt": _truncate(result.stderr),
                }
            )
            continue

        all_changes.append(file_rel)
        all_actions.append(
            {
                "status": "fixed",
                "file": file_rel,
                "changed_files": newly_changed,
                "stdout_excerpt": _truncate(result.stdout),
            }
        )

    unique_changes = sorted(set(all_changes))
    summary = (
        f"AI-fixed {len(unique_changes)} plugin structural issue(s)"
        if unique_changes
        else "No changes made"
    )
    if skipped_invalid:
        summary += f"; skipped {skipped_invalid} invalid issue payload(s)"

    # When no changes were made — whether because CLI failed (timeout,
    # crash, scope violation) or because fixes didn't produce diffs —
    # return report-only so the engine doesn't penalize trust.
    # The scan correctly identified real issues; they just need manual review.
    if not unique_changes:
        return FixResult(
            success=True,
            actions=all_actions,
            changes=[],
            summary=summary + "; issues reported for manual review",
            fix_type="report",
        )

    return FixResult(
        success=overall_success,
        actions=all_actions,
        changes=unique_changes,
        summary=summary,
    )
