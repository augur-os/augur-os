"""auto-flow-optimizer: Detect dispatch mode mismatches and performance issues.
Extracted from /ops-perf (ADR-200).

Scan: checks action YAML files for dispatch mode mismatches (e.g. fire for
actions that need LLM, ide for simple CRUD).
Fix: generates an optimization report with recommendations.

Note: RAG coverage gaps are handled by auto-rag-reindex (knowledge-enrichment loop).
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
import subprocess
from pathlib import Path

import yaml

from src.config.paths import get_all_client_skill_dirs
from src.config.path_primitives import resolve_vault_standalone
from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult


name = "auto-flow-optimizer"

# dispatch modes and their expected characteristics
_DISPATCH_HINTS = {
    "fire": {"needs_llm": False, "desc": "instant backend call"},
    "oneshot": {"needs_llm": True, "desc": "single LLM turn"},
    "chat": {"needs_llm": True, "desc": "multi-turn LLM conversation"},
    "ide": {"needs_llm": True, "desc": "IDE agent execution"},
    "escalation": {"needs_llm": True, "desc": "multi-agent escalation"},
}

# Keywords in descriptions that suggest LLM involvement
_LLM_KEYWORDS = ["generate", "analyze", "summarize", "draft", "write", "review", "ai", "llm", "claude"]
_SIMPLE_KEYWORDS = ["list", "status", "count", "refresh", "reindex", "cleanup", "delete"]

# Keys that mark an action as genuinely executable (it dispatches real work).
# An action carrying any of these triggers a backend/agent path and is subject to
# the dispatch-mode heuristic.
_EXECUTABLE_KEYS = ("command", "mcp_tool", "endpoint", "callable", "handler", "script")


def _is_descriptive_action(data: dict, action_id: str, action_yaml: Path) -> bool:
    """Return True for descriptive/non-executable actions (e.g. Browse overview cards).

    These actions only navigate to a page to *describe* a skill; they never invoke an
    LLM or backend, so ``dispatch: fire`` is correct even though their description
    necessarily mentions the AI/LLM skill being summarized. Flagging them as
    dispatch-mismatches is a false positive.

    Structural signal (preferred): the action has a ``page`` to navigate to and carries
    no executable callable. Convention fallback: id/filename ends with ``-overview``.
    """
    structural = bool(data.get("page")) and not any(data.get(key) for key in _EXECUTABLE_KEYS)
    convention = action_id.endswith("-overview") or action_yaml.stem.endswith("-overview")
    return structural or convention


def _iter_action_yaml_files(project_root: Path) -> list[tuple[str, Path]]:
    """Discover action YAML files with vault precedence and assets fallback."""
    action_files: list[tuple[str, Path]] = []
    seen: set[tuple[str, str]] = set()
    vault_root = resolve_vault_standalone()

    for skills_dir in get_all_client_skill_dirs(project_root):
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue

            skill_name = skill_dir.name
            skill_md = skill_dir / "SKILL.md"
            hub = None
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
                    action_files.append((skill_name, action_yaml))

    return action_files


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


def _scan_dispatch_mismatches(project_root: Path) -> list[dict]:
    """Find actions whose dispatch mode doesn't match their description."""
    issues: list[dict] = []

    for skill_name, action_yaml in _iter_action_yaml_files(project_root):
        try:
            data = yaml.safe_load(action_yaml.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue

        if not isinstance(data, dict):
            continue

        dispatch = data.get("dispatch", "fire")
        desc = (data.get("description", "") or "").lower()
        action_id = data.get("id", action_yaml.stem)
        file_display = (
            str(action_yaml.relative_to(project_root))
            if action_yaml.is_relative_to(project_root)
            else str(action_yaml)
        )

        # Descriptive overview cards only navigate to a page to summarize a skill; they
        # never dispatch an LLM/backend call, so dispatch: fire is correct even when the
        # description mentions the AI skill being described. Skip the heuristic for them.
        if _is_descriptive_action(data, action_id, action_yaml):
            continue

        # Check: fire dispatch with LLM-suggesting description
        if dispatch == "fire":
            if any(kw in desc for kw in _LLM_KEYWORDS):
                issues.append({
                    "action": "dispatch-mismatch",
                    "file": file_display,
                    "action_id": action_id,
                    "current_dispatch": dispatch,
                    "suggestion": "ide or oneshot",
                    "reason": "Description suggests LLM involvement but dispatch is 'fire'",
                })

        # Check: ide/chat dispatch with simple CRUD description
        elif dispatch in ("ide", "chat"):
            if any(kw in desc for kw in _SIMPLE_KEYWORDS) and not any(kw in desc for kw in _LLM_KEYWORDS):
                issues.append({
                    "action": "dispatch-mismatch",
                    "file": file_display,
                    "action_id": action_id,
                    "current_dispatch": dispatch,
                    "suggestion": "fire",
                    "reason": f"Description suggests simple operation but dispatch is '{dispatch}'",
                })

    return issues


def scan(ctx: OpsContext) -> ScanResult:
    dispatch_issues = _scan_dispatch_mismatches(ctx.project_root)

    if not dispatch_issues:
        return ScanResult(issues=[], summary="No dispatch mismatches found", severity="info")

    return ScanResult(
        issues=dispatch_issues,
        summary=f"Found {len(dispatch_issues)} dispatch mismatches",
        severity="warning",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} optimization opportunities")

    # Generate optimization report
    report_dir = ctx.project_root / "docs" / "generated"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / "flow-optimizer-report.md"

    lines = [
        "# Flow Optimization Report",
        "",
    ]

    if issues:
        lines.extend([
            "## Dispatch Mode Mismatches",
            "",
            "| Action | Current | Suggested | Reason |",
            "|--------|---------|-----------|--------|",
        ])
        for iss in issues:
            lines.append(
                f"| `{iss['action_id']}` | {iss['current_dispatch']} | {iss['suggestion']} | {iss['reason']} |"
            )
        lines.append("")

    report_file.write_text("\n".join(lines), encoding="utf-8")

    sha = _commit_files(
        ctx.project_root,
        "docs(adaptive): update flow optimization report",
        [str(report_file.relative_to(ctx.project_root))],
    )

    summary = f"Report generated: {len(issues)} dispatch mismatches"
    if sha:
        summary += f" (commit {sha})"

    return FixResult(success=True, changes=[str(report_file)], summary=summary)
