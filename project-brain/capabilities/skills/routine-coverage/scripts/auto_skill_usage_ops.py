"""auto-skill-usage: Analyze skill invocation logs for usage patterns.

Reads ~/Library/Logs/Augur/skill-usage.jsonl (written by the PreToolUse
hook in scripts/hooks/skill-usage-tracker.sh) and cross-references against
registered skills to find undertriggered and popular skills.

Difficulty levels:
  d0: Report undertriggered skills (0 invocations in 30 days)
  d1: Also report popular skills (>50 invocations) as upgrade candidates
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
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.config.paths import get_logs_dir, get_project_brain_skills_dir
from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    evolution_gap,
    make_issue,
)

name = "auto-skill-usage"

DIFFICULTY_SPEC = {
    0: "Report undertriggered skills (0 invocations in 30 days)",
    1: "Also report popular skills (>50 invocations) as upgrade candidates",
}

_WINDOW_DAYS = 30
_POPULAR_THRESHOLD = 50


def _load_usage_log(log_file: Path, cutoff: datetime) -> Counter:
    """Parse skill-usage.jsonl and return invocation counts since cutoff.

    Skips malformed lines instead of failing (Gotcha #2).
    """
    counts: Counter = Counter()
    if not log_file.exists():
        return counts

    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue

            ts_str = entry.get("ts", "")
            skill = entry.get("skill", "")
            if not skill or skill == "unknown":
                continue

            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue

            if ts >= cutoff:
                counts[skill] += 1

    return counts


def _discover_skills(project_root: Path) -> list[str]:
    """List all project-brain skill names."""
    skills_dir = get_project_brain_skills_dir(project_root)
    if not skills_dir.is_dir():
        return []
    return sorted(
        d.name
        for d in skills_dir.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    )


def _skill_aliases(project_root: Path, all_skills: list[str]) -> dict[str, str]:
    """Map generated command/client skill names back to source skill names."""
    skills_dir = get_project_brain_skills_dir(project_root)
    aliases: dict[str, str] = {}
    for skill_name in all_skills:
        skill_dir = skills_dir / skill_name
        aliases[skill_name] = skill_name
        aliases[f"augur:{skill_name}"] = skill_name

        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            meta, _body = parse_frontmatter(skill_md, include_sidecar_config=False)
            commands = meta.get("x-augur-commands") or []
            if isinstance(commands, list):
                for command in commands:
                    if not isinstance(command, dict):
                        continue
                    command_id = command.get("id")
                    if isinstance(command_id, str) and command_id:
                        aliases[command_id] = skill_name
                        aliases[f"augur:{command_id}"] = skill_name

        command_dir = skill_dir / "commands"
        if command_dir.is_dir():
            for command_file in command_dir.glob("*.md"):
                aliases[command_file.stem] = skill_name
                aliases[f"augur:{command_file.stem}"] = skill_name

    return aliases


def _canonicalize_counts(
    counts: Counter,
    aliases: dict[str, str],
    all_skills: list[str],
) -> Counter:
    """Convert logged wrapper names into canonical source-skill counts."""
    valid_skills = set(all_skills)
    canonical: Counter = Counter()
    for logged_name, count in counts.items():
        skill_name = aliases.get(logged_name)
        if skill_name is None and isinstance(logged_name, str) and logged_name.startswith("augur:"):
            skill_name = aliases.get(logged_name.split(":", 1)[1])
        if skill_name in valid_skills:
            canonical[skill_name] += count
    return canonical


# -- Scan ------------------------------------------------------------------


def scan(ctx: OpsContext) -> ScanResult:
    """Analyze skill usage logs and report undertriggered/popular skills."""
    log_file = get_logs_dir() / "skill-usage.jsonl"
    cutoff = datetime.now(timezone.utc) - timedelta(days=_WINDOW_DAYS)

    # Load usage data
    counts = _load_usage_log(log_file, cutoff)

    # Discover all registered skills
    all_skills = _discover_skills(ctx.project_root)

    if not all_skills:
        return ScanResult(
            issues=[],
            summary="No skills found in skills/",
            severity="info",
            health="verified",
        )

    if not log_file.exists():
        return ScanResult(
            issues=[],
            summary="No usage log yet (skill-usage.jsonl does not exist). "
                    "Invoke a skill to start tracking.",
            severity="info",
            health="verified",
        )

    counts = _canonicalize_counts(counts, _skill_aliases(ctx.project_root, all_skills), all_skills)
    issues: list[dict] = []

    # Undertriggered: registered skills with 0 invocations
    undertriggered = [s for s in all_skills if counts.get(s, 0) == 0]
    for skill_name in undertriggered:
        issues.append(make_issue(
            category="skill-usage",
            detail=f"Skill '{skill_name}' has 0 invocations in the last "
                   f"{_WINDOW_DAYS} days — may need a better description or "
                   f"is genuinely unused",
            path=f"skills/{skill_name}/SKILL.md",
            kind="maintenance",
            root_cause_type="usage_observation",
            fixability="manual",
        ))

    # Popular skills at difficulty >= 1
    if ctx.difficulty >= 1:
        popular = [
            (skill, count)
            for skill, count in counts.most_common()
            if count > _POPULAR_THRESHOLD
        ]
        for skill_name, count in popular:
            issues.append(make_issue(
                category="skill-usage",
                detail=f"Skill '{skill_name}' has {count} invocations in "
                       f"{_WINDOW_DAYS} days — popular, prioritize for "
                       f"quality upgrades",
                path=f"skills/{skill_name}/SKILL.md",
                kind="maintenance",
                root_cause_type="manual_debt",
                fixability="manual",
            ))

    # Evolution gap: at max difficulty with no issues
    if ctx.difficulty >= 1 and not issues:
        issues.append(evolution_gap(
            "All skills have balanced usage — consider tracking per-action "
            "invocation breakdown and error rates. Next: extend hook to log "
            "action IDs and success/failure status.",
            category="skill-usage",
        ))

    total_invocations = sum(counts.values())
    active_skills = sum(1 for s in all_skills if counts.get(s, 0) > 0)
    summary = (
        f"{total_invocations} mapped invocations across {active_skills}/"
        f"{len(all_skills)} source skills in {_WINDOW_DAYS}d. "
        f"{len(undertriggered)} undertriggered."
    )

    severity = "warning" if undertriggered else "info"
    health = "verified"

    return ScanResult(
        issues=issues,
        summary=summary,
        severity=severity,
        health=health,
        items_scanned=len(all_skills),
    )


# -- Fix -------------------------------------------------------------------


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Usage analysis is report-only — no automated fixes."""
    return FixResult(
        success=True,
        summary=f"Reported {len(issues)} skill usage observations. "
                f"Review undertriggered skills for description improvements.",
        fix_type="report",
    )
