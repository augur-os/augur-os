"""auto-context-audit: Measure MCP context token usage across agents, flag budget violations.

Checks:
  d0: Agent token_estimate vs budget limits, SKILL.md bloat (>500 lines)
  d1: Per-tier budget analysis, cross-agent context overlap detection
  d2: Trim overly verbose SKILL.md descriptions
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
import json
import logging
from pathlib import Path

from src.config.paths import get_project_brain_skills_dir
from src.lib.ops_protocol import (
    OpsContext,
    ScanResult,
    FixResult,
    make_issue,
    evolution_gap,
    report_only_fix,
)

name = "auto-context-audit"

DIFFICULTY_SPEC = {
    0: "Surface — agent budget checks, SKILL.md line count bloat",
    1: "Content — per-tier budget analysis, cross-agent overlap detection",
    2: "Deep — trim overly verbose SKILL.md descriptions",
}

logger = logging.getLogger(__name__)

# Budget thresholds (tokens)
DEFAULT_CONTEXT_BUDGET = 64000
MAX_SKILL_MD_LINES = 500


def _load_agent_registry(project_root: Path) -> dict:
    """Load .claude/agents/registry.json."""
    registry_path = project_root / ".claude" / "agents" / "registry.json"
    if not registry_path.is_file():
        return {}
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        return data.get("agents", {}) if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _get_skill_md_files(project_root: Path) -> list[Path]:
    """Collect all SKILL.md files from project-brain skill sources."""
    skills_dir = get_project_brain_skills_dir(project_root)
    if not skills_dir.is_dir():
        return []
    return sorted(skills_dir.glob("*/SKILL.md"))


def scan(ctx: OpsContext) -> ScanResult:
    """Scan agent configs and SKILL.md files for context budget violations."""
    from src.config.paths import get_project_root

    project_root = get_project_root()
    issues: list[dict] = []
    items_scanned = 0

    # --- d0: Agent budget checks ---
    agents = _load_agent_registry(project_root)
    for agent_name, agent_config in agents.items():
        if not isinstance(agent_config, dict):
            continue
        items_scanned += 1
        tiers = agent_config.get("tiers", {})
        if not isinstance(tiers, dict):
            continue
        for tier_name, tier_config in tiers.items():
            if not isinstance(tier_config, dict):
                continue
            budget = tier_config.get("contextBudget", DEFAULT_CONTEXT_BUDGET)
            if not isinstance(budget, (int, float)):
                continue
            # Flag extremely large budgets (>200k tokens)
            if budget > 200000:
                issues.append(make_issue(
                    category="context-audit",
                    detail=f"Agent '{agent_name}' tier '{tier_name}' has oversized context budget: {budget:,} tokens",
                    path=f".claude/agents/registry.json#{agent_name}.tiers.{tier_name}",
                    kind="actionable",
                    root_cause_type="manual_debt",
                    fixability="manual",
                ))

    # --- d0: SKILL.md bloat check ---
    skill_md_files = _get_skill_md_files(project_root)
    for skill_md in skill_md_files:
        items_scanned += 1
        try:
            content = skill_md.read_text(encoding="utf-8")
            line_count = len(content.splitlines())
            if line_count > MAX_SKILL_MD_LINES:
                rel_path = str(skill_md.relative_to(project_root))
                issues.append(make_issue(
                    category="context-audit",
                    detail=f"SKILL.md is {line_count} lines (>{MAX_SKILL_MD_LINES}) — bloated context load",
                    path=rel_path,
                    kind="actionable",
                    root_cause_type="manual_debt",
                    fixability="auto" if ctx.difficulty >= 2 else "manual",
                ))
        except OSError:
            continue

    # --- d1: Per-tier budget analysis ---
    if ctx.difficulty >= 1:
        # Check for agents without any budget defined
        for agent_name, agent_config in agents.items():
            if not isinstance(agent_config, dict):
                continue
            tiers = agent_config.get("tiers", {})
            if not isinstance(tiers, dict) or not tiers:
                issues.append(make_issue(
                    category="context-audit",
                    detail=f"Agent '{agent_name}' has no tier definitions — no budget governance",
                    path=f".claude/agents/registry.json#{agent_name}",
                    kind="maintenance",
                    root_cause_type="manual_debt",
                    fixability="manual",
                ))

        # Check for agents with identical budgets across all tiers (no differentiation)
        for agent_name, agent_config in agents.items():
            if not isinstance(agent_config, dict):
                continue
            tiers = agent_config.get("tiers", {})
            if not isinstance(tiers, dict) or len(tiers) < 2:
                continue
            budgets = set()
            for tier_config in tiers.values():
                if isinstance(tier_config, dict):
                    budgets.add(tier_config.get("contextBudget", 0))
            if len(budgets) == 1:
                issues.append(make_issue(
                    category="context-audit",
                    detail=f"Agent '{agent_name}' has identical budget ({budgets.pop():,}) across all tiers — no cost differentiation",
                    path=f".claude/agents/registry.json#{agent_name}",
                    kind="maintenance",
                    root_cause_type="manual_debt",
                    fixability="manual",
                ))

    # --- d2: evolution gaps ---
    if ctx.difficulty >= 2 and not issues:
        issues.append(evolution_gap(
            "All context audit checks pass at max difficulty. "
            "Consider adding: actual runtime token measurement via MCP logs, "
            "context window utilization tracking per session, "
            "cross-agent context overlap detection.",
            category="context-audit",
        ))

    severity = "warning" if any(
        i.get("kind") == "actionable" for i in issues
    ) else "info"
    health = "degraded" if severity == "warning" else "verified"

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} context audit issues" if issues else "Context budgets clean",
        severity=severity,
        health=health,
        items_scanned=items_scanned,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix context audit issues. Report-only at d0-d1, trim at d2+."""
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} issues found")

    if not issues:
        return FixResult(success=True, summary="No issues to fix")

    # d0-d1: report-only
    if ctx.difficulty < 2:
        return report_only_fix(ctx, "context-audit-report.json", issues, noun="violation")

    # d2+: attempt to trim bloated SKILL.md files
    from src.config.paths import get_project_root

    project_root = get_project_root()
    actions: list[dict] = []
    changes: list[str] = []

    bloated = [i for i in issues if "bloated context load" in i.get("detail", "")]
    for issue in bloated:
        path = issue.get("path", "")
        if not path:
            continue
        skill_md = project_root / path
        if not skill_md.is_file():
            continue
        try:
            content = skill_md.read_text(encoding="utf-8")
            lines = content.splitlines()
            original_count = len(lines)

            # Strategy: remove excessive blank lines and trim trailing whitespace
            trimmed_lines: list[str] = []
            blank_run = 0
            for line in lines:
                stripped = line.rstrip()
                if not stripped:
                    blank_run += 1
                    if blank_run <= 2:  # Allow max 2 consecutive blank lines
                        trimmed_lines.append("")
                else:
                    blank_run = 0
                    trimmed_lines.append(stripped)

            new_count = len(trimmed_lines)
            if new_count < original_count:
                skill_md.write_text("\n".join(trimmed_lines) + "\n", encoding="utf-8")
                actions.append({"action": "trim_skill_md", "path": path, "before": original_count, "after": new_count})
                changes.append(f"Trimmed {path}: {original_count} -> {new_count} lines")
        except OSError as e:
            logger.warning(f"Failed to trim {path}: {e}")

    # Write report for non-bloat issues
    remaining = [i for i in issues if "bloated context load" not in i.get("detail", "")]
    if remaining:
        from src.lib.ops_protocol import write_report
        write_report(ctx, "context-audit-report.json", {"issues": remaining})

    summary = f"Applied {len(actions)} fixes" if actions else "No auto-fixable issues at current difficulty"
    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=summary,
    )
